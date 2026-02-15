"""
Plattformabhaengige Pfade fuer Config und Aufnahmen
"""
import os
import sys
from pathlib import Path


def get_config_dir() -> Path:
    """Gibt das Config-Verzeichnis zurueck und erstellt es bei Bedarf.
    Windows: %APPDATA%/iptv-app
    Linux:   ~/.config/iptv-app
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    config_dir = base / "iptv-app"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_recordings_dir() -> Path:
    """Gibt das Aufnahme-Verzeichnis zurueck.
    Windows: ~/Videos/IPTV
    Linux:   ~/Aufnahmen/IPTV
    """
    if sys.platform == "win32":
        return Path.home() / "Videos" / "IPTV"
    return Path.home() / "Aufnahmen" / "IPTV"
