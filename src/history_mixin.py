"""
Verlauf & Aufnahmen: Wiedergabeverlauf, Aufnahme-Steuerung, Position speichern/laden
"""
from datetime import datetime

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QAbstractItemView,
    QScroller, QMessageBox
)

from watch_history_manager import WatchEntry


class HistoryMixin:

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

        # Geplante / laufende Aufnahmen oben anzeigen
        active = self.schedule_manager.get_active()
        now = datetime.now().timestamp()
        for rec in active:
            if rec.status == "recording":
                label = f"\u23FA  {rec.channel_name}"
                if rec.epg_title:
                    label += f" \u2013 {rec.epg_title}"
                end_str = datetime.fromtimestamp(rec.end_timestamp).strftime("%H:%M")
                label += f"  \u2022  L\u00e4uft bis {end_str}"
            else:
                start_str = datetime.fromtimestamp(rec.start_timestamp).strftime("%d.%m. %H:%M")
                end_str = datetime.fromtimestamp(rec.end_timestamp).strftime("%H:%M")
                label = f"\U0001F4F9  {rec.channel_name}"
                if rec.epg_title:
                    label += f" \u2013 {rec.epg_title}"
                label += f"  \u2022  {start_str} \u2013 {end_str}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, ("scheduled", rec))
            item.setForeground(
                __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(
                    "#e8691a" if rec.status == "recording" else "#6fcf97"
                )
            )
            self.channel_list.addItem(item)

        rec_dir = self.recorder.output_dir
        if not rec_dir.exists() and not active:
            self.status_bar.showMessage("Keine Aufnahmen vorhanden")
            return
        elif not rec_dir.exists():
            self.status_bar.showMessage(f"{len(active)} geplante Aufnahmen")
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
        """Startet oder stoppt die Aufnahme (aufrufbar von beiden Record-Buttons)"""
        if self.recorder.is_recording:
            # Stoppen
            filepath = self.recorder.stop()
            if filepath and filepath.exists() and filepath.stat().st_size > 0:
                self.status_bar.showMessage(f"Aufnahme gespeichert: {filepath.name}")
            else:
                self.status_bar.showMessage("Aufnahme gestoppt")
            self._sync_record_buttons(False)
        else:
            # Starten
            if not self._current_stream_url:
                self._sync_record_buttons(False)
                return
            filepath = self.recorder.start(self._current_stream_url, self._current_stream_title)
            self.status_bar.showMessage(f"Aufnahme: {filepath.name}")
            self._sync_record_buttons(True)

    def _sync_record_buttons(self, recording: bool):
        """Synchronisiert den Aufnahme-Status in allen Buttons."""
        tip = "Aufnahme stoppen" if recording else "Aufnahme starten"
        self.btn_record.setChecked(recording)
        self.btn_record.setToolTip(tip)
        fs_btn = getattr(self, 'fs_btn_record', None)
        if fs_btn:
            fs_btn.setChecked(recording)
            fs_btn.setToolTip(tip)

    def _update_record_button(self):
        """Aktualisiert das Aussehen des Aufnahme-Buttons"""
        self._sync_record_buttons(self.recorder.is_recording)

    def _update_recording_status(self):
        """Aktualisiert den Aufnahme-Status in der Statusbar"""
        # Button-State synchronisieren falls ffmpeg unerwartet beendet
        if self.btn_record.isChecked() and not self.recorder.is_recording:
            self._sync_record_buttons(False)
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
