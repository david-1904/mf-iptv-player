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
        """Laedt ZIP herunter, entpackt in Temp-Ordner und startet Updater-Script.

        Da die laufende EXE auf Windows nicht ueberschrieben werden kann, wird ein
        Batch-Script erstellt das nach dem App-Exit die Dateien kopiert und die App
        neu startet. Die App muss danach selbst beendet werden (return-Wert 'RESTART').
        """
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
                        exe_name = os.path.basename(sys.executable) if getattr(sys, "frozen", False) else "MF IPTV Player.exe"
                        exe_path = os.path.join(app_dir, exe_name)

                        # In Temp-Ordner entpacken
                        extract_dir = tempfile.mkdtemp(prefix="mfiptv_update_")
                        with zipfile.ZipFile(tmp.name, "r") as zf:
                            zf.extractall(extract_dir)

                        # Unterordner-Struktur normalisieren (ZIP enthaelt oft einen Unterordner)
                        entries = os.listdir(extract_dir)
                        source_dir = extract_dir
                        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
                            source_dir = os.path.join(extract_dir, entries[0])

                        # PowerShell-Script erstellen das nach App-Exit ein Fortschrittsfenster zeigt
                        pid = os.getpid()
                        ps_path = os.path.join(tempfile.gettempdir(), "mfiptv_updater.ps1")
                        # Pfade fuer PowerShell escapen (keine einfachen Anfuehrungszeichen in Pfaden erlaubt)
                        src_esc = source_dir.replace("'", "''")
                        app_esc = app_dir.replace("'", "''")
                        ext_esc = extract_dir.replace("'", "''")
                        exe_esc = exe_path.replace("'", "''")
                        ps = f"""Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'MF IPTV Player - Update'
$form.Size = New-Object System.Drawing.Size(380, 140)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.ControlBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)

$lbl = New-Object System.Windows.Forms.Label
$lbl.Text = 'Update wird installiert...'
$lbl.ForeColor = [System.Drawing.Color]::White
$lbl.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$lbl.AutoSize = $false
$lbl.Size = New-Object System.Drawing.Size(360, 30)
$lbl.Location = New-Object System.Drawing.Point(10, 20)
$lbl.TextAlign = 'MiddleCenter'
$form.Controls.Add($lbl)

$sub = New-Object System.Windows.Forms.Label
$sub.Text = 'Bitte warten...'
$sub.ForeColor = [System.Drawing.Color]::FromArgb(160, 160, 160)
$sub.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$sub.AutoSize = $false
$sub.Size = New-Object System.Drawing.Size(360, 20)
$sub.Location = New-Object System.Drawing.Point(10, 55)
$sub.TextAlign = 'MiddleCenter'
$form.Controls.Add($sub)

$form.Show()
$form.Refresh()

# Warten bis App-Prozess beendet
$sub.Text = 'Warte auf App-Beendigung...'
$form.Refresh()
do {{
    Start-Sleep -Milliseconds 500
    $proc = Get-Process -Id {pid} -ErrorAction SilentlyContinue
}} while ($proc)

# Dateien kopieren
$sub.Text = 'Dateien werden kopiert...'
$form.Refresh()
& robocopy '{src_esc}' '{app_esc}' /E /IS /IT /NP /NFL /NDL /NJH /NJS | Out-Null

# Temp-Ordner loeschen
$sub.Text = 'Aufraumen...'
$form.Refresh()
Remove-Item -Path '{ext_esc}' -Recurse -Force -ErrorAction SilentlyContinue

# App neu starten
$sub.Text = 'App wird gestartet...'
$form.Refresh()
Start-Process '{exe_esc}'
Start-Sleep -Milliseconds 800

$form.Close()
Remove-Item -Path $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""
                        with open(ps_path, "w", encoding="utf-8") as f:
                            f.write(ps)

                        # PowerShell-Script detached starten (mit sichtbarem Fenster)
                        import subprocess
                        CREATE_NEW_PROCESS_GROUP = 0x00000200
                        DETACHED_PROCESS = 0x00000008
                        subprocess.Popen(
                            [
                                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                "-WindowStyle", "Hidden", "-File", ps_path,
                            ],
                            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                            close_fds=True,
                        )

                        if progress_callback:
                            progress_callback("App wird neu gestartet...")
                        return True, "RESTART"

                    finally:
                        try:
                            os.unlink(tmp.name)
                        except OSError:
                            pass

        except Exception as e:
            logger.error("Windows-Update fehlgeschlagen: %s", e)
            return False, str(e)
