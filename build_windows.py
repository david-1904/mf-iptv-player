"""
Build-Skript fuer Windows-EXE mit PyInstaller.

Ausfuehren:
    pip install pyinstaller
    python build_windows.py

Ergebnis: dist/MF IPTV Player/  (ZIP-bar, Endnutzer klickt MF IPTV Player.exe)

Voraussetzung: libmpv-2.dll muss im Projektordner oder PATH liegen.
Download: https://sourceforge.net/projects/mpv-player-windows/files/libmpv/
"""
import PyInstaller.__main__
import shutil
import glob
import sys
import os

here = os.path.dirname(os.path.abspath(__file__))
dist_dir = os.path.join(here, "dist", "MF IPTV Player")

# --- libmpv-2.dll suchen ---
mpv_dll = None
# 1) Im Projektordner
for pattern in ["libmpv-2.dll", "mpv-2.dll", "libmpv*.dll"]:
    found = glob.glob(os.path.join(here, pattern))
    if found:
        mpv_dll = found[0]
        break
# 2) Im PATH
if not mpv_dll:
    mpv_dll = shutil.which("libmpv-2.dll") or shutil.which("mpv-2.dll")

if not mpv_dll:
    print("FEHLER: libmpv-2.dll nicht gefunden!")
    print("Lade sie herunter von:")
    print("  https://sourceforge.net/projects/mpv-player-windows/files/libmpv/")
    print("und lege sie in diesen Ordner:", here)
    sys.exit(1)

print(f"libmpv gefunden: {mpv_dll}")

# --- PyInstaller ausfuehren ---
add_binary = mpv_dll + os.pathsep + "."

PyInstaller.__main__.run([
    os.path.join(here, "src", "main.py"),
    "--name", "MF IPTV Player",
    "--onedir",
    "--windowed",
    "--icon", os.path.join(here, "icon.svg"),
    "--add-data", os.path.join(here, "src", "assets") + os.pathsep + "assets",
    "--add-data", os.path.join(here, "icon.svg") + os.pathsep + ".",
    "--add-binary", add_binary,
    "--paths", os.path.join(here, "src"),
    "--noconfirm",
])

print()
print(f"Fertig! Verteilbares Paket liegt in: {dist_dir}")
print("Diesen Ordner als ZIP packen und weitergeben.")
