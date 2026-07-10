"""
Suche: Text-Eingabe, Ausfuehrung, Ergebnis-Anzeige
"""
import asyncio

from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtCore import Qt, QTimer
from i18n import _tr


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
            self._search_filter = "all"
            for k, btn in self._search_filter_buttons.items():
                btn.setProperty("active", "true" if k == "all" else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
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

    @staticmethod
    def _matches_query(name: str, words: list[str]) -> bool:
        """True wenn alle Suchwörter im Namen vorkommen (unabhängig von Reihenfolge)."""
        name_lower = name.lower()
        return all(w in name_lower for w in words)

    @staticmethod
    def _cast_match(item, words: list[str]) -> str:
        """Prüft ob eine Person aus Besetzung/Regie zur Suche passt.

        Gibt den Namen der passenden Person zurück (für die Anzeige),
        sonst einen leeren String. Es müssen alle Suchwörter im Namen
        derselben Person vorkommen, damit "tom hanks" gezielt trifft.
        """
        people: list[str] = []
        for blob in (getattr(item, "cast", ""), getattr(item, "director", "")):
            if blob:
                people.extend(p.strip() for p in blob.split(",") if p.strip())
        for person in people:
            pl = person.lower()
            if all(w in pl for w in words):
                return person
        return ""

    @staticmethod
    def _actor_suffix(actor: str, words: list[str]) -> str:
        """Haengt den gefundenen Schauspieler zur Erklaerung des Treffers an –
        aber nicht, wenn die Suche exakt dieser Name war (dann stuende der Name
        in jeder Ergebniszeile und waere reine Redundanz)."""
        if not actor or set(actor.lower().split()) == set(words):
            return ""
        return f"  ·  {actor}"

    def _add_search_result(self, label: str, item):
        """Fügt einen Treffer zur Ergebnisliste hinzu."""
        list_item = QListWidgetItem(label)
        list_item.setData(Qt.UserRole, item)
        self.channel_list.addItem(list_item)

    async def _perform_search(self, query: str):
        """Durchsucht alle Streams nach dem Suchbegriff"""
        # Falls die Suche aus einer offenen VOD-/Serien-Detailansicht heraus
        # gestartet wird: zurueck zur Ergebnisliste (sonst bliebe die Detailseite
        # sichtbar und die Treffer landen unsichtbar dahinter).
        self._restore_detail_layout()
        self.channel_stack.setCurrentIndex(0)
        self._show_loading(_tr("Suche läuft..."))
        self.channel_list.clear()
        words = query.lower().split()

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
                    if self._matches_query(item.name, words):
                        prefix = "" if sf == "live" else "[Live] "
                        list_item = QListWidgetItem(f"{prefix}{item.name}")
                        list_item.setData(Qt.UserRole, item)
                        self.channel_list.addItem(list_item)

            # VOD filtern (Name oder Besetzung/Regie)
            if sf in ("all", "vod"):
                prefix = "" if sf == "vod" else "[Film] "
                for item in self._search_cache_vod:
                    if not item.name:
                        continue
                    if self._matches_query(item.name, words):
                        self._add_search_result(f"{prefix}{item.name}", item)
                    else:
                        actor = self._cast_match(item, words)
                        if actor:
                            self._add_search_result(f"{prefix}{item.name}{self._actor_suffix(actor, words)}", item)

            # Serien filtern (Name oder Besetzung/Regie)
            if sf in ("all", "series"):
                prefix = "" if sf == "series" else "[Serie] "
                for item in self._search_cache_series:
                    if not item.name:
                        continue
                    if self._matches_query(item.name, words):
                        self._add_search_result(f"{prefix}{item.name}", item)
                    else:
                        actor = self._cast_match(item, words)
                        if actor:
                            self._add_search_result(f"{prefix}{item.name}{self._actor_suffix(actor, words)}", item)

            count = self.channel_list.count()
            self._hide_loading(_tr('{} Treffer f\u00fcr "{}"').format(count, query))

        except Exception as e:
            self._hide_loading(_tr("Suchfehler: {}").format(e))
