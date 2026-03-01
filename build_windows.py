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

# --- Icon: SVG -> ICO konvertieren (falls noetig) ---
icon_svg = os.path.join(here, "icon.svg")
icon_ico = os.path.join(here, "icon.ico")
icon_arg = None

if os.path.exists(icon_ico):
    icon_arg = icon_ico
    print(f"Icon gefunden: {icon_ico}")
else:
    # Versuche SVG -> ICO mit Pillow+cairosvg
    try:
        from PIL import Image
        import cairosvg
        import io
        png_data = cairosvg.svg2png(url=icon_svg, output_width=256, output_height=256)
        img = Image.open(io.BytesIO(png_data))
        img.save(icon_ico, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        icon_arg = icon_ico
        print(f"Icon konvertiert: {icon_ico}")
    except Exception:
        # Kein Pillow/cairosvg vorhanden, ohne Icon bauen
        print("WARNUNG: icon.ico nicht vorhanden und SVG-Konvertierung fehlgeschlagen.")
        print("         EXE wird ohne Icon gebaut. Fuer ein Icon: pip install Pillow cairosvg")

# --- PyInstaller ausfuehren ---
add_binary = mpv_dll + os.pathsep + "."

args = [
    os.path.join(here, "src", "main.py"),
    "--name", "MF IPTV Player",
    "--onedir",
    "--windowed",
    "--add-data", os.path.join(here, "src", "assets") + os.pathsep + "assets",
    "--add-data", icon_svg + os.pathsep + ".",
    "--add-data", icon_ico + os.pathsep + ".",
    "--add-binary", add_binary,
    "--paths", os.path.join(here, "src"),
    "--noconfirm",
    # PySide6: PyInstaller erkennt die meisten Imports automatisch.
    # Nur hidden-imports fuer Module die nicht per "from PySide6.X" importiert werden.
    "--collect-all", "shiboken6",
    "--hidden-import", "PySide6.QtOpenGLWidgets",
    "--hidden-import", "PySide6.QtOpenGL",
    # Weitere Abhaengigkeiten
    "--collect-all", "qasync",
    "--collect-all", "aiohttp",
    "--hidden-import", "multidict",
    "--hidden-import", "yarl",
    "--hidden-import", "aiosignal",
    "--hidden-import", "frozenlist",
    "--hidden-import", "async_timeout",
]

if icon_arg:
    args += ["--icon", icon_arg]

PyInstaller.__main__.run(args)

print()
print(f"Fertig! Verteilbares Paket liegt in: {dist_dir}")
print("Diesen Ordner als ZIP packen und weitergeben.")
