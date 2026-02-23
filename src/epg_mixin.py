"""
EPG: Programmfuehrer laden, anzeigen, Catchup abspielen
"""
import asyncio
import aiohttp
from datetime import datetime

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QListWidgetItem
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
            epg_data = await self.api.get_short_epg(stream_id, limit=5)
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

            desc = current_entry.description.strip() if current_entry.description else ""
            self.epg_now_desc.setText(desc)
            self.epg_now_desc.setVisible(bool(desc))
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

    def _clear_epg_panel(self):
        """Clear EPG panel"""
        self.epg_channel_name.setText("")
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
        """Spielt eine vergangene Sendung via Catchup/Timeshift ab"""
        if not self.api or self._current_epg_stream_id is None:
            return

        stream_id = self._current_epg_stream_id
        duration_min = max(1, (entry.stop_timestamp - entry.start_timestamp) // 60)
        start = datetime.fromtimestamp(entry.start_timestamp)
        url = self.api.creds.catchup_url(stream_id, start, duration_min)

        channel_name = self.epg_channel_name.text()
        start_str = start.strftime("%H:%M")
        end_str = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
        title = f"{channel_name} - {entry.title} ({start_str}-{end_str})"

        self._play_stream(url, title, "vod")

    # ── Kanal-Detailpanel ─────────────────────────────────────────────

    def _show_channel_detail(self, stream_data):
        """Zeigt das Kanal-Detailpanel rechts (nur wenn kein Player aktiv)."""
        # Nur anzeigen wenn kein Player laueft
        if self.player_area.isVisible() and not self._pip_mode:
            return

        self._detail_stream_data = stream_data

        name = getattr(stream_data, 'name', '') or getattr(stream_data, 'title', '')
        self.detail_channel_name.setText(name)

        # Platzhalter bis Logo geladen
        self.detail_logo.setText("📺")
        self.detail_logo.setPixmap(QPixmap())

        # EPG-Platzhalter bis Daten da sind
        self.detail_now_title.setText("Lade Programm…")
        self.detail_now_time.setText("")
        self.detail_now_progress.hide()
        self.detail_now_desc.hide()
        self.detail_next_widget.hide()

        # Layout anpassen: Kanalliste schmal, Detailpanel breit
        self.channel_nav_widget.setMaximumWidth(360)
        self._epg_splitter.setSizes([99999, 0])
        self.epg_panel.hide()
        self.channel_detail_panel.show()

        # Logo async laden
        icon_url = getattr(stream_data, 'stream_icon', '') or getattr(stream_data, 'icon', '')
        if icon_url:
            asyncio.ensure_future(self._load_detail_logo(icon_url))

    def _hide_channel_detail(self):
        """Versteckt das Kanal-Detailpanel und stellt Normallayout wieder her."""
        if not hasattr(self, 'channel_detail_panel'):
            return
        self.channel_detail_panel.hide()
        self.channel_nav_widget.setMaximumWidth(16777215)
        if self.current_mode == "live":
            self.epg_panel.show()
            self._epg_splitter.setSizes([600, 260])

    def _update_detail_epg(self, epg_data: list):
        """Befuellt den JETZT/DANACH-Bereich im Detailpanel mit EPG-Daten."""
        if not self.channel_detail_panel.isVisible():
            return

        now = datetime.now().timestamp()
        current = None
        nxt = None
        for entry in epg_data:
            if entry.start_timestamp <= now <= entry.stop_timestamp:
                current = entry
            elif entry.start_timestamp > now and nxt is None:
                nxt = entry

        if current:
            s = datetime.fromtimestamp(current.start_timestamp).strftime("%H:%M")
            e = datetime.fromtimestamp(current.stop_timestamp).strftime("%H:%M")
            self.detail_now_title.setText(current.title)
            self.detail_now_time.setText(f"{s} – {e}")
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
        else:
            self.detail_now_title.setText("Keine EPG-Daten")
            self.detail_now_time.setText("")
            self.detail_now_progress.hide()
            self.detail_now_desc.hide()

        if nxt:
            s = datetime.fromtimestamp(nxt.start_timestamp).strftime("%H:%M")
            e = datetime.fromtimestamp(nxt.stop_timestamp).strftime("%H:%M")
            self.detail_next_title.setText(nxt.title)
            self.detail_next_time.setText(f"{s} – {e}")
            self.detail_next_widget.show()
        else:
            self.detail_next_widget.hide()

    async def _load_detail_logo(self, url: str):
        """Laedt das Senderlogo fuer das Detailpanel (gross, abgerundet per CSS)."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                pixmap = await self._fetch_poster(session, url, 88, 88)
                if pixmap and self.channel_detail_panel.isVisible():
                    scaled = pixmap.scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.detail_logo.setPixmap(scaled)
                    self.detail_logo.setText("")
        except Exception:
            pass

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
