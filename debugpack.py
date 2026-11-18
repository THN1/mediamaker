"""Debug package (menu Deploy => Create debug package): everything that is needed to understand why a search for a commercial (or a cut) went
wrong, in a folder `debug/<time>` next to the INI file and as a zip file of the same name that can be uploaded.

Contents: README.txt, segment.json (cut values, neighbours, times), delogo.json (the rectangle or the RemoveLogo mask), reference_logo.json and
reference_logo_edges.png, last_search.json (what the last search did: method, crop, every frame it looked at, the result), options.txt, versions.txt,
list.json (the whole segment list), frame_at_slider.png and logo_area_at_slider.png, the end of the debug log, and an unchanged piece of the
recording (ffmpeg -c copy) from 50 s before to 10 s after the slider position (where the search stopped), with clip_info.txt telling where the
slider, the markers and the place where the reference logo was created are inside the piece.
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

CLIP_BEFORE = 50.0              # seconds before the slider position
CLIP_AFTER = 10.0               # seconds after the slider position


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


def image_array(image) -> Optional[np.ndarray]:
    """RGB array (height, width, 3) from a QImage or an array; None if that is not possible."""
    if image is None:
        return None
    if isinstance(image, np.ndarray):
        return image
    try:
        from PySide6 import QtGui
        converted = image.convertToFormat(QtGui.QImage.Format.Format_RGB888)
        width, height, per_line = converted.width(), converted.height(), converted.bytesPerLine()
        raw = np.frombuffer(converted.constBits(), np.uint8, count=height * per_line).reshape(height, per_line)
        return raw[:, :width * 3].reshape(height, width, 3).copy()
    except Exception:
        return None


def small_grey(rgb: np.ndarray, size: tuple = (64, 48)) -> np.ndarray:
    """Small grey picture without the mean brightness (to compare pictures that differ in colour handling and scale)."""
    from PIL import Image
    grey = np.asarray(Image.fromarray(rgb).convert("L").resize(size, Image.BILINEAR), np.float32)
    return grey - grey.mean()


def preview_offset(preview_rgb: np.ndarray, frames: dict, centre: int, radius: int = 40) -> dict:
    """Which frame of `frames` (number -> small RGB picture, as ffmpeg delivers them) does the picture of the preview show? Compares with the frames
    centre-radius..centre+radius; `best_offset` is the number of frames the preview is AHEAD of the frame number (positive: the preview shows a
    LATER picture than ffmpeg does for that frame number)."""
    mine = small_grey(preview_rgb)
    diffs = {n - centre: float(np.abs(small_grey(f) - mine).mean()) for n, f in frames.items() if abs(n - centre) <= radius}
    if not diffs:
        return {"result": "no frames to compare"}
    best = min(diffs, key=diffs.get)
    others = sorted(v for k, v in diffs.items() if k != best)
    return {"best_offset_frames": best, "best_difference": round(diffs[best], 2), "difference_at_0": round(diffs.get(0, float("nan")), 2),
            "second_best_difference": round(others[0], 2) if others else None,
            "meaning": ("the preview shows the picture of frame number + %d (ffmpeg numbering)" % best) if best else "preview and ffmpeg agree on this frame number",
            "reliable": bool(others and diffs[best] < 0.6 * others[0])}


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


def clip_window(centre: float, before: Optional[float] = None, after: Optional[float] = None) -> tuple:
    """(start, duration, position of the centre inside the piece) in seconds, from the start of the recording; the piece does not begin before 0."""
    before = CLIP_BEFORE if before is None else before
    after = CLIP_AFTER if after is None else after
    start = max(0.0, centre - before)
    return start, centre + after - start, centre - start


def clip_command(path: str, start: float, duration: float, out: str, ffmpeg: str = "ffmpeg") -> list:
    """Unchanged piece: no re-encoding (-c copy), all video and audio streams."""
    return [ffmpeg, "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", path, "-t", f"{duration:.3f}", "-map", "0:v", "-map", "0:a?", "-c", "copy", out]


def versions_text(version: str, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe", commit: str = "") -> str:
    def first_line(cmd):
        try:
            out = subprocess.run([cmd, "-version"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
            return out.splitlines()[0] if out else "(no answer)"
        except OSError:
            return "(not found)"
    lines = [f"MediaMaker {version}"] + ([f"Commit {commit}"] if commit else []) + [f"Python {sys.version.split()[0]} on {platform.platform()}", first_line(ffmpeg), first_line(ffprobe)]
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
  reference_logo.json     the reference logo: rectangle, number of edge pixels, and at which frame (button L) it was created
  reference_logo_edges.png  its edge picture (white = edge), enlarged
  reference_logo_frame.png  the picture that the button L took the reference logo from (ffmpeg, whole frame, the rectangle marked)
  reference_logo_area.png   the area of the logo in that picture, enlarged
  reference_logo_vlc_preview.png   what the preview showed when L was pressed (if available) - compare with reference_logo_frame.png
  preview_check.json      which frame number the picture of the preview really belongs to (offset between VLC and ffmpeg numbering)
  vlc_preview.png         what the preview shows at the moment the package is made
  last_save.json          (only after a save in DVD mode) what the last save did: the ffmpeg command, its messages (warnings like "Non-monotonous DTS" are in them), the frames expected and
                          written, the segments, and the streams of the file that was written (start time and length of the picture and the sound)
  last_search.json        what the last "Seek next commercial" / "Seek end of commercial" did: method (crop or reference logo), start, every frame
                          that was looked at with its value, and the result
  options.txt, versions.txt, list.json   settings, program and tool versions, the whole segment list
  frame_at_slider.png, logo_area_at_slider.png   the picture (ffmpeg) at the position of the slider when the package is made, and the area of the
                          logo in it - NOT the picture of the reference logo (that is reference_logo_frame.png)
  debug_log_tail.txt      the end of mediamaker_debug.log (only with MEDIAMAKER_DEBUG=1)
  dvd_*.vob, dvd_info.json   (DVD mode only) unchanged pieces of the VOB files, cut by BYTES (a DVD time stamp jumps, a cut by time cannot be trusted): around the slider,
                          around every jump of the time stamps of the file, and the end of every part together with the beginning of the next one (the seam);
                          dvd_info.json says which bytes and pictures they are, lists the jumps and the languages read from the IFO file, which is in the package too (VTS_nn_0.IFO; the list of subtitles of the last save is in last_save.json: subtitle_lists)
  clip.*, clip_info.txt   an unchanged piece of the recording (ffmpeg -c copy) from {before:.0f} s before to {after:.0f} s after the slider position
                          (= frame_at_slider.png, where the search stopped); clip_info.txt says where the slider, marker A and B and the place
                          where the reference logo was created are inside the piece

Please upload the zip file and describe what went wrong (for example: the end of the commercial was found too early / too late, at about ...).
"""


# ----------------------------------------------------------------------------- DVD: unchanged pieces of the files (bytes, not times: time stamps jump in a VOB file)
BYTES_AROUND = 3 * 1024 * 1024           # the piece around the slider and around a jump: this many bytes before and behind
BYTES_AT_SEAM = 6 * 1024 * 1024          # the end of a part and the beginning of the next
MAX_JUMPS = 3                            # of one file


def byte_window(centre: int, size: int, before: int = BYTES_AROUND, after: int = BYTES_AROUND, sector: int = 2048) -> tuple:
    """(start, length) in bytes of a piece around `centre` in a file of `size` bytes, from a sector border to a sector border (the start is a pack header)."""
    start = max(0, (centre - before) // sector * sector)
    end = min(size, -(-(centre + after) // sector) * sector)
    return start, end - start


def copy_bytes(path: str, start: int, length: int, out: str, block: int = 1 << 20) -> int:
    """Writes `length` bytes of `path` from `start` into `out` (like dd); returns the number written."""
    done = 0
    with open(path, "rb") as src, open(out, "wb") as dst:
        src.seek(start)
        while done < length:
            data = src.read(min(block, length - done))
            if not data:
                break
            dst.write(data)
            done += len(data)
    return done
