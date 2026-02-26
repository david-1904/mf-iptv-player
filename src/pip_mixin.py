"""
PiP-Modus & Loading-Overlay
"""
import asyncio


class PipMixin:

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

        # PiP-Leiste positionieren und zeigen
        self.pip_title_label.setText(self._current_stream_title or "")
        self.pip_bar.setGeometry(0, 0, self.player_area.width(), 40)
        self.pip_bar.raise_()
        self.pip_bar.show()

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

        # PiP-Leiste verstecken
        self.pip_bar.hide()

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
        width = 400 if self.current_mode in ("vod", "series") else 360
        self.channel_area.setFixedWidth(width)

    def _on_pip_expand(self):
        """PiP verlassen und zurück zum Live-Modus mit vollem Player"""
        self._exit_pip_mode()
        self._switch_mode("live")

    def _update_pip_position(self):
        """Positioniert den PiP-Player in die rechte untere Ecke"""
        if not self._pip_mode:
            return
        parent = self.main_page
        margin = 16
        x = parent.width() - self.player_area.width() - margin
        y = parent.height() - self.player_area.height() - margin
        self.player_area.move(max(0, x), max(0, y))

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
