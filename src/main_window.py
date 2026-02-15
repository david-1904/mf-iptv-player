"""
Hauptfenster der IPTV-App
"""
import asyncio
import aiohttp
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem, QComboBox,
    QPushButton, QLineEdit, QLabel, QMessageBox, QSlider,
    QFrame, QToolBar, QStatusBar, QMenu, QGroupBox, QScrollArea,
    QProgressBar, QAbstractItemView, QScroller
)
from PySide6.QtCore import Qt, QSize, Slot, QTimer, QEvent
from PySide6.QtGui import QIcon, QAction, QPixmap

from xtream_api import XtreamAPI, XtreamCredentials, Category, LiveStream, VodStream, Series, Episode, EpgEntry
from m3u_provider import M3uProvider
from account_manager import AccountManager, AccountEntry
from player_widget import MpvPlayerWidget
from favorites_manager import FavoritesManager, Favorite
from watch_history_manager import WatchHistoryManager, WatchEntry
from recorder import StreamRecorder
from epg_dialog import EpgDialog
from flow_layout import FlowLayout


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MF IPTV Player")
        self.setMinimumSize(1200, 700)

        self.account_manager = AccountManager()
        self.favorites_manager = FavoritesManager()
        self.history_manager = WatchHistoryManager()
        self.recorder = StreamRecorder()
        self.api: XtreamAPI | None = None
        self.current_mode = "live"  # live, vod, series, favorites, history, search
        self._last_mode_before_search = "live"

        # Cache fuer geladene Daten
        self.live_categories: list[Category] = []
        self.vod_categories: list[Category] = []
        self.series_categories: list[Category] = []

        # Such-Cache (alle Streams ohne Kategorie-Filter)
        self._search_cache_live: list[LiveStream] = []
        self._search_cache_vod: list[VodStream] = []
        self._search_cache_series: list[Series] = []
        self._search_cache_loaded = False

        # EPG Cache
        self._epg_cache: dict[int, list[EpgEntry]] = {}
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

    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet("""
            #sidebar {
                background-color: #0d0d14;
                border-right: 1px solid #1a1a2a;
            }
            QPushButton {
                text-align: left;
                padding: 10px 14px;
                margin: 2px 10px;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: #999;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1a1a2a;
                color: #ccc;
            }
            QPushButton:checked {
                background-color: #0078d4;
                border-radius: 8px;
                color: white;
                font-weight: bold;
            }
            QComboBox {
                padding: 6px 8px;
                margin: 6px 10px;
                background: #1e1e2e;
                border: 1px solid #2a2a3a;
                border-radius: 6px;
                color: white;
                font-size: 12px;
            }
            QComboBox:hover { border-color: #0078d4; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1e1e2e;
                color: white;
                selection-background-color: #0078d4;
                border: 1px solid #2a2a3a;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Account-Auswahl
        self.account_combo = QComboBox()
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        layout.addWidget(self.account_combo)
        layout.addSpacing(4)

        # Suchfeld (immer sichtbar, oben)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("\U0001F50D Suche...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 7px 10px;
                margin: 4px 10px;
                background: #1e1e2e;
                border: 1px solid #2a2a3a;
                border-radius: 8px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #0078d4; background: #252535; }
        """)
        self.search_input.returnPressed.connect(self._execute_search)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_input)
        layout.addSpacing(4)

        # Trennlinie
        line0 = QFrame()
        line0.setFrameShape(QFrame.HLine)
        line0.setStyleSheet("background-color: #1a1a2a; margin: 4px 10px;")
        layout.addWidget(line0)

        # Modus-Buttons
        self.btn_live = QPushButton("\U0001F4FA  Live TV")
        self.btn_live.setCheckable(True)
        self.btn_live.setChecked(True)
        self.btn_live.clicked.connect(lambda: self._switch_mode("live"))

        self.btn_vod = QPushButton("\U0001F3AC  Filme")
        self.btn_vod.setCheckable(True)
        self.btn_vod.clicked.connect(lambda: self._switch_mode("vod"))

        self.btn_series = QPushButton("\U0001F4D6  Serien")
        self.btn_series.setCheckable(True)
        self.btn_series.clicked.connect(lambda: self._switch_mode("series"))

        layout.addWidget(self.btn_live)
        layout.addWidget(self.btn_vod)
        layout.addWidget(self.btn_series)

        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #1a1a2a; margin: 4px 10px;")
        layout.addWidget(line)

        # Favoriten-Button
        self.btn_favorites = QPushButton("\u2605  Favoriten")
        self.btn_favorites.setCheckable(True)
        self.btn_favorites.clicked.connect(lambda: self._switch_mode("favorites"))
        layout.addWidget(self.btn_favorites)

        # Verlauf-Button
        self.btn_history = QPushButton("\U0001F552  Verlauf")
        self.btn_history.setCheckable(True)
        self.btn_history.clicked.connect(lambda: self._switch_mode("history"))
        layout.addWidget(self.btn_history)

        # Aufnahmen-Button
        self.btn_recordings = QPushButton("\u23FA  Aufnahmen")
        self.btn_recordings.setCheckable(True)
        self.btn_recordings.clicked.connect(lambda: self._switch_mode("recordings"))
        layout.addWidget(self.btn_recordings)

        # Spacer
        layout.addStretch()

        # Einstellungen-Button
        self.btn_settings = QPushButton("Einstellungen")
        self.btn_settings.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px 14px;
                margin: 2px 10px;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: #666;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1a1a2a;
                color: #999;
            }
        """)
        self.btn_settings.clicked.connect(self._show_settings)
        layout.addWidget(self.btn_settings)

        return sidebar

    def _create_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("Account hinzufuegen")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 16px;")
        layout.addWidget(title)

        # Eingabefelder
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Account-Name")
        layout.addWidget(self.input_name)

        # Account-Typ Auswahl
        type_layout = QHBoxLayout()
        type_label = QLabel("Typ:")
        type_label.setStyleSheet("font-size: 13px; color: #ccc;")
        type_layout.addWidget(type_label)
        self.account_type_combo = QComboBox()
        self.account_type_combo.addItem("Xtream Codes", "xtream")
        self.account_type_combo.addItem("M3U Playlist", "m3u")
        self.account_type_combo.currentIndexChanged.connect(self._on_account_type_changed)
        type_layout.addWidget(self.account_type_combo, stretch=1)
        layout.addLayout(type_layout)

        # Xtream-Felder
        self.xtream_fields = QWidget()
        xtream_layout = QVBoxLayout(self.xtream_fields)
        xtream_layout.setContentsMargins(0, 0, 0, 0)

        self.input_server = QLineEdit()
        self.input_server.setPlaceholderText("Server URL (http://...)")
        xtream_layout.addWidget(self.input_server)

        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("Benutzername")
        xtream_layout.addWidget(self.input_username)

        self.input_password = QLineEdit()
        self.input_password.setPlaceholderText("Passwort")
        self.input_password.setEchoMode(QLineEdit.Password)
        xtream_layout.addWidget(self.input_password)

        layout.addWidget(self.xtream_fields)

        # M3U-Felder
        self.m3u_fields = QWidget()
        m3u_layout = QVBoxLayout(self.m3u_fields)
        m3u_layout.setContentsMargins(0, 0, 0, 0)

        self.input_m3u_url = QLineEdit()
        self.input_m3u_url.setPlaceholderText("M3U Playlist URL (http://...)")
        m3u_layout.addWidget(self.input_m3u_url)

        layout.addWidget(self.m3u_fields)
        self.m3u_fields.hide()

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_add_account = QPushButton("Account speichern")
        self.btn_add_account.clicked.connect(self._add_account)
        btn_layout.addWidget(self.btn_add_account)

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                padding: 8px 16px; border-radius: 6px;
                background-color: #1e1e2e; color: #ccc; border: 1px solid #2a2a3a;
            }
            QPushButton:hover { background-color: #2a2a3a; }
        """)
        self.btn_cancel.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.main_page))
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

        # Account-Liste
        layout.addSpacing(24)
        list_title = QLabel("Gespeicherte Accounts")
        list_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(list_title)

        self.account_list = QListWidget()
        self.account_list.setMaximumHeight(200)
        layout.addWidget(self.account_list)

        self.btn_delete_account = QPushButton("Account loeschen")
        self.btn_delete_account.clicked.connect(self._delete_account)
        layout.addWidget(self.btn_delete_account)

        layout.addStretch()

        return page

    @Slot(int)
    def _on_account_type_changed(self, index: int):
        """Zeigt/versteckt Felder je nach Account-Typ"""
        account_type = self.account_type_combo.itemData(index)
        self.xtream_fields.setVisible(account_type == "xtream")
        self.m3u_fields.setVisible(account_type == "m3u")

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
                    background-color: #1a1a2a;
                    border: none;
                    color: #ddd;
                    font-size: 11px;
                }
                QListWidget::item {
                    padding: 6px;
                    border-radius: 6px;
                    background-color: #1e1e2e;
                }
                QListWidget::item:hover {
                    border: 1px solid #0078d4;
                }
                QListWidget::item:selected {
                    border: 2px solid #0078d4;
                    color: white;
                }
                QScrollBar:vertical {
                    background: #1a1a2a;
                    width: 8px;
                }
                QScrollBar::handle:vertical {
                    background: #444;
                    border-radius: 4px;
                    min-height: 20px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            """)
        else:
            self.channel_list.setStyleSheet("""
                QListWidget {
                    background-color: #121212;
                    border: none;
                    color: #ddd;
                    font-size: 12px;
                }
                QListWidget::item {
                    padding: 8px 10px;
                    border-bottom: 1px solid #1a1a2a;
                }
                QListWidget::item:hover {
                    background-color: #1a1a2a;
                }
                QListWidget::item:selected {
                    background-color: #0a2a4a;
                    border-left: 3px solid #0078d4;
                    color: white;
                }
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

    def _create_channel_area(self) -> QWidget:
        """Erstellt den Kanalbereich mit Liste, EPG-Panel und Serien-Detailansicht"""
        self.channel_stack = QStackedWidget()

        # Seite 0: Kanalliste + EPG
        channel_list_page = QWidget()
        cl_layout = QVBoxLayout(channel_list_page)
        cl_layout.setContentsMargins(0, 0, 0, 0)
        cl_layout.setSpacing(0)

        # Kategorie-Auswahl (Button + inline Liste)
        self.category_btn = QPushButton("Kategorie waehlen  \u25BE")
        self.category_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                margin: 0;
                background: #161622;
                border: none;
                border-bottom: 1px solid #1a1a2a;
                border-radius: 0;
                color: #ccc;
                font-size: 13px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover { background: #1c1c2c; color: white; }
        """)
        self._category_items: list[tuple[str, str]] = []  # (name, id)
        self._current_category_index = -1
        self.category_btn.clicked.connect(self._toggle_category_list)
        cl_layout.addWidget(self.category_btn)

        # Inline-Kategorie-Liste (aufklappbar)
        self.category_list = QListWidget()
        self.category_list.setStyleSheet("""
            QListWidget {
                background: #161622;
                border: none;
                border-bottom: 1px solid #1a1a2a;
                color: #ccc;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 14px;
            }
            QListWidget::item:hover {
                background: #1c1c2c;
                color: white;
            }
            QListWidget::item:selected {
                background: #0a2a4a;
                color: white;
            }
            QScrollBar:vertical {
                background: #161622;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: #444;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.category_list.itemClicked.connect(self._on_category_list_clicked)
        self.category_list.hide()
        cl_layout.addWidget(self.category_list)

        # Sortierung (nur bei VOD/Serien sichtbar)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Standard",
            "Zuletzt hinzugefuegt",
            "Bewertung (beste zuerst)",
            "A - Z",
            "Z - A",
        ])
        self.sort_combo.setStyleSheet("""
            QComboBox {
                padding: 5px 10px;
                margin: 0;
                background: #161622;
                border: none;
                border-bottom: 1px solid #1a1a2a;
                color: #999;
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
        self.sort_combo.hide()
        cl_layout.addWidget(self.sort_combo)

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
        self._loading_text = QLabel("Lade...")
        self._loading_text.setAlignment(Qt.AlignCenter)
        self._loading_text.setStyleSheet("color: #888; font-size: 13px;")
        self._loading_retry_btn = QPushButton("Erneut versuchen")
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
        self._apply_channel_list_style(grid_mode=False)
        self.channel_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.channel_list.itemClicked.connect(self._on_channel_clicked)
        self.channel_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self._show_channel_context_menu)
        cl_layout.addWidget(self.channel_list, stretch=1)

        # EPG Panel
        self.epg_panel = self._create_epg_panel()
        self.epg_panel.setMinimumHeight(120)
        self.epg_panel.setMaximumHeight(220)
        cl_layout.addWidget(self.epg_panel)

        self.channel_stack.addWidget(channel_list_page)

        # Seite 1: Serien-Detailansicht
        self.series_detail_page = self._create_series_detail_page()
        self.channel_stack.addWidget(self.series_detail_page)

        # Seite 2: VOD-Detailansicht
        self.vod_detail_page = self._create_vod_detail_page()
        self.channel_stack.addWidget(self.vod_detail_page)

        return self.channel_stack

    def _create_epg_panel(self) -> QWidget:
        """Creates the EPG info panel"""
        panel = QFrame()
        panel.setObjectName("epgPanel")
        panel.setStyleSheet("""
            #epgPanel {
                background-color: #0d0d14;
                border-top: 1px solid #1a1a2a;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Kopfzeile: Sendername + Button
        header = QHBoxLayout()
        header.setSpacing(8)
        self.epg_channel_name = QLabel("")
        self.epg_channel_name.setStyleSheet("font-size: 13px; font-weight: bold; color: #0078d4;")
        header.addWidget(self.epg_channel_name)
        header.addStretch()

        self.btn_full_epg = QPushButton("Programm \u25B8")
        self.btn_full_epg.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #0078d4;
                border: 1px solid #0078d4;
                padding: 3px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #0078d4; color: white; }
            QPushButton:disabled { border-color: #333; color: #444; }
        """)
        self.btn_full_epg.clicked.connect(self._show_full_epg)
        self.btn_full_epg.setEnabled(False)
        header.addWidget(self.btn_full_epg)
        layout.addLayout(header)

        # Jetzt-Label
        self.epg_now_label = QLabel("JETZT")
        self.epg_now_label.setStyleSheet("font-size: 9px; font-weight: bold; color: #0078d4; letter-spacing: 1px;")
        layout.addWidget(self.epg_now_label)

        # Jetzt: Zeit + Titel
        self.epg_now_title = QLabel("")
        self.epg_now_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #eee;")
        self.epg_now_title.setWordWrap(True)
        layout.addWidget(self.epg_now_title)

        # Fortschrittsbalken
        self.epg_progress = QProgressBar()
        self.epg_progress.setFixedHeight(3)
        self.epg_progress.setTextVisible(False)
        self.epg_progress.setStyleSheet("""
            QProgressBar {
                background: #1a1a2a;
                border: none;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background: #0078d4;
                border-radius: 1px;
            }
        """)
        layout.addWidget(self.epg_progress)

        # Beschreibung
        self.epg_now_desc = QLabel("")
        self.epg_now_desc.setStyleSheet("font-size: 11px; color: #888; line-height: 1.3;")
        self.epg_now_desc.setWordWrap(True)
        layout.addWidget(self.epg_now_desc)

        # Danach-Label + Titel
        self.epg_next_label = QLabel("DANACH")
        self.epg_next_label.setStyleSheet("font-size: 9px; font-weight: bold; color: #555; letter-spacing: 1px; margin-top: 4px;")
        layout.addWidget(self.epg_next_label)

        self.epg_next_title = QLabel("")
        self.epg_next_title.setStyleSheet("font-size: 12px; color: #999;")
        self.epg_next_title.setWordWrap(True)
        layout.addWidget(self.epg_next_title)

        layout.addStretch()
        self._clear_epg_panel()

        return panel

    def _create_series_detail_page(self) -> QWidget:
        """Erstellt die Serien-Detailansicht mit Staffeln und Episoden"""
        page = QWidget()
        page.setStyleSheet("background-color: #121212;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: Zurueck-Button + Serientitel
        header = QFrame()
        header.setStyleSheet("background-color: #0d0d14; border-bottom: 1px solid #1a1a2a;")
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)

        self.btn_series_back = QPushButton("\u2190 Zurueck")
        self.btn_series_back.setStyleSheet("""
            QPushButton {
                background: transparent; color: #0078d4; border: none;
                font-size: 13px; padding: 4px 8px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #1a1a2a; color: #1094e8; }
        """)
        self.btn_series_back.clicked.connect(self._series_back)
        header_layout.addWidget(self.btn_series_back)

        self.series_title_label = QLabel("")
        self.series_title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: white;")
        header_layout.addWidget(self.series_title_label, stretch=1)
        layout.addWidget(header)

        # Info-Bereich: Cover + Plot
        info_frame = QFrame()
        info_frame.setStyleSheet("border-bottom: 1px solid #1a1a2a;")
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_layout.setSpacing(12)

        self.series_cover_label = QLabel()
        self.series_cover_label.setFixedSize(120, 180)
        self.series_cover_label.setStyleSheet("background-color: #1e1e2e; border-radius: 6px; border: none;")
        self.series_cover_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.series_cover_label, alignment=Qt.AlignTop)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(6)

        self.series_plot_label = QLabel("")
        self.series_plot_label.setWordWrap(True)
        self.series_plot_label.setStyleSheet("color: #bbb; font-size: 12px; border: none;")
        self.series_plot_label.setAlignment(Qt.AlignTop)
        meta_layout.addWidget(self.series_plot_label, stretch=1)

        self.series_rating_label = QLabel("")
        self.series_rating_label.setStyleSheet("color: #f0c040; font-size: 12px; border: none;")
        meta_layout.addWidget(self.series_rating_label)

        info_layout.addLayout(meta_layout, stretch=1)
        layout.addWidget(info_frame)

        # Staffel-Auswahl
        season_bar = QFrame()
        season_bar.setFixedHeight(36)
        season_bar.setStyleSheet("background-color: #0d0d14; border-bottom: 1px solid #1a1a2a;")
        season_layout = QHBoxLayout(season_bar)
        season_layout.setContentsMargins(10, 2, 10, 2)

        season_label = QLabel("Staffel:")
        season_label.setStyleSheet("color: #999; font-size: 12px;")
        season_layout.addWidget(season_label)

        self.season_combo = QComboBox()
        self.season_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 8px; background: #1e1e2e; border: 1px solid #2a2a3a;
                border-radius: 6px; color: white; font-size: 12px; min-width: 100px;
            }
            QComboBox:hover { border-color: #0078d4; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #1e1e2e; color: white;
                selection-background-color: #0078d4; border: 1px solid #2a2a3a;
            }
        """)
        self.season_combo.currentIndexChanged.connect(self._on_season_changed)
        season_layout.addWidget(self.season_combo)
        season_layout.addStretch()
        layout.addWidget(season_bar)

        # Episoden-Liste
        self.episode_list = QListWidget()
        self.episode_list.setStyleSheet("""
            QListWidget {
                background-color: #121212; border: none; color: #ddd; font-size: 12px;
            }
            QListWidget::item {
                padding: 8px 10px; border-bottom: 1px solid #1a1a2a;
            }
            QListWidget::item:hover { background-color: #1a1a2a; }
            QListWidget::item:selected {
                background-color: #0a2a4a; border-left: 3px solid #0078d4; color: white;
            }
            QScrollBar:vertical {
                background: #121212; width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #444; border-radius: 4px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.episode_list.itemDoubleClicked.connect(self._on_episode_selected)
        layout.addWidget(self.episode_list, stretch=1)

        # Serien-Daten-Cache
        self._series_data: dict | None = None
        self._current_series: Series | None = None

        return page

    def _show_series_detail(self, series: Series):
        """Zeigt die Serien-Detailansicht an"""
        self._current_series = series
        self.series_title_label.setText(series.name)
        self.series_plot_label.setText(series.plot or "")
        self.series_rating_label.setText(f"Bewertung: {series.rating}" if series.rating and series.rating not in ("0", "") else "")
        self.series_cover_label.clear()
        self.series_cover_label.setText("...")
        self.season_combo.clear()
        self.episode_list.clear()
        self._series_data = None

        self.channel_stack.setCurrentIndex(1)
        asyncio.ensure_future(self._load_series_detail(series))

    async def _load_series_detail(self, series: Series):
        """Laedt Serien-Details asynchron"""
        self._show_loading("Lade Serien-Informationen...")
        try:
            data = await self.api.get_series_info_parsed(series.series_id)
            self._series_data = data

            # Info aktualisieren (API liefert oft ausfuehrlichere Daten)
            info = data.get("info", {})
            plot = info.get("plot", "") or series.plot or ""
            self.series_plot_label.setText(plot)
            rating = str(info.get("rating", "")) or series.rating
            if rating and rating not in ("0", ""):
                self.series_rating_label.setText(f"Bewertung: {rating}")

            # Staffeln eintragen
            self.season_combo.blockSignals(True)
            self.season_combo.clear()
            for s in data["seasons"]:
                self.season_combo.addItem(f"Staffel {s}", s)
            self.season_combo.blockSignals(False)

            # Erste Staffel laden
            if data["seasons"]:
                self._populate_episodes(data["seasons"][0])

            self._hide_loading(f"{len(data['seasons'])} Staffeln geladen")

            # Cover laden
            cover_url = info.get("cover", "") or series.cover
            if cover_url:
                asyncio.ensure_future(self._load_series_cover(cover_url))

        except Exception as e:
            self._hide_loading(f"Fehler: {e}")

    async def _load_series_cover(self, url: str):
        """Laedt das Serien-Cover asynchron"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            pixmap = await self._fetch_poster(session, url, 120, 180)
            if pixmap:
                self.series_cover_label.setPixmap(pixmap)
                self.series_cover_label.setText("")

    @Slot(int)
    def _on_season_changed(self, index: int):
        """Aktualisiert die Episodenliste bei Staffelwechsel"""
        if index >= 0 and self._series_data:
            season = self.season_combo.itemData(index)
            if season is not None:
                self._populate_episodes(season)

    def _populate_episodes(self, season: int):
        """Fuellt die Episodenliste fuer eine Staffel"""
        self.episode_list.clear()
        if not self._series_data:
            return

        episodes = self._series_data["episodes"].get(season, [])
        for ep in episodes:
            text = f"E{ep.episode_num:02d}  {ep.title}"
            if ep.duration:
                text += f"  ({ep.duration})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, ep)
            self.episode_list.addItem(item)

        self.status_bar.showMessage(f"Staffel {season}: {len(episodes)} Episoden")

    @Slot(QListWidgetItem)
    def _on_episode_selected(self, item: QListWidgetItem):
        """Spielt eine Episode ab"""
        ep = item.data(Qt.UserRole)
        if not ep or not self.api:
            return
        url = self.api.creds.series_url(ep.id, ep.container_extension)
        title = f"{self._current_series.name} - S{ep.season:02d}E{ep.episode_num:02d} {ep.title}" if self._current_series else ep.title

        resume_pos = self._check_resume_position(ep.id, "vod")

        self._play_stream(url, title, "vod", ep.id,
                          container_extension=ep.container_extension)

        if resume_pos > 0:
            QTimer.singleShot(500, lambda: self.player.seek(resume_pos, relative=False))

    def _series_back(self):
        """Zurueck zur Kanalliste"""
        self.channel_stack.setCurrentIndex(0)

    # --- VOD Detail ---

    def _create_vod_detail_page(self) -> QWidget:
        """Erstellt die VOD-Detailansicht im Streaming-App-Style"""
        page = QWidget()
        page.setStyleSheet("background-color: #0a0a12;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: Zurueck-Button
        header = QFrame()
        header.setStyleSheet("background-color: #0d0d14; border-bottom: 1px solid #1a1a2a;")
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)

        self.btn_vod_back = QPushButton("\u2190 Zurueck")
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

        # Scrollbarer Inhaltsbereich
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #0a0a12; }
            QScrollBar:vertical { background: #0a0a12; width: 8px; }
            QScrollBar::handle:vertical { background: #333; border-radius: 4px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background-color: #0a0a12;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # === Hero-Bereich: Poster + Infos nebeneinander ===
        hero = QFrame()
        hero.setStyleSheet("background-color: #10101a;")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_layout.setSpacing(24)

        # Grosses Poster (links)
        self.vod_cover_label = QLabel()
        self.vod_cover_label.setFixedSize(220, 330)
        self.vod_cover_label.setStyleSheet("""
            background-color: #1a1a2a;
            border-radius: 8px;
            border: 1px solid #2a2a3a;
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

        self.btn_play_vod = QPushButton("\u25B6\uFE0E  Abspielen")
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

        self.btn_trailer = QPushButton("Trailer")
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
        sep.setStyleSheet("background-color: #1a1a2a;")
        content_layout.addWidget(sep)

        # === Details-Bereich ===
        details = QWidget()
        details.setStyleSheet("background-color: #0a0a12;")
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
        self.vod_plot_header = QLabel("Handlung")
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
        dir_header = QLabel("Regie")
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
        cast_header = QLabel("Besetzung")
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
        self._current_vod: VodStream | None = None
        self._current_trailer_url: str = ""

        return page

    def _show_vod_detail(self, vod: VodStream):
        """Zeigt die VOD-Detailansicht an"""
        self._current_vod = vod
        self.vod_title_label.setText(vod.name)
        self.vod_hero_title.setText(vod.name)
        self.vod_subtitle_label.setText("")
        self.vod_plot_label.setText("")
        self.vod_plot_header.hide()
        self.vod_director_widget.hide()
        self.vod_cast_widget.hide()
        self.vod_genre_widget.hide()
        self.vod_cover_label.clear()
        self.vod_cover_label.setText("...")
        self.btn_trailer.hide()
        self._current_trailer_url = ""
        self._clear_rating_badges()
        self._clear_genre_tags()
        self._clear_cast_chips()

        self.channel_stack.setCurrentIndex(2)
        asyncio.ensure_future(self._load_vod_detail(vod))

    def _clear_rating_badges(self):
        """Entfernt alle Rating-Badges"""
        while self.vod_ratings_layout.count() > 1:
            item = self.vod_ratings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_genre_tags(self):
        """Entfernt alle Genre-Tags"""
        while self.vod_genre_layout.count() > 1:
            item = self.vod_genre_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_genre_tag(self, genre: str):
        """Fuegt ein Genre-Tag als Chip hinzu"""
        chip = QLabel(f"  {genre.strip()}  ")
        chip.setStyleSheet("""
            background-color: #1a1a2a;
            color: #0078d4;
            font-size: 12px;
            padding: 5px 12px;
            border-radius: 12px;
            border: 1px solid #0078d4;
        """)
        self.vod_genre_layout.insertWidget(self.vod_genre_layout.count() - 1, chip)

    def _add_rating_badge(self, source: str, score: str, color: str = "#f0c040"):
        """Fuegt ein Rating-Badge hinzu"""
        badge = QLabel(f"  {source}  {score}  ")
        badge.setStyleSheet(f"""
            background-color: #1a1a2a;
            color: {color};
            font-size: 13px;
            font-weight: bold;
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid #2a2a3a;
        """)
        # Vor dem Stretch einfuegen
        self.vod_ratings_layout.insertWidget(self.vod_ratings_layout.count() - 1, badge)

    def _clear_cast_chips(self):
        """Entfernt alle Besetzungs-Chips"""
        while self.vod_cast_flow_layout.count():
            item = self.vod_cast_flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_cast_chip(self, actor: str, color: str):
        """Fuegt einen Schauspieler-Chip mit Initialen-Kreis hinzu"""
        initials = "".join(w[0].upper() for w in actor.split()[:2] if w)
        chip = QWidget()
        chip.setFixedHeight(34)
        chip.setStyleSheet(f"""
            QWidget {{
                background-color: #1a1a2a;
                border: 1px solid #2a2a3a;
                border-radius: 17px;
            }}
        """)
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(3, 3, 12, 3)
        lay.setSpacing(6)
        # Initialen-Kreis
        circle = QLabel(initials)
        circle.setFixedSize(26, 26)
        circle.setAlignment(Qt.AlignCenter)
        circle.setStyleSheet(f"""
            background-color: {color};
            color: white;
            font-size: 10px;
            font-weight: bold;
            border-radius: 13px;
            border: none;
        """)
        lay.addWidget(circle)
        # Name
        name = QLabel(actor)
        name.setStyleSheet("color: #ccc; font-size: 13px; background: transparent; border: none;")
        lay.addWidget(name)
        self.vod_cast_flow_layout.addWidget(chip)

    async def _load_vod_detail(self, vod: VodStream):
        """Laedt VOD-Details asynchron"""
        self._show_loading("Lade Film-Informationen...")
        try:
            data = await self.api.get_vod_info(vod.stream_id)
            info = data.get("info", {}) or {}

            # Plot
            plot = info.get("plot", "") or info.get("description", "") or ""
            self.vod_plot_label.setText(plot)

            # Untertitel-Zeile: Jahr | Dauer | Genre
            sub_parts = []
            release = info.get("releasedate", "") or info.get("release_date", "")
            if release:
                # Nur das Jahr extrahieren
                year = release[:4] if len(release) >= 4 else release
                sub_parts.append(year)
            duration = info.get("duration", "")
            if duration:
                sub_parts.append(duration)
            genre = info.get("genre", "")
            if genre:
                sub_parts.append(genre)
            self.vod_subtitle_label.setText("  \u2022  ".join(sub_parts))

            # Rating-Badges
            self._clear_rating_badges()
            rating = str(info.get("rating", "")) or vod.rating or ""
            if rating and rating not in ("0", "0.0", ""):
                try:
                    score = float(rating)
                    # Farbe je nach Score
                    if score >= 7:
                        color = "#4caf50"
                    elif score >= 5:
                        color = "#f0c040"
                    else:
                        color = "#f44336"
                    self._add_rating_badge("\u2605 Rating", f"{score:.1f}", color)
                except ValueError:
                    self._add_rating_badge("\u2605 Rating", rating)

            rating_5 = info.get("rating_5based", "")
            if rating_5 and str(rating_5) not in ("0", "0.0", ""):
                try:
                    s5 = float(rating_5)
                    self._add_rating_badge("\u2605 /5", f"{s5:.1f}", "#f0c040")
                except ValueError:
                    pass

            # TMDB-Daten holen falls tmdb_id vorhanden
            tmdb_id = info.get("tmdb_id", "") or info.get("tmdb", "")
            if tmdb_id:
                asyncio.ensure_future(self._fetch_tmdb_ratings(str(tmdb_id)))

            # Genre-Tags
            genre = info.get("genre", "")
            if genre:
                self._clear_genre_tags()
                for g in genre.split(","):
                    g = g.strip()
                    if g:
                        self._add_genre_tag(g)
                self.vod_genre_widget.show()

            # Plot sichtbar machen
            if plot:
                self.vod_plot_header.show()

            # Regie
            director = info.get("director", "")
            if director:
                self.vod_director_label.setText(director)
                self.vod_director_widget.show()

            # Besetzung als Chips (echte Widgets)
            cast = info.get("cast", "") or info.get("actors", "")
            if cast:
                actors = [a.strip() for a in cast.split(",") if a.strip()]
                self._clear_cast_chips()
                colors = ["#0078d4", "#6a5acd", "#2e8b57", "#cd5c5c", "#b8860b",
                          "#4682b4", "#8b668b", "#3cb371", "#cd853f", "#5f9ea0"]
                for i, actor in enumerate(actors):
                    self._add_cast_chip(actor, colors[i % len(colors)])
                self.vod_cast_widget.show()

            # Trailer
            trailer = info.get("youtube_trailer", "") or info.get("trailer", "")
            if trailer:
                if trailer.startswith("http"):
                    self._current_trailer_url = trailer
                else:
                    self._current_trailer_url = f"https://www.youtube.com/watch?v={trailer}"
            else:
                import urllib.parse
                query = urllib.parse.quote_plus(f"{vod.name} trailer")
                self._current_trailer_url = f"https://www.youtube.com/results?search_query={query}"
            self.btn_trailer.show()

            self._hide_loading("")

            # Cover laden
            cover_url = info.get("cover_big", "") or info.get("movie_image", "") or vod.stream_icon
            if cover_url:
                asyncio.ensure_future(self._load_vod_cover(cover_url))

        except Exception as e:
            self._hide_loading(f"Fehler: {e}")
            if vod.stream_icon:
                asyncio.ensure_future(self._load_vod_cover(vod.stream_icon))

    async def _fetch_tmdb_ratings(self, tmdb_id: str):
        """Holt Bewertungen von TMDB - benoetigt TMDB_API_KEY Umgebungsvariable"""
        import os
        api_key = os.environ.get("TMDB_API_KEY", "")
        if not api_key:
            return
        try:
            url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={api_key}&language=de-DE"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return
                    data = await resp.json()

                    vote = data.get("vote_average", 0)
                    vote_count = data.get("vote_count", 0)
                    if vote and vote_count > 0:
                        if vote >= 7:
                            color = "#4caf50"
                        elif vote >= 5:
                            color = "#f0c040"
                        else:
                            color = "#f44336"
                        self._add_rating_badge("TMDB", f"{vote:.1f}", color)

                    # Plot updaten falls leer
                    if not self.vod_plot_label.text():
                        overview = data.get("overview", "")
                        if overview:
                            self.vod_plot_label.setText(overview)

        except Exception:
            pass

    async def _load_vod_cover(self, url: str):
        """Laedt das VOD-Cover asynchron"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            pixmap = await self._fetch_poster(session, url, 220, 330)
            if pixmap:
                scaled = pixmap.scaled(
                    220, 330, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.vod_cover_label.setPixmap(scaled)
                self.vod_cover_label.setText("")

    def _play_current_vod(self):
        """Spielt den aktuellen VOD-Film ab"""
        if not self._current_vod or not self.api:
            return
        vod = self._current_vod
        url = self.api.creds.vod_url(vod.stream_id, vod.container_extension)

        # Fortsetzen-Dialog pruefen
        resume_pos = self._check_resume_position(vod.stream_id, "vod")

        self._play_stream(url, vod.name, "vod", vod.stream_id,
                          icon=getattr(vod, 'stream_icon', ''),
                          container_extension=vod.container_extension)

        if resume_pos > 0:
            QTimer.singleShot(500, lambda: self.player.seek(resume_pos, relative=False))

    def _vod_back(self):
        """Zurueck zur Filmliste"""
        self.channel_stack.setCurrentIndex(0)

    def _play_trailer(self):
        """Oeffnet den Trailer im Browser"""
        if self._current_trailer_url:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(self._current_trailer_url))

    def _create_player_area(self) -> QWidget:
        """Erstellt den Playerbereich mit Header, Video und Controls"""
        area = QWidget()
        area.setObjectName("playerArea")
        area.setStyleSheet("#playerArea { background-color: #000; }")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Player-Header (Titel + Close)
        self.player_header = QWidget()
        self.player_header.setStyleSheet("background-color: #0d0d14; border-bottom: 1px solid #1a1a2a;")
        self.player_header.setFixedHeight(32)
        header_layout = QHBoxLayout(self.player_header)
        header_layout.setContentsMargins(10, 0, 6, 0)

        self.player_title = QLabel("")
        self.player_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #ccc;")
        header_layout.addWidget(self.player_title)
        header_layout.addStretch()

        self.btn_stop = QPushButton("\u2715")
        self.btn_stop.setFixedSize(24, 24)
        self.btn_stop.setStyleSheet("""
            QPushButton { background: transparent; color: #666; border: none; font-size: 14px; }
            QPushButton:hover { color: #ff4444; }
        """)
        self.btn_stop.clicked.connect(self._stop_playback)
        header_layout.addWidget(self.btn_stop)
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

        self.player = MpvPlayerWidget()
        self.player.double_clicked.connect(self._toggle_player_maximized)
        self.player.escape_pressed.connect(self._on_player_escape)
        self.player.buffering_changed.connect(self._on_buffering)
        pc_layout.addWidget(self.player)

        # Buffering-Overlay
        self.buffering_overlay = QLabel("Laden...")
        self.buffering_overlay.setAlignment(Qt.AlignCenter)
        self.buffering_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: #0078d4;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.buffering_overlay.hide()
        self.buffering_overlay.setParent(player_container)

        # Info-Overlay (Hover)
        self.info_overlay = self._create_info_overlay(player_container)
        self.info_overlay.hide()

        self._info_overlay_timer = QTimer()
        self._info_overlay_timer.setSingleShot(True)
        self._info_overlay_timer.timeout.connect(self._hide_info_overlay)

        player_container.setMouseTracking(True)
        self.player.setMouseTracking(True)
        player_container.installEventFilter(self)

        player_layout.addWidget(player_container, stretch=1)

        self.stream_info_panel = self._create_stream_info_panel()
        self.stream_info_panel.setFixedWidth(200)
        self.stream_info_panel.hide()
        player_layout.addWidget(self.stream_info_panel)

        layout.addLayout(player_layout, stretch=1)

        # Player-Controls
        self.player_controls = self._create_player_controls()
        layout.addWidget(self.player_controls)

        # Timer fuer Controls und Stream-Info
        self.stream_info_timer = QTimer()
        self.stream_info_timer.timeout.connect(self._update_stream_info)

        self.controls_timer = QTimer()
        self.controls_timer.timeout.connect(self._update_player_controls)

        self._buffering_dots = 0
        self._buffering_timer = QTimer()
        self._buffering_timer.timeout.connect(self._animate_buffering)

        # PiP-Close-Button (nur im PiP-Modus sichtbar)
        self.pip_close_btn = QPushButton("\u2715", area)
        self.pip_close_btn.setFixedSize(28, 28)
        self.pip_close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(0, 0, 0, 160); color: #ccc; border: none;
                border-radius: 14px; font-size: 13px;
            }
            QPushButton:hover { background: rgba(255, 50, 50, 200); color: white; }
        """)
        self.pip_close_btn.clicked.connect(self._stop_playback)
        self.pip_close_btn.hide()

        return area

    def _create_player_controls(self) -> QWidget:
        """Erstellt die Player-Steuerleiste"""
        bar = QFrame()
        bar.setFixedHeight(48)
        bar.setStyleSheet("""
            QFrame#controlBar {
                background-color: #0d0d14;
                border-top: 1px solid #1a1a2a;
            }
            QPushButton {
                background: transparent;
                color: #ccc;
                border: none;
                font-size: 15px;
                padding: 4px 8px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1a1a2a; color: white; }
            QPushButton:checked { color: #0078d4; }
            QPushButton#recordBtn { color: #ccc; }
            QPushButton#recordBtn:checked { color: #ff4444; background: rgba(255, 68, 68, 30); }
            QPushButton#recordBtn:checked:hover { background: rgba(255, 68, 68, 60); }
        """)
        bar.setObjectName("controlBar")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # Play/Pause
        self.btn_play_pause = QPushButton("\u25B6\uFE0E")
        self.btn_play_pause.setFixedSize(36, 36)
        self.btn_play_pause.setToolTip("Play/Pause (Leertaste)")
        self.btn_play_pause.clicked.connect(self._toggle_play_pause)
        layout.addWidget(self.btn_play_pause)

        # Stop
        self.btn_stop_controls = QPushButton("\u25A0")
        self.btn_stop_controls.setFixedSize(36, 36)
        self.btn_stop_controls.setToolTip("Stop")
        self.btn_stop_controls.clicked.connect(self._stop_playback)
        layout.addWidget(self.btn_stop_controls)

        # Aufnahme
        self.btn_record = QPushButton("\u25CF")
        self.btn_record.setObjectName("recordBtn")
        self.btn_record.setCheckable(True)
        self.btn_record.setFixedSize(36, 36)
        self.btn_record.setToolTip("Aufnahme starten")
        self.btn_record.clicked.connect(self._toggle_recording)
        layout.addWidget(self.btn_record)

        # Skip-Buttons
        self.btn_skip_back = QPushButton("\u25C0\u25C0")
        self.btn_skip_back.setFixedSize(36, 36)
        self.btn_skip_back.setToolTip("-10 Sekunden")
        self.btn_skip_back.clicked.connect(lambda: self._skip_seconds(-10))
        layout.addWidget(self.btn_skip_back)

        self.btn_skip_forward = QPushButton("\u25B6\u25B6")
        self.btn_skip_forward.setFixedSize(36, 36)
        self.btn_skip_forward.setToolTip("+10 Sekunden")
        self.btn_skip_forward.clicked.connect(lambda: self._skip_seconds(10))
        layout.addWidget(self.btn_skip_forward)

        # Trennlinie
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #1e1e2e;")
        layout.addWidget(sep1)

        # Lautstaerke
        vol_label = QLabel("\u266B")
        vol_label.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(vol_label)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1e1e2e;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 2px;
            }
        """)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(self.volume_slider)

        # Trennlinie
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #1e1e2e;")
        layout.addWidget(sep2)

        # Positions-Label
        self.player_pos_label = QLabel("00:00")
        self.player_pos_label.setFixedWidth(55)
        self.player_pos_label.setStyleSheet("color: #999; font-size: 11px;")
        self.player_pos_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.player_pos_label)

        # Seek-Slider
        self._seeking = False
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #1e1e2e;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border-radius: 2px;
            }
        """)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        layout.addWidget(self.seek_slider, stretch=1)

        # Dauer-Label
        self.player_dur_label = QLabel("00:00")
        self.player_dur_label.setFixedWidth(55)
        self.player_dur_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.player_dur_label)

        # EPG-Info (nur fuer Live)
        self.player_info_label = QLabel("")
        self.player_info_label.setStyleSheet("color: #999; font-size: 11px;")
        self.player_info_label.hide()
        layout.addWidget(self.player_info_label, stretch=1)

        # LIVE-Button (Timeshift → zurueck zu Live)
        self.btn_go_live = QPushButton("LIVE")
        self.btn_go_live.setFixedHeight(26)
        self.btn_go_live.setStyleSheet("""
            QPushButton {
                background: transparent; color: #00cc66; border: 1px solid #00cc66;
                padding: 2px 12px; border-radius: 6px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(0, 204, 102, 40); }
        """)
        self.btn_go_live.clicked.connect(self._go_live)
        self.btn_go_live.hide()
        layout.addWidget(self.btn_go_live)

        # Trennlinie
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setStyleSheet("color: #1e1e2e;")
        layout.addWidget(sep3)

        # Audio-Button
        self.btn_audio = QPushButton("Audio")
        self.btn_audio.setFixedHeight(26)
        self.btn_audio.setStyleSheet("""
            QPushButton {
                background: transparent; color: #888; border: 1px solid #2a2a3a;
                padding: 2px 10px; border-radius: 6px; font-size: 11px;
            }
            QPushButton:hover { border-color: #555; color: #ccc; }
        """)
        self.btn_audio.clicked.connect(self._show_audio_menu)
        layout.addWidget(self.btn_audio)

        # Sub-Button
        self.btn_subtitle = QPushButton("Sub")
        self.btn_subtitle.setFixedHeight(26)
        self.btn_subtitle.setStyleSheet("""
            QPushButton {
                background: transparent; color: #888; border: 1px solid #2a2a3a;
                padding: 2px 10px; border-radius: 6px; font-size: 11px;
            }
            QPushButton:hover { border-color: #555; color: #ccc; }
        """)
        self.btn_subtitle.clicked.connect(self._show_subtitle_menu)
        layout.addWidget(self.btn_subtitle)

        # Info-Button
        self.btn_stream_info = QPushButton("Info")
        self.btn_stream_info.setCheckable(True)
        self.btn_stream_info.setFixedHeight(26)
        self.btn_stream_info.setStyleSheet("""
            QPushButton {
                background: transparent; color: #888; border: 1px solid #2a2a3a;
                padding: 2px 10px; border-radius: 6px; font-size: 11px;
            }
            QPushButton:hover { border-color: #555; color: #ccc; }
            QPushButton:checked { border-color: #0078d4; color: #0078d4; }
        """)
        self.btn_stream_info.clicked.connect(self._toggle_stream_info)
        layout.addWidget(self.btn_stream_info)

        return bar

    def _create_info_overlay(self, parent: QWidget) -> QWidget:
        """Erstellt das Info-Overlay fuer Mouse-Hover ueber dem Player"""
        overlay = QFrame(parent)
        overlay.setObjectName("infoOverlay")
        overlay.setStyleSheet("""
            #infoOverlay {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
                    stop:0 rgba(0, 0, 0, 200),
                    stop:0.7 rgba(0, 0, 0, 140),
                    stop:1 rgba(0, 0, 0, 0));
                border: none;
            }
        """)

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 40, 20, 16)
        layout.setSpacing(6)

        layout.addStretch()

        # Zeile: Logo + Sendername
        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        self.overlay_logo = QLabel()
        self.overlay_logo.setFixedSize(64, 64)
        self.overlay_logo.setStyleSheet("background: transparent;")
        self.overlay_logo.setAlignment(Qt.AlignCenter)
        self.overlay_logo.hide()
        title_row.addWidget(self.overlay_logo)

        self.overlay_title = QLabel("")
        self.overlay_title.setStyleSheet("font-size: 18px; font-weight: bold; color: white; background: transparent;")
        title_row.addWidget(self.overlay_title, stretch=1)

        layout.addLayout(title_row)

        # EPG: Aktuelle Sendung
        self.overlay_now = QLabel("")
        self.overlay_now.setStyleSheet("font-size: 13px; color: #ccc; background: transparent;")
        self.overlay_now.setWordWrap(True)
        layout.addWidget(self.overlay_now)

        # Fortschrittsbalken
        self.overlay_progress = QProgressBar()
        self.overlay_progress.setFixedHeight(3)
        self.overlay_progress.setTextVisible(False)
        self.overlay_progress.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,30); border: none; border-radius: 1px; }
            QProgressBar::chunk { background: #0078d4; border-radius: 1px; }
        """)
        self.overlay_progress.hide()
        layout.addWidget(self.overlay_progress)

        # EPG: Naechste Sendung
        self.overlay_next = QLabel("")
        self.overlay_next.setStyleSheet("font-size: 13px; color: #999; background: transparent;")
        layout.addWidget(self.overlay_next)

        return overlay

    def _show_info_overlay(self):
        """Zeigt das Info-Overlay und aktualisiert den Inhalt"""
        if not self.player_area.isVisible() or self._pip_mode:
            return

        # Titel
        title = self.player_title.text()
        self.overlay_title.setText(title)

        # Logo
        logo_key = f"{self._current_stream_icon}_128x128"
        if self._current_stream_icon:
            if logo_key in self._image_cache:
                cached = self._image_cache[logo_key]
                if cached:
                    self.overlay_logo.setPixmap(cached.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.overlay_logo.show()
                else:
                    self.overlay_logo.hide()
            else:
                # Noch nicht geladen
                self.overlay_logo.hide()
                asyncio.ensure_future(self._load_overlay_logo(self._current_stream_icon))
        else:
            self.overlay_logo.hide()

        # EPG-Daten
        now_ts = datetime.now().timestamp()
        current_entry = None
        next_entry = None
        if self._current_playing_stream_id and self._current_stream_type == "live":
            epg = self._epg_cache.get(self._current_playing_stream_id, [])
            for entry in epg:
                if entry.start_timestamp <= now_ts <= entry.stop_timestamp:
                    current_entry = entry
                elif entry.start_timestamp > now_ts and next_entry is None:
                    next_entry = entry

        if current_entry:
            start = datetime.fromtimestamp(current_entry.start_timestamp).strftime("%H:%M")
            end = datetime.fromtimestamp(current_entry.stop_timestamp).strftime("%H:%M")
            self.overlay_now.setText(f"{start} – {end}   {current_entry.title}")
            self.overlay_now.show()
            duration = current_entry.stop_timestamp - current_entry.start_timestamp
            if duration > 0:
                elapsed = now_ts - current_entry.start_timestamp
                self.overlay_progress.setValue(max(0, min(100, int(elapsed / duration * 100))))
                self.overlay_progress.show()
            else:
                self.overlay_progress.hide()
        else:
            self.overlay_now.hide()
            self.overlay_progress.hide()

        if next_entry:
            start = datetime.fromtimestamp(next_entry.start_timestamp).strftime("%H:%M")
            self.overlay_next.setText(f"Danach: {start}  {next_entry.title}")
            self.overlay_next.show()
        else:
            self.overlay_next.hide()

        # Overlay positionieren (untere Haelfte des player_container)
        parent = self.info_overlay.parentWidget()
        if parent:
            w = parent.width()
            h = parent.height()
            overlay_h = min(180, h // 2)
            self.info_overlay.setGeometry(0, h - overlay_h, w, overlay_h)

        self.info_overlay.raise_()
        self.info_overlay.show()
        self._info_overlay_timer.start(3000)

    def _hide_info_overlay(self):
        self.info_overlay.hide()

    async def _load_overlay_logo(self, url: str):
        """Laedt das Senderlogo fuer das Overlay"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                pixmap = await self._fetch_poster(session, url, 128, 128)
                if pixmap and self._current_stream_icon == url and self.info_overlay.isVisible():
                    self.overlay_logo.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.overlay_logo.show()
        except Exception:
            pass

    def _create_stream_info_panel(self) -> QWidget:
        """Creates the stream info panel"""
        panel = QFrame()
        panel.setObjectName("streamInfoPanel")
        panel.setStyleSheet("""
            #streamInfoPanel {
                background-color: #0d0d14;
                border-left: 1px solid #1a1a2a;
            }
            QLabel {
                color: #ccc;
            }
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 1px solid #1a1a2a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(250)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Video Info
        video_group = QGroupBox("Video")
        video_layout = QVBoxLayout(video_group)

        self.info_resolution = QLabel("Aufloesung: -")
        video_layout.addWidget(self.info_resolution)

        self.info_fps = QLabel("FPS: -")
        video_layout.addWidget(self.info_fps)

        self.info_video_codec = QLabel("Codec: -")
        video_layout.addWidget(self.info_video_codec)

        layout.addWidget(video_group)

        # Audio Info
        audio_group = QGroupBox("Audio")
        audio_layout = QVBoxLayout(audio_group)

        self.info_audio_codec = QLabel("Codec: -")
        audio_layout.addWidget(self.info_audio_codec)

        self.info_audio_tracks = QLabel("Tonspuren: -")
        audio_layout.addWidget(self.info_audio_tracks)

        layout.addWidget(audio_group)

        layout.addStretch()

        return panel

    def _setup_toolbar(self):
        toolbar = QToolBar("Hauptwerkzeugleiste")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        # Refresh-Action
        refresh_action = QAction("Aktualisieren", self)
        refresh_action.triggered.connect(self._refresh_current)
        toolbar.addAction(refresh_action)

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit")

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # indeterminate
        self.loading_bar.setFixedSize(120, 14)
        self.loading_bar.hide()
        self.status_bar.addPermanentWidget(self.loading_bar)

    def _show_loading(self, message: str):
        self.status_bar.showMessage(message)
        self.loading_bar.show()
        # Kanalliste verstecken, Overlay zeigen (nur auf Seite 0)
        if self.channel_stack.currentIndex() == 0:
            self._loading_text.setText(message)
            self._loading_spinner.show()
            self._loading_retry_btn.hide()
            self.channel_list.hide()
            self.epg_panel.hide()
            self.channel_loading.show()

    def _hide_loading(self, message: str = "Bereit"):
        self.loading_bar.hide()
        self.status_bar.showMessage(message)
        # Overlay verstecken, Kanalliste zeigen
        self.channel_loading.hide()
        if self.channel_stack.currentIndex() == 0:
            self.channel_list.show()
            if self.current_mode == "live":
                self.epg_panel.show()

    def _show_loading_error(self, error: str):
        """Zeigt Fehler im Loading-Overlay mit Retry-Button"""
        self.loading_bar.hide()
        self.status_bar.showMessage(f"Fehler: {error}")
        if self.channel_stack.currentIndex() == 0:
            self._loading_spinner.hide()
            self._loading_text.setText(f"Verbindungsfehler\n{error}")
            self._loading_retry_btn.show()
            self.channel_loading.show()
            self.channel_list.hide()

    def _retry_load(self):
        """Laedt erneut nach einem Fehler"""
        # Caches leeren fuer den aktuellen Modus
        if self.current_mode == "live":
            self.live_categories = []
        elif self.current_mode == "vod":
            self.vod_categories = []
        elif self.current_mode == "series":
            self.series_categories = []
        asyncio.ensure_future(self._load_categories())

    def _load_initial_account(self):
        """Laedt gespeicherte Accounts beim Start"""
        self._update_account_combo()
        account = self.account_manager.get_selected()
        if account:
            if account.type == "m3u":
                self.api = M3uProvider(account.name, account.url)
                self.content_stack.setCurrentWidget(self.main_page)
                asyncio.ensure_future(self._load_m3u_and_categories())
            else:
                creds = XtreamCredentials(
                    server=account.server, username=account.username,
                    password=account.password, name=account.name,
                )
                self.api = XtreamAPI(creds)
                self.content_stack.setCurrentWidget(self.main_page)
                asyncio.ensure_future(self._load_categories())
            self._update_series_button_visibility()
        else:
            self.content_stack.setCurrentWidget(self.settings_page)

    async def _load_m3u_and_categories(self):
        """Laedt M3U-Playlist und dann die Kategorien"""
        self._show_loading("Lade M3U-Playlist...")
        try:
            await self.api.load()
            await self._load_categories()
        except Exception as e:
            self._show_loading_error(str(e))

    def _update_series_button_visibility(self):
        """Blendet Serien-Button aus wenn M3U Account aktiv"""
        account = self.account_manager.get_selected()
        is_m3u = account and account.type == "m3u"
        self.btn_series.setVisible(not is_m3u)
        if is_m3u and self.current_mode == "series":
            self._switch_mode("live")

    def _update_account_combo(self):
        """Aktualisiert die Account-Dropdown"""
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for acc in self.account_manager.get_all():
            if acc.type == "m3u":
                self.account_combo.addItem(f"{acc.name} (M3U)")
            else:
                self.account_combo.addItem(f"{acc.name} (Xtream)")
        self.account_combo.setCurrentIndex(self.account_manager.selected_index)
        self.account_combo.blockSignals(False)

        # Account-Liste in Einstellungen aktualisieren
        self.account_list.clear()
        for acc in self.account_manager.get_all():
            if acc.type == "m3u":
                self.account_list.addItem(f"{acc.name} (M3U)")
            else:
                self.account_list.addItem(f"{acc.name} (Xtream - {acc.server})")

    @Slot(int)
    def _on_account_changed(self, index: int):
        if index >= 0:
            self.account_manager.select_account(index)
            account = self.account_manager.get_selected()
            if account:
                # Cache leeren
                self.live_categories = []
                self.vod_categories = []
                self.series_categories = []
                self._search_cache_loaded = False

                if account.type == "m3u":
                    self.api = M3uProvider(account.name, account.url)
                    asyncio.ensure_future(self._load_m3u_and_categories())
                else:
                    creds = XtreamCredentials(
                        server=account.server, username=account.username,
                        password=account.password, name=account.name,
                    )
                    self.api = XtreamAPI(creds)
                    asyncio.ensure_future(self._load_categories())

                self._update_series_button_visibility()

    def _switch_mode(self, mode: str):
        if mode == "search" and self.current_mode != "search":
            self._last_mode_before_search = self.current_mode
        self.current_mode = mode

        # Buttons aktualisieren
        self.btn_live.setChecked(mode == "live")
        self.btn_vod.setChecked(mode == "vod")
        self.btn_series.setChecked(mode == "series")
        self.btn_favorites.setChecked(mode == "favorites")
        self.btn_history.setChecked(mode == "history")
        self.btn_recordings.setChecked(mode == "recordings")

        # Kategorie nur bei Live/VOD/Serien anzeigen
        self.category_btn.setVisible(mode in ("live", "vod", "series"))
        if mode not in ("live", "vod", "series"):
            self.category_list.hide()

        # Sortierung nur bei VOD/Serien anzeigen
        self.sort_combo.setVisible(mode in ("vod", "series"))

        # Detail-Ansichten zuruecksetzen
        self.channel_stack.setCurrentIndex(0)

        # PiP-Modus umschalten wenn Player laeuft
        is_grid_mode = mode in ("vod", "series")
        if self.player_area.isVisible() and not self._player_maximized:
            if is_grid_mode and not self._pip_mode:
                self._enter_pip_mode()
            elif not is_grid_mode and self._pip_mode:
                self._exit_pip_mode()

        if mode == "favorites":
            self._load_favorites()
        elif mode == "history":
            self._load_history()
        elif mode == "recordings":
            self._load_recordings()
        elif mode == "search":
            # Liste fuer Suchmodus vorbereiten
            QScroller.ungrabGesture(self.channel_list.viewport())
            self.channel_list.setViewMode(QListWidget.ListMode)
            self.channel_list.setIconSize(QSize(0, 0))
            self.channel_list.setGridSize(QSize())
            self.channel_list.setResizeMode(QListWidget.Fixed)
            self.channel_list.setWordWrap(False)
            self.channel_list.setSpacing(0)
            self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
            self._apply_channel_list_style(grid_mode=False)
            self.epg_panel.setVisible(False)
            self.channel_list.clear()
            self.status_bar.showMessage("Enter druecken zum Suchen")
        else:
            # Sofort Loading-Zustand zeigen (nicht auf async warten)
            self.channel_list.clear()
            self.channel_list.hide()
            self.epg_panel.hide()
            self._loading_text.setText("Lade...")
            self.channel_loading.show()
            asyncio.ensure_future(self._load_categories())

    def _enter_pip_mode(self):
        """Wechselt den Player in den PiP-Modus (klein, rechts unten)"""
        if self._pip_mode:
            return
        self._pip_mode = True

        # Aus dem Layout nehmen
        self.main_page.layout().removeWidget(self.player_area)

        # Controls und Header verstecken
        self.player_header.hide()
        self.player_controls.hide()
        if self.stream_info_panel.isVisible():
            self.stream_info_panel.hide()
            self.btn_stream_info.setChecked(False)
            self.stream_info_timer.stop()

        # Feste Groesse + Styling fuer PiP
        self.player_area.setFixedSize(380, 220)
        self.player_area.setStyleSheet("""
            #playerArea {
                background-color: #000;
                border: 2px solid #333;
                border-radius: 8px;
            }
        """)

        # PiP-Close-Button positionieren und zeigen
        self.pip_close_btn.move(self.player_area.width() - 34, 6)
        self.pip_close_btn.raise_()
        self.pip_close_btn.show()

        # Position aktualisieren und anzeigen
        self._update_pip_position()
        self.player_area.raise_()
        self.player_area.show()

        # Kanalliste volle Breite freigeben
        self.channel_area.setMinimumWidth(0)
        self.channel_area.setMaximumWidth(16777215)

    def _exit_pip_mode(self):
        """Wechselt den Player zurueck in den normalen Modus"""
        if not self._pip_mode:
            return
        self._pip_mode = False

        # PiP-Button verstecken
        self.pip_close_btn.hide()

        # Feste Groesse aufheben
        self.player_area.setMinimumSize(0, 0)
        self.player_area.setMaximumSize(16777215, 16777215)
        self.player_area.setStyleSheet("#playerArea { background-color: #000; }")

        # Header und Controls wieder zeigen
        self.player_header.show()
        self.player_controls.show()

        # Zurueck ins Layout
        self.main_page.layout().addWidget(self.player_area)

        # Kanalliste feste Breite
        width = 400 if self.current_mode in ("vod", "series") else 320
        self.channel_area.setFixedWidth(width)

    def _update_pip_position(self):
        """Positioniert den PiP-Player in die rechte untere Ecke"""
        if not self._pip_mode:
            return
        parent = self.main_page
        margin = 16
        x = parent.width() - self.player_area.width() - margin
        y = parent.height() - self.player_area.height() - margin
        self.player_area.move(max(0, x), max(0, y))

    async def _load_categories(self):
        if not self.api:
            return

        self._show_loading("Lade Kategorien...")

        try:
            if self.current_mode == "live":
                if not self.live_categories:
                    self.live_categories = await self.api.get_live_categories()
                categories = self.live_categories
            elif self.current_mode == "vod":
                if not self.vod_categories:
                    self.vod_categories = await self.api.get_vod_categories()
                categories = self.vod_categories
            else:
                if not self.series_categories:
                    self.series_categories = await self.api.get_series_categories()
                categories = self.series_categories

            self._category_items = [(cat.category_name, cat.category_id) for cat in categories]
            self._current_category_index = 0 if categories else -1
            self.category_list.clear()
            for cat in categories:
                self.category_list.addItem(cat.category_name)
            self.category_list.hide()
            if categories:
                self.category_btn.setText(f"{categories[0].category_name}  \u25BE")
                await self._load_items(categories[0].category_id)
            else:
                self.category_btn.setText("Keine Kategorien")

            self._hide_loading()
        except Exception as e:
            self._show_loading_error(str(e))

    def _sort_items(self, items):
        """Sortiert VOD/Serien-Items nach aktueller Sortierauswahl"""
        sort_index = self.sort_combo.currentIndex()
        if sort_index == 0:  # Standard
            return items
        elif sort_index == 1:  # Zuletzt hinzugefuegt
            return sorted(items, key=lambda x: x.added or "", reverse=True)
        elif sort_index == 2:  # Bewertung (beste zuerst)
            def rating_key(x):
                try:
                    return float(x.rating) if x.rating else 0.0
                except ValueError:
                    return 0.0
            return sorted(items, key=rating_key, reverse=True)
        elif sort_index == 3:  # A - Z
            return sorted(items, key=lambda x: x.name.lower())
        elif sort_index == 4:  # Z - A
            return sorted(items, key=lambda x: x.name.lower(), reverse=True)
        return items

    def _on_sort_changed(self):
        """Sortierung geaendert - Kategorie neu laden"""
        if self.current_mode not in ("vod", "series"):
            return
        if self._current_category_index < 0:
            return
        _, cat_id = self._category_items[self._current_category_index]
        asyncio.ensure_future(self._load_items(cat_id))

    def _toggle_category_list(self):
        """Klappt die Kategorie-Liste auf/zu"""
        if self.category_list.isVisible():
            self._close_category_list()
        else:
            self.category_list.show()
            self.channel_list.hide()
            self.epg_panel.hide()
            # Zur aktuellen Kategorie scrollen
            if 0 <= self._current_category_index < self.category_list.count():
                self.category_list.setCurrentRow(self._current_category_index)
                self.category_list.scrollToItem(self.category_list.currentItem())
            name = self._category_items[self._current_category_index][0] if self._current_category_index >= 0 else "Kategorie"
            self.category_btn.setText(f"{name}  \u25B4")

    def _close_category_list(self):
        """Schliesst die Kategorie-Liste und zeigt Kanalliste wieder"""
        self.category_list.hide()
        self.channel_list.show()
        if self.current_mode == "live":
            self.epg_panel.show()
        name = self._category_items[self._current_category_index][0] if self._current_category_index >= 0 else "Kategorie"
        self.category_btn.setText(f"{name}  \u25BE")

    def _on_category_list_clicked(self, item: QListWidgetItem):
        """Kategorie aus der inline-Liste gewaehlt"""
        index = self.category_list.row(item)
        self._current_category_index = index
        name, cat_id = self._category_items[index]
        self._close_category_list()
        asyncio.ensure_future(self._load_items(cat_id))

    async def _load_items(self, category_id: str):
        if not self.api:
            return

        self._show_loading("Lade Inhalte...")
        self.channel_list.clear()

        # View-Modus je nach Kategorie umschalten
        is_grid = self.current_mode in ("vod", "series")
        # Scroller-Zustand immer zuerst aufraumen
        QScroller.ungrabGesture(self.channel_list.viewport())
        if is_grid:
            self.channel_list.setViewMode(QListWidget.IconMode)
            self.channel_list.setIconSize(QSize(150, 220))
            self.channel_list.setGridSize(QSize(170, 280))
            self.channel_list.setResizeMode(QListWidget.Adjust)
            self.channel_list.setWordWrap(True)
            self.channel_list.setSpacing(10)
            self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            self.channel_list.verticalScrollBar().setSingleStep(60)
            # Drag-to-Scroll im Grid-Modus
            QScroller.grabGesture(self.channel_list.viewport(), QScroller.LeftMouseButtonGesture)
        else:
            self.channel_list.setViewMode(QListWidget.ListMode)
            self.channel_list.setIconSize(QSize(32, 32))
            self.channel_list.setGridSize(QSize())
            self.channel_list.setResizeMode(QListWidget.Fixed)
            self.channel_list.setWordWrap(False)
            self.channel_list.setSpacing(0)
            self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self._apply_channel_list_style(grid_mode=is_grid)
        self.epg_panel.setVisible(self.current_mode == "live")

        try:
            if self.current_mode == "live":
                items = await self.api.get_live_streams(category_id)
                for item in items:
                    name = item.name
                    if item.tv_archive:
                        name += "  \u25C2\u25C2"
                    list_item = QListWidgetItem(name)
                    list_item.setData(Qt.UserRole, item)
                    self.channel_list.addItem(list_item)

            elif self.current_mode == "vod":
                items = await self.api.get_vod_streams(category_id)
                items = self._sort_items(items)
                for item in items:
                    list_item = QListWidgetItem(item.name)
                    list_item.setData(Qt.UserRole, item)
                    if item.rating and item.rating not in ("0", ""):
                        list_item.setToolTip(f"Bewertung: {item.rating}")
                    self.channel_list.addItem(list_item)

            else:  # series
                items = await self.api.get_series(category_id)
                items = self._sort_items(items)
                for item in items:
                    list_item = QListWidgetItem(item.name)
                    list_item.setData(Qt.UserRole, item)
                    if item.rating and item.rating not in ("0", ""):
                        list_item.setToolTip(f"Bewertung: {item.rating}")
                    self.channel_list.addItem(list_item)

            self._hide_loading(f"{self.channel_list.count()} Eintraege geladen")

            # Poster/Logos laden
            asyncio.ensure_future(self._load_item_posters())

        except Exception as e:
            self._show_loading_error(str(e))

    async def _load_item_posters(self):
        """Laedt Poster/Cover/Logos"""
        self._poster_load_generation += 1
        current_gen = self._poster_load_generation
        icon_size = self.channel_list.iconSize()
        sem = asyncio.Semaphore(8)

        items_to_load = []
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            data = item.data(Qt.UserRole)
            url = ""
            if isinstance(data, LiveStream):
                url = data.stream_icon
            elif isinstance(data, VodStream):
                url = data.stream_icon
            elif isinstance(data, Series):
                url = data.cover
            if url:
                items_to_load.append((i, url))

        if not items_to_load:
            return

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async def load_one(index, url):
                async with sem:
                    if self._poster_load_generation != current_gen:
                        return
                    pixmap = await self._fetch_poster(session, url, icon_size.width(), icon_size.height())
                    if pixmap and self._poster_load_generation == current_gen:
                        item = self.channel_list.item(index)
                        if item:
                            item.setIcon(QIcon(pixmap))

            await asyncio.gather(
                *[load_one(i, url) for i, url in items_to_load],
                return_exceptions=True
            )

    async def _fetch_poster(self, session: aiohttp.ClientSession, url: str, w: int, h: int) -> QPixmap | None:
        """Laedt ein Bild, skaliert und cached es"""
        cache_key = f"{url}_{w}x{h}"
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    pixmap = QPixmap()
                    pixmap.loadFromData(data)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self._image_cache[cache_key] = scaled
                        return scaled
        except Exception:
            pass

        self._image_cache[cache_key] = None
        return None

    @Slot(QListWidgetItem)
    def _on_channel_selected(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if not data:
            return

        # Aufnahmen brauchen kein API
        if isinstance(data, tuple) and len(data) == 2 and data[0] == "recording":
            filepath = data[1]
            name = filepath.stem.replace("_", " ")
            self._play_stream(str(filepath), name, "vod")
            return

        if not self.api:
            return

        if isinstance(data, LiveStream):
            url = self.api.creds.stream_url(data.stream_id)
            self._play_stream(url, data.name, "live", data.stream_id, icon=data.stream_icon)

        elif isinstance(data, VodStream):
            self._show_vod_detail(data)

        elif isinstance(data, Series):
            self._show_series_detail(data)

        elif isinstance(data, WatchEntry):
            if data.stream_type == "live":
                url = self.api.creds.stream_url(data.stream_id)
                self._play_stream(url, data.title, "live", data.stream_id, icon=data.icon)
            elif data.stream_type == "vod":
                vod = VodStream(
                    stream_id=data.stream_id, name=data.title,
                    stream_icon=data.icon,
                    container_extension=data.container_extension or "mp4"
                )
                self._show_vod_detail(vod)

        elif isinstance(data, Favorite):
            if data.type == "live":
                url = self.api.creds.stream_url(data.id)
                self._play_stream(url, data.name, "live", data.id, icon=data.icon or "")
            elif data.type == "vod":
                vod = VodStream(
                    stream_id=data.id, name=data.name,
                    stream_icon=data.icon,
                    container_extension=data.container_extension or "mp4"
                )
                self._show_vod_detail(vod)
            elif data.type == "series":
                s = Series(series_id=data.id, name=data.name, cover=data.icon)
                self._show_series_detail(s)

    def _play_stream(self, url: str, title: str, stream_type: str = "live", stream_id: int = None, icon: str = "", container_extension: str = ""):
        """Spielt einen Stream im integrierten Player ab"""
        # Vorherige Position speichern
        self._save_current_position()

        self.player_title.setText(title)
        self._current_stream_type = stream_type
        self._current_playing_stream_id = stream_id
        self._current_stream_icon = icon
        self._current_stream_title = title
        self._current_container_ext = container_extension
        self._current_stream_url = url
        self._timeshift_active = False
        self._timeshift_paused_at = 0

        is_grid_mode = self.current_mode in ("vod", "series")

        if not self.player_area.isVisible():
            if is_grid_mode:
                # Im Grid-Modus: PiP statt side-by-side
                self.player_area.show()
                self._enter_pip_mode()
            else:
                # Normaler Modus: side-by-side
                self.channel_area.setFixedWidth(320)
                self.player_area.show()
        elif self._pip_mode and not is_grid_mode:
            # War PiP, jetzt nicht mehr Grid → zurueck zu normal
            self._exit_pip_mode()

        self._update_seek_controls_visibility()
        self.player.play(url)
        self.btn_play_pause.setText("\u2759\u2759")
        self.player_info_label.setText("")
        self.controls_timer.start(1000)
        self.status_bar.showMessage(f"Spiele: {title}")

        # Verlaufseintrag anlegen
        account = self.account_manager.get_selected()
        if account and stream_id is not None:
            entry = WatchEntry(
                stream_id=stream_id,
                stream_type=stream_type,
                account_name=account.name,
                title=title,
                icon=icon,
                container_extension=container_extension,
            )
            self.history_manager.add_or_update(entry)

    def _stop_playback(self):
        """Stoppt die Wiedergabe und versteckt den Player"""
        self._save_current_position()
        if self.recorder.is_recording:
            self.recorder.stop()
            self._update_record_button()
        self.player.stop()
        self.buffering_overlay.hide()
        self.info_overlay.hide()
        self.stream_info_timer.stop()
        self.controls_timer.stop()
        self.btn_stream_info.setChecked(False)
        self.stream_info_panel.hide()
        self._current_stream_type = None
        self._current_playing_stream_id = None
        self._current_stream_url = ""
        self._timeshift_active = False
        self._timeshift_paused_at = 0
        if self._player_maximized:
            self._toggle_player_maximized()
        if self._pip_mode:
            # PiP-Modus sauber verlassen
            self._pip_mode = False
            self.pip_close_btn.hide()
            self.player_area.setMinimumSize(0, 0)
            self.player_area.setMaximumSize(16777215, 16777215)
            self.player_area.setStyleSheet("#playerArea { background-color: #000; }")
            self.player_header.show()
            self.player_controls.show()
            self.main_page.layout().addWidget(self.player_area)
        self.player_area.hide()
        # Kanalliste wieder voll breit
        self.channel_area.setMinimumWidth(0)
        self.channel_area.setMaximumWidth(16777215)

    @Slot(bool)
    def _on_buffering(self, buffering: bool):
        """Zeigt/versteckt den Lade-Indikator im Player"""
        if buffering:
            # Overlay auf volle Groesse des Parents setzen
            parent = self.buffering_overlay.parentWidget()
            if parent:
                self.buffering_overlay.setGeometry(0, 0, parent.width(), parent.height())
            self.buffering_overlay.raise_()
            self.buffering_overlay.show()
            self._buffering_dots = 0
            self._buffering_timer.start(400)
        else:
            self._buffering_timer.stop()
            self.buffering_overlay.hide()

    def _animate_buffering(self):
        """Animiert den Buffering-Text"""
        self._buffering_dots = (self._buffering_dots + 1) % 4
        dots = "." * self._buffering_dots
        self.buffering_overlay.setText(f"Laden{dots}")

    def _toggle_play_pause(self):
        """Play/Pause umschalten - mit Timeshift fuer Catchup-Sender"""
        if (self._current_stream_type == "live"
                and self._current_epg_has_catchup
                and not self._timeshift_active):
            if self.player.is_playing:
                # Pause bei Live mit Catchup: Timestamp merken
                self._timeshift_paused_at = datetime.now().timestamp()
                self.player.pause()
                self.btn_play_pause.setText("\u25B6\uFE0E")
            else:
                # Resume nach Pause: in Timeshift wechseln
                self._enter_timeshift(self._timeshift_paused_at)
                self.btn_play_pause.setText("\u2759\u2759")
            return

        self.player.pause()
        if self.player.is_playing:
            self.btn_play_pause.setText("\u2759\u2759")
        else:
            self.btn_play_pause.setText("\u25B6\uFE0E")

    def _enter_timeshift(self, start_timestamp: float):
        """Wechselt vom Live-Stream in den Timeshift-Modus"""
        if not self.api or self._current_playing_stream_id is None:
            return

        stream_id = self._current_playing_stream_id
        now = datetime.now().timestamp()
        duration_min = max(1, int((now - start_timestamp) / 60))
        start = datetime.fromtimestamp(start_timestamp)
        url = self.api.creds.catchup_url(stream_id, start, duration_min)

        self._timeshift_active = True
        # Pause-State zuruecksetzen bevor neue URL geladen wird
        if self.player.player and self.player.player.pause:
            self.player.player.pause = False
        self.player.play(url)
        self._update_seek_controls_visibility()
        self._update_go_live_style()

    def _go_live(self):
        """Kehrt vom Timeshift zurueck zum Live-Stream"""
        if not self.api or self._current_playing_stream_id is None:
            return

        stream_id = self._current_playing_stream_id
        url = self.api.creds.stream_url(stream_id)

        self._timeshift_active = False
        self._timeshift_paused_at = 0
        self.player.play(url)
        self.btn_play_pause.setText("\u2759\u2759")
        self._update_seek_controls_visibility()
        self._update_go_live_style()

    def _update_go_live_style(self):
        """Aktualisiert den LIVE-Button Stil (gruen = live, rot = timeshift)"""
        if self._timeshift_active:
            self.btn_go_live.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 68, 68, 30); color: #ff4444; border: 1px solid #ff4444;
                    padding: 2px 12px; border-radius: 6px; font-size: 11px; font-weight: bold;
                }
                QPushButton:hover { background: rgba(255, 68, 68, 60); }
            """)
        else:
            self.btn_go_live.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #00cc66; border: 1px solid #00cc66;
                    padding: 2px 12px; border-radius: 6px; font-size: 11px; font-weight: bold;
                }
                QPushButton:hover { background: rgba(0, 204, 102, 40); }
            """)

    def _skip_seconds(self, seconds: int):
        """Spult vor/zurueck - startet Timeshift bei Live-Catchup-Sendern"""
        if (self._current_stream_type == "live"
                and self._current_epg_has_catchup
                and not self._timeshift_active
                and seconds < 0):
            # Zurueckspulen bei Live → Timeshift starten
            start = datetime.now().timestamp() + seconds
            self._enter_timeshift(start)
            self.btn_play_pause.setText("\u2759\u2759")
        else:
            self.player.seek(seconds)

    def _on_volume_changed(self, value: int):
        """Lautstaerke aendern"""
        self.player.set_volume(value)

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_released(self):
        dur = self.player.duration or 0
        if dur > 0:
            target = self.seek_slider.value() / 1000.0 * dur
            self.player.seek(target, relative=False)
        self._seeking = False

    def _update_seek_controls_visibility(self):
        """Blendet Seek-Controls je nach Stream-Typ ein/aus"""
        is_vod = self._current_stream_type == "vod"
        is_catchup_live = self._current_stream_type == "live" and self._current_epg_has_catchup
        show_seek = is_vod or self._timeshift_active
        # Skip-Buttons auch bei Catchup-Live-Sendern zeigen
        self.btn_skip_back.setVisible(show_seek or is_catchup_live)
        self.btn_skip_forward.setVisible(show_seek or is_catchup_live)
        # Slider/Position nur bei VOD oder aktivem Timeshift
        self.player_pos_label.setVisible(show_seek)
        self.seek_slider.setVisible(show_seek)
        self.player_dur_label.setVisible(show_seek)
        self.player_info_label.setVisible(not show_seek)
        # LIVE-Button nur im Timeshift zeigen
        self.btn_go_live.setVisible(self._timeshift_active)

    def _update_player_controls(self):
        """Aktualisiert die Player-Steuerleiste"""
        self._update_seek_controls_visibility()
        self._save_current_position()
        self._update_recording_status()

        if self._timeshift_active:
            # Timeshift: Position/Dauer anzeigen
            pos = self.player.position or 0
            dur = self.player.duration or 0
            self.player_pos_label.setText(self._format_time(pos))
            self.player_dur_label.setText(self._format_time(dur))
            if dur > 0 and not self._seeking:
                self.seek_slider.setValue(int(pos / dur * 1000))
        elif self._current_stream_type == "live" and self._current_playing_stream_id:
            # EPG-Info fuer Live-Sender anzeigen
            epg = self._epg_cache.get(self._current_playing_stream_id, [])
            now = datetime.now().timestamp()
            for entry in epg:
                if entry.start_timestamp <= now <= entry.stop_timestamp:
                    start = datetime.fromtimestamp(entry.start_timestamp).strftime("%H:%M")
                    end = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
                    self.player_info_label.setText(f"{start}-{end}  {entry.title}")
                    return
            self.player_info_label.setText("LIVE")
        elif self._current_stream_type == "vod":
            # Position/Dauer fuer VOD anzeigen
            pos = self.player.position or 0
            dur = self.player.duration or 0
            self.player_pos_label.setText(self._format_time(pos))
            self.player_dur_label.setText(self._format_time(dur))
            if dur > 0 and not self._seeking:
                self.seek_slider.setValue(int(pos / dur * 1000))

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Formatiert Sekunden als HH:MM:SS oder MM:SS"""
        s = int(seconds)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _toggle_player_maximized(self):
        """Wechselt zwischen echtem OS-Fullscreen und normalem Modus"""
        if self._pip_mode:
            # Doppelklick im PiP: zurueck zu Live mit vollem Player
            self._exit_pip_mode()
            self._switch_mode("live")
            return

        if self._player_maximized:
            # Fullscreen verlassen
            self.sidebar.show()
            self.channel_area.show()
            self.player_header.show()
            self.player_controls.show()
            self._player_maximized = False
            if self._was_maximized_before_fullscreen:
                self.showMaximized()
            else:
                self.showNormal()
        else:
            # Echtes OS-Fullscreen
            self._was_maximized_before_fullscreen = self.isMaximized()
            self.sidebar.hide()
            self.channel_area.hide()
            self.player_header.hide()
            self.player_controls.hide()
            self._player_maximized = True
            self.showFullScreen()

    def _on_player_escape(self):
        """Escape im Player druecken -> Fullscreen oder PiP verlassen"""
        if self._player_maximized:
            self._toggle_player_maximized()
        elif self._pip_mode:
            self._exit_pip_mode()
            self._switch_mode("live")

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

    def _show_settings(self):
        self._update_account_combo()
        self.content_stack.setCurrentWidget(self.settings_page)

    def _add_account(self):
        name = self.input_name.text().strip()
        account_type = self.account_type_combo.currentData()

        if account_type == "m3u":
            m3u_url = self.input_m3u_url.text().strip()
            if not name or not m3u_url:
                QMessageBox.warning(self, "Fehler", "Bitte Name und URL ausfuellen")
                return
            entry = AccountEntry(name=name, type="m3u", url=m3u_url)
        else:
            server = self.input_server.text().strip()
            username = self.input_username.text().strip()
            password = self.input_password.text().strip()
            if not all([name, server, username, password]):
                QMessageBox.warning(self, "Fehler", "Bitte alle Felder ausfuellen")
                return
            entry = AccountEntry(
                name=name, type="xtream",
                server=server, username=username, password=password,
            )

        asyncio.ensure_future(self._test_and_add_account(entry))

    async def _test_and_add_account(self, entry: AccountEntry):
        self._show_loading("Teste Verbindung...")
        self.btn_add_account.setEnabled(False)

        try:
            if entry.type == "m3u":
                api = M3uProvider(entry.name, entry.url)
                await api.load()
            else:
                creds = XtreamCredentials(
                    server=entry.server, username=entry.username,
                    password=entry.password, name=entry.name,
                )
                api = XtreamAPI(creds)
                await api.get_account_info()

            self.account_manager.add_account(entry)
            self.api = api

            # Eingaben leeren
            self.input_name.clear()
            self.input_server.clear()
            self.input_username.clear()
            self.input_password.clear()
            self.input_m3u_url.clear()

            self._update_account_combo()
            self._update_series_button_visibility()
            self.content_stack.setCurrentWidget(self.main_page)
            await self._load_categories()

            self._hide_loading("Account erfolgreich hinzugefuegt")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Verbindung fehlgeschlagen:\n{e}")
            self._hide_loading("Verbindung fehlgeschlagen")
        finally:
            self.btn_add_account.setEnabled(True)

    def _delete_account(self):
        row = self.account_list.currentRow()
        if row >= 0:
            reply = QMessageBox.question(
                self, "Account loeschen",
                "Account wirklich loeschen?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.account_manager.remove_account(row)
                self._update_account_combo()
                if not self.account_manager.get_all():
                    self.api = None

    def _refresh_current(self):
        """Aktualisiert die aktuelle Ansicht"""
        if self.current_mode == "favorites":
            self._load_favorites()
            return
        if self.current_mode == "history":
            self._load_history()
            return
        if self.current_mode == "recordings":
            self._load_recordings()
            return

        # Cache fuer aktuellen Modus leeren
        if self.current_mode == "live":
            self.live_categories = []
        elif self.current_mode == "vod":
            self.vod_categories = []
        else:
            self.series_categories = []

        asyncio.ensure_future(self._load_categories())

    def _load_favorites(self):
        """Laedt und zeigt Favoriten an"""
        QScroller.ungrabGesture(self.channel_list.viewport())
        self.channel_list.setViewMode(QListWidget.ListMode)
        self.channel_list.setIconSize(QSize(0, 0))
        self.channel_list.setGridSize(QSize())
        self.channel_list.setResizeMode(QListWidget.Fixed)
        self.channel_list.setWordWrap(False)
        self.channel_list.setSpacing(0)
        self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self._apply_channel_list_style(grid_mode=False)
        self.epg_panel.setVisible(False)
        self.channel_list.clear()

        account = self.account_manager.get_selected()
        if not account:
            return

        favorites = self.favorites_manager.get_all(account.name)

        for fav in favorites:
            # Stern-Symbol vor dem Namen
            text = f"\u2605 {fav.name}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, fav)
            self.channel_list.addItem(list_item)

        self.status_bar.showMessage(f"{len(favorites)} Favoriten")

    def _load_history(self):
        """Laedt und zeigt den Wiedergabeverlauf an"""
        QScroller.ungrabGesture(self.channel_list.viewport())
        self.channel_list.setViewMode(QListWidget.ListMode)
        self.channel_list.setIconSize(QSize(0, 0))
        self.channel_list.setGridSize(QSize())
        self.channel_list.setResizeMode(QListWidget.Fixed)
        self.channel_list.setWordWrap(False)
        self.channel_list.setSpacing(0)
        self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self._apply_channel_list_style(grid_mode=False)
        self.epg_panel.setVisible(False)
        self.channel_list.clear()

        account = self.account_manager.get_selected()
        if not account:
            return

        entries = self.history_manager.get_all(account.name)

        for entry in entries:
            # Typ-Badge + Titel + Zeitpunkt
            type_badge = {"live": "[Live]", "vod": "[Film]", "series": "[Serie]"}.get(entry.stream_type, "")
            time_str = self._format_relative_time(entry.watched_at)
            text = f"{type_badge} {entry.title}  \u2022  {time_str}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, entry)
            self.channel_list.addItem(list_item)

        self.status_bar.showMessage(f"{len(entries)} Eintraege im Verlauf")

    def _load_recordings(self):
        """Laedt und zeigt gespeicherte Aufnahmen an"""
        QScroller.ungrabGesture(self.channel_list.viewport())
        self.channel_list.setViewMode(QListWidget.ListMode)
        self.channel_list.setIconSize(QSize(0, 0))
        self.channel_list.setGridSize(QSize())
        self.channel_list.setResizeMode(QListWidget.Fixed)
        self.channel_list.setWordWrap(False)
        self.channel_list.setSpacing(0)
        self.channel_list.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self._apply_channel_list_style(grid_mode=False)
        self.epg_panel.setVisible(False)
        self.channel_list.clear()

        rec_dir = self.recorder.output_dir
        if not rec_dir.exists():
            self.status_bar.showMessage("Keine Aufnahmen vorhanden")
            return

        files = sorted(
            [f for f in rec_dir.iterdir() if f.is_file() and f.suffix in (".mkv", ".mp4", ".ts")],
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        for f in files:
            size_mb = f.stat().st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            time_str = self._format_relative_time(mtime.isoformat())
            # Titel aus Dateiname rekonstruieren (underscores -> spaces, timestamp entfernen)
            name = f.stem
            # Letzten _YYYYMMDD_HHMMSS Teil entfernen
            parts = name.rsplit("_", 2)
            if len(parts) >= 3 and len(parts[-1]) == 6 and len(parts[-2]) == 8:
                name = "_".join(parts[:-2])
            display_name = name.replace("_", " ")
            text = f"\u23FA {display_name}  \u2022  {size_mb:.0f} MB  \u2022  {time_str}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, ("recording", f))
            self.channel_list.addItem(list_item)

        self.status_bar.showMessage(f"{len(files)} Aufnahmen")

    @staticmethod
    def _format_relative_time(iso_str: str) -> str:
        """Formatiert ISO-Zeitstempel als relative Zeitangabe"""
        try:
            dt = datetime.fromisoformat(iso_str)
            diff = datetime.now() - dt
            seconds = int(diff.total_seconds())
            if seconds < 60:
                return "gerade eben"
            elif seconds < 3600:
                mins = seconds // 60
                return f"vor {mins} Min."
            elif seconds < 86400:
                hours = seconds // 3600
                return f"vor {hours}h"
            elif seconds < 172800:
                return "gestern"
            else:
                days = seconds // 86400
                return f"vor {days} Tagen"
        except (ValueError, TypeError):
            return ""

    def _save_current_position(self):
        """Speichert die aktuelle Wiedergabeposition im Verlauf"""
        if not self._current_playing_stream_id or not self._current_stream_type:
            return

        account = self.account_manager.get_selected()
        if not account:
            return

        pos = self.player.position or 0
        dur = self.player.duration or 0
        if pos <= 0:
            return

        entry = WatchEntry(
            stream_id=self._current_playing_stream_id,
            stream_type=self._current_stream_type,
            account_name=account.name,
            title=self._current_stream_title,
            icon=self._current_stream_icon,
            position=pos,
            duration=dur,
            container_extension=self._current_container_ext,
        )
        self.history_manager.add_or_update(entry)

    def _check_resume_position(self, stream_id: int, stream_type: str) -> float:
        """Prueft ob eine gespeicherte Position existiert und fragt den Benutzer"""
        account = self.account_manager.get_selected()
        if not account:
            return 0.0

        pos, dur = self.history_manager.get_position(stream_id, stream_type, account.name)

        # Nur fortsetzen wenn > 30s gespielt und < 90% der Dauer
        if pos <= 30 or dur <= 0 or (pos / dur) >= 0.9:
            return 0.0

        pos_str = self._format_time(pos)
        dur_str = self._format_time(dur)

        reply = QMessageBox.question(
            self, "Fortsetzen",
            f"Fortsetzen bei {pos_str} / {dur_str}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            return pos
        return 0.0

    def _toggle_recording(self):
        """Startet oder stoppt die Aufnahme"""
        want_record = self.btn_record.isChecked()

        if not want_record:
            # Stoppen gewuenscht
            if self.recorder.is_recording:
                filepath = self.recorder.stop()
                if filepath and filepath.exists() and filepath.stat().st_size > 0:
                    self.status_bar.showMessage(f"Aufnahme gespeichert: {filepath.name}")
                else:
                    self.status_bar.showMessage("Aufnahme gestoppt")
            self.btn_record.setChecked(False)
            self.btn_record.setToolTip("Aufnahme starten")
        else:
            # Starten gewuenscht
            if not self._current_stream_url:
                self.btn_record.setChecked(False)
                return
            # Falls noch alte Aufnahme laeuft, erst stoppen
            if self.recorder.is_recording:
                self.recorder.stop()
            filepath = self.recorder.start(self._current_stream_url, self._current_stream_title)
            self.btn_record.setToolTip("Aufnahme stoppen")
            self.status_bar.showMessage(f"Aufnahme: {filepath.name}")

    def _update_record_button(self):
        """Aktualisiert das Aussehen des Aufnahme-Buttons"""
        recording = self.recorder.is_recording
        self.btn_record.setChecked(recording)
        self.btn_record.setToolTip("Aufnahme stoppen" if recording else "Aufnahme starten")

    def _update_recording_status(self):
        """Aktualisiert den Aufnahme-Status in der Statusbar"""
        # Button-State synchronisieren falls ffmpeg unerwartet beendet
        if self.btn_record.isChecked() and not self.recorder.is_recording:
            self.btn_record.setChecked(False)
            self.btn_record.setToolTip("Aufnahme starten")
            self.status_bar.showMessage("Aufnahme beendet (ffmpeg gestoppt)")
            return
        if self.recorder.is_recording and self.recorder.start_time:
            elapsed = datetime.now() - self.recorder.start_time
            mins, secs = divmod(int(elapsed.total_seconds()), 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                time_str = f"{hours}:{mins:02d}:{secs:02d}"
            else:
                time_str = f"{mins:02d}:{secs:02d}"
            self.status_bar.showMessage(
                f"\u23FA Aufnahme: {self.recorder.current_title} - seit {time_str}"
            )

    def _on_search_text_changed(self, text: str):
        """Wechselt bei Texteingabe in den Suchmodus, bei leerem Feld zurueck"""
        if text.strip() and self.current_mode != "search":
            self._switch_mode("search")
        elif not text.strip() and self.current_mode == "search":
            self._switch_mode(self._last_mode_before_search or "live")

    def _execute_search(self):
        """Startet die Suche basierend auf dem Suchfeld-Text"""
        query = self.search_input.text().strip()
        if not query or not self.api:
            return
        if self.current_mode != "search":
            self._switch_mode("search")
        asyncio.ensure_future(self._perform_search(query))

    async def _perform_search(self, query: str):
        """Durchsucht alle Streams nach dem Suchbegriff"""
        self._show_loading("Suche laeuft...")
        self.channel_list.clear()
        query_lower = query.lower()

        try:
            # Cache aufbauen falls noch nicht vorhanden
            if not self._search_cache_loaded:
                self._search_cache_live = await self.api.get_live_streams()
                self._search_cache_vod = await self.api.get_vod_streams()
                try:
                    self._search_cache_series = await self.api.get_series()
                except Exception:
                    self._search_cache_series = []
                self._search_cache_loaded = True

            # Live-Streams filtern
            for item in self._search_cache_live:
                if query_lower in item.name.lower():
                    name = f"[Live] {item.name}"
                    if item.tv_archive:
                        name += "  \u25C2\u25C2"
                    list_item = QListWidgetItem(name)
                    list_item.setData(Qt.UserRole, item)
                    self.channel_list.addItem(list_item)

            # VOD filtern
            for item in self._search_cache_vod:
                if query_lower in item.name.lower():
                    list_item = QListWidgetItem(f"[Film] {item.name}")
                    list_item.setData(Qt.UserRole, item)
                    self.channel_list.addItem(list_item)

            # Serien filtern
            for item in self._search_cache_series:
                if query_lower in item.name.lower():
                    list_item = QListWidgetItem(f"[Serie] {item.name}")
                    list_item.setData(Qt.UserRole, item)
                    self.channel_list.addItem(list_item)

            count = self.channel_list.count()
            self._hide_loading(f"{count} Treffer fuer \"{query}\"")

        except Exception as e:
            self._hide_loading(f"Suchfehler: {e}")

    def _show_channel_context_menu(self, position):
        """Zeigt Kontextmenu fuer Kanal an"""
        item = self.channel_list.itemAt(position)
        if not item:
            return

        data = item.data(Qt.UserRole)
        if not data:
            return

        account = self.account_manager.get_selected()
        if not account:
            return

        menu = QMenu(self)

        if self.current_mode == "favorites":
            # Im Favoriten-Modus: Nur Entfernen anzeigen
            action_remove = menu.addAction("Aus Favoriten entfernen")
            action = menu.exec(self.channel_list.mapToGlobal(position))
            if action == action_remove:
                self._remove_from_favorites(data)
        else:
            # In anderen Modi: Hinzufuegen/Entfernen je nach Status
            is_fav = self._is_item_favorite(data, account.name)
            if is_fav:
                action_toggle = menu.addAction("Aus Favoriten entfernen")
            else:
                action_toggle = menu.addAction("Zu Favoriten hinzufuegen")

            action = menu.exec(self.channel_list.mapToGlobal(position))
            if action == action_toggle:
                self._toggle_favorite(data, account.name)

    def _is_item_favorite(self, data, account_name: str) -> bool:
        """Prueft ob ein Item ein Favorit ist"""
        if isinstance(data, LiveStream):
            return self.favorites_manager.is_favorite(data.stream_id, "live", account_name)
        elif isinstance(data, VodStream):
            return self.favorites_manager.is_favorite(data.stream_id, "vod", account_name)
        elif isinstance(data, Series):
            return self.favorites_manager.is_favorite(data.series_id, "series", account_name)
        return False

    def _toggle_favorite(self, data, account_name: str):
        """Wechselt Favoriten-Status eines Items"""
        favorite = self._create_favorite_from_data(data, account_name)
        if favorite:
            is_now_fav = self.favorites_manager.toggle(favorite)
            if is_now_fav:
                self.status_bar.showMessage(f"'{favorite.name}' zu Favoriten hinzugefuegt")
            else:
                self.status_bar.showMessage(f"'{favorite.name}' aus Favoriten entfernt")
            # Liste aktualisieren um Stern anzuzeigen/entfernen
            self._update_current_list_item_display()

    def _remove_from_favorites(self, fav: Favorite):
        """Entfernt einen Favoriten"""
        self.favorites_manager.remove(fav.id, fav.type, fav.account_name)
        self.status_bar.showMessage(f"'{fav.name}' aus Favoriten entfernt")
        self._load_favorites()

    def _create_favorite_from_data(self, data, account_name: str) -> Favorite | None:
        """Erstellt ein Favorite-Objekt aus Stream/Series-Daten"""
        if isinstance(data, LiveStream):
            return Favorite(
                id=data.stream_id,
                name=data.name,
                type="live",
                icon=data.stream_icon,
                account_name=account_name
            )
        elif isinstance(data, VodStream):
            return Favorite(
                id=data.stream_id,
                name=data.name,
                type="vod",
                icon=data.stream_icon,
                container_extension=data.container_extension,
                account_name=account_name
            )
        elif isinstance(data, Series):
            return Favorite(
                id=data.series_id,
                name=data.name,
                type="series",
                icon=data.cover,
                account_name=account_name
            )
        return None

    def _update_current_list_item_display(self):
        """Aktualisiert die Anzeige der aktuellen Liste (Stern-Markierung)"""
        account = self.account_manager.get_selected()
        if not account or self.current_mode == "favorites":
            return

        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            data = item.data(Qt.UserRole)
            if not data:
                continue

            is_fav = self._is_item_favorite(data, account.name)
            name = self._get_item_name(data)

            if is_fav:
                item.setText(f"\u2605 {name}")
            else:
                item.setText(name)

    def _get_item_name(self, data) -> str:
        """Gibt den Anzeigenamen eines Items zurueck"""
        if isinstance(data, LiveStream):
            name = data.name
            if data.tv_archive:
                name += " \u23EA"
            return name
        elif isinstance(data, VodStream):
            return data.name
        elif isinstance(data, Series):
            return data.name
        return ""

    # --- EPG Methods ---

    @Slot(QListWidgetItem)
    def _on_channel_clicked(self, item: QListWidgetItem):
        """Handle single click on channel - load EPG for live streams"""
        data = item.data(Qt.UserRole)
        if not data or not self.api:
            return

        # Only load EPG for live streams
        stream_id = None
        stream_name = ""

        has_catchup = False
        if isinstance(data, LiveStream):
            stream_id = data.stream_id
            stream_name = data.name
            has_catchup = data.tv_archive
        elif isinstance(data, Favorite) and data.type == "live":
            stream_id = data.id
            stream_name = data.name

        if stream_id:
            self._current_epg_stream_id = stream_id
            self._current_epg_has_catchup = has_catchup
            self.epg_channel_name.setText(stream_name)
            asyncio.ensure_future(self._load_epg(stream_id))
        else:
            self._clear_epg_panel()

    async def _load_epg(self, stream_id: int):
        """Load EPG data for a stream"""
        # Check cache first
        if stream_id in self._epg_cache:
            self._update_epg_panel(self._epg_cache[stream_id])
            return

        try:
            epg_data = await self.api.get_short_epg(stream_id, limit=5)
            self._epg_cache[stream_id] = epg_data
            # Only update if still the same stream
            if self._current_epg_stream_id == stream_id:
                self._update_epg_panel(epg_data)
        except Exception:
            self._clear_epg_panel()

    def _update_epg_panel(self, epg_data: list[EpgEntry]):
        """Update EPG panel with data"""
        if not epg_data:
            self.epg_now_label.hide()
            self.epg_now_title.setText("Keine EPG-Daten")
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
            if entry.start_timestamp <= now <= entry.stop_timestamp:
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

            desc = current_entry.description.strip() if current_entry.description else ""
            self.epg_now_desc.setText(desc)
            self.epg_now_desc.setVisible(bool(desc))
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

    def _clear_epg_panel(self):
        """Clear EPG panel"""
        self.epg_channel_name.setText("")
        self.epg_now_label.hide()
        self.epg_now_title.setText("Waehle einen Kanal")
        self.epg_now_desc.hide()
        self.epg_progress.hide()
        self.epg_next_label.hide()
        self.epg_next_title.setText("")
        self.btn_full_epg.setEnabled(False)
        self._current_epg_stream_id = None
        self._current_epg_has_catchup = False

    def _show_full_epg(self):
        """Show full EPG dialog - laedt bei Catchup-Sendern den vollen EPG"""
        if self._current_epg_stream_id is None:
            return

        has_catchup = self._current_epg_has_catchup
        if has_catchup:
            asyncio.ensure_future(self._show_full_epg_async(has_catchup))
        else:
            epg_data = self._epg_cache.get(self._current_epg_stream_id, [])
            self._open_epg_dialog(epg_data, has_catchup)

    async def _show_full_epg_async(self, has_catchup: bool):
        """Laedt vollen EPG asynchron und oeffnet den Dialog"""
        stream_id = self._current_epg_stream_id
        if stream_id is None or not self.api:
            return

        self._show_loading("Lade vollstaendiges Programm...")
        try:
            epg_data = await self.api.get_full_epg(stream_id)
            if not epg_data:
                epg_data = self._epg_cache.get(stream_id, [])
            if self._current_epg_stream_id == stream_id:
                self._open_epg_dialog(epg_data, has_catchup)
        except Exception:
            epg_data = self._epg_cache.get(stream_id, [])
            self._open_epg_dialog(epg_data, has_catchup)
        finally:
            self._hide_loading()

    def _open_epg_dialog(self, epg_data: list[EpgEntry], has_catchup: bool):
        """Oeffnet den EPG-Dialog (non-blocking mit open())"""
        channel_name = self.epg_channel_name.text()
        self._epg_dialog = EpgDialog(channel_name, epg_data, has_catchup=has_catchup, parent=self)
        self._epg_dialog.finished.connect(self._on_epg_dialog_finished)
        self._epg_dialog.open()

    def _on_epg_dialog_finished(self):
        """Wird aufgerufen wenn der EPG-Dialog geschlossen wird"""
        dialog = self._epg_dialog
        self._epg_dialog = None
        if dialog and dialog.selected_catchup_entry is not None:
            self._play_catchup(dialog.selected_catchup_entry)

    def _play_catchup(self, entry: EpgEntry):
        """Spielt eine vergangene Sendung via Catchup/Timeshift ab"""
        if not self.api or self._current_epg_stream_id is None:
            return

        stream_id = self._current_epg_stream_id
        duration_min = max(1, (entry.stop_timestamp - entry.start_timestamp) // 60)
        start = datetime.fromtimestamp(entry.start_timestamp)
        url = self.api.creds.catchup_url(stream_id, start, duration_min)

        channel_name = self.epg_channel_name.text()
        start_str = start.strftime("%H:%M")
        end_str = datetime.fromtimestamp(entry.stop_timestamp).strftime("%H:%M")
        title = f"{channel_name} - {entry.title} ({start_str}-{end_str})"

        self._play_stream(url, title, "vod")

    # --- Audio Track Methods ---

    def _show_audio_menu(self):
        """Zeigt Menu mit verfuegbaren Audio-Spuren"""
        tracks = self.player.get_audio_tracks()
        menu = QMenu(self)

        if not tracks:
            action = menu.addAction("Keine Audio-Spuren verfuegbar")
            action.setEnabled(False)
        else:
            for track in tracks:
                parts = []
                if track["title"]:
                    parts.append(track["title"])
                if track["lang"]:
                    parts.append(track["lang"])
                if track["channels"]:
                    parts.append(track["channels"])

                if parts:
                    label = " - ".join(parts)
                else:
                    label = f"Spur {track['id']}"

                action = menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(track["selected"])
                tid = track["id"]
                action.triggered.connect(lambda checked, t=tid: self.player.set_audio_track(t))

        menu.exec(self.btn_audio.mapToGlobal(self.btn_audio.rect().topLeft()))

    # --- Subtitle Methods ---

    def _show_subtitle_menu(self):
        """Zeigt Menu mit verfuegbaren Untertiteln"""
        tracks = self.player.get_subtitle_tracks()
        menu = QMenu(self)

        # "Aus"-Eintrag
        action_off = menu.addAction("Aus")
        action_off.setCheckable(True)
        action_off.setChecked(not any(t["selected"] for t in tracks))
        action_off.triggered.connect(lambda: self.player.set_subtitle_track(False))

        if tracks:
            menu.addSeparator()
            for track in tracks:
                label = ""
                if track["title"]:
                    label = track["title"]
                    if track["lang"]:
                        label += f" ({track['lang']})"
                elif track["lang"]:
                    label = f"Spur {track['id']} ({track['lang']})"
                else:
                    label = f"Spur {track['id']}"

                action = menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(track["selected"])
                tid = track["id"]
                action.triggered.connect(lambda checked, t=tid: self.player.set_subtitle_track(t))

        # Menu unter dem Button anzeigen
        menu.exec(self.btn_subtitle.mapToGlobal(self.btn_subtitle.rect().topLeft()))

    # --- Stream Info Methods ---

    def _toggle_stream_info(self):
        """Toggle stream info panel visibility"""
        if self.btn_stream_info.isChecked():
            self.stream_info_panel.show()
            self._update_stream_info()
            self.stream_info_timer.start(2000)  # Update every 2 seconds
        else:
            self.stream_info_panel.hide()
            self.stream_info_timer.stop()

    def _update_stream_info(self):
        """Update stream info panel with current stream data"""
        info = self.player.get_stream_info()

        # Video info
        if info["video_width"] and info["video_height"]:
            self.info_resolution.setText(f"Aufloesung: {info['video_width']}x{info['video_height']}")
        else:
            self.info_resolution.setText("Aufloesung: -")

        if info["fps"]:
            self.info_fps.setText(f"FPS: {info['fps']:.2f}")
        else:
            self.info_fps.setText("FPS: -")

        if info["video_codec"]:
            self.info_video_codec.setText(f"Codec: {info['video_codec']}")
        else:
            self.info_video_codec.setText("Codec: -")

        # Audio info
        if info["audio_codec"]:
            self.info_audio_codec.setText(f"Codec: {info['audio_codec']}")
        else:
            self.info_audio_codec.setText("Codec: -")

        num_tracks = len(info["audio_tracks"])
        if num_tracks > 0:
            self.info_audio_tracks.setText(f"Tonspuren: {num_tracks}")
        else:
            self.info_audio_tracks.setText("Tonspuren: -")

    def closeEvent(self, event):
        self._save_current_position()
        if self.recorder.is_recording:
            self.recorder.stop()
        self.stream_info_timer.stop()
        self.controls_timer.stop()
        self.player.cleanup()
        super().closeEvent(event)
