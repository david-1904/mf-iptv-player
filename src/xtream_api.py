"""
Xtream Codes API Client
Basiert auf der myboard API-Implementierung
"""
import asyncio
import aiohttp
import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


def _decode_base64(value: str) -> str:
    """Dekodiert Base64-kodierten Text (typisch bei Xtream Codes EPG)"""
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except Exception:
        return value


@dataclass
class XtreamCredentials:
    server: str
    username: str
    password: str
    name: str = ""

    @property
    def base_url(self) -> str:
        server = self.server.rstrip('/')
        return f"{server}/player_api.php"

    def stream_url(self, stream_id: int, extension: str = "m3u8") -> str:
        server = self.server.rstrip('/')
        return f"{server}/live/{self.username}/{self.password}/{stream_id}.{extension}"

    def vod_url(self, stream_id: int, extension: str) -> str:
        server = self.server.rstrip('/')
        return f"{server}/movie/{self.username}/{self.password}/{stream_id}.{extension}"

    def series_url(self, episode_id: str, extension: str) -> str:
        server = self.server.rstrip('/')
        return f"{server}/series/{self.username}/{self.password}/{episode_id}.{extension}"

    def catchup_url(self, stream_id: int, start: datetime, duration_min: int, extension: str = "m3u8") -> str:
        server = self.server.rstrip('/')
        start_str = start.strftime("%Y-%m-%d:%H-%M")
        return f"{server}/timeshift/{self.username}/{self.password}/{duration_min}/{start_str}/{stream_id}.{extension}"


@dataclass
class Category:
    category_id: str
    category_name: str
    parent_id: int = 0


@dataclass
class LiveStream:
    stream_id: int
    name: str
    stream_icon: str = ""
    epg_channel_id: str = ""
    category_id: str = ""
    tv_archive: bool = False
    tv_archive_duration: int = 0


@dataclass
class VodStream:
    stream_id: int
    name: str
    stream_icon: str = ""
    rating: str = ""
    rating_5based: float = 0.0
    added: str = ""
    category_id: str = ""
    container_extension: str = "mp4"


@dataclass
class Series:
    series_id: int
    name: str
    cover: str = ""
    plot: str = ""
    rating: str = ""
    rating_5based: float = 0.0
    added: str = ""
    category_id: str = ""


@dataclass
class Episode:
    id: str
    episode_num: int
    title: str
    container_extension: str = "mp4"
    duration: str = ""
    season: int = 1
    plot: str = ""


@dataclass
class EpgEntry:
    title: str
    start_timestamp: int
    stop_timestamp: int
    description: str = ""


