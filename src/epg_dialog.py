"""
EPG Detail Dialog
"""
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget,
    QPushButton, QHBoxLayout, QFrame, QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve

from xtream_api import EpgEntry
from ui_builder import _pi
from i18n import _tr


class EpgDialog(QDialog):
    """Dialog mit vollstaendigem Programmueberblick"""

    def __init__(self, channel_name: str, epg_data: list[EpgEntry], has_catchup: bool = False,
                 schedule_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Programm \u2013 {}").format(channel_name))
        self.setMinimumSize(600, 580)
        self.resize(660, 760)
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
            catchup_badge = QLabel(_tr("◀◀  Catchup"))
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
        btn_close.setToolTip(_tr("Schließen"))
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

        # Bei überlappenden Einträgen nur den mit dem spätesten Start als "aktuell" markieren
        current_ts = None
        for entry in epg_data:
            if entry.start_timestamp <= now < entry.stop_timestamp:
                if current_ts is None or entry.start_timestamp > current_ts:
                    current_ts = entry.start_timestamp

        if not epg_data:
            empty = QLabel(_tr("Keine Programmdaten verfügbar"))
            empty.setStyleSheet("color: #555; padding: 48px; font-size: 14px;")
            empty.setAlignment(Qt.AlignCenter)
            content_layout.addWidget(empty)
        else:
            for entry in epg_data:
                is_current = (current_ts is not None and entry.start_timestamp == current_ts)
                is_future = entry.start_timestamp > now

                # Datums-Trennzeile wenn Tag wechselt
                entry_date = datetime.fromtimestamp(entry.start_timestamp).date()
                if entry_date != last_date:
                    last_date = entry_date
                    today = datetime.now().date()
                    if entry_date == today:
                        day_str = _tr("Heute")
                    elif (entry_date - today).days == 1:
                        day_str = _tr("Morgen")
                    elif (entry_date - today).days == -1:
                        day_str = _tr("Gestern")
                    else:
                        day_str = entry_date.strftime("%A, %d. %B")
                    sep = self._create_date_separator(day_str)
                    content_layout.addWidget(sep)

                row = self._create_program_row(entry, now, is_current)
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
        lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #666; text-transform: uppercase;")
        lbl.setFixedWidth(lbl.sizeHint().width() + 8)

        line_r = QFrame()
        line_r.setFrameShape(QFrame.HLine)
        line_r.setStyleSheet("color: #1e1e30;")

        lay.addWidget(line_l, stretch=1)
        lay.addWidget(lbl)
        lay.addWidget(line_r, stretch=3)
        return w

    def _create_program_row(self, entry: EpgEntry, now: float, is_current: bool = False) -> QFrame:
        """Erstellt eine kompakte Programmzeile mit ausklappbarer Beschreibung."""
        is_past = entry.stop_timestamp <= now

        row = QFrame()
        row.setObjectName("epgRow")

        if is_current:
            row.setStyleSheet("""
                #epgRow { background-color: #16202c; border-left: 3px solid #e8691a; border-bottom: 1px solid #1e2a38; }
                #epgRow:hover { background-color: #1c2a3a; }
            """)
        elif is_past:
            row.setStyleSheet("""
                #epgRow { background-color: transparent; border-left: 3px solid transparent; border-bottom: 1px solid #161626; }
                #epgRow:hover { background-color: #141420; }
            """)
        else:
            row.setStyleSheet("""
                #epgRow { background-color: transparent; border-left: 3px solid transparent; border-bottom: 1px solid #161626; }
                #epgRow:hover { background-color: #14141e; }
            """)

        outer = QVBoxLayout(row)
        outer.setContentsMargins(16, 0, 14, 0)
        outer.setSpacing(0)

        # ── Hauptzeile (feste Höhe) ───────────────────────────
        main_line = QWidget()
        main_line.setFixedHeight(44)
        main_line.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(main_line)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)

        # Zeit als einzelnes Label
        start = datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M")
        end   = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
        time_color = '#e8691a' if is_current else '#484860' if is_past else '#666'
        time_label = QLabel(f"{start} – {end}")
        time_label.setStyleSheet(f"font-size: 13px; font-weight: 500; color: {time_color};")
        time_label.setFixedWidth(112)
        hl.addWidget(time_label)

        # Fortschrittsbalken für aktuelle Sendung (vertikal zentriert, schmal)
        if is_current:
            duration = entry.stop_timestamp - entry.start_timestamp
            if duration > 0:
                elapsed = now - entry.start_timestamp
                progress = max(0, min(100, int(elapsed / duration * 100)))
                bar = QProgressBar()
                bar.setFixedSize(3, 28)
                bar.setOrientation(Qt.Vertical)
                bar.setTextVisible(False)
                bar.setValue(progress)
                bar.setStyleSheet("""
                    QProgressBar { background: rgba(232,105,26,0.2); border: none; border-radius: 1px; }
                    QProgressBar::chunk { background: #e8691a; border-radius: 1px; }
                """)
                hl.addWidget(bar)

        # Titel
        weight = "600" if is_current else "normal"
        title_color = "white" if is_current else "#5a5a75" if is_past else "#ccc"
        title_label = QLabel(entry.title)
        title_label.setStyleSheet(f"font-size: 14px; font-weight: {weight}; color: {title_color};")
        title_label.setWordWrap(False)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        hl.addWidget(title_label, stretch=1)

        # JETZT-Badge
        if is_current:
            badge = QLabel(_tr("JETZT"))
            badge.setStyleSheet("""
                font-size: 9px; font-weight: bold; color: white;
                background-color: #e8691a; padding: 2px 8px; border-radius: 3px;
            """)
            badge.setFixedHeight(18)
            hl.addWidget(badge)

        # Catchup-Button
        if self._has_catchup and (is_past or is_current):
            btn_play = QPushButton()
            btn_play.setIcon(_pi("play.svg", 14))
            btn_play.setIconSize(QSize(14, 14))
            btn_play.setFixedSize(28, 28)
            btn_play.setToolTip(_tr("Von Anfang abspielen") if is_current else _tr("Abspielen"))
            btn_play.setStyleSheet("""
                QPushButton { background: transparent; border: 1px solid rgba(0,120,212,0.4); border-radius: 6px; }
                QPushButton:hover { background-color: #0078d4; border-color: #0078d4; }
            """)
            btn_play.clicked.connect(lambda checked=False, e=entry: self._on_catchup_clicked(e))
            hl.addWidget(btn_play)

        # Aufnahme-Button
        if self._schedule_callback and (is_current or not is_past):
            btn_rec = QPushButton()
            btn_rec.setIcon(_pi("record.svg", 14))
            btn_rec.setIconSize(QSize(14, 14))
            btn_rec.setToolTip(_tr("Aufnahme planen"))
            btn_rec.setFixedSize(28, 28)
            btn_rec.setStyleSheet("""
                QPushButton { background: transparent; border: 1px solid #2a2a3a; border-radius: 5px; }
                QPushButton:hover { background: #c0392b; border-color: #c0392b; }
            """)
            btn_rec.clicked.connect(lambda checked=False, e=entry: self._schedule_callback(e))
            hl.addWidget(btn_rec)

        # Expand-Button (nur wenn Beschreibung vorhanden)
        desc = entry.description.strip() if entry.description else ""
        if desc:
            btn_expand = QPushButton()
            btn_expand.setIcon(_pi("chevron-right.svg", 14, rotate=90))
            btn_expand.setIconSize(QSize(14, 14))
            btn_expand.setFixedSize(24, 24)
            btn_expand.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 4px; padding: 4px; }"
                "QPushButton:hover { background-color: rgba(255,255,255,10); }"
            )
            hl.addWidget(btn_expand)
        else:
            btn_expand = None

        outer.addWidget(main_line)

        # ── Beschreibungs-Bereich (ausgeklappt = sichtbar) ───
        if desc:
            desc_widget = QLabel(desc)
            desc_color = '#888' if is_current else '#555570' if is_past else '#777'
            desc_widget.setStyleSheet(
                f"font-size: 13px; color: {desc_color}; padding: 0 0 10px 114px;"
            )
            desc_widget.setWordWrap(True)
            desc_widget.hide()
            outer.addWidget(desc_widget)

            _expanded = [False]
            def _toggle(checked=False, dw=desc_widget, btn=btn_expand, state=_expanded):
                state[0] = not state[0]
                dw.setVisible(state[0])
                btn.setIcon(_pi("chevron-right.svg", 14, rotate=-90 if state[0] else 90))

            btn_expand.clicked.connect(_toggle)

        return row

    def _on_catchup_clicked(self, entry: EpgEntry):
        self.selected_catchup_entry = entry
        self.accept()
