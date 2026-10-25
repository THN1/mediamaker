"""Fetch a single frame from a recording (port of oneframe() without a temporary BMP file).

Addressing: frame n is the picture at the time  video start + n / fps  (origin="video"),
container start + n / fps (origin="container", default) or following the pattern of VB6 (origin="vb6", see
origin_base()). The jump with -ss is only an acceleration;
the target frame is determined with absolute timestamps (-copyts + trim). The result therefore does not depend
on how the respective ffmpeg version treats -ss and start times (see check_seek.py).
"""
from __future__ import annotations

import io
import re
import subprocess
from fractions import Fraction
from math import floor

import numpy as np
from PIL import Image

from ffmpeg_cmd import fmt_seconds, origin_base, stream_times_of


stream_times = stream_times_of      # name for older callers


def frame_time(frame: int, fps: Fraction, times: tuple[Fraction, Fraction], origin: str = "container",
               preroll: int = 2) -> Fraction:
    """Absolute timestamp (seconds, truncated to milliseconds) of frame `frame`."""
    t = origin_base(frame, fps, times[0], times[1], origin, preroll) + Fraction(frame) / fps
    return Fraction(floor(t * 1000), 1000)


def seek_before(target: Fraction, container_start: Fraction, preroll: int) -> int:
    """Whole seconds for -ss (relative to the container start), `preroll` seconds before the target."""
    return max(0, floor(target - container_start) - preroll)


def grab_frame(path: str, frame: int, fps: Fraction, preroll: int = 2, ffmpeg: str = "ffmpeg",
               origin: str = "container") -> np.ndarray:
    """Returns frame `frame` as an RGB array (height x width x 3, row 0 = TOP edge of the picture)."""
    times = stream_times_of(path)
    t = frame_time(frame, fps, times, origin, preroll)
    d = seek_before(t, times[0], preroll)
    cmd = [ffmpeg, "-v", "error", "-hide_banner", "-copyts"]
    if d > 0:
        cmd += ["-ss", str(d)]
    cmd += ["-i", path, "-filter_complex", f"[0:v]trim=start={fmt_seconds(t)},setpts=PTS-STARTPTS[v]",
            "-frames:v", "1", "-map", "[v]", "-f", "image2pipe", "-c:v", "png", "-"]
    res = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    if res.returncode != 0 or not res.stdout:
        raise RuntimeError(f"Frame {frame} could not be read: {res.stderr.decode(errors='replace')[-300:]}")
    return np.asarray(Image.open(io.BytesIO(res.stdout)).convert("RGB"))


def grab_window(path: str, first: int, count: int, fps: Fraction, size: tuple[int, int] = (180, 144),
                preroll: int = 2, ffmpeg: str = "ffmpeg", origin: str = "container") -> tuple[int, np.ndarray]:
    """Fetches `count` consecutive frames starting at frame `first` in one call, reduced to `size`.

        Returns: (number of the first frame delivered, array count x height x width x 3). If the window begins before
        the start of the file, it starts at frame 0; at the end of the file fewer frames may be returned.
    """
    first = max(0, first)
    times = stream_times_of(path)
    t = frame_time(first, fps, times, origin, preroll)
    d = seek_before(t, times[0], preroll)
    w, h = size
    cmd = [ffmpeg, "-v", "error", "-hide_banner", "-copyts"] + (["-ss", str(d)] if d > 0 else []) + [
        "-i", path, "-filter_complex", f"[0:v]trim=start={fmt_seconds(t)},setpts=PTS-STARTPTS,scale={w}:{h}:flags=area[v]",
        "-frames:v", str(count), "-map", "[v]", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    res = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    n = len(res.stdout) // (w * h * 3)
    return first, np.frombuffer(res.stdout[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def _decode_numbered(path: str, first: int, count: int, fps: Fraction, tail: str, shape: tuple, preroll: int = 2,
                     ffmpeg: str = "ffmpeg", on_start=None) -> dict:
    """The common part of grab_numbered and grab_scanlines: decodes up to `count` consecutive frames from frame `first` on, applies the
    filters `tail` (they must give pictures of `shape` = (height, width) in rgb24) and numbers the frames by their time stamps."""
    times = stream_times_of(path)
    first = max(0, first)
    t = frame_time(first, fps, times, "container", preroll)
    d = seek_before(t, times[0], preroll)
    h, w = shape
    cmd = [ffmpeg, "-v", "info", "-hide_banner", "-nostats", "-copyts"] + (["-ss", str(d)] if d > 0 else []) + [
        "-i", path, "-filter_complex",
        f"[0:v]trim=start={fmt_seconds(t)},showinfo,setpts=PTS-STARTPTS,{tail}[v]",
        "-frames:v", str(count), "-map", "[v]", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if on_start:
        on_start(proc)
    out, err = proc.communicate()
    if proc.returncode != 0 and not out:
        raise RuntimeError(f"Frames could not be read: {err.decode(errors='replace')[-300:]}")
    pts = [float(x) for x in re.findall(r"pts_time:\s*(-?[0-9.]+)", err.decode(errors="replace"))]
    n = len(out) // (w * h * 3)
    frames = np.frombuffer(out[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)
    container, rate = float(times[0]), float(fps)
    return {floor((pts[i] - container) * rate + 1e-3): frames[i] for i in range(min(n, len(pts)))}


def grab_numbered(path: str, first: int, count: int, fps: Fraction, size: tuple, preroll: int = 2,
                  ffmpeg: str = "ffmpeg", on_start=None) -> dict:
    """Fetches up to `count` consecutive frames starting at frame `first` (numbers counted from the container start) in one call.

        Returns: {frame number: array height x width x 3}, reduced to `size` = (width, height). The number of each frame is determined
        from its timestamp, not from the order. If `first` lies before the first frame of the file (recordings in which the
        sound starts earlier than the video) or behind the end, the corresponding numbers are missing from the result.
        on_start(process) receives the ffmpeg process so that the caller can cancel it.
    """
    w, h = size
    return _decode_numbered(path, first, count, fps, f"scale={w}:{h}:flags=area", (h, w), preroll, ffmpeg, on_start)


def grab_scanlines(path: str, first: int, count: int, fps: Fraction, x_from: int, x_to: int, y: int, preroll: int = 2,
                   ffmpeg: str = "ffmpeg", on_start=None) -> dict:
    """Like grab_numbered, but only ONE horizontal line of each frame at full resolution: the pixels x_from..x_to (both included) of the line y.

        Returns {frame number: array 1 x (x_to - x_from + 1) x 3}. The values are exactly those of the same line of the whole frame (the
        conversion to RGB happens before cutting out the line), but for hundreds of frames only a few kilobytes are transferred.
    """
    width = x_to - x_from + 1
    return _decode_numbered(path, first, count, fps, f"format=rgb24,crop={width}:1:{x_from}:{y}", (1, width), preroll, ffmpeg, on_start)
