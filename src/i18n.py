"""
i18n-Helper für Mixin-Klassen.

Mixin-Klassen erben nicht von QObject und haben daher keinen eigenen
tr()-Context. Diese Funktion verwendet explizit "MainWindow" als Context,
damit pylupdate6 und Qt zur Laufzeit denselben Context nutzen.

Verwendung in Mixin-Dateien:
    from i18n import _tr
    self.btn_live = AnimatedButton(_tr("Live TV"))
"""
from PySide6.QtCore import QCoreApplication


def _tr(text: str) -> str:
    return QCoreApplication.translate("MainWindow", text)
