"""
EPG: Programmfuehrer laden, anzeigen, Catchup abspielen
"""
import asyncio
import aiohttp
from datetime import datetime

from PySide6.QtCore import Qt, Slot, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QListWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QPixmap

from xtream_api import LiveStream, EpgEntry
from favorites_manager import Favorite
from epg_dialog import EpgDialog


class EpgMixin:

    @Slot(QListWidgetItem)
    def _on_channel_clicked(self, item: QListWidgetItem):
        """Handle single click on channel - load EPG for live streams"""
        data = item.data(Qt.UserRole)
        if not data or not self.api:
            return

        stream_id = None
        stream_name = ""
        has_catchup = False

        if isinstance(data, LiveStream):
            stream_id = data.stream_id
            stream_name = data.name
            has_catchup = data.tv_archive
        elif isinstance(data, Favorite) and data.type == "live":
            stream_id = data.id
            stream_name = data.name

        if stream_id:
            self._current_epg_stream_id = stream_id
            self._current_epg_has_catchup = has_catchup
            self.epg_channel_name.setText(stream_name)
            # Logo im EPG-Panel laden
            icon_url = getattr(data, 'stream_icon', '') or getattr(data, 'icon', '')
            asyncio.ensure_future(self._load_epg_panel_logo(icon_url))
            # Detail-Panel anzeigen (nur wenn kein Player aktiv)
            self._show_channel_detail(data)
            asyncio.ensure_future(self._load_epg(stream_id))
        else:
            self._clear_epg_panel()
            self._hide_channel_detail()

    async def _load_epg(self, stream_id: int):
        """Load EPG data for a stream"""
        if stream_id in self._epg_cache:
            epg = self._epg_cache[stream_id]
            self._update_epg_panel(epg)
            self._update_detail_epg(epg)
            return

        try:
            epg_data = await self.api.get_short_epg(stream_id, limit=8)
            self._epg_cache[stream_id] = epg_data
            if self._current_epg_stream_id == stream_id:
                self._update_epg_panel(epg_data)
                # Detail-Panel aktualisieren wenn es diesen Sender zeigt
                detail_id = getattr(self._detail_stream_data, 'stream_id',
                                    getattr(self._detail_stream_data, 'id', None))
                if self.channel_detail_panel.isVisible() and detail_id == stream_id:
                    self._update_detail_epg(epg_data)
        except Exception:
            self._clear_epg_panel()

    def _update_epg_panel(self, epg_data: list[EpgEntry]):
        """Update EPG panel with data"""
        if not epg_data:
            self.epg_now_label.hide()
            self.epg_now_title.setText("Keine EPG-Daten")
            self.epg_now_desc.setText("")
            self.epg_progress.hide()
            self.epg_next_label.hide()
            self.epg_next_title.setText("")
            self.btn_full_epg.setEnabled(False)
            return

        now = datetime.now().timestamp()
        current_entry = None
        next_entry = None

        for entry in epg_data:
            if entry.start_timestamp <= now <= entry.stop_timestamp:
                current_entry = entry
            elif entry.start_timestamp > now and next_entry is None:
                next_entry = entry

        if not current_entry and epg_data:
            current_entry = epg_data[0]
            if len(epg_data) > 1:
                next_entry = epg_data[1]

        if current_entry:
            start = datetime.fromtimestamp(current_entry.start_timestamp).strftime("%H:%M")
            end = datetime.fromtimestamp(current_entry.stop_timestamp).strftime("%H:%M")
            self.epg_now_label.show()
            self.epg_now_title.setText(f"{start} – {end}   {current_entry.title}")

            # Fortschrittsbalken
            duration = current_entry.stop_timestamp - current_entry.start_timestamp
            if duration > 0:
                elapsed = now - current_entry.start_timestamp
                progress = max(0, min(100, int(elapsed / duration * 100)))
                self.epg_progress.setValue(progress)
                self.epg_progress.show()
            else:
                self.epg_progress.hide()

            self.epg_now_desc.hide()
        else:
            self.epg_now_label.hide()
            self.epg_now_title.setText("")
            self.epg_now_desc.setText("")
            self.epg_progress.hide()

        if next_entry:
            start = datetime.fromtimestamp(next_entry.start_timestamp).strftime("%H:%M")
            end = datetime.fromtimestamp(next_entry.stop_timestamp).strftime("%H:%M")
            self.epg_next_label.show()
            self.epg_next_title.setText(f"{start} – {end}   {next_entry.title}")
        else:
            self.epg_next_label.hide()
            self.epg_next_title.setText("")

        self.btn_full_epg.setEnabled(True)
        # Fuer Hover-Overlay bereitstellen (auch wenn Detail-Panel nicht offen ist)
        self._detail_now_entry = current_entry
        self._detail_next_entry = next_entry

    def _clear_epg_panel(self):
        """Clear EPG panel"""
        self.epg_channel_name.setText("")
        self.epg_channel_logo.clear()
        self.epg_now_label.hide()
        self.epg_now_title.setText("Waehle einen Kanal")
        self.epg_now_desc.hide()
        self.epg_progress.hide()
        self.epg_next_label.hide()
        self.epg_next_title.setText("")
        self.btn_full_epg.setEnabled(False)
        self._current_epg_stream_id = None
        self._current_epg_has_catchup = False

    def _show_full_epg(self):
        """Show full EPG dialog - laedt bei Catchup-Sendern den vollen EPG"""
        if self._current_epg_stream_id is None:
            return

        has_catchup = self._current_epg_has_catchup
        if has_catchup:
            asyncio.ensure_future(self._show_full_epg_async(has_catchup))
        else:
            epg_data = self._epg_cache.get(self._current_epg_stream_id, [])
            self._open_epg_dialog(epg_data, has_catchup)

    async def _show_full_epg_async(self, has_catchup: bool):
        """Laedt vollen EPG asynchron und oeffnet den Dialog"""
        stream_id = self._current_epg_stream_id
        if stream_id is None or not self.api:
            return

        self._show_loading("Lade vollstaendiges Programm...")
        try:
            epg_data = await self.api.get_full_epg(stream_id)
            if not epg_data:
                epg_data = self._epg_cache.get(stream_id, [])
            if self._current_epg_stream_id == stream_id:
                self._open_epg_dialog(epg_data, has_catchup)
        except Exception:
            epg_data = self._epg_cache.get(stream_id, [])
            self._open_epg_dialog(epg_data, has_catchup)
        finally:
            self._hide_loading()

    def _open_epg_dialog(self, epg_data: list[EpgEntry], has_catchup: bool):
        """Oeffnet den EPG-Dialog (non-blocking mit open())"""
        channel_name = self.epg_channel_name.text()
        self._epg_dialog = EpgDialog(channel_name, epg_data, has_catchup=has_catchup, parent=self)
        self._epg_dialog.finished.connect(self._on_epg_dialog_finished)
        self._epg_dialog.open()

    def _on_epg_dialog_finished(self):
        """Wird aufgerufen wenn der EPG-Dialog geschlossen wird"""
        dialog = self._epg_dialog
        self._epg_dialog = None
        if dialog and dialog.selected_catchup_entry is not None:
            self._play_catchup(dialog.selected_catchup_entry)

    def _play_catchup(self, entry: EpgEntry):
        """Spielt eine vergangene/aktuelle Sendung via Catchup ab (EPG bleibt sichtbar)."""
        if not self.api or self._current_epg_stream_id is None:
            return

        stream_id = self._current_epg_stream_id
        duration_min = max(1, (entry.stop_timestamp - entry.start_timestamp) // 60)
        start = datetime.fromtimestamp(entry.start_timestamp)
        url = self.api.creds.catchup_url(stream_id, start, duration_min)

        channel_name = self.epg_channel_name.text()
        start_str = start.strftime("%H:%M")
        end_str = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
        title = f"{channel_name} \u2013 {entry.title} ({start_str}\u2013{end_str})"

        # Als Live-Stream abspielen damit EPG-Panel (3-Spalten) sichtbar bleibt
        self._play_stream(url, title, "live", stream_id)
        # Timeshift aktiv: Seek-Controls einblenden
        self._timeshift_active = True
        self._timeshift_start_ts = entry.start_timestamp
        self._update_seek_controls_visibility()

    def _play_detail_prev(self):
        """Spielt die vorherige Sendung via Catchup ab."""
        if self._detail_prev_entry:
            self._play_catchup(self._detail_prev_entry)

    def _play_detail_now_catchup(self):
        """Spielt die aktuelle Sendung ab Beginn via Catchup ab."""
        if self._detail_now_entry:
            self._play_catchup(self._detail_now_entry)

    # ── Kanal-Detailpanel ─────────────────────────────────────────────

    def _show_channel_detail(self, stream_data):
        """Zeigt das Kanal-Detailpanel. Layout: Senderliste | EPG | TV (3 Spalten)."""
        self._detail_stream_data = stream_data

        name = getattr(stream_data, 'name', '') or getattr(stream_data, 'title', '')
        self.detail_channel_name.setText(name)
        self.detail_channel_name.updateGeometry()  # word-wrap Hoehe an Parent-Layout melden

        # Logo-Platzhalter
        self.detail_logo.setText("\U0001F4FA")
        self.detail_logo.setPixmap(QPixmap())

        # EPG-Platzhalter
        self.detail_prev_widget.hide()
        self.detail_now_title.setText("Lade Programm\u2026")
        self.detail_now_time.setText("")
        self.detail_now_progress.hide()
        self.detail_now_desc.hide()
        self.detail_future_section.hide()
        self.detail_epg_action_btn.setEnabled(False)
        self._detail_prev_entry = None
        self._detail_now_entry = None
        self._detail_next_entry = None

        # EPG-Panel-Zeile verstecken, Senderliste bleibt immer sichtbar
        self._epg_splitter.setSizes([99999, 0])
        self.epg_panel.hide()

        # 2-Spalten: Senderliste ausblenden, Detail einblenden (Slide)
        self.channel_nav_widget.hide()
        if self.player_area.isVisible() and not self._pip_mode:
            ca_width = min(480, max(360, int(self.main_page.width() * 0.32)))
            self.channel_area.setFixedWidth(ca_width)
        self._slide_in(self.channel_detail_panel)

        icon_url = getattr(stream_data, 'stream_icon', '') or getattr(stream_data, 'icon', '')
        if icon_url:
            asyncio.ensure_future(self._load_detail_logo(icon_url))

        stream_id = getattr(stream_data, 'stream_id', None) or getattr(stream_data, 'id', None)
        if stream_id:
            asyncio.ensure_future(self._load_epg(stream_id))

    def _hide_channel_detail(self):
        """Versteckt das Kanal-Detailpanel mit Slide-Animation."""
        if not hasattr(self, 'channel_detail_panel'):
            return
        if not self.channel_detail_panel.isVisible():
            return
        self._slide_out(self.channel_detail_panel)

    def _toggle_channel_detail(self):
        """Toggle-Button: Detail-Panel auf- oder zuschieben."""
        if self.channel_detail_panel.isVisible():
            self._hide_channel_detail()
        elif self._detail_stream_data:
            self._show_channel_detail(self._detail_stream_data)

    def _slide_in(self, widget):
        """Schiebt das Detail-Panel von rechts ein."""
        target = self.channel_area.width()
        widget.setMaximumWidth(0)
        widget.show()
        self._slide_anim = QPropertyAnimation(widget, b"maximumWidth")
        self._slide_anim.setDuration(220)
        self._slide_anim.setStartValue(0)
        self._slide_anim.setEndValue(target)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        def _on_slide_in_done():
            widget.setMaximumWidth(16777215)
            # Nach der Animation Layout-Cache zuruecksetzen, damit word-wrapped
            # Labels ihre Hoehe korrekt neu berechnen (Animation kann Caches korrumpieren)
            widget.layout().invalidate()
            widget.layout().activate()

        self._slide_anim.finished.connect(_on_slide_in_done)
        self._slide_anim.start()

    def _slide_out(self, widget):
        """Schiebt das Detail-Panel nach rechts zu."""
        self._slide_anim = QPropertyAnimation(widget, b"maximumWidth")
        self._slide_anim.setDuration(180)
        self._slide_anim.setStartValue(widget.width())
        self._slide_anim.setEndValue(0)
        self._slide_anim.setEasingCurve(QEasingCurve.InCubic)
        self._slide_anim.finished.connect(self._on_detail_hidden)
        self._slide_anim.start()

    def _on_detail_hidden(self):
        """Wird nach der Slide-Out-Animation aufgerufen."""
        self.channel_detail_panel.hide()
        self.channel_detail_panel.setMaximumWidth(16777215)
        self.channel_nav_widget.show()
        if self.player_area.isVisible() and not self._pip_mode:
            self.channel_area.setFixedWidth(360)
        pass

    def _update_detail_epg(self, epg_data: list):
        """Befuellt den DAVOR/JETZT/DANACH-Bereich im Detailpanel mit EPG-Daten."""
        if not self.channel_detail_panel.isVisible():
            return

        now = datetime.now().timestamp()
        prev = None
        current = None
        future = []
        for entry in sorted(epg_data, key=lambda e: e.start_timestamp):
            if entry.stop_timestamp <= now:
                prev = entry  # letzten vergangenen Eintrag merken
            elif entry.start_timestamp <= now <= entry.stop_timestamp:
                current = entry
            elif entry.start_timestamp > now:
                future.append(entry)

        future = future[:3]

        # Eintraege fuer Play-Button-Callbacks speichern
        self._detail_prev_entry = prev
        self._detail_now_entry = current
        self._detail_next_entry = future[0] if future else None

        # DAVOR-Bereich
        if prev:
            s = datetime.fromtimestamp(prev.start_timestamp).strftime("%H:%M")
            e = datetime.fromtimestamp(prev.stop_timestamp).strftime("%H:%M")
            self.detail_prev_title.setText(prev.title)
            self.detail_prev_time.setText(f"{s} \u2013 {e}")
            self.detail_prev_play_btn.setVisible(self._current_epg_has_catchup)
            self.detail_prev_widget.show()
        else:
            self.detail_prev_widget.hide()

        if current:
            s = datetime.fromtimestamp(current.start_timestamp).strftime("%H:%M")
            e = datetime.fromtimestamp(current.stop_timestamp).strftime("%H:%M")
            self.detail_now_title.setText(current.title)
            self.detail_now_time.setText(f"{s} \u2013 {e}")
            dur = current.stop_timestamp - current.start_timestamp
            if dur > 0:
                prog = max(0, min(100, int((now - current.start_timestamp) / dur * 100)))
                self.detail_now_progress.setValue(prog)
                self.detail_now_progress.show()
            if current.description:
                self.detail_now_desc.setText(current.description)
                self.detail_now_desc.show()
            else:
                self.detail_now_desc.hide()
            # 📹-Button fuer JETZT verdrahten
            try:
                self.detail_now_rec_btn.clicked.disconnect()
            except RuntimeError:
                pass
            self.detail_now_rec_btn.clicked.connect(
                lambda checked=False, e=current: self._schedule_from_epg(e)
            )
            self.detail_now_rec_btn.show()
        else:
            self.detail_now_title.setText("Keine EPG-Daten")
            self.detail_now_time.setText("")
            self.detail_now_progress.hide()
            self.detail_now_desc.hide()
            self.detail_now_rec_btn.hide()

        # DANACH: bis zu 3 zukuenftige Eintraege dynamisch aufbauen
        while self.detail_future_layout.count():
            item = self.detail_future_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if future:
            for entry in future:
                s = datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M")
                e_time = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
                entry_w = QWidget()
                entry_w.setStyleSheet("background: transparent;")
                entry_lay = QVBoxLayout(entry_w)
                entry_lay.setContentsMargins(0, 0, 0, 0)
                entry_lay.setSpacing(2)
                title_lbl = QLabel(entry.title)
                title_lbl.setStyleSheet("font-size: 15px; color: #aaa;")
                title_lbl.setWordWrap(True)
                entry_lay.addWidget(title_lbl)
                # Zeitzeile + 📹-Button
                time_row = QHBoxLayout()
                time_row.setSpacing(6)
                time_lbl = QLabel(f"{s} \u2013 {e_time}")
                time_lbl.setStyleSheet("font-size: 12px; color: #555;")
                time_row.addWidget(time_lbl, stretch=1)
                rec_btn = QPushButton("\U0001F4F9")
                rec_btn.setToolTip("Aufnahme planen")
                rec_btn.setFixedHeight(22)
                rec_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent; color: #666;
                        border: 1px solid #333; border-radius: 3px;
                        font-size: 11px; padding: 0 5px;
                    }
                    QPushButton:hover { background: #c0392b; color: white; border-color: #c0392b; }
                """)
                rec_btn.clicked.connect(
                    lambda checked=False, e=entry: self._schedule_from_epg(e)
                )
                time_row.addWidget(rec_btn, alignment=Qt.AlignVCenter)
                entry_lay.addLayout(time_row)
                self.detail_future_layout.addWidget(entry_w)
            self.detail_future_section.show()
        else:
            self.detail_future_section.hide()

        self.detail_epg_action_btn.setEnabled(True)

    async def _load_detail_logo(self, url: str):
        """Laedt das Senderlogo und setzt es als 80x80 Icon."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                pixmap = await self._fetch_poster(session, url, 160, 160)
                if pixmap and self.channel_detail_panel.isVisible():
                    scaled = pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.detail_logo.setPixmap(scaled)
                    self.detail_logo.setText("")
        except Exception:
            pass

    async def _load_epg_panel_logo(self, url: str):
        """Laedt das Senderlogo fuer das EPG-Panel (64x64)."""
        if not url:
            self.epg_channel_logo.clear()
            return
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                pixmap = await self._fetch_poster(session, url, 64, 64)
                if pixmap:
                    self.epg_channel_logo.setPixmap(pixmap)
        except Exception:
            pass

    def _schedule_from_epg(self, entry):
        """Oeffnet den Planungsdialog fuer eine EPG-Sendung."""
        if not self.api or self._current_epg_stream_id is None:
            return
        channel_name = self.epg_channel_name.text()
        stream_url = self.api.creds.stream_url(self._current_epg_stream_id)
        self._open_schedule_dialog(
            channel_name=channel_name,
            stream_url=stream_url,
            start_ts=entry.start_timestamp,
            end_ts=entry.stop_timestamp,
            epg_title=entry.title,
        )

    def _play_detail_stream(self):
        """Spielt den im Detailpanel angezeigten Sender ab."""
        data = self._detail_stream_data
        if not data or not self.api:
            return
        if isinstance(data, LiveStream):
            url = self.api.creds.stream_url(data.stream_id)
            self._play_stream(url, data.name, "live", data.stream_id, icon=data.stream_icon)
        elif isinstance(data, Favorite) and data.type == "live":
            url = self.api.creds.stream_url(data.id)
            self._play_stream(url, data.name, "live", data.id, icon=data.icon or "")
