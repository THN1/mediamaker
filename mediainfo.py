"""Media info (VB6: menu Media info, Ctrl+K): properties of a file in sections like "General", "Video #1", "Audio #1".

The report comes from ffprobe (reads only the start and end of the file, quick even over the network). The section "MediaMaker"
shows the values the program works with: start of container and video, the number of the first video frame and, if a
segment is passed, its markers. The text can be copied in the dialog.
"""
from __future__ import annotations

import json
import os
import subprocess
from fractions import Fraction
from typing import Optional

from cutlist import Segment
from ffmpeg_cmd import _start_fraction, stream_times_of
from mediaprobe import first_frame_number

WIDTH = 34


def _kv(label: str, value) -> str:
    return f"{label:<{WIDTH}}: {value}"


def _hms(seconds: Optional[float]) -> str:
    if seconds is None:
        return "unknown"
    ms = int(round(seconds * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d}.{ms % 1000:03d} ({seconds:.3f} s)"


def _num(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rate(text) -> Optional[Fraction]:
    f = _start_fraction(text, Fraction(0))
    return f if f > 0 else None


def _kbps(bits) -> str:
    n = _num(bits)
    return f"{n / 1000:,.0f} kb/s".replace(",", " ") if n else "unknown"


def _size(n: int) -> str:
    return f"{n:,} bytes".replace(",", " ") + f" ({n / 2 ** 20:,.1f} MiB)".replace(",", " ")


def _lang(stream: dict) -> str:
    return stream.get("tags", {}).get("language", "")


def build_sections(path: str, segment: Optional[Segment] = None, ffprobe: str = "ffprobe", first_fn=first_frame_number) -> list:
    """List of (title, text) for the tabs of the dialog."""
    out = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
                         capture_output=True, check=True, stdin=subprocess.DEVNULL).stdout
    data = json.loads(out or b"{}")
    fmt, streams = data.get("format", {}), data.get("streams", [])
    sections = []

    size = os.path.getsize(path) if os.path.exists(path) else _num(fmt.get("size")) or 0
    general = ["General",
               _kv("Complete name", path),
               _kv("Format", f"{fmt.get('format_long_name', '?')} ({fmt.get('format_name', '?')})"),
               _kv("File size", _size(int(size))),
               _kv("Duration", _hms(_num(fmt.get("duration")))),
               _kv("Overall bit rate", _kbps(fmt.get("bit_rate"))),
               _kv("Start time (container)", _hms(_num(fmt.get("start_time")))),
               _kv("Streams", f"{len(streams)} ({sum(s.get('codec_type') == 'video' for s in streams)} video, "
                              f"{sum(s.get('codec_type') == 'audio' for s in streams)} audio)")]
    sections.append(("General", "\n".join(general)))

    counters = {"video": 0, "audio": 0}
    fps_main: Optional[Fraction] = None
    for s in streams:
        kind = s.get("codec_type", "other")
        counters[kind] = counters.get(kind, 0) + 1
        n = counters[kind]
        if kind == "video":
            avg, rfr = _rate(s.get("avg_frame_rate")), _rate(s.get("r_frame_rate"))
            fps_main = fps_main or avg or rfr
            lines = [f"Video #{n}",
                     _kv("Stream index", s.get("index")),
                     _kv("Format", f"{s.get('codec_long_name', s.get('codec_name', '?'))} ({s.get('codec_name', '?')})"),
                     _kv("Profile / level", f"{s.get('profile', '?')} / {s.get('level', '?')}"),
                     _kv("Width x height", f"{s.get('width')} x {s.get('height')}"),
                     _kv("Display aspect ratio", s.get("display_aspect_ratio", "unknown")),
                     _kv("Sample aspect ratio", s.get("sample_aspect_ratio", "unknown")),
                     _kv("Frame rate (average)", f"{float(avg):.3f} fps ({avg})" if avg else "unknown"),
                     _kv("Frame rate (stream)", f"{float(rfr):.3f} fps ({rfr})" if rfr else "unknown"),
                     _kv("Scan type", s.get("field_order", "unknown")),
                     _kv("Pixel format", s.get("pix_fmt", "unknown")),
                     _kv("Bit rate", _kbps(s.get("bit_rate"))),
                     _kv("Start time", _hms(_num(s.get("start_time")))),
                     _kv("Duration", _hms(_num(s.get("duration")))),
                     _kv("Frames (from header)", s.get("nb_frames", "unknown"))]
            sections.append((f"Video #{n}", "\n".join(lines)))
        elif kind == "audio":
            lines = [f"Audio #{n}",
                     _kv("Stream index", s.get("index")),
                     _kv("Format", f"{s.get('codec_long_name', s.get('codec_name', '?'))} ({s.get('codec_name', '?')})"),
                     _kv("Channels", f"{s.get('channels', '?')} ({s.get('channel_layout', '?')})"),
                     _kv("Sampling rate", f"{s.get('sample_rate', '?')} Hz"),
                     _kv("Bit rate", _kbps(s.get("bit_rate"))),
                     _kv("Language", _lang(s) or "unknown"),
                     _kv("Start time", _hms(_num(s.get("start_time")))),
                     _kv("Duration", _hms(_num(s.get("duration"))))]
            sections.append((f"Audio #{n}" + (f" ({_lang(s)})" if _lang(s) else ""), "\n".join(lines)))
        else:
            lines = [f"{kind.capitalize()} #{n}",
                     _kv("Stream index", s.get("index")),
                     _kv("Format", s.get("codec_name", "unknown")),
                     _kv("Language", _lang(s) or "unknown")]
            sections.append((f"{kind.capitalize()} #{n}", "\n".join(lines)))

    sections.append(("MediaMaker", _mediamaker_section(path, streams, fps_main, segment, first_fn)))
    return sections


def _mediamaker_section(path: str, streams: list, fps: Optional[Fraction], seg: Optional[Segment], first_fn) -> str:
    lines = ["MediaMaker: values used for the frame numbers", "",
             "Frame numbers are counted from the first decodable video frame (number 0).",
             "Internally a frame is the picture at (container start + (first frame offset + n) / frame rate)."]
    try:
        container, video = stream_times_of(path)
    except Exception as e:
        return "\n".join(lines + ["", _kv("Start times", f"not available ({e})")])
    lines += ["",
              _kv("Container start", f"{float(container):.6f} s"),
              _kv("Video start", f"{float(video):.6f} s")]
    for n, s in enumerate((s for s in streams if s.get("codec_type") == "audio"), 1):
        start = _num(s.get("start_time"))
        if start is not None:
            lines.append(_kv(f"Audio #{n} start", f"{start:.6f} s ({(start - float(container)) * float(fps or 25):+.1f} frames vs. container start)"))
    if fps:
        lines.append(_kv("Video start in frames", f"{float(video - container) * float(fps):.2f}"))
        try:
            lines.append(_kv("First video frame offset", first_fn(path, fps)))
        except Exception as e:
            lines.append(_kv("First video frame offset", f"not available ({e})"))
    else:
        lines.append(_kv("Frame rate", "unknown"))
    if seg is not None:
        f0 = seg.first_frame
        both = lambda n: f"{n - f0}  (absolute: {n})" if f0 else f"{n}"
        lines += ["", "Selected segment (frame numbers are counted from the first video frame = 0):",
                  _kv("Offset of the first video frame", f"{f0} frames after the container start"),
                  _kv("Marker A (start)", both(seg.start)),
                  _kv("Marker B (end, exclusive)", both(seg.end)),
                  _kv("Frames in the segment", seg.end - seg.start),
                  _kv("Number of frames in the video", f"{seg.total_frames - f0}"),
                  _kv("Frame rate", f"{float(seg.fps):.3f} fps ({seg.fps})"),
                  _kv("Size", f"{seg.width} x {seg.height}"),
                  _kv("Crop top/bottom/left/right", f"{seg.crop_top}/{seg.crop_bottom}/{seg.crop_left}/{seg.crop_right}"),
                  _kv("Logo mask / area", "none" if not seg.mask else ("PNG mask" if seg.has_png_mask else seg.mask))]
    return "\n".join(lines)


def full_text(sections: list) -> str:
    return "\n\n".join(text for _, text in sections)
