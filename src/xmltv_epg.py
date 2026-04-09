"""
XMLTV EPG-Parser — lädt und parst externen EPG-Feed (XML oder .gz)
"""
import gzip
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import aiohttp

from xtream_api import EpgEntry


_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=60)
# Einträge die mehr als 3 Stunden in der Vergangenheit enden werden verworfen
_PAST_CUTOFF_SECS = 3 * 3600


def _parse_xmltv_ts(ts_str: str) -> int:
    """Parst XMLTV-Zeitstempel '20240101120000 +0000' → Unix-Timestamp (int)."""
    ts_str = ts_str.strip()
    try:
        if " " in ts_str:
            dt = datetime.strptime(ts_str, "%Y%m%d%H%M%S %z")
        else:
            dt = datetime.strptime(ts_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return 0


class XmltvEpg:
    """Lädt und parst einen XMLTV-EPG-Feed. Lookup nach channel-id (tvg-id)."""

    def __init__(self):
        self._data: dict[str, list[EpgEntry]] = {}
        self.loaded: bool = False
        self.channel_count: int = 0

    async def fetch(self, url: str) -> None:
        """Lädt den XMLTV-Feed von url und parst ihn. Wirft bei Fehler eine Exception."""
        self.loaded = False
        self._data = {}

        async with aiohttp.ClientSession(timeout=_FETCH_TIMEOUT) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                raw = await resp.read()

        # Gzip automatisch erkennen (URL-Endung oder Magic Bytes)
        if url.rstrip("?").endswith(".gz") or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)

        self._parse_xml(raw)
        self.channel_count = len(self._data)
        self.loaded = True

    def _parse_xml(self, data: bytes) -> None:
        root = ET.fromstring(data)
        cutoff = time.time() - _PAST_CUTOFF_SECS

        for programme in root.iter("programme"):
            ch_id = programme.get("channel", "")
            start = _parse_xmltv_ts(programme.get("start", ""))
            stop = _parse_xmltv_ts(programme.get("stop", ""))
            if not ch_id or not start or not stop:
                continue
            if stop < cutoff:
                continue

            title_el = programme.find("title")
            title = (title_el.text or "") if title_el is not None else ""
            desc_el = programme.find("desc")
            desc = (desc_el.text or "") if desc_el is not None else ""

            self._data.setdefault(ch_id, []).append(
                EpgEntry(title=title, start_timestamp=start,
                         stop_timestamp=stop, description=desc)
            )

        for entries in self._data.values():
            entries.sort(key=lambda e: e.start_timestamp)

    def get_short_epg(self, channel_id: str, limit: int = 8) -> list[EpgEntry]:
        """Gibt bis zu `limit` Einträge ab dem aktuell laufenden zurück."""
        entries = self._data.get(channel_id, [])
        if not entries:
            return []
        now = time.time()
        # Suche den ersten Eintrag dessen stop noch in der Zukunft liegt
        start_idx = 0
        for i, e in enumerate(entries):
            if e.stop_timestamp > now:
                start_idx = i
                break
        return entries[start_idx: start_idx + limit]

    def get_full_epg(self, channel_id: str) -> list[EpgEntry]:
        """Gibt alle gespeicherten Einträge für diesen Kanal zurück."""
        return list(self._data.get(channel_id, []))
