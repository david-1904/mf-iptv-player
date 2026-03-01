"""
Build-Skript fuer Windows-EXE mit Nuitka.

Nuitka kompiliert Python zu C-Code statt einem self-extracting Archive,
was deutlich weniger Antivirus-Fehlalarme produziert als PyInstaller.

Ausfuehren:
    pip install nuitka ordered-set zstandard
    python build_windows.py

Ergebnis: dist/MF IPTV Player/  (ZIP-bar, Endnutzer klickt MF IPTV Player.exe)

Voraussetzung: libmpv-2.dll muss im Projektordner oder PATH liegen.
Download: https://sourceforge.net/projects/mpv-player-windows/files/libmpv/
"""
import subprocess
import shutil
import glob
import sys
import os

here = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(here, "src")
out_dir = os.path.join(here, "dist")
final_dir = os.path.join(out_dir, "MF IPTV Player")

# --- libmpv-2.dll suchen ---
mpv_dll = None
for pattern in ["libmpv-2.dll", "mpv-2.dll", "libmpv*.dll"]:
    found = glob.glob(os.path.join(here, pattern))
    if found:
        mpv_dll = found[0]
        break
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
        print("WARNUNG: icon.ico nicht vorhanden und SVG-Konvertierung fehlgeschlagen.")
        print("         EXE wird ohne Icon gebaut. Fuer ein Icon: pip install Pillow cairosvg")

# --- Version aus version.py lesen ---
version_str = "1.0.0.0"
try:
    version_file = os.path.join(src_dir, "version.py")
    with open(version_file) as f:
        for line in f:
            if "__version__" in line:
                v = line.split("=")[1].strip().strip('"').strip("'")
                parts = v.split(".")
                while len(parts) < 4:
                    parts.append("0")
                version_str = ".".join(parts[:4])
                break
    print(f"Version: {version_str}")
except Exception:
    pass

# --- Nuitka ausfuehren ---
# --standalone: Ordner-Output (wie PyInstaller --onedir), kein self-extracting Archive
# --enable-plugin=pyside6: PySide6-spezifische Optimierungen und Qt-Plugin-Erkennung
nuitka_out = os.path.join(out_dir, "main.dist")

cmd = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--enable-plugin=pyside6",
    "--windows-console-mode=disable",
    f"--windows-product-name=MF IPTV Player",
    f"--windows-file-description=MF IPTV Player",
    f"--windows-product-version={version_str}",
    f"--windows-file-version={version_str}",
    f"--include-data-dir={os.path.join(src_dir, 'assets')}=assets",
    f"--include-data-file={icon_svg}=icon.svg",
    f"--include-data-file={mpv_dll}=libmpv-2.dll",
    f"--output-dir={out_dir}",
    "--assume-yes-for-downloads",
    os.path.join(src_dir, "main.py"),
]

if icon_arg:
    cmd.insert(-1, f"--windows-icon-from-ico={icon_arg}")

env = os.environ.copy()
env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")

print("Starte Nuitka Build...")
print("(Das dauert deutlich laenger als PyInstaller - bitte warten)")
result = subprocess.run(cmd, env=env)

if result.returncode != 0:
    print("FEHLER: Nuitka Build fehlgeschlagen!")
    sys.exit(result.returncode)

# --- Output-Ordner umbenennen ---
if os.path.exists(final_dir):
    shutil.rmtree(final_dir)

if os.path.exists(nuitka_out):
    shutil.move(nuitka_out, final_dir)
    # main.exe -> MF IPTV Player.exe umbenennen
    old_exe = os.path.join(final_dir, "main.exe")
    new_exe = os.path.join(final_dir, "MF IPTV Player.exe")
    if os.path.exists(old_exe):
        os.rename(old_exe, new_exe)
    print(f"\nFertig! Verteilbares Paket liegt in: {final_dir}")
else:
    print("FEHLER: Nuitka-Output-Ordner nicht gefunden!")
    sys.exit(1)
