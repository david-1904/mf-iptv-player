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

        # Geplante Aufnahme: Abbrechen-Dialog
        if isinstance(data, tuple) and len(data) == 2 and data[0] == "scheduled":
            from PySide6.QtWidgets import QMessageBox
            rec = data[1]
            label = rec.channel_name
            if rec.epg_title:
                label += f" \u2013 {rec.epg_title}"
            reply = QMessageBox.question(
                self, "Geplante Aufnahme",
                f"Aufnahme abbrechen?\n{label}",
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
            # Sender-State fuer EPG-Detail-Toggle merken
            self._detail_stream_data = data
            self._current_epg_stream_id = data.stream_id
            self._current_epg_has_catchup = getattr(data, 'tv_archive', False)
            self.epg_channel_name.setText(data.name)
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
        # else: gleicher Sender (Catchup/Seek) → icon + Logo behalten

        self._current_stream_type = stream_type
        self._current_playing_stream_id = stream_id

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

        if not self.player_area.isVisible():
            if is_vod_playback:
                # Film/Serie: Player ueber volle Breite, Kanalliste ausblenden
                self.channel_area.hide()
                self.player_area.show()
            else:
                # Live-TV: side-by-side mit Kanalliste
                self.channel_area.setFixedWidth(360)
                self.player_area.show()
        elif is_vod_playback and self.channel_area.isVisible():
            self.channel_area.hide()
        elif self._pip_mode and not is_vod_playback:
            self._exit_pip_mode()

        self._update_seek_controls_visibility()
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
        is_live = self._current_stream_type == "live"
        is_catchup_live = is_live and self._current_epg_has_catchup
        show_seek = is_vod or self._timeshift_active
        # Skip-Buttons auch bei Catchup-Live-Sendern zeigen
        self.btn_skip_back.setVisible(show_seek or is_catchup_live)
        self.btn_skip_forward.setVisible(show_seek or is_catchup_live)
        # Slider/Position nur bei VOD oder aktivem Timeshift
        self.player_pos_label.setVisible(show_seek)
        self.seek_slider.setVisible(show_seek)
        self.player_dur_label.setVisible(show_seek)
        # LIVE-Button nur im Timeshift zeigen
        self.btn_go_live.setVisible(self._timeshift_active)
        # Zap-Buttons nur bei Live
        self.btn_zap_prev.setVisible(is_live)
        self.btn_zap_next.setVisible(is_live)
        # EPG-Zeile: nur bei Live, nicht im Vollbild, nicht in PiP
        self.live_epg_bar.setVisible(
            is_live and not self._player_maximized and not self._pip_mode)

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
            if self._current_stream_type != "vod":
                self.channel_area.show()
            self.player_header.show()
            self.player_controls.show()
            self._player_maximized = False
            self.showMaximized()
        else:
            # Echtes OS-Fullscreen
            self._was_maximized_before_fullscreen = self.isMaximized()
            self._hide_info_overlay()
            self._info_overlay_timer.stop()
            self.sidebar.hide()
            self.channel_area.hide()
            self.player_header.hide()
            self.live_epg_bar.hide()
            self.player_controls.hide()
            self._player_maximized = True
            self.showFullScreen()
            # Windows: showFullScreen() kann Relayout triggern der Widgets wieder einblendet
            # → nochmals verstecken nach der Zustandsänderung
            QTimer.singleShot(100, self._enforce_fullscreen_hidden)

    def _enforce_fullscreen_hidden(self):
        """Stellt sicher dass Controls im Vollbild versteckt bleiben (Windows-Fix)."""
        if self._player_maximized:
            self.player_header.hide()
            self.player_controls.hide()
            self.live_epg_bar.hide()

    def _on_player_escape(self):
        """Escape im Player druecken -> Fullscreen oder PiP verlassen"""
        if self._player_maximized:
            self._toggle_player_maximized()
        elif self._pip_mode:
            self._exit_pip_mode()
            self._switch_mode("live")

    def _position_fullscreen_controls(self):
        """Positioniert die Fullscreen-Kontrollleiste am unteren Rand"""
        parent = self.fullscreen_controls.parentWidget()
        if parent:
            ctrl_h = 260
            self.fullscreen_controls.setGeometry(0, parent.height() - ctrl_h, parent.width(), ctrl_h)

    def _show_info_overlay(self, force: bool = False):
        """Zeigt den Hover-Overlay mit Logo + JETZT/DANACH im Live-Modus."""
        if self._player_maximized or self._current_stream_type != "live":
            return
        if not force and not self.player.is_playing:
            return
        self._info_overlay_timer.stop()
        self.overlay_channel_name.setText(self._current_stream_title)
        now = self._detail_now_entry
        nxt = self._detail_next_entry
        self.overlay_now_title.setText(now.title if now else "")
        self.overlay_next_title.setText(nxt.title if nxt else "")
        parent = self.info_overlay.parentWidget()
        if parent:
            h = 165
            self.info_overlay.setGeometry(0, parent.height() - h, parent.width(), h)
        self.info_overlay.raise_()
        self.info_overlay.show()

    def _hide_info_overlay(self):
        self.info_overlay.hide()

    def _show_fullscreen_controls(self):
        """Zeigt die Fullscreen-Kontrollleiste und startet den Auto-Hide-Timer"""
        if not self._player_maximized:
            return
        self._update_fs_info()
        self._update_fullscreen_controls()
        self._position_fullscreen_controls()
        self.fullscreen_controls.raise_()
        self.fullscreen_controls.show()
        self.unsetCursor()
        self._fs_controls_timer.start(3000)

    def _update_fs_info(self):
        """Befüllt die Info-Sektion im Fullscreen-Overlay (Kanal, EPG)"""
        self.fs_channel_title.setText(self.player_title.text())

        # Logo
        logo_key = f"{self._current_stream_icon}_128x128"
        if self._current_stream_icon:
            if logo_key in self._image_cache:
                cached = self._image_cache[logo_key]
                if cached:
                    self.fs_channel_logo.setPixmap(cached.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.fs_channel_logo.show()
            else:
                asyncio.ensure_future(self._load_overlay_logo(self._current_stream_icon))
        else:
            self.fs_channel_logo.hide()

        # EPG
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

        has_catchup_live = (self._current_epg_has_catchup
                            and self._current_stream_type == "live")

        if current_entry:
            start = datetime.fromtimestamp(current_entry.start_timestamp).strftime("%H:%M")
            end = datetime.fromtimestamp(current_entry.stop_timestamp).strftime("%H:%M")
            self.fs_epg_now.setText(f"{start} – {end}   {current_entry.title}")
            self.fs_epg_now.show()
            self._fs_epg_current_entry = current_entry
            duration = current_entry.stop_timestamp - current_entry.start_timestamp
            if duration > 0:
                if has_catchup_live:
                    # Wert: im Timeshift aus player.position/duration, sonst aus Uhrzeit
                    if self._timeshift_active:
                        pos = self.player.position or 0
                        if self._timeshift_start_ts > 0:
                            current_ts = self._timeshift_start_ts + pos
                            val = max(0, min(1000, int((current_ts - current_entry.start_timestamp) / duration * 1000)))
                        else:
                            val = None
                    else:
                        elapsed = now_ts - current_entry.start_timestamp
                        val = max(0, min(1000, int(elapsed / duration * 1000)))
                    if val is not None and not getattr(self, '_fs_epg_seeking', False):
                        self.fs_epg_seek_slider.blockSignals(True)
                        self.fs_epg_seek_slider.setValue(val)
                        self.fs_epg_seek_slider.blockSignals(False)
                    self.fs_epg_seek_slider.show()
                    self.fs_epg_von_anfang_btn.show()
                    self.fs_epg_progress.hide()
                else:
                    elapsed = now_ts - current_entry.start_timestamp
                    self.fs_epg_progress.setValue(max(0, min(100, int(elapsed / duration * 100))))
                    self.fs_epg_progress.show()
                    self.fs_epg_seek_slider.hide()
                    self.fs_epg_von_anfang_btn.hide()
            else:
                self.fs_epg_progress.hide()
                self.fs_epg_seek_slider.hide()
                self.fs_epg_von_anfang_btn.hide()
        else:
            self.fs_epg_now.hide()
            self.fs_epg_progress.hide()
            self.fs_epg_seek_slider.hide()
            self.fs_epg_von_anfang_btn.hide()
            self._fs_epg_current_entry = None

        if next_entry:
            start = datetime.fromtimestamp(next_entry.start_timestamp).strftime("%H:%M")
            self.fs_epg_next.setText(f"Danach: {start}  {next_entry.title}")
            self.fs_epg_next.show()
        else:
            self.fs_epg_next.hide()

    def _on_fs_epg_seek_released(self):
        """Nutzer hat EPG-Slider losgelassen → seekern oder Catchup starten"""
        self._fs_epg_seeking = False
        entry = getattr(self, '_fs_epg_current_entry', None)
        if not entry:
            return
        show_duration = entry.stop_timestamp - entry.start_timestamp
        if show_duration <= 0:
            return
        now_ts = datetime.now().timestamp()
        target_ts = entry.start_timestamp + (self.fs_epg_seek_slider.value() / 1000.0) * show_duration

        if self._timeshift_active:
            if target_ts >= now_ts:
                pos = self.player.position or 0
                current_ts = self._timeshift_start_ts + pos
                val = max(0, min(1000, int((current_ts - entry.start_timestamp) / show_duration * 1000)))
                self.fs_epg_seek_slider.blockSignals(True)
                self.fs_epg_seek_slider.setValue(val)
                self.fs_epg_seek_slider.blockSignals(False)
                return
            stream_pos = target_ts - self._timeshift_start_ts
            dur = self.player.duration or 0
            if stream_pos >= 0 and dur > 0 and stream_pos <= dur:
                self.player.seek(stream_pos, relative=False)
            else:
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
            return

        # Live → Catchup-URL mit angepasstem Startzeitpunkt
        if not self.api or not self._current_playing_stream_id:
            return
        if target_ts >= now_ts:
            elapsed = now_ts - entry.start_timestamp
            val = max(0, min(1000, int(elapsed / show_duration * 1000)))
            self.fs_epg_seek_slider.blockSignals(True)
            self.fs_epg_seek_slider.setValue(val)
            self.fs_epg_seek_slider.blockSignals(False)
            return
        seek_to = min(target_ts, now_ts - 10)
        remaining = max(1, int((entry.stop_timestamp - seek_to) / 60))
        url = self.api.creds.catchup_url(
            self._current_playing_stream_id, datetime.fromtimestamp(seek_to), remaining)
        self._timeshift_start_ts = seek_to
        self._play_stream(url, self._current_stream_title or "", "live", self._current_playing_stream_id)
        self._timeshift_active = True
        self._update_seek_controls_visibility()

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
        if not self._player_maximized:
            return

        is_vod = self._current_stream_type == "vod"
        is_live = self._current_stream_type == "live"
        has_catchup = self._current_epg_has_catchup
        timeshift = self._timeshift_active

        # Play/Pause
        self.fs_btn_play_pause.setText("\u2759\u2759" if self.player.is_playing else "\u25B6\uFE0E")

        # Skip zurück: VOD, Timeshift oder Live+Catchup
        self.fs_btn_skip_back.setVisible(is_vod or timeshift or (is_live and has_catchup))
        # Skip vor: nur VOD oder Timeshift
        self.fs_btn_skip_forward.setVisible(is_vod or timeshift)
        # LIVE-Button: nur im Timeshift
        self.fs_btn_go_live.setVisible(timeshift)
        # EPG-Seek-Slider Wert laufend aktualisieren
        if (self.fs_epg_seek_slider.isVisible()
                and not getattr(self, '_fs_epg_seeking', False)):
            entry = getattr(self, '_fs_epg_current_entry', None)
            if timeshift:
                pos = self.player.position or 0
                if self._timeshift_start_ts > 0 and entry:
                    show_dur = entry.stop_timestamp - entry.start_timestamp
                    current_ts = self._timeshift_start_ts + pos
                    val = max(0, min(1000, int((current_ts - entry.start_timestamp) / show_dur * 1000))) if show_dur > 0 else None
                else:
                    val = None
            else:
                if entry:
                    now_ts = datetime.now().timestamp()
                    dur = entry.stop_timestamp - entry.start_timestamp
                    val = max(0, min(1000, int((now_ts - entry.start_timestamp) / dur * 1000))) if dur > 0 else 0
                else:
                    val = None
            if val is not None:
                self.fs_epg_seek_slider.blockSignals(True)
                self.fs_epg_seek_slider.setValue(val)
                self.fs_epg_seek_slider.blockSignals(False)

        # Seek-Zeile: nur VOD (Timeshift nutzt EPG-Slider in der Info-Sektion)
        self.fs_seek_row.setVisible(is_vod)
        if is_vod:
            pos = self.player.position or 0
            dur = self.player.duration or 0
            self.fs_pos_label.setText(self._format_time(pos))
            self.fs_dur_label.setText(self._format_time(dur))
            if dur > 0 and not self._fs_seeking:
                self.fs_seek_slider.setValue(int(pos / dur * 1000))

    def _fs_play_von_anfang(self):
        """Spielt die aktuelle Sendung ab Beginn via Catchup ab (aus Vollbild)"""
        if not self._current_playing_stream_id:
            return
        now_ts = datetime.now().timestamp()
        for entry in self._epg_cache.get(self._current_playing_stream_id, []):
            if entry.start_timestamp <= now_ts <= entry.stop_timestamp:
                self._play_catchup(entry)
                return

    def _live_play_von_anfang(self):
        """Spielt die aktuelle Sendung ab Beginn via Catchup ab (aus normalem Player)"""
        if not self._current_playing_stream_id:
            return
        now_ts = datetime.now().timestamp()
        for entry in self._epg_cache.get(self._current_playing_stream_id, []):
            if entry.start_timestamp <= now_ts <= entry.stop_timestamp:
                self._play_catchup(entry)
                return

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

    def _update_live_epg_row(self):
        """Aktualisiert die EPG-Fortschrittszeile im normalen Player"""
        if self._player_maximized or self._pip_mode:
            return
        if self._current_stream_type != "live":
            return
        now_ts = datetime.now().timestamp()
        current_entry = None
        if self._current_playing_stream_id:
            for entry in self._epg_cache.get(self._current_playing_stream_id, []):
                if entry.start_timestamp <= now_ts <= entry.stop_timestamp:
                    current_entry = entry
                    break
        has_catchup = self._current_epg_has_catchup
        self.live_epg_catchup_btn.setVisible(has_catchup)
        if current_entry:
            duration = current_entry.stop_timestamp - current_entry.start_timestamp
            if duration > 0:
                if has_catchup:
                    if self._timeshift_active:
                        pos = self.player.position or 0
                        if self._timeshift_start_ts > 0:
                            current_ts = self._timeshift_start_ts + pos
                            val = max(0, min(1000, int((current_ts - current_entry.start_timestamp) / duration * 1000)))
                        else:
                            val = None
                    else:
                        elapsed = now_ts - current_entry.start_timestamp
                        val = max(0, min(1000, int(elapsed / duration * 1000)))
                    if val is not None and not getattr(self, '_live_epg_seeking', False):
                        self.live_epg_seek_slider.blockSignals(True)
                        self.live_epg_seek_slider.setValue(val)
                        self.live_epg_seek_slider.blockSignals(False)
                    self.live_epg_seek_slider.show()
                    self.live_epg_von_anfang_btn.show()
                    self.live_epg_progress.hide()
                    self._live_epg_current_entry = current_entry
                else:
                    elapsed = now_ts - current_entry.start_timestamp
                    self.live_epg_progress.setValue(
                        max(0, min(100, int(elapsed / duration * 100))))
                    self.live_epg_progress.show()
                    self.live_epg_seek_slider.hide()
                    self.live_epg_von_anfang_btn.hide()
                    self._live_epg_current_entry = None
                return
        self.live_epg_seek_slider.hide()
        self.live_epg_progress.hide()
        self.live_epg_von_anfang_btn.hide()
        self._live_epg_current_entry = None

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
        """Fuehrt einen Reconnect-Versuch durch.

        Erster Versuch: schnelles player.play() ohne mpv-Neustart.
        Falls mpv danach einfriert (nur Standbild), greift der Freeze-Watchdog
        im MpvPlayerWidget nach 5s und macht einen vollstaendigen Neustart.
        """
        if not self._current_stream_url or not self._current_stream_type:
            return
        self._stream_starting = True
        self._stream_start_timer.start(8000)
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

    def _zap(self, offset: int):
        """Wechselt um `offset` Einträge in der Kanalliste (+1 vor, -1 zurück)."""
        count = self.channel_list.count()
        if count == 0:
            return
        current = self.channel_list.currentRow()
        new_row = (current + offset) % count
        self.channel_list.setCurrentRow(new_row)
        self._on_channel_selected(self.channel_list.item(new_row))
        # Overlay nach kurzem Delay einblenden (Player startet noch) + 3s auto-hide
        QTimer.singleShot(350, self._show_info_overlay_zap)

    def _show_info_overlay_zap(self):
        self._show_info_overlay(force=True)
        self._info_overlay_timer.start(5000)

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
                        self.fs_channel_logo.setPixmap(pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        self.fs_channel_logo.show()
        except Exception:
            pass