class XtreamAPI:
    def __init__(self, credentials: XtreamCredentials):
        self.creds = credentials

    def _params(self, **extra) -> dict:
        params = {
            "username": self.creds.username,
            "password": self.creds.password,
        }
        params.update(extra)
        return params

    async def _get(self, action: str, retries: int = 3, **params) -> dict | list:
        timeout = aiohttp.ClientTimeout(total=15)
        all_params = self._params(action=action, **params)
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(self.creds.base_url, params=all_params) as resp:
                        resp.raise_for_status()
                        return await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(1 + attempt)

    async def get_account_info(self) -> dict:
        """Holt Account-Informationen"""
        return await self._get("")

    async def get_live_categories(self) -> list[Category]:
        """Holt alle Live-TV Kategorien"""
        data = await self._get("get_live_categories")
        return [
            Category(
                category_id=str(c.get("category_id", "")),
                category_name=c.get("category_name", ""),
                parent_id=c.get("parent_id", 0)
            )
            for c in (data or []) if isinstance(c, dict)
        ]

    async def get_live_streams(self, category_id: Optional[str] = None) -> list[LiveStream]:
        """Holt Live-Streams einer Kategorie"""
        params = {}
        if category_id:
            params["category_id"] = category_id
        data = await self._get("get_live_streams", **params)
        return [
            LiveStream(
                stream_id=s.get("stream_id", 0),
                name=s.get("name", ""),
                stream_icon=s.get("stream_icon", ""),
                epg_channel_id=s.get("epg_channel_id", ""),
                category_id=str(s.get("category_id", "")),
                tv_archive=bool(s.get("tv_archive", 0)),
                tv_archive_duration=int(s.get("tv_archive_duration", 0) or 0),
            )
            for s in (data or []) if isinstance(s, dict)
        ]

    async def get_vod_categories(self) -> list[Category]:
        """Holt alle VOD Kategorien"""
        data = await self._get("get_vod_categories")
        return [
            Category(
                category_id=str(c.get("category_id", "")),
                category_name=c.get("category_name", ""),
                parent_id=c.get("parent_id", 0)
            )
            for c in (data or []) if isinstance(c, dict)
        ]

    async def get_vod_streams(self, category_id: Optional[str] = None) -> list[VodStream]:
        """Holt VOD-Streams einer Kategorie"""
        params = {}
        if category_id:
            params["category_id"] = category_id
        data = await self._get("get_vod_streams", **params)
        return [
            VodStream(
                stream_id=s.get("stream_id", 0),
                name=s.get("name", ""),
                stream_icon=s.get("stream_icon", ""),
                rating=str(s.get("rating", "")),
                rating_5based=float(s.get("rating_5based", 0) or 0),
                added=str(s.get("added", "")),
                category_id=str(s.get("category_id", "")),
                container_extension=s.get("container_extension", "mp4")
            )
            for s in (data or []) if isinstance(s, dict)
        ]

    async def get_series_categories(self) -> list[Category]:
        """Holt alle Serien-Kategorien"""
        data = await self._get("get_series_categories")
        return [
            Category(
                category_id=str(c.get("category_id", "")),
                category_name=c.get("category_name", ""),
                parent_id=c.get("parent_id", 0)
            )
            for c in (data or []) if isinstance(c, dict)
        ]

    async def get_series(self, category_id: Optional[str] = None) -> list[Series]:
        """Holt Serien einer Kategorie"""
        params = {}
        if category_id:
            params["category_id"] = category_id
        data = await self._get("get_series", **params)
        return [
            Series(
                series_id=s.get("series_id", 0),
                name=s.get("name", ""),
                cover=s.get("cover", ""),
                plot=s.get("plot", ""),
                rating=str(s.get("rating", "")),
                rating_5based=float(s.get("rating_5based", 0) or 0),
                added=str(s.get("added", "")),
                category_id=str(s.get("category_id", ""))
            )
            for s in (data or []) if isinstance(s, dict)
        ]

    async def get_vod_info(self, vod_id: int) -> dict:
        """Holt detaillierte VOD-Informationen (Plot, Cast, Director etc.)"""
        return await self._get("get_vod_info", vod_id=vod_id)

    async def get_series_info(self, series_id: int) -> dict:
        """Holt detaillierte Serien-Informationen mit Episoden"""
        return await self._get("get_series_info", series_id=series_id)

    async def get_series_info_parsed(self, series_id: int) -> dict:
        """Holt und parst Serien-Informationen mit Staffeln und Episoden"""
        raw = await self.get_series_info(series_id)
        info = raw.get("info", {}) or {}
        episodes_raw = raw.get("episodes", {}) or {}

        seasons = sorted(int(s) for s in episodes_raw.keys())
        episodes: dict[int, list[Episode]] = {}

        for season_str, ep_list in episodes_raw.items():
            season_num = int(season_str)
            parsed = []
            for ep in (ep_list or []):
                parsed.append(Episode(
                    id=str(ep.get("id", "")),
                    episode_num=int(ep.get("episode_num", 0)),
                    title=ep.get("title", ""),
                    container_extension=ep.get("container_extension", "mp4"),
                    duration=ep.get("info", {}).get("duration", "") if isinstance(ep.get("info"), dict) else "",
                    season=season_num,
                    plot=ep.get("info", {}).get("plot", "") if isinstance(ep.get("info"), dict) else "",
                ))
            parsed.sort(key=lambda e: e.episode_num)
            episodes[season_num] = parsed

        return {"info": info, "seasons": seasons, "episodes": episodes}

    async def get_short_epg(self, stream_id: int, limit: int = 2) -> list[EpgEntry]:
        """Holt EPG-Daten fuer einen Stream (aktuell + kommend)"""
        data = await self._get("get_short_epg", stream_id=stream_id, limit=limit)
        listings = data.get("epg_listings", []) if isinstance(data, dict) else []
        return [
            EpgEntry(
                title=_decode_base64(e.get("title", "")),
                start_timestamp=int(e.get("start_timestamp", 0)),
                stop_timestamp=int(e.get("stop_timestamp", 0)),
                description=_decode_base64(e.get("description", ""))
            )
            for e in listings
        ]

    async def get_full_epg(self, stream_id: int) -> list[EpgEntry]:
        """Holt vollstaendige EPG-Daten inkl. vergangener Sendungen"""
        data = await self._get("get_simple_data_table", stream_id=stream_id)
        listings = data.get("epg_listings", []) if isinstance(data, dict) else []
        return [
            EpgEntry(
                title=_decode_base64(e.get("title", "")),
                start_timestamp=int(e.get("start_timestamp", 0)),
                stop_timestamp=int(e.get("stop_timestamp", 0)),
                description=_decode_base64(e.get("description", ""))
            )
            for e in listings
        ]
