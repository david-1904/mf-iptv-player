"""
Kreisfoermiger Rating-Indikator (TMDB/Rotten Tomatoes Style)
"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class CircularRatingWidget(QWidget):
    """Kreisfoermiger Score-Indikator mit farbigem Arc"""

    def __init__(self, score: float, size: int = 56, parent=None):
        super().__init__(parent)
        self._score = max(0.0, min(10.0, score))
        self._size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        score = self._score
        size = self._size
        pen_width = 4
        margin = pen_width / 2 + 1

        # Farbe nach Score
        if score >= 7:
            arc_color = QColor("#21d07a")
            track_color = QColor("#204529")
        elif score >= 5:
            arc_color = QColor("#d2d531")
            track_color = QColor("#423d0f")
        else:
            arc_color = QColor("#db2360")
            track_color = QColor("#571435")

        rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

        # Hintergrund-Kreis
        painter.setBrush(QColor("#081c22"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(0, 0, size, size))

        # Track (Hintergrund-Ring)
        track_pen = QPen(track_color, pen_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)

        # Score-Arc
        if score > 0:
            arc_pen = QPen(arc_color, pen_width, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(arc_pen)
            span = int((score / 10.0) * 360 * 16)
            painter.drawArc(rect, 90 * 16, -span)

        # Score-Text zentriert
        painter.setPen(QColor("#fff"))
        font = QFont()
        font.setPixelSize(int(size * 0.32))
        font.setBold(True)
        painter.setFont(font)

        # Ganzzahl oder eine Dezimalstelle
        if score == int(score):
            text = f"{int(score)}"
        else:
            text = f"{score:.1f}"

        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, text)
        painter.end()


def create_rating_indicator(source: str, score: float, vote_count: int = 0) -> QWidget:
    """Erstellt ein fertiges Container-Widget mit Kreis + Label + Vote-Count"""
    container = QWidget()
    container.setAttribute(Qt.WA_TranslucentBackground)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.setAlignment(Qt.AlignCenter)

    # Rating-Kreis
    circle = CircularRatingWidget(score, 56)
    layout.addWidget(circle, alignment=Qt.AlignCenter)

    # Source-Label
    source_label = QLabel(source)
    source_label.setAlignment(Qt.AlignCenter)
    source_label.setStyleSheet("color: #aaa; font-size: 11px; background: transparent;")
    layout.addWidget(source_label)

    # Vote-Count
    if vote_count > 0:
        if vote_count >= 1000:
            count_text = f"{vote_count / 1000:.1f}K"
        else:
            count_text = str(vote_count)
        count_label = QLabel(count_text)
        count_label.setAlignment(Qt.AlignCenter)
        count_label.setStyleSheet("color: #666; font-size: 10px; background: transparent;")
        layout.addWidget(count_label)

    return container
