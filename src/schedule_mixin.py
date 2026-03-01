"""
Geplante Aufnahmen: Background-Checker, Planungs-Dialog
"""
import asyncio
import uuid
from datetime import datetime

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDateTimeEdit,
)

from schedule_manager import ScheduledRecording


class ScheduleMixin:

    async def _schedule_checker_loop(self):
        """Laeuft im Hintergrund, prueft alle 30s ob Aufnahmen faellig sind."""
        while True:
            await asyncio.sleep(30)
            self._check_scheduled_recordings()

    def _check_scheduled_recordings(self):
        now = datetime.now().timestamp()
        changed = False

        for rec in self.schedule_manager.get_all():
            if rec.status == "pending" and rec.start_timestamp <= now < rec.end_timestamp:
                if not self.recorder.is_recording:
                    display = rec.channel_name
                    if rec.epg_title:
                        display += f" \u2013 {rec.epg_title}"
                    self.recorder.start(rec.stream_url, display)
                    self._sync_record_buttons(True)
                    self.status_bar.showMessage(f"\u23FA Geplante Aufnahme gestartet: {display}")
                else:
                    self.status_bar.showMessage(
                        f"Geplante Aufnahme konnte nicht starten (andere Aufnahme laeuft): {rec.channel_name}"
                    )
                    rec.status = "failed"
                    changed = True
                    continue
                rec.status = "recording"
                changed = True

            elif rec.status == "recording" and now >= rec.end_timestamp:
                self.recorder.stop()
                self._sync_record_buttons(False)
                rec.status = "done"
                changed = True
                self.status_bar.showMessage(f"Geplante Aufnahme beendet: {rec.channel_name}")

        if changed:
            self.schedule_manager.save()
            if self.current_mode == "recordings":
                self._load_recordings()

    def _open_schedule_dialog(self, channel_name: str, stream_url: str,
                               start_ts: float, end_ts: float, epg_title: str = ""):
        """Oeffnet den Dialog zum Planen einer Aufnahme."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Aufnahme planen")
        dialog.setModal(True)
        dialog.setMinimumWidth(380)
        dialog.setStyleSheet("""
            QDialog { background: #1a1a2a; color: white; }
            QLabel { color: #ccc; font-size: 13px; }
            QLabel#lbl_channel { color: white; font-size: 15px; font-weight: bold; }
            QLabel#lbl_epg { color: #aaa; font-size: 13px; }
            QPushButton {
                padding: 8px 16px; border-radius: 6px;
                background: #2a2a3a; color: white; border: none; font-size: 13px;
            }
            QPushButton:hover { background: #3a3a4a; }
            QPushButton#btn_confirm {
                background: #c0392b; color: white; font-weight: bold;
            }
            QPushButton#btn_confirm:hover { background: #e74c3c; }
            QDateTimeEdit {
                background: #2a2a3a; color: white; border: 1px solid #3a3a4a;
                border-radius: 4px; padding: 6px 8px; font-size: 13px;
            }
            QDateTimeEdit:focus { border-color: #0078d4; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_channel = QLabel(f"\u23FA  {channel_name}")
        lbl_channel.setObjectName("lbl_channel")
        layout.addWidget(lbl_channel)

        if epg_title:
            lbl_epg = QLabel(epg_title)
            lbl_epg.setObjectName("lbl_epg")
            lbl_epg.setWordWrap(True)
            layout.addWidget(lbl_epg)

        layout.addSpacing(4)

        # Start
        start_row = QHBoxLayout()
        start_row.addWidget(QLabel("Start:"))
        start_dt = QDateTimeEdit()
        start_dt.setDisplayFormat("dd.MM.yyyy  HH:mm")
        start_dt.setCalendarPopup(True)
        start_dt.setDateTime(QDateTime.fromSecsSinceEpoch(int(start_ts)))
        start_row.addWidget(start_dt)
        layout.addLayout(start_row)

        # Ende
        end_row = QHBoxLayout()
        end_row.addWidget(QLabel("Ende:  "))
        end_dt = QDateTimeEdit()
        end_dt.setDisplayFormat("dd.MM.yyyy  HH:mm")
        end_dt.setCalendarPopup(True)
        end_dt.setDateTime(QDateTime.fromSecsSinceEpoch(int(end_ts)))
        end_row.addWidget(end_dt)
        layout.addLayout(end_row)

        layout.addSpacing(8)

        # Buttons
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(dialog.reject)
        btn_confirm = QPushButton("\u23FA  Aufnahme planen")
        btn_confirm.setObjectName("btn_confirm")

        def on_confirm():
            import time
            s_ts = float(start_dt.dateTime().toSecsSinceEpoch())
            e_ts = float(end_dt.dateTime().toSecsSinceEpoch())
            if e_ts <= s_ts:
                return
            account = self.account_manager.get_selected()
            now = time.time()

            if s_ts <= now < e_ts:
                # Sofort starten – keine Verzögerung durch Checker
                rec = ScheduledRecording(
                    id=str(uuid.uuid4()),
                    channel_name=channel_name,
                    stream_url=stream_url,
                    start_timestamp=s_ts,
                    end_timestamp=e_ts,
                    account_name=account.name if account else "",
                    epg_title=epg_title,
                    status="recording",
                )
                self.schedule_manager.add(rec)
                display = channel_name
                if epg_title:
                    display += f" \u2013 {epg_title}"
                self.recorder.start(stream_url, display)
                self._sync_record_buttons(True)
                self.status_bar.showMessage(f"\u23FA Aufnahme gestartet: {display}")
            else:
                rec = ScheduledRecording(
                    id=str(uuid.uuid4()),
                    channel_name=channel_name,
                    stream_url=stream_url,
                    start_timestamp=s_ts,
                    end_timestamp=e_ts,
                    account_name=account.name if account else "",
                    epg_title=epg_title,
                    status="pending",
                )
                self.schedule_manager.add(rec)
                start_str = start_dt.dateTime().toString("HH:mm")
                self.status_bar.showMessage(
                    f"Aufnahme geplant: {channel_name} um {start_str}"
                )
            dialog.accept()

        btn_confirm.clicked.connect(on_confirm)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_confirm)
        layout.addLayout(btn_row)

        dialog.exec()
