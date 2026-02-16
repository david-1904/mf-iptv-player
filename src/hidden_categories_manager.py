"""
Verwaltung ausgeblendeter Kategorien mit JSON-Speicherung
"""
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from platform_utils import get_config_dir


@dataclass
class HiddenCategory:
    account_name: str
    mode: str  # "live", "vod", "series"
    category_id: str
    category_name: str = ""


class HiddenCategoriesManager:
    """Verwaltet ausgeblendete Kategorien pro Account und Modus"""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_config_dir() / "hidden_categories.json"
        self.config_path = config_path
        self.hidden: list[HiddenCategory] = []
        self._load()

    def _load(self):
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self.hidden = [
                    HiddenCategory(**entry) for entry in data.get("hidden", [])
                ]
        except (json.JSONDecodeError, KeyError, TypeError):
            self.hidden = []

    def _save(self):
        data = {"hidden": [asdict(entry) for entry in self.hidden]}
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def hide(self, account_name: str, mode: str, category_id: str, category_name: str = "") -> bool:
        if self.is_hidden(account_name, mode, category_id):
            return False
        self.hidden.append(HiddenCategory(
            account_name=account_name, mode=mode,
            category_id=category_id, category_name=category_name,
        ))
        self._save()
        return True

    def unhide(self, account_name: str, mode: str, category_id: str) -> bool:
        for i, entry in enumerate(self.hidden):
            if entry.account_name == account_name and entry.mode == mode and entry.category_id == category_id:
                del self.hidden[i]
                self._save()
                return True
        return False

    def is_hidden(self, account_name: str, mode: str, category_id: str) -> bool:
        return any(
            e.account_name == account_name and e.mode == mode and e.category_id == category_id
            for e in self.hidden
        )

    def get_hidden(self, account_name: str, mode: str) -> list[HiddenCategory]:
        return [e for e in self.hidden if e.account_name == account_name and e.mode == mode]

    def unhide_all(self, account_name: str, mode: str):
        self.hidden = [
            e for e in self.hidden
            if not (e.account_name == account_name and e.mode == mode)
        ]
        self._save()
