"""
Kontextmenue fuer Kanalliste
"""
from PySide6.QtWidgets import QMenu

from xtream_api import LiveStream, VodStream, Series


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

        menu = QMenu(self)

        if self.current_mode == "favorites":
            # Im Favoriten-Modus: Nur Entfernen anzeigen
            action_remove = menu.addAction("Aus Favoriten entfernen")
            action = menu.exec(self.channel_list.mapToGlobal(position))
            if action == action_remove:
                self._remove_from_favorites(data)
        else:
            # In anderen Modi: Hinzufuegen/Entfernen je nach Status
            is_fav = self._is_item_favorite(data, account.name)
            if is_fav:
                action_toggle = menu.addAction("Aus Favoriten entfernen")
            else:
                action_toggle = menu.addAction("Zu Favoriten hinzufuegen")

            action = menu.exec(self.channel_list.mapToGlobal(position))
            if action == action_toggle:
                self._toggle_favorite(data, account.name)

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
