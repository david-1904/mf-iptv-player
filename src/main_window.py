"""
Hauptfenster der IPTV-App — Coordinator
Erbt von allen Mixin-Klassen, die jeweils einen Funktionsbereich abdecken.
"""
import asyncio
import platform

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QApplication,
)
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QPixmap

from xtream_api import XtreamAPI, Category
from account_manager import AccountManager
from favorites_manager import FavoritesManager
from watch_history_manager import WatchHistoryManager
from hidden_categories_manager import HiddenCategoriesManager
from recorder import StreamRecorder
from session_manager import SessionManager

from ui_builder import UiBuilderMixin
from playback_mixin import PlaybackMixin
from vod_detail_mixin import VodDetailMixin
from series_detail_mixin import SeriesDetailMixin
from categories_mixin import CategoriesMixin
from epg_mixin import EpgMixin
from favorites_mixin import FavoritesMixin
from search_mixin import SearchMixin
from history_mixin import HistoryMixin
from stream_controls_mixin import StreamControlsMixin
from account_mixin import AccountMixin
from pip_mixin import PipMixin
from channel_context_mixin import ChannelContextMixin
from updater import UpdateChecker
from app_settings import AppSettings
from schedule_manager import ScheduleManager
from schedule_mixin import ScheduleMixin
from epg_search_mixin import EpgSearchMixin
from i18n import _tr

