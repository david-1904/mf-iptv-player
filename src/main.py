#!/usr/bin/env python3
"""
MF IPTV Player
Verwendet PySide6 und mpv
"""
import sys
import os
from PySide6.QtWidgets import QApplication, QAbstractButton, QAbstractSlider, QComboBox, QAbstractItemView
from PySide6.QtCore import Qt, QObject, QEvent, QTranslator
from PySide6.QtGui import QPalette, QColor, QIcon, QFont, QFontDatabase
import qasync
import asyncio

from app_settings import AppSettings
from main_window import MainWindow


class _HandCursorFilter(QObject):
    """Setzt den Zeigefinger-Cursor global auf alle interaktiven Widgets."""
    _types = (QAbstractButton, QAbstractSlider, QComboBox, QAbstractItemView)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter and isinstance(obj, self._types):
            obj.setCursor(
                Qt.CursorShape.PointingHandCursor if obj.isEnabled()
                else Qt.CursorShape.ArrowCursor
            )
        return False


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
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #07071a, stop:0.5 #0b0b1f, stop:1 #0d081e);
        }
        QToolBar {
            background-color: rgba(8, 8, 20, 220);
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
            background-color: rgba(255, 255, 255, 8);
        }
        QStatusBar {
            background-color: rgba(7, 7, 18, 230);
            color: #777;
            border-top: 1px solid rgba(255, 255, 255, 5);
        }
        QLineEdit {
            padding: 9px 12px;
            border: 1px solid rgba(255, 255, 255, 12);
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 5);
            color: white;
            margin: 4px 0;
        }
        QLineEdit:focus {
            border-color: rgba(0, 120, 212, 200);
            background-color: rgba(0, 120, 212, 8);
        }
        QPushButton {
            padding: 8px 16px;
            border: 1px solid rgba(255, 255, 255, 10);
            border-radius: 8px;
            background-color: #0078d4;
            color: white;
        }
        QPushButton:hover {
            background-color: #1a8ae8;
            border-color: rgba(255, 255, 255, 18);
        }
        QPushButton:pressed {
            background-color: #006cc1;
        }
        QPushButton:disabled {
            background-color: rgba(255, 255, 255, 5);
            border-color: rgba(255, 255, 255, 5);
            color: rgba(255, 255, 255, 30);
        }
        QComboBox {
            padding: 8px 12px;
            border: 1px solid rgba(255, 255, 255, 10);
            border-radius: 8px;
            background-color: rgba(255, 255, 255, 5);
            color: white;
        }
        QComboBox:hover {
            border-color: rgba(0, 120, 212, 160);
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
            background-color: #10101e;
            color: white;
            selection-background-color: rgba(0, 120, 212, 180);
            border: 1px solid rgba(255, 255, 255, 10);
            border-radius: 8px;
            outline: none;
        }
        QScrollBar:vertical {
            background-color: transparent;
            width: 6px;
            margin: 2px;
        }
        QScrollBar::handle:vertical {
            background-color: rgba(255, 255, 255, 18);
            border-radius: 3px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: rgba(255, 255, 255, 32);
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar:horizontal {
            height: 0;
        }
        QToolTip {
            background-color: rgba(14, 14, 28, 245);
            color: #ddd;
            border: 1px solid rgba(255, 255, 255, 14);
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 12px;
        }
        QMessageBox {
            background-color: #12121e;
        }
        QMessageBox QLabel {
            color: white;
        }
        QToolTip {
            background-color: #1a1a2e;
            color: #e0e0e0;
            border: 1px solid #3a3a5a;
            border-radius: 5px;
            padding: 5px 8px;
            font-size: 12px;
        }
    """.replace("ARROW_DOWN_PATH", _arrow_down))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MF IPTV Player")
    app.setOrganizationName("IPTVApp")
    app.setDesktopFileName("iptv-player")

    _fonts_dir = os.path.join(_base_path(), "assets", "fonts")
    for _fname in ("FiraSans-Regular.ttf", "FiraSans-Medium.ttf",
                   "FiraSans-SemiBold.ttf", "FiraSans-Bold.ttf"):
        QFontDatabase.addApplicationFont(os.path.join(_fonts_dir, _fname))

    font = QFont("Fira Sans", 10)
    font.setWeight(QFont.Medium)
    app.setFont(font)

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

    # Sprache laden und Translator installieren (vor MainWindow-Erstellung)
    _lang = AppSettings().get("language", "de")
    _translator = QTranslator(app)
    if _lang != "de":
        _qm_path = os.path.join(_base_path(), "assets", "translations", f"app_{_lang}.qm")
        if _translator.load(_qm_path):
            app.installTranslator(_translator)

    _cursor_filter = _HandCursorFilter(app)
    app.installEventFilter(_cursor_filter)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
