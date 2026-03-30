"""
Live-Events: Erkennung und Aufbereitung von Sport-Events aus dem EPG.
"""
import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout, QLabel

from sports_data import SportsDataClient, RssItem, TeamInfo
from xtream_api import LiveStream, EpgEntry

# ── Konstanten ────────────────────────────────────────────────────────────────

SPORT_CHANNEL_KEYWORDS = [
    "sport", "football", "soccer", "fussball", "calcio",
    "basketball", "tennis", "formula", "formel", "moto",
    "golf", "rugby", "hockey", "boxing", "fight",
    "eurosport", "arena", "esport", "sportl", "sports",
    "bein", "eleven", "dazn", "sky sport",
]

QUALITY_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"\b(4k|uhd)\b", re.I), 4),
    (re.compile(r"\b(fhd|1080)\b", re.I), 3),
    (re.compile(r"\bhd\b", re.I), 2),
    (re.compile(r"\bsd\b", re.I), 1),
]

# Regex für "Team A vs Team B" Muster
DUEL_PATTERNS = [
    re.compile(r"^(.+?)\s+(?:vs\.?|gegen|contro|contre|v\.?)\s+(.+?)(?:\s*[-–|].*)?$", re.I),
    re.compile(r"^(.+?)\s*[-–]\s*(.+?)(?:\s*\|.*)?$"),
]

# Keywords die auf eine Sportart hindeuten (im EPG-Titel oder Kanalnamen)
SPORT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "football":        ["bundesliga", "champions league", "uefa", "premier league",
                        "la liga", "serie a", "ligue 1", "dfb", "wm", "em",
                        "fussball", "football", "soccer", "calcio"],
    "formula1":        ["formel 1", "formula 1", "formula one", "f1", "grand prix", "gp"],
    "tennis":          ["tennis", "wimbledon", "roland garros", "us open", "atp", "wta"],
    "basketball":      ["basketball", "nba", "bbl", "euroleague"],
    "motorsport":      ["motogp", "moto gp", "superbike", "dtm", "nascar", "indycar"],
    "golf":            ["golf", "pga", "masters", "open championship"],
    "rugby":           ["rugby", "six nations"],
    "hockey":          ["hockey", "eishockey", "nhl", "del "],
    "boxing":          ["boxing", "boxen", "ufc", "mma", "fight night"],
}

# Bracket-Prefix Pattern: [DE], [UK], | HD |, etc.
BRACKET_PREFIX_RE = re.compile(r"^\s*[\[\(|][^\]\)\|]{1,6}[\]\)\|]\s*[-–]?\s*")

# Wie lange Events gecacht werden
EVENTS_CACHE_TTL = 300       # 5 Minuten
THESPORTSDB_CACHE_TTL = 3600  # 1 Stunde
RSS_CACHE_TTL = 600           # 10 Minuten

EPG_LOOKAHEAD_HOURS = 48      # Wie weit in die Zukunft schauen
XMLTV_CACHE_TTL = 1800        # 30 Minuten Disk-Cache für XMLTV

# ── Datenklassen ──────────────────────────────────────────────────────────────

@dataclass
class SportStream:
    stream: LiveStream
    quality: int        # 4=4K, 3=FHD, 2=HD, 1=SD, 0=unbekannt
    clean_name: str     # Kanalname ohne Bracket-Prefix


@dataclass
class SportEvent:
    event_id: str
    title: str
    sport_type: str             # "football", "formula1", "tennis", ...
    start_timestamp: int
    stop_timestamp: int
    is_duel: bool
    team_a: str = ""
    team_b: str = ""
    venue: str = ""
    referee: str = ""
    streams: list[SportStream] = field(default_factory=list)
    news: list[RssItem] = field(default_factory=list)

    @property
    def is_live(self) -> bool:
        now = time.time()
        return self.start_timestamp <= now <= self.stop_timestamp

    @property
    def starts_in_seconds(self) -> float:
        return self.start_timestamp - time.time()

    @property
    def best_stream(self) -> Optional[SportStream]:
        return max(self.streams, key=lambda s: s.quality) if self.streams else None


# ── Mixin ─────────────────────────────────────────────────────────────────────

