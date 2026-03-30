"""
Event card widgets für den Live-Events Tab.
DuelCardWidget: Team A vs Team B mit Stadion, Schiedsrichter, News, Sender.
EventCardWidget: Allgemeines Event (F1, Tennis, Golf) mit Ort, News, Sender.
"""
import time
import webbrowser
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)

from xtream_api import LiveStream

SPORT_ICONS = {
    "football":   "⚽",
    "formula1":   "🏎",
    "tennis":     "🎾",
    "basketball": "🏀",
    "motorsport": "🏍",
    "golf":       "⛳",
    "rugby":      "🏉",
    "hockey":     "🏒",
    "boxing":     "🥊",
    "sport":      "🏆",
}

# ── Styling ───────────────────────────────────────────────────────────────────

CARD_STYLE = """
    QFrame#eventCard {
        background: #12121e;
        border: 1px solid #1e1e2e;
        border-radius: 12px;
    }
    QFrame#eventCard:hover {
        border-color: #2a2a4a;
    }
"""

DIVIDER_STYLE = "background: #1e1e2e; min-width: 1px; max-width: 1px;"

LIVE_BADGE_STYLE = """
    QPushButton {
        background: #c0392b;
        color: white;
        font-size: 10px;
        font-weight: bold;
        border-radius: 8px;
        padding: 2px 8px;
        border: none;
    }
"""

SOON_BADGE_STYLE = """
    QLabel {
        background: #1a3a1a;
        color: #4caf50;
        font-size: 10px;
        font-weight: bold;
        border-radius: 8px;
        padding: 2px 8px;
    }
"""

STREAM_BTN_STYLE = """
    QPushButton {
        background: #1a1a2e;
        color: #ccc;
        font-size: 11px;
        border: 1px solid #2a2a4a;
        border-radius: 6px;
        padding: 3px 10px;
    }
    QPushButton:hover {
        background: #e8691a;
        color: white;
        border-color: #e8691a;
    }
"""

QUALITY_COLORS = {4: "#f1c40f", 3: "#3498db", 2: "#27ae60", 1: "#7f8c8d", 0: "#7f8c8d"}
QUALITY_LABELS = {4: "4K", 3: "FHD", 2: "HD", 1: "SD", 0: ""}

NEWS_ITEM_STYLE = """
    QLabel {
        color: #aaa;
        font-size: 12px;
        padding: 4px 0;
    }
    QLabel:hover {
        color: #e8691a;
    }
"""

# ── Base card ─────────────────────────────────────────────────────────────────

class _BaseCardWidget(QFrame):

    play_requested = Signal(object)  # LiveStream

    def __init__(self, event, parent=None):
        super().__init__(parent)
        self.event = event
        self.setObjectName("eventCard")
        self.setStyleSheet(CARD_STYLE)
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(0)

        # Linke Hälfte (60%)
        self._left = QWidget()
        self._left.setStyleSheet("background: transparent;")
        self._left_layout = QVBoxLayout(self._left)
        self._left_layout.setContentsMargins(0, 0, 16, 0)
        self._left_layout.setSpacing(8)
        outer.addWidget(self._left, stretch=6)

        # Trennlinie
        divider = QWidget()
        divider.setStyleSheet(DIVIDER_STYLE)
        divider.setFixedWidth(1)
        outer.addWidget(divider)

        # Rechte Hälfte (40%) — News
        self._right = QWidget()
        self._right.setStyleSheet("background: transparent;")
        self._right_layout = QVBoxLayout(self._right)
        self._right_layout.setContentsMargins(16, 0, 0, 0)
        self._right_layout.setSpacing(4)
        outer.addWidget(self._right, stretch=4)

        self._build_left()
        self._build_right()

    def _build_left(self):
        raise NotImplementedError

    def _build_right(self):
        """News-Spalte aufbauen."""
        news_header = QLabel("📰 News")
        news_header.setStyleSheet("color: #555; font-size: 11px; font-weight: bold; background: transparent;")
        self._right_layout.addWidget(news_header)

        if self.event.news:
            for item in self.event.news[:5]:
                lbl = _ClickableLabel(item.title, item.url)
                lbl.setWordWrap(True)
                lbl.setStyleSheet(NEWS_ITEM_STYLE)
                self._right_layout.addWidget(lbl)
        else:
            no_news = QLabel("Keine News verfügbar")
            no_news.setStyleSheet("color: #333; font-size: 12px; font-style: italic; background: transparent;")
            self._right_layout.addWidget(no_news)

        self._right_layout.addStretch()

    def _make_header_row(self) -> QWidget:
        """Erstellt die Kopfzeile mit Sportart-Icon, Zeitstempel und Live-Badge."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        icon = SPORT_ICONS.get(self.event.sport_type, "🏆")
        sport_lbl = QLabel(f"{icon}  {self.event.sport_type.replace('formula1', 'Formel 1').replace('football', 'Fußball').replace('basketball', 'Basketball').replace('tennis', 'Tennis').replace('motorsport', 'Motorsport').replace('golf', 'Golf').replace('rugby', 'Rugby').replace('hockey', 'Hockey').replace('boxing', 'Boxen').replace('sport', 'Sport')}")
        sport_lbl.setStyleSheet("color: #666; font-size: 11px; font-weight: bold; background: transparent;")
        layout.addWidget(sport_lbl)

        time_str = datetime.fromtimestamp(self.event.start_timestamp).strftime("%H:%M")
        end_str = datetime.fromtimestamp(self.event.stop_timestamp).strftime("%H:%M")
        time_lbl = QLabel(f"{time_str} – {end_str}")
        time_lbl.setStyleSheet("color: #555; font-size: 11px; background: transparent;")
        layout.addWidget(time_lbl)

        layout.addStretch()

        if self.event.is_live:
            badge = QPushButton("● LIVE")
            badge.setStyleSheet(LIVE_BADGE_STYLE)
            badge.setEnabled(False)
            badge.setFixedHeight(20)
            layout.addWidget(badge)
            # Blinken via Timer
            self._live_visible = True
            self._blink_timer = QTimer(self)
            self._blink_timer.timeout.connect(self._blink_live)
            self._blink_timer.start(800)
            self._live_badge = badge
        else:
            secs = self.event.starts_in_seconds
            if secs > 0:
                hours = int(secs // 3600)
                mins = int((secs % 3600) // 60)
                if hours > 0:
                    soon_text = f"in {hours}h {mins}m"
                else:
                    soon_text = f"in {mins} Min"
                soon = QLabel(f"⏰ {soon_text}")
                soon.setStyleSheet(SOON_BADGE_STYLE)
                layout.addWidget(soon)

        return row

    def _blink_live(self):
        self._live_visible = not self._live_visible
        self._live_badge.setVisible(self._live_visible)

    def _make_stream_buttons(self) -> QWidget:
        """Erstellt die Sender-Buttons mit Qualitätsbadge."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for ss in self.event.streams[:4]:
            quality_label = QUALITY_LABELS.get(ss.quality, "")
            quality_color = QUALITY_COLORS.get(ss.quality, "#7f8c8d")
            btn_text = ss.clean_name
            if quality_label:
                btn_text += f"  [{quality_label}]"

            btn = QPushButton(btn_text)
            btn.setStyleSheet(STREAM_BTN_STYLE)

            # Qualitäts-Akzentfarbe im Border
            btn.setStyleSheet(STREAM_BTN_STYLE + f"""
                QPushButton {{ border-top: 2px solid {quality_color}; }}
            """)
            btn.clicked.connect(lambda checked=False, s=ss.stream: self.play_requested.emit(s))
            layout.addWidget(btn)

        layout.addStretch()
        return row


