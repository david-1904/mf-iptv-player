"""
EPG-Programmsuche: Durchsucht laufendes und kommendes Programm quer über alle Sender.
EPG wird beim Öffnen vollständig geladen — erst danach ist die Suche aktiv.
Cache wird pro Account auf Disk gespeichert (TTL 4h).
"""
import asyncio
import json
import time
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QSizePolicy

_EPG_CACHE_TTL = 24 * 3600  # 24 Stunden


class EpgSearchMixin:

    # ── Öffnen ───────────────────────────────────────────────────────────────

    def _epg_search_open(self):
        """Beim Öffnen: EPG sofort laden, Eingabe gesperrt bis fertig."""
        self._epg_search_filter = "all"
        self._epg_search_ready = False
        self._epg_search_generation = getattr(self, '_epg_search_generation', 0) + 1
        self._epg_search_set_filter_ui("all")
        self._epg_search_set_locked(True)
        self._epg_search_show_placeholder("EPG wird geladen…")
        asyncio.ensure_future(self._epg_search_load_all())

    def _epg_search_set_locked(self, locked: bool):
        """Sperrt/entsperrt das Suchfeld."""
        self.epg_search_input.setEnabled(not locked)
        if locked:
            self.epg_search_input.setPlaceholderText("Bitte warten – lade Programmdaten…")
            self.epg_search_loading_widget.show()
        else:
            self.epg_search_input.setPlaceholderText("Sendungstitel oder Beschreibung suchen…")
            self.epg_search_loading_widget.hide()
            self.epg_search_input.setFocus()

    def _epg_search_show_placeholder(self, msg: str):
        lay = self.epg_search_results_layout
        while lay.count():
            w = lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #555; font-size: 13px; padding: 20px 8px;")
        lay.addWidget(lbl)
        lay.addStretch()

    # ── Disk-Cache ───────────────────────────────────────────────────────────

    def _epg_cache_path(self) -> Path:
        from platform_utils import get_config_dir
        account = self.account_manager.get_selected()
        name = account.name if account else "default"
        safe = re.sub(r'[^\w\-]', '_', name)[:40]
        return get_config_dir() / f"epg_cache_{safe}.json"

    def _epg_cache_load_from_disk(self) -> bool:
        """Lädt EPG-Cache von Disk. Gibt True zurück wenn Cache frisch genug ist."""
        path = self._epg_cache_path()
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("saved_at", 0) > _EPG_CACHE_TTL:
                return False
            from xtream_api import EpgEntry
            for sid_str, entries in data.get("entries", {}).items():
                sid = int(sid_str)
                if sid not in self._epg_cache:
                    self._epg_cache[sid] = [
                        EpgEntry(
                            title=e["title"],
                            start_timestamp=e["start"],
                            stop_timestamp=e["stop"],
                            description=e.get("desc", ""),
                        )
                        for e in entries
                    ]
            return True
        except Exception:
            return False

    def _epg_cache_save_to_disk(self):
        """Speichert aktuellen EPG-Cache auf Disk."""
        try:
            entries = {
                str(sid): [
                    {"title": e.title, "start": e.start_timestamp,
                     "stop": e.stop_timestamp, "desc": e.description}
                    for e in epg_list
                ]
                for sid, epg_list in self._epg_cache.items()
            }
            path = self._epg_cache_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"saved_at": int(time.time()), "entries": entries}, f)
        except Exception:
            pass

    # ── Laden ────────────────────────────────────────────────────────────────

    async def _epg_search_load_all(self):
        """Lädt EPG für alle Sender vollständig — erst dann Suche freischalten."""
        gen = self._epg_search_generation
        if not self.api:
            self._epg_search_set_locked(False)
            return

        if not getattr(self, '_search_cache_live', None):
            self._epg_search_set_status("Lade Senderliste…")
            self._search_cache_live = await self.api.get_live_streams()

        all_streams = getattr(self, '_search_cache_live', [])
        if not all_streams:
            self._epg_search_set_locked(False)
            self._epg_search_show_placeholder("Keine Sender verfügbar")
            return

        # Ausgeblendete Kategorien ausschließen
        account = self.account_manager.get_selected()
        account_name = account.name if account else ""
        hidden_ids = {
            e.category_id
            for e in self.hidden_categories_manager.get_hidden(account_name, "live")
        }
        streams = [s for s in all_streams if s.category_id not in hidden_ids]

        # Disk-Cache laden (einmal pro Session, wenn noch nicht geschehen)
        if not getattr(self, '_epg_disk_cache_loaded', False):
            self._epg_search_set_status("Lade gespeicherten EPG-Cache…")
            self._epg_disk_cache_loaded = True
            if self._epg_cache_load_from_disk():
                # Frischer Cache vom Disk — prüfen ob komplett
                missing_after_disk = [s for s in streams if s.stream_id not in self._epg_cache]
                if len(missing_after_disk) < len(streams) * 0.1:
                    # ≥ 90% gecacht → direkt fertig
                    self._epg_search_finish(gen)
                    return

        missing = [s for s in streams if s.stream_id not in self._epg_cache]
        total = len(streams)
        already_done = total - len(missing)

        if not missing:
            self._epg_search_finish(gen)
            return

        self.epg_search_progress.setMaximum(total)
        self.epg_search_progress.setValue(already_done)

        loaded = 0
        sem = asyncio.Semaphore(15)

        import aiohttp as _aiohttp
        connector = _aiohttp.TCPConnector(limit=20)
        timeout = _aiohttp.ClientTimeout(total=15)

        async def _load_all_with_session():
            nonlocal loaded
            async with _aiohttp.ClientSession(connector=connector, timeout=timeout) as shared_session:
                async def _load_one(stream):
                    nonlocal loaded
                    async with sem:
                        if self._epg_search_generation != gen:
                            return
                        if stream.stream_id not in self._epg_cache:
                            try:
                                epg = await self.api.get_short_epg(
                                    stream.stream_id, limit=20, session=shared_session
                                )
                                self._epg_cache[stream.stream_id] = epg
                            except Exception:
                                self._epg_cache[stream.stream_id] = []
                        loaded += 1
                        done = already_done + loaded
                        if self._epg_search_generation == gen:
                            self.epg_search_progress.setValue(done)
                            self._epg_search_set_status(f"Lade Programmdaten… {done}/{total}")

                await asyncio.gather(*[_load_one(s) for s in missing], return_exceptions=True)

        await _load_all_with_session()

        if self._epg_search_generation == gen:
            self._epg_search_finish(gen)

    def _epg_search_force_reload(self):
        """Löscht Cache und lädt EPG neu von der API."""
        try:
            self._epg_cache_path().unlink(missing_ok=True)
        except Exception:
            pass
        # Gecachte Einträge für Live-Streams verwerfen
        streams_by_id = {s.stream_id for s in getattr(self, '_search_cache_live', [])}
        for sid in list(self._epg_cache.keys()):
            if sid in streams_by_id:
                del self._epg_cache[sid]
        self._epg_disk_cache_loaded = False
        self._epg_search_ready = False
        self._epg_search_generation = getattr(self, '_epg_search_generation', 0) + 1
        self._epg_search_set_locked(True)
        self._epg_search_show_placeholder("EPG wird neu geladen…")
        asyncio.ensure_future(self._epg_search_load_all())

    def _epg_search_finish(self, gen: int):
        """Wird aufgerufen wenn alle EPG-Daten geladen sind."""
        if self._epg_search_generation != gen:
            return
        self._epg_search_ready = True
        self._epg_cache_save_to_disk()
        self._epg_search_set_locked(False)
        self._epg_search_show_placeholder("Sendungstitel oder Beschreibung eingeben")
        self._epg_search_set_status("")

    # ── Filter / Suche ───────────────────────────────────────────────────────

    def _epg_search_set_filter_ui(self, key: str):
        for k, btn in self._epg_filter_buttons.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _epg_search_filter_changed(self, key: str):
        self._epg_search_filter = key
        self._epg_search_set_filter_ui(key)
        if getattr(self, '_epg_search_ready', False) and self.epg_search_input.text().strip():
            self._epg_search_execute()

    def _epg_search_query_changed(self, text: str):
        if not getattr(self, '_epg_search_ready', False):
            return
        if not hasattr(self, '_epg_search_debounce'):
            self._epg_search_debounce = QTimer()
            self._epg_search_debounce.setSingleShot(True)
            self._epg_search_debounce.timeout.connect(self._epg_search_execute)
        if text.strip():
            self._epg_search_debounce.start(300)
        else:
            self._epg_search_debounce.stop()
            self._epg_search_show_placeholder("Sendungstitel oder Beschreibung eingeben")

    # ── Ergebnisse ───────────────────────────────────────────────────────────

    def _epg_search_execute(self):
        if not hasattr(self, 'epg_search_results_layout'):
            return

        query = self.epg_search_input.text().strip().lower()
        if not query:
            return

        now = datetime.now().timestamp()
        words = query.split()
        filt = getattr(self, '_epg_search_filter', 'all')

        account = self.account_manager.get_selected()
        account_name = account.name if account else ""
        hidden_ids = {
            e.category_id
            for e in self.hidden_categories_manager.get_hidden(account_name, "live")
        }
        streams_by_id = {
            s.stream_id: s
            for s in getattr(self, '_search_cache_live', [])
            if s.category_id not in hidden_ids
        }

        results = []
        for stream_id, entries in self._epg_cache.items():
            stream = streams_by_id.get(stream_id)
            if not stream:
                continue
            for entry in entries:
                if entry.start_timestamp <= now < entry.stop_timestamp:
                    status = "now"
                elif entry.start_timestamp > now:
                    status = "soon"
                else:
                    continue  # Vergangene Einträge überspringen

                if filt == "now" and status != "now":
                    continue
                if filt == "soon" and status != "soon":
                    continue

                haystack = (entry.title + " " + entry.description).lower()
                if not all(w in haystack for w in words):
                    continue

                results.append((stream, entry, status))
                break  # pro Sender nur den relevantesten Eintrag

        results.sort(key=lambda x: (0 if x[2] == "now" else 1, x[1].start_timestamp, x[0].name))

        lay = self.epg_search_results_layout
        while lay.count():
            w = lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        if results:
            for stream, entry, status in results[:300]:
                lay.addWidget(self._epg_search_make_row(stream, entry, status))
        else:
            lbl = QLabel("Keine Treffer")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #444; font-size: 13px; padding: 40px;")
            lay.addWidget(lbl)

        lay.addStretch()

    def _epg_search_make_row(self, stream, entry, status: str) -> QWidget:
        from ui_builder import _pi
        row = QWidget()
        row.setObjectName("epgSearchRow")
        row.setStyleSheet("""
            #epgSearchRow {
                background: rgba(255,255,255,3);
                border-bottom: 1px solid rgba(255,255,255,6);
            }
            #epgSearchRow:hover { background: rgba(255,255,255,6); }
        """)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 8, 10, 8)
        lay.setSpacing(8)

        # Badge
        badge = QLabel()
        badge.setFixedWidth(42)
        badge.setAlignment(Qt.AlignCenter)
        if status == "now":
            badge.setText("JETZT")
            badge.setStyleSheet(
                "background: #27ae60; color: #fff; font-size: 9px; font-weight: bold; "
                "border-radius: 3px; padding: 2px 4px;"
            )
        else:
            start_dt = datetime.fromtimestamp(entry.start_timestamp)
            today = datetime.now().date()
            if start_dt.date() == today:
                t = start_dt.strftime("%H:%M")
            else:
                t = start_dt.strftime("%a\n%H:%M")
            badge.setText(t)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet("color: #0078d4; font-size: 11px; font-weight: bold;")
        lay.addWidget(badge, alignment=Qt.AlignVCenter)

        # Text (Titel + Sender · Zeit) — in QWidget damit stretch korrekt begrenzt
        text_widget = QWidget()
        text_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_col = QVBoxLayout(text_widget)
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        title_lbl = QLabel(entry.title)
        title_lbl.setStyleSheet("color: #ddd; font-size: 13px;")
        title_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text_col.addWidget(title_lbl)

        s = datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M")
        e = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
        meta_lbl = QLabel(f"{stream.name}  ·  {s}–{e}")
        meta_lbl.setStyleSheet("color: #555; font-size: 11px;")
        meta_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text_col.addWidget(meta_lbl)

        lay.addWidget(text_widget, stretch=1)

        # Aktion: Jetzt=Abspielen, Bald=Aufnahme planen
        btn = QPushButton()
        btn.setFixedSize(28, 28)
        btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #2a2a3a; border-radius: 5px; }
            QPushButton:hover { background: #0078d4; border-color: #0078d4; }
        """)
        if status == "now":
            btn.setIcon(_pi("play.svg", 13))
            btn.setIconSize(QSize(13, 13))
            btn.setToolTip("Abspielen")
            btn.clicked.connect(
                lambda checked=False, s=stream, e=entry: self._epg_search_play(s, e)
            )
        else:
            btn.setIcon(_pi("record.svg", 13))
            btn.setIconSize(QSize(13, 13))
            btn.setToolTip("Aufnahme planen")
            btn.clicked.connect(
                lambda checked=False, s=stream, e=entry: self._epg_search_schedule(s, e)
            )
        lay.addWidget(btn, alignment=Qt.AlignVCenter)

        return row

    def _epg_search_play(self, stream, entry):
        if not self.api:
            return
        url = self.api.creds.stream_url(stream.stream_id)
        self._play_stream(url, stream.name, "live", stream.stream_id, icon=stream.stream_icon)

    def _epg_search_schedule(self, stream, entry):
        if not self.api:
            return
        self._open_schedule_dialog(
            channel_name=stream.name,
            stream_url=self.api.creds.stream_url(stream.stream_id),
            start_ts=entry.start_timestamp,
            end_ts=entry.stop_timestamp,
            epg_title=entry.title,
            fixed_time=True,
        )

    def _epg_search_set_status(self, msg: str):
        if hasattr(self, 'epg_search_status_lbl'):
            self.epg_search_status_lbl.setText(msg)
