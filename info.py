"""Übersicht über alle Segmente (VB6: Menü Information, frmInfo): was die Liste ergibt, wenn sie so geschnitten wird.

Zu jedem Segment stehen Quelldatei, Lage im fertigen Film (Start- und Endzeit, daran lassen sich die Schnittpunkte und später die
Kapitel prüfen) und Eigenschaften der Quelle. Unter der Liste steht eine Zusammenfassung mit der Gesamtlänge und der
voraussichtlichen Dateigröße bei den Bitraten des Profils.

Bildnummern erscheinen wie in der Schnittliste: ab dem ersten Videobild gezählt (das erste Bild hat die Nummer 0).
"""
from __future__ import annotations

import os
import re
from fractions import Fraction
from typing import Callable, Iterable, Optional

from cutlist import Segment
from project import format_hms, format_time

HEADERS = ("#", "File", "FileSize", "Source duration", "First", "Last", "Length", "Start time", "End time", "Size", "FPS",
           "Sampling", "KB/s (v)", "KB/s (A)")
RIGHT_ALIGNED = frozenset({0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13})        # alle Spalten außer "File"
NOT_FOUND = "file not found"


def _kbit(text: str) -> Optional[int]:
    m = re.fullmatch(r"(\d+)k", text or "")
    return int(m.group(1)) if m else None


def build_info(segments: Iterable[Segment], profile: dict, number: Callable[[int], str] = lambda n: f"{n:,}",
               size_of: Callable[[str], int] = os.path.getsize, exists: Callable[[str], bool] = os.path.exists) -> tuple[list, str]:
    """(Zeilen, Zusammenfassung). Fehlende Quelldateien werden wie in VB6 gekennzeichnet und nicht mitgezählt."""
    rows: list[list[str]] = []
    total = Fraction(0)
    found = missing = 0
    for i, s in enumerate(segments, 1):
        first = s.first_frame
        row = [f"{i:02d}", s.path]
        if not exists(s.path):
            missing += 1
            rows.append(row + [NOT_FOUND] + [""] * (len(HEADERS) - 3))
            continue
        found += 1
        length = Fraction(s.end - s.start) / s.fps
        rows.append(row + [
            number(size_of(s.path)),
            format_hms(float(Fraction(s.total_frames - first) / s.fps)),
            str(s.start - first), str(s.end - first),
            format_time(length), format_time(total), format_time(total + length),
            f"{s.width}x{s.height}", f"{float(s.fps):.3f}", str(s.sample_rate), str(s.vbitrate_kbit), str(s.abitrate_kbit)])
        total += length
    return rows, summary_text(len(rows), found, missing, total, profile)


def summary_text(count: int, found: int, missing: int, total: Fraction, profile: dict) -> str:
    text = f"{count} segment{'s' if count != 1 else ''}; expected length of the result: {format_time(total)}"
    bv, ba = _kbit(profile.get("bv", "")), _kbit(profile.get("ba", ""))
    if bv and ba and total:
        mib = (bv + ba) * 1000 / 8 * float(total) / 2 ** 20
        text += (f"; expected size ≈ {mib:,.1f} MiB at the profile's {profile['bv']} (video) + {profile['ba']} (audio)")
    if "scale" in profile and "fps" in profile:
        text += f"; target {profile['scale'].replace(':', 'x')}, {profile['fps']} FPS"
    if missing:
        text += f"; {missing} source file{'s' if missing != 1 else ''} not found and not counted"
    return text
