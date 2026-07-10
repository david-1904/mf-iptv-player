"""
UI-Erstellung: Alle _create_* Methoden und Layout-Setup
"""
import asyncio
import os
import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem, QComboBox,
    QPushButton, QLineEdit, QLabel, QSlider,
    QFrame, QStatusBar, QGroupBox, QScrollArea, QSplitter,
    QProgressBar, QAbstractItemView, QScroller, QMenu, QTextEdit,
    QSizePolicy, QStyledItemDelegate
)
from PySide6.QtCore import Qt, QSize, Slot, QTimer, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QFont, QPainter, QPainterPath, QColor, QIcon
from PySide6.QtSvg import QSvgRenderer

from flow_layout import FlowLayout
from i18n import _tr

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")


def _svg_icon(name: str, size: int = 17, bright: bool = False,
              active_color: str = "#ffffff", right_pad: int = 0,
              rotate: int = 0) -> QIcon:
    """Load a Lucide SVG and return a QIcon with dim (Off) and bright (On/Active) states.

    bright=True  → off-state is #c0c0c8 instead of #707080 (for player controls on black bg)
    active_color → color for the On/checked state (default white; use #ff4444 for record, etc.)
    right_pad    → transparent pixels added to the right of the icon (icon-text spacing hack)
    """
    path = os.path.join(_ICONS_DIR, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            svg_data = f.read()
    except OSError:
        return QIcon()

    off_color   = "#c0c0c8" if bright else "#707080"
    hover_color = "#ffffff" if bright else "#aaaabb"

    def _render(color: str) -> QPixmap:
        colored = svg_data.replace("currentColor", color)
        renderer = QSvgRenderer(colored.encode())
        # Render at 3× then scale down — eliminates jagged edges on curves at small sizes
        render_size = size * 3
        big = QPixmap(render_size, render_size)
        big.fill(Qt.transparent)
        p = QPainter(big)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if rotate:
            p.translate(render_size / 2, render_size / 2)
            p.rotate(rotate)
            p.translate(-render_size / 2, -render_size / 2)
        renderer.render(p)
        p.end()
        px = big.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if right_pad > 0:
            padded = QPixmap(size + right_pad, size)
            padded.fill(Qt.transparent)
            pp = QPainter(padded)
            pp.drawPixmap(0, 0, px)
            pp.end()
            return padded
        return px

    icon = QIcon()
    icon.addPixmap(_render(off_color),    QIcon.Normal, QIcon.Off)
    icon.addPixmap(_render(hover_color),  QIcon.Active, QIcon.Off)
    icon.addPixmap(_render(active_color), QIcon.Normal, QIcon.On)
    return icon


def _si(name: str) -> QIcon:
    """Shorthand: sidebar icon (16px, with 6px right padding for icon-text spacing)."""
    return _svg_icon(name, size=16, right_pad=6)


def _pi(name: str, size: int = 20, rotate: int = 0) -> QIcon:
    """Shorthand: bright player icon (white active state)."""
    return _svg_icon(name, size, bright=True, rotate=rotate)


def _pi_colored(name: str, size: int, active_color: str) -> QIcon:
    """Bright player icon with a custom active/checked color."""
    return _svg_icon(name, size, bright=True, active_color=active_color)


_CATCHUP_PX: QPixmap | None = None


def _catchup_icon() -> QPixmap:
    global _CATCHUP_PX
    if _CATCHUP_PX is not None:
        return _CATCHUP_PX
    path = os.path.join(_ICONS_DIR, "catchup.svg")
    try:
        with open(path, "r", encoding="utf-8") as f:
            svg = f.read().replace("currentColor", "#8ca0cc")
        renderer = QSvgRenderer(svg.encode())
        size = 16
        big = QPixmap(size * 3, size * 3)
        big.fill(Qt.transparent)
        p = QPainter(big)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        renderer.render(p)
        p.end()
        _CATCHUP_PX = big.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception:
        _CATCHUP_PX = QPixmap()
    return _CATCHUP_PX


# Zentrale Qualitäts-Farben — werden von Delegate (QColor) und EPG-Suche (CSS) genutzt
_QUALITY_HEX = {
    "4K":  ("#d4a017", "#ffffff"),
    "FHD": ("#6a3fa0", "#ffffff"),
    "HD":  ("#0078d4", "#ffffff"),
    "SD":  ("#444444", "#aaaaaa"),
}
_QUALITY_BADGE_COLORS = {
    k: (QColor(bg), QColor(fg)) for k, (bg, fg) in _QUALITY_HEX.items()
}
_AUDIO_BADGE_BG    = QColor(232, 105, 26, 60)
_AUDIO_BADGE_BORDER= QColor(232, 105, 26, 130)
_AUDIO_BADGE_TEXT  = QColor("#e8691a")
_OFFLINE_BADGE_BG  = QColor(180, 40, 40, 80)
_OFFLINE_BADGE_BORDER = QColor(180, 40, 40, 160)
_OFFLINE_BADGE_TEXT   = QColor("#e05555")

# Dot-Indikatoren für Qualität in der Senderliste
_DOT_SIZE = 7
_DOT_AREA_W = 20  # feste Breite der Dot-Spalte
_DOT_QUALITY_COLORS = {k: QColor(bg) for k, (bg, _) in _QUALITY_HEX.items()}
_DOT_OFFLINE_COLOR = QColor("#cc3333")
_DOT_AUDIO_COLOR   = QColor("#e8691a")


def _quality_dot_tooltip(entry: dict) -> str:
    if entry.get("offline"):
        return "Offline"
    parts = []
    q = entry.get("q", "")
    a = entry.get("a", "")
    if q:
        parts.append(q)
    if a:
        parts.append(a)
    return " · ".join(parts)


class ClickSlider(QSlider):
    """QSlider that jumps directly to the clicked position on click."""
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.width() == 0:
                return
            ratio = max(0.0, min(1.0, event.position().x() / self.width()))
            val = self.minimum() + int((self.maximum() - self.minimum()) * ratio)
            self.setValue(val)
            self.sliderReleased.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


class _CatchupDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self._mw = main_window
        self._hovered_row = -1

    def _right_margin(self, stream) -> int:
        """Feste Breite der Icon-Spalte rechts (Catchup + Dots)."""
        margin = 0
        if getattr(stream, 'tv_archive', False):
            px = _catchup_icon()
            if not px.isNull():
                margin += px.width() + 8
        cache = getattr(self._mw, '_stream_quality_cache', {}) if self._mw else {}
        measured = cache.get(str(getattr(stream, 'stream_id', None)))
        if isinstance(measured, dict):
            margin += _DOT_AREA_W
        return margin

    def _draw_quality_dots(self, painter, right_x, center_y, measured):
        from PySide6.QtCore import QRectF
        size = _DOT_SIZE
        gap = 3
        dots = []
        if measured.get("offline"):
            dots = [_DOT_OFFLINE_COLOR]
        else:
            q = measured.get("q", "")
            if q in _DOT_QUALITY_COLORS:
                dots = [_DOT_QUALITY_COLORS[q]]
        if not dots:
            return
        x = right_x - size - 2
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(dots[0])
        painter.drawEllipse(QRectF(x, center_y - size / 2, size, size))
        painter.restore()

    def paint(self, painter, option, index):
        stream = index.data(Qt.UserRole)

        total_margin = self._right_margin(stream) if stream else 0

        if total_margin > 0:
            from PySide6.QtWidgets import QStyleOptionViewItem
            opt = QStyleOptionViewItem(option)
            opt.rect = option.rect.adjusted(0, 0, -total_margin, 0)
            super().paint(painter, opt, index)
        else:
            super().paint(painter, option, index)

        if stream is None:
            return

        right_x = option.rect.right() - 4
        center_y = option.rect.center().y()

        # Catchup-Icon (ganz rechts, immer sichtbar)
        if getattr(stream, 'tv_archive', False):
            px = _catchup_icon()
            if not px.isNull():
                from PySide6.QtCore import QSize
                from PySide6.QtWidgets import QStyle
                icon_rect = QStyle.alignedRect(
                    Qt.LeftToRight, Qt.AlignVCenter | Qt.AlignRight,
                    QSize(px.width(), px.height()),
                    option.rect.adjusted(0, 0, -4, 0),
                )
                painter.save()
                painter.setOpacity(0.7)
                painter.drawPixmap(icon_rect.topLeft(), px)
                painter.restore()
                right_x = icon_rect.left() - 4

        # Qualitäts-Dots (immer sichtbar wenn Daten vorhanden)
        cache = getattr(self._mw, '_stream_quality_cache', {}) if self._mw else {}
        measured = cache.get(str(getattr(stream, 'stream_id', None)))
        if isinstance(measured, dict):
            self._draw_quality_dots(painter, right_x, center_y, measured)


class AnimatedButton(QPushButton):
    """QPushButton mit sanftem Hover-Fade via QVariantAnimation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hover_progress = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, value):
        self._hover_progress = value
        self.update()

    def enterEvent(self, event):
        if not self.isChecked():
            self._anim.stop()
            self._anim.setStartValue(self._hover_progress)
            self._anim.setEndValue(1.0)
            self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_progress)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hover_progress > 0.0 and not self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 7, 7)
            painter.setClipPath(path)
            alpha = int(self._hover_progress * 14)
            painter.fillRect(self.rect(), QColor(255, 255, 255, alpha))


class UiBuilderMixin:

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet("""
            #sidebar {
                background-color: rgba(8, 8, 20, 210);
                border-right: 1px solid rgba(255, 255, 255, 7);
            }
            QPushButton {
                text-align: left;
                padding: 10px 16px;
                margin: 2px 8px;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: #888;
                font-size: 14px;
                font-family: "Fira Sans";
                font-weight: 500;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 120, 212, 55), stop:1 rgba(80, 40, 200, 28));
                border-left: 3px solid #0078d4;
                border-radius: 8px;
                padding-left: 13px;
                color: white;
                font-weight: bold;
            }
            QComboBox {
                padding: 6px 8px;
                margin: 6px 10px;
                background: rgba(255, 255, 255, 5);
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 8px;
                color: white;
                font-size: 12px;
            }
            QComboBox:hover { border-color: rgba(0, 120, 212, 150); }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #10101e;
                color: white;
                selection-background-color: rgba(0, 120, 212, 180);
                border: 1px solid rgba(255, 255, 255, 10);
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Gradient-Akzentlinie oben
        _accent = QFrame()
        _accent.setFixedHeight(3)
        _accent.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0078d4, stop:0.5 #7b40e8, stop:1 transparent);
                border: none;
            }
        """)
        layout.addWidget(_accent)

        # Account-Auswahl
        self.account_combo = QComboBox()
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        layout.addWidget(self.account_combo)

        # Suchfeld (immer sichtbar, oben)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(_tr("🔍 Suche…"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 7px 10px;
                background: rgba(255, 255, 255, 5);
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 8px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: rgba(0, 120, 212, 180);
                background: rgba(0, 120, 212, 8);
            }
        """)
        self.search_input.returnPressed.connect(self._execute_search)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        _search_wrapper = QWidget()
        _sw_layout = QHBoxLayout(_search_wrapper)
        _sw_layout.setContentsMargins(10, 6, 10, 6)
        _sw_layout.setSpacing(0)
        _sw_layout.addWidget(self.search_input)
        layout.addWidget(_search_wrapper)

        # Such-Filter-Chips (nur im Suchmodus sichtbar)
        self.search_filter_row = QWidget()
        self.search_filter_row.setObjectName("searchFilterRow")
        self.search_filter_row.setStyleSheet("""
            #searchFilterRow {
                background: rgba(255,255,255,3);
                border-bottom: 1px solid rgba(255,255,255,6);
            }
            #searchFilterRow QLabel {
                font-size: 11px; color: #666;
            }
            #searchFilterRow QPushButton {
                text-align: center; margin: 0;
                padding: 5px 2px; border-radius: 10px; font-size: 12px;
                background: transparent; border: 1px solid #3a3a50; color: #888;
            }
            #searchFilterRow QPushButton:hover { border-color: #0078d4; color: #ccc; }
            #searchFilterRow QPushButton[active="true"] {
                background: #0078d4; border-color: #0078d4; color: white; font-weight: bold;
            }
            #searchFilterRow QPushButton#btnFilterAll {
                border-color: #505068; color: #aaa;
            }
            #searchFilterRow QPushButton#btnFilterAll[active="true"] {
                background: #0078d4; border-color: #0078d4; color: white;
            }
        """)
        _sf_layout = QHBoxLayout(self.search_filter_row)
        _sf_layout.setContentsMargins(8, 5, 8, 5)
        _sf_layout.setSpacing(4)

        # Vier gleich breite Chips, die die schmale Sidebar-Breite (220px)
        # vollstaendig ausfuellen, damit nichts abgeschnitten wird.
        self._search_filter_buttons = {}
        for label, fkey in [(_tr("Alle"), "all"), (_tr("TV"), "live"), (_tr("Film"), "vod"), (_tr("Serie"), "series")]:
            btn = QPushButton(label)
            btn.setProperty("active", "false")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumWidth(0)
            btn.clicked.connect(lambda checked, k=fkey: self._set_search_filter(k))
            if fkey == "all":
                btn.setObjectName("btnFilterAll")
            _sf_layout.addWidget(btn)
            self._search_filter_buttons[fkey] = btn
        self._search_filter_buttons["all"].setProperty("active", "true")
        self.search_filter_row.hide()
        layout.addWidget(self.search_filter_row)

        def _sep():
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("background-color: rgba(255,255,255,6); margin: 0 10px;")
            return line

        def _section_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("""
                QLabel {
                    color: rgba(255,255,255,70);
                    font-size: 10px;
                    font-weight: bold;
                    letter-spacing: 1.5px;
                    padding: 0 18px;
                    margin: 0;
                }
            """)
            return lbl

        layout.addWidget(_sep())
        layout.addSpacing(10)
        layout.addWidget(_section_label(_tr("INHALTE")))
        layout.addSpacing(4)

        _icon_size = QSize(22, 16)  # 16px icon + 6px right padding via _si()

        # Modus-Buttons
        self.btn_live = AnimatedButton(_tr("Live TV"))
        self.btn_live.setCheckable(True)
        self.btn_live.setChecked(True)
        self.btn_live.setIcon(_si("tv.svg"))
        self.btn_live.setIconSize(_icon_size)
        self.btn_live.clicked.connect(lambda: self._switch_mode("live"))

        self.btn_vod = AnimatedButton(_tr("Filme"))
        self.btn_vod.setCheckable(True)
        self.btn_vod.setIcon(_si("film.svg"))
        self.btn_vod.setIconSize(_icon_size)
        self.btn_vod.clicked.connect(lambda: self._switch_mode("vod"))

        self.btn_series = AnimatedButton(_tr("Serien"))
        self.btn_series.setCheckable(True)
        self.btn_series.setIcon(_si("layers.svg"))
        self.btn_series.setIconSize(_icon_size)
        self.btn_series.clicked.connect(lambda: self._switch_mode("series"))

        layout.addWidget(self.btn_live)
        layout.addWidget(self.btn_vod)
        layout.addWidget(self.btn_series)

        layout.addSpacing(10)
        layout.addWidget(_section_label(_tr("MEINE BIBLIOTHEK")))
        layout.addSpacing(4)

        # Favoriten-Button
        self.btn_favorites = AnimatedButton(_tr("Favoriten"))
        self.btn_favorites.setCheckable(True)
        self.btn_favorites.setIcon(_si("star.svg"))
        self.btn_favorites.setIconSize(_icon_size)
        self.btn_favorites.clicked.connect(lambda: self._switch_mode("favorites"))
        layout.addWidget(self.btn_favorites)

        # Verlauf-Button
        self.btn_history = AnimatedButton(_tr("Verlauf"))
        self.btn_history.setCheckable(True)
        self.btn_history.setIcon(_si("clock.svg"))
        self.btn_history.setIconSize(_icon_size)
        self.btn_history.clicked.connect(lambda: self._switch_mode("history"))
        layout.addWidget(self.btn_history)

        # Aufnahmen-Button
        self.btn_recordings = AnimatedButton(_tr("Aufnahmen"))
        self.btn_recordings.setCheckable(True)
        self.btn_recordings.setIcon(_si("record.svg"))
        self.btn_recordings.setIconSize(_icon_size)
        self.btn_recordings.clicked.connect(lambda: self._switch_mode("recordings"))
        layout.addWidget(self.btn_recordings)

        layout.addSpacing(10)
        layout.addWidget(_section_label(_tr("TOOLS")))
        layout.addSpacing(4)

        # Programm-Suche
        self.btn_epg_search = AnimatedButton(_tr("Programm-Suche"))
        self.btn_epg_search.setCheckable(True)
        self.btn_epg_search.setIcon(_si("calendar.svg"))
        self.btn_epg_search.setIconSize(_icon_size)
        self.btn_epg_search.clicked.connect(lambda: self._switch_mode("epg_search"))
        layout.addWidget(self.btn_epg_search)

        # Aktualisieren-Button
        self.btn_refresh = AnimatedButton(_tr("Aktualisieren"))
        self.btn_refresh.setIcon(_si("refresh.svg"))
        self.btn_refresh.setIconSize(_icon_size)
        self.btn_refresh.clicked.connect(self._refresh_current)
        layout.addWidget(self.btn_refresh)

        # Einstellungen direkt unter Aktualisieren
        self.btn_settings = QPushButton(_tr("Einstellungen"))
        self.btn_settings.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px 16px;
                margin: 2px 8px;
                border: 1px solid transparent;
                border-radius: 8px;
                background: transparent;
                color: #666;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 6);
                border-color: rgba(255, 255, 255, 8);
                color: #aaa;
            }
        """)
        self.btn_settings.setIcon(_si("settings.svg"))
        self.btn_settings.setIconSize(_icon_size)
        self.btn_settings.clicked.connect(self._show_settings)
        layout.addWidget(self.btn_settings)

        # Spacer
        layout.addStretch()

        # Update-Button (initially hidden, shown by _check_for_updates)
        self.btn_update = QPushButton(_tr("Update verfügbar"))
        self.btn_update.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px 16px;
                margin: 2px 8px;
                border: 1px solid #27ae60;
                border-radius: 8px;
                background: #1a3a2a;
                color: #6fcf97;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
                color: #fff;
            }
        """)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.hide()
        layout.addWidget(self.btn_update)

        # Versions-Label unten links
        from version import __version__
        _version_label = QLabel(f"v{__version__}")
        _version_label.setAlignment(Qt.AlignCenter)
        _version_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 25);
                font-size: 11px;
                padding: 6px 0;
            }
        """)
        layout.addWidget(_version_label)

        return sidebar

    def _create_settings_page(self) -> QWidget:
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(0, 0, 0, 0)
        page_lay.setSpacing(0)

        # ── Fixed header ──────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(54)
        header.setStyleSheet(
            "QWidget { background: #0b0b1a; border-bottom: 1px solid #181828; }"
        )
        h_row = QHBoxLayout(header)
        h_row.setContentsMargins(24, 0, 16, 0)

        self.settings_title = QLabel(_tr("Account hinzufügen"))
        self.settings_title.setStyleSheet(
            "font-size: 15px; font-weight: 600; color: #d8d8f0;"
            " background: transparent; border: none;"
        )
        h_row.addWidget(self.settings_title)
        h_row.addStretch()

        self.btn_close_settings = QPushButton(_tr("Schließen"))
        self.btn_close_settings.setStyleSheet("""
            QPushButton {
                padding: 5px 14px; border-radius: 6px;
                background: #1a1a2e; border: 1px solid #282840;
                color: #999; font-size: 12px;
            }
            QPushButton:hover { background: #b02030; color: white; border-color: #b02030; }
        """)
        self.btn_close_settings.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.main_page)
        )
        h_row.addWidget(self.btn_close_settings)
        page_lay.addWidget(header)

        # ── Scrollable content ────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_w = QWidget()
        scroll_w.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(scroll_w)
        outer.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        outer.setContentsMargins(20, 18, 20, 32)
        outer.setSpacing(0)

        inner = QWidget()
        inner.setMaximumWidth(660)
        inner.setStyleSheet("background: transparent;")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(10)

        # ── Card factory ──────────────────────────────────────
        _card_idx = [0]

        def _card(title: str = "") -> tuple[QFrame, QVBoxLayout]:
            _card_idx[0] += 1
            n = f"sc{_card_idx[0]}"
            c = QFrame()
            c.setObjectName(n)
            c.setStyleSheet(f"""
                QFrame#{n} {{
                    background: #0f0f1e;
                    border: 1px solid #1c1c2e;
                    border-radius: 10px;
                }}
                QFrame#{n} QLabel {{ background: transparent; border: none; }}
                QFrame#{n} QWidget {{ background: transparent; }}
            """)
            lay = QVBoxLayout(c)
            lay.setContentsMargins(20, 16, 20, 18)
            lay.setSpacing(9)
            if title:
                sec = QLabel(title.upper())
                sec.setStyleSheet(
                    "font-size: 10px; font-weight: 700; color: #3e3e5e;"
                    " letter-spacing: 0.8px; margin-bottom: 2px;"
                )
                lay.addWidget(sec)
            return c, lay

        # ── Sektion-Trennlinie ────────────────────────────────
        def _divider() -> QWidget:
            d = QWidget()
            d.setFixedHeight(1)
            d.setStyleSheet("background: #1a1a2c;")
            return d

        # ══════════════════════════════════════════════════════
        # Karte 1 — Account hinzufügen / bearbeiten
        # ══════════════════════════════════════════════════════
        card1, c1 = _card(_tr("Account"))

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText(_tr("Account-Name"))
        c1.addWidget(self.input_name)

        typ_row = QHBoxLayout()
        typ_row.setSpacing(12)
        typ_lbl = QLabel(_tr("Typ"))
        typ_lbl.setStyleSheet("color: #7a7a9a; font-size: 12px; min-width: 36px;")
        typ_row.addWidget(typ_lbl)
        self.account_type_combo = QComboBox()
        self.account_type_combo.addItem(_tr("Xtream Codes"), "xtream")
        self.account_type_combo.addItem(_tr("M3U Playlist"), "m3u")
        self.account_type_combo.currentIndexChanged.connect(self._on_account_type_changed)
        typ_row.addWidget(self.account_type_combo, stretch=1)
        c1.addLayout(typ_row)

        self.xtream_fields = QWidget()
        xf = QVBoxLayout(self.xtream_fields)
        xf.setContentsMargins(0, 0, 0, 0)
        xf.setSpacing(6)
        self.input_server = QLineEdit()
        self.input_server.setPlaceholderText(_tr("Server URL (http://...)"))
        xf.addWidget(self.input_server)
        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText(_tr("Benutzername"))
        xf.addWidget(self.input_username)
        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText(_tr("Passwort"))
        self.input_password.setEchoMode(QLineEdit.Password)
        xf.addWidget(self.input_password)
        c1.addWidget(self.xtream_fields)

        self.m3u_fields = QWidget()
        mf = QVBoxLayout(self.m3u_fields)
        mf.setContentsMargins(0, 0, 0, 0)
        self.input_m3u_url = QLineEdit()
        self.input_m3u_url.setPlaceholderText(_tr("M3U Playlist URL (http://...)"))
        mf.addWidget(self.input_m3u_url)
        c1.addWidget(self.m3u_fields)
        self.m3u_fields.hide()

        c1.addWidget(_divider())

        epg_lbl = QLabel(_tr("Externe EPG-URL (optional)"))
        epg_lbl.setStyleSheet("font-size: 11px; color: #55556a; margin-top: 2px;")
        c1.addWidget(epg_lbl)
        self.input_epg_url = QLineEdit()
        self.input_epg_url.setPlaceholderText(
            _tr("XMLTV-URL (http://... oder http://.../epg.xml.gz)")
        )
        c1.addWidget(self.input_epg_url)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_add_account = QPushButton(_tr("Account speichern"))
        self.btn_add_account.setStyleSheet("""
            QPushButton {
                background: #0078d4; color: white; border: none;
                border-radius: 7px; padding: 8px 22px;
                font-size: 13px; font-weight: 500;
            }
            QPushButton:hover { background: #1a8ae4; }
            QPushButton:pressed { background: #005fa8; }
            QPushButton:disabled { background: #1e1e30; color: #444; border: none; }
        """)
        self.btn_add_account.setFixedHeight(36)
        self.btn_add_account.clicked.connect(self._add_account)
        btn_row.addWidget(self.btn_add_account)

        self.btn_cancel_edit = QPushButton(_tr("Abbrechen"))
        self.btn_cancel_edit.setStyleSheet("""
            QPushButton {
                background: #1a1a2e; color: #999; border: 1px solid #282840;
                border-radius: 7px; padding: 8px 18px; font-size: 13px;
            }
            QPushButton:hover { background: #24243c; color: #ccc; }
        """)
        self.btn_cancel_edit.setFixedHeight(36)
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)
        self.btn_cancel_edit.hide()
        btn_row.addWidget(self.btn_cancel_edit)
        btn_row.addStretch()
        c1.addLayout(btn_row)

        inner_lay.addWidget(card1)

        # ══════════════════════════════════════════════════════
        # Karte 2 — Gespeicherte Accounts
        # ══════════════════════════════════════════════════════
        card2, c2 = _card(_tr("Gespeicherte Accounts"))

        self.account_list = QListWidget()
        self.account_list.setMaximumHeight(160)
        self.account_list.setStyleSheet("""
            QListWidget {
                background: #08081a;
                border: 1px solid #1a1a2c;
                border-radius: 7px;
                color: #c8c8e0;
                font-size: 13px;
                outline: 0;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #141424;
            }
            QListWidget::item:hover { background: #141430; }
            QListWidget::item:selected {
                background: rgba(0,120,212,22);
                color: white;
                border-bottom-color: rgba(0,120,212,30);
            }
            QScrollBar:vertical { background: transparent; width: 5px; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,14); border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.account_list.itemClicked.connect(self._on_account_list_clicked)
        c2.addWidget(self.account_list)

        acc_footer = QHBoxLayout()
        acc_hint = QLabel(_tr("Auf einen Account klicken, um ihn zu bearbeiten"))
        acc_hint.setStyleSheet("color: #3a3a55; font-size: 11px;")
        acc_footer.addWidget(acc_hint)
        acc_footer.addStretch()

        self.btn_delete_account = QPushButton(_tr("Löschen"))
        self.btn_delete_account.setStyleSheet("""
            QPushButton {
                background: transparent; color: #a03030;
                border: 1px solid #3a1818; border-radius: 6px;
                padding: 5px 16px; font-size: 12px;
            }
            QPushButton:hover { background: #a03030; color: white; border-color: #a03030; }
        """)
        self.btn_delete_account.setFixedHeight(28)
        self.btn_delete_account.clicked.connect(self._delete_account)
        acc_footer.addWidget(self.btn_delete_account)
        c2.addLayout(acc_footer)

        inner_lay.addWidget(card2)

        # ══════════════════════════════════════════════════════
        # Karte 3 — Line-Status
        # ══════════════════════════════════════════════════════
        card3, c3 = _card()

        ls_row = QHBoxLayout()
        ls_title = QLabel(_tr("Line-Status"))
        ls_title.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #b0b0cc; background: transparent;"
        )
        ls_row.addWidget(ls_title)
        ls_row.addStretch()

        self.btn_refresh_line_info = QPushButton("↻")
        self.btn_refresh_line_info.setToolTip(_tr("Aktualisieren"))
        self.btn_refresh_line_info.setFixedSize(28, 28)
        self.btn_refresh_line_info.setStyleSheet("""
            QPushButton {
                background: #181830; border: 1px solid #242440;
                border-radius: 14px; color: #777; font-size: 14px;
                padding: 0;
            }
            QPushButton:hover { background: #222244; color: white; }
        """)
        self.btn_refresh_line_info.clicked.connect(
            lambda: asyncio.ensure_future(self._refresh_line_info())
        )
        ls_row.addWidget(self.btn_refresh_line_info)
        c3.addLayout(ls_row)

        self.lbl_line_info = QLabel(_tr("Kein aktiver Account"))
        self.lbl_line_info.setStyleSheet("""
            QLabel {
                background: #08081a;
                border: 1px solid #1a1a2c;
                border-radius: 8px;
                padding: 12px 14px;
                color: #666;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        self.lbl_line_info.setWordWrap(True)
        c3.addWidget(self.lbl_line_info)

        inner_lay.addWidget(card3)

        # ══════════════════════════════════════════════════════
        # Karte 4 — Wiedergabe
        # ══════════════════════════════════════════════════════
        card4, c4 = _card(_tr("Wiedergabe"))

        def _setting_row(label_text: str) -> tuple[QHBoxLayout, QLabel]:
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #b8b8d0; font-size: 13px;")
            row.addWidget(lbl, stretch=1)
            return row, lbl

        hw_row, _ = _setting_row(_tr("Hardware-Dekodierung"))
        self.hwdec_combo = QComboBox()
        self.hwdec_combo.addItem(_tr("Automatisch (empfohlen)"), "auto")
        self.hwdec_combo.addItem(_tr("Hardware + Kopie (auto-copy)"), "auto-copy")
        self.hwdec_combo.addItem(_tr("Software (kompatibel, mehr CPU)"), "no")
        saved_hwdec = self.app_settings.get("hwdec", "auto")
        idx = self.hwdec_combo.findData(saved_hwdec)
        self.hwdec_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.hwdec_combo.currentIndexChanged.connect(self._on_hwdec_changed)
        self.hwdec_combo.setMaximumWidth(280)
        hw_row.addWidget(self.hwdec_combo)
        c4.addLayout(hw_row)

        self.lbl_hwdec_hint = QLabel(_tr("↻ App neu starten damit die Änderung wirkt"))
        self.lbl_hwdec_hint.setStyleSheet("color: #e8691a; font-size: 11px; margin: 0 0 4px 0;")
        self.lbl_hwdec_hint.hide()
        c4.addWidget(self.lbl_hwdec_hint)

        c4.addWidget(_divider())

        buf_row, _ = _setting_row(_tr("Wiedergabe-Stabilität"))
        self.buffer_combo = QComboBox()
        self.buffer_combo.addItem(_tr("Ausgewogen (4s)"), 4)
        self.buffer_combo.addItem(_tr("Hoch – stabil bei Aussetzern (8s)"), 8)
        self.buffer_combo.addItem(_tr("Niedrig – sehr gute Verbindung (1s)"), 1)
        saved_buf = self.app_settings.get("buffer_secs", 4)
        buf_idx = self.buffer_combo.findData(saved_buf)
        self.buffer_combo.setCurrentIndex(buf_idx if buf_idx >= 0 else 0)
        self.buffer_combo.currentIndexChanged.connect(self._on_buffer_changed)
        self.buffer_combo.setMaximumWidth(280)
        buf_row.addWidget(self.buffer_combo)
        c4.addLayout(buf_row)

        buf_hint = QLabel(_tr("Erhöhen wenn der Stream häufig unterbricht."))
        buf_hint.setStyleSheet("color: #44445a; font-size: 11px;")
        c4.addWidget(buf_hint)

        inner_lay.addWidget(card4)

        # ══════════════════════════════════════════════════════
        # Karte 5 — Sprache
        # ══════════════════════════════════════════════════════
        card5, c5 = _card(_tr("Sprache / Language"))

        lang_row, _ = _setting_row(_tr("Sprache"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Deutsch", "de")
        self.lang_combo.addItem("English", "en")
        saved_lang = self.app_settings.get("language", "de")
        lang_idx = self.lang_combo.findData(saved_lang)
        self.lang_combo.setCurrentIndex(lang_idx if lang_idx >= 0 else 0)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self.lang_combo.setMaximumWidth(200)
        lang_row.addWidget(self.lang_combo)
        c5.addLayout(lang_row)

        self.lbl_lang_hint = QLabel(_tr("↻ App neu starten damit die Änderung wirkt"))
        self.lbl_lang_hint.setStyleSheet("color: #e8691a; font-size: 11px; margin: 0;")
        self.lbl_lang_hint.hide()
        c5.addWidget(self.lbl_lang_hint)

        inner_lay.addWidget(card5)

        # ── Assemble ──────────────────────────────────────────
        outer.addWidget(inner)
        scroll.setWidget(scroll_w)
        page_lay.addWidget(scroll)

        return page

    def _create_main_page(self) -> QWidget:
        """Hauptseite mit Kanalliste und integriertem Player"""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Links: Kanalbereich (fuellt alles wenn kein Player, sonst feste Breite)
        self.channel_area = self._create_channel_area()
        layout.addWidget(self.channel_area)

        # Rechts: Playerbereich (fuellt den Rest, anfangs versteckt)
        self.player_area = self._create_player_area()
        layout.addWidget(self.player_area)
        self.player_area.hide()

        # Event-Filter fuer PiP-Positionierung bei Resize
        page.installEventFilter(self)

        return page

    def _apply_channel_list_style(self, grid_mode: bool):
        """Setzt Stylesheet passend zum View-Modus"""
        if grid_mode:
            self.channel_list.setStyleSheet("""
                QListWidget {
                    background-color: transparent;
                    border: none;
                    outline: 0;
                    color: #ddd;
                    font-size: 13px;
                    padding: 4px;
                }
                QListWidget::item {
                    border-radius: 10px;
                    background-color: rgba(20, 20, 42, 160);
                    border: 1px solid rgba(255, 255, 255, 7);
                }
                QListWidget::item:hover {
                    background-color: rgba(30, 30, 60, 180);
                    border: 1px solid rgba(255, 255, 255, 18);
                }
                QListWidget::item:selected {
                    background-color: rgba(0, 120, 212, 40);
                    border: 1px solid rgba(0, 120, 212, 110);
                    color: white;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 6px;
                }
                QScrollBar::handle:vertical {
                    background: rgba(255, 255, 255, 18);
                    border-radius: 3px;
                    min-height: 20px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            """)
        else:
            self.channel_list.setStyleSheet("""
                QListWidget {
                    background-color: transparent;
                    border: none;
                    outline: 0;
                    color: #ddd;
                    font-size: 15px;
                    font-family: "Fira Sans";
                    font-weight: 500;
                }
                QListWidget::item {
                    padding: 9px 12px;
                    border-bottom: 1px solid rgba(255, 255, 255, 4);
                    outline: 0;
                }
                QListWidget::item:hover {
                    background-color: rgba(255, 255, 255, 6);
                    color: #fff;
                }
                QListWidget::item:focus {
                    outline: 0;
                    border: none;
                }
                QListWidget::item:selected {
                    background-color: rgba(0, 120, 212, 22);
                    border-left: 3px solid #0078d4;
                    color: white;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 6px;
                }
                QScrollBar::handle:vertical {
                    background: rgba(255, 255, 255, 18);
                    border-radius: 3px;
                    min-height: 20px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            """)

    def _create_channel_area(self) -> QWidget:
        """Erstellt den Kanalbereich mit Liste, EPG-Panel und Serien-Detailansicht"""
        self.channel_stack = QStackedWidget()

        # Seite 0: Horizontales Layout [Kanal-Navigation | Kanal-Detailansicht]
        channel_list_page = QWidget()
        outer_layout = QHBoxLayout(channel_list_page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Links: Kanal-Navigation (Kategorie-Button + Kanalliste + EPG-Panel)
        self.channel_nav_widget = QWidget()
        self._detail_stream_data = None  # Aktuell im Detail-Panel angezeigter Sender
        cl_layout = QVBoxLayout(self.channel_nav_widget)
        cl_layout.setContentsMargins(0, 0, 0, 0)
        cl_layout.setSpacing(0)

        # Kategorie-Zeile (Label + Button, analog zur Sortierungs-Zeile)
        self.category_row = QWidget()
        self.category_row.setStyleSheet("background: rgba(255, 255, 255, 3); border-bottom: 1px solid rgba(255, 255, 255, 6);")
        _cat_row_layout = QHBoxLayout(self.category_row)
        _cat_row_layout.setContentsMargins(12, 0, 0, 0)
        _cat_row_layout.setSpacing(8)

        _cat_label = QLabel(_tr("Kategorie:"))
        _cat_label.setStyleSheet("color: #666; font-size: 12px; border: none; background: transparent;")
        _cat_row_layout.addWidget(_cat_label)

        self.category_btn = QPushButton("W\u00e4hlen  \u25BE")
        self.category_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 8px;
                background: transparent;
                border: none;
                border-radius: 0;
                color: #ccc;
                font-size: 12px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover { color: white; background: #1c1c2c; }
        """)
        self._category_items: list[tuple[str, str]] = []  # (name, id)
        self._current_category_index = -1
        self.category_btn.clicked.connect(self._toggle_category_list)
        _cat_row_layout.addWidget(self.category_btn, stretch=1)
        cl_layout.addWidget(self.category_row)

        # Favoriten-Filter-Leiste (nur im Favoriten-Modus sichtbar)
        self.fav_filter_row = QWidget()
        self.fav_filter_row.setObjectName("favFilterRow")
        self.fav_filter_row.setStyleSheet("#favFilterRow { background: rgba(255, 255, 255, 3); border-bottom: 1px solid rgba(255, 255, 255, 6); }")
        _fav_outer = QVBoxLayout(self.fav_filter_row)
        _fav_outer.setContentsMargins(8, 4, 8, 4)
        _fav_outer.setSpacing(6)

        # Zeile 1: Typ-Buttons
        _fav_btn_container = QWidget()
        _fav_layout = QHBoxLayout(_fav_btn_container)
        _fav_layout.setContentsMargins(0, 0, 0, 0)
        _fav_layout.setSpacing(6)

        self._fav_filter_buttons = {}
        _fav_btn_style = """
            QPushButton {
                padding: 4px 12px; border-radius: 12px; font-size: 12px;
                background: transparent; border: 1px solid #2a2a3a; color: #888;
            }
            QPushButton:hover { border-color: #0078d4; color: #ccc; }
            QPushButton[active="true"] { background: #0078d4; border-color: #0078d4; color: white; font-weight: bold; }
        """
        for label, ftype in [(_tr("Alle"), None), ("📺 " + _tr("Live"), "live"), ("🎬 " + _tr("Filme"), "vod"), ("📖 " + _tr("Serien"), "series")]:
            btn = QPushButton(label)
            btn.setStyleSheet(_fav_btn_style)
            btn.setProperty("active", "false")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=ftype: self._set_fav_filter(t))
            _fav_layout.addWidget(btn)
            self._fav_filter_buttons[ftype] = btn

        self._fav_filter_buttons[None].setProperty("active", "true")
        _fav_layout.addStretch()
        _fav_outer.addWidget(_fav_btn_container)

        # Zeile 2: Sortier-Dropdown (direkt unter den Typ-Buttons)
        _fav_sort_container = QWidget()
        _fav_sort_layout = QHBoxLayout(_fav_sort_container)
        _fav_sort_layout.setContentsMargins(0, 0, 0, 0)
        _fav_sort_layout.setSpacing(8)

        _fav_sort_label = QLabel(_tr("Sortierung:"))
        _fav_sort_label.setStyleSheet("color: #666; font-size: 12px; border: none;")
        _fav_sort_layout.addWidget(_fav_sort_label)

        self.fav_sort_combo = QComboBox()
        self.fav_sort_combo.setCursor(Qt.PointingHandCursor)
        self.fav_sort_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                background: transparent;
                border: none;
                color: #ccc;
                font-size: 12px;
            }
            QComboBox:hover { color: white; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1e1e2e;
                color: white;
                selection-background-color: #0078d4;
                border: 1px solid #2a2a3a;
            }
        """)
        self.fav_sort_combo.currentIndexChanged.connect(self._on_fav_sort_changed)
        _fav_sort_layout.addWidget(self.fav_sort_combo)
        _fav_sort_layout.addStretch()
        _fav_outer.addWidget(_fav_sort_container)

        self.fav_filter_row.hide()
        cl_layout.addWidget(self.fav_filter_row)

        # Inline-Kategorie-Liste (aufklappbar)
        self.category_list = QListWidget()
        self.category_list.setStyleSheet("""
            QListWidget {
                background: rgba(8, 8, 20, 220);
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 6);
                color: #ccc;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 14px;
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 6);
                color: white;
            }
            QListWidget::item:selected {
                background: rgba(0, 120, 212, 25);
                color: white;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 18);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.category_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.category_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.category_list.customContextMenuRequested.connect(self._on_category_context_menu)
        self.category_list.itemClicked.connect(self._on_category_list_clicked)
        self.category_list.hide()
        cl_layout.addWidget(self.category_list, stretch=1)

        # Trenner + Button für ausgeblendete Kategorien (nur wenn Dropdown offen + hat versteckte)
        self._hidden_cat_sep = QFrame()
        self._hidden_cat_sep.setFrameShape(QFrame.HLine)
        self._hidden_cat_sep.setStyleSheet("background: rgba(255,255,255,8); margin: 0;")
        self._hidden_cat_sep.hide()
        cl_layout.addWidget(self._hidden_cat_sep)

        self.manage_hidden_btn = QPushButton(_tr("Kategorien verwalten"))
        self.manage_hidden_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 9px 16px;
                margin: 0;
                border: none;
                border-radius: 0;
                background: transparent;
                color: #666;
                font-size: 13px;
            }
            QPushButton:hover { background: rgba(255,255,255,6); color: #aaa; }
        """)
        self.manage_hidden_btn.clicked.connect(self._show_manage_categories_dialog)
        self.manage_hidden_btn.hide()
        cl_layout.addWidget(self.manage_hidden_btn)


        # Sortierung (nur bei VOD/Serien sichtbar)
        self.sort_widget = QWidget()
        self.sort_widget.setStyleSheet("background: rgba(255, 255, 255, 3); border-bottom: 1px solid rgba(255, 255, 255, 6);")
        sort_layout = QHBoxLayout(self.sort_widget)
        sort_layout.setContentsMargins(12, 4, 10, 4)
        sort_layout.setSpacing(8)

        sort_label = QLabel(_tr("Sortierung:"))
        sort_label.setStyleSheet("color: #666; font-size: 12px; border: none;")
        sort_layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            _tr("Standard"),
            _tr("Zuletzt hinzugefügt"),
            _tr("Bewertung (beste zuerst)"),
            _tr("A – Z"),
            _tr("Z – A"),
        ])
        self.sort_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                background: transparent;
                border: none;
                color: #ccc;
                font-size: 12px;
            }
            QComboBox:hover { color: white; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1e1e2e;
                color: white;
                selection-background-color: #0078d4;
                border: 1px solid #2a2a3a;
            }
        """)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        saved_sort = self.app_settings.get("vod_sort_index", 0)
        if saved_sort:
            self.sort_combo.blockSignals(True)
            self.sort_combo.setCurrentIndex(saved_sort)
            self.sort_combo.blockSignals(False)
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addStretch()

        self.sort_widget.hide()
        cl_layout.addWidget(self.sort_widget)

        # Loading-Overlay (statt leerer Liste)
        self.channel_loading = QWidget()
        self.channel_loading.setStyleSheet("background: transparent;")
        cl_loading_layout = QVBoxLayout(self.channel_loading)
        cl_loading_layout.setAlignment(Qt.AlignCenter)
        self._loading_spinner = QProgressBar()
        self._loading_spinner.setRange(0, 0)
        self._loading_spinner.setFixedWidth(200)
        self._loading_spinner.setFixedHeight(6)
        self._loading_spinner.setStyleSheet("""
            QProgressBar {
                background: #1a1a2a;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #0078d4;
                border-radius: 3px;
            }
        """)
        self._loading_text = QLabel(_tr("Lade…"))
        self._loading_text.setAlignment(Qt.AlignCenter)
        self._loading_text.setStyleSheet("color: #888; font-size: 13px;")
        self._loading_retry_btn = QPushButton(_tr("Erneut versuchen"))
        self._loading_retry_btn.setFixedWidth(160)
        self._loading_retry_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background: #1a8ae8; }
        """)
        self._loading_retry_btn.clicked.connect(self._retry_load)
        self._loading_retry_btn.hide()
        cl_loading_layout.addWidget(self._loading_spinner, alignment=Qt.AlignCenter)
        cl_loading_layout.addWidget(self._loading_text, alignment=Qt.AlignCenter)
        cl_loading_layout.addWidget(self._loading_retry_btn, alignment=Qt.AlignCenter)
        self.channel_loading.hide()
        cl_layout.addWidget(self.channel_loading, stretch=1)

        self.channel_list = QListWidget()
        self.channel_list.setItemDelegate(_CatchupDelegate(self.channel_list, self))
        self._apply_channel_list_style(grid_mode=False)
        self.channel_list.itemClicked.connect(self._on_channel_selected)
        self.channel_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.channel_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self._show_channel_context_menu)
        self.channel_list.viewport().setMouseTracking(True)
        self.channel_list.viewport().installEventFilter(self)

        # EPG Panel
        self.epg_panel = self._create_epg_panel()
        self.epg_panel.setMinimumHeight(200)

        # Splitter zwischen Kanalliste und EPG
        self._epg_splitter = QSplitter(Qt.Vertical)
        self._epg_splitter.setChildrenCollapsible(False)
        self._epg_splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background: rgba(255, 255, 255, 8);
                height: 3px;
            }
            QSplitter::handle:vertical:hover {
                background: rgba(232, 105, 26, 200);
            }
        """)
        self._epg_splitter.addWidget(self.channel_list)
        self._epg_splitter.addWidget(self.epg_panel)
        self._epg_splitter.setSizes([99999, 0])
        self.epg_panel.hide()

        # ── Quality-Hinweis-Banner (einmalig) ────────────────────────────────
        from platform_utils import get_config_dir
        _hint_flag = get_config_dir() / "epg_quality_hint_dismissed"
        if not _hint_flag.exists():
            hint_bar = QWidget()
            hint_bar.setObjectName("epgQualityHint")
            hint_bar.setStyleSheet("""
                #epgQualityHint {
                    background: rgba(0,120,212,12);
                    border-bottom: 1px solid rgba(0,120,212,40);
                }
            """)
            hint_lay = QHBoxLayout(hint_bar)
            hint_lay.setContentsMargins(12, 6, 8, 6)
            hint_lay.setSpacing(8)
            hint_lbl = QLabel(_tr("Sender abspielen → App misst Qualität und zeigt sie als Punkt: 4K = gold · FHD = lila · HD = blau · SD = grau"))
            hint_lbl.setStyleSheet("color: #5aaef0; font-size: 11px;")
            hint_lbl.setWordWrap(True)
            hint_lay.addWidget(hint_lbl, stretch=1)
            dismiss_btn = QPushButton()
            dismiss_btn.setIcon(_pi("x.svg", 11))
            dismiss_btn.setIconSize(QSize(11, 11))
            dismiss_btn.setFixedSize(20, 20)
            dismiss_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,15);
                    border: 1px solid rgba(255,255,255,30);
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,30);
                }
            """)
            def _dismiss_hint(_checked=False, bar=hint_bar, flag=_hint_flag):
                bar.hide()
                try:
                    flag.touch()
                except Exception:
                    pass
            dismiss_btn.clicked.connect(_dismiss_hint)
            hint_lay.addWidget(dismiss_btn, alignment=Qt.AlignVCenter)
            cl_layout.addWidget(hint_bar)

        cl_layout.addWidget(self._epg_splitter, stretch=1)

        outer_layout.addWidget(self.channel_nav_widget, stretch=1)

        # Rechts: modernes Kanal-Detailpanel (standardmaessig versteckt)
        self.channel_detail_panel = self._create_channel_detail_panel()
        self.channel_detail_panel.hide()
        outer_layout.addWidget(self.channel_detail_panel)

        self.channel_stack.addWidget(channel_list_page)

        # Seite 1: Serien-Detailansicht
        self.series_detail_page = self._create_series_detail_page()
        self.channel_stack.addWidget(self.series_detail_page)

        # Seite 2: VOD-Detailansicht
        self.vod_detail_page = self._create_vod_detail_page()
        self.channel_stack.addWidget(self.vod_detail_page)

        # Seite 3: EPG-Programmsuche
        self.epg_search_page = self._create_epg_search_page()
        self.channel_stack.addWidget(self.epg_search_page)

        return self.channel_stack

    def _create_epg_search_page(self) -> QWidget:
        """EPG-Programmsuche: Was läuft gerade / bald auf allen Sendern."""
        from PySide6.QtWidgets import QLineEdit
        page = QWidget()
        page.setObjectName("epgSearchPage")
        page.setStyleSheet("#epgSearchPage { background-color: #0a0a14; }")

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(
            "background: rgba(255,255,255,3); border-bottom: 1px solid rgba(255,255,255,6);"
        )
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(14, 12, 14, 10)
        h_lay.setSpacing(8)

        title_row = QHBoxLayout()
        title_lbl = QLabel(_tr("Programm-Suche"))
        title_lbl.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        title_row.addWidget(title_lbl, stretch=1)
        reload_btn = QPushButton()
        reload_btn.setIcon(_si("refresh.svg"))
        reload_btn.setIconSize(QSize(15, 15))
        reload_btn.setFixedSize(28, 28)
        reload_btn.setToolTip(_tr("EPG neu laden"))
        reload_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; }
            QPushButton:hover { background: rgba(255,255,255,10); border-radius: 5px; }
        """)
        reload_btn.clicked.connect(self._epg_search_force_reload)
        title_row.addWidget(reload_btn)
        h_lay.addLayout(title_row)

        self.epg_search_input = QLineEdit()
        self.epg_search_input.setPlaceholderText(_tr("Sendung suchen…"))
        self.epg_search_input.setClearButtonEnabled(True)
        self.epg_search_input.setStyleSheet("""
            QLineEdit {
                padding: 7px 10px; background: rgba(255,255,255,5);
                border: 1px solid rgba(255,255,255,10); border-radius: 8px;
                color: white; font-size: 13px;
            }
            QLineEdit:focus { border-color: rgba(0,120,212,180); background: rgba(0,120,212,8); }
        """)
        self.epg_search_input.textChanged.connect(self._epg_search_query_changed)
        h_lay.addWidget(self.epg_search_input)

        outer.addWidget(header)

        # ── Filter-Chips ─────────────────────────────────────────────────────
        filter_row = QWidget()
        filter_row.setObjectName("epgFilterRow")
        filter_row.setStyleSheet("""
            #epgFilterRow {
                background: rgba(255,255,255,3);
                border-bottom: 1px solid rgba(255,255,255,6);
            }
            #epgFilterRow QPushButton {
                text-align: center; margin: 0;
                padding: 4px 14px; border-radius: 10px; font-size: 12px;
                background: transparent; border: 1px solid #3a3a50; color: #888;
            }
            #epgFilterRow QPushButton:hover { border-color: #0078d4; color: #ccc; }
            #epgFilterRow QPushButton[active="true"] {
                background: #0078d4; border-color: #0078d4; color: white; font-weight: bold;
            }
        """)
        f_lay = QHBoxLayout(filter_row)
        f_lay.setContentsMargins(10, 6, 10, 6)
        f_lay.setSpacing(6)

        self._epg_filter_buttons = {}
        for label, fkey in [(_tr("Alle"), "all"), (_tr("Jetzt"), "now"), (_tr("Bald"), "soon")]:
            btn = QPushButton(label)
            btn.setProperty("active", "true" if fkey == "all" else "false")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, k=fkey: self._epg_search_filter_changed(k))
            f_lay.addWidget(btn)
            self._epg_filter_buttons[fkey] = btn
        f_lay.addStretch()

        self.epg_sort_quality_btn = QPushButton(_tr("Qualität"))
        self.epg_sort_quality_btn.setProperty("active", "false")
        self.epg_sort_quality_btn.setCursor(Qt.PointingHandCursor)
        self.epg_sort_quality_btn.setToolTip(_tr("Nach Qualität sortieren"))
        self.epg_sort_quality_btn.clicked.connect(self._epg_search_toggle_quality_sort)
        f_lay.addWidget(self.epg_sort_quality_btn)

        outer.addWidget(filter_row)

        # ── Lade-Bereich ─────────────────────────────────────────────────────
        self.epg_search_loading_widget = QWidget()
        loading_lay = QVBoxLayout(self.epg_search_loading_widget)
        loading_lay.setContentsMargins(14, 8, 14, 6)
        loading_lay.setSpacing(4)

        self.epg_search_status_lbl = QLabel("")
        self.epg_search_status_lbl.setStyleSheet("color: #666; font-size: 11px;")
        loading_lay.addWidget(self.epg_search_status_lbl)

        self.epg_search_progress = QProgressBar()
        self.epg_search_progress.setTextVisible(False)
        self.epg_search_progress.setFixedHeight(3)
        self.epg_search_progress.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,8); border: none; border-radius: 1px; }
            QProgressBar::chunk { background: #0078d4; border-radius: 1px; }
        """)
        loading_lay.addWidget(self.epg_search_progress)
        self.epg_search_loading_widget.hide()

        outer.addWidget(self.epg_search_loading_widget)

        # ── Ergebnis-ScrollArea ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: #2a2a3a; border-radius: 2px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        results_container = QWidget()
        results_container.setStyleSheet("background: transparent;")
        self.epg_search_results_layout = QVBoxLayout(results_container)
        self.epg_search_results_layout.setContentsMargins(0, 0, 0, 0)
        self.epg_search_results_layout.setSpacing(0)
        self.epg_search_results_layout.addStretch()

        scroll.setWidget(results_container)
        outer.addWidget(scroll, stretch=1)

        return page

    def _create_channel_detail_panel(self) -> QWidget:
        """Modernes Kanal-Detailpanel: Hero-Bild, Logo, Name, EPG mit Fortschrittsbalken."""
        panel = QWidget()
        panel.setObjectName("channelDetailPanel")
        panel.setStyleSheet("""
            #channelDetailPanel {
                background-color: rgba(7, 7, 18, 220);
                border-left: 1px solid rgba(255, 255, 255, 7);
            }
        """)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Zurück-Leiste
        back_bar = QWidget()
        back_bar.setFixedHeight(36)
        back_bar.setStyleSheet("background: rgba(255, 255, 255, 3); border-bottom: 1px solid rgba(255, 255, 255, 6);")
        back_bar_layout = QHBoxLayout(back_bar)
        back_bar_layout.setContentsMargins(8, 0, 8, 0)
        self.detail_back_btn = QPushButton("‹  " + _tr("Senderliste"))
        self.detail_back_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #777;
                border: none; font-size: 13px; padding: 0 8px;
            }
            QPushButton:hover { color: #ccc; }
        """)
        self.detail_back_btn.clicked.connect(self._hide_channel_detail)
        back_bar_layout.addWidget(self.detail_back_btn)
        back_bar_layout.addStretch()
        outer.addWidget(back_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0a0a12; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #2a2a3a; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignTop)

        # Catchup-Button-Stil (genutzt in Header + DAVOR-Bereich)
        _catchup_btn_ss = """
            QPushButton {
                background: transparent; color: #e8691a;
                border: 1px solid #e8691a; border-radius: 8px;
                font-size: 13px; font-weight: bold; padding: 0 16px;
            }
            QPushButton:hover { background: rgba(232, 105, 26, 30); color: #ffab6e; border-color: #ffab6e; }
        """

        # ── Header: Logo + Kanalname ──────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        self.detail_logo = QLabel()
        self.detail_logo.setFixedSize(80, 80)
        self.detail_logo.setAlignment(Qt.AlignCenter)
        self.detail_logo.setStyleSheet("""
            background-color: #1a1a2a;
            border-radius: 12px;
            color: #444;
            font-size: 26px;
        """)
        self.detail_logo.setText("\U0001F4FA")
        header_row.addWidget(self.detail_logo, alignment=Qt.AlignVCenter)

        name_block = QVBoxLayout()
        name_block.setSpacing(8)

        self.detail_channel_name = QLabel("")
        self.detail_channel_name.setStyleSheet(
            "font-size: 26px; font-weight: bold; color: #ffffff;"
        )
        self.detail_channel_name.setWordWrap(True)
        self.detail_channel_name.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        name_block.addWidget(self.detail_channel_name)

        header_row.addLayout(name_block, stretch=1)
        lay.addLayout(header_row)

        # ── Trennlinie ────────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,6); margin: 0;")
        lay.addWidget(sep)

        # ── DAVOR-Bereich ─────────────────────────────────────────
        self.detail_prev_widget = QWidget()
        self.detail_prev_widget.setStyleSheet("background: transparent;")
        prev_lay = QVBoxLayout(self.detail_prev_widget)
        prev_lay.setContentsMargins(0, 0, 0, 0)
        prev_lay.setSpacing(4)

        davor_lbl = QLabel(_tr("DAVOR"))
        davor_lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #333; letter-spacing: 2px;"
        )
        prev_lay.addWidget(davor_lbl)

        prev_row = QHBoxLayout()
        prev_row.setSpacing(8)
        self.detail_prev_title = QLabel("")
        self.detail_prev_title.setStyleSheet("font-size: 16px; color: #555;")
        self.detail_prev_title.setWordWrap(True)
        prev_row.addWidget(self.detail_prev_title, stretch=1)
        self.detail_prev_play_btn = QPushButton("\u25B6")
        self.detail_prev_play_btn.setFixedHeight(28)
        self.detail_prev_play_btn.setStyleSheet(_catchup_btn_ss)
        self.detail_prev_play_btn.clicked.connect(self._play_detail_prev)
        self.detail_prev_play_btn.hide()
        prev_row.addWidget(self.detail_prev_play_btn, alignment=Qt.AlignVCenter)
        prev_lay.addLayout(prev_row)

        self.detail_prev_time = QLabel("")
        self.detail_prev_time.setStyleSheet("font-size: 12px; color: #444;")
        prev_lay.addWidget(self.detail_prev_time)

        self.detail_prev_widget.hide()
        lay.addWidget(self.detail_prev_widget)

        # ── JETZT-Bereich ─────────────────────────────────────────
        self.detail_now_section = QWidget()
        self.detail_now_section.setStyleSheet("background: transparent;")
        now_lay = QVBoxLayout(self.detail_now_section)
        now_lay.setContentsMargins(0, 0, 0, 0)
        now_lay.setSpacing(8)

        jetzt_lbl = QLabel(_tr("JETZT"))
        jetzt_lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #e8691a; letter-spacing: 2px;"
        )
        now_lay.addWidget(jetzt_lbl)

        now_title_row = QHBoxLayout()
        now_title_row.setSpacing(8)
        self.detail_now_title = QLabel("\u2013")
        self.detail_now_title.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #eeeeee;"
        )
        self.detail_now_title.setWordWrap(True)
        now_title_row.addWidget(self.detail_now_title, stretch=1)
        now_lay.addLayout(now_title_row)

        now_time_row = QHBoxLayout()
        now_time_row.setSpacing(8)
        self.detail_now_time = QLabel("")
        self.detail_now_time.setStyleSheet("font-size: 14px; color: #666;")
        now_time_row.addWidget(self.detail_now_time, stretch=1)
        self.detail_now_rec_btn = QPushButton()
        self.detail_now_rec_btn.setIcon(_pi("record.svg", 16))
        self.detail_now_rec_btn.setIconSize(QSize(16, 16))
        self.detail_now_rec_btn.setToolTip(_tr("Aufnahme planen"))
        self.detail_now_rec_btn.setFixedSize(30, 30)
        self.detail_now_rec_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #888;
                border: 1px solid #444; border-radius: 4px;
                padding: 0;
            }
            QPushButton:hover { background: #c0392b; border-color: #c0392b; }
        """)
        self.detail_now_rec_btn.hide()
        now_time_row.addWidget(self.detail_now_rec_btn, alignment=Qt.AlignVCenter)
        now_lay.addLayout(now_time_row)

        self.detail_now_progress = QProgressBar()
        self.detail_now_progress.setFixedHeight(4)
        self.detail_now_progress.setTextVisible(False)
        self.detail_now_progress.setStyleSheet("""
            QProgressBar {
                background: #1e1e2e; border: none; border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #e8691a; border-radius: 2px;
            }
        """)
        self.detail_now_progress.hide()
        now_lay.addWidget(self.detail_now_progress)

        self.detail_now_desc = QLabel("")
        self.detail_now_desc.setStyleSheet(
            "font-size: 15px; color: #888; line-height: 1.6;"
        )
        self.detail_now_desc.setWordWrap(True)
        self.detail_now_desc.hide()
        now_lay.addWidget(self.detail_now_desc)

        lay.addWidget(self.detail_now_section)

        # ── DANACH-Bereich (dynamisch, bis zu 3 Eintraege) ────────────────────────
        self.detail_future_section = QWidget()
        self.detail_future_section.setStyleSheet("background: transparent;")
        future_outer = QVBoxLayout(self.detail_future_section)
        future_outer.setContentsMargins(0, 0, 0, 0)
        future_outer.setSpacing(6)

        danach_lbl = QLabel(_tr("DANACH"))
        danach_lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #444; letter-spacing: 2px;"
        )
        future_outer.addWidget(danach_lbl)

        self.detail_future_container = QWidget()
        self.detail_future_container.setStyleSheet("background: transparent;")
        self.detail_future_layout = QVBoxLayout(self.detail_future_container)
        self.detail_future_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_future_layout.setSpacing(8)
        future_outer.addWidget(self.detail_future_container)

        self.detail_future_section.hide()
        lay.addWidget(self.detail_future_section)

        # ── Vollstaendiges EPG-Button ──────────────────────────────
        self.detail_epg_action_btn = QPushButton(_tr("Vollständiges EPG") + "  \u25B8")
        self.detail_epg_action_btn.setFixedHeight(38)
        self.detail_epg_action_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #e8691a;
                border: 1px solid #e8691a;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
                padding: 0 18px;
            }
            QPushButton:hover { background: rgba(232, 105, 26, 30); }
            QPushButton:disabled { color: #555; border-color: #333; }
        """)
        self.detail_epg_action_btn.clicked.connect(self._show_full_epg)
        self.detail_epg_action_btn.setEnabled(False)
        lay.addWidget(self.detail_epg_action_btn)

        lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        return panel

    def _create_epg_panel(self) -> QWidget:
        """Creates the EPG info panel"""
        panel = QFrame()
        panel.setObjectName("epgPanel")
        panel.setStyleSheet("""
            #epgPanel {
                background-color: rgba(8, 8, 20, 210);
                border-top: 1px solid rgba(255, 255, 255, 7);
            }
        """)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        # ScrollArea damit langer EPG-Inhalt nicht abgeschnitten wird
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 15);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        panel_layout.addWidget(scroll)

        # Inhalt-Widget innerhalb der ScrollArea
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)
        scroll.setWidget(content)
        self._epg_content_widget = content
        content.setCursor(Qt.PointingHandCursor)
        content.installEventFilter(self)

        # Haupt-Zeile: Logo links | EPG-Infos rechts
        main_row = QHBoxLayout()
        main_row.setSpacing(12)
        main_row.setContentsMargins(0, 0, 0, 0)

        # Logo: QFrame als Hintergrund-Container, Label innen transparent
        # (Qt-Bug: background-color im QLabel-Stylesheet überdeckt setPixmap)
        _epg_logo_frame = QFrame()
        _epg_logo_frame.setFixedSize(64, 64)
        _epg_logo_frame.setStyleSheet("QFrame { background-color: rgba(255,255,255,6); border: 1px solid rgba(255,255,255,8); border-radius: 10px; }")
        _epg_logo_inner = QHBoxLayout(_epg_logo_frame)
        _epg_logo_inner.setContentsMargins(2, 2, 2, 2)
        _epg_logo_inner.setSpacing(0)
        self.epg_channel_logo = QLabel()
        self.epg_channel_logo.setAlignment(Qt.AlignCenter)
        self.epg_channel_logo.setStyleSheet("background: transparent;")
        _epg_logo_inner.addWidget(self.epg_channel_logo)
        main_row.addWidget(_epg_logo_frame, alignment=Qt.AlignTop)

        # Rechte Spalte: Sendername + EPG-Infos + Button unten
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_col.setContentsMargins(0, 0, 0, 0)

        self.epg_channel_name = QLabel("")
        self.epg_channel_name.setStyleSheet("font-size: 14px; font-weight: bold; color: #e8691a;")
        self.epg_channel_name.setWordWrap(False)
        right_col.addWidget(self.epg_channel_name)

        self.epg_now_label = QLabel(_tr("JETZT"))
        self.epg_now_label.setStyleSheet("font-size: 9px; font-weight: bold; color: #e8691a; letter-spacing: 1px;")
        right_col.addWidget(self.epg_now_label)

        self.epg_now_title = QLabel("")
        self.epg_now_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #eee;")
        self.epg_now_title.setWordWrap(True)
        self.epg_now_title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        right_col.addWidget(self.epg_now_title)

        self.epg_progress = QProgressBar()
        self.epg_progress.setFixedHeight(3)
        self.epg_progress.setTextVisible(False)
        self.epg_progress.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,8); border: none; border-radius: 1px; }
            QProgressBar::chunk { background: #e8691a; border-radius: 1px; }
        """)
        right_col.addWidget(self.epg_progress)

        # Beschreibung (versteckt)
        self.epg_now_desc = QLabel("")
        self.epg_now_desc.setStyleSheet("font-size: 13px; color: #888;")
        self.epg_now_desc.setWordWrap(True)
        self.epg_now_desc.hide()
        right_col.addWidget(self.epg_now_desc)

        self.epg_next_label = QLabel(_tr("DANACH"))
        self.epg_next_label.setStyleSheet("font-size: 9px; font-weight: bold; color: #555; letter-spacing: 1px;")
        right_col.addWidget(self.epg_next_label)

        self.epg_next_title = QLabel("")
        self.epg_next_title.setStyleSheet("font-size: 13px; color: #888;")
        self.epg_next_title.setWordWrap(True)
        self.epg_next_title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        right_col.addWidget(self.epg_next_title)

        right_col.addStretch()

        # EPG-Button ganz unten rechts
        self.btn_full_epg = QPushButton(_tr("EPG") + " \u25B8")
        self.btn_full_epg.setToolTip(_tr("Vollständiges Sendeprogramm anzeigen"))
        self.btn_full_epg.setFixedHeight(24)
        self.btn_full_epg.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.btn_full_epg.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #e8691a;
                border: 1px solid #e8691a;
                padding: 2px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #e8691a; color: white; }
            QPushButton:disabled { border-color: #333; color: #444; }
        """)
        self.btn_full_epg.clicked.connect(self._toggle_channel_detail)
        self.btn_full_epg.setEnabled(False)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_full_epg)
        right_col.addLayout(btn_row)

        main_row.addLayout(right_col, stretch=1)
        layout.addLayout(main_row)

        self._clear_epg_panel()

        return panel

    def _create_series_detail_page(self) -> QWidget:
        """Erstellt die Serien-Detailansicht mit Staffeln und Episoden"""
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: Zurueck-Button
        header = QFrame()
        header.setStyleSheet("background-color: rgba(8, 8, 20, 215); border-bottom: 1px solid rgba(255, 255, 255, 7);")
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        self.btn_series_back = QPushButton(_tr("\u2190 Zur\u00fcck"))
        self.btn_series_back.setStyleSheet("""
            QPushButton {
                background: transparent; color: #0078d4; border: none;
                font-size: 13px; padding: 4px 8px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #1a1a2a; color: #1094e8; }
        """)
        self.btn_series_back.clicked.connect(self._series_back)
        header_layout.addWidget(self.btn_series_back)
        header_layout.addStretch()
        layout.addWidget(header)

        # Hero: Cover links + Info rechts (volle Fensterbreite)
        hero = QFrame()
        hero.setStyleSheet("background-color: rgba(10, 10, 22, 215); border-bottom: 1px solid rgba(255, 255, 255, 7);")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(28, 28, 28, 28)
        hero_layout.setSpacing(28)

        # Grosses Cover
        self.series_cover_label = QLabel()
        self.series_cover_label.setFixedSize(200, 300)
        self.series_cover_label.setStyleSheet("""
            background-color: #1a1a2e;
            border-radius: 12px;
            border: 1px solid #2a2a4a;
            color: #2a2a4a;
            font-size: 52px;
        """)
        self.series_cover_label.setAlignment(Qt.AlignCenter)
        self.series_cover_label.setText("\u25B6")
        hero_layout.addWidget(self.series_cover_label, alignment=Qt.AlignTop)

        # Info-Spalte direkt im Hero
        info_col = QVBoxLayout()
        info_col.setSpacing(10)
        info_col.setContentsMargins(0, 4, 12, 4)

        self.series_title_label = QLabel("")
        self.series_title_label.setWordWrap(True)
        self.series_title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        info_col.addWidget(self.series_title_label)

        self.series_subtitle_label = QLabel("")
        self.series_subtitle_label.setStyleSheet("font-size: 12px; color: #666;")
        self.series_subtitle_label.setWordWrap(True)
        info_col.addWidget(self.series_subtitle_label)

        self.series_rating_label = QLabel("")
        self.series_rating_label.setStyleSheet("""
            font-size: 12px; font-weight: bold; color: #f0c040;
            background-color: #1e1c08; padding: 3px 10px;
            border-radius: 5px; border: 1px solid #3a3810;
        """)
        self.series_rating_label.hide()
        info_col.addWidget(self.series_rating_label, alignment=Qt.AlignLeft)

        info_col.addSpacing(4)

        # QTextEdit statt QLabel: scrollt intern wenn Text zu lang
        self.series_plot_label = QTextEdit()
        self.series_plot_label.setReadOnly(True)
        self.series_plot_label.setFrameShape(QFrame.NoFrame)
        self.series_plot_label.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.series_plot_label.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.series_plot_label.setStyleSheet("""
            QTextEdit {
                font-size: 14px; color: #aaa; background: transparent;
                border: none; padding: 0px;
            }
            QScrollBar:vertical { background: #0f0f1a; width: 5px; }
            QScrollBar::handle:vertical { background: #2a2a3a; border-radius: 2px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        info_col.addWidget(self.series_plot_label, stretch=1)

        hero_layout.addLayout(info_col)
        layout.addWidget(hero)

        # Season-Bar: Dropdown + Trailer-Button ganz links unter dem Hero
        season_bar = QFrame()
        season_bar.setFixedHeight(48)
        season_bar.setStyleSheet("background-color: rgba(8, 8, 20, 215); border-bottom: 1px solid rgba(255, 255, 255, 7);")
        season_layout = QHBoxLayout(season_bar)
        season_layout.setContentsMargins(20, 0, 20, 0)
        season_layout.setSpacing(12)

        self.season_combo = QComboBox()
        self.season_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 16px; background: #1a1a2a;
                border: 1px solid #2a2a3a; border-radius: 14px;
                color: #ccc; font-size: 13px; min-width: 140px;
            }
            QComboBox:hover { border-color: #0078d4; color: white; }
            QComboBox::drop-down { border: none; padding-right: 8px; }
            QComboBox QAbstractItemView {
                background: #1a1a2a; color: white;
                selection-background-color: #0078d4;
                border: 1px solid #2a2a3a;
            }
        """)
        self.season_combo.currentIndexChanged.connect(self._on_season_changed)
        season_layout.addWidget(self.season_combo)

        self.btn_series_trailer = QPushButton(_tr("Trailer"))
        self.btn_series_trailer.setStyleSheet("""
            QPushButton {
                background: transparent; color: #0078d4; border: 1px solid #0078d4;
                padding: 6px 20px; border-radius: 14px; font-size: 13px;
            }
            QPushButton:hover { background-color: #0078d4; color: white; }
        """)
        self.btn_series_trailer.clicked.connect(self._play_series_trailer)
        self.btn_series_trailer.hide()
        season_layout.addWidget(self.btn_series_trailer)

        season_layout.addStretch()
        layout.addWidget(season_bar)

        # Episoden-Liste (volle Breite, scrollbar)
        self.episode_list = QListWidget()
        self.episode_list.setStyleSheet("""
            QListWidget {
                background-color: transparent; border: none; outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #111120;
                padding: 0px;
            }
            QListWidget::item:hover { background-color: #111120; }
            QListWidget::item:selected { background-color: #0a1e33; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: #2a2a3a; border-radius: 3px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.episode_list.setMouseTracking(True)
        self.episode_list.itemClicked.connect(self._on_episode_selected)
        layout.addWidget(self.episode_list, stretch=1)

        # Serien-Daten-Cache
        self._series_data: dict | None = None
        self._current_series = None

        return page

    def _create_vod_detail_page(self) -> QWidget:
        """Erstellt die VOD-Detailansicht im Streaming-App-Style"""
        page = QWidget()
        page.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: Zurueck-Button
        header = QFrame()
        header.setStyleSheet("background-color: rgba(8, 8, 20, 215); border-bottom: 1px solid rgba(255, 255, 255, 7);")
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)

        self.btn_vod_back = QPushButton(_tr("\u2190 Zur\u00fcck"))
        self.btn_vod_back.setStyleSheet("""
            QPushButton {
                background: transparent; color: #0078d4; border: none;
                font-size: 13px; padding: 4px 8px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #1a1a2a; color: #1094e8; }
        """)
        self.btn_vod_back.clicked.connect(self._vod_back)
        header_layout.addWidget(self.btn_vod_back)

        self.vod_title_label = QLabel("")
        self.vod_title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
        header_layout.addWidget(self.vod_title_label, stretch=1)
        layout.addWidget(header)

        # Ladebalken (indeterminate, erscheint während Infos/Cover laden)
        self.vod_loading_bar = QProgressBar()
        self.vod_loading_bar.setRange(0, 0)
        self.vod_loading_bar.setFixedHeight(3)
        self.vod_loading_bar.setTextVisible(False)
        self.vod_loading_bar.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,8); border: none; }
            QProgressBar::chunk { background: #0078d4; }
        """)
        self.vod_loading_bar.hide()
        layout.addWidget(self.vod_loading_bar)

        # Scrollbarer Inhaltsbereich
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { background: transparent; width: 8px; }
            QScrollBar::handle:vertical { background: #333; border-radius: 4px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # === Hero-Bereich: Poster + Infos nebeneinander ===
        hero = QFrame()
        hero.setStyleSheet("background-color: rgba(255, 255, 255, 3);")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_layout.setSpacing(24)

        # Grosses Poster (links)
        self.vod_cover_label = QLabel()
        self.vod_cover_label.setFixedSize(220, 330)
        self.vod_cover_label.setStyleSheet("""
            background-color: rgba(255, 255, 255, 6);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 10);
            color: #333;
            font-size: 48px;
        """)
        self.vod_cover_label.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(self.vod_cover_label, alignment=Qt.AlignTop)

        # Rechts: Titel, Ratings, Meta, Buttons
        info_layout = QVBoxLayout()
        info_layout.setSpacing(12)

        # Filmtitel gross
        self.vod_hero_title = QLabel("")
        self.vod_hero_title.setWordWrap(True)
        self.vod_hero_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff;")
        info_layout.addWidget(self.vod_hero_title)

        # Untertitel-Zeile: Jahr, Dauer, Genre
        self.vod_subtitle_label = QLabel("")
        self.vod_subtitle_label.setStyleSheet("font-size: 13px; color: #888;")
        info_layout.addWidget(self.vod_subtitle_label)

        # Rating-Badges
        self.vod_ratings_widget = QWidget()
        self.vod_ratings_layout = QHBoxLayout(self.vod_ratings_widget)
        self.vod_ratings_layout.setContentsMargins(0, 4, 0, 4)
        self.vod_ratings_layout.setSpacing(10)
        self.vod_ratings_layout.addStretch()
        info_layout.addWidget(self.vod_ratings_widget)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_play_vod = QPushButton(_tr("\u25B6\uFE0E  Abspielen"))
        self.btn_play_vod.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: white; border: none;
                padding: 12px 36px; border-radius: 8px;
                font-size: 15px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1094e8; }
        """)
        self.btn_play_vod.clicked.connect(self._play_current_vod)
        btn_layout.addWidget(self.btn_play_vod)

        self.btn_trailer = QPushButton(_tr("Trailer"))
        self.btn_trailer.setStyleSheet("""
            QPushButton {
                background: transparent; color: #0078d4; border: 1px solid #0078d4;
                padding: 12px 28px; border-radius: 8px; font-size: 15px;
            }
            QPushButton:hover { background-color: #0078d4; color: white; }
        """)
        self.btn_trailer.clicked.connect(self._play_trailer)
        self.btn_trailer.hide()
        btn_layout.addWidget(self.btn_trailer)
        btn_layout.addStretch()
        info_layout.addLayout(btn_layout)

        info_layout.addStretch()
        hero_layout.addLayout(info_layout, stretch=1)
        content_layout.addWidget(hero)

        # === Trennlinie ===
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,6);")
        content_layout.addWidget(sep)

        # === Details-Bereich ===
        details = QWidget()
        details.setStyleSheet("background-color: transparent;")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(24, 20, 24, 20)
        details_layout.setSpacing(20)

        # Genre-Tags
        self.vod_genre_widget = QWidget()
        self.vod_genre_layout = QHBoxLayout(self.vod_genre_widget)
        self.vod_genre_layout.setContentsMargins(0, 0, 0, 0)
        self.vod_genre_layout.setSpacing(8)
        self.vod_genre_layout.addStretch()
        self.vod_genre_widget.hide()
        details_layout.addWidget(self.vod_genre_widget)

        # Handlung
        self.vod_plot_header = QLabel(_tr("Handlung"))
        self.vod_plot_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #eee;")
        self.vod_plot_header.hide()
        details_layout.addWidget(self.vod_plot_header)

        self.vod_plot_label = QLabel("")
        self.vod_plot_label.setWordWrap(True)
        self.vod_plot_label.setStyleSheet("color: #ccc; font-size: 14px; line-height: 1.6;")
        self.vod_plot_label.setAlignment(Qt.AlignTop)
        details_layout.addWidget(self.vod_plot_label)

        # Regie
        self.vod_director_widget = QWidget()
        self.vod_director_widget.hide()
        dir_layout = QVBoxLayout(self.vod_director_widget)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(8)
        dir_header = QLabel(_tr("Regie"))
        dir_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #eee;")
        dir_layout.addWidget(dir_header)
        self.vod_director_label = QLabel("")
        self.vod_director_label.setStyleSheet("color: #bbb; font-size: 14px;")
        dir_layout.addWidget(self.vod_director_label)
        details_layout.addWidget(self.vod_director_widget)

        # Besetzung
        self.vod_cast_widget = QWidget()
        self.vod_cast_widget.hide()
        cast_outer = QVBoxLayout(self.vod_cast_widget)
        cast_outer.setContentsMargins(0, 0, 0, 0)
        cast_outer.setSpacing(10)
        cast_header = QLabel(_tr("Besetzung"))
        cast_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #eee;")
        cast_outer.addWidget(cast_header)
        # Flow-Layout fuer Schauspieler-Chips
        self.vod_cast_flow = QWidget()
        self.vod_cast_flow_layout = FlowLayout(self.vod_cast_flow, margin=0, spacing=8)
        cast_outer.addWidget(self.vod_cast_flow)
        details_layout.addWidget(self.vod_cast_widget)

        details_layout.addStretch()
        content_layout.addWidget(details, stretch=1)

        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        # Versteckte Labels fuer Kompatibilitaet
        self.vod_rating_label = QLabel("")
        self.vod_meta_label = QLabel("")

        # VOD-Daten-Cache
        self._current_vod = None
        self._current_trailer_url: str = ""

        return page

    def _create_player_area(self) -> QWidget:
        """Erstellt den Playerbereich mit Header, Video und Controls"""
        from player_widget import MpvPlayerWidget

        area = QWidget()
        area.setObjectName("playerArea")
        area.setStyleSheet("#playerArea { background-color: #000; }")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Player-Header (Titel + Close)
        self.player_header = QWidget()
        self.player_header.setStyleSheet("background-color: rgba(8, 8, 20, 215); border-bottom: 1px solid rgba(255, 255, 255, 7);")
        self.player_header.setFixedHeight(32)
        header_layout = QHBoxLayout(self.player_header)
        header_layout.setContentsMargins(10, 0, 6, 0)

        self.player_channel_logo = QLabel()
        self.player_channel_logo.setFixedSize(22, 22)
        self.player_channel_logo.setAlignment(Qt.AlignCenter)
        self.player_channel_logo.setStyleSheet("background: transparent;")
        self.player_channel_logo.hide()
        header_layout.addWidget(self.player_channel_logo)
        header_layout.addSpacing(6)

        self.player_title = QLabel("")
        self.player_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #ccc;")
        header_layout.addWidget(self.player_title)
        header_layout.addStretch()

        layout.addWidget(self.player_header)

        # Video + Info-Panel
        player_layout = QHBoxLayout()
        player_layout.setContentsMargins(0, 0, 0, 0)
        player_layout.setSpacing(0)

        # Player + Buffering-Overlay in Container
        player_container = QWidget()
        player_container.setStyleSheet("background: black;")
        pc_layout = QVBoxLayout(player_container)
        pc_layout.setContentsMargins(0, 0, 0, 0)
        pc_layout.setSpacing(0)

        self.player = MpvPlayerWidget(
            hwdec=self.app_settings.get("hwdec", "auto"),
            buffer_secs=self.app_settings.get("buffer_secs", 4),
        )
        self.player.double_clicked.connect(self._toggle_player_maximized)
        self.player.escape_pressed.connect(self._on_player_escape)
        self.player.buffering_changed.connect(self._on_buffering)
        pc_layout.addWidget(self.player)

        # Buffering-Overlay
        self.buffering_overlay = QLabel(_tr("Laden..."))
        self.buffering_overlay.setAlignment(Qt.AlignCenter)
        self.buffering_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: #e8691a;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.buffering_overlay.hide()
        self.buffering_overlay.setParent(player_container)

        player_container.setMouseTracking(True)
        self.player_container = player_container
        self.fullscreen_controls = self._create_fullscreen_controls_overlay(player_container)
        # Windows: QOpenGLWidget ist ein natives Child-Window und liegt sonst immer
        # über normalen Sibling-Widgets. WA_NativeWindow gibt dem Overlay ein eigenes
        # HWND, damit Windows die Z-Reihenfolge korrekt über raise_() verwalten kann.
        if sys.platform == "win32":
            self.fullscreen_controls.setAttribute(Qt.WA_NativeWindow)
        self._fs_controls_timer = QTimer()
        self._fs_controls_timer.setSingleShot(True)
        self._fs_controls_timer.timeout.connect(self._hide_fullscreen_controls)

        # Info-Overlay: groß Logo + aktuelle Sendung, erscheint beim Hover
        self.info_overlay = QWidget(player_container)
        self.info_overlay.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(0,0,0,0), stop:0.35 rgba(0,0,0,155), stop:1 rgba(0,0,0,220));
        """)
        self.info_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.info_overlay.hide()
        _ov_layout = QHBoxLayout(self.info_overlay)
        _ov_layout.setContentsMargins(24, 18, 24, 18)
        _ov_layout.setSpacing(20)

        # Großes Senderlogo links
        self.overlay_logo = QLabel()
        self.overlay_logo.setFixedSize(120, 120)
        self.overlay_logo.setAlignment(Qt.AlignCenter)
        self.overlay_logo.setStyleSheet("background: transparent;")
        _ov_layout.addWidget(self.overlay_logo, alignment=Qt.AlignVCenter)

        # Rechte Spalte: Sendername + JETZT/DANACH-Zeilen
        _ov_text = QVBoxLayout()
        _ov_text.setSpacing(5)
        _ov_text.setContentsMargins(0, 0, 0, 0)
        _ov_text.addStretch()

        self.overlay_channel_name = QLabel()
        self.overlay_channel_name.setStyleSheet(
            "color: #e8691a; font-size: 12px; font-weight: bold; background: transparent;"
        )
        _ov_text.addWidget(self.overlay_channel_name)

        # JETZT-Zeile
        _now_row = QHBoxLayout()
        _now_row.setSpacing(10)
        _now_row.setContentsMargins(0, 0, 0, 0)
        _now_lbl = QLabel("JETZT")
        _now_lbl.setStyleSheet(
            "color: #e8691a; font-size: 9px; font-weight: bold; letter-spacing: 1px; background: transparent;"
        )
        _now_lbl.setFixedWidth(46)
        _now_row.addWidget(_now_lbl, alignment=Qt.AlignVCenter)
        self.overlay_now_title = QLabel()
        self.overlay_now_title.setStyleSheet(
            "color: #fff; font-size: 17px; font-weight: bold; background: transparent;"
        )
        _now_row.addWidget(self.overlay_now_title, stretch=1)
        _ov_text.addLayout(_now_row)

        # DANACH-Zeile
        _next_row = QHBoxLayout()
        _next_row.setSpacing(10)
        _next_row.setContentsMargins(0, 0, 0, 0)
        _next_lbl = QLabel("DANACH")
        _next_lbl.setStyleSheet(
            "color: #888; font-size: 9px; font-weight: bold; letter-spacing: 1px; background: transparent;"
        )
        _next_lbl.setFixedWidth(46)
        _next_row.addWidget(_next_lbl, alignment=Qt.AlignVCenter)
        self.overlay_next_title = QLabel()
        self.overlay_next_title.setStyleSheet(
            "color: #aaa; font-size: 14px; background: transparent;"
        )
        _next_row.addWidget(self.overlay_next_title, stretch=1)
        _ov_text.addLayout(_next_row)

        _ov_text.addStretch()
        _ov_layout.addLayout(_ov_text, stretch=1)

        self._info_overlay_timer = QTimer()
        self._info_overlay_timer.setSingleShot(True)
        self._info_overlay_timer.timeout.connect(self._hide_info_overlay)

        self._buffering_watchdog = QTimer()
        self._buffering_watchdog.setSingleShot(True)
        self._buffering_watchdog.timeout.connect(self._on_buffering_timeout)


        self._reconnect_timer = QTimer()
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._do_reconnect)

        # Sicherheitsnetz: _stream_starting wird nach 5s automatisch aufgehoben
        self._stream_start_timer = QTimer()
        self._stream_start_timer.setSingleShot(True)
        self._stream_start_timer.timeout.connect(self._clear_stream_starting)

        self.player.stream_ended.connect(self._on_stream_ended)
        self.player.gl_context_recreated.connect(self._on_gl_context_recreated)
        self.player.stream_specs_detected.connect(self._on_stream_specs_detected)

        player_container.setMouseTracking(True)
        self.player.setMouseTracking(True)
        player_container.installEventFilter(self)

        player_layout.addWidget(player_container, stretch=1)

        self.stream_info_panel = self._create_stream_info_panel()
        self.stream_info_panel.setParent(self.player_container)
        self.stream_info_panel.hide()

        layout.addLayout(player_layout, stretch=1)

        # EPG-Zeile fuer Live-Streams (Slider + Catchup-Button)
        self.live_epg_bar = self._create_live_epg_bar()
        layout.addWidget(self.live_epg_bar)

        # Player-Controls
        self.player_controls = self._create_player_controls()
        layout.addWidget(self.player_controls)

        # Timer fuer Controls und Stream-Info
        self.stream_info_timer = QTimer()
        self.stream_info_timer.timeout.connect(self._update_stream_info)

        self._stream_info_hide_timer = QTimer()
        self._stream_info_hide_timer.setSingleShot(True)
        self._stream_info_hide_timer.timeout.connect(self._auto_hide_stream_info)

        self.controls_timer = QTimer()
        self.controls_timer.timeout.connect(self._update_player_controls)

        self._buffering_dots = 0
        self._buffering_timer = QTimer()
        self._buffering_timer.timeout.connect(self._animate_buffering)

        self._buffering_show_timer = QTimer()
        self._buffering_show_timer.setSingleShot(True)
        self._buffering_show_timer.timeout.connect(self._show_buffering_overlay)

        # PiP-Kontrollleiste (schwebt oben im PiP-Fenster, nur im PiP-Modus)
        self.pip_bar = QFrame(area)
        self.pip_bar.setObjectName("pipBar")
        self.pip_bar.setStyleSheet("""
            QFrame#pipBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0,0,0,210), stop:1 rgba(0,0,0,0));
                border: none;
            }
        """)
        _pip_layout = QHBoxLayout(self.pip_bar)
        _pip_layout.setContentsMargins(8, 6, 4, 10)
        _pip_layout.setSpacing(2)

        self.pip_title_label = QLabel("")
        self.pip_title_label.setStyleSheet(
            "color: rgba(255,255,255,200); font-size: 10pt; background: transparent;"
        )
        _pip_layout.addWidget(self.pip_title_label, stretch=1)

        _pip_font = QFont()
        _pip_font.setPointSize(11)
        _pip_btn_base = """
            QPushButton {
                background: transparent; color: white; border: none;
                border-radius: 4px; padding: 0px;
            }
        """

        self.pip_expand_btn = QPushButton()
        self.pip_expand_btn.setIcon(_pi("maximize2.svg", 14))
        self.pip_expand_btn.setIconSize(QSize(14, 14))
        self.pip_expand_btn.setFixedSize(28, 26)
        self.pip_expand_btn.setToolTip(_tr("Vergrößern"))
        self.pip_expand_btn.setStyleSheet(
            _pip_btn_base +
            "QPushButton:hover { background: rgba(50,180,50,180); border-radius: 4px; }"
        )
        self.pip_expand_btn.clicked.connect(self._on_pip_expand)
        _pip_layout.addWidget(self.pip_expand_btn)

        self.pip_close_btn = QPushButton()
        self.pip_close_btn.setIcon(_svg_icon("x.svg", 14, bright=True))
        self.pip_close_btn.setIconSize(QSize(14, 14))
        self.pip_close_btn.setFixedSize(28, 26)
        self.pip_close_btn.setToolTip(_tr("Wiedergabe beenden"))
        self.pip_close_btn.setStyleSheet(
            _pip_btn_base +
            "QPushButton:hover { background: rgba(220,50,50,200); border-radius: 4px; }"
        )
        self.pip_close_btn.clicked.connect(self._stop_playback)
        _pip_layout.addWidget(self.pip_close_btn)

        self.pip_bar.hide()

        return area

    def _create_live_epg_bar(self) -> QWidget:
        """EPG-Fortschrittszeile fuer Live-Streams (zwischen Video und Controls)"""
        bar = QWidget()
        bar.setFixedHeight(38)
        bar.setStyleSheet("background: rgba(8, 8, 20, 215); border-top: 1px solid rgba(255, 255, 255, 7);")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # Exakt derselbe Stil wie aktiver Sidebar-Button (blauer Gradient + linker Akzent)
        _epg_btn_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 120, 212, 55), stop:1 rgba(80, 40, 200, 28));
                border: none;
                border-left: 3px solid #0078d4;
                border-radius: 8px;
                padding: 0px 14px;
                color: white;
                font-size: 12px; font-weight: 600;
                text-align: center;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 120, 212, 80), stop:1 rgba(80, 40, 200, 50));
            }
        """
        _epg_icon_size = QSize(16, 16)

        self.live_epg_von_anfang_btn = QPushButton(" " + _tr("Anfang"))
        self.live_epg_von_anfang_btn.setIcon(_pi("refresh.svg", 16))
        self.live_epg_von_anfang_btn.setIconSize(_epg_icon_size)
        self.live_epg_von_anfang_btn.setFixedHeight(28)
        self.live_epg_von_anfang_btn.setStyleSheet(_epg_btn_style)
        self.live_epg_von_anfang_btn.clicked.connect(self._live_play_von_anfang)
        self.live_epg_von_anfang_btn.hide()
        layout.addWidget(self.live_epg_von_anfang_btn)

        self.live_epg_catchup_btn = QPushButton(" " + _tr("Catchup"))
        self.live_epg_catchup_btn.setIcon(_pi("catchup.svg", 16))
        self.live_epg_catchup_btn.setIconSize(_epg_icon_size)
        self.live_epg_catchup_btn.setFixedHeight(28)
        self.live_epg_catchup_btn.setStyleSheet(_epg_btn_style)
        self.live_epg_catchup_btn.clicked.connect(self._show_full_epg)
        self.live_epg_catchup_btn.hide()
        layout.addWidget(self.live_epg_catchup_btn)

        self.live_epg_epg_btn = QPushButton(" " + _tr("EPG"))
        self.live_epg_epg_btn.setIcon(_pi("clock.svg", 16))
        self.live_epg_epg_btn.setIconSize(_epg_icon_size)
        self.live_epg_epg_btn.setFixedHeight(28)
        self.live_epg_epg_btn.setStyleSheet(_epg_btn_style)
        self.live_epg_epg_btn.clicked.connect(self._toggle_channel_detail)
        layout.addWidget(self.live_epg_epg_btn)

        self.live_epg_seek_slider = ClickSlider(Qt.Horizontal)
        self.live_epg_seek_slider.setRange(0, 1000)
        self.live_epg_seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1e1e2e; height: 4px; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #e8691a; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QSlider::sub-page:horizontal { background: #e8691a; border-radius: 2px; }
        """)
        self.live_epg_seek_slider.sliderPressed.connect(
            lambda: setattr(self, '_live_epg_seeking', True))
        self.live_epg_seek_slider.sliderReleased.connect(self._on_live_epg_seek_released)
        self.live_epg_seek_slider.hide()
        layout.addWidget(self.live_epg_seek_slider, stretch=1)

        self.live_epg_progress = QProgressBar()
        self.live_epg_progress.setFixedHeight(4)
        self.live_epg_progress.setTextVisible(False)
        self.live_epg_progress.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,8); border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #e8691a; border-radius: 2px; }
        """)
        self.live_epg_progress.hide()
        layout.addWidget(self.live_epg_progress, stretch=1)

        bar.hide()
        return bar

    def _create_player_controls(self) -> QWidget:
        """Erstellt die Player-Steuerleiste"""
        bar = QFrame()
        bar.setFixedHeight(50)
        bar.setStyleSheet("""
            QFrame#controlBar {
                background-color: rgba(8, 8, 20, 220);
                border-top: 1px solid rgba(255, 255, 255, 7);
            }
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 10); }
            QPushButton#recordBtn:checked { background: rgba(255, 68, 68, 18); }
            QPushButton#recordBtn:checked:hover { background: rgba(255, 68, 68, 35); }
        """)
        bar.setObjectName("controlBar")

        _CTRL_ICON = 20   # transport buttons
        _SIDE_ICON = 17   # secondary (audio/sub/info/zoom)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(4)

        # --- transport icons pre-built and stored for runtime icon-swap ---
        self._icon_play  = _pi("play.svg",  _CTRL_ICON)
        self._icon_pause = _pi("pause.svg", _CTRL_ICON)

        # Play/Pause
        self.btn_play_pause = QPushButton()
        self.btn_play_pause.setIcon(self._icon_play)
        self.btn_play_pause.setIconSize(QSize(_CTRL_ICON, _CTRL_ICON))
        self.btn_play_pause.setFixedSize(36, 36)
        self.btn_play_pause.setToolTip(_tr("Play / Pause  (Leertaste)"))
        self.btn_play_pause.clicked.connect(self._toggle_play_pause)
        layout.addWidget(self.btn_play_pause)

        # Stop
        self.btn_stop_controls = QPushButton()
        self.btn_stop_controls.setIcon(_pi("square.svg", _CTRL_ICON))
        self.btn_stop_controls.setIconSize(QSize(_CTRL_ICON, _CTRL_ICON))
        self.btn_stop_controls.setFixedSize(36, 36)
        self.btn_stop_controls.setToolTip("Stop")
        self.btn_stop_controls.clicked.connect(self._stop_playback)
        layout.addWidget(self.btn_stop_controls)

        # Aufnahme
        self.btn_record = QPushButton()
        self.btn_record.setObjectName("recordBtn")
        self.btn_record.setCheckable(True)
        self.btn_record.setIcon(_pi_colored("record.svg", _CTRL_ICON - 2, "#ff4444"))
        self.btn_record.setIconSize(QSize(_CTRL_ICON - 2, _CTRL_ICON - 2))
        self.btn_record.setFixedSize(36, 36)
        self.btn_record.setToolTip(_tr("Aufnahme starten / stoppen"))
        self.btn_record.clicked.connect(self._toggle_recording)
        layout.addWidget(self.btn_record)

        # Zap-Buttons (Kanal zurück/vor)
        self.btn_zap_prev = QPushButton()
        self.btn_zap_prev.setIcon(_pi("chevron-left.svg", _CTRL_ICON))
        self.btn_zap_prev.setIconSize(QSize(_CTRL_ICON, _CTRL_ICON))
        self.btn_zap_prev.setFixedSize(32, 32)
        self.btn_zap_prev.setToolTip(_tr("Vorheriger Kanal"))
        self.btn_zap_prev.clicked.connect(self._zap_prev)
        self.btn_zap_prev.hide()
        layout.addWidget(self.btn_zap_prev)

        self.btn_zap_next = QPushButton()
        self.btn_zap_next.setIcon(_pi("chevron-right.svg", _CTRL_ICON))
        self.btn_zap_next.setIconSize(QSize(_CTRL_ICON, _CTRL_ICON))
        self.btn_zap_next.setFixedSize(32, 32)
        self.btn_zap_next.setToolTip(_tr("Nächster Kanal"))
        self.btn_zap_next.clicked.connect(self._zap_next)
        self.btn_zap_next.hide()
        layout.addWidget(self.btn_zap_next)

        # Skip-Buttons
        self.btn_skip_back = QPushButton()
        self.btn_skip_back.setIcon(_pi("rewind.svg", _CTRL_ICON))
        self.btn_skip_back.setIconSize(QSize(_CTRL_ICON, _CTRL_ICON))
        self.btn_skip_back.setFixedSize(36, 36)
        self.btn_skip_back.setToolTip("−30 Sekunden")
        self.btn_skip_back.clicked.connect(lambda: self._skip_seconds(-30))
        layout.addWidget(self.btn_skip_back)

        self.btn_skip_forward = QPushButton()
        self.btn_skip_forward.setIcon(_pi("fast-forward.svg", _CTRL_ICON))
        self.btn_skip_forward.setIconSize(QSize(_CTRL_ICON, _CTRL_ICON))
        self.btn_skip_forward.setFixedSize(36, 36)
        self.btn_skip_forward.setToolTip("+30 Sekunden")
        self.btn_skip_forward.clicked.connect(lambda: self._skip_seconds(30))
        layout.addWidget(self.btn_skip_forward)

        # Separator
        _sep = lambda: (lambda s: (s.setFrameShape(QFrame.VLine), s.setFixedHeight(20),
                         s.setStyleSheet("QFrame{color:rgba(255,255,255,12);}")))(QFrame())
        sep1 = QFrame(); sep1.setFrameShape(QFrame.VLine)
        sep1.setFixedHeight(20); sep1.setStyleSheet("QFrame{color:rgba(255,255,255,12);}")
        layout.addWidget(sep1)

        # Lautstärke-Icon + Slider (klickbar zum Muten)
        self._px_vol        = _pi("volume-2.svg", 16).pixmap(QSize(16, 16))
        self._px_vol_muted  = _pi("volume-x.svg", 16).pixmap(QSize(16, 16))
        self.vol_mute_btn = QLabel()
        self.vol_mute_btn.setPixmap(self._px_vol)
        self.vol_mute_btn.setFixedSize(20, 20)
        self.vol_mute_btn.setStyleSheet("background: transparent;")
        self.vol_mute_btn.setCursor(Qt.PointingHandCursor)
        self.vol_mute_btn.mousePressEvent = lambda e: self._toggle_mute()
        layout.addWidget(self.vol_mute_btn)

        self.volume_slider = ClickSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(88)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: rgba(255,255,255,15); height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #e8691a; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::sub-page:horizontal { background: #e8691a; border-radius: 2px; }
        """)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(self.volume_slider)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedHeight(20); sep2.setStyleSheet("QFrame{color:rgba(255,255,255,12);}")
        layout.addWidget(sep2)

        # Positions-Label
        self.player_pos_label = QLabel("00:00")
        self.player_pos_label.setFixedWidth(48)
        self.player_pos_label.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        self.player_pos_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.player_pos_label)

        # Seek-Slider
        self._seeking = False
        self.seek_slider = ClickSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: rgba(255,255,255,15); height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #e8691a; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::sub-page:horizontal { background: #e8691a; border-radius: 2px; }
        """)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        layout.addWidget(self.seek_slider, stretch=1)

        # Dauer-Label
        self.player_dur_label = QLabel("00:00")
        self.player_dur_label.setFixedWidth(48)
        self.player_dur_label.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        layout.addWidget(self.player_dur_label)

        self.player_info_label = QLabel("")  # Kompatibilitäts-Platzhalter
        layout.addStretch(1)

        # LIVE-Badge
        self.btn_go_live = QPushButton("LIVE")
        self.btn_go_live.setFixedHeight(24)
        self.btn_go_live.setStyleSheet("""
            QPushButton {
                background: rgba(232,105,26,12); color: #e8691a;
                border: 1px solid rgba(232,105,26,160); padding: 0px 12px;
                border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 1px;
            }
            QPushButton:hover { background: rgba(232,105,26,30); border-color: #e8691a; }
        """)
        self.btn_go_live.clicked.connect(self._go_live)
        self.btn_go_live.hide()
        layout.addWidget(self.btn_go_live)

        sep3 = QFrame(); sep3.setFrameShape(QFrame.VLine)
        sep3.setFixedHeight(20); sep3.setStyleSheet("QFrame{color:rgba(255,255,255,12);}")
        layout.addWidget(sep3)

        # Secondary icon buttons (Audio / Sub / Info / Zoom)
        _pill_style = """
            QPushButton {
                background: transparent; border: 1px solid rgba(255,255,255,10);
                border-radius: 6px; padding: 2px 8px; color: #888; font-size: 11px;
            }
            QPushButton:hover { border-color: rgba(255,255,255,25); color: #ccc; }
            QPushButton:checked { border-color: rgba(232,105,26,180); color: #e8691a; }
        """

        self.btn_audio = QPushButton()
        self.btn_audio.setIcon(_pi("headphones.svg", _SIDE_ICON))
        self.btn_audio.setIconSize(QSize(_SIDE_ICON, _SIDE_ICON))
        self.btn_audio.setFixedSize(32, 32)
        self.btn_audio.setToolTip(_tr("Tonspur w\u00e4hlen"))
        self.btn_audio.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 6px; padding: 4px; }
            QPushButton:hover { background: rgba(255,255,255,10); }
        """)
        self.btn_audio.clicked.connect(self._show_audio_menu)
        layout.addWidget(self.btn_audio)

        self.btn_subtitle = QPushButton()
        self.btn_subtitle.setIcon(_pi("captions.svg", _SIDE_ICON))
        self.btn_subtitle.setIconSize(QSize(_SIDE_ICON, _SIDE_ICON))
        self.btn_subtitle.setFixedSize(32, 32)
        self.btn_subtitle.setToolTip(_tr("Untertitel w\u00e4hlen"))
        self.btn_subtitle.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 6px; padding: 4px; }
            QPushButton:hover { background: rgba(255,255,255,10); }
        """)
        self.btn_subtitle.clicked.connect(self._show_subtitle_menu)
        layout.addWidget(self.btn_subtitle)

        self.btn_stream_info = QPushButton()
        self.btn_stream_info.setCheckable(True)
        self.btn_stream_info.setIcon(_pi_colored("info.svg", _SIDE_ICON, "#e8691a"))
        self.btn_stream_info.setIconSize(QSize(_SIDE_ICON, _SIDE_ICON))
        self.btn_stream_info.setFixedSize(32, 32)
        self.btn_stream_info.setToolTip(_tr("Stream-Info"))
        self.btn_stream_info.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 6px; padding: 4px; }
            QPushButton:hover { background: rgba(255,255,255,10); }
            QPushButton:checked { background: rgba(232,105,26,15); }
        """)
        self.btn_stream_info.clicked.connect(self._toggle_stream_info)
        layout.addWidget(self.btn_stream_info)

        self.btn_zoom = QPushButton()
        self.btn_zoom.setIcon(_pi("crop.svg", _SIDE_ICON))
        self.btn_zoom.setIconSize(QSize(_SIDE_ICON, _SIDE_ICON))
        self.btn_zoom.setFixedSize(32, 32)
        self.btn_zoom.setToolTip(_tr("Seitenverh\u00e4ltnis: Normal \u2192 Fill \u2192 Stretch"))
        self.btn_zoom.setStyleSheet("""
            QPushButton { background: transparent; border: none; border-radius: 6px; padding: 4px; }
            QPushButton:hover { background: rgba(255,255,255,10); }
        """)
        self.btn_zoom.clicked.connect(self._cycle_zoom_mode)
        layout.addWidget(self.btn_zoom)

        sep4 = QFrame(); sep4.setFrameShape(QFrame.VLine)
        sep4.setFixedHeight(20); sep4.setStyleSheet("QFrame{color:rgba(255,255,255,12);}")
        layout.addWidget(sep4)

        # Vollbild
        self.btn_fullscreen = QPushButton()
        self.btn_fullscreen.setIcon(_pi("maximize.svg", _CTRL_ICON))
        self.btn_fullscreen.setIconSize(QSize(_CTRL_ICON, _CTRL_ICON))
        self.btn_fullscreen.setFixedSize(36, 36)
        self.btn_fullscreen.setToolTip(_tr("Vollbild  (F / Doppelklick)"))
        self.btn_fullscreen.clicked.connect(self._toggle_player_maximized)
        layout.addWidget(self.btn_fullscreen)

        return bar

    def _create_fullscreen_controls_overlay(self, parent: QWidget) -> QWidget:
        """Vollbild-Kontrollleiste als Auto-Hide-Overlay"""
        overlay = QFrame(parent)
        overlay.setObjectName("fsControls")
        overlay.setStyleSheet("""
            #fsControls {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
                    stop:0 rgba(0, 0, 0, 240),
                    stop:0.7 rgba(0, 0, 0, 210),
                    stop:1 rgba(0, 0, 0, 80));
                border: none;
            }
            QPushButton {
                background: transparent;
                color: #ddd;
                border: none;
                font-size: 16px;
                padding: 6px 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 25); color: white; }
            QPushButton#fsRecordBtn { color: #ccc; }
            QPushButton#fsRecordBtn:checked { color: #ff4444; background: rgba(255, 68, 68, 30); }
            QPushButton#fsRecordBtn:checked:hover { background: rgba(255, 68, 68, 60); }
            QLabel {
                color: #ddd;
                font-size: 12px;
                background: transparent;
            }
            QSlider {
                background: transparent;
            }
            QProgressBar {
                background: rgba(255, 255, 255, 30);
                border: none;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background: #e8691a;
                border-radius: 1px;
            }
        """)

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 0, 20, 16)
        layout.setSpacing(8)
        layout.addStretch()

        # Info-Sektion: Kanallogo + Name + EPG (wird bei Mausbewegung befüllt)
        fs_info_section = QWidget()
        fs_info_section.setStyleSheet("background: transparent;")
        info_layout = QHBoxLayout(fs_info_section)
        info_layout.setContentsMargins(0, 0, 0, 4)
        info_layout.setSpacing(12)

        self.fs_channel_logo = QLabel()
        self.fs_channel_logo.setFixedSize(120, 120)
        self.fs_channel_logo.setStyleSheet("background: transparent;")
        self.fs_channel_logo.setAlignment(Qt.AlignCenter)
        self.fs_channel_logo.hide()
        info_layout.addWidget(self.fs_channel_logo)

        fs_text_col = QWidget()
        fs_text_col.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(fs_text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        self.fs_channel_title = QLabel("")
        self.fs_channel_title.setStyleSheet("font-size: 22px; font-weight: bold; color: white; background: transparent;")
        text_layout.addWidget(self.fs_channel_title)

        self.fs_epg_now = QLabel("")
        self.fs_epg_now.setStyleSheet("font-size: 15px; color: #ccc; background: transparent;")
        self.fs_epg_now.hide()
        text_layout.addWidget(self.fs_epg_now)

        # Fortschritts-Zeile: Seek-Slider (Catchup) oder visueller Balken
        fs_prog_row = QWidget()
        fs_prog_row.setStyleSheet("background: transparent;")
        prog_row_layout = QHBoxLayout(fs_prog_row)
        prog_row_layout.setContentsMargins(0, 2, 0, 2)
        prog_row_layout.setSpacing(8)

        self.fs_epg_von_anfang_btn = QPushButton(_tr(" Anfang"))
        self.fs_epg_von_anfang_btn.setIcon(_pi("refresh.svg", 15))
        self.fs_epg_von_anfang_btn.setIconSize(QSize(15, 15))
        self.fs_epg_von_anfang_btn.setFixedHeight(32)
        self.fs_epg_von_anfang_btn.setToolTip(_tr("Sendung von Anfang abspielen (Catchup)"))
        self.fs_epg_von_anfang_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 120, 212, 55), stop:1 rgba(80, 40, 200, 28));
                border: none; border-left: 3px solid #0078d4;
                border-radius: 8px; padding: 2px 16px;
                color: white; font-size: 13px; font-weight: 600; text-align: center;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 120, 212, 80), stop:1 rgba(80, 40, 200, 50));
            }
        """)
        self.fs_epg_von_anfang_btn.clicked.connect(self._fs_play_von_anfang)
        self.fs_epg_von_anfang_btn.hide()
        prog_row_layout.addWidget(self.fs_epg_von_anfang_btn)

        self.fs_epg_seek_slider = ClickSlider(Qt.Horizontal)
        self.fs_epg_seek_slider.setRange(0, 1000)
        self.fs_epg_seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255,255,255,40); height: 4px; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white; width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #e8691a; border-radius: 2px; }
        """)
        self.fs_epg_seek_slider.sliderPressed.connect(lambda: setattr(self, '_fs_epg_seeking', True))
        self.fs_epg_seek_slider.sliderReleased.connect(self._on_fs_epg_seek_released)
        self.fs_epg_seek_slider.hide()
        prog_row_layout.addWidget(self.fs_epg_seek_slider, stretch=1)

        self.fs_epg_progress = QProgressBar()
        self.fs_epg_progress.setFixedHeight(4)
        self.fs_epg_progress.setTextVisible(False)
        self.fs_epg_progress.hide()
        prog_row_layout.addWidget(self.fs_epg_progress, stretch=1)

        text_layout.addWidget(fs_prog_row)

        self.fs_epg_next = QLabel("")
        self.fs_epg_next.setStyleSheet("font-size: 14px; color: #aaa; background: transparent;")
        self.fs_epg_next.hide()
        text_layout.addWidget(self.fs_epg_next)

        info_layout.addWidget(fs_text_col, stretch=1)
        layout.addWidget(fs_info_section)

        # Zeile 1: Seek-Slider (nur bei VOD/Timeshift)
        self.fs_seek_row = QWidget()
        self.fs_seek_row.setStyleSheet("background: transparent;")
        seek_layout = QHBoxLayout(self.fs_seek_row)
        seek_layout.setContentsMargins(0, 0, 0, 0)
        seek_layout.setSpacing(8)

        self.fs_pos_label = QLabel("00:00")
        self.fs_pos_label.setFixedWidth(55)
        self.fs_pos_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        seek_layout.addWidget(self.fs_pos_label)

        self.fs_seek_slider = ClickSlider(Qt.Horizontal)
        self.fs_seek_slider.setRange(0, 1000)
        self.fs_seek_slider.setValue(0)
        self.fs_seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 40);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #e8691a;
                border-radius: 2px;
            }
        """)
        self.fs_seek_slider.sliderPressed.connect(lambda: setattr(self, '_fs_seeking', True))
        self.fs_seek_slider.sliderReleased.connect(self._on_fs_seek_released)
        seek_layout.addWidget(self.fs_seek_slider, stretch=1)

        self.fs_dur_label = QLabel("00:00")
        self.fs_dur_label.setFixedWidth(55)
        seek_layout.addWidget(self.fs_dur_label)

        self.fs_seek_row.hide()
        layout.addWidget(self.fs_seek_row)

        # Zeile 2: Steuer-Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        _FS = 26   # fullscreen transport icon size
        _FS_SM = 20  # secondary icon size

        self._icon_play_fs  = _pi("play.svg",  _FS)
        self._icon_pause_fs = _pi("pause.svg", _FS)

        self.fs_btn_play_pause = QPushButton()
        self.fs_btn_play_pause.setIcon(self._icon_play_fs)
        self.fs_btn_play_pause.setIconSize(QSize(_FS, _FS))
        self.fs_btn_play_pause.setFixedSize(48, 48)
        self.fs_btn_play_pause.setToolTip("Play / Pause")
        self.fs_btn_play_pause.clicked.connect(self._toggle_play_pause)
        btn_row.addWidget(self.fs_btn_play_pause)

        self.fs_btn_skip_back = QPushButton()
        self.fs_btn_skip_back.setIcon(_pi("rewind.svg", _FS))
        self.fs_btn_skip_back.setIconSize(QSize(_FS, _FS))
        self.fs_btn_skip_back.setFixedSize(44, 44)
        self.fs_btn_skip_back.clicked.connect(lambda: self._skip_seconds(-30))
        self.fs_btn_skip_back.setToolTip(_tr("30s zur\u00fcck"))
        self.fs_btn_skip_back.hide()
        btn_row.addWidget(self.fs_btn_skip_back)

        self.fs_btn_skip_forward = QPushButton()
        self.fs_btn_skip_forward.setIcon(_pi("fast-forward.svg", _FS))
        self.fs_btn_skip_forward.setIconSize(QSize(_FS, _FS))
        self.fs_btn_skip_forward.setFixedSize(44, 44)
        self.fs_btn_skip_forward.clicked.connect(lambda: self._skip_seconds(30))
        self.fs_btn_skip_forward.setToolTip(_tr("30s vor"))
        self.fs_btn_skip_forward.hide()
        btn_row.addWidget(self.fs_btn_skip_forward)

        self.fs_btn_go_live = QPushButton("LIVE")
        self.fs_btn_go_live.setFixedHeight(34)
        self.fs_btn_go_live.setStyleSheet("""
            QPushButton {
                background: rgba(232,105,26,12); color: #e8691a;
                border: 1px solid rgba(232,105,26,160); padding: 4px 16px;
                border-radius: 16px; font-size: 12px; font-weight: 700; letter-spacing: 1px;
            }
            QPushButton:hover { background: rgba(232,105,26,30); border-color: #e8691a; }
        """)
        self.fs_btn_go_live.clicked.connect(self._go_live)
        self.fs_btn_go_live.hide()
        btn_row.addWidget(self.fs_btn_go_live)

        self.fs_btn_stop = QPushButton()
        self.fs_btn_stop.setIcon(_pi("square.svg", _FS))
        self.fs_btn_stop.setIconSize(QSize(_FS, _FS))
        self.fs_btn_stop.setFixedSize(44, 44)
        self.fs_btn_stop.setToolTip("Stop")
        self.fs_btn_stop.clicked.connect(self._stop_playback)
        btn_row.addWidget(self.fs_btn_stop)

        self.fs_btn_record = QPushButton()
        self.fs_btn_record.setObjectName("fsRecordBtn")
        self.fs_btn_record.setCheckable(True)
        self.fs_btn_record.setIcon(_pi_colored("record.svg", _FS - 4, "#ff4444"))
        self.fs_btn_record.setIconSize(QSize(_FS - 4, _FS - 4))
        self.fs_btn_record.setFixedSize(44, 44)
        self.fs_btn_record.setToolTip(_tr("Aufnahme starten / stoppen"))
        self.fs_btn_record.clicked.connect(self._toggle_recording)
        btn_row.addWidget(self.fs_btn_record)

        btn_row.addStretch()

        # Secondary icon buttons
        _fs_icon_btn_style = """
            QPushButton { background: transparent; border: none; border-radius: 8px; padding: 6px; }
            QPushButton:hover { background: rgba(255,255,255,12); }
            QPushButton:checked { background: rgba(232,105,26,18); }
        """

        self.fs_btn_audio = QPushButton()
        self.fs_btn_audio.setIcon(_pi("headphones.svg", _FS_SM))
        self.fs_btn_audio.setIconSize(QSize(_FS_SM, _FS_SM))
        self.fs_btn_audio.setFixedSize(40, 40)
        self.fs_btn_audio.setToolTip(_tr("Tonspur w\u00e4hlen"))
        self.fs_btn_audio.setStyleSheet(_fs_icon_btn_style)
        self.fs_btn_audio.clicked.connect(self._show_audio_menu)
        btn_row.addWidget(self.fs_btn_audio)

        self.fs_btn_subtitle = QPushButton()
        self.fs_btn_subtitle.setIcon(_pi("captions.svg", _FS_SM))
        self.fs_btn_subtitle.setIconSize(QSize(_FS_SM, _FS_SM))
        self.fs_btn_subtitle.setFixedSize(40, 40)
        self.fs_btn_subtitle.setToolTip(_tr("Untertitel w\u00e4hlen"))
        self.fs_btn_subtitle.setStyleSheet(_fs_icon_btn_style)
        self.fs_btn_subtitle.clicked.connect(self._show_subtitle_menu)
        btn_row.addWidget(self.fs_btn_subtitle)

        self.fs_btn_stream_info = QPushButton()
        self.fs_btn_stream_info.setCheckable(True)
        self.fs_btn_stream_info.setIcon(_pi_colored("info.svg", _FS_SM, "#e8691a"))
        self.fs_btn_stream_info.setIconSize(QSize(_FS_SM, _FS_SM))
        self.fs_btn_stream_info.setFixedSize(40, 40)
        self.fs_btn_stream_info.setToolTip(_tr("Stream-Info"))
        self.fs_btn_stream_info.setStyleSheet(_fs_icon_btn_style)
        self.fs_btn_stream_info.clicked.connect(self._toggle_stream_info)
        btn_row.addWidget(self.fs_btn_stream_info)

        self.fs_btn_zoom = QPushButton()
        self.fs_btn_zoom.setIcon(_pi("crop.svg", _FS_SM))
        self.fs_btn_zoom.setIconSize(QSize(_FS_SM, _FS_SM))
        self.fs_btn_zoom.setFixedSize(40, 40)
        self.fs_btn_zoom.setToolTip(_tr("Seitenverh\u00e4ltnis: Normal \u2192 Fill \u2192 Stretch"))
        self.fs_btn_zoom.setStyleSheet(_fs_icon_btn_style)
        self.fs_btn_zoom.clicked.connect(self._cycle_zoom_mode)
        btn_row.addWidget(self.fs_btn_zoom)

        btn_row.addSpacing(10)

        self._px_vol_fs       = _pi("volume-2.svg", 18).pixmap(QSize(18, 18))
        self._px_vol_muted_fs = _pi("volume-x.svg", 18).pixmap(QSize(18, 18))
        self.fs_vol_mute_btn = QLabel()
        self.fs_vol_mute_btn.setPixmap(self._px_vol_fs)
        self.fs_vol_mute_btn.setFixedSize(22, 22)
        self.fs_vol_mute_btn.setStyleSheet("background: transparent;")
        self.fs_vol_mute_btn.setCursor(Qt.PointingHandCursor)
        self.fs_vol_mute_btn.mousePressEvent = lambda e: self._toggle_mute()
        btn_row.addWidget(self.fs_vol_mute_btn)

        self.fs_volume_slider = QSlider(Qt.Horizontal)
        self.fs_volume_slider.setRange(0, 100)
        self.fs_volume_slider.setFixedWidth(110)
        self.fs_volume_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: rgba(255,255,255,40); height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: white; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QSlider::sub-page:horizontal { background: #e8691a; border-radius: 2px; }
        """)
        self.fs_volume_slider.blockSignals(True)
        self.fs_volume_slider.setValue(100)
        self.fs_volume_slider.blockSignals(False)
        self.fs_volume_slider.valueChanged.connect(self._on_volume_changed)
        btn_row.addWidget(self.fs_volume_slider)

        btn_row.addSpacing(8)

        fs_exit_btn = QPushButton()
        fs_exit_btn.setIcon(_pi("minimize.svg", _FS))
        fs_exit_btn.setIconSize(QSize(_FS, _FS))
        fs_exit_btn.setFixedSize(48, 48)
        fs_exit_btn.setToolTip(_tr("Vollbild verlassen  (Esc / F)"))
        fs_exit_btn.clicked.connect(self._toggle_player_maximized)
        btn_row.addWidget(fs_exit_btn)

        layout.addLayout(btn_row)

        self._fs_seeking = False
        overlay.hide()
        overlay.installEventFilter(self)

        return overlay

    def _create_stream_info_panel(self) -> QWidget:
        """Creates the stream info HUD overlay (floating over the video, top-right)."""
        panel = QFrame()
        panel.setObjectName("streamInfoPanel")
        panel.setStyleSheet("""
            #streamInfoPanel {
                background-color: rgba(8, 8, 22, 185);
                border: 1px solid rgba(255, 255, 255, 12);
                border-radius: 12px;
            }
            QLabel[role="header"] {
                color: #556;
                font-size: 9px;
                font-weight: bold;
                letter-spacing: 1.5px;
                background: transparent;
            }
            QLabel {
                color: #ddd;
                background: transparent;
                font-size: 12px;
            }
        """)
        panel.setFixedWidth(180)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        def _header(text):
            lbl = QLabel(text)
            lbl.setProperty("role", "header")
            lbl.setStyleSheet("color: #556; font-size: 9px; font-weight: bold; "
                              "letter-spacing: 1.5px; background: transparent;")
            return lbl

        # Video
        layout.addWidget(_header("VIDEO"))
        self.info_resolution = QLabel("–")
        self.info_fps = QLabel("–")
        self.info_video_codec = QLabel("–")
        for lbl in (self.info_resolution, self.info_fps, self.info_video_codec):
            layout.addWidget(lbl)

        layout.addSpacing(6)

        # Audio
        layout.addWidget(_header("AUDIO"))
        self.info_audio_codec = QLabel("–")
        self.info_audio_tracks = QLabel("–")
        for lbl in (self.info_audio_codec, self.info_audio_tracks):
            layout.addWidget(lbl)

        return panel

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setFixedHeight(28)
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #0d0d14;
                color: #e0e0e0;
                font-size: 13px;
                font-weight: bold;
                padding: 0 10px;
            }
            QStatusBar::item { border: none; }
        """)
        self.status_bar.showMessage(_tr("Bereit"))

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # indeterminate
        self.loading_bar.setFixedSize(120, 12)
        self.loading_bar.setStyleSheet("""
            QProgressBar {
                background: #1a1a2e; border: 1px solid #2a2a4a;
                border-radius: 3px;
            }
            QProgressBar::chunk { background: #0078d4; border-radius: 3px; }
        """)
        self.loading_bar.hide()
        self.status_bar.addPermanentWidget(self.loading_bar)
