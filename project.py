"""Saving and loading the segment list.

The list is stored as a JSON file (named fields, no more column numbers like SubItems(18)). Old CSV files
from the VB6 version (and the comment lines "C=" of the batch files) can still be loaded.
"""
from __future__ import annotations

import json
import os
from fractions import Fraction

from cutlist import Segment, parse_segments, snap_fps

FORMAT = "mediamaker-segments"
VERSION = 1


def segment_to_dict(s: Segment) -> dict:
    return {
        "path": s.path, "title": s.name, "start": s.start, "end": s.end, "total_frames": s.total_frames,
        "fps": f"{s.fps.numerator}/{s.fps.denominator}", "width": s.width, "height": s.height,
        "video_kbit": s.vbitrate_kbit, "audio_kbit": s.abitrate_kbit, "audio_stream": s.audio_sel,
        "crop": [s.crop_top, s.crop_bottom, s.crop_left, s.crop_right], "sample_rate": s.sample_rate, "mask": s.mask,
        "first_frame": s.first_frame,
    }


def segment_from_dict(d: dict, index: int) -> Segment:
    top, bottom, left, right = d.get("crop", [0, 0, 0, 0])
    return Segment(
        index=index, path=d["path"], name=d.get("title") or os.path.basename(d["path"].replace("\\", "/")),
        start=int(d["start"]), end=int(d["end"]), total_frames=int(d["total_frames"]),
        fps=Fraction(d["fps"]), width=int(d["width"]), height=int(d["height"]),
        vbitrate_kbit=int(d.get("video_kbit", 0)), abitrate_kbit=int(d.get("audio_kbit", 0)),
        audio_sel=d.get("audio_stream", "a"), crop_top=int(top), crop_bottom=int(bottom), crop_left=int(left),
        crop_right=int(right), sample_rate=int(d.get("sample_rate", 0)), mask=d.get("mask", ""),
        first_frame=int(d.get("first_frame", 0)))


def save_segments(path: str, segments: list[Segment]) -> None:
    data = {"format": FORMAT, "version": VERSION, "segments": [segment_to_dict(s) for s in segments]}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)                                    # either completely new or unchanged


def _read_text(path: str) -> str:
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def load_segments(path: str) -> list[Segment]:
    """Loads a .json file or an old VB6 .csv file. If the file does not exist the list is empty."""
    if not os.path.exists(path):
        return []
    text = _read_text(path)
    if text.lstrip().startswith("{"):
        data = json.loads(text)
        if data.get("format") != FORMAT:
            raise ValueError(f"{path}: not a MediaMaker segment list")
        return [segment_from_dict(d, i) for i, d in enumerate(data.get("segments", []), 1)]
    return parse_segments(text)                              # old CSV file


# ----------------------------------------------------------------------------- Display
def format_hms(seconds: float) -> str:
    """3725.4 -> '01:02:05' (hours may exceed 24)."""
    s = int(seconds + 0.5)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def format_time(seconds: Fraction) -> str:
    """Seconds (exact as a fraction) -> 'HH:MM:SS.mmm' (rounded to milliseconds)."""
    ms = int(Fraction(seconds) * 1000 + Fraction(1, 2))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}.{ms % 1000:03d}"


def timeof(frames: int, fps: Fraction) -> str:
    """Frame number -> 'HH:MM:SS.mmm'."""
    return format_time(Fraction(frames) / fps)


def segment_row(s: Segment, number: int) -> list[str]:
    """The 19 columns of the list in the order of VB6 (#, Path, Title, First, Last, Duration, Frames, FPS, ...).

        Frame numbers are counted from the first decodable video frame (the first frame has the number 0). Internally and in the
        JSON file the numbers count from the start of the container; the difference is `first_frame` (0 for lists from VB6)."""
    first = s.first_frame
    return [f"{number:02d}", s.path, s.name, str(s.start - first), str(s.end - first), format_hms(s.frames / float(s.fps)),
            str(s.total_frames - first), f"{float(s.fps):.3f}", str(s.width), str(s.height), str(s.vbitrate_kbit),
            str(s.abitrate_kbit), s.audio_sel, str(s.crop_top), str(s.crop_bottom), str(s.crop_left),
            str(s.crop_right), str(s.sample_rate), s.mask]
