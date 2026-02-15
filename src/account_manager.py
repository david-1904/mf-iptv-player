"""
Account-Verwaltung mit JSON-Speicherung
"""
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from platform_utils import get_config_dir


@dataclass
class AccountEntry:
    """Generischer Account-Eintrag (Xtream oder M3U)"""
    name: str
    type: str = "xtream"       # "xtream" oder "m3u"
    server: str = ""           # Xtream
    username: str = ""         # Xtream
    password: str = ""         # Xtream
    url: str = ""              # M3U Playlist-URL


class AccountManager:
    """Verwaltet IPTV-Accounts"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_config_dir() / "accounts.json"

        self.config_path = config_path
        self.accounts: list[AccountEntry] = []
        self.selected_index: int = -1
        self._load()

    def _load(self):
        """Laedt Accounts aus der Konfigurationsdatei"""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self.accounts = [
                    AccountEntry(**acc) for acc in data.get("accounts", [])
                ]
                self.selected_index = data.get("selected_index", -1)
                if self.selected_index >= len(self.accounts):
                    self.selected_index = len(self.accounts) - 1 if self.accounts else -1
        except (json.JSONDecodeError, KeyError):
            self.accounts = []
            self.selected_index = -1

    def _save(self):
        """Speichert Accounts in die Konfigurationsdatei"""
        data = {
            "accounts": [asdict(acc) for acc in self.accounts],
            "selected_index": self.selected_index,
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def add_account(self, account: AccountEntry) -> int:
        """Fuegt einen Account hinzu und gibt den Index zurueck"""
        self.accounts.append(account)
        self.selected_index = len(self.accounts) - 1
        self._save()
        return self.selected_index

    def remove_account(self, index: int):
        """Entfernt einen Account"""
        if 0 <= index < len(self.accounts):
            del self.accounts[index]
            if self.selected_index >= len(self.accounts):
                self.selected_index = len(self.accounts) - 1 if self.accounts else -1
            elif self.selected_index > index:
                self.selected_index -= 1
            self._save()

    def select_account(self, index: int):
        """Waehlt einen Account aus"""
        if 0 <= index < len(self.accounts):
            self.selected_index = index
            self._save()

    def get_selected(self) -> Optional[AccountEntry]:
        """Gibt den aktuell ausgewaehlten Account zurueck"""
        if 0 <= self.selected_index < len(self.accounts):
            return self.accounts[self.selected_index]
        return None

    def get_all(self) -> list[AccountEntry]:
        """Gibt alle Accounts zurueck"""
        return self.accounts.copy()

    def update_account(self, index: int, account: AccountEntry):
        """Aktualisiert einen Account"""
        if 0 <= index < len(self.accounts):
            self.accounts[index] = account
            self._save()
