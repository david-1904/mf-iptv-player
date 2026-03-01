"""
Audio/Untertitel/Stream-Info: Track-Auswahl, Info-Panel
"""
from PySide6.QtWidgets import QMenu


class StreamControlsMixin:

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

        btn = self.sender() or self.btn_audio
        menu.exec(btn.mapToGlobal(btn.rect().topLeft()))

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

        btn = self.sender() or self.btn_subtitle
        menu.exec(btn.mapToGlobal(btn.rect().topLeft()))

    def _toggle_stream_info(self):
        """Toggle stream info panel visibility"""
        # Sender kann btn_stream_info oder fs_btn_stream_info sein — beide sync halten
        btn = self.sender()
        checked = btn.isChecked() if btn else self.btn_stream_info.isChecked()
        self.btn_stream_info.setChecked(checked)
        fs_btn = getattr(self, 'fs_btn_stream_info', None)
        if fs_btn:
            fs_btn.setChecked(checked)
        if checked:
            self.stream_info_panel.show()
            self._update_stream_info()
            self.stream_info_timer.start(2000)
        else:
            self.stream_info_panel.hide()
            self.stream_info_timer.stop()

    def _cycle_zoom_mode(self):
        """Wechselt zwischen Normal / Fill / Stretch"""
        _ZOOM_MODES = [
            ("Normal",  0.0, True),   # panscan=0, keepaspect=yes
            ("Fill",    1.0, True),   # panscan=1 (zoom+crop), keepaspect=yes
            ("Stretch", 0.0, False),  # panscan=0, keepaspect=no (strecken)
        ]
        idx = getattr(self, "_zoom_mode_index", 0)
        idx = (idx + 1) % len(_ZOOM_MODES)
        self._zoom_mode_index = idx
        name, panscan, keepaspect = _ZOOM_MODES[idx]
        try:
            self.player.player["panscan"] = panscan
            self.player.player["keepaspect"] = keepaspect
        except Exception:
            pass
        self.btn_zoom.setText(name)
        if hasattr(self, "fs_btn_zoom"):
            self.fs_btn_zoom.setText(name)
        self.status_bar.showMessage(f"Bildgr\u00f6\u00dfe: {name}")

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
