"""Erkennung schwarzer Ränder (Letterbox) und Suche nach Werbeblöcken über den Rand.

Nachbau von border() und where_border() aus VB6.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Callable

import numpy as np

from frames import grab_frame


def count_black_lines(img: np.ndarray, blackness: int = 12, allowance: int = 1000) -> int:
    """Zählt die schwarzen Zeilen am UNTEREN Bildrand.

    Pro Zeile werden alle Farbwerte (R, G, B einzeln), die größer als `blackness` sind, aufsummiert
    (die Helligkeit selbst, nicht nur die Anzahl). Ist diese Summe größer als `allowance`, ist die Zeile
    nicht mehr schwarz. Es werden höchstens 25 % der Bildhöhe untersucht. Ergebnis 0 heißt:
    kein Rand gefunden (oder das ganze Prüfgebiet ist schwarz, z. B. bei einem Schwarzbild).
    """
    h = img.shape[0]
    rows = img[::-1][: h // 4 + 1].astype(np.int32)           # von unten nach oben
    sums = np.where(rows > blackness, rows, 0).sum(axis=(1, 2))
    over = np.flatnonzero(sums > allowance)
    return int(over[0]) if over.size else 0


def border_at(path: str, frame: int, fps: Fraction, opts: dict, ffmpeg: str = "ffmpeg") -> int:
    img = grab_frame(path, frame, fps, int(opts.get("floor", 2)), ffmpeg)
    return count_black_lines(img, int(opts.get("blackness", 12)), int(opts.get("allowance", 1000)))


def where_border(border_of: Callable[[int], int], pos: int, last: int, value: int,
                 equal: bool, stepping: int, lim: int = 3) -> int:
    """Sucht ab Bild `pos` das nächste Bild, dessen Rand zu `value` passt (equal=True)
    bzw. davon abweicht (equal=False). Grob-zu-fein: große Schritte, bei Treffer einen Schritt
    zurück und die Schrittweite verkleinern, bis 1 erreicht ist.

    VB6-Aufrufe: 'Ende der Werbung' = where_border(crop, True, 1000); 'nächste Werbung' = (crop, False, 6000).
    Voraussetzung (wie in VB6): die Bedingung ist ab der Fundstelle dauerhaft erfüllt.
    """
    while stepping > 0:
        if pos + stepping > last:
            stepping = (stepping + 8) // 10          # Dateiende: nur Schrittweite verkleinern
            continue
        pos += stepping
        diff = abs(border_of(pos) - value)
        if (equal and diff < lim) or (not equal and diff > lim):
            pos -= stepping
            stepping = (stepping + 8) // 10          # erreicht auf jeden Fall 1 vor 0
    return min(pos + 1, last)
