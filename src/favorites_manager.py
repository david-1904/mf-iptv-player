"""
Favoriten-Verwaltung mit JSON-Speicherung
"""
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum
from platform_utils import get_config_dir


class FavoriteType(Enum):
    LIVE = "live"
    VOD = "vod"
    SERIES = "series"


@dataclass
class Favorite:
    id: int  # stream_id oder series_id
    name: str
    type: str  # "live", "vod", "series"
    icon: str = ""
    container_extension: str = ""  # Fuer VOD/Series
    account_name: str = ""  # Zugehoeriger Account


class FavoritesManager:
    """Verwaltet Favoriten"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_config_dir() / "favorites.json"

        self.config_path = config_path
        self.favorites: list[Favorite] = []
        self._load()

    def _load(self):
        """Laedt Favoriten aus der Konfigurationsdatei"""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self.favorites = [
                    Favorite(**fav) for fav in data.get("favorites", [])
                ]
        except (json.JSONDecodeError, KeyError, TypeError):
            self.favorites = []

    def _save(self):
        """Speichert Favoriten in die Konfigurationsdatei"""
        data = {
            "favorites": [asdict(fav) for fav in self.favorites],
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def add(self, favorite: Favorite) -> bool:
        """Fuegt einen Favoriten hinzu. Gibt False zurueck wenn bereits vorhanden."""
        if self.is_favorite(favorite.id, favorite.type, favorite.account_name):
            return False
        self.favorites.append(favorite)
        self._save()
        return True

    def remove(self, item_id: int, item_type: str, account_name: str) -> bool:
        """Entfernt einen Favoriten. Gibt True zurueck wenn erfolgreich."""
        for i, fav in enumerate(self.favorites):
            if fav.id == item_id and fav.type == item_type and fav.account_name == account_name:
                del self.favorites[i]
                self._save()
                return True
        return False

    def toggle(self, favorite: Favorite) -> bool:
        """Wechselt Favoriten-Status. Gibt True zurueck wenn jetzt Favorit."""
        if self.is_favorite(favorite.id, favorite.type, favorite.account_name):
            self.remove(favorite.id, favorite.type, favorite.account_name)
            return False
        else:
            self.add(favorite)
            return True

    def is_favorite(self, item_id: int, item_type: str, account_name: str) -> bool:
        """Prueft ob ein Item ein Favorit ist"""
        return any(
            fav.id == item_id and fav.type == item_type and fav.account_name == account_name
            for fav in self.favorites
        )

    def get_all(self, account_name: Optional[str] = None) -> list[Favorite]:
        """Gibt alle Favoriten zurueck, optional gefiltert nach Account"""
        if account_name is None:
            return self.favorites.copy()
        return [fav for fav in self.favorites if fav.account_name == account_name]

    def get_by_type(self, item_type: str, account_name: Optional[str] = None) -> list[Favorite]:
        """Gibt Favoriten eines bestimmten Typs zurueck"""
        favs = self.get_all(account_name)
        return [fav for fav in favs if fav.type == item_type]

    def clear_account(self, account_name: str):
        """Entfernt alle Favoriten eines Accounts"""
        self.favorites = [fav for fav in self.favorites if fav.account_name != account_name]
        self._save()
