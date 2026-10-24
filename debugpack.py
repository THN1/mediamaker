"""Debug package (menu Deploy => Create debug package): everything that is needed to understand why a search for a commercial (or a cut) went
wrong, in a folder `debug/<time>` next to the INI file and as a zip file of the same name that can be uploaded.

Contents: README.txt, segment.json (cut values, neighbours, times), delogo.json (the rectangle or the RemoveLogo mask), reference_logo.json and
reference_logo_edges.png, last_search.json (what the last search did: method, crop, every frame it looked at, the result), options.txt, versions.txt,
list.json (the whole segment list), frame_at_slider.png and logo_area_at_slider.png, the end of the debug log, and an unchanged piece of the
recording (ffmpeg -c copy) from 50 s before to 10 s after marker B, with clip_info.txt telling where the markers are inside the piece.
"""
from __future__ import annotations

import dataclasses
import json
import os
import platform
import subprocess
import sys
import zipfile
from fractions import Fraction
from typing import Optional

import numpy as np

CLIP_BEFORE = 50.0              # seconds before marker B
CLIP_AFTER = 10.0               # seconds after marker B


def hms(seconds: float) -> str:
    h, rest = divmod(max(0.0, float(seconds)), 3600)
    m, s = divmod(rest, 60)
    return f"{int(h)}:{int(m):02d}:{s:06.3f}"


def _plain(value):
    """JSON-capable form of a value (Fractions become text)."""
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def write_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_plain(data), f, indent=2, ensure_ascii=False)


def write_png(path: str, array: np.ndarray, scale: int = 1) -> None:
    from PIL import Image
    if array.dtype == bool:
        array = array.astype(np.uint8) * 255
    image = Image.fromarray(array)
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.NEAREST)
    image.save(path)


def segment_report(segments: list, index: int, slider: int, to_time) -> dict:
    """Cut values of the segment `index` (0-based): the numbers as the program counts them (from the container start) and as it shows them (from
    the first decodable picture), the times, and the neighbours. `to_time(frame)` gives the time in seconds from the start of the recording."""
    seg = segments[index]
    first = seg.first_frame
    raw = dataclasses.asdict(seg)
    if seg.mask and not seg.mask.split()[0].replace(".", "").replace(",", "").isdigit():
        raw["mask"] = f"<PNG mask, {len(seg.mask)} characters of base64; see removelogo_mask.png>"
    shown = lambda n: n - first
    def line(s):
        return {"start": s.start, "end": s.end, "start_shown": s.start - s.first_frame, "end_shown": s.end - s.first_frame, "path": s.path}
    return {
        "segment": _plain(raw),
        "numbers": {"first_frame": first, "total_frames": seg.total_frames, "marker_A_start": seg.start, "marker_B_end": seg.end,
                    "marker_A_shown": shown(seg.start), "marker_B_shown": shown(seg.end), "frames_in_segment": seg.end - seg.start,
                    "slider": slider, "slider_shown": shown(slider), "fps": str(seg.fps)},
        "times_from_recording_start": {"marker_A": hms(to_time(seg.start)), "marker_B": hms(to_time(seg.end)), "slider": hms(to_time(slider)),
                                       "first_frame": hms(to_time(first)), "end_of_file": hms(to_time(seg.total_frames))},
        "previous": line(segments[index - 1]) if index > 0 else None,
        "next": line(segments[index + 1]) if index + 1 < len(segments) else None,
        "segments_in_list": len(segments),
    }


def clip_window(b_seconds: float, before: float = CLIP_BEFORE, after: float = CLIP_AFTER) -> tuple:
    """(start, duration, position of B inside the piece) in seconds, from the start of the recording; the piece does not begin before 0."""
    start = max(0.0, b_seconds - before)
    return start, b_seconds + after - start, b_seconds - start


def clip_command(path: str, start: float, duration: float, out: str, ffmpeg: str = "ffmpeg") -> list:
    """Unchanged piece: no re-encoding (-c copy), all video and audio streams."""
    return [ffmpeg, "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", path, "-t", f"{duration:.3f}", "-map", "0:v", "-map", "0:a?", "-c", "copy", out]


def versions_text(version: str, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> str:
    def first_line(cmd):
        try:
            out = subprocess.run([cmd, "-version"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
            return out.splitlines()[0] if out else "(no answer)"
        except OSError:
            return "(not found)"
    lines = [f"MediaMaker {version}", f"Python {sys.version.split()[0]} on {platform.platform()}", first_line(ffmpeg), first_line(ffprobe)]
    try:
        import PySide6
        lines.append(f"PySide6 {PySide6.__version__}")
    except Exception:
        lines.append("PySide6: (not available)")
    try:
        import vlc
        lines.append(f"python-vlc {getattr(vlc, '__version__', '?')}, libvlc {vlc.libvlc_get_version().decode(errors='replace')}")
    except Exception:
        lines.append("python-vlc / libvlc: (not available)")
    return "\n".join(lines) + "\n"


def tail(path: str, lines: int = 300) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""


def make_zip(folder: str, zip_path: str) -> str:
    """All files of the folder in one zip file (written under a temporary name first)."""
    part = zip_path + ".part"
    try:
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            base = os.path.basename(folder)
            for root, _, files in os.walk(folder):
                for name in sorted(files):
                    full = os.path.join(root, name)
                    z.write(full, os.path.join(base, os.path.relpath(full, folder)))
        os.replace(part, zip_path)
    finally:
        if os.path.exists(part):
            os.remove(part)
    return zip_path


README = """MediaMaker debug package, {stamp}

What is in here
  segment.json            cut values of the selected segment (the numbers as the program counts them and as it shows them), times, neighbours
  delogo.json             the DeLogo rectangle (fractions and pixels) or the RemoveLogo mask
  removelogo_mask.png     the mask of the RemoveLogo filter (only if the segment has one)
  reference_logo.json     the reference logo: rectangle, number of edge pixels
  reference_logo_edges.png  its edge picture (white = edge), enlarged
  last_search.json        what the last "Seek next commercial" / "Seek end of commercial" did: method (crop or reference logo), start, every frame
                          that was looked at with its value, and the result
  options.txt, versions.txt, list.json   settings, program and tool versions, the whole segment list
  frame_at_slider.png, logo_area_at_slider.png   the picture at the position of the slider and the area of the logo in it
  debug_log_tail.txt      the end of mediamaker_debug.log (only with MEDIAMAKER_DEBUG=1)
  clip.*, clip_info.txt   an unchanged piece of the recording (ffmpeg -c copy) from {before:.0f} s before to {after:.0f} s after marker B;
                          clip_info.txt says where marker A and B are inside the piece

Please upload the zip file and describe what went wrong (for example: the end of the commercial was found too early / too late, at about ...).
"""
