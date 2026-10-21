"""Senderlogo: Maske für removelogo, Isolierung des Logos, Erkennung und Suche im Film.

Nachbau der VB6-Funktionen monochrome() / frmRemoveLogo, logo(), binary(), bin(), ones(),
where_logo() und rewind(). Die Zahlenwerte (8, 5, 400, 18, 0.2, 25, 20, 100) stammen aus VB6.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Optional

import numpy as np
from PIL import Image

from frames import grab_frame

THRESHOLD = 8        # frmRemoveLogo: Helligkeit ab 8 gilt als "weiß" (Logo)
EXTRA = 5            # Rand um das isolierte Logo in Pixeln
LINE_SUM = 400       # Summe der Bytes einer 1-Bit-Zeile, ab der sie als "Logo-Zeile" gilt
BIN_MIN = 18         # bin(): Helligkeitsunterschied benachbarter Pixel, ab dem eine Kante gezählt wird
MIN_CONF = 0.2       # where_logo(): Mindest-Übereinstimmung


@dataclass
class LogoRef:
    rect: tuple[int, int, int, int]      # links, oben, rechts, unten (Pixel, rechts/unten exklusiv)
    edges: np.ndarray                    # Kantenkarte des Referenzlogos (bool)
    ones: int                            # Anzahl der Kanten in der Referenz


# ----------------------------------------------------------------------------- Bausteine
def to_grey(img: np.ndarray) -> np.ndarray:
    """RGB -> 8-Bit-Grau (Rec.709 wie FreeImage_ConvertToGreyscale)."""
    r, g, b = (img[..., i].astype(np.float64) for i in range(3))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.5).astype(np.uint8)


def edge_map(grey: np.ndarray, bin_min: int = BIN_MIN) -> np.ndarray:
    """bin(): Pixel x ist eine Kante, wenn |grau(x) - grau(x+1)| > bin_min (VB6: 18). Letzte Spalte bleibt leer."""
    m = np.zeros(grey.shape, dtype=bool)
    m[:, :-1] = np.abs(grey[:, 1:].astype(int) - grey[:, :-1].astype(int)) > bin_min
    return m


def ones(m1: np.ndarray, m2: np.ndarray) -> int:
    """Anzahl gemeinsamer Kanten. Wie in VB6 bleibt die letzte Zeile außen vor."""
    return int((m1[:-1] & m2[:-1]).sum())


# ----------------------------------------------------------------------------- Maske (removelogo)
def make_mask(frame_rgb: np.ndarray, threshold: int = THRESHOLD, blend: float = 0.0) -> np.ndarray:
    """1-Bit-Maske eines (möglichst schwarzen) Bildes mit Logo: True = Logo.

    blend (0..1): schwärzt ein Band um die Bildmitte (Höhe = blend * halbe Bildhöhe nach oben
    und unten), um störende Reste mitten im Bild zu entfernen (hscBlend in frmRemoveLogo).
    """
    mask = to_grey(frame_rgb) >= threshold
    if blend > 0:
        h = mask.shape[0] // 2
        k = int(blend * h)
        mask[max(0, h - k): h + k + 1, :] = False
    return mask


def mask_to_png_b64(mask: np.ndarray) -> str:
    """Wie VB6 (SubItems(18)): 1-Bit-PNG als Base64-Text ohne Zeilenumbrüche."""
    buf = io.BytesIO()
    Image.fromarray(mask).save(buf, format="PNG")          # bool-Array -> Modus "1"
    return base64.b64encode(buf.getvalue()).decode("ascii")


def mask_from_png_b64(text: str) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(text))).convert("1"))


# ----------------------------------------------------------------------------- Logo isolieren
def isolate_logo(mask: np.ndarray, extra: int = EXTRA, bin_min: int = BIN_MIN) -> Optional[LogoRef]:
    """Sucht das Logo im oberen Viertel der Maske und bildet das Referenzlogo (monochrome()).

    Zeilen zählen als "Logo-Zeile", wenn die Summe ihrer Bytes (1 Byte = 8 Pixel, linkes Pixel = höchstes
    Bit) größer als 400 ist. Gefunden wird der erste zusammenhängende Block solcher Zeilen von oben.
    """
    h, w = mask.shape
    packed = np.packbits(mask, axis=1)
    sums = packed.sum(axis=1, dtype=np.int64)

    # 1. Schleife: obere linke Ecke (h0 = oberste Zeile in FreeImage-Zählung von unten, w0 = linkes Byte * 8)
    h0 = w0 = 0
    for y in range(h - 1, h * 3 // 4 - 1, -1):
        r = h - 1 - y
        if sums[r] > LINE_SUM:
            for x in np.flatnonzero(packed[r] > 7):
                if h0 == 0:
                    h0 = y
                if w0 == 0 or w0 > x * 8:
                    w0 = int(x) * 8
        elif w0 * h0 > 0:
            break
    if w0 * h0 == 0:
        return None

    # 2. Schleife: rechte untere Ecke, höchstens 50 Zeilen unterhalb von h0
    w1 = 0
    for y in range(h0, h0 - 51, -1):
        r = h - 1 - y
        if r < 0 or r >= h:
            break
        if sums[r] > LINE_SUM:
            for x in range(packed.shape[1] - 1, w0 // 8 - 1, -1):
                if packed[r, x] > 7 and (w1 == 0 or w1 < x * 8):
                    w1 = x * 8
        else:
            h1 = y
            left, top = max(0, w0 - extra), max(0, h - h0 - extra)
            right, bottom = min(w, w1 + extra), min(h, h - h1 + extra)
            crop = (mask[top:bottom, left:right] * 255).astype(np.uint8)
            edges = edge_map(crop, bin_min)
            return LogoRef((left, top, right, bottom), edges, ones(edges, edges))
    return None


# ----------------------------------------------------------------------------- Referenz aus Rechteck (delogo)
def absolute_rect(rel: str, width: int, height: int) -> tuple[int, int, int, int]:
    """SubItems(18) im delogo-Modus: 'x y breite höhe' als Bruchteile des Bildes -> Pixel (absolute())."""
    x, y, bw, bh = (float(t.replace(",", ".")) for t in rel.split(" ")[:4])
    return round(width * x), round(height * y), round(width * (x + bw)), round(height * (y + bh))


def ref_from_rect(frame_rgb: np.ndarray, rect: tuple[int, int, int, int], bin_min: int = BIN_MIN) -> LogoRef:
    """cmdLogo_Click ohne PNG-Maske: Referenz aus dem Rechteck des aktuellen Bildes."""
    left, top, right, bottom = rect
    edges = edge_map(to_grey(frame_rgb[top:bottom, left:right]), bin_min)
    return LogoRef(rect, edges, ones(edges, edges))


# ----------------------------------------------------------------------------- Erkennung
def logo_confidence(frame_rgb: np.ndarray, ref: LogoRef, bin_min: int = BIN_MIN) -> float:
    """Anteil der Referenzkanten, die im Logo-Rechteck dieses Bildes ebenfalls vorkommen (0..1)."""
    left, top, right, bottom = ref.rect
    edges = edge_map(to_grey(frame_rgb[top:bottom, left:right]), bin_min)
    return ones(edges, ref.edges) / ref.ones if ref.ones else 0.0


def confidence_at(path: str, frame: int, fps: Fraction, ref: LogoRef, opts: dict, ffmpeg: str = "ffmpeg") -> float:
    return logo_confidence(grab_frame(path, frame, fps, int(opts.get("floor", 2)), ffmpeg), ref,
                           int(opts.get("logo_edge", BIN_MIN)))


INITIAL_REWIND = 25        # Bilder, die zuerst zurückgegangen wird (VB6); dort liegt die Referenzfarbe
DEFAULT_MAX_REWIND = 45    # Bilder insgesamt (VB6: 25 + bis zu 20); bei 25 FPS 1,8 Sekunden
COARSE_STEP = 5            # bei langem Rückspulen wird zuerst in Schritten von 5 Bildern gesucht


def rewind(pos: int, bottom_line_avg: Callable[[int], tuple[int, int, int]], max_back: int = DEFAULT_MAX_REWIND) -> int:
    """Geht vom gefundenen Logo-Beginn zurück und sucht den Szenenwechsel (rewind()).

    Referenz ist der Mittelwert der untersten Bildzeile 25 Bilder vor `pos` (in VB6 FreeImage-Scanline 0); danach wird bis
    `max_back` Bilder insgesamt zurückgegangen, bis sich die Farbe um mehr als 100 ändert (VB6: höchstens 20 weitere Bilder,
    Bild für Bild). Bei längeren Strecken wird zuerst in Schritten von 5 Bildern gesucht und dann Bild für Bild verfeinert,
    damit das Zurückspulen auch über mehrere Sekunden schnell bleibt.
    """
    if max_back <= 0:
        return pos
    pos -= min(INITIAL_REWIND, max_back)
    steps = max_back - INITIAL_REWIND
    if steps <= 0:
        return pos
    ref = bottom_line_avg(pos)

    def changed(p: int) -> bool:
        return sum(abs(a - b) for a, b in zip(bottom_line_avg(p), ref)) > 100

    if steps <= 20:                                  # wie VB6: Bild für Bild
        for _ in range(steps):
            pos -= 1
            if changed(pos):
                break
        return pos + 1
    moved = 0
    while moved < steps:
        n = min(COARSE_STEP, steps - moved)
        if changed(pos - n):                         # der Wechsel liegt in diesen n Bildern: Bild für Bild nachsehen
            for _ in range(n):
                pos -= 1
                if changed(pos):
                    break
            return pos + 1
        pos -= n
        moved += n
    return pos + 1


def bottom_line_average(path: str, frame: int, fps: Fraction, opts: dict, ffmpeg: str = "ffmpeg") -> tuple[int, int, int]:
    img = grab_frame(path, max(0, frame), fps, int(opts.get("floor", 2)), ffmpeg)
    return tuple(int(v) for v in img[-1].astype(np.int64).sum(axis=0) // img.shape[1])


def where_logo(conf_of: Callable[[int], float], pos: int, last: int, equal: bool, stepping: int,
               rewind_fn: Optional[Callable[[int], int]] = None, min_conf: float = MIN_CONF) -> int:
    """Sucht ab Bild `pos` das nächste Bild MIT Logo (equal=True, danach rewind) bzw. OHNE Logo (equal=False).

    VB6-Aufrufe: 'Ende der Werbung' = (True, 1000), 'nächste Werbung' = (False, 6000).
    """
    while stepping > 0:
        if pos + stepping >= last:
            stepping = (stepping + 8) // 10          # Dateiende: nur Schrittweite verkleinern
            continue
        pos += stepping
        c = conf_of(pos)
        if (equal and c > min_conf) or (not equal and c < min_conf):
            pos -= stepping
            stepping = (stepping + 8) // 10
    if equal:
        return rewind_fn(pos) if rewind_fn else pos
    return pos + 1