# ── Duell-Karte ───────────────────────────────────────────────────────────────

class DuelCardWidget(_BaseCardWidget):

    def _build_left(self):
        # Header: Sportart + Zeit + Live-Badge
        self._left_layout.addWidget(self._make_header_row())

        # Teams
        teams_row = QWidget()
        teams_row.setStyleSheet("background: transparent;")
        teams_layout = QHBoxLayout(teams_row)
        teams_layout.setContentsMargins(0, 4, 0, 4)
        teams_layout.setSpacing(12)

        team_a = QLabel(self.event.team_a)
        team_a.setStyleSheet("color: #fff; font-size: 18px; font-weight: bold; background: transparent;")
        team_a.setWordWrap(True)
        teams_layout.addWidget(team_a, stretch=4)

        vs = QLabel("vs")
        vs.setStyleSheet("color: #e8691a; font-size: 14px; font-weight: bold; background: transparent;")
        vs.setAlignment(Qt.AlignCenter)
        teams_layout.addWidget(vs, stretch=1)

        team_b = QLabel(self.event.team_b)
        team_b.setStyleSheet("color: #fff; font-size: 18px; font-weight: bold; background: transparent;")
        team_b.setWordWrap(True)
        teams_layout.addWidget(team_b, stretch=4)

        self._left_layout.addWidget(teams_row)

        # Meta-Info: Stadion + Schiedsrichter
        if self.event.venue:
            venue_lbl = QLabel(f"🏟  {self.event.venue}")
            venue_lbl.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
            venue_lbl.setWordWrap(True)
            self._left_layout.addWidget(venue_lbl)

        if self.event.referee:
            ref_lbl = QLabel(f"👨‍⚖️  {self.event.referee}")
            ref_lbl.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
            self._left_layout.addWidget(ref_lbl)

        self._left_layout.addStretch()

        # Sender-Buttons
        self._left_layout.addWidget(self._make_stream_buttons())


# ── Event-Karte ───────────────────────────────────────────────────────────────

class EventCardWidget(_BaseCardWidget):

    def _build_left(self):
        # Header: Sportart + Zeit + Live-Badge
        self._left_layout.addWidget(self._make_header_row())

        # Event-Titel
        title_lbl = QLabel(self.event.title)
        title_lbl.setStyleSheet("color: #fff; font-size: 18px; font-weight: bold; background: transparent;")
        title_lbl.setWordWrap(True)
        self._left_layout.addWidget(title_lbl)

        # Ort
        if self.event.venue:
            venue_lbl = QLabel(f"🏟  {self.event.venue}")
            venue_lbl.setStyleSheet("color: #666; font-size: 12px; background: transparent;")
            venue_lbl.setWordWrap(True)
            self._left_layout.addWidget(venue_lbl)

        self._left_layout.addStretch()

        # Sender-Buttons
        self._left_layout.addWidget(self._make_stream_buttons())


# ── Hilfwidgets ───────────────────────────────────────────────────────────────

class _ClickableLabel(QLabel):
    """QLabel das bei Klick eine URL im Browser öffnet."""

    def __init__(self, text: str, url: str, parent=None):
        super().__init__(text, parent)
        self._url = url
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet(NEWS_ITEM_STYLE)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._url:
            webbrowser.open(self._url)
        super().mousePressEvent(event)
