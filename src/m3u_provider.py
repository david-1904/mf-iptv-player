"""
M3U Playlist Provider
Parst M3U-Playlists per URL und stellt die gleiche Schnittstelle wie XtreamAPI bereit.
"""
import re
import asyncio
import aiohttp
import ssl
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from xtream_api import Category, LiveStream, VodStream, Series, EpgEntry

# Dateiendungen die als VOD erkannt werden
_VOD_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov"}

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


@dataclass
class _ParsedStream:
    name: str
    url: str
    group: str
    logo: str
    tvg_id: str
    is_vod: bool
    stream_id: int = 0


class M3uCredsBridge:
    """Bridge-Klasse mit gleichen URL-Methoden wie XtreamCredentials"""

    def __init__(self, name: str):
        self.name = name
        self._url_map: dict[int, str] = {}

    def stream_url(self, stream_id: int, extension: str = "m3u8") -> str:
        return self._url_map.get(stream_id, "")

    def vod_url(self, stream_id: int, extension: str = "mp4") -> str:
        return self._url_map.get(stream_id, "")

    def series_url(self, episode_id: str, extension: str = "mp4") -> str:
        return ""

    def catchup_url(self, stream_id: int, start, duration_min: int, extension: str = "m3u8") -> str:
        return ""


class M3uProvider:
    """M3U Provider mit gleicher Schnittstelle wie XtreamAPI"""

    def __init__(self, name: str, url: str):
        self._name = name
        self._url = url
        self.creds = M3uCredsBridge(name)

        self._live_streams: dict[str, list[LiveStream]] = {}  # cat_id -> streams
        self._vod_streams: dict[str, list[VodStream]] = {}
        self._live_categories: list[Category] = []
        self._vod_categories: list[Category] = []

    async def load(self):
        """M3U-Playlist herunterladen und parsen"""
        # SSL-Verifikation deaktivieren (viele IPTV-Server haben self-signed Certs)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        for attempt in range(3):
            try:
                connector = aiohttp.TCPConnector(ssl=ssl_ctx)
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=60),
                    connector=connector,
                    headers=_HTTP_HEADERS,
                ) as session:
                    async with session.get(self._url) as resp:
                        resp.raise_for_status()
                        text = await resp.text(errors="replace")
                break
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == 2:
                    raise
                await asyncio.sleep(1 + attempt)

        # BOM entfernen falls vorhanden
        if text.startswith("\ufeff"):
            text = text[1:]

        streams = self._parse_m3u(text)
        if not streams:
            raise ValueError("Keine Kanaele in der Playlist gefunden")
        self._build_data(streams)

    def _parse_m3u(self, text: str) -> list[_ParsedStream]:
        """Parst M3U-Text in eine Liste von Streams"""
        lines = text.splitlines()
        streams: list[_ParsedStream] = []
        current_info: dict | None = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                current_info = self._parse_extinf(line)
            elif not line.startswith("#") and current_info is not None:
                # Stream-URL
                url = line
                name = current_info.get("name", "Unbekannt")
                group = current_info.get("group", "Allgemein")
                logo = current_info.get("logo", "")
                tvg_id = current_info.get("tvg_id", "")

                # VOD-Erkennung anhand Dateiendung (URL-Pfad ohne Query/Pseudo-Parameter)
                url_path = urlparse(url.lower()).path.split("&")[0]
                is_vod = any(url_path.endswith(ext) for ext in _VOD_EXTENSIONS)

                streams.append(_ParsedStream(
                    name=name,
                    url=url,
                    group=group,
                    logo=logo,
                    tvg_id=tvg_id,
                    is_vod=is_vod,
                ))
                current_info = None

        return streams

    @staticmethod
    def _parse_extinf(line: str) -> dict:
        """Parst eine #EXTINF-Zeile"""
        info: dict = {}

        # tvg-id
        m = re.search(r'tvg-id="([^"]*)"', line)
        info["tvg_id"] = m.group(1) if m else ""

        # tvg-logo
        m = re.search(r'tvg-logo="([^"]*)"', line)
        info["logo"] = m.group(1) if m else ""

        # group-title
        m = re.search(r'group-title="([^"]*)"', line)
        info["group"] = m.group(1).strip() if m else "Allgemein"

        # Kanal-Name (nach dem letzten Komma)
        m = re.search(r',\s*(.+)$', line)
        info["name"] = m.group(1).strip() if m else "Unbekannt"

        return info

    def _build_data(self, streams: list[_ParsedStream]):
        """Baut Kategorien und Stream-Listen aus geparsten Daten"""
        self._live_streams.clear()
        self._vod_streams.clear()
        self._live_categories.clear()
        self._vod_categories.clear()
        self.creds._url_map.clear()

        live_groups: dict[str, list[_ParsedStream]] = {}
        vod_groups: dict[str, list[_ParsedStream]] = {}

        # Streams nach Gruppe und Typ sortieren
        stream_id = 1
        for s in streams:
            s.stream_id = stream_id
            self.creds._url_map[stream_id] = s.url
            stream_id += 1

            if s.is_vod:
                vod_groups.setdefault(s.group, []).append(s)
            else:
                live_groups.setdefault(s.group, []).append(s)

        # Live-Kategorien + Streams aufbauen
        for cat_idx, (group_name, group_streams) in enumerate(sorted(live_groups.items()), start=1):
            cat_id = str(cat_idx)
            self._live_categories.append(Category(
                category_id=cat_id,
                category_name=group_name,
            ))
            self._live_streams[cat_id] = [
                LiveStream(
                    stream_id=s.stream_id,
                    name=s.name,
                    stream_icon=s.logo,
                    epg_channel_id=s.tvg_id,
                    category_id=cat_id,
                )
                for s in group_streams
            ]

        # VOD-Kategorien + Streams aufbauen
        cat_offset = len(self._live_categories)
        for cat_idx, (group_name, group_streams) in enumerate(sorted(vod_groups.items()), start=cat_offset + 1):
            cat_id = str(cat_idx)
            self._vod_categories.append(Category(
                category_id=cat_id,
                category_name=group_name,
            ))
            self._vod_streams[cat_id] = [
                VodStream(
                    stream_id=s.stream_id,
                    name=s.name,
                    stream_icon=s.logo,
                    category_id=cat_id,
                    container_extension=urlparse(s.url).path.rsplit(".", 1)[-1] if "." in urlparse(s.url).path else "mp4",
                )
                for s in group_streams
            ]

    # --- Gleiche Schnittstelle wie XtreamAPI ---

    async def get_account_info(self) -> dict:
        return {
            "user_info": {"username": self._name, "status": "Active"},
            "server_info": {"url": self._url},
        }

    async def get_live_categories(self) -> list[Category]:
        return self._live_categories

    async def get_live_streams(self, category_id: Optional[str] = None) -> list[LiveStream]:
        if category_id:
            return self._live_streams.get(category_id, [])
        all_streams = []
        for streams in self._live_streams.values():
            all_streams.extend(streams)
        return all_streams

    async def get_vod_categories(self) -> list[Category]:
        return self._vod_categories

    async def get_vod_streams(self, category_id: Optional[str] = None) -> list[VodStream]:
        if category_id:
            return self._vod_streams.get(category_id, [])
        all_streams = []
        for streams in self._vod_streams.values():
            all_streams.extend(streams)
        return all_streams

    async def get_series_categories(self) -> list[Category]:
        return []

    async def get_series(self, category_id: Optional[str] = None) -> list[Series]:
        return []

    async def get_short_epg(self, stream_id: int, limit: int = 2) -> list[EpgEntry]:
        return []

    async def get_full_epg(self, stream_id: int) -> list[EpgEntry]:
        return []

    async def get_vod_info(self, vod_id: int) -> dict:
        return {}

    async def get_series_info_parsed(self, series_id: int) -> dict:
        return {"info": {}, "seasons": [], "episodes": {}}
