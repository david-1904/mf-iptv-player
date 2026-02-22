"""
UI-Erstellung: Alle _create_* Methoden und Layout-Setup
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem, QComboBox,
    QPushButton, QLineEdit, QLabel, QSlider,
    QFrame, QToolBar, QStatusBar, QGroupBox, QScrollArea, QSplitter,
    QProgressBar, QAbstractItemView, QScroller, QMenu
)
from PySide6.QtCore import Qt, QSize, Slot, QTimer
from PySide6.QtGui import QAction, QPixmap

from flow_layout import FlowLayout


class UiBuilderMixin:

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
        self.btn_settings = QPushButton("\u2699  Einstellungen")
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

        # Titelzeile mit Schliessen-Button
        title_row = QHBoxLayout()
        title = QLabel("Account hinzufuegen")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 16px;")
        title_row.addWidget(title)
        title_row.addStretch()
        self.btn_close_settings = QPushButton("Schliessen")
        self.btn_close_settings.setStyleSheet("""
            QPushButton {
                padding: 6px 14px; border-radius: 6px;
                background: #2a2a3a; border: 1px solid #3a3a4a;
                color: #ccc; font-size: 12px;
            }
            QPushButton:hover { background: #e04050; color: white; border-color: #e04050; }
        """)
        self.btn_close_settings.clicked.connect(lambda: self.content_stack.setCurrentWidget(self.main_page))
        title_row.addWidget(self.btn_close_settings)
        layout.addLayout(title_row)

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
                    font-size: 13px;
                    padding: 0;
                }
                QListWidget::item {
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
        self.category_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.category_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.category_list.customContextMenuRequested.connect(self._on_category_context_menu)
        self.category_list.itemClicked.connect(self._on_category_list_clicked)
        self.category_list.hide()
        cl_layout.addWidget(self.category_list, stretch=1)

        # Button: Ausgeblendete Kategorien verwalten
        self.manage_hidden_btn = QPushButton("Ausgeblendete Kategorien verwalten")
        self.manage_hidden_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                margin: 0;
                background: #1a1a2a;
                border: none;
                border-bottom: 1px solid #1a1a2a;
                border-radius: 0;
                color: #888;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover { background: #1c1c2c; color: #ccc; }
        """)
        self.manage_hidden_btn.clicked.connect(self._show_hidden_categories_dialog)
        self.manage_hidden_btn.hide()
        cl_layout.addWidget(self.manage_hidden_btn)

        # Sortierung (nur bei VOD/Serien sichtbar)
        self.sort_widget = QWidget()
        self.sort_widget.setStyleSheet("background: #161622; border-bottom: 1px solid #1a1a2a;")
        sort_layout = QHBoxLayout(self.sort_widget)
        sort_layout.setContentsMargins(12, 4, 10, 4)
        sort_layout.setSpacing(8)

        sort_label = QLabel("Sortierung:")
        sort_label.setStyleSheet("color: #666; font-size: 12px; border: none;")
        sort_layout.addWidget(sort_label)

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
        self.channel_list.viewport().installEventFilter(self)

        # EPG Panel
        self.epg_panel = self._create_epg_panel()
        self.epg_panel.setMinimumHeight(80)

        # Splitter zwischen Kanalliste und EPG
        self._epg_splitter = QSplitter(Qt.Vertical)
        self._epg_splitter.setChildrenCollapsible(False)
        self._epg_splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background: #1a1a2a;
                height: 4px;
            }
            QSplitter::handle:vertical:hover {
                background: #0078d4;
            }
        """)
        self._epg_splitter.addWidget(self.channel_list)
        self._epg_splitter.addWidget(self.epg_panel)
        self._epg_splitter.setSizes([600, 260])
        cl_layout.addWidget(self._epg_splitter, stretch=1)

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
                background: #0d0d14;
                width: 4px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical {
                background: #333;
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
        layout.setSpacing(6)
        scroll.setWidget(content)

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
        self._current_series = None

        return page

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

        self.player_container = player_container
        self.fullscreen_controls = self._create_fullscreen_controls_overlay(player_container)
        self._fs_controls_timer = QTimer()
        self._fs_controls_timer.setSingleShot(True)
        self._fs_controls_timer.timeout.connect(self._hide_fullscreen_controls)

        self._buffering_watchdog = QTimer()
        self._buffering_watchdog.setSingleShot(True)
        self._buffering_watchdog.timeout.connect(self._on_buffering_timeout)

        self._reconnect_timer = QTimer()
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._do_reconnect)

        self.player.stream_ended.connect(self._on_stream_ended)

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

    def _create_fullscreen_controls_overlay(self, parent: QWidget) -> QWidget:
        """Vollbild-Kontrollleiste als Auto-Hide-Overlay"""
        overlay = QFrame(parent)
        overlay.setObjectName("fsControls")
        overlay.setStyleSheet("""
            #fsControls {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
                    stop:0 rgba(0, 0, 0, 220),
                    stop:0.6 rgba(0, 0, 0, 150),
                    stop:1 rgba(0, 0, 0, 0));
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
            QLabel {
                color: #ddd;
                font-size: 12px;
                background: transparent;
            }
        """)

        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(20, 0, 20, 16)
        layout.setSpacing(8)
        layout.addStretch()

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

        self.fs_seek_slider = QSlider(Qt.Horizontal)
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
                background: #0078d4;
                border-radius: 2px;
            }
        """)
        self.fs_seek_slider.sliderPressed.connect(lambda: setattr(self, '_fs_seeking', True))
        self.fs_seek_slider.sliderReleased.connect(self._on_fs_seek_released)
        seek_layout.addWidget(self.fs_seek_slider, stretch=1)

        self.fs_dur_label = QLabel("00:00")
        self.fs_dur_label.setFixedWidth(55)
        seek_layout.addWidget(self.fs_dur_label)

        layout.addWidget(self.fs_seek_row)

        # Zeile 2: Steuer-Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self.fs_btn_play_pause = QPushButton("\u25B6\uFE0E")
        self.fs_btn_play_pause.setFixedSize(44, 44)
        self.fs_btn_play_pause.clicked.connect(self._toggle_play_pause)
        btn_row.addWidget(self.fs_btn_play_pause)

        self.fs_btn_skip_back = QPushButton("\u25C0\u25C0")
        self.fs_btn_skip_back.setFixedSize(44, 44)
        self.fs_btn_skip_back.clicked.connect(lambda: self._skip_seconds(-10))
        btn_row.addWidget(self.fs_btn_skip_back)

        self.fs_btn_skip_forward = QPushButton("\u25B6\u25B6")
        self.fs_btn_skip_forward.setFixedSize(44, 44)
        self.fs_btn_skip_forward.clicked.connect(lambda: self._skip_seconds(10))
        btn_row.addWidget(self.fs_btn_skip_forward)

        vol_icon = QLabel("\u266B")
        vol_icon.setStyleSheet("font-size: 14px; color: #888; background: transparent;")
        btn_row.addWidget(vol_icon)

        self.fs_volume_slider = QSlider(Qt.Horizontal)
        self.fs_volume_slider.setRange(0, 100)
        self.fs_volume_slider.setFixedWidth(100)
        self.fs_volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 40);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white;
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
        self.fs_volume_slider.blockSignals(True)
        self.fs_volume_slider.setValue(100)
        self.fs_volume_slider.blockSignals(False)
        self.fs_volume_slider.valueChanged.connect(self._on_volume_changed)
        btn_row.addWidget(self.fs_volume_slider)

        btn_row.addStretch()

        self.fs_info_label = QLabel("")
        self.fs_info_label.setStyleSheet("color: #ddd; font-size: 13px; background: transparent;")
        self.fs_info_label.setAlignment(Qt.AlignCenter)
        btn_row.addWidget(self.fs_info_label)

        btn_row.addStretch()

        fs_exit_btn = QPushButton("\u26F6")
        fs_exit_btn.setFixedSize(44, 44)
        fs_exit_btn.setToolTip("Vollbild verlassen")
        fs_exit_btn.clicked.connect(self._toggle_player_maximized)
        btn_row.addWidget(fs_exit_btn)

        layout.addLayout(btn_row)

        self._fs_seeking = False
        overlay.hide()
        overlay.installEventFilter(self)

        return overlay

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
