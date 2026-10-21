"""Zeitleiste (VB6: picTimeline): 20 Vorschaubilder um den Marker, rote Kreuze für fehlende Bilder, roter Schnittstrich.

Das Bild RECHTS vom Strich hat die Nummer des Markers (Marker A: erstes Bild des Segments; Marker B: das Segment endet mit
dem Bild LINKS vom Strich). Ein Klick auf ein Bild verschiebt den Marker so, dass der Strich unmittelbar neben diesem Bild
liegt; die beiden Bilder direkt am Strich bewirken nichts.
"""
from __future__ import annotations

import time
from math import floor
from typing import Optional

from PySide6 import QtCore, QtGui

from player import debug_log

RANGE = 20                       # Anzahl der Vorschaubilder
LINE_WIDTH = 3                   # Breite des Schnittstrichs in Pixeln


def window_numbers(center: int, count: int = RANGE) -> list:
    """Bildnummern der Zeitleiste: von center - count/2 bis center + count/2 - 1; das Bild rechts vom Strich ist `center`."""
    start = center - count // 2
    return list(range(start, start + count))


def cell_width(width: int, count: int = RANGE) -> int:
    return max(width // count, 1)


def click_delta(index: int) -> int:
    """Verschiebung des Markers bei Klick auf das Bild mit dem Index 0..19 (von links): wie picTimeline_Click in VB6."""
    if index < 9:
        return index - 9
    if index > 10:
        return index - 10
    return 0


def click_index(x: int, width: int, count: int = RANGE) -> int:
    """Index (0..count-1) des Bildes unter x (Pixel ab dem linken Rand der Zeichenfläche).

    Gerechnet wird mit der Zellenbreite, mit der auch gezeichnet wird (VB6 teilte durch die ganze Breite und lag am rechten
    Rand dadurch um bis zu ein halbes Bild daneben); der Rest rechts außerhalb der Zellen zählt zum letzten Bild.
    """
    return max(0, min(count - 1, x // cell_width(width, count)))


def thumb_size(src_width: int, src_height: int, cell: int) -> tuple:
    """Größe eines Vorschaubildes: längste Seite = Zellenbreite - 1, das Pixelverhältnis der Quelle bleibt (wie FreeImage)."""
    side = max(cell - 1, 1)
    if src_width >= src_height:
        return side, max(1, round(side * src_height / src_width))
    return max(1, round(side * src_width / src_height)), side


def frame_number(pts: float, container_start: float, fps: float) -> int:
    return floor((pts - container_start) * fps + 1e-3)


def draw_strip(painter, rect, cells: list) -> None:
    """Zeichnet die Zeitleiste. cells = 20 Paare (Zustand, QImage): "image", "cross" (fehlt) oder "pending" (wird geladen)."""
    cw = cell_width(rect.width(), len(cells))
    top, height = rect.y(), rect.height()
    red = QtGui.QColor(255, 0, 0)
    for i, (state, image) in enumerate(cells):
        x0 = rect.x() + i * cw
        if state == "image" and image is not None:
            painter.drawImage(x0, top, image)
        elif state == "pending":                            # wird noch geladen: hellgraue Fläche
            painter.fillRect(x0, top, cw - 1, height, QtGui.QColor(215, 215, 215))
        elif state == "cross":
            painter.setPen(red)
            painter.drawLine(x0, top, x0 + cw, top + height)
            painter.drawLine(x0, top + height, x0 + cw, top)
    line_x = rect.x() + (len(cells) // 2) * cw
    painter.fillRect(line_x - LINE_WIDTH // 2, top, LINE_WIDTH, height, red)


class ThumbLoader(QtCore.QThread):
    """Holt die Vorschaubilder im Hintergrund (ein Aufruf von ffmpeg); ein Abbruch beendet ffmpeg."""

    loaded = QtCore.Signal(int, object, object)          # Marke, {Nummer: Array}, (erste, letzte angeforderte Nummer)
    failed = QtCore.Signal(int, str)                     # Marke, Fehlermeldung

    def __init__(self, token: int, path: str, first: int, last: int, fps, size: tuple, grab_fn):
        super().__init__()
        self.token, self.path, self.first, self.last = token, path, first, last
        self.fps, self.size, self.grab_fn = fps, size, grab_fn
        self._proc = None
        self.cancelled = False

    def _remember(self, proc) -> None:
        self._proc = proc
        if self.cancelled:
            proc.terminate()

    def cancel(self) -> None:
        self.cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()

    def run(self) -> None:
        started = time.monotonic()
        try:
            frames = self.grab_fn(self.path, self.first, self.last - self.first + 1, self.fps, self.size,
                                  on_start=self._remember)
        except Exception as e:                             # nicht lesbar (oder abgebrochen): melden, nicht verschlucken
            if not self.cancelled:
                debug_log(f"Vorschaubilder {self.first}..{self.last} fehlgeschlagen: {e!r}")
                self.failed.emit(self.token, f"{type(e).__name__}: {e}")
            return
        debug_log(f"Vorschaubilder {self.first}..{self.last}: {len(frames)} Bilder in {time.monotonic() - started:.1f} s")
        if not self.cancelled:
            self.loaded.emit(self.token, frames, (self.first, self.last))
