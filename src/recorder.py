"""
Stream-Aufnahme mit ffmpeg
"""
import subprocess
import signal
import sys
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from platform_utils import get_recordings_dir

_IS_WIN = sys.platform == "win32"


def _find_ffmpeg() -> str:
    """Sucht ffmpeg: neben der EXE (PyInstaller), dann im PATH."""
    # Bei PyInstaller liegt ffmpeg.exe neben der EXE
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        local = os.path.join(exe_dir, "ffmpeg.exe" if _IS_WIN else "ffmpeg")
        if os.path.isfile(local):
            return local
    return "ffmpeg"


class StreamRecorder:
    """Nimmt Streams verlustfrei mit ffmpeg auf"""

    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = get_recordings_dir()
        self.output_dir = output_dir
        self._process: Optional[subprocess.Popen] = None
        self._current_title: str = ""
        self._current_file: Optional[Path] = None
        self._start_time: Optional[datetime] = None
        self._log_file: Optional[Path] = None
        self._log_fh = None

    @property
    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def current_title(self) -> str:
        return self._current_title

    @property
    def current_file(self) -> Optional[Path]:
        return self._current_file

    @property
    def start_time(self) -> Optional[datetime]:
        return self._start_time

    def start(self, url: str, title: str) -> Path:
        """Startet die Aufnahme. Gibt den Dateipfad zurueck."""
        if self.is_recording:
            self.stop()

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Dateiname: Titel bereinigen + Datum/Zeit
        safe_title = re.sub(r'[^\w\s\-]', '', title).strip().replace(' ', '_')
        if not safe_title:
            safe_title = "Aufnahme"
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_title}_{timestamp}.mkv"
        self._current_file = self.output_dir / filename
        self._current_title = title
        self._start_time = now

        # Log-Datei fuer ffmpeg stderr (Debugging)
        self._log_file = self.output_dir / f".ffmpeg_{timestamp}.log"

        self._log_fh = open(self._log_file, "w")

        # Plattformabhaengige Prozess-Erstellung
        popen_kwargs = dict(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=self._log_fh,
        )
        if _IS_WIN:
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["preexec_fn"] = os.setpgrp

        self._process = subprocess.Popen(
            [
                _find_ffmpeg(),
                "-nostdin",
                "-extension_picky", "0",
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
                "-i", url,
                "-map", "0:v?",
                "-map", "0:a?",
                "-c", "copy",
                "-y",
                str(self._current_file),
            ],
            **popen_kwargs,
        )

        return self._current_file

    def stop(self) -> Optional[Path]:
        """Stoppt die Aufnahme. Gibt den Dateipfad zurueck."""
        if not self._process:
            return None

        filepath = self._current_file

        try:
            if _IS_WIN:
                self._process.terminate()
            else:
                os.killpg(self._process.pid, signal.SIGINT)
            self._process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                if _IS_WIN:
                    self._process.kill()
                else:
                    os.killpg(self._process.pid, signal.SIGKILL)
                self._process.wait(timeout=3)
            except Exception:
                pass
        except Exception:
            try:
                self._process.kill()
                self._process.wait(timeout=3)
            except Exception:
                pass

        self._process = None
        self._current_title = ""
        self._start_time = None

        # Log-Handle schliessen
        if self._log_fh:
            try:
                self._log_fh.close()
            except Exception:
                pass
            self._log_fh = None

        # Log-Datei aufraeumen
        if self._log_file and self._log_file.exists():
            try:
                self._log_file.unlink()
            except Exception:
                pass
            self._log_file = None

        return filepath
