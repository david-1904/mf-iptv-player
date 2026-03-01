"""
Geplante Aufnahmen: Datenhaltung und Persistenz
"""
import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from platform_utils import get_config_dir


@dataclass
class ScheduledRecording:
    id: str
    channel_name: str
    stream_url: str
    start_timestamp: float
    end_timestamp: float
    account_name: str
    epg_title: str = ""
    status: str = "pending"  # "pending", "recording", "done", "failed"


class ScheduleManager:

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = get_config_dir() / "scheduled.json"
        self.config_path = config_path
        self.recordings: list[ScheduledRecording] = []
        self._load()

    def _load(self):
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path) as f:
                data = json.load(f)
            self.recordings = [ScheduledRecording(**r) for r in data.get("recordings", [])]
        except Exception:
            self.recordings = []

    def save(self):
        data = {"recordings": [asdict(r) for r in self.recordings]}
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def add(self, rec: ScheduledRecording):
        self.recordings.append(rec)
        self.save()

    def remove(self, rec_id: str):
        self.recordings = [r for r in self.recordings if r.id != rec_id]
        self.save()

    def get_all(self) -> list[ScheduledRecording]:
        return self.recordings.copy()

    def get_active(self) -> list[ScheduledRecording]:
        """Alle noch nicht abgeschlossenen Aufnahmen (geplant + laufend)"""
        return [r for r in self.recordings if r.status in ("pending", "recording")]

    def cleanup_old(self):
        """Entfernt erledigte Aufnahmen die aelter als 7 Tage sind"""
        import time
        cutoff = time.time() - 7 * 86400
        self.recordings = [
            r for r in self.recordings
            if r.status not in ("done", "failed") or r.end_timestamp > cutoff
        ]
        self.save()


def new_id() -> str:
    return str(uuid.uuid4())
