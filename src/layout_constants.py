"""
Zentrale Layout-Konstanten fuer groessenabhaengiges Sizing.

Werte, die vorher an mehreren Stellen unabhaengig als Magic Numbers
dupliziert waren, leben hier, damit Anpassungen fuer unterschiedliche
Bildschirmgroessen/DPI-Einstellungen nur an einer Stelle noetig sind.
"""

# Live-Kanalliste (neben dem Player im Live-Modus)
LIVE_CHANNEL_AREA_DEFAULT_WIDTH = 360        # Startwert, bevor Inhalt gemessen wurde
LIVE_CHANNEL_AREA_MIN_WIDTH = 300
LIVE_CHANNEL_AREA_MAX_WIDTH = 500            # Obergrenze bei gespeicherter Inhaltsbreite
LIVE_CHANNEL_AREA_CONTENT_MAX_WIDTH = 560    # Obergrenze bei automatischer Inhaltsmessung

# VOD/Serien-Grid
GRID_MIN_CELL_WIDTH = 180
GRID_TARGET_CELL_WIDTH = 210  # Spaltenzahl richtet sich danach -> gleich grosse Poster auf allen Breiten
GRID_POSTER_ASPECT_RATIO = 1.5
GRID_TITLE_AREA_HEIGHT = 48
GRID_CELL_HORIZONTAL_PADDING = 16

# Fullscreen-Steuerleiste
FULLSCREEN_CONTROLS_MIN_HEIGHT = 90
FULLSCREEN_CONTROLS_MAX_HEIGHT_RATIO = 0.45
