"""
Kontextmenue fuer Kanalliste
"""
import time

from PySide6.QtWidgets import QMenu

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
                action_toggle = menu.addAction("Zu Favoriten hinzufuegen")

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
