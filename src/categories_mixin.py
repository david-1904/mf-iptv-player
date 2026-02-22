"""
Kategorien & Navigation: Laden, Filtern, Sortieren, Verstecken
"""
import asyncio
import aiohttp

from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QMenu, QAbstractItemView,
    QScroller, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QCheckBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap

from xtream_api import LiveStream, VodStream, Series


class CategoriesMixin:

    def _switch_mode(self, mode: str):
        if mode == "search" and self.current_mode != "search":
            self._last_mode_before_search = self.current_mode
        self.current_mode = mode

        # Buttons aktualisieren
        self.btn_live.setChecked(mode == "live")
        self.btn_vod.setChecked(mode == "vod")
        self.btn_series.setChecked(mode == "series")
        self.btn_favorites.setChecked(mode == "favorites")
        self.btn_history.setChecked(mode == "history")
        self.btn_recordings.setChecked(mode == "recordings")

        # Kategorie nur bei Live/VOD/Serien anzeigen
        self.category_btn.setVisible(mode in ("live", "vod", "series"))
        if mode not in ("live", "vod", "series"):
            self.category_list.hide()

        # Sortierung nur bei VOD/Serien anzeigen
        self.sort_widget.setVisible(mode in ("vod", "series"))

        # Detail-Ansichten zuruecksetzen
        self.channel_stack.setCurrentIndex(0)

        # Player-Layout anpassen wenn Player laeuft
        if self.player_area.isVisible() and not self._player_maximized:
            is_grid_mode = mode in ("vod", "series")
            if is_grid_mode:
                # Grid-Modus: Kanalliste voll breit, Player als PiP
                self.channel_area.show()
                self.channel_area.setMinimumWidth(0)
                self.channel_area.setMaximumWidth(16777215)
                if not self._pip_mode:
                    self._enter_pip_mode()
            elif self._current_stream_type == "vod":
                # Film laeuft + Wechsel zu Live/etc: Kanalliste anzeigen, side-by-side
                self.channel_area.show()
                self.channel_area.setFixedWidth(320)
                if self._pip_mode:
                    self._exit_pip_mode()
            else:
                # Live laeuft: normal side-by-side
                self.channel_area.show()
                if self._pip_mode:
                    self._exit_pip_mode()

        if mode == "favorites":
            self._load_favorites()
        elif mode == "history":
            self._load_history()
        elif mode == "recordings":
            self._load_recordings()
        elif mode == "search":
            # Liste fuer Suchmodus vorbereiten
            QScroller.ungrabGesture(self.channel_list.viewport())
            self.channel_list.setViewMode(QListWidget.ListMode)
            self.channel_list.setIconSize(QSize(0, 0))
            self.channel_list.setGridSize(QSize())
            self.channel_list.setResizeMode(QListWidget.Fixed)
            self.channel_list.setWordWrap(False)
            self.channel_list.setSpacing(0)
            self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
            self._apply_channel_list_style(grid_mode=False)
            self.epg_panel.setVisible(False)
            self.channel_list.clear()
            self.status_bar.showMessage("Enter druecken zum Suchen")
        else:
            # Sofort Loading-Zustand zeigen (nicht auf async warten)
            self.channel_list.clear()
            self.channel_list.hide()
            self.epg_panel.hide()
            self._loading_text.setText("Lade...")
            self.channel_loading.show()
            asyncio.ensure_future(self._load_categories())

    async def _load_categories(self):
        if not self.api:
            return

        self._show_loading("Lade Kategorien...")

        try:
            if self.current_mode == "live":
                if not self.live_categories:
                    self.live_categories = await self.api.get_live_categories()
                categories = self.live_categories
            elif self.current_mode == "vod":
                if not self.vod_categories:
                    self.vod_categories = await self.api.get_vod_categories()
                categories = self.vod_categories
            else:
                if not self.series_categories:
                    self.series_categories = await self.api.get_series_categories()
                categories = self.series_categories

            # Versteckte Kategorien filtern
            account = self.account_manager.get_selected()
            account_name = account.name if account else ""
            visible_cats = [
                cat for cat in categories
                if not self.hidden_categories_manager.is_hidden(account_name, self.current_mode, cat.category_id)
            ]

            self._category_items = [(cat.category_name, cat.category_id) for cat in visible_cats]
            self._current_category_index = 0 if visible_cats else -1
            self.category_list.clear()
            for cat in visible_cats:
                self.category_list.addItem(cat.category_name)
            self.category_list.hide()

            # "Ausgeblendete verwalten"-Button nur zeigen wenn es versteckte gibt
            has_hidden = len(self.hidden_categories_manager.get_hidden(account_name, self.current_mode)) > 0
            self.manage_hidden_btn.setVisible(has_hidden)

            if visible_cats:
                self.category_btn.setText(f"{visible_cats[0].category_name}  \u25BE")
                await self._load_items(visible_cats[0].category_id)
            else:
                self.category_btn.setText("Keine Kategorien")

            self._hide_loading()
        except Exception as e:
            self._show_loading_error(str(e))

    def _sort_items(self, items):
        """Sortiert VOD/Serien-Items nach aktueller Sortierauswahl"""
        sort_index = self.sort_combo.currentIndex()
        if sort_index == 0:  # Standard
            return items
        elif sort_index == 1:  # Zuletzt hinzugefuegt
            return sorted(items, key=lambda x: x.added or "", reverse=True)
        elif sort_index == 2:  # Bewertung (beste zuerst)
            def rating_key(x):
                try:
                    return float(x.rating) if x.rating else 0.0
                except ValueError:
                    return 0.0
            return sorted(items, key=rating_key, reverse=True)
        elif sort_index == 3:  # A - Z
            return sorted(items, key=lambda x: x.name.lower())
        elif sort_index == 4:  # Z - A
            return sorted(items, key=lambda x: x.name.lower(), reverse=True)
        return items

    def _on_sort_changed(self):
        """Sortierung geaendert - Kategorie neu laden"""
        if self.current_mode not in ("vod", "series"):
            return
        if self._current_category_index < 0:
            return
        _, cat_id = self._category_items[self._current_category_index]
        asyncio.ensure_future(self._load_items(cat_id))

    def _toggle_category_list(self):
        """Klappt die Kategorie-Liste auf/zu"""
        if self.category_list.isVisible():
            self._close_category_list()
        else:
            self.category_list.show()
            self.channel_list.hide()
            self.epg_panel.hide()
            # Zur aktuellen Kategorie scrollen
            if 0 <= self._current_category_index < self.category_list.count():
                self.category_list.setCurrentRow(self._current_category_index)
                self.category_list.scrollToItem(self.category_list.currentItem())
            name = self._category_items[self._current_category_index][0] if self._current_category_index >= 0 else "Kategorie"
            self.category_btn.setText(f"{name}  \u25B4")

    def _close_category_list(self):
        """Schliesst die Kategorie-Liste und zeigt Kanalliste wieder"""
        self.category_list.hide()
        self.channel_list.show()
        if self.current_mode == "live":
            self.epg_panel.show()
        name = self._category_items[self._current_category_index][0] if self._current_category_index >= 0 else "Kategorie"
        self.category_btn.setText(f"{name}  \u25BE")

    def _on_category_list_clicked(self, item: QListWidgetItem):
        """Kategorie aus der inline-Liste gewaehlt"""
        # Nur bei Einzelklick ohne Kontextmenue
        selected = self.category_list.selectedItems()
        if len(selected) > 1:
            return
        index = self.category_list.row(item)
        self._current_category_index = index
        name, cat_id = self._category_items[index]
        self._close_category_list()
        asyncio.ensure_future(self._load_items(cat_id))

    def _on_category_context_menu(self, pos):
        """Kontextmenue fuer Kategorie-Liste (Ausblenden)"""
        selected = self.category_list.selectedItems()
        if not selected:
            return

        menu = QMenu(self)
        if len(selected) == 1:
            action = menu.addAction("Kategorie ausblenden")
        else:
            action = menu.addAction(f"{len(selected)} Kategorien ausblenden")

        result = menu.exec(self.category_list.mapToGlobal(pos))
        if result != action:
            return

        account = self.account_manager.get_selected()
        if not account:
            return

        for item in selected:
            index = self.category_list.row(item)
            if 0 <= index < len(self._category_items):
                name, cat_id = self._category_items[index]
                self.hidden_categories_manager.hide(account.name, self.current_mode, cat_id, name)

        asyncio.ensure_future(self._load_categories())

    def _show_hidden_categories_dialog(self):
        """Zeigt Dialog zum Verwalten ausgeblendeter Kategorien"""
        account = self.account_manager.get_selected()
        if not account:
            return

        hidden = self.hidden_categories_manager.get_hidden(account.name, self.current_mode)
        if not hidden:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Ausgeblendete Kategorien")
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)

        label = QLabel(f"{len(hidden)} ausgeblendete Kategorien:")
        layout.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        checkboxes: list[tuple[QCheckBox, str]] = []
        for entry in hidden:
            cb = QCheckBox(entry.category_name or entry.category_id)
            cb.setChecked(False)
            scroll_layout.addWidget(cb)
            checkboxes.append((cb, entry.category_id))

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        unhide_selected_btn = QPushButton("Ausgewaehlte einblenden")
        unhide_all_btn = QPushButton("Alle einblenden")
        btn_layout.addWidget(unhide_selected_btn)
        btn_layout.addWidget(unhide_all_btn)
        layout.addLayout(btn_layout)

        def unhide_selected():
            for cb, cat_id in checkboxes:
                if cb.isChecked():
                    self.hidden_categories_manager.unhide(account.name, self.current_mode, cat_id)
            dialog.accept()
            asyncio.ensure_future(self._load_categories())

        def unhide_all():
            self.hidden_categories_manager.unhide_all(account.name, self.current_mode)
            dialog.accept()
            asyncio.ensure_future(self._load_categories())

        unhide_selected_btn.clicked.connect(unhide_selected)
        unhide_all_btn.clicked.connect(unhide_all)

        dialog.exec()

    async def _load_items(self, category_id: str):
        if not self.api:
            return

        self._show_loading("Lade Inhalte...")
        self.channel_list.clear()

        # View-Modus je nach Kategorie umschalten
        is_grid = self.current_mode in ("vod", "series")
        # Scroller-Zustand immer zuerst aufraumen
        QScroller.ungrabGesture(self.channel_list.viewport())
        if is_grid:
            self.channel_list.setViewMode(QListWidget.IconMode)
            self.channel_list.setResizeMode(QListWidget.Adjust)
            self.channel_list.setWordWrap(True)
            self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            self.channel_list.verticalScrollBar().setSingleStep(60)
            self._update_grid_size()
            # Drag-to-Scroll im Grid-Modus
            QScroller.grabGesture(self.channel_list.viewport(), QScroller.LeftMouseButtonGesture)
        else:
            self.channel_list.setViewMode(QListWidget.ListMode)
            self.channel_list.setIconSize(QSize(32, 32))
            self.channel_list.setGridSize(QSize())
            self.channel_list.setResizeMode(QListWidget.Fixed)
            self.channel_list.setWordWrap(False)
            self.channel_list.setSpacing(0)
            self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self._apply_channel_list_style(grid_mode=is_grid)
        self.epg_panel.setVisible(self.current_mode == "live")

        try:
            if self.current_mode == "live":
                items = await self.api.get_live_streams(category_id)
                for item in items:
                    name = item.name
                    if item.tv_archive:
                        name += "  \u25C2\u25C2"
                    list_item = QListWidgetItem(name)
                    list_item.setData(Qt.UserRole, item)
                    self.channel_list.addItem(list_item)

            elif self.current_mode == "vod":
                items = await self.api.get_vod_streams(category_id)
                items = self._sort_items(items)
                cell_size = self.channel_list.gridSize()
                for item in items:
                    list_item = QListWidgetItem(item.name)
                    list_item.setData(Qt.UserRole, item)
                    if cell_size.isValid():
                        list_item.setSizeHint(cell_size)
                    if item.rating and item.rating not in ("0", ""):
                        list_item.setToolTip(f"Bewertung: {item.rating}")
                    self.channel_list.addItem(list_item)

            else:  # series
                items = await self.api.get_series(category_id)
                items = self._sort_items(items)
                cell_size = self.channel_list.gridSize()
                for item in items:
                    list_item = QListWidgetItem(item.name)
                    list_item.setData(Qt.UserRole, item)
                    if cell_size.isValid():
                        list_item.setSizeHint(cell_size)
                    if item.rating and item.rating not in ("0", ""):
                        list_item.setToolTip(f"Bewertung: {item.rating}")
                    self.channel_list.addItem(list_item)

            self._hide_loading(f"{self.channel_list.count()} Eintraege geladen")

            # Poster/Logos laden
            asyncio.ensure_future(self._load_item_posters())

        except Exception as e:
            self._show_loading_error(str(e))

    async def _load_item_posters(self):
        """Laedt Poster/Cover/Logos"""
        self._poster_load_generation += 1
        current_gen = self._poster_load_generation
        icon_size = self.channel_list.iconSize()
        sem = asyncio.Semaphore(8)

        items_to_load = []
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            data = item.data(Qt.UserRole)
            url = ""
            if isinstance(data, LiveStream):
                url = data.stream_icon
            elif isinstance(data, VodStream):
                url = data.stream_icon
            elif isinstance(data, Series):
                url = data.cover
            if url:
                items_to_load.append((i, url))

        if not items_to_load:
            return

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async def load_one(index, url):
                async with sem:
                    if self._poster_load_generation != current_gen:
                        return
                    pixmap = await self._fetch_poster(session, url, icon_size.width(), icon_size.height())
                    if pixmap and self._poster_load_generation == current_gen:
                        item = self.channel_list.item(index)
                        if item:
                            item.setIcon(QIcon(pixmap))

            await asyncio.gather(
                *[load_one(i, url) for i, url in items_to_load],
                return_exceptions=True
            )

    def _update_grid_size(self):
        """Berechnet Grid-Größe dynamisch basierend auf verfügbarer Breite."""
        if self.current_mode not in ("vod", "series"):
            return
        available = self.channel_list.viewport().width()
        # Fallback wenn channel_list versteckt (Lade-Zustand): channel_area nutzen
        if available < 100:
            available = self.channel_area.width()
        if available < 100:
            return  # Noch nicht bereit
        # Spalten: mindestens 180px pro Zelle, maximal 8 Spalten
        min_cell_w = 180
        max_cols = 8
        cols = max(1, min(max_cols, available // min_cell_w))
        cell_w = available // cols
        # Poster füllt die Zelle mit je 8px Rand links/rechts
        poster_w = cell_w - 16
        poster_h = int(poster_w * 1.5)
        cell_h = poster_h + 48
        old_icon_w = self.channel_list.iconSize().width()
        self.channel_list.setIconSize(QSize(poster_w, poster_h))
        self.channel_list.setGridSize(QSize(cell_w, cell_h))
        self.channel_list.setSpacing(0)
        self.channel_list.setUniformItemSizes(True)
        # SizeHint aller vorhandenen Items aktualisieren
        hint = QSize(cell_w, cell_h)
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            if item:
                item.setSizeHint(hint)
        # Poster neu laden wenn sich Größe wesentlich geändert hat
        if abs(old_icon_w - poster_w) > 20 and self.channel_list.count() > 0:
            asyncio.ensure_future(self._load_item_posters())

    async def _fetch_poster(self, session: aiohttp.ClientSession, url: str, w: int, h: int) -> QPixmap | None:
        """Laedt ein Bild, skaliert und cached es"""
        cache_key = f"{url}_{w}x{h}"
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    pixmap = QPixmap()
                    pixmap.loadFromData(data)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self._image_cache[cache_key] = scaled
                        return scaled
        except Exception:
            pass

        self._image_cache[cache_key] = None
        return None
