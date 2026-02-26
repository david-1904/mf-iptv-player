"""
Account-Verwaltung: Laden, Hinzufuegen, Loeschen, Wechseln
"""
import asyncio

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from xtream_api import XtreamAPI, XtreamCredentials
from m3u_provider import M3uProvider
from account_manager import AccountEntry


class AccountMixin:

    @Slot(int)
    def _on_account_type_changed(self, index: int):
        """Zeigt/versteckt Felder je nach Account-Typ"""
        account_type = self.account_type_combo.itemData(index)
        self.xtream_fields.setVisible(account_type == "xtream")
        self.m3u_fields.setVisible(account_type == "m3u")

    def _load_initial_account(self):
        """Laedt gespeicherte Accounts beim Start"""
        self._update_account_combo()
        account = self.account_manager.get_selected()
        if account:
            # Letzten Modus wiederherstellen
            is_m3u = account.type == "m3u"
            saved_mode = self.session_manager.get_mode(account.name)
            if saved_mode in ("live", "vod", "series") and not (saved_mode == "series" and is_m3u):
                self.current_mode = saved_mode
                self.btn_live.setChecked(saved_mode == "live")
                self.btn_vod.setChecked(saved_mode == "vod")
                self.btn_series.setChecked(saved_mode == "series")
                self.btn_favorites.setChecked(False)
                self.btn_history.setChecked(False)
                self.category_btn.setVisible(True)
                self.sort_widget.setVisible(saved_mode in ("vod", "series"))

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
                self._epg_cache = {}
                self._initial_epg_loaded = False

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

        # EPG-Cache leeren → beim naechsten Kanalklick frisch laden
        self._epg_cache = {}
        self._clear_epg_panel()
        self._initial_epg_loaded = False

        # Cache fuer aktuellen Modus leeren
        if self.current_mode == "live":
            self.live_categories = []
        elif self.current_mode == "vod":
            self.vod_categories = []
        else:
            self.series_categories = []

        asyncio.ensure_future(self._load_categories())
