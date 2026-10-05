"""
EPG: Programmfuehrer laden, anzeigen, Catchup abspielen
"""
import asyncio
import aiohttp
from datetime import datetime

from PySide6.QtCore import Qt, Slot, QPropertyAnimation, QEasingCurve, QSize, QTimer, QPoint, Signal
from PySide6.QtWidgets import (
    QListWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QProgressBar,
)
from PySide6.QtGui import QPixmap
from ui_builder import _pi, _pi_colored

from xtream_api import LiveStream, EpgEntry, dedupe_epg
from favorites_manager import Favorite
from i18n import _tr

_FUTURE_WINDOW = 2 * 86400          # wie weit das Programm nach vorne reicht
_MAX_PAST_DAYS = 2                   # mehr Zeilen machen den Aufbau spuerbar traege


class _ProgrammeRow(QFrame):
    """Programmzeile; Klick auf die Zeile klappt die Beschreibung auf."""
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _day_label(ts: float) -> str:
    day = datetime.fromtimestamp(ts).date()
    today = datetime.now().date()
    diff = (day - today).days
    if diff == 0:
        return _tr("Heute")
    if diff == 1:
        return _tr("Morgen")
    if diff == -1:
        return _tr("Gestern")
    weekdays = [_tr("Mo"), _tr("Di"), _tr("Mi"), _tr("Do"), _tr("Fr"), _tr("Sa"), _tr("So")]
    return f"{weekdays[day.weekday()]}, {day.strftime('%d.%m.')}"


