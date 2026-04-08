# MF IPTV Player

A modern IPTV player with support for Xtream Codes and M3U playlists, built with Python, PySide6, and mpv.

![Version](https://img.shields.io/badge/Version-2.0.7-blue)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![PySide6](https://img.shields.io/badge/UI-PySide6-green)
![mpv](https://img.shields.io/badge/Player-mpv-orange)

## Features

- **Live TV, Movies (VOD) and Series** with full Xtream Codes & M3U support
- **Electronic Program Guide (EPG)** with Catchup / Timeshift
- **EPG program search** across all channels
- **Scheduled recordings** via EPG integration
- **Stream recording** powered by ffmpeg
- **Favorites** and **watch history** with resume support
- **Category management** — hide/show categories
- **Global search** across all content types
- **Picture-in-Picture** mode
- **Audio & subtitle track selection**
- **Multiple accounts** (Xtream Codes + M3U)
- **Auto-update** via GitHub Releases
- **Multilingual UI** — German & English (language selector in Settings)

---

## Windows — Download Ready-to-Run

1. Go to [**Releases**](../../releases)
2. Download the latest `MF-IPTV-Player-Windows.zip`
3. Extract the ZIP
4. Run `MF IPTV Player.exe`

> ffmpeg is bundled — no additional installation needed.

---

## Linux — Run from Source

### Requirements

- Python 3.11+
- mpv (`pacman -S mpv` / `apt install mpv` / `dnf install mpv`)
- ffmpeg (for recordings)

### Setup

```bash
git clone https://github.com/mf-iptv/mf-iptv-player.git
cd mf-iptv-player
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start

```bash
./run.sh
```

---

## Windows — Run from Source (Developers)

### Requirements

- [Python 3.11+](https://www.python.org/downloads/) — check "Add to PATH" during installation
- [libmpv-2.dll](https://sourceforge.net/projects/mpv-player-windows/files/libmpv/) — place in the project folder
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) — `ffmpeg.exe` in PATH or project folder

### Setup & Start

```bat
git clone https://github.com/mf-iptv/mf-iptv-player.git
cd mf-iptv-player
run.bat
```

---

## Build Windows EXE

The Windows release is built with [Nuitka](https://nuitka.net/) via GitHub Actions on every tagged release.

To build locally:

```bat
pip install nuitka
python build_windows.py
```

Output is placed in `dist/MF IPTV Player/`. Distribute this folder as a ZIP.

---

## License

Private project.
