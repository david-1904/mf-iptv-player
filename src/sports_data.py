"""
Sports data: TheSportsDB (venue/referee) + RSS news feeds per sport type.
All requests are async via aiohttp. Results are TTL-cached in memory.
"""
import asyncio
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

# ── TheSportsDB ───────────────────────────────────────────────────────────────
THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

# ── RSS feeds per sport type ──────────────────────────────────────────────────
RSS_FEEDS: dict[str, list[str]] = {
    "football": [
        "https://www.kicker.de/news/fussball/bundesliga/rss.xml",
        "https://www.sport1.de/news/fussball.rss",
    ],
    "champions_league": [
        "https://www.kicker.de/news/fussball/chleague/rss.xml",
    ],
    "formula1": [
        "https://www.motorsport-total.com/rss/f1.xml",
        "https://www.auto-motor-und-sport.de/rss/formel-1.xml",
    ],
    "tennis": [
        "https://www.tennisnet.com/rss",
    ],
    "basketball": [
        "https://www.sport1.de/news/basketball.rss",
    ],
    "motorsport": [
        "https://www.motorsport-total.com/rss/news.xml",
    ],
    "sport": [
        "https://www.sport1.de/news.rss",
    ],
}

# Atom namespace
_ATOM_NS = "http://www.w3.org/2005/Atom"

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class RssItem:
    title: str
    url: str
    published: float = 0.0   # Unix timestamp
    summary: str = ""


@dataclass
class TeamInfo:
    name: str
    venue: str = ""
    city: str = ""
    country: str = ""
    badge_url: str = ""


# ── Simple TTL cache ──────────────────────────────────────────────────────────

class _TtlCache:
    def __init__(self):
        self._data: dict[str, tuple[float, object]] = {}

    def get(self, key: str, ttl: float) -> Optional[object]:
        entry = self._data.get(key)
        if entry and (time.monotonic() - entry[0]) < ttl:
            return entry[1]
        return None

    def set(self, key: str, value: object):
        self._data[key] = (time.monotonic(), value)


# ── Client ────────────────────────────────────────────────────────────────────

class SportsDataClient:

    def __init__(self):
        self._cache = _TtlCache()
        self._thesportsdb_sem = asyncio.Semaphore(3)
        self._rss_sem = asyncio.Semaphore(5)

    # ── TheSportsDB ───────────────────────────────────────────────────────────

    async def get_team_info(self, team_name: str) -> Optional[TeamInfo]:
        """Look up team venue and info from TheSportsDB (free, no key needed)."""
        key = f"team:{team_name.lower()}"
        cached = self._cache.get(key, ttl=3600)
        if cached is not None:
            return cached

        async with self._thesportsdb_sem:
            try:
                url = f"{THESPORTSDB_BASE}/searchteams.php"
                timeout = aiohttp.ClientTimeout(total=8)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, params={"t": team_name}) as resp:
                        if resp.status != 200:
                            return None
                        data = await resp.json()

                teams = data.get("teams") if data else None
                if not teams:
                    self._cache.set(key, None)
                    return None

                t = teams[0]
                info = TeamInfo(
                    name=t.get("strTeam", team_name),
                    venue=t.get("strStadium", ""),
                    city=t.get("strStadiumLocation", ""),
                    country=t.get("strCountry", ""),
                    badge_url=t.get("strTeamBadge", "") or "",
                )
                self._cache.set(key, info)
                return info

            except Exception:
                return None

    async def get_event_details(
        self, team_a: str, team_b: str
    ) -> tuple[Optional[TeamInfo], Optional[TeamInfo]]:
        """Fetch both teams concurrently."""
        results = await asyncio.gather(
            self.get_team_info(team_a),
            self.get_team_info(team_b),
            return_exceptions=True,
        )
        a = results[0] if isinstance(results[0], TeamInfo) else None
        b = results[1] if isinstance(results[1], TeamInfo) else None
        return a, b

    # ── RSS ───────────────────────────────────────────────────────────────────

    async def get_sport_news(
        self, sport_type: str, filter_terms: list[str] | None = None, limit: int = 5
    ) -> list[RssItem]:
        """
        Fetch RSS news for a sport type. Optionally filter by team/event names.
        Returns up to `limit` items, sorted by recency.
        """
        feeds = RSS_FEEDS.get(sport_type) or RSS_FEEDS.get("sport", [])
        if not feeds:
            return []

        key = f"rss:{sport_type}:{','.join(filter_terms or [])}"
        cached = self._cache.get(key, ttl=600)
        if cached is not None:
            return cached

        tasks = [self._fetch_rss(url) for url in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: list[RssItem] = []
        cutoff = time.time() - 48 * 3600  # only last 48h
        for result in results:
            if isinstance(result, list):
                all_items.extend(item for item in result if item.published >= cutoff)

        if filter_terms:
            terms_lower = [t.lower() for t in filter_terms if t]
            filtered = [
                item for item in all_items
                if any(term in item.title.lower() for term in terms_lower)
            ]
            # fall back to unfiltered if no matches
            all_items = filtered if filtered else all_items

        all_items.sort(key=lambda i: i.published, reverse=True)
        result_items = all_items[:limit]
        self._cache.set(key, result_items)
        return result_items

    async def _fetch_rss(self, url: str) -> list[RssItem]:
        key = f"feed:{url}"
        cached = self._cache.get(key, ttl=300)
        if cached is not None:
            return cached

        async with self._rss_sem:
            try:
                timeout = aiohttp.ClientTimeout(total=8)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers={"Accept": "application/rss+xml, application/xml, text/xml"}) as resp:
                        if resp.status != 200:
                            return []
                        text = await resp.text(errors="replace")

                items = self._parse_rss(text)
                self._cache.set(key, items)
                return items

            except Exception:
                return []

    def _parse_rss(self, xml_text: str) -> list[RssItem]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        items: list[RssItem] = []

        # RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")
            summary = item.findtext("description", "").strip()
            # strip HTML tags from summary
            summary = ET.fromstring(f"<x>{summary}</x>").text or summary if summary else ""
            items.append(RssItem(
                title=title,
                url=link,
                published=_parse_rfc822(pub_date),
                summary=summary[:200],
            ))

        # Atom
        if not items:
            ns = {"a": _ATOM_NS}
            for entry in root.findall("a:entry", ns):
                title_el = entry.find("a:title", ns)
                link_el = entry.find("a:link", ns)
                updated_el = entry.find("a:updated", ns)
                summary_el = entry.find("a:summary", ns)
                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link = link_el.get("href", "") if link_el is not None else ""
                pub = updated_el.text if updated_el is not None else ""
                summary = summary_el.text or "" if summary_el is not None else ""
                items.append(RssItem(
                    title=title,
                    url=link,
                    published=_parse_iso8601(pub),
                    summary=summary[:200],
                ))

        return items

    def clear_cache(self):
        self._cache._data.clear()


# ── Date parsing helpers ──────────────────────────────────────────────────────

def _parse_rfc822(date_str: str) -> float:
    """Parse RFC 822 date (RSS pubDate) to Unix timestamp."""
    if not date_str:
        return 0.0
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str).timestamp()
    except Exception:
        return 0.0


def _parse_iso8601(date_str: str) -> float:
    """Parse ISO 8601 date (Atom updated) to Unix timestamp."""
    if not date_str:
        return 0.0
    from datetime import datetime, timezone
    try:
        # Handle trailing Z
        s = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0
