"""
Suche: Text-Eingabe, Ausfuehrung, Ergebnis-Anzeige
"""
import asyncio

from PySide6.QtWidgets import QListWidgetItem

from PySide6.QtCore import Qt


class SearchMixin:

    def _on_search_text_changed(self, text: str):
        """Wechselt bei Texteingabe in den Suchmodus, bei leerem Feld zurueck"""
        if text.strip() and self.current_mode != "search":
            self._switch_mode("search")
        elif not text.strip() and self.current_mode == "search":
            self._switch_mode(self._last_mode_before_search or "live")

    def _execute_search(self):
        """Startet die Suche basierend auf dem Suchfeld-Text"""
        query = self.search_input.text().strip()
        if not query or not self.api:
            return
        if self.current_mode != "search":
            self._switch_mode("search")
        asyncio.ensure_future(self._perform_search(query))

    async def _perform_search(self, query: str):
        """Durchsucht alle Streams nach dem Suchbegriff"""
        self._show_loading("Suche laeuft...")
        self.channel_list.clear()
        query_lower = query.lower()

        try:
            # Cache aufbauen falls noch nicht vorhanden
            if not self._search_cache_loaded:
                self._search_cache_live = await self.api.get_live_streams()
                self._search_cache_vod = await self.api.get_vod_streams()
                try:
                    self._search_cache_series = await self.api.get_series()
                except Exception:
                    self._search_cache_series = []
                self._search_cache_loaded = True

            # Live-Streams filtern
            for item in self._search_cache_live:
                if not item.name:
                    continue
                if query_lower in item.name.lower():
                    name = f"[Live] {item.name}"
                    if item.tv_archive:
                        name += "  \u25C2\u25C2"
                    list_item = QListWidgetItem(name)
                    list_item.setData(Qt.UserRole, item)
                    self.channel_list.addItem(list_item)

            # VOD filtern
            for item in self._search_cache_vod:
                if not item.name:
                    continue
                if query_lower in item.name.lower():
                    list_item = QListWidgetItem(f"[Film] {item.name}")
                    list_item.setData(Qt.UserRole, item)
                    self.channel_list.addItem(list_item)

            # Serien filtern
            for item in self._search_cache_series:
                if not item.name:
                    continue
                if query_lower in item.name.lower():
                    list_item = QListWidgetItem(f"[Serie] {item.name}")
                    list_item.setData(Qt.UserRole, item)
                    self.channel_list.addItem(list_item)

            count = self.channel_list.count()
            self._hide_loading(f"{count} Treffer fuer \"{query}\"")

        except Exception as e:
            self._hide_loading(f"Suchfehler: {e}")
