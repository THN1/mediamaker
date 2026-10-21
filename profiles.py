"""Profil (Zieldatei) und Optionen: Prüfung der Werte, Vorgaben und Berechnungen.

Reine Logik ohne Oberfläche, damit sie sich testen lässt. Das Profil beschreibt die Ausgabedatei (Bildgröße, Bildrate,
Bitraten, Tonformat), die Optionen steuern das Verhalten des Programms (Beschnitt, Suche, Tonspur, ...).
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from cutlist import Segment

PROFILE_KEYS = ("description", "scale", "sws_flags", "pad", "fps", "bv", "acodec_in", "acodec_out", "ar", "ba")
REQUIRED_PROFILE_KEYS = ("scale", "sws_flags", "fps", "bv", "acodec_in", "acodec_out", "ar", "ba")

# Vorschläge für die Auswahlfelder im Bearbeiten-Dialog (in VB6 gab es nur die Bildraten)
PRESETS = {
    "fps": ["23.976", "24.000", "24.975", "25.000", "29.970", "30.000"],
    "sws_flags": ["lanczos", "bicubic", "bilinear", "spline", "neighbor", "area"],
    "ar": ["44100", "48000"],
    "acodec_in": ["mp2", "ac3", "aac", "mp3", "eac3", "dts"],
    "acodec_out": ["aac", "ac3", "mp3"],
    "pad": ["False", "True"],
    "multilanguage": ["False", "True"],
}


def ordered_profile(p: dict) -> dict:
    """Profil mit `pad` (Vorgabe False) in der Reihenfolge von PROFILE_KEYS; unbekannte Schlüssel folgen am Ende."""
    q = {"pad": "False", **p}
    ordered = {k: q[k] for k in PROFILE_KEYS if k in q}
    ordered.update({k: v for k, v in q.items() if k not in ordered})
    return ordered


def validate_profile(p: dict) -> list[str]:
    """Liste verständlicher Fehlermeldungen; leer = in Ordnung."""
    errors = []
    if "pad" in p and p["pad"] not in ("True", "False"):
        errors.append('"pad" must be True or False.')
    for key in REQUIRED_PROFILE_KEYS:
        if not p.get(key, "").strip():
            errors.append(f'"{key}" must not be empty.')
    scale = p.get("scale", "")
    m = re.fullmatch(r"(\d+):(\d+)", scale)
    if scale and not m:
        errors.append('"scale" must have the format width:height, for example 720:576.')
    elif m and (int(m.group(1)) % 2 or int(m.group(2)) % 2 or 0 in (int(m.group(1)), int(m.group(2)))):
        errors.append('"scale": width and height must be even numbers greater than zero (required by the video encoder).')
    if p.get("fps") and (not re.fullmatch(r"\d{2}\.\d{3}", p["fps"]) or float(p["fps"]) <= 0):
        errors.append('"fps" must have exactly the format ##.### (for example 25.000 or 29.970).')
    for key in ("bv", "ba"):
        if p.get(key) and not re.fullmatch(r"[1-9]\d*k", p[key]):
            errors.append(f'"{key}" must be a number followed by "k" (for example 3072k).')
    if p.get("ar") and not re.fullmatch(r"[1-9]\d{3,5}", p["ar"]):
        errors.append('"ar" must be a sampling rate such as 44100 or 48000.')
    return errors


def _int(value: str) -> Optional[int]:
    return int(value) if re.fullmatch(r"\d+", value or "") else None


def _float(value: str) -> Optional[float]:
    return float(value) if re.fullmatch(r"\d+(\.\d+)?", value or "") else None


# Optionen, die nicht (mehr) im Dialog erscheinen:
REMOVED_OPTIONS = {"focus", "pad"}            # focus: ohne Wirkung; pad: gehört jetzt zum Profil
HIDDEN_OPTIONS = {"logo_edge", "logo_conf"}   # nur für Fortgeschrittene, stehen nur in der INI-Datei

# Gliederung des Optionsdialogs: (Überschrift, Schlüssel)
OPTION_GROUPS = (
    ("Border detection", ("crop", "blackness", "allowance", "border_tol")),
    ("Seeking commercials", ("pause", "overlap", "step_end", "step_next", "logo_rewind")),
    ("Audio and subtitles", ("audio", "multilanguage", "subtitle", "aflags")),
    ("Technical", ("floor", "detect")),
)


def validate_options(o: dict) -> list[str]:
    errors = []
    ranges = {"crop": (0, 288), "floor": (0, 60), "blackness": (0, 255), "allowance": (0, 10 ** 7), "overlap": (0, 10 ** 6),
              "audio": (1, 99), "pause": (0, 10 ** 5), "detect": (0, 10 ** 8), "step_end": (1, 3600), "step_next": (1, 36000),
              "border_tol": (0, 50), "logo_edge": (1, 255)}
    for key, (lo, hi) in ranges.items():
        if key in o:
            v = _int(o[key])
            if v is None or not lo <= v <= hi:
                errors.append(f'"{key}" must be a whole number between {lo} and {hi}.')
    for key, (lo, hi) in {"logo_rewind": (0, 600), "logo_conf": (0, 1)}.items():
        if key in o:
            v = _float(o[key])
            if v is None or not lo <= v <= hi:
                errors.append(f'"{key}" must be a number between {lo} and {hi} (decimal point, e.g. 1.8).')
    if "multilanguage" in o and o["multilanguage"] not in ("True", "False"):
        errors.append('"multilanguage" must be True or False.')
    if "subtitle" in o and not re.fullmatch(r"0|\d+(,\d+)*", o["subtitle"]):
        errors.append('"subtitle" must be 0 (off) or a list of track numbers separated by commas.')
    return errors


def valid_profile_name(name: str) -> Optional[str]:
    """None = in Ordnung, sonst die Fehlermeldung."""
    if not name.strip():
        return "The name must not be empty."
    if "=" in name or name.strip().startswith(("[", ";")) or "\n" in name:
        return 'The name must not contain "=" or line breaks and must not begin with "[" or ";".'
    return None


def default_name(profile: dict) -> str:
    return profile.get("description", "").replace(" ", "_")


def profile_from_segment(seg: Segment) -> dict:
    """Werte der Zieldatei aus den Eigenschaften eines Mustervideos (VB6: 'Reuse source A/V')."""
    return {"bv": f"{seg.vbitrate_kbit}k", "scale": f"{seg.width}:{seg.height}", "fps": f"{float(seg.fps):.3f}",
            "ar": str(seg.sample_rate), "ba": f"{seg.abitrate_kbit}k"}


def weighted_bitrate(segments: Iterable[Segment], kind: str) -> int:
    """Mittlere Bitrate in kbit/s, gewichtet mit der Dauer der Segmente (kind = "video" oder "audio")."""
    total = weighted = 0.0
    for s in segments:
        t = s.frames / float(s.fps)
        total += t
        weighted += t * (s.vbitrate_kbit if kind == "video" else s.abitrate_kbit)
    return round(weighted / total) if total else 0


def normalize_bitrate(text: str) -> Optional[str]:
    """'3000' -> '3000k', '3000k' -> '3000k', Unsinn -> None."""
    t = text.strip()
    t = t[:-1] if t.endswith("k") else t
    return f"{int(t)}k" if re.fullmatch(r"[1-9]\d*", t) else None


def wrapped_lines(text_width: int, field_width: int, min_lines: int = 1, max_lines: int = 4) -> int:
    """Anzahl der Zeilen, die ein Text der Breite `text_width` (Pixel) in einem Feld der Breite `field_width` braucht,
    begrenzt auf min_lines..max_lines (wie die Höhenberechnung von frmProfile in VB6)."""
    usable = max(field_width - 12, 1)                      # Rand und Rollbalken abziehen
    return max(min_lines, min(max_lines, -(-text_width // usable)))
