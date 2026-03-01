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
from PySide6.QtGui import QIcon, QPixmap, QPainter, QFont, QFontMetrics, QColor

from xtream_api import LiveStream, VodStream, Series


class CategoriesMixin:

    def _switch_mode(self, mode: str):
        if mode == "search" and self.current_mode != "search":
            self._last_mode_before_search = self.current_mode
        self.current_mode = mode
        # Session-Modus merken
        if mode in ("live", "vod", "series"):
            account = self.account_manager.get_selected()
            if account:
                self.session_manager.save_mode(account.name, mode)
        # Detailpanel schliessen bei Moduswechsel
        self._hide_channel_detail()

        # Buttons aktualisieren
        self.btn_live.setChecked(mode == "live")
        self.btn_vod.setChecked(mode == "vod")
        self.btn_series.setChecked(mode == "series")
        self.btn_favorites.setChecked(mode == "favorites")
        self.btn_history.setChecked(mode == "history")
        self.btn_recordings.setChecked(mode == "recordings")

        # Kategorie nur bei Live/VOD/Serien anzeigen
        self.category_row.setVisible(mode in ("live", "vod", "series"))
        if mode not in ("live", "vod", "series"):
            self.category_list.hide()

        # Favoriten-Filter nur im Favoriten-Modus
        self.fav_filter_row.setVisible(mode == "favorites")
        if mode == "favorites":
            self._set_fav_filter(None)  # Filter zurücksetzen auf "Alle"

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
                self.channel_area.setFixedWidth(360)
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

        # Falls Kategorie-Dropdown offen war, korrekt schliessen
        if self.category_list.isVisible():
            self.category_list.hide()
            self._epg_splitter.show()

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

            # Versteckte Kategorien filtern + leere Namen ausfiltern
            account = self.account_manager.get_selected()
            account_name = account.name if account else ""
            visible_cats = [
                cat for cat in categories
                if cat.category_name.strip()
                and not self.hidden_categories_manager.is_hidden(account_name, self.current_mode, cat.category_id)
            ]

            self._category_items = [(cat.category_name, cat.category_id) for cat in visible_cats]

            # Session-Restore: letzte Kategorie wiederfinden
            session = self.session_manager.get(account_name, self.current_mode)
            target_cat_idx = 0
            if session and visible_cats:
                saved_cat_id = session.get("category_id")
                for i, cat in enumerate(visible_cats):
                    if cat.category_id == saved_cat_id:
                        target_cat_idx = i
                        break

            self._current_category_index = target_cat_idx if visible_cats else -1
            self.category_list.clear()
            for cat in visible_cats:
                self.category_list.addItem(cat.category_name)
            self.category_list.hide()

            # "Ausgeblendete verwalten"-Button nur zeigen wenn es versteckte gibt
            has_hidden = len(self.hidden_categories_manager.get_hidden(account_name, self.current_mode)) > 0
            self.manage_hidden_btn.setVisible(has_hidden)

            if visible_cats:
                target_cat = visible_cats[target_cat_idx]
                self.category_btn.setText(f"{target_cat.category_name}  \u25BE")
                await self._load_items(target_cat.category_id)
                if session:
                    self._restore_session_item(session)
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
            self._epg_splitter.hide()
            # Zur aktuellen Kategorie scrollen
            if 0 <= self._current_category_index < self.category_list.count():
                self.category_list.setCurrentRow(self._current_category_index)
                self.category_list.scrollToItem(self.category_list.currentItem())
            name = self._category_items[self._current_category_index][0] if self._current_category_index >= 0 else "Kategorie"
            self.category_btn.setText(f"{name}  \u25B4")

    def _close_category_list(self):
        """Schliesst die Kategorie-Liste und zeigt Kanalliste wieder"""
        self.category_list.hide()
        self._epg_splitter.show()
        self.channel_list.show()
        pass
        name = self._category_items[self._current_category_index][0] if self._current_category_index >= 0 else "Kategorie"
        self.category_btn.setText(f"{name}  \u25BE")

    def _on_category_list_clicked(self, item: QListWidgetItem):
        """Kategorie aus der inline-Liste gewaehlt"""
        index = self.category_list.row(item)
        self._current_category_index = index
        name, cat_id = self._category_items[index]
        self._close_category_list()
        asyncio.ensure_future(self._load_items(cat_id))

    def _on_category_context_menu(self, pos):
        """Kontextmenue fuer Kategorie-Liste (Ausblenden)"""
        menu = QMenu(self)
        action = menu.addAction("Kategorien ausblenden...")
        result = menu.exec(self.category_list.mapToGlobal(pos))
        if result == action:
            self._show_hide_categories_dialog()

    def _show_hide_categories_dialog(self):
        """Zeigt Dialog zum Ausblenden von Kategorien (mit Checkboxen)"""
        account = self.account_manager.get_selected()
        if not account or not self._category_items:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Kategorien ausblenden")
        dialog.setMinimumWidth(350)
        layout = QVBoxLayout(dialog)

        label = QLabel("Kategorien zum Ausblenden auswählen:")
        layout.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        checkboxes: list[tuple[QCheckBox, str, str]] = []
        for name, cat_id in self._category_items:
            cb = QCheckBox(name)
            cb.setChecked(False)
            scroll_layout.addWidget(cb)
            checkboxes.append((cb, cat_id, name))

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        hide_btn = QPushButton("Ausblenden")
        cancel_btn = QPushButton("Abbrechen")
        btn_layout.addWidget(hide_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def do_hide():
            any_hidden = False
            for cb, cat_id, name in checkboxes:
                if cb.isChecked():
                    self.hidden_categories_manager.hide(account.name, self.current_mode, cat_id, name)
                    any_hidden = True
            dialog.accept()
            if any_hidden:
                asyncio.ensure_future(self._load_categories())

        hide_btn.clicked.connect(do_hide)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec()

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

    def _restore_session_item(self, session: dict):
        """Stellt das zuletzt geöffnete Item aus der Session wieder her"""
        mode = self.current_mode
        if mode not in ("live", "vod", "series"):
            return

        # Nicht aktivieren wenn bereits aktiv (z.B. nach manuellem Refresh)
        already_active = (
            (mode == "live" and self._current_playing_stream_id is not None) or
            (mode == "vod" and getattr(self, "_current_vod", None) is not None) or
            (mode == "series" and getattr(self, "_current_series", None) is not None)
        )

        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            data = item.data(Qt.UserRole)

            match = False
            if mode == "live" and isinstance(data, LiveStream):
                match = data.stream_id == session.get("stream_id")
            elif mode == "vod" and isinstance(data, VodStream):
                match = data.stream_id == session.get("stream_id")
            elif mode == "series" and isinstance(data, Series):
                match = data.series_id == session.get("series_id")

            if match:
                self.channel_list.setCurrentRow(i)
                self.channel_list.scrollToItem(item)
                if not already_active and mode == "live":
                    self._on_channel_selected(item)
                break

    def _get_item_rating(self, data) -> str:
        """Extrahiert die anzuzeigende Bewertung aus einem VOD/Serien-Item"""
        if not isinstance(data, (VodStream, Series)):
            return ""
        rating_str = data.rating
        if rating_str and rating_str not in ("0", "0.0", ""):
            try:
                val = float(rating_str)
                if val > 0:
                    return f"{val:.1f}"
            except (ValueError, TypeError):
                pass
        return ""

    def _draw_rating_badge(self, pixmap: QPixmap, rating: str) -> QPixmap:
        """Zeichnet einen kleinen farbigen Rating-Badge auf das Poster"""
        result = QPixmap(pixmap)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont()
        font.setPointSize(max(7, min(10, result.height() // 22)))
        font.setBold(True)
        painter.setFont(font)

        fm = QFontMetrics(font)
        text = f"\u2605 {rating}"
        text_w = fm.horizontalAdvance(text)
        text_h = fm.height()
        padding = 3
        badge_w = text_w + padding * 2
        badge_h = text_h + padding * 2

        # Farbe je nach Bewertung
        try:
            val = float(rating)
            if val >= 7.0:
                color = QColor(46, 160, 67)   # Grün
            elif val >= 5.0:
                color = QColor(200, 140, 20)  # Orange
            else:
                color = QColor(200, 50, 50)   # Rot
        except Exception:
            color = QColor(80, 80, 80)

        # Badge zeichnen
        painter.setOpacity(0.85)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(4, 4, badge_w, badge_h, 3, 3)

        painter.setOpacity(1.0)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(4 + padding, 4 + padding + fm.ascent(), text)

        painter.end()
        return result

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
        self.epg_panel.hide()

        try:
            if self.current_mode == "live":
                items = await self.api.get_live_streams(category_id)
                for item in items:
                    name = item.name
                    if item.tv_archive:
                        name += "  \u21BA"
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
            self._update_current_list_item_display()

            # Ersten Live-Sender markieren + EPG vorladen (Detail-Panel bleibt zu)
            if self.current_mode == "live" and self.channel_list.count() > 0:
                self._initial_epg_loaded = True
                first_item = self.channel_list.item(0)
                if first_item:
                    self.channel_list.setCurrentRow(0)
                    data = first_item.data(Qt.UserRole)
                    if hasattr(data, 'stream_id'):
                        self._detail_stream_data = data
                        self._current_epg_stream_id = data.stream_id
                        self._current_epg_has_catchup = getattr(data, 'tv_archive', False)
                        self.epg_channel_name.setText(data.name)
                        asyncio.ensure_future(self._load_epg(data.stream_id))

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
                items_to_load.append((i, url, data))

        if not items_to_load:
            return

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async def load_one(index, url, data):
                async with sem:
                    if self._poster_load_generation != current_gen:
                        return
                    pixmap = await self._fetch_poster(session, url, icon_size.width(), icon_size.height())
                    if pixmap and self._poster_load_generation == current_gen:
                        rating = self._get_item_rating(data)
                        if rating:
                            pixmap = self._draw_rating_badge(pixmap, rating)
                        item = self.channel_list.item(index)
                        if item:
                            item.setIcon(QIcon(pixmap))

            await asyncio.gather(
                *[load_one(i, url, data) for i, url, data in items_to_load],
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
