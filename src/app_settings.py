"""
Einfacher Key-Value-Speicher fuer App-Einstellungen.
"""
import json
from pathlib import Path


class AppSettings:
    _CONFIG_DIR = Path.home() / ".config" / "iptv-app"
    _SETTINGS_FILE = _CONFIG_DIR / "settings.json"

    def __init__(self):
        self._data: dict = {}
        self._load()

    def _load(self):
        try:
            if self._SETTINGS_FILE.exists():
                with open(self._SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        self._CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()
