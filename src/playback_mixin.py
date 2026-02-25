"""
Wiedergabe: Stream-Steuerung, Timeshift, Buffering, Player-Maximierung, Info-Overlay
"""
import asyncio
import aiohttp
from datetime import datetime

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtWidgets import QListWidgetItem

from xtream_api import LiveStream, VodStream, Series, EpgEntry
from watch_history_manager import WatchEntry
from favorites_manager import Favorite


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

        if not self.api:
            return

        if isinstance(data, LiveStream):
            url = self.api.creds.stream_url(data.stream_id)
            self._play_stream(url, data.name, "live", data.stream_id, icon=data.stream_icon)

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

    def _play_stream(self, url: str, title: str, stream_type: str = "live", stream_id: int = None, icon: str = "", container_extension: str = ""):
        """Spielt einen Stream im integrierten Player ab"""
        # Reconnect-Zustand zuruecksetzen
        self._stream_starting = True  # end-file waehrend Verbindungsaufbau ignorieren
        self._stream_start_timer.start(5000)  # Sicherheitsnetz: nach 5s aufheben
        self._reconnect_attempt = 0
        self._reconnect_timer.stop()
        self._buffering_watchdog.stop()
        # Vorherige Position speichern
        self._save_current_position()

        self.player_title.setText(title)
        self._current_stream_type = stream_type
        self._current_playing_stream_id = stream_id
        self._current_stream_icon = icon
        self._current_stream_title = title
        self._current_container_ext = container_extension
        self._current_stream_url = url
        self._timeshift_active = False
        self._timeshift_paused_at = 0

        is_vod_playback = stream_type == "vod"

        if not self.player_area.isVisible():
            if is_vod_playback:
                # Film/Serie: Player ueber volle Breite, Kanalliste ausblenden
                self.channel_area.hide()
                self.player_area.show()
            else:
                # Live-TV: side-by-side mit Kanalliste
                self.channel_area.setFixedWidth(320)
                self.player_area.show()
        elif is_vod_playback and self.channel_area.isVisible():
            self.channel_area.hide()
        elif self._pip_mode and not is_vod_playback:
            self._exit_pip_mode()

        self._update_seek_controls_visibility()
        # Detailpanel schliessen wenn Stream startet
        self._hide_channel_detail()
        self.player.play(url)
        self.btn_play_pause.setText("\u2759\u2759")
        self.player_info_label.setText("")
        self.controls_timer.start(1000)
        self.status_bar.showMessage(f"Spiele: {title}")

        # Verlaufseintrag anlegen
        account = self.account_manager.get_selected()
        if account and stream_id is not None:
            entry = WatchEntry(
                stream_id=stream_id,
                stream_type=stream_type,
                account_name=account.name,
                title=title,
                icon=icon,
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
        self.info_overlay.hide()
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
        self.player_area.hide()
        # Kanalliste wieder anzeigen und voll breit
        self.channel_area.show()
        self.channel_area.setMinimumWidth(0)
        self.channel_area.setMaximumWidth(16777215)

    @Slot(bool)
    def _on_buffering(self, buffering: bool):
        """Zeigt/versteckt den Lade-Indikator im Player"""
        if buffering:
            # Overlay auf volle Groesse des Parents setzen
            parent = self.buffering_overlay.parentWidget()
            if parent:
                self.buffering_overlay.setGeometry(0, 0, parent.width(), parent.height())
            self.buffering_overlay.raise_()
            self.buffering_overlay.show()
            self._buffering_dots = 0
            self._buffering_timer.start(400)
            # Watchdog: bei Live-Streams nach 10s Reconnect anstoßen
            if self._current_stream_type == "live":
                self._buffering_watchdog.start(10000)
        else:
            self._buffering_timer.stop()
            self.buffering_overlay.hide()
            self._buffering_watchdog.stop()
            self._reconnect_timer.stop()
            self._stream_start_timer.stop()
            if self._reconnect_attempt > 0:
                self.status_bar.showMessage(f"Verbunden: {self._current_stream_title}", 4000)
            self._reconnect_attempt = 0
            self._stream_starting = False  # Stream laeuft → Schutzphase beenden

    def _animate_buffering(self):
        """Animiert den Buffering-Text"""
        self._buffering_dots = (self._buffering_dots + 1) % 4
        dots = "." * self._buffering_dots
        self.buffering_overlay.setText(f"Laden{dots}")

    def _toggle_play_pause(self):
        """Play/Pause umschalten - mit Timeshift fuer Catchup-Sender"""
        if (self._current_stream_type == "live"
                and self._current_epg_has_catchup
                and not self._timeshift_active):
            if self.player.is_playing:
                # Pause bei Live mit Catchup: Timestamp merken
                self._timeshift_paused_at = datetime.now().timestamp()
                self.player.pause()
                self.btn_play_pause.setText("\u25B6\uFE0E")
            else:
                # Resume nach Pause: in Timeshift wechseln
                self._enter_timeshift(self._timeshift_paused_at)
                self.btn_play_pause.setText("\u2759\u2759")
            return

        self.player.pause()
        if self.player.is_playing:
            self.btn_play_pause.setText("\u2759\u2759")
        else:
            self.btn_play_pause.setText("\u25B6\uFE0E")

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
        self.player.play(url)
        self.btn_play_pause.setText("\u2759\u2759")
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
            self.btn_play_pause.setText("\u2759\u2759")
        else:
            self.player.seek(seconds)

    def _on_volume_changed(self, value: int):
        """Lautstaerke aendern und beide Slider synchronisieren"""
        self.player.set_volume(value)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(value)
        self.volume_slider.blockSignals(False)
        fs_vol = getattr(self, 'fs_volume_slider', None)
        if fs_vol is not None:
            fs_vol.blockSignals(True)
            fs_vol.setValue(value)
            fs_vol.blockSignals(False)

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
        is_catchup_live = self._current_stream_type == "live" and self._current_epg_has_catchup
        show_seek = is_vod or self._timeshift_active
        # Skip-Buttons auch bei Catchup-Live-Sendern zeigen
        self.btn_skip_back.setVisible(show_seek or is_catchup_live)
        self.btn_skip_forward.setVisible(show_seek or is_catchup_live)
        # Slider/Position nur bei VOD oder aktivem Timeshift
        self.player_pos_label.setVisible(show_seek)
        self.seek_slider.setVisible(show_seek)
        self.player_dur_label.setVisible(show_seek)
        self.player_info_label.setVisible(not show_seek)
        # LIVE-Button nur im Timeshift zeigen
        self.btn_go_live.setVisible(self._timeshift_active)

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
                if entry.start_timestamp <= now <= entry.stop_timestamp:
                    start = datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M")
                    end = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
                    self.player_info_label.setText(f"{start}-{end}  {entry.title}")
                    return
            self.player_info_label.setText("LIVE")
        elif self._current_stream_type == "vod":
            # Position/Dauer fuer VOD anzeigen
            pos = self.player.position or 0
            dur = self.player.duration or 0
            self.player_pos_label.setText(self._format_time(pos))
            self.player_dur_label.setText(self._format_time(dur))
            if dur > 0 and not self._seeking:
                self.seek_slider.setValue(int(pos / dur * 1000))

        self._update_fullscreen_controls()

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
            # Doppelklick im PiP: zurueck zu Live mit vollem Player
            self._exit_pip_mode()
            self._switch_mode("live")
            return

        if self._player_maximized:
            # Fullscreen verlassen
            self._fs_controls_timer.stop()
            self._hide_fullscreen_controls()
            self.unsetCursor()
            self.sidebar.show()
            self.channel_area.show()
            self.player_header.show()
            self.player_controls.show()
            self._player_maximized = False
            if self._was_maximized_before_fullscreen:
                self.showMaximized()
            else:
                self.showNormal()
        else:
            # Echtes OS-Fullscreen
            self._was_maximized_before_fullscreen = self.isMaximized()
            self.sidebar.hide()
            self.channel_area.hide()
            self.player_header.hide()
            self.player_controls.hide()
            self._player_maximized = True
            self.showFullScreen()

    def _on_player_escape(self):
        """Escape im Player druecken -> Fullscreen oder PiP verlassen"""
        if self._player_maximized:
            self._toggle_player_maximized()
        elif self._pip_mode:
            self._exit_pip_mode()
            self._switch_mode("live")

    def _show_info_overlay(self):
        """Zeigt das Info-Overlay und aktualisiert den Inhalt"""
        if not self.player_area.isVisible() or self._pip_mode:
            return

        # Titel
        title = self.player_title.text()
        self.overlay_title.setText(title)

        # Logo
        logo_key = f"{self._current_stream_icon}_128x128"
        if self._current_stream_icon:
            if logo_key in self._image_cache:
                cached = self._image_cache[logo_key]
                if cached:
                    self.overlay_logo.setPixmap(cached.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.overlay_logo.show()
                else:
                    self.overlay_logo.hide()
            else:
                # Noch nicht geladen
                self.overlay_logo.hide()
                asyncio.ensure_future(self._load_overlay_logo(self._current_stream_icon))
        else:
            self.overlay_logo.hide()

        # EPG-Daten
        now_ts = datetime.now().timestamp()
        current_entry = None
        next_entry = None
        if self._current_playing_stream_id and self._current_stream_type == "live":
            epg = self._epg_cache.get(self._current_playing_stream_id, [])
            for entry in epg:
                if entry.start_timestamp <= now_ts <= entry.stop_timestamp:
                    current_entry = entry
                elif entry.start_timestamp > now_ts and next_entry is None:
                    next_entry = entry

        if current_entry:
            start = datetime.fromtimestamp(current_entry.start_timestamp).strftime("%H:%M")
            end = datetime.fromtimestamp(current_entry.stop_timestamp).strftime("%H:%M")
            self.overlay_now.setText(f"{start} – {end}   {current_entry.title}")
            self.overlay_now.show()
            duration = current_entry.stop_timestamp - current_entry.start_timestamp
            if duration > 0:
                elapsed = now_ts - current_entry.start_timestamp
                self.overlay_progress.setValue(max(0, min(100, int(elapsed / duration * 100))))
                self.overlay_progress.show()
            else:
                self.overlay_progress.hide()
        else:
            self.overlay_now.hide()
            self.overlay_progress.hide()

        if next_entry:
            start = datetime.fromtimestamp(next_entry.start_timestamp).strftime("%H:%M")
            self.overlay_next.setText(f"Danach: {start}  {next_entry.title}")
            self.overlay_next.show()
        else:
            self.overlay_next.hide()

        # Overlay positionieren (untere Haelfte des player_container)
        parent = self.info_overlay.parentWidget()
        if parent:
            w = parent.width()
            h = parent.height()
            overlay_h = min(180, h // 2)
            self.info_overlay.setGeometry(0, h - overlay_h, w, overlay_h)

        self.info_overlay.raise_()
        self.info_overlay.show()
        self._info_overlay_timer.start(3000)

    def _hide_info_overlay(self):
        self.info_overlay.hide()

    def _position_fullscreen_controls(self):
        """Positioniert die Fullscreen-Kontrollleiste am unteren Rand"""
        parent = self.fullscreen_controls.parentWidget()
        if parent:
            ctrl_h = 120
            self.fullscreen_controls.setGeometry(0, parent.height() - ctrl_h, parent.width(), ctrl_h)

    def _show_fullscreen_controls(self):
        """Zeigt die Fullscreen-Kontrollleiste und startet den Auto-Hide-Timer"""
        if not self._player_maximized:
            return
        self._position_fullscreen_controls()
        self.fullscreen_controls.raise_()
        self.fullscreen_controls.show()
        self.unsetCursor()
        self._fs_controls_timer.start(3000)

    def _hide_fullscreen_controls(self):
        """Versteckt die Fullscreen-Kontrollleiste und blendet Cursor aus"""
        self.fullscreen_controls.hide()
        if self._player_maximized:
            self.setCursor(Qt.BlankCursor)

    def _on_fs_seek_released(self):
        """Seek-Slider im Fullscreen-Overlay losgelassen"""
        self._fs_seeking = False
        dur = self.player.duration or 0
        if dur > 0:
            target = self.fs_seek_slider.value() / 1000.0 * dur
            self.player.seek(target, relative=False)
        self.seek_slider.blockSignals(True)
        self.seek_slider.setValue(self.fs_seek_slider.value())
        self.seek_slider.blockSignals(False)

    def _update_fullscreen_controls(self):
        """Aktualisiert den Inhalt der Fullscreen-Kontrollleiste"""
        if not self._player_maximized or not self.fullscreen_controls.isVisible():
            return
        # Play/Pause-Button synchronisieren
        is_playing = self.player.is_playing
        self.fs_btn_play_pause.setText("\u2759\u2759" if is_playing else "\u25B6\uFE0E")
        # Seek-Zeile nur bei VOD oder Timeshift anzeigen
        show_seek = self._current_stream_type == "vod" or self._timeshift_active
        self.fs_seek_row.setVisible(show_seek)
        if show_seek:
            pos = self.player.position or 0
            dur = self.player.duration or 0
            self.fs_pos_label.setText(self._format_time(pos))
            self.fs_dur_label.setText(self._format_time(dur))
            if dur > 0 and not self._fs_seeking:
                self.fs_seek_slider.setValue(int(pos / dur * 1000))
        # EPG-Info fuer Live-Streams
        if self._current_stream_type == "live":
            self.fs_info_label.setText(self.player_info_label.text())
        else:
            self.fs_info_label.setText("")

    @Slot(str)
    def _on_stream_ended(self, reason: str):
        """Wird aufgerufen wenn mpv den Stream beendet (Thread-safe via Signal)"""
        if not self._current_stream_url or not self._current_stream_type:
            return
        # Absichtlich gestoppt oder noch im Verbindungsaufbau → kein Reconnect
        if reason in ('stop', 'quit'):
            return
        if self._stream_starting:
            return
        if self._current_stream_type == "live" and reason in ('error', 'eof', 'unknown'):
            self._schedule_reconnect()
        elif self._current_stream_type == "vod" and reason == 'error':
            self.buffering_overlay.hide()
            self.status_bar.showMessage("Fehler: Video konnte nicht geladen werden")

    def _schedule_reconnect(self):
        """Plant den naechsten Reconnect-Versuch"""
        self._buffering_watchdog.stop()
        self._reconnect_timer.stop()
        if self._reconnect_attempt >= self._max_reconnect_attempts:
            self._on_stream_error_final()
            return
        self._reconnect_attempt += 1
        delay = min(3000 * self._reconnect_attempt, 10000)
        self.status_bar.showMessage(
            f"Stream unterbrochen – Verbindungsversuch {self._reconnect_attempt}/{self._max_reconnect_attempts} ..."
        )
        self._reconnect_timer.start(delay)

    def _clear_stream_starting(self):
        """Hebt die Schutzphase auf (Sicherheitsnetz nach 5s)"""
        self._stream_starting = False

    def _do_reconnect(self):
        """Fuehrt einen Reconnect-Versuch durch"""
        if not self._current_stream_url or not self._current_stream_type:
            return
        self._stream_starting = True
        self._stream_start_timer.start(5000)
        self.player.play(self._current_stream_url)

    def _on_buffering_timeout(self):
        """Watchdog: Stream buffert zu lange → Reconnect"""
        if self._current_stream_type == "live":
            self._schedule_reconnect()

    def _on_stream_error_final(self):
        """Alle Reconnect-Versuche gescheitert"""
        self._reconnect_attempt = 0
        self.buffering_overlay.hide()
        self._buffering_timer.stop()
        self.status_bar.showMessage("Stream nicht erreichbar – bitte anderen Sender wählen")

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
            self.player.play(self._current_stream_url)
            if _pos > 5:
                QTimer.singleShot(2500, lambda: self.player.seek(_pos, relative=False))
        else:
            # Live: URL direkt neu abspielen
            self.player.play(self._current_stream_url)

    async def _load_overlay_logo(self, url: str):
        """Laedt das Senderlogo fuer das Overlay"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                pixmap = await self._fetch_poster(session, url, 128, 128)
                if pixmap and self._current_stream_icon == url and self.info_overlay.isVisible():
                    self.overlay_logo.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.overlay_logo.show()
        except Exception:
            pass
