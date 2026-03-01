"""
Favoriten: Laden, Hinzufuegen, Entfernen, Anzeige-Updates
"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QAbstractItemView, QScroller
)

from xtream_api import LiveStream, VodStream, Series
from favorites_manager import Favorite


class FavoritesMixin:

    def _set_fav_filter(self, ftype):
        """Setzt den Favoriten-Filter und aktualisiert die Button-Hervorhebung."""
        self._current_fav_filter = ftype
        for t, btn in self._fav_filter_buttons.items():
            btn.setProperty("active", "true" if t == ftype else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._load_favorites()

    def _load_favorites(self):
        """Laedt und zeigt Favoriten an, gefiltert nach aktuellem Typ-Filter."""
        import asyncio
        ftype = getattr(self, "_current_fav_filter", None)
        is_grid = ftype in ("vod", "series")

        QScroller.ungrabGesture(self.channel_list.viewport())
        if is_grid:
            self.channel_list.setViewMode(QListWidget.IconMode)
            self.channel_list.setResizeMode(QListWidget.Adjust)
            self.channel_list.setWordWrap(True)
            self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            self.channel_list.verticalScrollBar().setSingleStep(60)
            self._update_grid_size()
            QScroller.grabGesture(self.channel_list.viewport(), QScroller.LeftMouseButtonGesture)
        else:
            self.channel_list.setViewMode(QListWidget.ListMode)
            self.channel_list.setIconSize(QSize(0, 0))
            self.channel_list.setGridSize(QSize())
            self.channel_list.setResizeMode(QListWidget.Fixed)
            self.channel_list.setWordWrap(False)
            self.channel_list.setSpacing(0)
            self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self._apply_channel_list_style(grid_mode=is_grid)
        self.epg_panel.setVisible(False)
        self.channel_list.clear()

        account = self.account_manager.get_selected()
        if not account:
            return

        if ftype:
            favorites = self.favorites_manager.get_by_type(ftype, account.name)
        else:
            favorites = self.favorites_manager.get_all(account.name)

        type_icons = {"live": "📺", "vod": "🎬", "series": "📖"}
        cell_size = self.channel_list.gridSize()
        for fav in favorites:
            if is_grid:
                list_item = QListWidgetItem(fav.name)
                if cell_size.isValid():
                    list_item.setSizeHint(cell_size)
            else:
                icon = type_icons.get(fav.type, "★")
                list_item = QListWidgetItem(f"{icon} {fav.name}")
            list_item.setData(Qt.UserRole, fav)
            self.channel_list.addItem(list_item)

        label = {"live": "Live TV", "vod": "Filme", "series": "Serien"}.get(ftype, "Favoriten")
        self.status_bar.showMessage(f"{len(favorites)} {label}")

        if is_grid:
            asyncio.ensure_future(self._load_item_posters())

    def _is_item_favorite(self, data, account_name: str) -> bool:
        """Prueft ob ein Item ein Favorit ist"""
        if isinstance(data, LiveStream):
            return self.favorites_manager.is_favorite(data.stream_id, "live", account_name)
        elif isinstance(data, VodStream):
            return self.favorites_manager.is_favorite(data.stream_id, "vod", account_name)
        elif isinstance(data, Series):
            return self.favorites_manager.is_favorite(data.series_id, "series", account_name)
        return False

    def _toggle_favorite(self, data, account_name: str):
        """Wechselt Favoriten-Status eines Items"""
        favorite = self._create_favorite_from_data(data, account_name)
        if favorite:
            is_now_fav = self.favorites_manager.toggle(favorite)
            if is_now_fav:
                self.status_bar.showMessage(f"'{favorite.name}' zu Favoriten hinzugefuegt")
            else:
                self.status_bar.showMessage(f"'{favorite.name}' aus Favoriten entfernt")
            # Liste aktualisieren um Stern anzuzeigen/entfernen
            self._update_current_list_item_display()

    def _remove_from_favorites(self, fav: Favorite):
        """Entfernt einen Favoriten"""
        self.favorites_manager.remove(fav.id, fav.type, fav.account_name)
        self.status_bar.showMessage(f"'{fav.name}' aus Favoriten entfernt")
        self._load_favorites()

    def _create_favorite_from_data(self, data, account_name: str) -> Favorite | None:
        """Erstellt ein Favorite-Objekt aus Stream/Series-Daten"""
        if isinstance(data, LiveStream):
            return Favorite(
                id=data.stream_id,
                name=data.name,
                type="live",
                icon=data.stream_icon,
                account_name=account_name
            )
        elif isinstance(data, VodStream):
            return Favorite(
                id=data.stream_id,
                name=data.name,
                type="vod",
                icon=data.stream_icon,
                container_extension=data.container_extension,
                account_name=account_name
            )
        elif isinstance(data, Series):
            return Favorite(
                id=data.series_id,
                name=data.name,
                type="series",
                icon=data.cover,
                account_name=account_name
            )
        return None

    def _update_current_list_item_display(self):
        """Aktualisiert die Anzeige der aktuellen Liste (Stern-Markierung)"""
        account = self.account_manager.get_selected()
        if not account or self.current_mode == "favorites":
            return

        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            data = item.data(Qt.UserRole)
            if not data:
                continue

            is_fav = self._is_item_favorite(data, account.name)
            name = self._get_item_name(data)

            if is_fav:
                item.setText(f"\u2605 {name}")
            else:
                item.setText(name)
