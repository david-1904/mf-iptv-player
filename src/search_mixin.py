"""
Suche: Text-Eingabe, Ausfuehrung, Ergebnis-Anzeige
"""
import asyncio

from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtCore import Qt, QTimer


class SearchMixin:

    def _set_search_filter(self, fkey: str):
        """Setzt den Such-Filter und wiederholt die Suche falls aktiv."""
        self._search_filter = fkey
        for k, btn in self._search_filter_buttons.items():
            btn.setProperty("active", "true" if k == fkey else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if self.search_input.text().strip():
            self._execute_search()

    def _on_search_text_changed(self, text: str):
        """Wechselt bei Texteingabe in den Suchmodus, bei leerem Feld zurueck"""
        if text.strip() and self.current_mode != "search":
            self._switch_mode("search")
        elif not text.strip() and self.current_mode == "search":
            self._switch_mode(self._last_mode_before_search or "live")

        if not hasattr(self, "_search_debounce_timer"):
            self._search_debounce_timer = QTimer()
            self._search_debounce_timer.setSingleShot(True)
            self._search_debounce_timer.timeout.connect(self._execute_search)
        if text.strip():
            self._search_debounce_timer.start(400)
        else:
            self._search_debounce_timer.stop()

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

            sf = getattr(self, "_search_filter", "all")

            # Live-Streams filtern
            if sf in ("all", "live"):
                for item in self._search_cache_live:
                    if not item.name:
                        continue
                    if query_lower in item.name.lower():
                        prefix = "" if sf == "live" else "[Live] "
                        list_item = QListWidgetItem(f"{prefix}{item.name}")
                        list_item.setData(Qt.UserRole, item)
                        self.channel_list.addItem(list_item)

            # VOD filtern
            if sf in ("all", "vod"):
                for item in self._search_cache_vod:
                    if not item.name:
                        continue
                    if query_lower in item.name.lower():
                        prefix = "" if sf == "vod" else "[Film] "
                        list_item = QListWidgetItem(f"{prefix}{item.name}")
                        list_item.setData(Qt.UserRole, item)
                        self.channel_list.addItem(list_item)

            # Serien filtern
            if sf in ("all", "series"):
                for item in self._search_cache_series:
                    if not item.name:
                        continue
                    if query_lower in item.name.lower():
                        prefix = "" if sf == "series" else "[Serie] "
                        list_item = QListWidgetItem(f"{prefix}{item.name}")
                        list_item.setData(Qt.UserRole, item)
                        self.channel_list.addItem(list_item)

            count = self.channel_list.count()
            self._hide_loading(f"{count} Treffer fuer \"{query}\"")

        except Exception as e:
            self._hide_loading(f"Suchfehler: {e}")
