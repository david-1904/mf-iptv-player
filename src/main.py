#!/usr/bin/env python3
"""
MF IPTV Player
Verwendet PySide6 und mpv
"""
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor, QIcon
import qasync
import asyncio

from main_window import MainWindow


def _base_path() -> str:
    """Gibt den Basispfad zurueck (PyInstaller-kompatibel)."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def setup_dark_theme(app: QApplication):
    """Konfiguriert ein dunkles Theme"""
    app.setStyle("Fusion")
    _assets = os.path.join(_base_path(), "assets")
    _arrow_down = os.path.join(_assets, "arrow-down.svg").replace("\\", "/")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(18, 18, 18))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(30, 30, 46))
    palette.setColor(QPalette.AlternateBase, QColor(35, 35, 50))
    palette.setColor(QPalette.ToolTipBase, QColor(30, 30, 46))
    palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(30, 30, 46))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(0, 120, 212))
    palette.setColor(QPalette.Highlight, QColor(0, 120, 212))
    palette.setColor(QPalette.HighlightedText, Qt.white)

    app.setPalette(palette)

    app.setStyleSheet("""
        QMainWindow {
            background-color: #121212;
        }
        QToolBar {
            background-color: #0d0d14;
            border: none;
            padding: 4px;
        }
        QToolBar QToolButton {
            background: transparent;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            color: #ccc;
        }
        QToolBar QToolButton:hover {
            background-color: #1a1a2a;
        }
        QStatusBar {
            background-color: #0d0d14;
            color: #999;
        }
        QLineEdit {
            padding: 8px;
            border: 1px solid #2a2a3a;
            border-radius: 6px;
            background-color: #1e1e2e;
            color: white;
            margin: 4px 0;
        }
        QLineEdit:focus {
            border-color: #0078d4;
        }
        QPushButton {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            background-color: #0078d4;
            color: white;
        }
        QPushButton:hover {
            background-color: #1a8ae8;
        }
        QPushButton:pressed {
            background-color: #006cc1;
        }
        QPushButton:disabled {
            background-color: #2a2a3a;
            color: #666;
        }
        QComboBox {
            padding: 8px;
            border: 1px solid #2a2a3a;
            border-radius: 6px;
            background-color: #1e1e2e;
            color: white;
        }
        QComboBox::drop-down {
            border: none;
            width: 24px;
            subcontrol-position: center right;
        }
        QComboBox::down-arrow {
            image: url(ARROW_DOWN_PATH);
            width: 10px;
            height: 7px;
        }
        QComboBox QAbstractItemView {
            background-color: #1e1e2e;
            color: white;
            selection-background-color: #0078d4;
        }
        QScrollBar:vertical {
            background-color: #121212;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #444;
            border-radius: 6px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #555;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar:horizontal {
            height: 0;
        }
        QToolTip {
            background-color: #1e1e2e;
            color: #ddd;
            border: 1px solid #2a2a3a;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
        }
        QMessageBox {
            background-color: #1e1e2e;
        }
        QMessageBox QLabel {
            color: white;
        }
    """.replace("ARROW_DOWN_PATH", _arrow_down))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MF IPTV Player")
    app.setOrganizationName("IPTVApp")
    app.setDesktopFileName("iptv-player")

    base = _base_path() if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Windows: .ico bevorzugen (bessere Taskbar-Qualitaet), sonst SVG
    if sys.platform == 'win32':
        icon_path = os.path.join(base, "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base, "icon.svg")
    else:
        icon_path = os.path.join(base, "icon.svg")
    app.setWindowIcon(QIcon(icon_path))

    setup_dark_theme(app)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
