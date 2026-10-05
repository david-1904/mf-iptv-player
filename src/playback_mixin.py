"""
Wiedergabe: Stream-Steuerung, Timeshift, Buffering, Player-Maximierung, Info-Overlay
"""
import asyncio
import aiohttp
import time
from datetime import datetime

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import QListWidgetItem

from xtream_api import LiveStream, VodStream, Series, EpgEntry, dedupe_epg
from watch_history_manager import WatchEntry
from favorites_manager import Favorite
from i18n import _tr
from ui_builder import _pi
from layout_constants import FULLSCREEN_CONTROLS_MIN_HEIGHT, FULLSCREEN_CONTROLS_MAX_HEIGHT_RATIO


class PlaybackMixin:

    @Slot(QListWidgetItem)
    def _on_channel_selected(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if not data:
            return

        # Aufnahmen brauchen kein API
        if isinstance(data, tuple) and len(data) == 2 and data[0] == "recording":
            filepath = data[1]
            name = filepath.stem.replace("_", " ")
            self._play_stream(str(filepath), name, "vod")
            return

        # Geplante Aufnahme: Abbrechen-Dialog
        if isinstance(data, tuple) and len(data) == 2 and data[0] == "scheduled":
            from PySide6.QtWidgets import QMessageBox
            rec = data[1]
            label = rec.channel_name
            if rec.epg_title:
                label += f" \u2013 {rec.epg_title}"
            reply = QMessageBox.question(
                self, _tr("Geplante Aufnahme"),
                _tr("Aufnahme abbrechen?") + f"\n{label}",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                if rec.status == "recording" or self.recorder.is_recording:
                    self.recorder.stop()
                    self._sync_record_buttons(False)
                self.schedule_manager.remove(rec.id)
                self._load_recordings()
            return

        if not self.api:
            return

        if isinstance(data, LiveStream):
            self._play_live_stream(data)

        elif isinstance(data, VodStream):
            self._show_vod_detail(data)

        elif isinstance(data, Series):
            self._show_series_detail(data)

        elif isinstance(data, WatchEntry):
            if data.stream_type == "live":
                url = self.api.creds.stream_url(data.stream_id)
                self._play_stream(url, data.title, "live", data.stream_id, icon=data.icon)
            elif data.stream_type == "vod":
                vod = VodStream(
                    stream_id=data.stream_id, name=data.title,
                    stream_icon=data.icon,
                    container_extension=data.container_extension or "mp4"
                )
                self._show_vod_detail(vod)

        elif isinstance(data, Favorite):
            if data.type == "live":
                url = self.api.creds.stream_url(data.id)
                self._play_stream(url, data.name, "live", data.id, icon=data.icon or "")
            elif data.type == "vod":
                vod = VodStream(
                    stream_id=data.id, name=data.name,
                    stream_icon=data.icon,
                    container_extension=data.container_extension or "mp4"
                )
                self._show_vod_detail(vod)
            elif data.type == "series":
                s = Series(series_id=data.id, name=data.name, cover=data.icon)
                self._show_series_detail(s)

    def _play_live_stream(self, data: LiveStream):
        # Sender-State fuer EPG-Detail-Toggle merken
        self._detail_stream_data = data
        self._current_epg_stream_id = data.stream_id
        self._current_epg_has_catchup = getattr(data, 'tv_archive', False)
        self.epg_channel_name.setText(data.name)
        self._playing_channel_name = data.name
        asyncio.ensure_future(self._load_epg(data.stream_id))
        url = self.api.creds.stream_url(data.stream_id)
        self._play_stream(url, data.name, "live", data.stream_id, icon=data.stream_icon)
        QTimer.singleShot(350, self._show_info_overlay_zap)
        if data.category_id:
            account = self.account_manager.get_selected()
            if account:
                self.session_manager.save_live(
                    account.name, data.stream_id, data.name, data.stream_icon, data.category_id
                )

    def _play_stream(self, url: str, title: str, stream_type: str = "live", stream_id: int = None, icon: str = "", container_extension: str = "", start: float = 0.0):
        """Spielt einen Stream im integrierten Player ab"""
        # Reconnect-Zustand zuruecksetzen
        self._stream_starting = True  # end-file waehrend Verbindungsaufbau ignorieren
        self._vod_eof_received = False  # Reset: Buffering-Overlay wieder erlauben
        self._vod_has_played = False    # Reset: noch nicht angespielt
        self._stream_start_timer.start(5000)  # Sicherheitsnetz: nach 5s aufheben
        self._reconnect_attempt = 0
        self._reconnect_timer.stop()
        self._buffering_watchdog.stop()
        self._buffering_accumulated = 0.0
        self._buffering_since = None
        self._buffering_text = _tr("Laden")
        self._hide_stream_error()
        # Vorherige Position speichern
        self._save_current_position()

        self.player_title.setText(title)

        # Logo nur bei echtem Senderwechsel oder explizitem neuem Icon zuruecksetzen.
        # Bei Catchup/Timeshift (gleicher stream_id, kein icon) bleibt das Logo erhalten.
        if icon:
            self._current_stream_icon = icon
            self.player_channel_logo.clear()
            self.player_channel_logo.hide()
        elif stream_id is None or stream_id != self._current_playing_stream_id:
            self._current_stream_icon = ""
            self.player_channel_logo.clear()
            self.player_channel_logo.hide()
            # EPG-Einträge für Overlay zurücksetzen damit kein altes EPG erscheint
            self._detail_now_entry = None
            self._detail_next_entry = None
        # else: gleicher Sender (Catchup/Seek) → icon + Logo + EPG behalten

        # EPG-Bar sofort leeren damit kein altes EPG bleibt, wenn neuer Sender kein EPG hat
        self.live_epg_bar.hide()

        self._current_stream_type = stream_type
        self._current_playing_stream_id = stream_id
        # Ab hier bestimmt die Wiedergabe das Layout — ein evtl. vor einer
        # Detailansicht gespeicherter Zustand ist damit hinfaellig.
        self._detail_saved_layout = None

        # Logo sofort laden (oder aus Cache anzeigen) — kein Hover noetig
        if self._current_stream_icon:
            asyncio.ensure_future(self._load_overlay_logo(self._current_stream_icon))
        self._current_stream_title = title
        self._current_container_ext = container_extension
        self._current_stream_url = url
        self._timeshift_active = False
        self._timeshift_paused_at = 0
        self._timeshift_start_ts = 0.0

        is_vod_playback = stream_type == "vod"

        # PiP immer beenden wenn eine Aufnahme / VOD gestartet wird —
        # sonst bleibt der Player als floating Overlay (recording spielt im Mini-Fenster)
        if self._pip_mode and is_vod_playback:
            self._exit_pip_mode()

        if not self.player_area.isVisible():
            if is_vod_playback:
                # Film/Serie/Aufnahme: Player ueber volle Breite, Kanalliste ausblenden
                self.channel_area.hide()
                self.player_area.show()
            else:
                # Live-TV: side-by-side mit Kanalliste
                self.channel_area.setFixedWidth(self._live_channel_width())
                self.player_area.show()
        elif is_vod_playback and self.channel_area.isVisible():
            self.channel_area.hide()
        elif self._pip_mode and not is_vod_playback:
            self._exit_pip_mode()
        self._update_live_idle_panel()

        self._update_seek_controls_visibility()
        if not getattr(self, '_keep_detail_open', False):
            self._hide_channel_detail()
            self._playing_catchup_entry = None
        self.player.play(url, seekable=stream_type == "vod", start=start)
        self.btn_play_pause.setIcon(getattr(self, '_icon_pause', self.btn_play_pause.icon()))
        self.player_info_label.setText("")
        self.controls_timer.start(1000)
        self.status_bar.showMessage(_tr("Wiedergabe: {}").format(title), 4000)

        # Verlaufseintrag anlegen
        account = self.account_manager.get_selected()
        if account and stream_id is not None:
            # Gespeicherte Position nicht mit 0 ueberschreiben, bevor der Film laeuft
            _, prev_dur = self.history_manager.get_position(stream_id, stream_type, account.name)
            entry = WatchEntry(
                stream_id=stream_id,
                stream_type=stream_type,
                account_name=account.name,
                title=title,
                icon=icon,
                position=start,
                duration=prev_dur if start > 0 else 0.0,
                container_extension=container_extension,
            )
            self.history_manager.add_or_update(entry)

    def _stop_playback(self):
        """Stoppt die Wiedergabe und versteckt den Player"""
        self._stream_starting = False
        self._stream_start_timer.stop()
        self._reconnect_attempt = 0
        self._reconnect_timer.stop()
        self._buffering_watchdog.stop()
        self._save_current_position()
        if self.recorder.is_recording:
            self.recorder.stop()
            self._update_record_button()
        self.player.stop()
        self.buffering_overlay.hide()
        self._hide_stream_error()
        self.info_overlay.hide()
        self._info_overlay_timer.stop()
        self.stream_info_timer.stop()
        self.controls_timer.stop()
        self.btn_stream_info.setChecked(False)
        self.stream_info_panel.hide()
        self._current_stream_type = None
        self._current_playing_stream_id = None
        self._current_stream_url = ""
        self._timeshift_active = False
        self._timeshift_paused_at = 0
        if self._player_maximized:
            self._toggle_player_maximized()
        if self._pip_mode:
            # PiP-Modus sauber verlassen
            self._pip_mode = False
            self.pip_close_btn.hide()
            self.player_area.setMinimumSize(0, 0)
            self.player_area.setMaximumSize(16777215, 16777215)
            self.player_area.setStyleSheet("#playerArea { background-color: #000; }")
            self.player_header.show()
            self.player_controls.show()
            self.main_page.layout().addWidget(self.player_area)
        self.live_epg_bar.hide()
        self.live_epg_catchup_btn.hide()
        self.player_channel_logo.clear()
        self.player_channel_logo.hide()
        self.player_area.hide()
        # Kanalliste wieder anzeigen und voll breit
        self.channel_area.show()
        self.channel_area.setMinimumWidth(0)
        self.channel_area.setMaximumWidth(16777215)
        self._update_live_idle_panel()

    @Slot(bool)
    def _on_buffering(self, buffering: bool):
        """Zeigt/versteckt den Lade-Indikator im Player"""
        # VOD normal beendet → keine Buffering-Overlays mehr anzeigen
        if buffering and getattr(self, '_vod_eof_received', False):
            return
        if buffering:
            self._buffering_show_timer.start(400)
            # Watchdog bei Live-Streams: Timer basiert auf akkumulierter Buffering-Zeit.
            # Bei kurzen True/False-Oszillationen (z.B. langsame HLS-Segmente) feuert
            # der Watchdog trotzdem nach insgesamt 10s Buffering – ohne einzelne
            # Phasen zu ignorieren.
            if self._current_stream_type == "live":
                if self._buffering_since is None:
                    self._buffering_since = time.monotonic()
                elapsed = self._buffering_accumulated + (time.monotonic() - self._buffering_since)
                remaining_ms = max(500, int((10.0 - elapsed) * 1000))
                self._buffering_watchdog.start(remaining_ms)
        else:
            self._buffering_show_timer.stop()
            self._buffering_timer.stop()
            self.buffering_overlay.hide()
            self._hide_stream_error()
            self._buffering_text = _tr("Laden")
            self._buffering_watchdog.stop()
            self._reconnect_timer.stop()
            self._stream_start_timer.stop()
            # Buffering-Zeit aufaddieren
            if self._buffering_since is not None:
                self._buffering_accumulated += time.monotonic() - self._buffering_since
                self._buffering_since = None
            if self._current_stream_type == "vod":
                self._vod_has_played = True
            if self._reconnect_attempt > 0:
                self.status_bar.showMessage(_tr("Verbunden: {}").format(self._current_stream_title), 4000)
            self._reconnect_attempt = 0
            self._stream_starting = False  # Stream laeuft → Schutzphase beenden

    def _show_buffering_overlay(self):
        parent = self.buffering_overlay.parentWidget()
        if parent:
            controls_h = self.player_controls.height() if self.player_controls.isVisible() else 0
            epg_h = self.live_epg_bar.height() if self.live_epg_bar.isVisible() else 0
            h = parent.height() - controls_h - epg_h
            self.buffering_overlay.setGeometry(0, 0, parent.width(), h)
        self.buffering_overlay.raise_()
        self.buffering_overlay.show()
        self._buffering_dots = 0
        self._buffering_timer.start(400)

    def _animate_buffering(self):
        """Animiert den Buffering-Text"""
        self._buffering_dots = (self._buffering_dots + 1) % 4
        dots = "." * self._buffering_dots
        self.buffering_overlay.setText(self._buffering_text + dots)

    def _toggle_play_pause(self):
        """Play/Pause umschalten - mit Timeshift fuer Catchup-Sender"""
        if (self._current_stream_type == "live"
                and self._current_epg_has_catchup
                and not self._timeshift_active):
            if self.player.is_playing:
                # Pause bei Live mit Catchup: Timestamp merken
                self._timeshift_paused_at = datetime.now().timestamp()
                self.player.pause()
                self.btn_play_pause.setIcon(getattr(self, '_icon_play', self.btn_play_pause.icon()))
            else:
                # Resume nach Pause: in Timeshift wechseln
                self._enter_timeshift(self._timeshift_paused_at)
                self.btn_play_pause.setIcon(getattr(self, '_icon_pause', self.btn_play_pause.icon()))
            return

        self.player.pause()
        if self.player.is_playing:
            self.btn_play_pause.setIcon(getattr(self, '_icon_pause', self.btn_play_pause.icon()))
        else:
            self.btn_play_pause.setIcon(getattr(self, '_icon_play', self.btn_play_pause.icon()))

    def _enter_timeshift(self, start_timestamp: float):
        """Wechselt vom Live-Stream in den Timeshift-Modus"""
        if not self.api or self._current_playing_stream_id is None:
            return

        stream_id = self._current_playing_stream_id
        now = datetime.now().timestamp()
        duration_min = max(1, int((now - start_timestamp) / 60))
        start = datetime.fromtimestamp(start_timestamp)
        url = self.api.creds.catchup_url(stream_id, start, duration_min)

        self._timeshift_active = True
        self._timeshift_start_ts = start_timestamp
        # Pause-State zuruecksetzen bevor neue URL geladen wird
        if self.player.player and self.player.player.pause:
            self.player.player.pause = False
        self.player.play(url)
        self._update_seek_controls_visibility()
        self._update_go_live_style()

    def _go_live(self):
        """Kehrt vom Timeshift zurueck zum Live-Stream"""
        if not self.api or self._current_playing_stream_id is None:
            return

        stream_id = self._current_playing_stream_id
        url = self.api.creds.stream_url(stream_id)

        self._timeshift_active = False
        self._timeshift_paused_at = 0
        self._timeshift_start_ts = 0.0
        self.player.play(url)
        self.btn_play_pause.setIcon(getattr(self, '_icon_pause', self.btn_play_pause.icon()))
        self._update_seek_controls_visibility()
        self._update_go_live_style()

    def _update_go_live_style(self):
        """Aktualisiert den LIVE-Button Stil (gruen = live, rot = timeshift)"""
        if self._timeshift_active:
            self.btn_go_live.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 68, 68, 30); color: #ff4444; border: 1px solid #ff4444;
                    padding: 2px 12px; border-radius: 6px; font-size: 11px; font-weight: bold;
                }
                QPushButton:hover { background: rgba(255, 68, 68, 60); }
            """)
        else:
            self.btn_go_live.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #00cc66; border: 1px solid #00cc66;
                    padding: 2px 12px; border-radius: 6px; font-size: 11px; font-weight: bold;
                }
                QPushButton:hover { background: rgba(0, 204, 102, 40); }
            """)

    def _skip_seconds(self, seconds: int):
        """Spult vor/zurueck - startet Timeshift bei Live-Catchup-Sendern"""
        if (self._current_stream_type == "live"
                and self._current_epg_has_catchup
                and not self._timeshift_active
                and seconds < 0):
            # Zurueckspulen bei Live → Timeshift starten
            start = datetime.now().timestamp() + seconds
            self._enter_timeshift(start)
            self.btn_play_pause.setIcon(getattr(self, '_icon_pause', self.btn_play_pause.icon()))
        else:
            self.player.seek(seconds)

    def _on_volume_changed(self, value: int):
        """Lautstaerke aendern und beide Slider synchronisieren"""
        self.player.set_volume(value)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(value)
        self.volume_slider.blockSignals(False)
        # Wenn Slider bewegt wird → automatisch entmuten
        if getattr(self, '_muted', False) and value > 0:
            self._muted = False
            self.player.set_mute(False)
            self._update_mute_icons()

    def _toggle_mute(self):
        """Stummschalten umschalten"""
        self._muted = not getattr(self, '_muted', False)
        self.player.set_mute(self._muted)
        self._update_mute_icons()

    def _update_mute_icons(self):
        """Lautsprecher-Icon in Controls-Bar und Fullscreen aktualisieren"""
        muted = getattr(self, '_muted', False)
        vol_btn = getattr(self, 'vol_mute_btn', None)
        if vol_btn is not None:
            px = self._px_vol_muted if muted else self._px_vol
            vol_btn.setPixmap(px)

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_released(self):
        dur = self.player.duration or 0
        if dur > 0:
            target = self.seek_slider.value() / 1000.0 * dur
            self.player.seek(target, relative=False)
        self._seeking = False

    def _update_seek_controls_visibility(self):
        """Blendet Seek-Controls je nach Stream-Typ ein/aus"""
        is_vod = self._current_stream_type == "vod"
        is_live = self._current_stream_type == "live"
        is_catchup_live = is_live and self._current_epg_has_catchup
        show_seek = is_vod or self._timeshift_active
        # Skip-Buttons auch bei Catchup-Live-Sendern zeigen
        self.btn_skip_back.setVisible(show_seek or is_catchup_live)
        self.btn_skip_forward.setVisible(show_seek or is_catchup_live)
        # Positions-Slider nur bei Filmen; Live/Timeshift nutzt die EPG-Leiste
        show_seek = is_vod
        self.player_pos_label.setVisible(show_seek)
        self.seek_slider.setVisible(show_seek)
        self.player_dur_label.setVisible(show_seek)
        # LIVE-Button nur im Timeshift zeigen
        self.btn_go_live.setVisible(self._timeshift_active)
        # Zap-Buttons nur bei Live
        self.btn_zap_prev.setVisible(is_live)
        self.btn_zap_next.setVisible(is_live)
        # EPG-Zeile: bei Vollbild/PiP/nicht-Live immer verstecken;
        # beim Live-Modus steuert der EPG-Ticker die Sichtbarkeit (zeigt erst wenn Daten da)
        if not is_live or self._pip_mode:
            self.live_epg_bar.hide()

    def _update_player_controls(self):
        """Aktualisiert die Player-Steuerleiste"""
        self._update_seek_controls_visibility()
        self._save_current_position()
        self._update_recording_status()

        if self._timeshift_active:
            # Timeshift: Position/Dauer anzeigen
            pos = self.player.position or 0
            dur = self.player.duration or 0
            self.player_pos_label.setText(self._format_time(pos))
            self.player_dur_label.setText(self._format_time(dur))
            if dur > 0 and not self._seeking:
                self.seek_slider.setValue(int(pos / dur * 1000))
        elif self._current_stream_type == "live" and self._current_playing_stream_id:
            # EPG-Info fuer Live-Sender anzeigen
            epg = self._epg_cache.get(self._current_playing_stream_id, [])
            now = datetime.now().timestamp()
            for entry in epg:
                if entry.start_timestamp <= now < entry.stop_timestamp:
                    start = datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M")
                    end = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
                    self.player_info_label.setText(f"{start}-{end}  {entry.title}")
                    break
            else:
                self.player_info_label.setText("LIVE")
        elif self._current_stream_type == "vod":
            # Position/Dauer fuer VOD anzeigen
            pos = self.player.position or 0
            dur = self.player.duration or 0
            self.player_pos_label.setText(self._format_time(pos))
            self.player_dur_label.setText(self._format_time(dur))
            if dur > 0 and not self._seeking:
                self.seek_slider.setValue(int(pos / dur * 1000))

        self._update_live_epg_row()
        if self._player_maximized and self.fullscreen_controls.isVisible():
            self._position_fullscreen_controls()

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Formatiert Sekunden als HH:MM:SS oder MM:SS"""
        s = int(seconds)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _toggle_player_maximized(self):
        """Wechselt zwischen echtem OS-Fullscreen und normalem Modus"""
        if self._pip_mode:
            self._exit_pip_mode()
            if self._current_stream_type != "vod":
                # Doppelklick im PiP: zurueck zu Live mit vollem Player
                self._switch_mode("live")
                return
            # Film: aus dem Mini-Player direkt wieder ins Vollbild

        if self._player_maximized:
            # Fullscreen verlassen
            self._fs_controls_timer.stop()
            self._hide_fullscreen_controls()
            self._player_maximized = False
            self._undock_fullscreen_controls()
            self.unsetCursor()
            self.sidebar.show()
            if self._current_stream_type != "vod":
                self.channel_area.show()
            self.player_header.show()
            self.status_bar.show()
            self.btn_fullscreen.setIcon(_pi("maximize.svg", 20))
            self._update_seek_controls_visibility()
            self._update_live_epg_row()
            if self._current_stream_type == "vod":
                # Film verkleinert sich zum Mini-Player, die Detailansicht ist wieder sichtbar
                self.channel_area.show()
                self._enter_pip_mode()
            was_maximized = getattr(self, '_was_maximized_before_fullscreen', True)
            self.showNormal()
            if was_maximized:
                QTimer.singleShot(0, self.showMaximized)
        else:
            # Echtes OS-Fullscreen
            self._was_maximized_before_fullscreen = self.isMaximized()
            self._info_overlay_timer.stop()
            self.sidebar.hide()
            self.channel_area.hide()
            self.player_header.hide()
            self.status_bar.hide()
            self._player_maximized = True
            self._dock_fullscreen_controls()
            self.btn_fullscreen.setIcon(_pi("minimize.svg", 20))
            self.showFullScreen()
            self.player.setFocus()
            # Windows: showFullScreen() kann Relayout triggern der Widgets wieder einblendet
            # → nochmals verstecken nach der Zustandsänderung
            QTimer.singleShot(100, self._enforce_fullscreen_hidden)

    def _dock_fullscreen_controls(self):
        """Haengt Info-Overlay, EPG-Leiste und Steuerleiste ins Vollbild-Overlay ein -
        dieselben Widgets wie im Fenster, damit beide Ansichten identisch aussehen."""
        area_layout = self.player_area.layout()
        self._fs_dock_index = {
            "epg": area_layout.indexOf(self.live_epg_bar),
            "controls": area_layout.indexOf(self.player_controls),
        }
        self.info_overlay.hide()
        lay = self._fs_overlay_layout
        lay.addWidget(self.info_overlay)
        lay.addWidget(self.live_epg_bar)
        lay.addWidget(self.player_controls)

    def _undock_fullscreen_controls(self):
        idx = getattr(self, '_fs_dock_index', None)
        if not idx:
            return
        area_layout = self.player_area.layout()
        area_layout.insertWidget(idx["epg"], self.live_epg_bar)
        area_layout.insertWidget(idx["controls"], self.player_controls)
        self.info_overlay.setParent(self.player_container)
        self.info_overlay.hide()
        self.player_controls.show()
        self._fs_dock_index = None

    def _enforce_fullscreen_hidden(self):
        """Stellt sicher dass Fenster-Elemente im Vollbild versteckt bleiben (Windows-Fix)."""
        if self._player_maximized:
            self.player_header.hide()
            self.status_bar.hide()

    def _on_player_escape(self):
        """Escape im Player druecken -> Fullscreen oder PiP verlassen"""
        if self._player_maximized:
            self._toggle_player_maximized()
        elif self._pip_mode:
            self._exit_pip_mode()
            self._switch_mode("live")

    def _position_fullscreen_controls(self):
        """Positioniert die Fullscreen-Kontrollleiste am unteren Rand.

        Hoehe ergibt sich aus dem tatsaechlichen Inhalt (sizeHint), nicht aus
        einem festen Pixelwert - sonst nimmt die Leiste auf kleinen Fenstern
        (z.B. 1366x768) einen unverhaeltnismaessig grossen Anteil der Hoehe
        ein, auf grossen/4K-Fenstern dagegen zu wenig.
        """
        parent = self.fullscreen_controls.parentWidget()
        if parent:
            ctrl_h = self.fullscreen_controls.sizeHint().height()
            ctrl_h = max(FULLSCREEN_CONTROLS_MIN_HEIGHT,
                         min(ctrl_h, int(parent.height() * FULLSCREEN_CONTROLS_MAX_HEIGHT_RATIO)))
            self.fullscreen_controls.setGeometry(0, parent.height() - ctrl_h, parent.width(), ctrl_h)

    def _fill_info_overlay(self):
        """Befuellt Logo/Sender/JETZT/DANACH - gemeinsam fuer Fenster und Vollbild."""
        is_live = self._current_stream_type == "live"
        if is_live:
            self.overlay_channel_name.setText(
                getattr(self, '_playing_channel_name', None) or self._current_stream_title)
            now, nxt = self._playhead_epg()
            if now is None:
                now, nxt = self._detail_now_entry, self._detail_next_entry
            self.overlay_now_lbl.setText(_tr("LÄUFT") if self._timeshift_active else _tr("JETZT"))
            now_text = now.title if now else ""
        else:
            # Film/Serie: nur der Titel, gross wie ein Sendungstitel
            nxt = None
            now_text = self._current_stream_title
        self.overlay_channel_name.setVisible(is_live)
        self.overlay_now_title.setText(now_text)
        self.overlay_next_title.setText(nxt.title if nxt else "")
        # Leere Zeilen nicht als nackte Labels zeigen (EPG evtl. noch nicht geladen)
        for lbl, title in ((self.overlay_now_lbl, self.overlay_now_title),
                           (self.overlay_next_lbl, self.overlay_next_title)):
            visible = bool(title.text())
            lbl.setVisible(visible and is_live)
            title.setVisible(visible)

    def _show_info_overlay(self, force: bool = False):
        """Zeigt den Hover-Overlay mit Logo + JETZT/DANACH im Live-Modus."""
        if self._player_maximized or self._pip_mode or self._current_stream_type != "live":
            return
        if not force and not self.player.is_playing:
            return
        self._info_overlay_timer.stop()
        self._fill_info_overlay()
        parent = self.info_overlay.parentWidget()
        if parent:
            small = parent.height() < 160
            self.overlay_logo.setVisible(not small)
            self.info_overlay.layout().setContentsMargins(24, 6 if small else 18, 24, 6 if small else 18)
            h = min(165, parent.height())
            self.info_overlay.setGeometry(0, parent.height() - h, parent.width(), h)
        self.info_overlay.raise_()
        self.info_overlay.show()

    def _hide_info_overlay(self):
        if self._player_maximized:
            return  # im Vollbild gehoert das Overlay zur Vollbild-Leiste
        self.info_overlay.hide()

    def _show_fullscreen_controls(self):
        """Zeigt die Fullscreen-Kontrollleiste und startet den Auto-Hide-Timer"""
        if not self._player_maximized:
            return
        self._fill_info_overlay()
        self.info_overlay.setVisible(self._current_stream_type in ("live", "vod"))
        self.overlay_logo.setVisible(self._current_stream_type == "live")
        self.info_overlay.layout().setContentsMargins(24, 18, 24, 12)
        self._update_seek_controls_visibility()
        self._update_live_epg_row()
        self._position_fullscreen_controls()
        self.fullscreen_controls.raise_()
        self.fullscreen_controls.show()
        self.unsetCursor()
        self._fs_controls_timer.start(3000)
        self._fs_last_cursor_pos = QCursor.pos()
        self._fs_idle_since = time.monotonic()
        self._fs_cursor_watch_timer.start()

    def _hide_fullscreen_controls(self):
        """Versteckt die Fullscreen-Kontrollleiste und blendet Cursor aus"""
        self.fullscreen_controls.hide()
        self._fs_cursor_watch_timer.stop()
        if self._player_maximized:
            self.setCursor(Qt.BlankCursor)

    def _check_fs_controls_idle(self):
        """Watchdog gegen haengenbleibende Fullscreen-Leiste bei fehlenden
        Enter/Leave-Events (Cursor steht bereits beim Einblenden auf der Leiste
        und bewegt sich danach nicht mehr -> ohne diese Pruefung wuerde der
        Auto-Hide-Timer dauerhaft gestoppt bleiben)."""
        if not self._player_maximized or not self.fullscreen_controls.isVisible():
            self._fs_cursor_watch_timer.stop()
            return
        pos = QCursor.pos()
        if pos != self._fs_last_cursor_pos:
            self._fs_last_cursor_pos = pos
            self._fs_idle_since = time.monotonic()
            return
        if time.monotonic() - self._fs_idle_since >= 3.0:
            self._fs_controls_timer.stop()
            self._hide_fullscreen_controls()

    def _live_play_von_anfang(self):
        """Spielt die aktuelle Sendung ab Beginn via Catchup ab (aus normalem Player)"""
        if not self._current_playing_stream_id:
            return
        entry, _ = self._playhead_epg()
        if entry:
            self._play_catchup(entry)

    def _on_live_epg_seek_released(self):
        """Live EPG-Slider losgelassen → seekern oder Catchup starten"""
        self._live_epg_seeking = False
        entry = getattr(self, '_live_epg_current_entry', None)
        if not entry:
            return
        show_duration = entry.stop_timestamp - entry.start_timestamp
        if show_duration <= 0:
            return
        now_ts = datetime.now().timestamp()
        target_ts = entry.start_timestamp + (self.live_epg_seek_slider.value() / 1000.0) * show_duration

        if self._timeshift_active:
            # Im Timeshift: Ziel-Zeitstempel in Stream-Position umrechnen
            if target_ts >= now_ts:
                # Vorwaerts-Seek → Slider zuruecksetzen
                pos = self.player.position or 0
                current_ts = self._timeshift_start_ts + pos
                val = max(0, min(1000, int((current_ts - entry.start_timestamp) / show_duration * 1000)))
                self.live_epg_seek_slider.blockSignals(True)
                self.live_epg_seek_slider.setValue(val)
                self.live_epg_seek_slider.blockSignals(False)
                return
            stream_pos = target_ts - self._timeshift_start_ts
            dur = self.player.duration or 0
            if stream_pos >= 0 and dur > 0 and stream_pos <= dur:
                self.player.seek(stream_pos, relative=False)
            else:
                # Seek vor Catchup-Start → neuen Catchup starten
                seek_to = min(target_ts, now_ts - 10)
                if not self.api or not self._current_playing_stream_id:
                    return
                remaining = max(1, int((entry.stop_timestamp - seek_to) / 60))
                url = self.api.creds.catchup_url(
                    self._current_playing_stream_id, datetime.fromtimestamp(seek_to), remaining)
                self._timeshift_start_ts = seek_to
                self._play_stream(url, self._current_stream_title or "", "live",
                                  self._current_playing_stream_id)
                self._timeshift_active = True
                self._update_seek_controls_visibility()
                self.live_epg_bar.show()
            return

        # Live → Vorwaerts-Seek nicht erlaubt
        if not self.api or not self._current_playing_stream_id:
            return
        if target_ts >= now_ts:
            elapsed = now_ts - entry.start_timestamp
            val = max(0, min(1000, int(elapsed / show_duration * 1000)))
            self.live_epg_seek_slider.blockSignals(True)
            self.live_epg_seek_slider.setValue(val)
            self.live_epg_seek_slider.blockSignals(False)
            return
        seek_to = min(target_ts, now_ts - 10)
        remaining = max(1, int((entry.stop_timestamp - seek_to) / 60))
        url = self.api.creds.catchup_url(
            self._current_playing_stream_id, datetime.fromtimestamp(seek_to), remaining)
        self._timeshift_start_ts = seek_to
        self._play_stream(url, self._current_stream_title or "", "live",
                          self._current_playing_stream_id)
        self._timeshift_active = True
        self._update_seek_controls_visibility()
        self.live_epg_bar.show()

    def _playhead_ts(self) -> float:
        """Zeitpunkt im Programm, der gerade zu sehen ist (bei Timeshift/Catchup in der Vergangenheit)."""
        if self._timeshift_active and self._timeshift_start_ts > 0:
            return self._timeshift_start_ts + (self.player.position or 0)
        return datetime.now().timestamp()

    def _playhead_epg(self):
        """(Sendung an der Abspielposition, folgende Sendung) fuer den laufenden Sender."""
        sid = self._current_playing_stream_id
        if not sid or self._current_stream_type != "live":
            return None, None
        entries = list(self._epg_cache.get(sid, []))
        detail = getattr(self, '_detail_epg_entries', None)
        if detail and self._detail_stream_id() == sid:
            entries += detail
        playing = getattr(self, '_playing_catchup_entry', None)
        if playing:
            entries.append(playing)
        entries = dedupe_epg(entries)
        ts = self._playhead_ts()
        current = next((e for e in entries if e.start_timestamp <= ts < e.stop_timestamp), None)
        after = current.stop_timestamp if current else ts
        nxt = next((e for e in entries if e.start_timestamp >= after), None)
        return current, nxt

    def _update_live_epg_row(self):
        """Aktualisiert die EPG-Fortschrittszeile (Fenster und Vollbild)"""
        if self._pip_mode:
            return
        if self._current_stream_type != "live":
            return
        now_ts = self._playhead_ts()
        current_entry, _ = self._playhead_epg()
        has_catchup = self._current_epg_has_catchup
        self.live_epg_catchup_btn.setVisible(has_catchup)
        if current_entry:
            duration = current_entry.stop_timestamp - current_entry.start_timestamp
            if duration > 0:
                title = self.live_epg_title
                title.setText(title.fontMetrics().elidedText(
                    current_entry.title, Qt.ElideRight, title.maximumWidth()))
                title.setToolTip(current_entry.title)
                self.live_epg_start_lbl.setText(
                    datetime.fromtimestamp(current_entry.start_timestamp).strftime("%H:%M"))
                self.live_epg_stop_lbl.setText(
                    datetime.fromtimestamp(current_entry.stop_timestamp).strftime("%H:%M"))
                if has_catchup:
                    val = max(0, min(1000, int((now_ts - current_entry.start_timestamp) / duration * 1000)))
                    if not getattr(self, '_live_epg_seeking', False):
                        self.live_epg_seek_slider.blockSignals(True)
                        self.live_epg_seek_slider.setValue(val)
                        self.live_epg_seek_slider.blockSignals(False)
                    self.live_epg_seek_slider.show()
                    self.live_epg_von_anfang_btn.show()
                    self.live_epg_progress.hide()
                    self.live_epg_bar.show()
                    self._live_epg_current_entry = current_entry
                else:
                    elapsed = now_ts - current_entry.start_timestamp
                    self.live_epg_progress.setValue(
                        max(0, min(100, int(elapsed / duration * 100))))
                    self.live_epg_progress.show()
                    self.live_epg_seek_slider.hide()
                    self.live_epg_von_anfang_btn.hide()
                    self.live_epg_bar.show()
                    self._live_epg_current_entry = None
                return
        # Kein EPG-Eintrag gefunden: Bar komplett verstecken statt nur Button anzuzeigen
        self.live_epg_bar.hide()
        self.live_epg_seek_slider.hide()
        self.live_epg_progress.hide()
        self.live_epg_von_anfang_btn.hide()
        self._live_epg_current_entry = None

    @Slot(str)
    def _on_stream_ended(self, reason: str):
        """Wird aufgerufen wenn mpv den Stream beendet (Thread-safe via Signal)"""
        if not self._current_stream_url or not self._current_stream_type:
            return
        # VOD normal beendet: VOR dem _stream_starting-Guard behandeln,
        # damit das Flag auch während der Schutzphase gesetzt wird
        if self._current_stream_type == "vod" and reason in ('eof', 'unknown'):
            if getattr(self, '_vod_eof_received', False):
                return  # Guard gegen doppelten Aufruf
            self._vod_eof_received = True  # Blockiert weitere Buffering-Overlays
            self.buffering_overlay.hide()
            self._buffering_timer.stop()
            self._buffering_watchdog.stop()
            self._mark_as_fully_watched()
            # Vollbild-Verlassen und Cleanup verzögert ausführen (nach Signal-Handler-Rückkehr),
            # damit kein Render-Deadlock zwischen mpv-Event-Thread und Qt-Main-Thread entsteht
            QTimer.singleShot(0, self._handle_vod_end)
            self.status_bar.showMessage(_tr("Als gesehen markiert"), 4000)
            return
        # Absichtlich gestoppt oder noch im Verbindungsaufbau → kein Reconnect
        if reason in ('stop', 'quit'):
            return
        if self._stream_starting:
            return
        if self._current_stream_type == "live" and reason in ('error', 'eof', 'unknown'):
            self._schedule_reconnect()
        elif self._current_stream_type == "vod" and reason == 'error':
            self._show_stream_error(
                _tr("Video konnte nicht geladen werden"),
                _tr("Der Anbieter hat die Datei nicht ausgeliefert. Versuche es erneut oder später."),
            )

    def _handle_vod_end(self):
        """Cleanup nach VOD-Ende: Player stoppen, Vollbild verlassen, zur Detailansicht zurück.
        Wird verzögert via QTimer.singleShot(0) aufgerufen, damit der mpv-Signal-Handler
        vollständig abgeschlossen ist bevor Qt Window-State-Änderungen durchgeführt werden.
        """
        # Player erst stoppen (verhindert mpv-Render während Vollbild-Transition)
        try:
            self.player.stop()
        except Exception:
            pass
        if self._player_maximized:
            self._toggle_player_maximized()
        # Zur Detailansicht zurücknavigieren: player_area ausblenden, channel_area einblenden
        if self._pip_mode:
            self._exit_pip_mode()
        self.player_area.hide()
        self.channel_area.show()
        self.channel_area.setMinimumWidth(0)
        self.channel_area.setMaximumWidth(16777215)
        # Richtige Detail-Seite anzeigen
        if self.channel_stack.currentIndex() == 1:
            # Serien-Detailansicht: Episodenliste mit Gesehen-Status aktualisieren
            season_idx = self.season_combo.currentIndex()
            if season_idx >= 0:
                self._populate_episodes(self.season_combo.itemData(season_idx))
        elif hasattr(self, '_current_vod') and self._current_vod:
            # Film-Detailansicht
            self.channel_stack.setCurrentIndex(2)

    def _schedule_reconnect(self):
        """Plant den naechsten Reconnect-Versuch"""
        self._buffering_watchdog.stop()
        self._reconnect_timer.stop()
        if self._reconnect_attempt >= self._max_reconnect_attempts:
            self._on_stream_error_final()
            return
        self._reconnect_attempt += 1
        delay = min(3000 * self._reconnect_attempt, 10000)
        self._buffering_text = _tr("Verbindung wird wiederhergestellt {}/{}").format(
            self._reconnect_attempt, self._max_reconnect_attempts)
        self.buffering_overlay.setText(self._buffering_text)
        if not self.buffering_overlay.isVisible():
            self._show_buffering_overlay()
        self._reconnect_timer.start(delay)

    def _last_saved_position(self) -> float:
        account = self.account_manager.get_selected()
        if not account or self._current_playing_stream_id is None:
            return 0.0
        pos, _ = self.history_manager.get_position(
            self._current_playing_stream_id, self._current_stream_type, account.name)
        return pos

    def _clear_stream_starting(self):
        """Hebt die Schutzphase auf (Sicherheitsnetz nach 5s)"""
        self._stream_starting = False

    def _do_reconnect(self):
        """Fuehrt einen Reconnect-Versuch durch.

        Erster Versuch: schnelles player.play() ohne mpv-Neustart.
        Falls mpv danach einfriert (nur Standbild), greift der Freeze-Watchdog
        im MpvPlayerWidget nach 5s und macht einen vollstaendigen Neustart.
        """
        if not self._current_stream_url or not self._current_stream_type:
            return
        self._stream_starting = True
        self._stream_start_timer.start(8000)
        if self._current_stream_type == "vod":
            # Film nach Fehler an der zuletzt gespeicherten Stelle fortsetzen
            start = self._last_saved_position()
            self.player.play(self._current_stream_url, seekable=True, start=start)
            return
        self.player.play(self._current_stream_url)

    def _on_buffering_timeout(self):
        """Watchdog: Stream buffert zu lange → Reconnect"""
        if self._current_stream_type == "live":
            self._schedule_reconnect()

    def _on_stream_error_final(self):
        """Alle Reconnect-Versuche gescheitert"""
        self._reconnect_attempt = 0
        self._show_stream_error(
            _tr("Sender nicht erreichbar"),
            _tr("Die Verbindung konnte nach mehreren Versuchen nicht hergestellt werden."),
        )

    def _show_stream_error(self, title: str, text: str):
        self.buffering_overlay.hide()
        self._buffering_timer.stop()
        self._buffering_show_timer.stop()
        self._buffering_watchdog.stop()
        self.stream_error_title.setText(title)
        self.stream_error_text.setText(text)
        self.stream_error_other_btn.setVisible(self._current_stream_type == "live")
        parent = self.stream_error_overlay.parentWidget()
        self.stream_error_overlay.setGeometry(0, 0, parent.width(), parent.height())
        self.stream_error_overlay.raise_()
        self.stream_error_overlay.show()
        if self.fullscreen_controls.isVisible():
            self.fullscreen_controls.raise_()

    def _hide_stream_error(self):
        self.stream_error_overlay.hide()

    def _retry_stream(self):
        self._hide_stream_error()
        self._reconnect_attempt = 0
        self._buffering_text = _tr("Laden")
        self._show_buffering_overlay()
        self._do_reconnect()

    def _choose_other_channel(self):
        self._hide_stream_error()
        if self._player_maximized:
            self._toggle_player_maximized()
        self.channel_list.setFocus()

    @Slot()
    def _on_gl_context_recreated(self):
        """GL-Kontext nach Bildschirmsperre neu erstellt → Stream neu starten.

        Nach GL-Kontextverlust hängt mpv's Video-Pipeline und liefert nur noch
        ein einzelnes Standbild. Einzige zuverlässige Lösung: Stream komplett neu
        starten, damit mpv sauber in den neuen Render-Kontext rendert.
        """
        if not self._current_stream_url:
            return

        # Schutzphase setzen, damit der end-file während des Neustarts keinen
        # weiteren Reconnect auslöst
        self._stream_starting = True
        self._stream_start_timer.start(8000)
        self._reconnect_attempt = 0
        self._reconnect_timer.stop()
        self._buffering_watchdog.stop()

        if self._current_stream_type == "vod":
            # VOD: aktuelle Position merken und nach dem Neustart wiederherstellen
            _pos = self.player.position or 0
            self.player.play(self._current_stream_url, seekable=True, start=_pos if _pos > 5 else 0.0)
        else:
            # Live: URL direkt neu abspielen
            self.player.play(self._current_stream_url, seekable=self._current_stream_type == "vod")

    def _zap(self, offset: int):
        """Wechselt um `offset` Einträge in der Kanalliste (+1 vor, -1 zurück)."""
        count = self.channel_list.count()
        if count == 0:
            return
        current = self.channel_list.currentRow()
        new_row = (current + offset) % count
        self.channel_list.setCurrentRow(new_row)
        self._on_channel_selected(self.channel_list.item(new_row))
        if self._player_maximized:
            QTimer.singleShot(400, self._show_fullscreen_controls)
        # Overlay nach kurzem Delay einblenden (Player startet noch) + 3s auto-hide
        QTimer.singleShot(350, self._show_info_overlay_zap)

    def _show_info_overlay_zap(self):
        self._show_info_overlay(force=True)
        self._info_overlay_timer.start(5000)

    def _has_active_stream(self) -> bool:
        return bool(self._current_stream_url) and self.player_area.isVisible()

    def _setup_playback_shortcuts(self):
        """Globale Tastenkuerzel. Textfelder behalten ihre Tasten (ShortcutOverride)."""
        def when_playing(fn):
            return lambda: fn() if self._has_active_stream() else None

        def live_zap(offset):
            if self._has_active_stream() and self._current_stream_type == "live":
                self._zap(offset)

        def volume_step(delta):
            if self._has_active_stream():
                self._on_volume_changed(max(0, min(100, self.volume_slider.value() + delta)))

        bindings = [
            ((Qt.Key_Space, Qt.Key_K), when_playing(self._toggle_play_pause)),
            ((Qt.Key_F,), when_playing(self._toggle_player_maximized)),
            ((Qt.Key_M,), when_playing(self._toggle_mute)),
            ((Qt.Key_PageUp,), lambda: live_zap(-1)),
            ((Qt.Key_PageDown,), lambda: live_zap(1)),
            ((Qt.Key_Plus, Qt.Key_Equal), lambda: volume_step(5)),
            ((Qt.Key_Minus,), lambda: volume_step(-5)),
        ]
        self._playback_shortcuts = []
        for keys, handler in bindings:
            for key in keys:
                sc = QShortcut(QKeySequence(key), self)
                sc.activated.connect(handler)
                self._playback_shortcuts.append(sc)

    def _zap_prev(self):
        self._zap(-1)

    def _zap_next(self):
        self._zap(1)

    async def _load_overlay_logo(self, url: str):
        """Laedt das Senderlogo fuer Header, Hover-Overlay und Fullscreen."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                pixmap = await self._fetch_poster(session, url, 128, 128)
                if pixmap and self._current_stream_icon == url:
                    self.player_channel_logo.setPixmap(pixmap.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.player_channel_logo.show()
                    self.overlay_logo.setPixmap(pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    if self.fullscreen_controls.isVisible():
                        self._position_fullscreen_controls()
        except Exception:
            pass
