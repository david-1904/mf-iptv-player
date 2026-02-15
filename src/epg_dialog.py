"""
EPG Detail Dialog
"""
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget,
    QPushButton, QHBoxLayout, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, QTimer

from xtream_api import EpgEntry


class EpgDialog(QDialog):
    """Dialog mit vollstaendigem Programmueberblick"""

    def __init__(self, channel_name: str, epg_data: list[EpgEntry], has_catchup: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Programm - {channel_name}")
        self.setMinimumSize(520, 500)
        self.resize(600, 700)
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
                color: white;
            }
        """)
        self._has_catchup = has_catchup
        self.selected_catchup_entry: EpgEntry | None = None
        self._setup_ui(channel_name, epg_data)

    def _setup_ui(self, channel_name: str, epg_data: list[EpgEntry]):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("background-color: #0d0d14; border-bottom: 1px solid #1a1a2a;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)

        title = QLabel(channel_name)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0078d4;")
        header_layout.addWidget(title)

        if self._has_catchup:
            catchup_badge = QLabel("\u25C2\u25C2 Catchup")
            catchup_badge.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #0078d4;
                background-color: #0a2a4a; padding: 3px 10px; border-radius: 8px;
                border: 1px solid #0078d4;
            """)
            header_layout.addWidget(catchup_badge)

        header_layout.addStretch()

        btn_close = QPushButton("\u2715")
        btn_close.setFixedSize(32, 32)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888;
                border: none;
                border-radius: 16px;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #2a2a3a; color: white; }
        """)
        btn_close.clicked.connect(self.accept)
        header_layout.addWidget(btn_close)
        layout.addWidget(header)

        # Scrollbarer Programmbereich
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #121212; }
            QScrollBar:vertical {
                background: #121212;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        now = datetime.now().timestamp()

        scroll_target = None

        if not epg_data:
            empty = QLabel("Keine Programmdaten verfuegbar")
            empty.setStyleSheet("color: #666; padding: 40px; font-size: 14px;")
            empty.setAlignment(Qt.AlignCenter)
            content_layout.addWidget(empty)
        else:
            for entry in epg_data:
                is_current = entry.start_timestamp <= now <= entry.stop_timestamp
                is_future = entry.start_timestamp > now
                row = self._create_program_row(entry, now)
                content_layout.addWidget(row)
                if is_current:
                    scroll_target = row
                elif is_future and scroll_target is None:
                    scroll_target = row

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        if scroll_target is not None:
            target = scroll_target
            QTimer.singleShot(0, lambda: scroll.ensureWidgetVisible(target))

    def _create_program_row(self, entry: EpgEntry, now: float) -> QWidget:
        """Erstellt eine Programmzeile"""
        is_current = entry.start_timestamp <= now <= entry.stop_timestamp
        is_past = entry.stop_timestamp < now

        row = QFrame()
        row.setObjectName("epgRow")
        if is_current:
            row.setStyleSheet("""
                #epgRow { background-color: #0f1f30; border-left: 3px solid #0078d4; border-bottom: 1px solid #1a2a3a; }
            """)
        elif is_past:
            row.setStyleSheet("""
                #epgRow { background-color: #121212; border-bottom: 1px solid #1a1a2a; }
            """)
        else:
            row.setStyleSheet("""
                #epgRow { background-color: #121212; border-bottom: 1px solid #1a1a2a; }
            """)

        layout = QVBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # Kopfzeile: Zeit + Titel + Badges/Buttons
        title_line = QHBoxLayout()
        title_line.setSpacing(10)

        # Zeit
        start = datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M")
        end = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
        time_color = '#0078d4' if is_current else '#666' if is_past else '#999'
        time_label = QLabel(f"{start} – {end}")
        time_label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {time_color};")
        time_label.setFixedWidth(100)
        title_line.addWidget(time_label)

        # Titel
        title_label = QLabel(entry.title)
        weight = "bold" if is_current else "normal"
        size = "14px" if is_current else "13px"
        title_color = "white" if is_current else "#555" if is_past else "#ccc"
        title_label.setStyleSheet(f"font-size: {size}; font-weight: {weight}; color: {title_color};")
        title_label.setWordWrap(True)
        title_line.addWidget(title_label, stretch=1)

        if is_current:
            badge = QLabel("JETZT")
            badge.setStyleSheet("""
                font-size: 9px; font-weight: bold; color: white;
                background-color: #0078d4; padding: 2px 8px; border-radius: 3px;
            """)
            badge.setFixedHeight(20)
            title_line.addWidget(badge)

        # Catchup-Button
        if self._has_catchup and (is_past or is_current):
            btn_play = QPushButton("\u25B6 " + ("Von Anfang" if is_current else "Abspielen"))
            btn_play.setFixedHeight(28)
            btn_play.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #0078d4;
                    border: 1px solid #0078d4; border-radius: 6px;
                    font-size: 11px; padding: 2px 12px;
                }
                QPushButton:hover { background-color: #0078d4; color: white; }
            """)
            btn_play.clicked.connect(lambda checked=False, e=entry: self._on_catchup_clicked(e))
            title_line.addWidget(btn_play)

        layout.addLayout(title_line)

        # Fortschrittsbalken fuer aktuelle Sendung
        if is_current:
            duration = entry.stop_timestamp - entry.start_timestamp
            if duration > 0:
                elapsed = now - entry.start_timestamp
                progress = max(0, min(100, int(elapsed / duration * 100)))
                bar = QProgressBar()
                bar.setFixedHeight(3)
                bar.setTextVisible(False)
                bar.setValue(progress)
                bar.setStyleSheet("""
                    QProgressBar { background: #1a3a5a; border: none; border-radius: 1px; }
                    QProgressBar::chunk { background: #0078d4; border-radius: 1px; }
                """)
                layout.addWidget(bar)

        # Beschreibung
        desc = entry.description.strip() if entry.description else ""
        if desc:
            desc_label = QLabel(desc)
            desc_color = '#aaa' if is_current else '#666' if is_past else '#888'
            desc_label.setStyleSheet(f"font-size: 11px; color: {desc_color}; padding-left: 110px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        return row

    def _on_catchup_clicked(self, entry: EpgEntry):
        self.selected_catchup_entry = entry
        self.accept()
