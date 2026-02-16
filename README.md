# MF IPTV Player

Ein moderner IPTV-Player mit Unterstuetzung fuer Xtream Codes und M3U-Playlists.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![PySide6](https://img.shields.io/badge/UI-PySide6-green)
![mpv](https://img.shields.io/badge/Player-mpv-orange)

## Features

- Live TV, Filme (VOD) und Serien
- Elektronischer Programmfuehrer (EPG) mit Catchup/Timeshift
- Favoriten und Wiedergabeverlauf
- Stream-Aufnahme (ffmpeg)
- Kategorien ausblenden/verwalten
- Suche ueber alle Inhalte
- Picture-in-Picture Modus
- Audio-/Untertitel-Auswahl
- Mehrere Accounts (Xtream Codes + M3U)

---

## Windows — Fertiges Programm herunterladen

1. Gehe zu [**Releases**](../../releases)
2. Lade die neueste `MF-IPTV-Player-Windows.zip` herunter
3. ZIP entpacken
4. `MF IPTV Player.exe` starten

> ffmpeg ist fuer Aufnahmen bereits enthalten. Keine Installation noetig.

---

## Linux — Aus Quellcode starten

### Voraussetzungen

- Python 3.11+
- mpv (`pacman -S mpv` / `apt install mpv`)
- ffmpeg (fuer Aufnahmen)

### Installation

```bash
git clone https://github.com/DEIN-USER/iptv-app.git
cd iptv-app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Starten

```bash
./run.sh
```

---

## Windows — Aus Quellcode starten (Entwickler)

### Voraussetzungen

- [Python 3.11+](https://www.python.org/downloads/) (bei Installation "Add to PATH" ankreuzen!)
- [libmpv-2.dll](https://sourceforge.net/projects/mpv-player-windows/files/libmpv/) — in den Projektordner legen
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) — `ffmpeg.exe` in den PATH oder Projektordner

### Installation & Start

```bat
git clone https://github.com/DEIN-USER/iptv-app.git
cd iptv-app
run.bat
```

---

## EXE selbst bauen

```bat
pip install pyinstaller
python build_windows.py
```

Das Ergebnis liegt in `dist/MF IPTV Player/`. Diesen Ordner als ZIP weitergeben.

---

## Lizenz

Privates Projekt.
