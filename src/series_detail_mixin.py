"""
Serien-Details: Staffeln, Episoden, Cover-Laden
"""
import asyncio
import aiohttp

from PySide6.QtCore import Qt, Slot, QTimer, QSize
from PySide6.QtWidgets import (
    QListWidgetItem, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy
)

from xtream_api import Series


class SeriesDetailMixin:

    def _show_series_detail(self, series: Series):
        """Zeigt die Serien-Detailansicht an"""
        self._current_series = series
        if series.category_id:
            account = self.account_manager.get_selected()
            if account:
                self.session_manager.save_series(
                    account.name, series.series_id, series.name, series.cover, series.category_id
                )
        self.series_title_label.setText(series.name)
        self.series_plot_label.setPlainText(series.plot or "")
        self.series_subtitle_label.setText("")
        rating = series.rating if series.rating and series.rating not in ("0", "") else ""
        if rating:
            self.series_rating_label.setText(f"\u2605  {rating}")
            self.series_rating_label.show()
        else:
            self.series_rating_label.hide()
        self.series_cover_label.clear()
        self.series_cover_label.setText("\u25B6")
        self.season_combo.clear()
        self.episode_list.clear()
        self._series_data = None
        self._series_trailer_url = ""
        self.btn_series_trailer.hide()

        # Volle Fensterbreite fuer Serien-Detail: Zustand speichern + Player ausblenden
        self._series_player_was_visible = self.player_area.isVisible()
        self._series_channel_area_min = self.channel_area.minimumWidth()
        self._series_channel_area_max = self.channel_area.maximumWidth()
        self._series_channel_area_visible = self.channel_area.isVisible()
        if self._series_player_was_visible:
            self.player_area.hide()
        self.channel_area.show()
        self.channel_area.setMinimumWidth(0)
        self.channel_area.setMaximumWidth(16777215)

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
            self.series_plot_label.setPlainText(plot)
            rating = str(info.get("rating", "")) or series.rating or ""
            if rating and rating not in ("0", ""):
                self.series_rating_label.setText(f"\u2605  {rating}")
                self.series_rating_label.show()
            else:
                self.series_rating_label.hide()

            # Subtitle: Jahr · Genre · Staffeln
            parts = []
            year = str(info.get("releaseDate", "") or info.get("release_date", "") or "")[:4]
            if year and year.isdigit():
                parts.append(year)
            genre = str(info.get("genre", "") or "").strip()
            if genre:
                parts.append(genre[:40])
            n_seasons = len(data["seasons"])
            if n_seasons:
                parts.append(f"{n_seasons} {'Staffel' if n_seasons == 1 else 'Staffeln'}")
            self.series_subtitle_label.setText("  \u00b7  ".join(parts))

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

            # Trailer
            import urllib.parse
            trailer = info.get("youtube_trailer", "") or info.get("trailer", "")
            if trailer:
                if trailer.startswith("http"):
                    self._series_trailer_url = trailer
                else:
                    self._series_trailer_url = f"https://www.youtube.com/watch?v={trailer}"
            else:
                query = urllib.parse.quote_plus(f"{series.name} trailer")
                self._series_trailer_url = f"https://www.youtube.com/results?search_query={query}"
            self.btn_series_trailer.show()

            # Cover laden
            cover_url = info.get("cover", "") or series.cover
            if cover_url:
                asyncio.ensure_future(self._load_series_cover(cover_url))

        except Exception as e:
            self._hide_loading(f"Fehler: {e}")

    async def _load_series_cover(self, url: str):
        """Laedt das Serien-Cover asynchron"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            pixmap = await self._fetch_poster(session, url, 200, 300)
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
            item = QListWidgetItem()
            item.setData(Qt.UserRole, ep)

            has_duration = bool(ep.duration)
            item.setSizeHint(QSize(0, 58 if has_duration else 46))

            card = QWidget()
            card.setStyleSheet("background: transparent;")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(14, 0, 14, 0)
            card_layout.setSpacing(12)

            # Episode-Badge
            badge = QLabel(f"E{ep.episode_num:02d}")
            badge.setFixedSize(36, 22)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet("""
                background-color: #0a1e33;
                color: #5a9fd4;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            """)
            card_layout.addWidget(badge, alignment=Qt.AlignVCenter)

            # Titel + Dauer untereinander
            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            text_col.setContentsMargins(0, 0, 0, 0)

            title_lbl = QLabel(ep.title)
            title_lbl.setStyleSheet("color: #ccc; font-size: 13px; background: transparent;")
            title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            text_col.addWidget(title_lbl)

            if has_duration:
                dur_lbl = QLabel(ep.duration)
                dur_lbl.setStyleSheet("color: #444; font-size: 11px; background: transparent;")
                text_col.addWidget(dur_lbl)

            card_layout.addLayout(text_col, stretch=1)

            self.episode_list.addItem(item)
            self.episode_list.setItemWidget(item, card)

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

        if self._pip_mode:
            self._exit_pip_mode()

        self._play_stream(url, title, "vod", ep.id,
                          container_extension=ep.container_extension)

        if resume_pos > 0:
            QTimer.singleShot(500, lambda: self.player.seek(resume_pos, relative=False))

    def _play_series_trailer(self):
        """Oeffnet den Serien-Trailer im Browser"""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if self._series_trailer_url:
            QDesktopServices.openUrl(QUrl(self._series_trailer_url))

    def _series_back(self):
        """Zurueck zur Kanalliste"""
        self.channel_stack.setCurrentIndex(0)
        # Exakt gespeicherten Zustand wiederherstellen
        min_w = getattr(self, "_series_channel_area_min", 0)
        max_w = getattr(self, "_series_channel_area_max", 16777215)
        self.channel_area.setMinimumWidth(min_w)
        self.channel_area.setMaximumWidth(max_w)
        if getattr(self, "_series_channel_area_visible", True):
            self.channel_area.show()
        else:
            self.channel_area.hide()
        if getattr(self, "_series_player_was_visible", False):
            self.player_area.show()