class EpgMixin:

    @Slot(QListWidgetItem)
    def _on_channel_clicked(self, item: QListWidgetItem):
        """Handle single click on channel - load EPG for live streams"""
        data = item.data(Qt.UserRole)
        if not data or not self.api:
            return

        stream_id = None
        stream_name = ""
        has_catchup = False

        if isinstance(data, LiveStream):
            stream_id = data.stream_id
            stream_name = data.name
            has_catchup = data.tv_archive
            if data.epg_channel_id:
                self._stream_epg_channel_map[stream_id] = data.epg_channel_id
        elif isinstance(data, Favorite) and data.type == "live":
            stream_id = data.id
            stream_name = data.name

        if stream_id:
            self._current_epg_stream_id = stream_id
            self._current_epg_has_catchup = has_catchup
            self.epg_channel_name.setText(stream_name)
            # Logo im EPG-Panel laden
            icon_url = getattr(data, 'stream_icon', '') or getattr(data, 'icon', '')
            asyncio.ensure_future(self._load_epg_panel_logo(icon_url))
            # Detail-Panel anzeigen (nur wenn kein Player aktiv)
            self._show_channel_detail(data)
            asyncio.ensure_future(self._load_epg(stream_id))
        else:
            self._clear_epg_panel()
            self._hide_channel_detail()

    async def _load_epg(self, stream_id: int):
        """Load EPG data for a stream"""
        if stream_id in self._epg_cache:
            epg = self._epg_cache[stream_id]
            self._update_epg_panel(epg)
            self._update_detail_epg(epg)
            if self._current_epg_stream_id == stream_id:
                self._update_live_epg_row()
            return

        # Noch nicht gecacht: altes EPG sofort wegräumen bevor await kommt
        self.epg_now_label.hide()
        self.epg_now_title.setText(_tr("Lade Programm\u2026"))
        self.epg_progress.hide()
        self.epg_next_label.hide()
        self.epg_next_title.setText("")
        self.btn_full_epg.setEnabled(False)

        from m3u_provider import M3uProvider
        is_m3u = isinstance(self.api, M3uProvider)
        xmltv = getattr(self, '_xmltv_epg', None)

        def _apply(epg_data):
            self._epg_cache[stream_id] = epg_data
            if self._current_epg_stream_id == stream_id:
                self._update_epg_panel(epg_data)
                self._update_live_epg_row()
                detail_id = getattr(self._detail_stream_data, 'stream_id',
                                    getattr(self._detail_stream_data, 'id', None))
                if self.channel_detail_panel.isVisible() and detail_id == stream_id:
                    self._update_detail_epg(epg_data)

        def _try_external() -> bool:
            """Versucht externen EPG. Gibt True zurück wenn Daten gefunden."""
            if not (xmltv and xmltv.loaded):
                return False
            tvg_id = self._stream_epg_channel_map.get(stream_id, "")
            if not tvg_id:
                return False
            external = xmltv.get_short_epg(tvg_id, limit=8)
            if external:
                _apply(external)
                return True
            return False

        if is_m3u:
            # M3U: externer EPG zuerst (Provider hat keinen), Fallback: Provider (leer)
            if not _try_external():
                try:
                    epg_data = await self.api.get_short_epg(stream_id, limit=8)
                    _apply(epg_data)
                except Exception:
                    self._clear_epg_panel()
        else:
            # Xtream: Provider-EPG zuerst (Matching via stream_id ist korrekt)
            # Externer EPG nur als Fallback wenn Provider nichts liefert
            try:
                epg_data = await self.api.get_short_epg(stream_id, limit=8)
                if epg_data:
                    _apply(epg_data)
                elif not _try_external():
                    _apply([])
            except Exception:
                if not _try_external():
                    self._clear_epg_panel()

    def _update_epg_panel(self, epg_data: list[EpgEntry]):
        """Update EPG panel with data"""
        if not epg_data:
            self.epg_now_label.hide()
            self.epg_now_title.setText(_tr("Keine EPG-Daten"))
            self.epg_now_desc.setText("")
            self.epg_progress.hide()
            self.epg_next_label.hide()
            self.epg_next_title.setText("")
            self.btn_full_epg.setEnabled(False)
            return

        now = datetime.now().timestamp()
        current_entry = None
        next_entry = None

        for entry in epg_data:
            if entry.start_timestamp <= now < entry.stop_timestamp:
                current_entry = entry
            elif entry.start_timestamp > now and next_entry is None:
                next_entry = entry

        if not current_entry and epg_data:
            current_entry = epg_data[0]
            if len(epg_data) > 1:
                next_entry = epg_data[1]

        if current_entry:
            start = datetime.fromtimestamp(current_entry.start_timestamp).strftime("%H:%M")
            end = datetime.fromtimestamp(current_entry.stop_timestamp).strftime("%H:%M")
            self.epg_now_label.show()
            self.epg_now_title.setText(f"{start} – {end}   {current_entry.title}")

            # Fortschrittsbalken
            duration = current_entry.stop_timestamp - current_entry.start_timestamp
            if duration > 0:
                elapsed = now - current_entry.start_timestamp
                progress = max(0, min(100, int(elapsed / duration * 100)))
                self.epg_progress.setValue(progress)
                self.epg_progress.show()
            else:
                self.epg_progress.hide()

            self.epg_now_desc.hide()
        else:
            self.epg_now_label.hide()
            self.epg_now_title.setText("")
            self.epg_now_desc.setText("")
            self.epg_progress.hide()

        if next_entry:
            start = datetime.fromtimestamp(next_entry.start_timestamp).strftime("%H:%M")
            end = datetime.fromtimestamp(next_entry.stop_timestamp).strftime("%H:%M")
            self.epg_next_label.show()
            self.epg_next_title.setText(f"{start} – {end}   {next_entry.title}")
        else:
            self.epg_next_label.hide()
            self.epg_next_title.setText("")

        self.btn_full_epg.setEnabled(True)
        # Fuer Hover-Overlay bereitstellen (auch wenn Detail-Panel nicht offen ist)
        self._detail_now_entry = current_entry
        self._detail_next_entry = next_entry

    def _clear_epg_panel(self):
        """Clear EPG panel"""
        self.epg_channel_name.setText("")
        self.epg_channel_logo.clear()
        self.epg_now_label.hide()
        self.epg_now_title.setText(_tr("Wähle einen Kanal"))
        self.epg_now_desc.hide()
        self.epg_progress.hide()
        self.epg_next_label.hide()
        self.epg_next_title.setText("")
        self.btn_full_epg.setEnabled(False)
        self._current_epg_stream_id = None

    def _show_full_epg(self):
        """Oeffnet das Programm des aktuellen Senders im Detailpanel."""
        if self._current_epg_stream_id is None or not self._detail_stream_data:
            return
        # Programm lebt in der Kanalspalte, die im Vollbild versteckt ist
        if self._player_maximized:
            self._toggle_player_maximized()
        if not self.channel_detail_panel.isVisible():
            self._show_channel_detail(self._detail_stream_data)

    async def _fetch_full_epg(self, stream_id: int) -> list[EpgEntry]:
        """Komplettes Programm (vergangen + kommend) aus Provider bzw. XMLTV."""
        from m3u_provider import M3uProvider
        xmltv = getattr(self, '_xmltv_epg', None)

        def from_xmltv():
            if xmltv and xmltv.loaded:
                tvg_id = self._stream_epg_channel_map.get(stream_id, "")
                if tvg_id:
                    return xmltv.get_full_epg(tvg_id) or []
            return []

        if isinstance(self.api, M3uProvider):
            data = from_xmltv()
            if data:
                return dedupe_epg(data)
        try:
            data = await self.api.get_full_epg(stream_id)
        except Exception:
            data = []
        if not data:
            data = from_xmltv()
        return dedupe_epg(data)

    async def _load_detail_full_epg(self, stream_id: int):
        data = await self._fetch_full_epg(stream_id)
        if data and self.channel_detail_panel.isVisible() and self._detail_stream_id() == stream_id:
            self._update_detail_epg(data, full=True)

    def _detail_stream_id(self):
        d = self._detail_stream_data
        return getattr(d, 'stream_id', None) or getattr(d, 'id', None)

    def _play_catchup(self, entry: EpgEntry):
        """Spielt eine vergangene/aktuelle Sendung via Catchup ab (EPG bleibt sichtbar)."""
        if not self.api or self._current_epg_stream_id is None:
            return

        stream_id = self._current_epg_stream_id
        duration_min = max(1, (entry.stop_timestamp - entry.start_timestamp) // 60)
        start = datetime.fromtimestamp(entry.start_timestamp)
        url = self.api.creds.catchup_url(stream_id, start, duration_min)

        channel_name = self.epg_channel_name.text()
        self._playing_channel_name = channel_name
        start_str = start.strftime("%H:%M")
        end_str = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
        title = f"{channel_name} \u2013 {entry.title} ({start_str}\u2013{end_str})"

        # Als Live-Stream abspielen; Programmliste bleibt offen
        self._keep_detail_open = True
        try:
            self._play_stream(url, title, "live", stream_id)
        finally:
            self._keep_detail_open = False
        self._playing_catchup_entry = entry
        if self.channel_detail_panel.isVisible() and getattr(self, '_detail_epg_entries', None):
            self._update_detail_epg(self._detail_epg_entries, full=self._detail_epg_full)
        # Timeshift aktiv: Seek-Controls einblenden
        self._timeshift_active = True
        self._timeshift_start_ts = entry.start_timestamp
        self._update_seek_controls_visibility()

    # ── Kanal-Detailpanel ─────────────────────────────────────────────

    def _show_channel_detail(self, stream_data):
        """Zeigt das Kanal-Detailpanel. Layout: Senderliste | EPG | TV (3 Spalten)."""
        self._detail_stream_data = stream_data

        name = getattr(stream_data, 'name', '') or getattr(stream_data, 'title', '')
        self.detail_channel_name.setText(name)
        self.detail_channel_name.updateGeometry()  # word-wrap Hoehe an Parent-Layout melden

        # Logo-Platzhalter
        self.detail_logo.setText("\U0001F4FA")
        self.detail_logo.setPixmap(QPixmap())

        # Programm-Platzhalter
        self._detail_epg_entries = []
        self._detail_epg_full = False
        self._clear_detail_programme()
        loading = QLabel(_tr("Lade Programm…"))
        loading.setStyleSheet("color: #8a8aa0; font-size: 13px; padding: 12px 0;")
        self.detail_programme_layout.addWidget(loading)

        # EPG-Panel-Zeile verstecken, Senderliste bleibt immer sichtbar
        self._epg_splitter.setSizes([99999, 0])
        self.epg_panel.hide()

        # 2-Spalten: Senderliste ausblenden, Detail einblenden (Slide)
        self.channel_nav_widget.hide()
        if (self.player_area.isVisible() and not self._pip_mode) or self.live_idle_panel.isVisible():
            ca_width = min(480, max(360, int(self.main_page.width() * 0.32)))
            self.channel_area.setFixedWidth(ca_width)
        self._slide_in(self.channel_detail_panel)

        icon_url = getattr(stream_data, 'stream_icon', '') or getattr(stream_data, 'icon', '')
        if icon_url:
            asyncio.ensure_future(self._load_detail_logo(icon_url))

        stream_id = getattr(stream_data, 'stream_id', None) or getattr(stream_data, 'id', None)
        if stream_id:
            asyncio.ensure_future(self._load_epg(stream_id))
            asyncio.ensure_future(self._load_detail_full_epg(stream_id))

    def _hide_channel_detail(self):
        """Versteckt das Kanal-Detailpanel mit Slide-Animation."""
        if not hasattr(self, 'channel_detail_panel'):
            return
        if not self.channel_detail_panel.isVisible():
            return
        self._slide_out(self.channel_detail_panel)

    def _toggle_channel_detail(self):
        """Toggle-Button: Detail-Panel auf- oder zuschieben."""
        if self._player_maximized:
            self._toggle_player_maximized()
        if self.channel_detail_panel.isVisible():
            self._hide_channel_detail()
        elif self._detail_stream_data:
            self._show_channel_detail(self._detail_stream_data)

    def _slide_in(self, widget):
        """Schiebt das Detail-Panel von rechts ein."""
        target = self.channel_area.width()
        widget.setMaximumWidth(0)
        widget.show()
        self._slide_anim = QPropertyAnimation(widget, b"maximumWidth")
        self._slide_anim.setDuration(220)
        self._slide_anim.setStartValue(0)
        self._slide_anim.setEndValue(target)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        def _on_slide_in_done():
            widget.setMaximumWidth(16777215)
            # Nach der Animation Layout-Cache zuruecksetzen, damit word-wrapped
            # Labels ihre Hoehe korrekt neu berechnen (Animation kann Caches korrumpieren)
            widget.layout().invalidate()
            widget.layout().activate()

        self._slide_anim.finished.connect(_on_slide_in_done)
        self._slide_anim.start()

    def _slide_out(self, widget):
        """Schiebt das Detail-Panel nach rechts zu."""
        self._slide_anim = QPropertyAnimation(widget, b"maximumWidth")
        self._slide_anim.setDuration(180)
        self._slide_anim.setStartValue(widget.width())
        self._slide_anim.setEndValue(0)
        self._slide_anim.setEasingCurve(QEasingCurve.InCubic)
        self._slide_anim.finished.connect(self._on_detail_hidden)
        self._slide_anim.start()

    def _on_detail_hidden(self):
        """Wird nach der Slide-Out-Animation aufgerufen."""
        self.channel_detail_panel.hide()
        self.channel_detail_panel.setMaximumWidth(16777215)
        self.channel_nav_widget.show()
        if (self.player_area.isVisible() and not self._pip_mode) or self.live_idle_panel.isVisible():
            self.channel_area.setFixedWidth(self._live_channel_width())

    def _clear_detail_programme(self):
        while self.detail_programme_layout.count():
            item = self.detail_programme_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _update_detail_epg(self, epg_data: list, full: bool = False):
        """Baut die Programmliste im Detailpanel (nach Tagen gegliedert)."""
        if not self.channel_detail_panel.isVisible():
            return
        # Kurz-EPG darf ein bereits geladenes Voll-EPG nicht ueberschreiben
        if not full and getattr(self, '_detail_epg_full', False):
            return
        self._detail_epg_entries = list(epg_data)
        self._detail_epg_full = full

        now = datetime.now().timestamp()
        stream = self._detail_stream_data
        has_catchup = bool(getattr(stream, 'tv_archive', False)) or self._current_epg_has_catchup
        archive_days = min(getattr(stream, 'tv_archive_duration', 0) or _MAX_PAST_DAYS, _MAX_PAST_DAYS)
        oldest = now - archive_days * 86400 if has_catchup else now
        newest = now + _FUTURE_WINDOW
        entries = [e for e in dedupe_epg(epg_data)
                   if e.stop_timestamp > oldest and e.start_timestamp < newest]

        self._clear_detail_programme()
        if not entries:
            empty = QLabel(_tr("Keine Programmdaten verfügbar"))
            empty.setStyleSheet("color: #8a8aa0; font-size: 13px; padding: 12px 0;")
            self.detail_programme_layout.addWidget(empty)
            return

        playing = getattr(self, '_playing_catchup_entry', None)
        scroll_target = None
        playing_row = None
        last_day = None
        for entry in entries:
            day = datetime.fromtimestamp(entry.start_timestamp).date()
            if day != last_day:
                last_day = day
                self.detail_programme_layout.addWidget(self._make_day_header(entry.start_timestamp))
            is_current = entry.start_timestamp <= now < entry.stop_timestamp
            is_playing = (playing is not None and playing.start_timestamp == entry.start_timestamp
                          and playing.title == entry.title)
            row = self._make_programme_row(entry, now, is_current, is_playing, has_catchup)
            self.detail_programme_layout.addWidget(row)
            if is_playing:
                playing_row = row
            if is_current or (scroll_target is None and entry.start_timestamp > now):
                scroll_target = row
        target = playing_row or scroll_target
        if target is not None:
            # Erst nach Layout bzw. Einfahr-Animation ist die Zeilenposition final
            for delay in (0, 300):
                QTimer.singleShot(delay, lambda t=target: self._scroll_detail_to(t))

    def _scroll_detail_to(self, row: QWidget):
        try:
            content = self.detail_scroll.widget()
            content.layout().activate()
            content.resize(content.width(), content.layout().sizeHint().height())
            y = row.mapTo(content, QPoint(0, 0)).y()
        except RuntimeError:
            return
        # Eine Zeile Kontext oberhalb der laufenden Sendung lassen
        self.detail_scroll.verticalScrollBar().setValue(max(0, y - 90))

    def _make_day_header(self, ts: float) -> QWidget:
        lbl = QLabel(_day_label(ts).upper())
        lbl.setStyleSheet(
            "color: #a6a6b8; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
            "padding: 14px 0 6px 0; border-bottom: 1px solid rgba(255,255,255,8);"
        )
        return lbl

    def _make_programme_row(self, entry: EpgEntry, now: float, is_current: bool,
                            is_playing: bool, has_catchup: bool) -> QWidget:
        is_past = entry.stop_timestamp <= now
        row = _ProgrammeRow()
        row.setObjectName("progRow")
        accent = "#0078d4" if is_playing else "#e8691a" if is_current else "transparent"
        bg = "rgba(232,105,26,18)" if is_current else "rgba(0,120,212,22)" if is_playing else "transparent"
        row.setStyleSheet(f"""
            #progRow {{ background: {bg}; border-left: 3px solid {accent};
                        border-bottom: 1px solid rgba(255,255,255,5); }}
            #progRow:hover {{ background: rgba(255,255,255,10); }}
            QLabel {{ background: transparent; border: none; }}
        """)
        outer = QVBoxLayout(row)
        outer.setContentsMargins(8, 8, 4, 8)
        outer.setSpacing(4)

        line = QHBoxLayout()
        line.setSpacing(10)
        time_lbl = QLabel(datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M"))
        time_color = "#e8691a" if is_current else "#8a8aa0" if is_past else "#a6a6b8"
        time_lbl.setStyleSheet(f"color: {time_color}; font-size: 13px; font-weight: 600;")
        time_lbl.setFixedWidth(42)
        time_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        line.addWidget(time_lbl, alignment=Qt.AlignTop)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_color = "white" if (is_current or is_playing) else "#8a8aa0" if is_past else "#ddd"
        weight = "600" if (is_current or is_playing) else "normal"
        title = QLabel(entry.title)
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {title_color}; font-size: 14px; font-weight: {weight};")
        title_col.addWidget(title)
        if is_playing:
            tag = QLabel(_tr("Läuft gerade"))
            tag.setStyleSheet("color: #5aaef0; font-size: 11px; font-weight: 600;")
            title_col.addWidget(tag)
        if is_current:
            dur = entry.stop_timestamp - entry.start_timestamp
            bar = QProgressBar()
            bar.setFixedHeight(3)
            bar.setTextVisible(False)
            bar.setRange(0, 1000)
            bar.setValue(int((now - entry.start_timestamp) / dur * 1000) if dur > 0 else 0)
            bar.setStyleSheet("""
                QProgressBar { background: rgba(255,255,255,20); border: none; border-radius: 1px; }
                QProgressBar::chunk { background: #e8691a; border-radius: 1px; }
            """)
            title_col.addWidget(bar)
            left = max(0, int((entry.stop_timestamp - now) // 60))
            rest = QLabel(_tr("bis {} · noch {} Min.").format(
                datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M"), left))
            rest.setStyleSheet("color: #a6a6b8; font-size: 11px;")
            title_col.addWidget(rest)
        line.addLayout(title_col, stretch=1)

        btn_ss = """
            QPushButton { background: transparent; border: 1px solid rgba(255,255,255,25); border-radius: 14px; }
            QPushButton:hover { background: rgba(255,255,255,30); }
        """
        if has_catchup and (is_past or is_current):
            play = QPushButton()
            play.setIcon(_pi("play.svg", 13))
            play.setIconSize(QSize(13, 13))
            play.setFixedSize(28, 28)
            play.setStyleSheet(btn_ss)
            play.setToolTip(_tr("Von Anfang abspielen") if is_current else _tr("Abspielen"))
            play.clicked.connect(lambda _=False, e=entry: self._play_catchup(e))
            line.addWidget(play, alignment=Qt.AlignTop)
        if not is_past:
            rec = QPushButton()
            rec.setIcon(_pi_colored("record.svg", 13, "#e5484d"))
            rec.setIconSize(QSize(13, 13))
            rec.setFixedSize(28, 28)
            rec.setStyleSheet(btn_ss.replace("rgba(255,255,255,30)", "rgba(229,72,77,60)"))
            rec.setToolTip(_tr("Aufnahme planen"))
            rec.clicked.connect(lambda _=False, e=entry: self._schedule_from_epg(e))
            line.addWidget(rec, alignment=Qt.AlignTop)
        outer.addLayout(line)

        desc = (entry.description or "").strip()
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #a6a6b8; font-size: 13px; padding-left: 52px;")
            desc_lbl.setVisible(is_current)
            outer.addWidget(desc_lbl)
            row.setCursor(Qt.PointingHandCursor)
            row.clicked.connect(lambda d=desc_lbl: d.setVisible(not d.isVisible()))
        return row

    async def _load_detail_logo(self, url: str):
        """Laedt das Senderlogo und setzt es als 80x80 Icon."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                pixmap = await self._fetch_poster(session, url, 160, 160)
                if pixmap and self.channel_detail_panel.isVisible():
                    scaled = pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.detail_logo.setPixmap(scaled)
                    self.detail_logo.setText("")
        except Exception:
            pass

    async def _load_epg_panel_logo(self, url: str):
        """Laedt das Senderlogo fuer das EPG-Panel (64x64)."""
        if not url:
            self.epg_channel_logo.clear()
            return
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                pixmap = await self._fetch_poster(session, url, 64, 64)
                if pixmap:
                    self.epg_channel_logo.setPixmap(pixmap)
        except Exception:
            pass

    def _schedule_from_epg(self, entry):
        """Oeffnet den Planungsdialog fuer eine EPG-Sendung."""
        if not self.api or self._current_epg_stream_id is None:
            return
        channel_name = self.epg_channel_name.text()
        stream_url = self.api.creds.stream_url(self._current_epg_stream_id)
        self._open_schedule_dialog(
            channel_name=channel_name,
            stream_url=stream_url,
            start_ts=entry.start_timestamp,
            end_ts=entry.stop_timestamp,
            epg_title=entry.title,
            fixed_time=True,
        )

    def _play_detail_stream(self):
        """Spielt den im Detailpanel angezeigten Sender ab."""
        data = self._detail_stream_data
        if not data or not self.api:
            return
        if isinstance(data, LiveStream):
            url = self.api.creds.stream_url(data.stream_id)
            self._play_stream(url, data.name, "live", data.stream_id, icon=data.stream_icon)
        elif isinstance(data, Favorite) and data.type == "live":
            url = self.api.creds.stream_url(data.id)
            self._play_stream(url, data.name, "live", data.id, icon=data.icon or "")
