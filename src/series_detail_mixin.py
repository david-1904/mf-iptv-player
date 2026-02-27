"""
Serien-Details: Staffeln, Episoden, Cover-Laden
"""
import asyncio
import aiohttp

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtWidgets import QListWidgetItem

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

        if self._pip_mode:
            self._exit_pip_mode()

        self._play_stream(url, title, "vod", ep.id,
                          container_extension=ep.container_extension)

        if resume_pos > 0:
            QTimer.singleShot(500, lambda: self.player.seek(resume_pos, relative=False))

    def _series_back(self):
        """Zurueck zur Kanalliste"""
        self.channel_stack.setCurrentIndex(0)
