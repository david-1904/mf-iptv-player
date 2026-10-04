"""
Live-TV-Leerlauf: Platzhalter rechts neben der Kanalliste, solange nichts laeuft.
Haelt das Layout stabil (kein Springen beim Starten/Stoppen), bietet den zuletzt
gesehenen Sender zum Weiterschauen an und fuellt grosse Fenster mit Programm-
vorschau und weiteren zuletzt gesehenen Sendern.
"""
import asyncio
from datetime import datetime

import aiohttp
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QWidget,
    QToolButton,
)

from xtream_api import LiveStream
from ui_builder import _pi
from i18n import _tr

_MAX_UPCOMING = 6
_MAX_RECENT = 6


class _IdlePanel(QFrame):
    resized = Signal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()


class LiveIdleMixin:

    def _create_live_idle_panel(self) -> QWidget:
        panel = _IdlePanel()
        panel.setObjectName("liveIdlePanel")
        panel.setStyleSheet("""
            #liveIdlePanel {
                background: qradialgradient(cx:0.5, cy:0.45, radius:0.8, fx:0.5, fy:0.45,
                    stop:0 #17173a, stop:1 #0a0a16);
                border-left: 1px solid rgba(255, 255, 255, 8);
            }
            QLabel { background: transparent; }
            QPushButton#idleResumeBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0078d4, stop:1 #4a3ad0);
                color: white; border: none; border-radius: 10px; font-weight: 600;
            }
            QPushButton#idleResumeBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a8ae4, stop:1 #5a4ae0);
            }
            QProgressBar {
                background: rgba(255, 255, 255, 25); border: none; border-radius: 2px;
            }
            QProgressBar::chunk { background: #e8691a; border-radius: 2px; }
            QToolButton#idleRecentTile {
                background: rgba(255, 255, 255, 6);
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 12px; color: #ccc;
            }
            QToolButton#idleRecentTile:hover {
                background: rgba(255, 255, 255, 16);
                border: 1px solid rgba(0, 120, 212, 120); color: white;
            }
        """)
        panel.resized.connect(self._layout_live_idle_panel)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.addStretch(1)

        self.idle_column = QWidget()
        col = QVBoxLayout(self.idle_column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        self.idle_logo = QLabel()
        self.idle_logo.setAlignment(Qt.AlignCenter)
        col.addWidget(self.idle_logo, alignment=Qt.AlignHCenter)
        col.addSpacing(10)

        self.idle_caption = QLabel()
        self.idle_caption.setAlignment(Qt.AlignCenter)
        col.addWidget(self.idle_caption)

        self.idle_title = QLabel()
        self.idle_title.setAlignment(Qt.AlignCenter)
        self.idle_title.setWordWrap(True)
        col.addWidget(self.idle_title)

        self.idle_epg_box = QWidget()
        epg = QVBoxLayout(self.idle_epg_box)
        epg.setContentsMargins(0, 8, 0, 0)
        epg.setSpacing(6)
        self.idle_epg_now = QLabel()
        self.idle_epg_now.setAlignment(Qt.AlignCenter)
        self.idle_epg_now.setWordWrap(True)
        epg.addWidget(self.idle_epg_now)
        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        self.idle_epg_start = QLabel()
        self.idle_epg_progress = QProgressBar()
        self.idle_epg_progress.setTextVisible(False)
        self.idle_epg_progress.setRange(0, 1000)
        self.idle_epg_stop = QLabel()
        prog_row.addWidget(self.idle_epg_start)
        prog_row.addWidget(self.idle_epg_progress, stretch=1)
        prog_row.addWidget(self.idle_epg_stop)
        epg.addLayout(prog_row)

        # Kommende Sendungen: feste Zeilen, Anzahl sichtbarer Zeilen je nach Platz
        self.idle_upcoming = QWidget()
        up = QVBoxLayout(self.idle_upcoming)
        up.setContentsMargins(0, 6, 0, 0)
        up.setSpacing(2)
        self._idle_upcoming_rows = []
        for _ in range(_MAX_UPCOMING):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(12)
            t = QLabel()
            t.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            name = QLabel()
            rl.addWidget(t)
            rl.addWidget(name, stretch=1)
            up.addWidget(row)
            row.hide()
            self._idle_upcoming_rows.append((row, t, name))
        epg.addWidget(self.idle_upcoming, alignment=Qt.AlignHCenter)
        self.idle_epg_box.hide()
        col.addWidget(self.idle_epg_box)

        col.addSpacing(18)
        self.idle_resume_btn = QPushButton(_tr("Weiterschauen"))
        self.idle_resume_btn.setObjectName("idleResumeBtn")
        self.idle_resume_btn.clicked.connect(self._resume_last_live)
        col.addWidget(self.idle_resume_btn, alignment=Qt.AlignHCenter)

        col.addSpacing(10)
        self.idle_hint = QLabel()
        self.idle_hint.setAlignment(Qt.AlignCenter)
        self.idle_hint.setWordWrap(True)
        col.addWidget(self.idle_hint)

        outer.addWidget(self.idle_column, alignment=Qt.AlignHCenter)

        # Weitere zuletzt gesehene Sender als Kacheln
        self.idle_recent = QWidget()
        rec = QVBoxLayout(self.idle_recent)
        rec.setContentsMargins(0, 36, 0, 0)
        rec.setSpacing(12)
        self.idle_recent_caption = QLabel(_tr("WEITERE ZULETZT GESEHENE SENDER"))
        self.idle_recent_caption.setAlignment(Qt.AlignCenter)
        rec.addWidget(self.idle_recent_caption)
        self._idle_recent_row = QHBoxLayout()
        self._idle_recent_row.setSpacing(12)
        rec.addLayout(self._idle_recent_row)
        outer.addWidget(self.idle_recent, alignment=Qt.AlignHCenter)

        outer.addStretch(1)

        self._idle_last_live = None
        self._idle_logo_pixmap = None
        self._idle_upcoming_entries = []
        self._idle_recent_tiles = []
        self._idle_scale = None
        self._idle_layout_busy = False
        panel.hide()
        return panel

    # ── Sichtbarkeit ─────────────────────────────────────────

    def _update_live_idle_panel(self):
        """Zeigt den Platzhalter genau dann, wenn Live-TV ohne laufende Wiedergabe aktiv ist."""
        show = (
            self.current_mode == "live"
            and self.api is not None
            and not self.player_area.isVisible()
        )
        was_visible = self.live_idle_panel.isVisible()
        if show:
            if not self.channel_detail_panel.isVisible():
                self.channel_area.setFixedWidth(self._live_channel_width())
            self.channel_area.show()
            if not was_visible:
                self.live_idle_panel.show()
            self._refresh_live_idle_content()
        elif was_visible:
            self.live_idle_panel.hide()
            if not self.player_area.isVisible():
                self.channel_area.setMinimumWidth(0)
                self.channel_area.setMaximumWidth(16777215)

    # ── Inhalt ───────────────────────────────────────────────

    def _refresh_live_idle_content(self):
        account = self.account_manager.get_selected()
        last = self.session_manager.get(account.name, "live") if account else None
        self._idle_last_live = last if last and last.get("stream_id") else None
        self._idle_upcoming_entries = []
        self.idle_epg_box.hide()
        self._set_idle_logo(None)

        if not self._idle_last_live:
            self.idle_caption.setText(_tr("LIVE TV"))
            self.idle_title.setText(_tr("Kein Sender aktiv"))
            self.idle_resume_btn.hide()
            self.idle_hint.setText(_tr("Wähle links einen Sender aus, um die Wiedergabe zu starten."))
        else:
            self.idle_caption.setText(_tr("ZULETZT GESEHEN"))
            self.idle_title.setText(self._idle_last_live.get("name", ""))
            self.idle_resume_btn.show()
            self.idle_hint.setText(_tr("oder wähle links einen anderen Sender"))
            asyncio.ensure_future(self._load_live_idle_details(dict(self._idle_last_live)))

        self._build_idle_recent_tiles(account.name if account else None)
        self._layout_live_idle_panel(force=True)

    def _set_idle_logo(self, pixmap):
        self._idle_logo_pixmap = pixmap
        self._apply_idle_logo()

    def _apply_idle_logo(self):
        s = self._idle_scale or 1.0
        size = int(128 * s)
        self.idle_logo.setFixedSize(size, size)
        if self._idle_logo_pixmap is not None:
            self.idle_logo.setPixmap(self._idle_logo_pixmap.scaled(
                size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon = int(72 * s)
            self.idle_logo.setPixmap(_pi("tv.svg", icon).pixmap(icon, icon))

    def _build_idle_recent_tiles(self, account_name):
        for tile in self._idle_recent_tiles:
            self._idle_recent_row.removeWidget(tile)
            tile.deleteLater()
        self._idle_recent_tiles = []
        if not account_name:
            return
        last_id = self._idle_last_live.get("stream_id") if self._idle_last_live else None
        seen = {last_id}
        for entry in self.history_manager.get_all(account_name):
            if entry.stream_type != "live" or entry.stream_id in seen:
                continue
            seen.add(entry.stream_id)
            tile = QToolButton()
            tile.setObjectName("idleRecentTile")
            tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            tile.setCursor(Qt.PointingHandCursor)
            tile.setToolTip(entry.title)
            tile.setProperty("full_title", entry.title)
            tile.setIcon(_pi("tv.svg", 40))
            tile.clicked.connect(
                lambda _=False, e=entry: self._play_live_by_id(e.stream_id, e.title, e.icon))
            self._idle_recent_row.addWidget(tile)
            self._idle_recent_tiles.append(tile)
            if entry.icon:
                asyncio.ensure_future(self._load_idle_tile_logo(tile, entry.icon))
            if len(self._idle_recent_tiles) >= _MAX_RECENT:
                break

    async def _load_idle_tile_logo(self, tile, url: str):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                pixmap = await self._fetch_poster(session, url, 128, 128)
            if pixmap and tile in self._idle_recent_tiles:
                tile.setIcon(QIcon(pixmap))
        except Exception:
            pass

    async def _load_live_idle_details(self, last: dict):
        stream_id = last["stream_id"]
        icon = last.get("icon") or ""

        def still_current() -> bool:
            return (self.live_idle_panel.isVisible() and self._idle_last_live
                    and self._idle_last_live.get("stream_id") == stream_id)

        if icon:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    pixmap = await self._fetch_poster(session, icon, 128, 128)
                if pixmap and still_current():
                    self._set_idle_logo(pixmap)
            except Exception:
                pass

        entries = None
        if self.api:
            try:
                entries = await self.api.get_short_epg(stream_id, limit=_MAX_UPCOMING + 2)
            except Exception:
                entries = None
        if not entries:
            entries = self._epg_cache.get(stream_id) or []
        if not still_current():
            return
        self._show_live_idle_epg(entries)
        self._layout_live_idle_panel(force=True)

    def _show_live_idle_epg(self, entries: list):
        now_ts = datetime.now().timestamp()
        upcoming = sorted((e for e in entries if e.stop_timestamp > now_ts),
                          key=lambda e: e.start_timestamp)
        now = next((e for e in upcoming if e.start_timestamp <= now_ts), None)
        if not now:
            self.idle_epg_box.hide()
            self._idle_upcoming_entries = []
            return
        dur = now.stop_timestamp - now.start_timestamp
        self.idle_epg_now.setText(_tr("Jetzt:") + f" {now.title}")
        self.idle_epg_start.setText(datetime.fromtimestamp(now.start_timestamp).strftime("%H:%M"))
        self.idle_epg_stop.setText(datetime.fromtimestamp(now.stop_timestamp).strftime("%H:%M"))
        self.idle_epg_progress.setValue(int((now_ts - now.start_timestamp) / dur * 1000) if dur > 0 else 0)
        self._idle_upcoming_entries = [e for e in upcoming if e.start_timestamp >= now.stop_timestamp]
        for i, (row, t, name) in enumerate(self._idle_upcoming_rows):
            if i < len(self._idle_upcoming_entries):
                e = self._idle_upcoming_entries[i]
                t.setText(datetime.fromtimestamp(e.start_timestamp).strftime("%H:%M"))
                name.setText(e.title)
        self.idle_epg_box.show()

    # ── Responsives Layout ───────────────────────────────────

    def _apply_idle_scale(self, s: float):
        if self._idle_scale == s:
            return
        self._idle_scale = s

        def px(v):
            return f"{round(v * s)}px"

        self.idle_column.setFixedWidth(round(460 * s))
        self.idle_caption.setStyleSheet(
            f"color: #8a8ab0; font-size: {px(11)}; font-weight: 600; letter-spacing: 2px;")
        self.idle_title.setStyleSheet(f"color: white; font-size: {px(26)}; font-weight: bold;")
        self.idle_epg_now.setStyleSheet(f"color: #ddd; font-size: {px(15)};")
        for lbl in (self.idle_epg_start, self.idle_epg_stop):
            lbl.setStyleSheet(f"color: #888; font-size: {px(12)};")
        self.idle_epg_progress.setFixedHeight(max(3, round(4 * s)))
        for _, t, name in self._idle_upcoming_rows:
            t.setFixedWidth(round(52 * s))
            t.setStyleSheet(f"color: #777; font-size: {px(13)};")
            name.setStyleSheet(f"color: #999; font-size: {px(13)};")
        self.idle_resume_btn.setStyleSheet(
            f"padding: {px(10)} {px(28)}; font-size: {px(15)};")
        icon = round(16 * s)
        self.idle_resume_btn.setIcon(_pi("play.svg", icon))
        self.idle_resume_btn.setIconSize(QSize(icon, icon))
        self.idle_hint.setStyleSheet(f"color: #666; font-size: {px(12)};")
        self.idle_recent_caption.setStyleSheet(
            f"color: #8a8ab0; font-size: {px(11)}; font-weight: 600; letter-spacing: 2px;")
        self._idle_recent_row.setSpacing(round(12 * s))
        self._apply_idle_logo()

    def _style_idle_tiles(self, s: float):
        tile_w, icon = round(124 * s), round(56 * s)
        for tile in self._idle_recent_tiles:
            tile.setFixedSize(tile_w, icon + round(52 * s))
            tile.setIconSize(QSize(icon, icon))
            tile.setStyleSheet(f"font-size: {round(12 * s)}px; padding: {round(8 * s)}px;")
            tile.ensurePolished()
            fm = tile.fontMetrics()
            tile.setText(fm.elidedText(tile.property("full_title"), Qt.ElideRight, tile_w - 16))

    def _layout_live_idle_panel(self, force: bool = False):
        """Passt Groesse und Informationsmenge an den verfuegbaren Platz an:
        erst volle Ausbaustufe, dann schrittweise Inhalte reduzieren bis alles passt."""
        panel = self.live_idle_panel
        if not panel.isVisible() or self._idle_layout_busy:
            return
        self._idle_layout_busy = True
        try:
            m = panel.layout().contentsMargins()
            avail_w = panel.width() - m.left() - m.right()
            avail_h = panel.height() - m.top() - m.bottom()
            if avail_w <= 0 or avail_h <= 0:
                return
            s = max(0.85, min(1.5, min(avail_w / 900, avail_h / 760)))
            s = round(s * 20) / 20  # Stufen vermeiden Neuberechnung bei jedem Pixel
            self._apply_idle_scale(s)
            self.idle_column.setFixedWidth(min(round(460 * s), avail_w))

            tile_w = round(124 * s) + round(12 * s)
            n_tiles = min(len(self._idle_recent_tiles), max(0, (avail_w + round(12 * s)) // tile_w))
            self._style_idle_tiles(s)
            for i, tile in enumerate(self._idle_recent_tiles):
                tile.setVisible(i < n_tiles)
            show_recent = n_tiles >= 2
            n_up = min(len(self._idle_upcoming_entries), _MAX_UPCOMING)

            def needed() -> int:
                h = self.idle_column.sizeHint().height()
                if show_recent:
                    h += self.idle_recent.sizeHint().height()
                return h

            self.idle_recent.setVisible(show_recent)
            self._set_idle_upcoming_count(n_up)
            while needed() > avail_h:
                if n_up > 1:
                    n_up -= 1
                    self._set_idle_upcoming_count(n_up)
                elif show_recent:
                    show_recent = False
                    self.idle_recent.hide()
                elif n_up > 0:
                    n_up = 0
                    self._set_idle_upcoming_count(0)
                else:
                    break
        finally:
            self._idle_layout_busy = False

    def _set_idle_upcoming_count(self, n: int):
        for i, (row, _, _) in enumerate(self._idle_upcoming_rows):
            row.setVisible(i < n)
        self.idle_upcoming.setVisible(n > 0)

    # ── Abspielen ────────────────────────────────────────────

    def _resume_last_live(self):
        last = self._idle_last_live
        if last:
            self._play_live_by_id(last["stream_id"], last.get("name", ""),
                                  last.get("icon", ""), last.get("category_id", ""))

    def _play_live_by_id(self, stream_id: int, name: str, icon: str = "", category_id: str = ""):
        if not self.api:
            return
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            data = item.data(Qt.UserRole) if item else None
            if isinstance(data, LiveStream) and data.stream_id == stream_id:
                self.channel_list.setCurrentItem(item)
                self.channel_list.scrollToItem(item)
                self._on_channel_selected(item)
                return
        self._play_live_stream(LiveStream(
            stream_id=stream_id, name=name, stream_icon=icon, category_id=category_id,
        ))
