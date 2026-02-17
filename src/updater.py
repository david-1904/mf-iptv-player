"""
Auto-Update via GitHub Releases.
Prueft auf neue Versionen und fuehrt Updates durch.
"""
import asyncio
import logging
import os
import platform
import sys
import zipfile
import tempfile
import shutil
from dataclasses import dataclass

import aiohttp

from version import __version__

logger = logging.getLogger(__name__)

GITHUB_REPO = "david-1904/mf-iptv-player"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


@dataclass
class ReleaseInfo:
    version: str
    download_url: str
    release_notes: str
    tag_name: str


def _parse_version(v: str) -> tuple[int, ...]:
    """Parst 'v1.2.3' oder '1.2.3' zu (1, 2, 3)."""
    v = v.lstrip("v")
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)


def _is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


class UpdateChecker:

    async def check_for_update(self) -> ReleaseInfo | None:
        """Prueft GitHub auf neue Version. Gibt ReleaseInfo zurueck oder None."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(RELEASES_URL) as resp:
                    if resp.status != 200:
                        logger.warning("Update-Check fehlgeschlagen: HTTP %s", resp.status)
                        return None
                    data = await resp.json()
        except Exception as e:
            logger.warning("Update-Check fehlgeschlagen: %s", e)
            return None

        tag = data.get("tag_name", "")
        if not tag or not _is_newer(tag, __version__):
            return None

        # Download-URL bestimmen
        download_url = ""
        is_windows = platform.system() == "Windows"
        assets = data.get("assets", [])
        for asset in assets:
            name = asset.get("name", "").lower()
            if is_windows and name.endswith(".zip"):
                download_url = asset["browser_download_url"]
                break

        body = data.get("body", "") or ""

        return ReleaseInfo(
            version=tag.lstrip("v"),
            download_url=download_url,
            release_notes=body,
            tag_name=tag,
        )

    async def update_linux(self, progress_callback=None) -> tuple[bool, str]:
        """Fuehrt git pull aus (Linux-Update)."""
        try:
            if progress_callback:
                progress_callback("Git pull wird ausgefuehrt...")

            # Projekt-Root ermitteln
            if getattr(sys, "frozen", False):
                return False, "Update nicht moeglich im gepackten Modus."
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            proc = await asyncio.create_subprocess_exec(
                "git", "pull", "origin", "main",
                cwd=project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                output = stdout.decode().strip()
                if progress_callback:
                    progress_callback("Update erfolgreich!")
                return True, output
            else:
                err = stderr.decode().strip()
                logger.error("git pull fehlgeschlagen: %s", err)
                return False, f"Fehler: {err}"
        except Exception as e:
            logger.error("Update fehlgeschlagen: %s", e)
            return False, str(e)

    async def update_windows(self, download_url: str, progress_callback=None) -> tuple[bool, str]:
        """Laedt ZIP herunter und ersetzt Dateien (Windows-Update)."""
        if not download_url:
            return False, "Kein Download-Link verfuegbar."

        try:
            if progress_callback:
                progress_callback("Download wird gestartet...")

            timeout = aiohttp.ClientTimeout(total=300)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(download_url) as resp:
                    if resp.status != 200:
                        return False, f"Download fehlgeschlagen: HTTP {resp.status}"

                    total = resp.content_length or 0
                    downloaded = 0
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                    try:
                        async for chunk in resp.content.iter_chunked(64 * 1024):
                            tmp.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total > 0:
                                pct = int(downloaded / total * 100)
                                progress_callback(f"Download: {pct}%")
                        tmp.close()

                        if progress_callback:
                            progress_callback("Entpacke Update...")

                        # Zielverzeichnis = Verzeichnis der EXE
                        app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))

                        with zipfile.ZipFile(tmp.name, "r") as zf:
                            # In temp-Ordner entpacken
                            extract_dir = tempfile.mkdtemp()
                            zf.extractall(extract_dir)

                            # Dateien kopieren
                            entries = os.listdir(extract_dir)
                            source_dir = extract_dir
                            if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
                                source_dir = os.path.join(extract_dir, entries[0])

                            for item in os.listdir(source_dir):
                                src = os.path.join(source_dir, item)
                                dst = os.path.join(app_dir, item)
                                if os.path.isdir(src):
                                    if os.path.exists(dst):
                                        shutil.rmtree(dst)
                                    shutil.copytree(src, dst)
                                else:
                                    shutil.copy2(src, dst)

                            shutil.rmtree(extract_dir)

                        if progress_callback:
                            progress_callback("Update erfolgreich!")
                        return True, "Update erfolgreich installiert."
                    finally:
                        os.unlink(tmp.name)

        except Exception as e:
            logger.error("Windows-Update fehlgeschlagen: %s", e)
            return False, str(e)
