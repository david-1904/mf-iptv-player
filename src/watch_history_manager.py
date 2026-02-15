"""
Wiedergabeverlauf-Verwaltung mit JSON-Speicherung
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field
from platform_utils import get_config_dir


MAX_HISTORY_ENTRIES = 200


@dataclass
class WatchEntry:
    stream_id: int
    stream_type: str  # "live", "vod", "series"
    account_name: str
    title: str
    icon: str = ""
    position: float = 0.0  # Sekunden
    duration: float = 0.0  # Sekunden
    container_extension: str = ""
    watched_at: str = ""  # ISO-Format


class WatchHistoryManager:
    """Verwaltet den Wiedergabeverlauf"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_config_dir() / "watch_history.json"

        self.config_path = config_path
        self.entries: list[WatchEntry] = []
        self._load()

    def _load(self):
        """Laedt Verlauf aus der Konfigurationsdatei"""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self.entries = [
                    WatchEntry(**entry) for entry in data.get("history", [])
                ]
        except (json.JSONDecodeError, KeyError, TypeError):
            self.entries = []

    def _save(self):
        """Speichert Verlauf in die Konfigurationsdatei"""
        data = {
            "history": [asdict(entry) for entry in self.entries],
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def add_or_update(self, entry: WatchEntry):
        """Fuegt einen Eintrag hinzu oder aktualisiert einen bestehenden"""
        entry.watched_at = datetime.now().isoformat()

        # Bestehenden Eintrag suchen und entfernen
        self.entries = [
            e for e in self.entries
            if not (e.stream_id == entry.stream_id
                    and e.stream_type == entry.stream_type
                    and e.account_name == entry.account_name)
        ]

        # Neuen Eintrag am Anfang einfuegen
        self.entries.insert(0, entry)

        # Max-Limit einhalten
        if len(self.entries) > MAX_HISTORY_ENTRIES:
            self.entries = self.entries[:MAX_HISTORY_ENTRIES]

        self._save()

    def get_all(self, account_name: Optional[str] = None) -> list[WatchEntry]:
        """Gibt alle Eintraege zurueck, optional gefiltert nach Account"""
        if account_name is None:
            return self.entries.copy()
        return [e for e in self.entries if e.account_name == account_name]

    def get_position(self, stream_id: int, stream_type: str, account_name: str) -> tuple[float, float]:
        """Gibt (position, duration) fuer einen Stream zurueck, oder (0, 0)"""
        for e in self.entries:
            if (e.stream_id == stream_id
                    and e.stream_type == stream_type
                    and e.account_name == account_name):
                return (e.position, e.duration)
        return (0.0, 0.0)

    def remove(self, stream_id: int, stream_type: str, account_name: str) -> bool:
        """Entfernt einen Eintrag. Gibt True zurueck wenn erfolgreich."""
        for i, e in enumerate(self.entries):
            if (e.stream_id == stream_id
                    and e.stream_type == stream_type
                    and e.account_name == account_name):
                del self.entries[i]
                self._save()
                return True
        return False

    def clear(self, account_name: Optional[str] = None):
        """Loescht alle Eintraege, optional nur fuer einen Account"""
        if account_name is None:
            self.entries = []
        else:
            self.entries = [e for e in self.entries if e.account_name != account_name]
        self._save()