class LiveEventsMixin:

    def _init_live_events_state(self):
        self._live_events_cache: list[SportEvent] = []
        self._live_events_cache_ts: float = 0.0
        self._live_events_time_filter: str = "now"
        self._live_events_sport_filter: Optional[str] = None
        self._live_events_loading: bool = False
        self._live_events_load_gen: int = 0
        self._sports_client = SportsDataClient()

    # ── Laden & Aufbereiten ───────────────────────────────────────────────────

    async def _load_live_events(self):
        """Haupteinstieg: lädt Events, reichert an, rendert."""
        print(f"[LiveEvents] _load_live_events gestartet, api={self.api is not None}")
        if self._live_events_loading:
            print("[LiveEvents] bereits am laden, abbruch")
            return

        # Cache noch gültig?
        if self._live_events_cache and (time.monotonic() - self._live_events_cache_ts) < EVENTS_CACHE_TTL:
            self._render_events_page()
            return

        self._live_events_loading = True
        self._live_events_load_gen += 1
        gen = self._live_events_load_gen

        self._show_live_events_loading(True, "Senderliste wird geladen…")
        try:
            channels_epg = await self._collect_sport_channels(gen)
            if gen != self._live_events_load_gen:
                return

            self._show_live_events_loading(True, f"Events werden erkannt ({len(channels_epg)} Kanäle)…")
            loop = asyncio.get_running_loop()
            events = await loop.run_in_executor(None, self._detect_and_group_events, channels_epg)
            if gen != self._live_events_load_gen:
                return

            if events:
                self._show_live_events_loading(True, f"{len(events)} Events gefunden, Daten werden geladen…")
                await self._enrich_events(events, gen)
                if gen != self._live_events_load_gen:
                    return

            self._live_events_cache = events
            self._live_events_cache_ts = time.monotonic()
            self._render_events_page()
        finally:
            self._live_events_loading = False
            self._show_live_events_loading(False)

    async def _collect_sport_channels(self, gen: int) -> list[tuple[SportStream, list[EpgEntry]]]:
        """Lädt XMLTV-Feed (ein Request), filtert Sport-Kanäle und gibt EPG-Einträge zurück."""
        if not self.api:
            return []

        # Erst Senderliste laden um stream_id → LiveStream Mapping zu bauen
        print("[LiveEvents] lade Streams…")
        all_streams = await self.api.get_live_streams()
        print(f"[LiveEvents] {len(all_streams)} Streams geladen")
        stream_map: dict[str, LiveStream] = {}
        for s in all_streams:
            if s.epg_channel_id:
                stream_map[s.epg_channel_id] = s
            stream_map[str(s.stream_id)] = s

        print("[LiveEvents] lade XMLTV…")
        self._show_live_events_loading(True, "EPG-Feed wird geladen…")
        try:
            xml_path = await self._fetch_xmltv_cached()
        except Exception as e:
            print(f"[LiveEvents] XMLTV Fehler: {e}")
            return []
        print(f"[LiveEvents] XMLTV unter {xml_path}, parse via iterparse…")
        self._show_live_events_loading(True, "EPG-Feed wird verarbeitet…")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._parse_xmltv, xml_path, stream_map)
        return result

    def _parse_xmltv(
        self, xml_path: str, stream_map: dict[str, LiveStream]
    ) -> list[tuple[SportStream, list[EpgEntry]]]:
        """Parst XMLTV via iterparse (streaming, kein DOM) und gibt Sport-Kanäle zurück."""
        import xml.etree.ElementTree as ET

        now = time.time()
        lookahead = now + EPG_LOOKAHEAD_HOURS * 3600

        channel_names: dict[str, str] = {}
        channel_epg: dict[str, list[EpgEntry]] = {}

        try:
            for event, elem in ET.iterparse(xml_path, events=("end",)):
                if elem.tag == "channel":
                    ch_id = elem.get("id", "")
                    name_el = elem.find("display-name")
                    if name_el is not None and name_el.text:
                        channel_names[ch_id] = name_el.text.strip()
                    elem.clear()  # Speicher freigeben

                elif elem.tag == "programme":
                    ch_id = elem.get("channel", "")
                    ch_name = channel_names.get(ch_id, ch_id)

                    if not self._is_sport_channel(ch_name):
                        elem.clear()
                        continue

                    start_ts = _parse_xmltv_time(elem.get("start", ""))
                    stop_ts = _parse_xmltv_time(elem.get("stop", ""))

                    if stop_ts < now or start_ts > lookahead:
                        elem.clear()
                        continue

                    title_el = elem.find("title")
                    desc_el = elem.find("desc")
                    title = title_el.text.strip() if title_el is not None and title_el.text else ""
                    desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

                    if title:
                        entry = EpgEntry(
                            title=title,
                            start_timestamp=int(start_ts),
                            stop_timestamp=int(stop_ts),
                            description=desc,
                        )
                        channel_epg.setdefault(ch_id, []).append(entry)

                    elem.clear()

        except ET.ParseError as e:
            print(f"[LiveEvents] XMLTV Parse-Fehler: {e}")
            return []

        # Name → Stream Lookup-Dict (normalisiert)
        name_stream_map: dict[str, LiveStream] = {
            _normalize_channel_name(s.name): s
            for s in stream_map.values()
            if isinstance(s, LiveStream)
        }

        # channel-id → SportStream + EPG zusammenführen
        result: list[tuple[SportStream, list[EpgEntry]]] = []
        for ch_id, entries in channel_epg.items():
            ch_name = channel_names.get(ch_id, "")
            stream = stream_map.get(ch_id)
            if stream is None:
                stream = name_stream_map.get(_normalize_channel_name(ch_name))
            if stream is None:
                continue

            ss = SportStream(
                stream=stream,
                quality=self._quality_rank(stream.name),
                clean_name=self._strip_bracket_prefix(stream.name),
            )
            result.append((ss, entries))

        print(f"[LiveEvents] {len(result)} Sport-Kanäle mit EPG gefunden")
        return result

    def _detect_and_group_events(
        self, channels_epg: list[tuple[SportStream, list[EpgEntry]]]
    ) -> list[SportEvent]:
        """Erkennt Events aus EPG-Titeln und gruppiert gleiche Events über Kanäle.
        O(n) via dict-Grouping: Schlüssel = normalisierter Titel + gerundeter Startzeitpunkt.
        """
        # Schlüssel: (norm_title, start_bucket) → list[(stream, entry)]
        # start_bucket = Startzeitpunkt auf 30 Minuten gerundet
        groups: dict[tuple[str, int], list[tuple[SportStream, EpgEntry]]] = {}

        for ss, entries in channels_epg:
            for entry in entries:
                norm = _normalize_title(entry.title)
                bucket = round(entry.start_timestamp / 1800) * 1800  # 30-Min-Bucket
                key = (norm, bucket)
                groups.setdefault(key, []).append((ss, entry))

        events: list[SportEvent] = []
        for group in groups:
            # Repräsentativen Entry nehmen (bester Qualitäts-Stream)
            group.sort(key=lambda x: x[0].quality, reverse=True)
            rep_ss, rep_entry = group[0]

            title = rep_entry.title
            sport_type = self._detect_sport_type(title, rep_ss.clean_name)
            teams = _parse_teams(title)
            is_duel = teams is not None

            # Streams deduplizieren: pro Qualitätsstufe nur einen
            seen_quality: set[int] = set()
            streams: list[SportStream] = []
            for ss, _ in sorted(group, key=lambda x: x[0].quality, reverse=True):
                if ss.quality not in seen_quality:
                    streams.append(ss)
                    seen_quality.add(ss.quality)

            event = SportEvent(
                event_id=f"{_normalize_title(title)}_{rep_entry.start_timestamp}",
                title=title,
                sport_type=sport_type,
                start_timestamp=rep_entry.start_timestamp,
                stop_timestamp=rep_entry.stop_timestamp,
                is_duel=is_duel,
                team_a=teams[0] if teams else "",
                team_b=teams[1] if teams else "",
                streams=streams,
            )
            events.append(event)

        # Chronologisch sortieren, laufende Events zuerst
        events.sort(key=lambda e: (not e.is_live, e.start_timestamp))
        return events

    async def _enrich_events(self, events: list[SportEvent], gen: int):
        """Reichert Events mit TheSportsDB + RSS an."""
        async def enrich_one(event: SportEvent):
            if gen != self._live_events_load_gen:
                return
            await asyncio.gather(
                self._enrich_sportsdb(event),
                self._enrich_news(event),
                return_exceptions=True,
            )

        await asyncio.gather(*[enrich_one(e) for e in events], return_exceptions=True)

    async def _enrich_sportsdb(self, event: SportEvent):
        if not event.is_duel or not event.team_a:
            return
        team_a_info, _ = await self._sports_client.get_event_details(
            event.team_a, event.team_b
        )
        if team_a_info:
            if team_a_info.venue:
                event.venue = team_a_info.venue
                if team_a_info.city:
                    event.venue += f" · {team_a_info.city}"

    async def _enrich_news(self, event: SportEvent):
        filter_terms = []
        if event.team_a:
            filter_terms.append(event.team_a)
        if event.team_b:
            filter_terms.append(event.team_b)
        if not filter_terms:
            filter_terms = [event.title]

        event.news = await self._sports_client.get_sport_news(
            event.sport_type,
            filter_terms=filter_terms,
            limit=5,
        )

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_events_page(self):
        """Filtert Events nach Zeit/Sportart und baut die Karten-Liste."""
        from event_card_widget import DuelCardWidget, EventCardWidget

        events = self._filter_events(self._live_events_cache)

        # Alten Inhalt leeren
        layout = self.live_events_cards_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not events:
            empty = QLabel("Keine Events gefunden")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #555; font-size: 16px; padding: 60px;")
            layout.addWidget(empty)
            return

        for event in events:
            if event.is_duel:
                card = DuelCardWidget(event, parent=self.live_events_cards_widget)
            else:
                card = EventCardWidget(event, parent=self.live_events_cards_widget)
            card.play_requested.connect(self._play_event_stream)
            layout.addWidget(card)

        layout.addStretch()

        # Sport-Filter-Pills aktualisieren
        self._update_sport_filter_pills(events)

    def _filter_events(self, events: list[SportEvent]) -> list[SportEvent]:
        """Filtert Events nach aktivem Zeit- und Sportart-Filter."""
        now = time.time()

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today_end = today_start + 86400

        tomorrow_start = today_end
        tomorrow_end = today_end + 86400

        # Wochenende: nächste Fr/Sa/So
        current_weekday = datetime.now().weekday()  # 0=Mo, 4=Fr, 5=Sa, 6=So
        days_to_friday = (4 - current_weekday) % 7
        if days_to_friday == 0 and datetime.now().hour >= 22:
            days_to_friday = 7
        friday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_to_friday)
        weekend_start = friday.timestamp()
        weekend_end = (friday + timedelta(days=3)).timestamp()

        filtered = []
        for e in events:
            if self._live_events_time_filter == "now":
                if not e.is_live:
                    continue
            elif self._live_events_time_filter == "today":
                if not (e.stop_timestamp >= now and e.start_timestamp < today_end):
                    continue
            elif self._live_events_time_filter == "tomorrow":
                if not (e.start_timestamp >= tomorrow_start and e.start_timestamp < tomorrow_end):
                    continue
            elif self._live_events_time_filter == "weekend":
                if not (e.start_timestamp >= weekend_start and e.start_timestamp < weekend_end):
                    continue

            if self._live_events_sport_filter:
                if e.sport_type != self._live_events_sport_filter:
                    continue

            filtered.append(e)
        return filtered

    def _update_sport_filter_pills(self, visible_events: list[SportEvent]):
        """Blendet Sport-Filter-Pills ein/aus je nach vorhandenen Events."""
        sport_types = {e.sport_type for e in self._live_events_cache}
        for sport, btn in self.live_events_sport_btns.items():
            btn.setVisible(sport == "all" or sport in sport_types)

    # ── UI-Callbacks ──────────────────────────────────────────────────────────

    def _on_live_events_time_filter(self, filter_name: str):
        self._live_events_time_filter = filter_name
        for name, btn in self.live_events_time_btns.items():
            btn.setChecked(name == filter_name)
        self._render_events_page()

    def _on_live_events_sport_filter(self, sport: Optional[str]):
        self._live_events_sport_filter = sport
        for name, btn in self.live_events_sport_btns.items():
            btn.setChecked(name == (sport or "all"))
        self._render_events_page()

    def _play_event_stream(self, stream: LiveStream):
        url = self.api.creds.stream_url(stream.stream_id)
        self._play_stream(url, stream.name, "live", stream.stream_id, icon=stream.stream_icon)

    def _show_live_events_loading(self, visible: bool, message: str = ""):
        if hasattr(self, "live_events_loading_widget"):
            self.live_events_loading_widget.setVisible(visible)
            if message and hasattr(self, "live_events_loading_label"):
                self.live_events_loading_label.setText(message)
        if hasattr(self, "live_events_scroll"):
            self.live_events_scroll.setVisible(not visible)
        if message:
            self.status_bar.showMessage(message)

    async def _fetch_xmltv_cached(self) -> str:
        """Lädt XMLTV direkt auf Disk (kein 80MB RAM-Buffer), gibt Dateipfad zurück."""
        cache_path = self._xmltv_cache_path()
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        # Cache prüfen
        if os.path.exists(cache_path):
            age = time.time() - os.path.getmtime(cache_path)
            if age < XMLTV_CACHE_TTL:
                print(f"[LiveEvents] XMLTV aus Cache ({int(age)}s alt)")
                self._show_live_events_loading(True, "EPG-Feed aus Cache…")
                return cache_path

        # Direkt auf Disk streamen — kein großer RAM-Buffer
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=120)
        downloaded = 0
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.api.creds.xmltv_url) as resp:
                resp.raise_for_status()
                with open(cache_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        mb = downloaded / 1024 / 1024
                        self._show_live_events_loading(True, f"EPG-Feed wird geladen… {mb:.1f} MB")

        print(f"[LiveEvents] XMLTV gecacht: {downloaded} Bytes → {cache_path}")
        return cache_path

    def _xmltv_cache_path(self) -> str:
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "iptv-app")
        server_hash = hashlib.md5(self.api.creds.server.encode()).hexdigest()[:8]
        return os.path.join(cache_dir, f"xmltv_{server_hash}.xml")

    def invalidate_live_events_cache(self):
        self._live_events_cache = []
        self._live_events_cache_ts = 0.0
        self._sports_client.clear_cache()

    # ── Hilfsfunktionen ───────────────────────────────────────────────────────

    def _is_sport_channel(self, name: str) -> bool:
        clean = self._strip_bracket_prefix(name).lower()
        return any(kw in clean for kw in SPORT_CHANNEL_KEYWORDS)

    def _strip_bracket_prefix(self, name: str) -> str:
        return BRACKET_PREFIX_RE.sub("", name).strip()

    def _quality_rank(self, name: str) -> int:
        name_lower = name.lower()
        for pattern, rank in QUALITY_PATTERNS:
            if pattern.search(name_lower):
                return rank
        return 0

    def _detect_sport_type(self, title: str, channel_name: str) -> str:
        combined = (title + " " + channel_name).lower()
        for sport_type, keywords in SPORT_TYPE_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                return sport_type
        return "sport"


