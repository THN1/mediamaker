"""Profile (target file) and options: checking of values, defaults and calculations.

Pure logic without a user interface so that it can be tested. The profile describes the output file (picture size, frame rate,
bit rates, audio format), the options control the behaviour of the program (crop, search, audio track, ...).
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from cutlist import Segment

PROFILE_KEYS = ("description", "scale", "sws_flags", "pad", "fps", "bv", "acodec_in", "acodec_out", "ar", "ba")
REQUIRED_PROFILE_KEYS = ("scale", "sws_flags", "fps", "bv", "acodec_in", "acodec_out", "ar", "ba")

# suggestions for the selection fields in the edit dialog (VB6 only had the frame rates)
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
    """Profile with `pad` (default False) in the order of PROFILE_KEYS; unknown keys follow at the end."""
    q = {"pad": "False", **p}
    ordered = {k: q[k] for k in PROFILE_KEYS if k in q}
    ordered.update({k: v for k, v in q.items() if k not in ordered})
    return ordered


def validate_profile(p: dict) -> list[str]:
    """List of understandable error messages; empty = OK."""
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


# options that no longer appear in the dialog:
REMOVED_OPTIONS = {"focus", "pad"}            # focus: no effect; pad: now belongs to the profile
HIDDEN_OPTIONS = {"logo_edge", "logo_conf", "cut_diff"}   # for advanced users only, they are only in the INI file

# grouping of the options dialog: (heading, keys)
OPTION_GROUPS = (
    ("Border detection", ("crop", "blackness", "allowance", "border_tol")),
    ("Seeking commercials", ("pause", "overlap", "step_end", "step_next", "cut_window", "logo_rewind")),
    ("Audio and subtitles", ("audio", "multilanguage", "subtitle", "aflags")),
    ("Batch file", ("path_map",)),
    ("Technical", ("floor", "detect")),
)


def validate_options(o: dict) -> list[str]:
    errors = []
    ranges = {"crop": (0, 288), "floor": (0, 60), "blackness": (0, 255), "allowance": (0, 10 ** 7), "overlap": (0, 10 ** 6),
              "audio": (1, 99), "pause": (0, 10 ** 5), "detect": (0, 10 ** 8), "step_end": (1, 3600), "step_next": (1, 36000),
              "border_tol": (0, 50), "logo_edge": (1, 255), "cut_window": (0, 50), "cut_diff": (1, 255)}
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
    for part in [p for p in o.get("path_map", "").split(";") if p.strip()]:
        source, equals, target = part.partition("=")
        if not equals or not source.strip() or not target.strip():
            errors.append('"path_map" must be a list of source=target pairs separated by semicolons.')
            break
    if "multilanguage" in o and o["multilanguage"] not in ("True", "False"):
        errors.append('"multilanguage" must be True or False.')
    if "subtitle" in o and not re.fullmatch(r"0|\d+(,\d+)*", o["subtitle"]):
        errors.append('"subtitle" must be 0 (off) or a list of track numbers separated by commas.')
    return errors


def valid_profile_name(name: str) -> Optional[str]:
    """None = OK, otherwise the error message."""
    if not name.strip():
        return "The name must not be empty."
    if "=" in name or name.strip().startswith(("[", ";")) or "\n" in name:
        return 'The name must not contain "=" or line breaks and must not begin with "[" or ";".'
    return None


def default_name(profile: dict) -> str:
    return profile.get("description", "").replace(" ", "_")


def profile_from_segment(seg: Segment) -> dict:
    """Values of the target file from the properties of a sample video (VB6: 'Reuse source A/V')."""
    return {"bv": f"{seg.vbitrate_kbit}k", "scale": f"{seg.width}:{seg.height}", "fps": f"{float(seg.fps):.3f}",
            "ar": str(seg.sample_rate), "ba": f"{seg.abitrate_kbit}k"}


def weighted_bitrate(segments: Iterable[Segment], kind: str) -> int:
    """Average bit rate in kbit/s, weighted by the duration of the segments (kind = "video" or "audio")."""
    total = weighted = 0.0
    for s in segments:
        t = s.frames / float(s.fps)
        total += t
        weighted += t * (s.vbitrate_kbit if kind == "video" else s.abitrate_kbit)
    return round(weighted / total) if total else 0


def normalize_bitrate(text: str) -> Optional[str]:
    """'3000' -> '3000k', '3000k' -> '3000k', nonsense -> None."""
    t = text.strip()
    t = t[:-1] if t.endswith("k") else t
    return f"{int(t)}k" if re.fullmatch(r"[1-9]\d*", t) else None


def wrapped_lines(text_width: int, field_width: int, min_lines: int = 1, max_lines: int = 4) -> int:
    """Number of lines a text of width `text_width` (pixels) needs in a field of width `field_width`,
        limited to min_lines..max_lines (like the height calculation of frmProfile in VB6)."""
    usable = max(field_width - 12, 1)                      # subtract border and scroll bar
    return max(min_lines, min(max_lines, -(-text_width // usable)))
