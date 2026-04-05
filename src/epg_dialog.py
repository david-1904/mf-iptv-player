"""
EPG Detail Dialog
"""
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget,
    QPushButton, QHBoxLayout, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QSize

from xtream_api import EpgEntry
from ui_builder import _pi


class EpgDialog(QDialog):
    """Dialog mit vollstaendigem Programmueberblick"""

    def __init__(self, channel_name: str, epg_data: list[EpgEntry], has_catchup: bool = False,
                 schedule_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Programm – {channel_name}")
        self.setMinimumSize(540, 520)
        self.resize(620, 720)
        self.setStyleSheet("""
            QDialog { background-color: #0f0f1a; color: white; }
        """)
        self._has_catchup = has_catchup
        self._schedule_callback = schedule_callback
        self.selected_catchup_entry: EpgEntry | None = None
        self._setup_ui(channel_name, epg_data)

    def _setup_ui(self, channel_name: str, epg_data: list[EpgEntry]):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("""
            background-color: #12121f;
            border-bottom: 1px solid #1e1e30;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 16, 14)
        header_layout.setSpacing(10)

        title = QLabel(channel_name)
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: white;")
        header_layout.addWidget(title)

        if self._has_catchup:
            catchup_badge = QLabel("◀◀  Catchup")
            catchup_badge.setStyleSheet("""
                font-size: 10px; font-weight: bold; color: #0078d4;
                background-color: rgba(0,120,212,0.12); padding: 3px 10px;
                border-radius: 8px; border: 1px solid rgba(0,120,212,0.4);
            """)
            header_layout.addWidget(catchup_badge)

        header_layout.addStretch()

        btn_close = QPushButton()
        btn_close.setIcon(_pi("x.svg", 16))
        btn_close.setIconSize(QSize(16, 16))
        btn_close.setFixedSize(32, 32)
        btn_close.setToolTip("Schließen")
        btn_close.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 6px; }
            QPushButton:hover { background-color: #2a2a3a; }
        """)
        btn_close.clicked.connect(self.accept)
        header_layout.addWidget(btn_close)
        layout.addWidget(header)

        # Scrollbarer Programmbereich
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #0f0f1a; }
            QScrollBar:vertical { background: #0f0f1a; width: 6px; }
            QScrollBar::handle:vertical {
                background: #2a2a3a; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 16)
        content_layout.setSpacing(0)

        now = datetime.now().timestamp()
        scroll_target = None
        last_date = None

        if not epg_data:
            empty = QLabel("Keine Programmdaten verfügbar")
            empty.setStyleSheet("color: #555; padding: 48px; font-size: 14px;")
            empty.setAlignment(Qt.AlignCenter)
            content_layout.addWidget(empty)
        else:
            for entry in epg_data:
                is_current = entry.start_timestamp <= now < entry.stop_timestamp
                is_future = entry.start_timestamp > now

                # Datums-Trennzeile wenn Tag wechselt
                entry_date = datetime.fromtimestamp(entry.start_timestamp).date()
                if entry_date != last_date:
                    last_date = entry_date
                    today = datetime.now().date()
                    if entry_date == today:
                        day_str = "Heute"
                    elif (entry_date - today).days == 1:
                        day_str = "Morgen"
                    elif (entry_date - today).days == -1:
                        day_str = "Gestern"
                    else:
                        day_str = entry_date.strftime("%A, %d. %B")
                    sep = self._create_date_separator(day_str)
                    content_layout.addWidget(sep)

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

    def _create_date_separator(self, day_str: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 4)
        lay.setSpacing(10)

        line_l = QFrame()
        line_l.setFrameShape(QFrame.HLine)
        line_l.setStyleSheet("color: #1e1e30;")

        lbl = QLabel(day_str)
        lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #444; text-transform: uppercase;")
        lbl.setFixedWidth(lbl.sizeHint().width() + 8)

        line_r = QFrame()
        line_r.setFrameShape(QFrame.HLine)
        line_r.setStyleSheet("color: #1e1e30;")

        lay.addWidget(line_l, stretch=1)
        lay.addWidget(lbl)
        lay.addWidget(line_r, stretch=3)
        return w

    def _create_program_row(self, entry: EpgEntry, now: float) -> QFrame:
        """Erstellt eine Programmzeile"""
        is_current = entry.start_timestamp <= now < entry.stop_timestamp
        is_past    = entry.stop_timestamp <= now

        row = QFrame()
        row.setObjectName("epgRow")

        if is_current:
            row.setStyleSheet("""
                #epgRow {
                    background-color: #16202c;
                    border-left: 3px solid #e8691a;
                    border-bottom: 1px solid #1e2a38;
                }
                #epgRow:hover { background-color: #1c2a3a; }
            """)
        elif is_past:
            row.setStyleSheet("""
                #epgRow {
                    background-color: transparent;
                    border-left: 3px solid transparent;
                    border-bottom: 1px solid #161626;
                }
                #epgRow:hover { background-color: #141420; }
            """)
        else:
            row.setStyleSheet("""
                #epgRow {
                    background-color: transparent;
                    border-left: 3px solid transparent;
                    border-bottom: 1px solid #161626;
                }
                #epgRow:hover { background-color: #14141e; }
            """)

        layout = QVBoxLayout(row)
        layout.setContentsMargins(16, 11, 14, 11)
        layout.setSpacing(5)

        # Kopfzeile: Zeit + Titel + Badges/Buttons
        title_line = QHBoxLayout()
        title_line.setSpacing(10)

        # Zeit
        start = datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M")
        end   = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
        time_color = '#e8691a' if is_current else '#383850' if is_past else '#555'
        time_label = QLabel(f"{start}")
        time_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {time_color};")
        time_label.setFixedWidth(44)
        title_line.addWidget(time_label)

        end_label = QLabel(f"– {end}")
        end_label.setStyleSheet(f"font-size: 12px; color: {time_color}; opacity: 0.7;")
        end_label.setFixedWidth(52)
        title_line.addWidget(end_label)

        # Titel
        weight = "600" if is_current else "normal"
        size   = "14px" if is_current else "13px"
        title_color = "white" if is_current else "#303044" if is_past else "#bbb"
        title_label = QLabel(entry.title)
        title_label.setStyleSheet(f"font-size: {size}; font-weight: {weight}; color: {title_color};")
        title_label.setWordWrap(True)
        title_line.addWidget(title_label, stretch=1)

        # JETZT-Badge
        if is_current:
            badge = QLabel("JETZT")
            badge.setStyleSheet("""
                font-size: 9px; font-weight: bold; color: white;
                background-color: #e8691a; padding: 2px 8px; border-radius: 3px;
            """)
            badge.setFixedHeight(18)
            title_line.addWidget(badge)

        # Catchup-Button
        if self._has_catchup and (is_past or is_current):
            btn_play = QPushButton()
            btn_play.setIcon(_pi("play.svg", 13))
            btn_play.setIconSize(QSize(13, 13))
            btn_play.setText("  " + ("Von Anfang" if is_current else "Abspielen"))
            btn_play.setFixedHeight(28)
            btn_play.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #0078d4;
                    border: 1px solid rgba(0,120,212,0.4); border-radius: 6px;
                    font-size: 11px; padding: 2px 10px;
                }
                QPushButton:hover { background-color: #0078d4; color: white; border-color: #0078d4; }
            """)
            btn_play.clicked.connect(lambda checked=False, e=entry: self._on_catchup_clicked(e))
            title_line.addWidget(btn_play)

        # Aufnahme-Button
        if self._schedule_callback and (is_current or not is_past):
            btn_rec = QPushButton()
            btn_rec.setIcon(_pi("record.svg", 14))
            btn_rec.setIconSize(QSize(14, 14))
            btn_rec.setToolTip("Aufnahme planen")
            btn_rec.setFixedSize(28, 28)
            btn_rec.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #2a2a3a; border-radius: 5px;
                    padding: 0;
                }
                QPushButton:hover { background: #c0392b; border-color: #c0392b; }
            """)
            btn_rec.clicked.connect(lambda checked=False, e=entry: self._schedule_callback(e))
            title_line.addWidget(btn_rec)

        layout.addLayout(title_line)

        # Fortschrittsbalken für aktuelle Sendung
        if is_current:
            duration = entry.stop_timestamp - entry.start_timestamp
            if duration > 0:
                elapsed  = now - entry.start_timestamp
                progress = max(0, min(100, int(elapsed / duration * 100)))
                bar = QProgressBar()
                bar.setFixedHeight(2)
                bar.setTextVisible(False)
                bar.setValue(progress)
                bar.setStyleSheet("""
                    QProgressBar { background: rgba(232,105,26,0.15); border: none; border-radius: 1px; }
                    QProgressBar::chunk { background: #e8691a; border-radius: 1px; }
                """)
                layout.addWidget(bar)

        # Beschreibung
        desc = entry.description.strip() if entry.description else ""
        if desc:
            desc_color = '#888' if is_current else '#2a2a38' if is_past else '#555'
            desc_label = QLabel(desc)
            desc_label.setStyleSheet(
                f"font-size: 11px; color: {desc_color}; padding-left: 100px; padding-top: 1px;"
            )
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        return row

    def _on_catchup_clicked(self, entry: EpgEntry):
        self.selected_catchup_entry = entry
        self.accept()
