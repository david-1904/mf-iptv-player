"""
Hero-Widget mit Backdrop: zeichnet ein Szenenbild hinter dem Inhalt,
abgedunkelt durch einen Verlauf (Scrim), damit Text lesbar bleibt.
Das Bild blendet nach dem Laden weich ein.
"""
from PySide6.QtWidgets import QFrame
from PySide6.QtCore import Qt, QRect, QSize, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QPixmap, QLinearGradient, QColor


class BackdropHero(QFrame):
    """QFrame das ein Cover-fuellendes Backdrop mit Scrim rendert.

    full_page=False: Hero-Streifen — Scrim links dunkler, unten Fade-out.
    full_page=True:  Ganzseitiger Hintergrund — Bild oben praesent, nach
                     unten zunehmend abgedunkelt (kein leerer Raum unter
                     kurzen Inhalten).
    """

    def __init__(self, parent=None, full_page: bool = False):
        super().__init__(parent)
        self._full_page = full_page
        self._pixmap: QPixmap | None = None
        self._scaled: QPixmap | None = None
        self._scaled_for: QSize = QSize()
        self._opacity = 0.0
        # Zaehler gegen Races: verhindert, dass ein verspaetet fertig geladenes
        # Backdrop des vorherigen Titels auf dem neuen landet
        self.generation = 0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(700)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, value):
        self._opacity = float(value)
        self.update()

    def set_backdrop(self, pixmap: QPixmap):
        """Setzt das Backdrop und blendet es weich ein."""
        if pixmap is None or pixmap.isNull():
            return
        self._pixmap = pixmap
        self._scaled = None
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def clear_backdrop(self):
        """Entfernt das Backdrop (beim Oeffnen eines neuen Titels)."""
        self.generation += 1
        self._anim.stop()
        self._pixmap = None
        self._scaled = None
        self._opacity = 0.0
        self.update()

    def _ensure_scaled(self, size: QSize):
        """Skaliert das Backdrop Cover-fuellend (cached pro Widget-Groesse)."""
        if self._scaled is not None and self._scaled_for == size:
            return
        self._scaled = self._pixmap.scaled(
            size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        self._scaled_for = QSize(size)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()

        # Grundfarbe (auch Fallback ohne Backdrop)
        painter.fillRect(rect, QColor(13, 13, 28))

        if self._pixmap is not None and not self._pixmap.isNull():
            self._ensure_scaled(rect.size())
            # Settle-Zoom: waehrend des Einblendens minimal hineingezoomt,
            # gleitet auf 1.0 — wirkt wie ein kurzer Kino-Moment beim Oeffnen
            zoom = 1.0 + 0.05 * (1.0 - self._opacity)
            src_w = max(1, int(rect.width() / zoom))
            src_h = max(1, int(rect.height() / zoom))
            # Zentriert beschneiden, vertikal Richtung oberes Drittel
            # (dort liegt bei Szenenbildern meist der Bildfokus)
            src_x = max(0, (self._scaled.width() - src_w) // 2)
            src_y = max(0, (self._scaled.height() - src_h) // 3)
            painter.setOpacity(self._opacity)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap(
                rect, self._scaled,
                QRect(src_x, src_y, src_w, src_h)
            )
            painter.setOpacity(1.0)

        if self._full_page:
            # Vertikal: oben Bild sichtbar, nach unten fast deckend dunkel
            v_scrim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            v_scrim.setColorAt(0.0, QColor(8, 8, 18, 115))
            v_scrim.setColorAt(0.45, QColor(9, 9, 19, 205))
            v_scrim.setColorAt(1.0, QColor(10, 10, 20, 247))
            painter.fillRect(rect, v_scrim)
            # Horizontal: linke Text-/Poster-Spalte zusaetzlich abdunkeln
            h_scrim = QLinearGradient(rect.topLeft(), rect.topRight())
            h_scrim.setColorAt(0.0, QColor(8, 8, 18, 150))
            h_scrim.setColorAt(0.55, QColor(8, 8, 18, 40))
            h_scrim.setColorAt(1.0, QColor(8, 8, 18, 15))
            painter.fillRect(rect, h_scrim)
        else:
            # Scrim: links dunkler (dort liegen Poster + Text), rechts luftiger
            scrim = QLinearGradient(rect.topLeft(), rect.topRight())
            scrim.setColorAt(0.0, QColor(8, 8, 18, 225))
            scrim.setColorAt(0.5, QColor(8, 8, 18, 175))
            scrim.setColorAt(1.0, QColor(8, 8, 18, 95))
            painter.fillRect(rect, scrim)

            # Unterer Fade: weicher Uebergang in den Detailbereich darunter
            fade_h = min(110, rect.height() // 3)
            fade_rect = QRect(rect.x(), rect.bottom() - fade_h + 1, rect.width(), fade_h)
            fade = QLinearGradient(fade_rect.topLeft(), fade_rect.bottomLeft())
            fade.setColorAt(0.0, QColor(10, 10, 20, 0))
            fade.setColorAt(1.0, QColor(10, 10, 20, 230))
            painter.fillRect(fade_rect, fade)
