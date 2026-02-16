"""
Hauptfenster der IPTV-App — Coordinator
Erbt von allen Mixin-Klassen, die jeweils einen Funktionsbereich abdecken.
"""
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPixmap

from xtream_api import XtreamAPI, Category
from account_manager import AccountManager
from favorites_manager import FavoritesManager
from watch_history_manager import WatchHistoryManager
from hidden_categories_manager import HiddenCategoriesManager
from recorder import StreamRecorder

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
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MF IPTV Player")
        self.setMinimumSize(1200, 700)

        self.account_manager = AccountManager()
        self.favorites_manager = FavoritesManager()
        self.history_manager = WatchHistoryManager()
        self.hidden_categories_manager = HiddenCategoriesManager()
        self.recorder = StreamRecorder()
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

        # EPG Cache
        self._epg_cache: dict = {}
        self._current_epg_stream_id: int | None = None
        self._current_epg_has_catchup: bool = False

        # Player-Zustand
        self._player_maximized = False
        self._was_maximized_before_fullscreen = False
        self._pip_mode = False
        self._current_stream_type = None  # "live" oder "vod"
        self._current_playing_stream_id = None
        self._current_stream_icon: str = ""
        self._current_stream_title: str = ""
        self._current_container_ext: str = ""
        self._current_stream_url: str = ""

        # Timeshift-Zustand
        self._timeshift_active = False
        self._timeshift_paused_at: float = 0

        # Poster-Cache
        self._image_cache: dict[str, QPixmap | None] = {}
        self._poster_load_generation = 0

        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._load_initial_account()

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
            if self.info_overlay.parentWidget() is obj and self.info_overlay.isVisible():
                w, h = obj.width(), obj.height()
                overlay_h = min(180, h // 2)
                self.info_overlay.setGeometry(0, h - overlay_h, w, overlay_h)
            if obj is self.main_page and self._pip_mode:
                self._update_pip_position()
        elif event.type() == QEvent.MouseMove:
            if self.info_overlay.parentWidget() is obj or obj is self.player:
                if self.player.is_playing:
                    self._show_info_overlay()
        elif event.type() == QEvent.Leave:
            if self.info_overlay.parentWidget() is obj:
                self._info_overlay_timer.start(800)
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._player_maximized:
            self._toggle_player_maximized()
        elif event.key() == Qt.Key_F and event.modifiers() == Qt.ControlModifier:
            self.content_stack.setCurrentWidget(self.main_page)
            self.search_input.setFocus()
            self.search_input.selectAll()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._save_current_position()
        if self.recorder.is_recording:
            self.recorder.stop()
        self.stream_info_timer.stop()
        self.controls_timer.stop()
        self.player.cleanup()
        super().closeEvent(event)
