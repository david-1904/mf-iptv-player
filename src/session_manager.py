"""
Session-Zustand: merkt sich zuletzt geöffnetes Item pro Account/Modus
"""
import json
from pathlib import Path


class SessionManager:
    def __init__(self):
        self._path = Path("~/.config/iptv-app/session.json").expanduser()

    # --- Modus ---

    def save_mode(self, account_name: str, mode: str):
        state = self._load()
        state[f"{account_name}_mode"] = mode
        self._save(state)

    def get_mode(self, account_name: str) -> str | None:
        return self._load().get(f"{account_name}_mode")

    # --- Item-Saves ---

    def save_live(self, account_name: str, stream_id: int, name: str, icon: str, category_id: str):
        state = self._load()
        state[f"{account_name}_live"] = {
            "stream_id": stream_id,
            "name": name,
            "icon": icon,
            "category_id": category_id,
        }
        self._save(state)

    def save_vod(self, account_name: str, stream_id: int, name: str, icon: str,
                 container_extension: str, category_id: str):
        state = self._load()
        state[f"{account_name}_vod"] = {
            "stream_id": stream_id,
            "name": name,
            "icon": icon,
            "container_extension": container_extension,
            "category_id": category_id,
        }
        self._save(state)

    def save_series(self, account_name: str, series_id: int, name: str, cover: str, category_id: str):
        state = self._load()
        state[f"{account_name}_series"] = {
            "series_id": series_id,
            "name": name,
            "cover": cover,
            "category_id": category_id,
        }
        self._save(state)

    # --- Abfrage ---

    def get(self, account_name: str, mode: str) -> dict | None:
        return self._load().get(f"{account_name}_{mode}")

    # --- Intern ---

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, state: dict):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