class MainWindow(
    UiBuilderMixin,
    PlaybackMixin,
    VodDetailMixin,
    SeriesDetailMixin,
    CategoriesMixin,
    EpgMixin,
    FavoritesMixin,
    SearchMixin,
    HistoryMixin,
    StreamControlsMixin,
    AccountMixin,
    PipMixin,
    ChannelContextMixin,
    ScheduleMixin,
    EpgSearchMixin,
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MF IPTV Player")
        self.setMinimumSize(1400, 800)

        self.account_manager = AccountManager()
        self.app_settings = AppSettings()
        self.favorites_manager = FavoritesManager()
        self.history_manager = WatchHistoryManager()
        self.hidden_categories_manager = HiddenCategoriesManager()
        self.session_manager = SessionManager()
        self.recorder = StreamRecorder()
        self.schedule_manager = ScheduleManager()
        self._editing_account_index = -1  # -1 = neu anlegen, >=0 = bearbeiten
        self.api: XtreamAPI | None = None
        self.current_mode = "live"  # live, vod, series, favorites, history, search
        self._last_mode_before_search = "live"

        # Cache fuer geladene Daten
        self.live_categories: list[Category] = []
        self.vod_categories: list[Category] = []
        self.series_categories: list[Category] = []

        # Such-Cache (alle Streams ohne Kategorie-Filter)
        self._search_cache_live = []
        self._search_cache_vod = []
        self._search_cache_series = []
        self._search_cache_loaded = False
        self._search_filter = "all"  # "all", "live", "vod", "series"

        # EPG Cache
        self._epg_cache: dict = {}
        self._current_epg_stream_id: int | None = None
        self._xmltv_epg = None           # XmltvEpg-Instanz wenn externe URL konfiguriert
        self._stream_epg_channel_map: dict[int, str] = {}  # stream_id → tvg-id
        self._current_epg_has_catchup: bool = False
        self._detail_prev_entry = None
        self._detail_now_entry = None
        self._detail_next_entry = None

        # Favoriten-Filter
        self._current_fav_filter = None  # None = Alle, "live"/"vod"/"series" = gefiltert

        # Player-Zustand
        self._player_maximized = False
        self._was_maximized_before_fullscreen = False
        self._pip_mode = False
        self._detail_saved_layout = None  # Layout-Zustand vor VOD/Serien-Detailansicht
        self._current_stream_type = None  # "live" oder "vod"
        self._current_playing_stream_id = None
        self._current_stream_icon: str = ""
        self._current_stream_title: str = ""
        self._current_container_ext: str = ""
        self._current_stream_url: str = ""

        # Timeshift-Zustand
        self._timeshift_active = False
        self._timeshift_paused_at: float = 0
        self._timeshift_start_ts: float = 0.0  # Echtzeit-Timestamp bei dem der Catchup-Stream beginnt

        # Reconnect-Zustand
        self._reconnect_attempt = 0
        self._max_reconnect_attempts = 5
        self._stream_starting = False  # Schutzphase: end-file waehrend Start ignorieren
        self._buffering_accumulated = 0.0   # akkumulierte Buffering-Sekunden (aktueller Stream)
        self._buffering_since: float | None = None  # Timestamp seit wann aktiv gebuffert

        # EPG-Zustand
        self._initial_epg_loaded = False

        # Poster-Cache
        self._image_cache: dict[str, QPixmap | None] = {}
        self._poster_load_generation = 0

        self._update_checker = UpdateChecker()
        self._update_release_info = None

        self.setMinimumSize(920, 600)
        self.resize(1400, 900)  # Vernuenftige Restore-Groesse fuer Fensterleisten-Doppelklick
        self._setup_ui()
        self._setup_statusbar()
        self._load_initial_account()
        self.showMaximized()

        self._bg_tasks: list[asyncio.Task] = []
        self._bg_tasks.append(asyncio.ensure_future(self._check_for_updates()))
        self._bg_tasks.append(asyncio.ensure_future(self._schedule_checker_loop()))

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Linke Sidebar (feste Breite)
        self.sidebar = self._create_sidebar()
        self.sidebar.setFixedWidth(220)
        main_layout.addWidget(self.sidebar)

        # Rechter Content-Bereich
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)

        # Seiten erstellen
        self.settings_page = self._create_settings_page()
        self.main_page = self._create_main_page()

        self.content_stack.addWidget(self.settings_page)
        self.content_stack.addWidget(self.main_page)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize:
            if self.buffering_overlay.parentWidget() is obj:
                self.buffering_overlay.setGeometry(0, 0, obj.width(), obj.height())
                if self.fullscreen_controls.isVisible():
                    self._position_fullscreen_controls()
                if self.info_overlay.isVisible():
                    h = 165
                    self.info_overlay.setGeometry(0, obj.height() - h, obj.width(), h)
                if self.stream_info_panel.isVisible():
                    self._position_stream_info_panel()
            if obj is self.main_page and self._pip_mode:
                self._update_pip_position()
            if obj is self.channel_list.viewport() and self.current_mode in ("vod", "series"):
                QTimer.singleShot(0, self._update_grid_size)
        elif event.type() == QEvent.MouseMove:
            if (obj is self.player_container or obj is self.player) and self.player.is_playing:
                if self._player_maximized:
                    self._show_fullscreen_controls()
            elif obj is self.channel_list.viewport() and self.current_mode == "live":
                delegate = self.channel_list.itemDelegate()
                if delegate and hasattr(delegate, '_hovered_row'):
                    item = self.channel_list.itemAt(event.position().toPoint())
                    row = self.channel_list.row(item) if item else -1
                    if delegate._hovered_row != row:
                        delegate._hovered_row = row
                        self.channel_list.viewport().update()
        elif event.type() == QEvent.Leave:
            if obj is self.channel_list.viewport():
                delegate = self.channel_list.itemDelegate()
                if delegate and hasattr(delegate, '_hovered_row') and delegate._hovered_row != -1:
                    delegate._hovered_row = -1
                    self.channel_list.viewport().update()
        elif event.type() == QEvent.Type.ToolTip:
            if obj is self.channel_list.viewport():
                from PySide6.QtWidgets import QToolTip
                from PySide6.QtGui import QCursor
                from ui_builder import _quality_dot_tooltip
                global_pos = QCursor.pos()
                local_pos = self.channel_list.viewport().mapFromGlobal(global_pos)
                item = self.channel_list.itemAt(local_pos)
                if item:
                    stream = item.data(Qt.UserRole)
                    rect = self.channel_list.visualItemRect(item)
                    delegate = self.channel_list.itemDelegate()
                    right_margin = delegate._right_margin(stream) if (delegate and stream) else 0
                    # Maus im Dot-Bereich (rechts)? → Qualitäts-Tooltip
                    if right_margin > 0 and local_pos.x() >= rect.right() - right_margin - 4:
                        cache = getattr(self, '_stream_quality_cache', {})
                        entry = cache.get(str(getattr(stream, 'stream_id', None)))
                        if isinstance(entry, dict):
                            tip = _quality_dot_tooltip(entry)
                            QToolTip.showText(global_pos, tip) if tip else QToolTip.hideText()
                        else:
                            QToolTip.hideText()
                    else:
                        text = item.text()
                        available = rect.width() - right_margin - 20
                        if self.channel_list.fontMetrics().horizontalAdvance(text) > available:
                            QToolTip.showText(global_pos, text)
                        else:
                            QToolTip.hideText()
                return True
        elif event.type() == QEvent.MouseButtonRelease:
            if obj is getattr(self, '_epg_content_widget', None):
                self._toggle_channel_detail()
                return False
        elif event.type() == QEvent.Enter:
            if obj is self.fullscreen_controls:
                self._fs_controls_timer.stop()
            elif obj is self.player_container and self.player.is_playing:
                if self.player_container.height() >= 200:
                    self._info_overlay_timer.stop()
                    self._show_info_overlay()
        elif event.type() == QEvent.Resize:
            if obj is self.player_container and self._pip_mode:
                self._hide_info_overlay()
        elif event.type() == QEvent.Leave:
            if obj is self.fullscreen_controls:
                self._fs_controls_timer.start(3000)
            elif obj is self.player_container:
                self._info_overlay_timer.start(400)
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._player_maximized:
            self._toggle_player_maximized()
        elif event.key() == Qt.Key_F and event.modifiers() == Qt.NoModifier and self.player.is_playing:
            self._toggle_player_maximized()
        elif event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
            self.content_stack.setCurrentWidget(self.main_page)
            self.search_input.setFocus()
            self.search_input.selectAll()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event):
        """OS-Fenstermaximierung/-Wiederherstellung ohne Layout-Bruch behandeln."""
        if event.type() == QEvent.Type.WindowStateChange:
            if not self._player_maximized:
                QTimer.singleShot(60, self._refresh_player_layout)
        super().changeEvent(event)

    def _refresh_player_layout(self):
        """Passt channel_area-Breite nach OS-Resize an."""
        if self._player_maximized or not self.player_area.isVisible():
            return
        # VOD/Series-Browse: Layout wird von _update_grid_size verwaltet
        if self.current_mode in ("vod", "series"):
            return
        # VOD-Playback: Kanalliste bleibt ausgeblendet, Player füllt volle Breite
        if self._current_stream_type == "vod":
            return
        # Detail-Panel verwaltet seine eigene Breite — nicht ueberschreiben
        if hasattr(self, 'channel_detail_panel') and self.channel_detail_panel.isVisible():
            return
        available = self.main_page.width()
        if available <= 0:
            return
        # Im Live-Modus: gespeicherte Content-Breite bevorzugen
        if self.current_mode == "live" and getattr(self, '_live_channel_area_w', 0) > 0:
            w = max(300, min(500, self._live_channel_area_w))
        else:
            # Breite proportional anpassen: 30% fuer Kanalliste, min 300, max 440
            w = max(300, min(440, int(available * 0.30)))
        self.channel_area.setFixedWidth(w)

    def closeEvent(self, event):
        self._save_current_position()
        # Background-Tasks sofort canceln (verhindert bis zu 30s Warten auf asyncio.sleep)
        for task in getattr(self, "_bg_tasks", []):
            task.cancel()
        if self.recorder.is_recording:
            self.recorder.stop_nowait()
        self.stream_info_timer.stop()
        self.controls_timer.stop()
        self.player.cleanup()
        super().closeEvent(event)

    # ── Auto-Update ──────────────────────────────────────────

    async def _check_for_updates(self):
        try:
            info = await self._update_checker.check_for_update()
        except Exception:
            return
        if not info:
            return
        self._update_release_info = info
        self.btn_update.setText(_tr("Update v{}").format(info.version))
        self.btn_update.clicked.connect(self._show_update_dialog)
        self.btn_update.show()

    def _show_update_dialog(self):
        info = self._update_release_info
        if not info:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(_tr("Update v{}").format(info.version))
        dlg.setMinimumSize(500, 400)
        layout = QVBoxLayout(dlg)

        title = QLabel(_tr("Version {} ist verfügbar!").format(info.version))
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(title)

        if info.release_notes:
            notes_label = QLabel(_tr("Release-Notes:"))
            notes_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(notes_label)
            notes = QTextEdit()
            notes.setReadOnly(True)
            notes.setMarkdown(info.release_notes)
            layout.addWidget(notes)

        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.hide()
        layout.addWidget(progress)

        status_label = QLabel("")
        status_label.setStyleSheet("color: #999;")
        layout.addWidget(status_label)

        update_btn = QPushButton(_tr("\u2B07  Jetzt aktualisieren"))
        update_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: #fff;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:disabled { background-color: #1a3a2a; color: #555; }
        """)
        layout.addWidget(update_btn)

        def on_update():
            update_btn.setEnabled(False)
            progress.show()
            asyncio.ensure_future(self._run_update(info, progress, status_label, update_btn))

        update_btn.clicked.connect(on_update)
        dlg.exec()

    async def _run_update(self, info, progress, status_label, update_btn):
        def on_progress(msg):
            status_label.setText(msg)

        if platform.system() == "Windows":
            success, msg = await self._update_checker.update_windows(
                info.download_url, progress_callback=on_progress
            )
        else:
            success, msg = await self._update_checker.update_linux(
                progress_callback=on_progress
            )

        progress.hide()
        if success:
            if msg == "RESTART":
                # Windows: Updater-Script läuft, App jetzt beenden
                status_label.setText(_tr("Update heruntergeladen \u2013 App wird neu gestartet\u2026"))
                status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
                QTimer.singleShot(1500, QApplication.instance().quit)
            else:
                # Linux: git pull, manueller Neustart nötig
                status_label.setText(_tr("Update erfolgreich! Bitte App neu starten."))
                status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
                update_btn.setText(_tr("\u2714  Bitte App neu starten"))
        else:
            status_label.setText(_tr("Fehler: {}").format(msg))
            status_label.setStyleSheet("color: #f44336;")
            update_btn.setEnabled(True)
