"""
VOD-Details: Film-Detailansicht, Poster, Ratings, Besetzung
"""
import asyncio
import aiohttp

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout

from xtream_api import VodStream


class VodDetailMixin:

    def _show_vod_detail(self, vod: VodStream):
        """Zeigt die VOD-Detailansicht an"""
        self._current_vod = vod
        if vod.category_id:
            account = self.account_manager.get_selected()
            if account:
                self.session_manager.save_vod(
                    account.name, vod.stream_id, vod.name,
                    vod.stream_icon, vod.container_extension, vod.category_id
                )
        self.vod_title_label.setText(vod.name)
        self.vod_hero_title.setText(vod.name)
        self.vod_subtitle_label.setText("")
        self.vod_plot_label.setText("")
        self.vod_plot_header.hide()
        self.vod_director_widget.hide()
        self.vod_cast_widget.hide()
        self.vod_genre_widget.hide()
        self.vod_cover_label.clear()
        self.vod_cover_label.setText("🎬")
        self.vod_loading_bar.show()
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
            self.vod_loading_bar.hide()

            # Cover laden
            cover_url = info.get("cover_big", "") or info.get("movie_image", "") or vod.stream_icon
            if cover_url:
                asyncio.ensure_future(self._load_vod_cover(cover_url))

        except Exception as e:
            self._hide_loading(f"Fehler: {e}")
            self.vod_loading_bar.hide()
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

        # PiP-Modus verlassen BEVOR _toggle_player_maximized aufgerufen wird,
        # damit dieser nicht faelschlicherweise _switch_mode("live") triggert.
        if self._pip_mode:
            self._exit_pip_mode()

        self._play_stream(url, vod.name, "vod", vod.stream_id,
                          icon=getattr(vod, 'stream_icon', ''),
                          container_extension=vod.container_extension)

        if resume_pos > 0:
            QTimer.singleShot(500, lambda: self.player.seek(resume_pos, relative=False))

        # Vollbild beim VOD-Start
        if not self._player_maximized:
            self._toggle_player_maximized()

    def _vod_back(self):
        """Zurueck zur Filmliste"""
        self.channel_stack.setCurrentIndex(0)

    def _play_trailer(self):
        """Oeffnet den Trailer im Browser"""
        if self._current_trailer_url:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(self._current_trailer_url))
