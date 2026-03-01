"""
Kontextmenue fuer Kanalliste
"""
import time

from PySide6.QtWidgets import QMenu, QMessageBox

from xtream_api import LiveStream, VodStream, Series
from favorites_manager import Favorite


class ChannelContextMixin:

    def _show_channel_context_menu(self, position):
        """Zeigt Kontextmenu fuer Kanal an"""
        item = self.channel_list.itemAt(position)
        if not item:
            return

        data = item.data(0x0100)  # Qt.UserRole
        if not data:
            return

        # --- Fertige Aufnahme (Datei) ---
        if isinstance(data, tuple) and len(data) == 2 and data[0] == "recording":
            filepath = data[1]
            menu = QMenu(self)
            action_play = menu.addAction("\u25B6  Abspielen")
            menu.addSeparator()
            action_delete = menu.addAction("\U0001F5D1  L\u00f6schen")
            action = menu.exec(self.channel_list.mapToGlobal(position))
            if action == action_play:
                name = filepath.stem.replace("_", " ")
                self._play_stream(str(filepath), name, "vod")
            elif action == action_delete:
                reply = QMessageBox.question(
                    self, "Aufnahme l\u00f6schen",
                    f"Aufnahme wirklich l\u00f6schen?\n{filepath.name}",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    try:
                        filepath.unlink()
                        self._load_recordings()
                        self.status_bar.showMessage(f"Gel\u00f6scht: {filepath.name}")
                    except Exception as e:
                        self.status_bar.showMessage(f"Fehler beim L\u00f6schen: {e}")
            return

        account = self.account_manager.get_selected()
        if not account:
            return

        # Ist es ein Live-Sender? (direkt oder als Favorit)
        is_live = isinstance(data, LiveStream) or (isinstance(data, Favorite) and data.type == "live")

        menu = QMenu(self)

        if self.current_mode == "favorites":
            # Im Favoriten-Modus: Nur Entfernen anzeigen
            action_remove = menu.addAction("Aus Favoriten entfernen")
            action_rec = None
            if is_live and self.api:
                menu.addSeparator()
                action_rec = menu.addAction("\U0001F4F9  Aufnahme planen")
            action = menu.exec(self.channel_list.mapToGlobal(position))
            if action == action_remove:
                self._remove_from_favorites(data)
            elif action_rec and action == action_rec:
                self._schedule_from_context(data)
        else:
            # In anderen Modi: Hinzufuegen/Entfernen je nach Status
            is_fav = self._is_item_favorite(data, account.name)
            if is_fav:
                action_toggle = menu.addAction("Aus Favoriten entfernen")
            else:
                action_toggle = menu.addAction("Zu Favoriten hinzuf\u00fcgen")

            action_rec = None
            if is_live and self.api:
                menu.addSeparator()
                action_rec = menu.addAction("\U0001F4F9  Aufnahme planen")

            action = menu.exec(self.channel_list.mapToGlobal(position))
            if action == action_toggle:
                self._toggle_favorite(data, account.name)
            elif action_rec and action == action_rec:
                self._schedule_from_context(data)

    def _schedule_from_context(self, data):
        """Oeffnet Aufnahme-Dialog fuer einen Sender ohne EPG."""
        if not self.api:
            return
        if isinstance(data, LiveStream):
            channel_name = data.name
            stream_url = self.api.creds.stream_url(data.stream_id)
        elif isinstance(data, Favorite) and data.type == "live":
            channel_name = data.name
            stream_url = self.api.creds.stream_url(data.id)
        else:
            return
        now = time.time()
        self._open_schedule_dialog(
            channel_name=channel_name,
            stream_url=stream_url,
            start_ts=now,
            end_ts=now + 3600,
        )

    def _get_item_name(self, data) -> str:
        """Gibt den Anzeigenamen eines Items zurueck"""
        if isinstance(data, LiveStream):
            name = data.name
            if data.tv_archive:
                name += " \u23EA"
            return name
        elif isinstance(data, VodStream):
            return data.name
        elif isinstance(data, Series):
            return data.name
        return ""