# ── Modul-Hilfsfunktionen ─────────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Kleinschreibung, Sonderzeichen entfernen für Vergleiche."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _titles_match(a: str, b: str) -> bool:
    """Fuzzy-Vergleich zweier normalisierter Titel."""
    if a == b:
        return True
    ratio = SequenceMatcher(None, a, b).ratio()
    return ratio >= 0.85


def _times_overlap(a: EpgEntry, b: EpgEntry) -> bool:
    """Prüft ob zwei EPG-Einträge zeitlich überlappen (±30 Min Toleranz)."""
    tolerance = 1800
    return (a.start_timestamp - tolerance) <= b.stop_timestamp and \
           (b.start_timestamp - tolerance) <= a.stop_timestamp


def _normalize_channel_name(name: str) -> str:
    """Normalisiert Kanalnamen für Matching: Brackets, HD/SD, Leerzeichen entfernen."""
    n = BRACKET_PREFIX_RE.sub("", name)
    n = re.sub(r"\b(hd|sd|fhd|uhd|4k)\b", "", n, flags=re.I)
    n = re.sub(r"[^\w]", "", n).lower()
    return n


def _parse_xmltv_time(time_str: str) -> float:
    """Parst XMLTV-Zeitformat '20240101120000 +0200' zu Unix-Timestamp."""
    if not time_str:
        return 0.0
    try:
        # Format: YYYYMMDDHHmmss +HHMM  oder  YYYYMMDDHHmmss +HH:MM
        time_str = time_str.strip()
        if " " in time_str:
            dt_part, tz_part = time_str.split(" ", 1)
        else:
            dt_part, tz_part = time_str[:14], "+0000"
        from datetime import datetime, timezone, timedelta
        dt = datetime.strptime(dt_part, "%Y%m%d%H%M%S")
        tz_part = tz_part.replace(":", "")
        sign = 1 if tz_part[0] == "+" else -1
        tz_hours = int(tz_part[1:3])
        tz_mins = int(tz_part[3:5]) if len(tz_part) >= 5 else 0
        offset = timedelta(hours=tz_hours, minutes=tz_mins) * sign
        dt_utc = dt - offset
        return dt_utc.replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return 0.0


def _find_stream_by_name(name: str, stream_map: dict) -> Optional[LiveStream]:
    """Sucht einen Stream per Name-Matching als Fallback."""
    if not name:
        return None
    name_lower = name.lower()
    for stream in stream_map.values():
        if isinstance(stream, LiveStream) and stream.name.lower() == name_lower:
            return stream
    return None


def _parse_teams(title: str) -> Optional[tuple[str, str]]:
    """Extrahiert Team A und Team B aus einem Duell-Titel."""
    for pattern in DUEL_PATTERNS:
        m = pattern.match(title.strip())
        if m:
            a = m.group(1).strip()
            b = m.group(2).strip()
            # Mindestlänge: beide Teams müssen sinnvoll lang sein
            if len(a) >= 2 and len(b) >= 2:
                return a, b
    return None
