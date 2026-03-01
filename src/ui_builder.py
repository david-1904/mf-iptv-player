"""
UI-Erstellung: Alle _create_* Methoden und Layout-Setup
"""
import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QListWidget, QListWidgetItem, QComboBox,
    QPushButton, QLineEdit, QLabel, QSlider,
    QFrame, QStatusBar, QGroupBox, QScrollArea, QSplitter,
    QProgressBar, QAbstractItemView, QScroller, QMenu
)
from PySide6.QtCore import Qt, QSize, Slot, QTimer
from PySide6.QtGui import QPixmap, QFont

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
                padding: 10px 16px;
                margin: 2px 8px;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: #aaa;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #1a1a2a;
                color: #ddd;
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

        # Trennlinie
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("background-color: #1a1a2a; margin: 4px 10px;")
        layout.addWidget(line2)

        # Aktualisieren-Button
        self.btn_refresh = QPushButton("\u21BB  Aktualisieren")
        self.btn_refresh.clicked.connect(self._refresh_current)
        layout.addWidget(self.btn_refresh)

        # Spacer
        layout.addStretch()

        # Update-Button (initially hidden, shown by _check_for_updates)
        self.btn_update = QPushButton("\u2B07  Update verfügbar")
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

        # Einstellungen-Button
        self.btn_settings = QPushButton("\u2699  Einstellungen")
        self.btn_settings.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px 16px;
                margin: 2px 8px;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: #888;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #1a1a2a;
                color: #bbb;
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
        self.settings_title = QLabel("Account hinzuf\u00fcgen")
        self.settings_title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 16px;")
        title_row.addWidget(self.settings_title)
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

        self.btn_cancel_edit = QPushButton("Abbrechen")
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)
        self.btn_cancel_edit.hide()
        btn_layout.addWidget(self.btn_cancel_edit)

        layout.addLayout(btn_layout)

        # Account-Liste
        layout.addSpacing(24)
        list_title = QLabel("Gespeicherte Accounts")
        list_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(list_title)

        self.account_list = QListWidget()
        self.account_list.setMaximumHeight(200)
        self.account_list.itemClicked.connect(self._on_account_list_clicked)
        layout.addWidget(self.account_list)

        acc_hint = QLabel("Auf einen Account klicken, um ihn zu bearbeiten")
        acc_hint.setStyleSheet("color: #555; font-size: 11px; margin: 2px 0;")
        layout.addWidget(acc_hint)

        self.btn_delete_account = QPushButton("Ausgew\u00e4hlten Account l\u00f6schen")
        self.btn_delete_account.clicked.connect(self._delete_account)
        layout.addWidget(self.btn_delete_account)

        # Line-Status
        layout.addSpacing(24)
        line_status_row = QHBoxLayout()
        line_status_title = QLabel("Line-Status")
        line_status_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        line_status_row.addWidget(line_status_title)
        line_status_row.addStretch()
        self.btn_refresh_line_info = QPushButton("\u21bb")
        self.btn_refresh_line_info.setToolTip("Aktualisieren")
        self.btn_refresh_line_info.setStyleSheet("""
            QPushButton {
                padding: 2px 8px; border-radius: 4px;
                background: #2a2a3a; border: 1px solid #3a3a4a; color: #aaa;
            }
            QPushButton:hover { background: #3a3a4a; color: white; }
        """)
        self.btn_refresh_line_info.clicked.connect(lambda: asyncio.ensure_future(self._refresh_line_info()))
        line_status_row.addWidget(self.btn_refresh_line_info)
        layout.addLayout(line_status_row)

        self.lbl_line_info = QLabel("Kein aktiver Account")
        self.lbl_line_info.setStyleSheet("""
            QLabel {
                background: #1a1a2a;
                border: 1px solid #2a2a3a;
                border-radius: 8px;
                padding: 12px 16px;
                color: #aaa;
                font-size: 13px;
            }
        """)
        self.lbl_line_info.setWordWrap(True)
        layout.addWidget(self.lbl_line_info)

        # Wiedergabe-Einstellungen
        layout.addSpacing(24)
        playback_title = QLabel("Wiedergabe")
        playback_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(playback_title)

        hwdec_row = QHBoxLayout()
        hwdec_label = QLabel("Hardware-Dekodierung:")
        hwdec_label.setStyleSheet("font-size: 13px; color: #ccc;")
        hwdec_row.addWidget(hwdec_label)
        self.hwdec_combo = QComboBox()
        self.hwdec_combo.addItem("Automatisch (empfohlen)", "auto")
        self.hwdec_combo.addItem("Hardware + Kopie (auto-copy)", "auto-copy")
        self.hwdec_combo.addItem("Software (kompatibel, mehr CPU)", "no")
        saved_hwdec = self.app_settings.get("hwdec", "auto")
        idx = self.hwdec_combo.findData(saved_hwdec)
        self.hwdec_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.hwdec_combo.currentIndexChanged.connect(self._on_hwdec_changed)
        hwdec_row.addWidget(self.hwdec_combo, stretch=1)
        layout.addLayout(hwdec_row)

        self.lbl_hwdec_hint = QLabel("↻ App neu starten damit die Änderung wirkt")
        self.lbl_hwdec_hint.setStyleSheet("color: #e8691a; font-size: 11px; margin: 2px 0 0 0;")
        self.lbl_hwdec_hint.hide()
        layout.addWidget(self.lbl_hwdec_hint)

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
                    font-size: 15px;
                }
                QListWidget::item {
                    padding: 9px 12px;
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
        self.category_row.setStyleSheet("background: #161622; border-bottom: 1px solid #1a1a2a;")
        _cat_row_layout = QHBoxLayout(self.category_row)
        _cat_row_layout.setContentsMargins(12, 0, 0, 0)
        _cat_row_layout.setSpacing(8)

        _cat_label = QLabel("Kategorie:")
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
        self.fav_filter_row.setStyleSheet("background: #161622; border-bottom: 1px solid #1a1a2a;")
        _fav_layout = QHBoxLayout(self.fav_filter_row)
        _fav_layout.setContentsMargins(8, 4, 8, 4)
        _fav_layout.setSpacing(6)

        self._fav_filter_buttons = {}
        _fav_btn_style = """
            QPushButton {{
                padding: 4px 12px; border-radius: 12px; font-size: 12px;
                background: transparent; border: 1px solid #2a2a3a; color: #888;
            }}
            QPushButton:hover {{ border-color: #0078d4; color: #ccc; }}
            QPushButton[active="true"] {{ background: #0078d4; border-color: #0078d4; color: white; font-weight: bold; }}
        """
        for label, ftype in [("Alle", None), ("📺 Live", "live"), ("🎬 Filme", "vod"), ("📖 Serien", "series")]:
            btn = QPushButton(label)
            btn.setStyleSheet(_fav_btn_style)
            btn.setProperty("active", "false")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=ftype: self._set_fav_filter(t))
            _fav_layout.addWidget(btn)
            self._fav_filter_buttons[ftype] = btn

        self._fav_filter_buttons[None].setProperty("active", "true")
        _fav_layout.addStretch()
        self.fav_filter_row.hide()
        cl_layout.addWidget(self.fav_filter_row)

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
        self.category_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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
        self.channel_list.itemClicked.connect(self._on_channel_selected)
        self.channel_list.itemDoubleClicked.connect(self._on_channel_selected)
        self.channel_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self._show_channel_context_menu)
        self.channel_list.viewport().installEventFilter(self)

        # EPG Panel
        self.epg_panel = self._create_epg_panel()
        self.epg_panel.setMinimumHeight(200)

        # Splitter zwischen Kanalliste und EPG
        self._epg_splitter = QSplitter(Qt.Vertical)
        self._epg_splitter.setChildrenCollapsible(False)
        self._epg_splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background: #1a1a2a;
                height: 4px;
            }
            QSplitter::handle:vertical:hover {
                background: #e8691a;
            }
        """)
        self._epg_splitter.addWidget(self.channel_list)
        self._epg_splitter.addWidget(self.epg_panel)
        self._epg_splitter.setSizes([99999, 0])
        self.epg_panel.hide()
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

        return self.channel_stack

    def _create_channel_detail_panel(self) -> QWidget:
        """Modernes Kanal-Detailpanel: Hero-Bild, Logo, Name, EPG mit Fortschrittsbalken."""
        panel = QWidget()
        panel.setObjectName("channelDetailPanel")
        panel.setStyleSheet("""
            #channelDetailPanel {
                background-color: #0a0a12;
                border-left: 1px solid #1a1a2a;
            }
        """)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Zurück-Leiste
        back_bar = QWidget()
        back_bar.setFixedHeight(36)
        back_bar.setStyleSheet("background: #0d0d1a; border-bottom: 1px solid #1a1a2a;")
        back_bar_layout = QHBoxLayout(back_bar)
        back_bar_layout.setContentsMargins(8, 0, 8, 0)
        self.detail_back_btn = QPushButton("‹  Senderliste")
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
        sep.setStyleSheet("background-color: #1a1a2a; margin: 0;")
        lay.addWidget(sep)

        # ── DAVOR-Bereich ─────────────────────────────────────────
        self.detail_prev_widget = QWidget()
        self.detail_prev_widget.setStyleSheet("background: transparent;")
        prev_lay = QVBoxLayout(self.detail_prev_widget)
        prev_lay.setContentsMargins(0, 0, 0, 0)
        prev_lay.setSpacing(4)

        davor_lbl = QLabel("DAVOR")
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

        jetzt_lbl = QLabel("JETZT")
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
        self.detail_now_rec_btn = QPushButton("\U0001F4F9")
        self.detail_now_rec_btn.setToolTip("Aufnahme planen")
        self.detail_now_rec_btn.setFixedHeight(30)
        self.detail_now_rec_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #888;
                border: 1px solid #444; border-radius: 4px;
                font-size: 17px; padding: 0 6px;
            }
            QPushButton:hover { background: #c0392b; color: white; border-color: #c0392b; }
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

        danach_lbl = QLabel("DANACH")
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
        self.detail_epg_action_btn = QPushButton("Vollst\u00e4ndiges EPG  \u25B8")
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
        _epg_logo_frame.setStyleSheet("QFrame { background-color: #1e1e2e; border-radius: 10px; }")
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

        self.epg_now_label = QLabel("JETZT")
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
            QProgressBar { background: #1a1a2a; border: none; border-radius: 1px; }
            QProgressBar::chunk { background: #e8691a; border-radius: 1px; }
        """)
        right_col.addWidget(self.epg_progress)

        # Beschreibung (versteckt)
        self.epg_now_desc = QLabel("")
        self.epg_now_desc.setStyleSheet("font-size: 13px; color: #888;")
        self.epg_now_desc.setWordWrap(True)
        self.epg_now_desc.hide()
        right_col.addWidget(self.epg_now_desc)

        self.epg_next_label = QLabel("DANACH")
        self.epg_next_label.setStyleSheet("font-size: 9px; font-weight: bold; color: #555; letter-spacing: 1px;")
        right_col.addWidget(self.epg_next_label)

        self.epg_next_title = QLabel("")
        self.epg_next_title.setStyleSheet("font-size: 13px; color: #888;")
        self.epg_next_title.setWordWrap(True)
        self.epg_next_title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        right_col.addWidget(self.epg_next_title)

        right_col.addStretch()

        # EPG-Button ganz unten rechts
        self.btn_full_epg = QPushButton("EPG \u25B8")
        self.btn_full_epg.setToolTip("Vollständiges Sendeprogramm anzeigen")
        self.btn_full_epg.setFixedHeight(24)
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
        page.setStyleSheet("background-color: #0a0a12;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: nur Zurueck-Button
        header = QFrame()
        header.setStyleSheet("background-color: #0d0d14; border-bottom: 1px solid #1a1a2a;")
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)

        self.btn_series_back = QPushButton("\u2190 Zur\u00fcck")
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

        # Hero-Bereich: Cover links (gross), Info rechts daneben
        hero = QFrame()
        hero.setStyleSheet("background-color: #10101a; border-bottom: 1px solid #1a1a2a;")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 16, 16, 16)
        hero_layout.setSpacing(14)

        # Cover links, gross
        self.series_cover_label = QLabel()
        self.series_cover_label.setFixedSize(170, 255)
        self.series_cover_label.setStyleSheet("""
            background-color: #1a1a2e;
            border-radius: 10px;
            border: 1px solid #2a2a3e;
            color: #2a2a4a;
            font-size: 44px;
        """)
        self.series_cover_label.setAlignment(Qt.AlignCenter)
        self.series_cover_label.setText("\u25B6")
        hero_layout.addWidget(self.series_cover_label, alignment=Qt.AlignTop)

        # Info rechts
        info_col = QVBoxLayout()
        info_col.setSpacing(8)
        info_col.setContentsMargins(0, 0, 0, 0)

        self.series_title_label = QLabel("")
        self.series_title_label.setWordWrap(True)
        self.series_title_label.setStyleSheet("font-size: 17px; font-weight: bold; color: white;")
        info_col.addWidget(self.series_title_label)

        self.series_subtitle_label = QLabel("")
        self.series_subtitle_label.setStyleSheet("font-size: 11px; color: #555;")
        self.series_subtitle_label.setWordWrap(True)
        info_col.addWidget(self.series_subtitle_label)

        self.series_rating_label = QLabel("")
        self.series_rating_label.setStyleSheet("""
            font-size: 11px; font-weight: bold; color: #f0c040;
            background-color: #1e1c08; padding: 2px 8px;
            border-radius: 5px; border: 1px solid #3a3810;
        """)
        self.series_rating_label.hide()
        info_col.addWidget(self.series_rating_label, alignment=Qt.AlignLeft)

        self.series_plot_label = QLabel("")
        self.series_plot_label.setWordWrap(True)
        self.series_plot_label.setStyleSheet("font-size: 13px; color: #999;")
        self.series_plot_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        info_col.addWidget(self.series_plot_label)
        info_col.addStretch()

        hero_layout.addLayout(info_col, stretch=1)
        hero.setMaximumHeight(290)
        layout.addWidget(hero)

        # Season-Bar: Dropdown links
        season_bar = QFrame()
        season_bar.setFixedHeight(44)
        season_bar.setStyleSheet("background-color: #0d0d14; border-bottom: 1px solid #1a1a2a;")
        season_layout = QHBoxLayout(season_bar)
        season_layout.setContentsMargins(16, 0, 16, 0)
        season_layout.setSpacing(10)

        self.season_combo = QComboBox()
        self.season_combo.setStyleSheet("""
            QComboBox {
                padding: 5px 14px; background: #1a1a2a;
                border: 1px solid #2a2a3a; border-radius: 14px;
                color: #ccc; font-size: 13px; min-width: 120px;
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
        season_layout.addStretch()
        layout.addWidget(season_bar)

        # Episoden-Liste
        self.episode_list = QListWidget()
        self.episode_list.setStyleSheet("""
            QListWidget {
                background-color: #0a0a12; border: none; outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #111120;
                padding: 0px;
            }
            QListWidget::item:hover { background-color: #111120; }
            QListWidget::item:selected { background-color: #0a1e33; }
            QScrollBar:vertical { background: #0a0a12; width: 6px; }
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

        # Ladebalken (indeterminate, erscheint während Infos/Cover laden)
        self.vod_loading_bar = QProgressBar()
        self.vod_loading_bar.setRange(0, 0)
        self.vod_loading_bar.setFixedHeight(3)
        self.vod_loading_bar.setTextVisible(False)
        self.vod_loading_bar.setStyleSheet("""
            QProgressBar { background: #1a1a2a; border: none; }
            QProgressBar::chunk { background: #0078d4; }
        """)
        self.vod_loading_bar.hide()
        layout.addWidget(self.vod_loading_bar)

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

        self.player = MpvPlayerWidget(hwdec=self.app_settings.get("hwdec", "auto"))
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

        player_container.setMouseTracking(True)
        self.player.setMouseTracking(True)
        player_container.installEventFilter(self)

        player_layout.addWidget(player_container, stretch=1)

        self.stream_info_panel = self._create_stream_info_panel()
        self.stream_info_panel.setFixedWidth(200)
        self.stream_info_panel.hide()
        player_layout.addWidget(self.stream_info_panel)

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

        self.controls_timer = QTimer()
        self.controls_timer.timeout.connect(self._update_player_controls)

        self._buffering_dots = 0
        self._buffering_timer = QTimer()
        self._buffering_timer.timeout.connect(self._animate_buffering)

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

        self.pip_expand_btn = QPushButton("\u2197")   # ↗ Pfeil
        self.pip_expand_btn.setFont(_pip_font)
        self.pip_expand_btn.setFixedSize(28, 26)
        self.pip_expand_btn.setToolTip("Vergrößern")
        self.pip_expand_btn.setStyleSheet(
            _pip_btn_base +
            "QPushButton:hover { background: rgba(50,180,50,180); border-radius: 4px; }"
        )
        self.pip_expand_btn.clicked.connect(self._on_pip_expand)
        _pip_layout.addWidget(self.pip_expand_btn)

        self.pip_close_btn = QPushButton("\u00d7")    # × Multiplikationszeichen
        self.pip_close_btn.setFont(_pip_font)
        self.pip_close_btn.setFixedSize(28, 26)
        self.pip_close_btn.setToolTip("Wiedergabe beenden")
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
        bar.setFixedHeight(34)
        bar.setStyleSheet("background: #0a0a12; border-top: 1px solid #1a1a2a;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        self.live_epg_von_anfang_btn = QPushButton("\u21BA Anfang")
        self.live_epg_von_anfang_btn.setFixedHeight(24)
        self.live_epg_von_anfang_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #e8691a;
                border: 1px solid #e8691a; padding: 1px 12px;
                border-radius: 5px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(245, 166, 35, 30); }
        """)
        self.live_epg_von_anfang_btn.clicked.connect(self._live_play_von_anfang)
        self.live_epg_von_anfang_btn.hide()
        layout.addWidget(self.live_epg_von_anfang_btn)

        self.live_epg_catchup_btn = QPushButton("\u25C4\u25C4 Catchup")
        self.live_epg_catchup_btn.setFixedHeight(24)
        self.live_epg_catchup_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #e8691a;
                border: 1px solid #e8691a; padding: 1px 12px;
                border-radius: 5px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(245, 166, 35, 30); }
        """)
        self.live_epg_catchup_btn.clicked.connect(self._show_full_epg)
        self.live_epg_catchup_btn.hide()
        layout.addWidget(self.live_epg_catchup_btn)

        self.live_epg_epg_btn = QPushButton("EPG \u25B8")
        self.live_epg_epg_btn.setFixedHeight(24)
        self.live_epg_epg_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #e8691a;
                border: 1px solid #e8691a; padding: 1px 12px;
                border-radius: 5px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(245, 166, 35, 30); }
        """)
        self.live_epg_epg_btn.clicked.connect(self._toggle_channel_detail)
        layout.addWidget(self.live_epg_epg_btn)

        self.live_epg_seek_slider = QSlider(Qt.Horizontal)
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
            QProgressBar { background: #1e1e2e; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #e8691a; border-radius: 2px; }
        """)
        self.live_epg_progress.hide()
        layout.addWidget(self.live_epg_progress, stretch=1)

        bar.hide()
        return bar

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
            QPushButton:checked { color: #e8691a; }
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

        # Zap-Buttons (Kanal zurück/vor)
        self.btn_zap_prev = QPushButton("\u2190")
        self.btn_zap_prev.setFixedSize(36, 36)
        self.btn_zap_prev.setToolTip("Vorheriger Kanal")
        self.btn_zap_prev.clicked.connect(self._zap_prev)
        self.btn_zap_prev.hide()
        layout.addWidget(self.btn_zap_prev)

        self.btn_zap_next = QPushButton("\u2192")
        self.btn_zap_next.setFixedSize(36, 36)
        self.btn_zap_next.setToolTip("Nächster Kanal")
        self.btn_zap_next.clicked.connect(self._zap_next)
        self.btn_zap_next.hide()
        layout.addWidget(self.btn_zap_next)

        # Skip-Buttons
        self.btn_skip_back = QPushButton("\u25C0\u25C0")
        self.btn_skip_back.setFixedSize(36, 36)
        self.btn_skip_back.setToolTip("-30 Sekunden")
        self.btn_skip_back.clicked.connect(lambda: self._skip_seconds(-30))
        layout.addWidget(self.btn_skip_back)

        self.btn_skip_forward = QPushButton("\u25B6\u25B6")
        self.btn_skip_forward.setFixedSize(36, 36)
        self.btn_skip_forward.setToolTip("+30 Sekunden")
        self.btn_skip_forward.clicked.connect(lambda: self._skip_seconds(30))
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
                background: #e8691a;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #e8691a;
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
                background: #e8691a;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #e8691a;
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

        # Stretch fuer Mitte (EPG-Info wurde entfernt, Hover-Overlay genuegt)
        self.player_info_label = QLabel("")  # Bleibt fuer Code-Kompatibilitaet
        layout.addStretch(1)

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
            QPushButton:checked { border-color: #e8691a; color: #e8691a; }
        """)
        self.btn_stream_info.clicked.connect(self._toggle_stream_info)
        layout.addWidget(self.btn_stream_info)

        # Vollbild-Button
        sep4 = QFrame()
        sep4.setFrameShape(QFrame.VLine)
        sep4.setStyleSheet("color: #1e1e2e;")
        layout.addWidget(sep4)

        self.btn_fullscreen = QPushButton("\u26F6")
        self.btn_fullscreen.setFixedSize(36, 36)
        self.btn_fullscreen.setToolTip("Vollbild (F / Doppelklick)")
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

        self.fs_epg_von_anfang_btn = QPushButton("\u21BA Anfang")
        self.fs_epg_von_anfang_btn.setFixedHeight(30)
        self.fs_epg_von_anfang_btn.setToolTip("Sendung von Anfang abspielen (Catchup)")
        self.fs_epg_von_anfang_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #e8691a;
                border: 1px solid #e8691a; padding: 2px 14px;
                border-radius: 6px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(245, 166, 35, 30); }
        """)
        self.fs_epg_von_anfang_btn.clicked.connect(self._fs_play_von_anfang)
        self.fs_epg_von_anfang_btn.hide()
        prog_row_layout.addWidget(self.fs_epg_von_anfang_btn)

        self.fs_epg_seek_slider = QSlider(Qt.Horizontal)
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
        btn_row.setSpacing(6)

        self.fs_btn_play_pause = QPushButton("\u25B6\uFE0E")
        self.fs_btn_play_pause.setFixedSize(44, 44)
        self.fs_btn_play_pause.clicked.connect(self._toggle_play_pause)
        btn_row.addWidget(self.fs_btn_play_pause)

        self.fs_btn_skip_back = QPushButton("\u25C0\u25C0")
        self.fs_btn_skip_back.setFixedSize(44, 44)
        self.fs_btn_skip_back.clicked.connect(lambda: self._skip_seconds(-30))
        self.fs_btn_skip_back.setToolTip("30s zurück")
        self.fs_btn_skip_back.hide()
        btn_row.addWidget(self.fs_btn_skip_back)

        self.fs_btn_skip_forward = QPushButton("\u25B6\u25B6")
        self.fs_btn_skip_forward.setFixedSize(44, 44)
        self.fs_btn_skip_forward.clicked.connect(lambda: self._skip_seconds(30))
        self.fs_btn_skip_forward.setToolTip("30s vor")
        self.fs_btn_skip_forward.hide()
        btn_row.addWidget(self.fs_btn_skip_forward)

        self.fs_btn_go_live = QPushButton("\u25CF  LIVE")
        self.fs_btn_go_live.setFixedHeight(34)
        self.fs_btn_go_live.setStyleSheet("""
            QPushButton {
                background: rgba(255, 68, 68, 30); color: #ff4444;
                border: 1px solid #ff4444; padding: 4px 14px;
                border-radius: 6px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(255, 68, 68, 60); }
        """)
        self.fs_btn_go_live.clicked.connect(self._go_live)
        self.fs_btn_go_live.hide()
        btn_row.addWidget(self.fs_btn_go_live)

        self.fs_btn_stop = QPushButton("\u25A0")
        self.fs_btn_stop.setFixedSize(44, 44)
        self.fs_btn_stop.setToolTip("Stop")
        self.fs_btn_stop.clicked.connect(self._stop_playback)
        btn_row.addWidget(self.fs_btn_stop)

        self.fs_btn_record = QPushButton("\u25CF")
        self.fs_btn_record.setObjectName("fsRecordBtn")
        self.fs_btn_record.setCheckable(True)
        self.fs_btn_record.setFixedSize(44, 44)
        self.fs_btn_record.setToolTip("Aufnahme starten")
        self.fs_btn_record.clicked.connect(self._toggle_recording)
        btn_row.addWidget(self.fs_btn_record)

        btn_row.addStretch()

        # Audio / Sub / Info
        self.fs_btn_audio = QPushButton("Audio")
        self.fs_btn_audio.setFixedHeight(32)
        self.fs_btn_audio.setStyleSheet("""
            QPushButton {
                background: transparent; color: #aaa;
                border: 1px solid #3a3a4a; padding: 2px 12px;
                border-radius: 6px; font-size: 12px;
            }
            QPushButton:hover { border-color: #888; color: white; }
        """)
        self.fs_btn_audio.clicked.connect(self._show_audio_menu)
        btn_row.addWidget(self.fs_btn_audio)

        self.fs_btn_subtitle = QPushButton("Sub")
        self.fs_btn_subtitle.setFixedHeight(32)
        self.fs_btn_subtitle.setStyleSheet("""
            QPushButton {
                background: transparent; color: #aaa;
                border: 1px solid #3a3a4a; padding: 2px 12px;
                border-radius: 6px; font-size: 12px;
            }
            QPushButton:hover { border-color: #888; color: white; }
        """)
        self.fs_btn_subtitle.clicked.connect(self._show_subtitle_menu)
        btn_row.addWidget(self.fs_btn_subtitle)

        self.fs_btn_stream_info = QPushButton("Info")
        self.fs_btn_stream_info.setCheckable(True)
        self.fs_btn_stream_info.setFixedHeight(32)
        self.fs_btn_stream_info.setStyleSheet("""
            QPushButton {
                background: transparent; color: #aaa;
                border: 1px solid #3a3a4a; padding: 2px 12px;
                border-radius: 6px; font-size: 12px;
            }
            QPushButton:hover { border-color: #888; color: white; }
            QPushButton:checked { border-color: #e8691a; color: #e8691a; }
        """)
        self.fs_btn_stream_info.clicked.connect(self._toggle_stream_info)
        btn_row.addWidget(self.fs_btn_stream_info)

        btn_row.addSpacing(12)

        vol_icon = QLabel("\U0001F50A")
        vol_icon.setStyleSheet("font-size: 15px; color: #aaa; background: transparent;")
        btn_row.addWidget(vol_icon)

        self.fs_volume_slider = QSlider(Qt.Horizontal)
        self.fs_volume_slider.setRange(0, 100)
        self.fs_volume_slider.setFixedWidth(110)
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
                background: #e8691a;
                border-radius: 2px;
            }
        """)
        self.fs_volume_slider.blockSignals(True)
        self.fs_volume_slider.setValue(100)
        self.fs_volume_slider.blockSignals(False)
        self.fs_volume_slider.valueChanged.connect(self._on_volume_changed)
        btn_row.addWidget(self.fs_volume_slider)

        btn_row.addSpacing(8)

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

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit")

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # indeterminate
        self.loading_bar.setFixedSize(120, 14)
        self.loading_bar.hide()
        self.status_bar.addPermanentWidget(self.loading_bar)
