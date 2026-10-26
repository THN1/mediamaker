"""Builds the ffmpeg command line from segment list, profile and options.

Port of the VB6 functions build(), multi(), crop(), delogo(), floor(), inc().
Differences from the VB6 version:
  * The return value is an argument list (not a string): no quoting problems with spaces,
    umlauts or quotation marks in file names, directly usable for subprocess.
  * Time values are calculated with exact fractions (Fraction) instead of floating point numbers.
    This removes the 1 ms noise (e.g. 2.479 instead of 2.480 at frame 199662 @ 25 fps).

NOT included yet (raises NotImplementedError): DVD mode, subtitles, multilanguage,
copy mode. The rest corresponds to the two normal VB6 branches (one or several source files).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from fractions import Fraction
from functools import lru_cache
from math import floor
from typing import Callable, Optional, Union

from cutlist import Job, Segment


# ----------------------------------------------------------------------------- Start times
def _start_fraction(value, default: Fraction) -> Fraction:
    """Start time from the output of ffprobe; missing or unknown values ("N/A", empty) result in `default`."""
    try:
        return Fraction(str(value)).limit_denominator(1_000_000)
    except (ValueError, ZeroDivisionError, TypeError):
        return default


@lru_cache(maxsize=64)
def stream_times_of(path: str, ffprobe: str = "ffprobe") -> tuple[Fraction, Fraction]:
    """(container start, video start) in seconds, exact as a fraction. TV recordings rarely start at 0.

        If the container or the video stream has no start time (ffprobe then reports "N/A"), 0 or the container start applies.
    """
    out = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-select_streams", "v:0",
                          "-show_entries", "format=start_time:stream=start_time", path],
                         capture_output=True, check=True, stdin=subprocess.DEVNULL).stdout
    d = json.loads(out or b"{}")
    fmt = _start_fraction(d.get("format", {}).get("start_time"), Fraction(0))
    vid = _start_fraction((d.get("streams") or [{}])[0].get("start_time"), fmt)
    return fmt, vid


# ----------------------------------------------------------------------------- Time calculation
def _ms_floor(x: Fraction) -> Fraction:
    return Fraction(floor(x * 1000), 1000)


def _ms_round(x: Fraction) -> Fraction:
    return Fraction(floor(x * 1000 + Fraction(1, 2)), 1000)


def fmt_seconds(x: Fraction) -> str:
    ms = int(x * 1000)
    return f"{ms // 1000}.{ms % 1000:03d}"


def split_seek(start_frame: int, fps: Fraction, preroll: int) -> tuple[int, Fraction]:
    """Splits the start time into a coarse jump (-ss before -i) and a remainder for trim.

        The jump lies `preroll` seconds earlier (safety distance to the keyframe);
        the remainder is then reached exactly by trim (truncated to the millisecond).
    """
    start = Fraction(start_frame) / fps
    seek = max(0, round(start) - preroll)       # round(): like CLng in VB6 (banker's rounding)
    return seek, _ms_floor(start - seek)


def trim_end(rest: Fraction, frames: int, fps: Fraction) -> Fraction:
    return _ms_round(rest + Fraction(frames) / fps)


def origin_base(start_frame: int, fps: Fraction, container_start: Fraction, video_start: Fraction,
                origin: str = "container", preroll: int = 2) -> Fraction:
    """Point in time from which frame numbers are counted.

        "video"     start of the video (first video packet).
        "container" start of the container (earliest stream, often the sound in TV recordings).
        "vb6"       reproduction of the VB6 behaviour as it presents itself with the user's ffmpeg version:
                    without -ss (jump 0 s) trim counts from the video start, with -ss from container start + jump.
                    For recordings in which sound and video do not start at the same time, the same frame number
                    therefore delivers differently shifted frames depending on the position (step at about 2.5 s).
    """
    if origin == "video":
        return video_start
    if origin == "container":
        return container_start
    if origin == "vb6":
        return video_start if split_seek(start_frame, fps, preroll)[0] == 0 else container_start
    raise ValueError(f"origin must be 'video', 'container' or 'vb6', not {origin!r}")


# ----------------------------------------------------------------------------- Filter parts
def _vb_idiv2(x: float) -> int:
    """VB6 '\\ 2': the operand is rounded first, then divided as an integer."""
    return int(round(x)) // 2


def _crop(seg: Segment, w: int, h: int, global_crop: int) -> tuple[str, int, int]:
    if global_crop > 0:
        return f"crop=iw:ih-2*{global_crop}:0:{global_crop},", w, h - 2 * global_crop
    t, b, l, r = seg.crop_top, seg.crop_bottom, seg.crop_left, seg.crop_right
    if t + b + l + r > 0:
        return f"crop=iw-{l + r}:ih-{t + b}:{l}:{t},", w - l - r, h - t - b
    return "", w, h


def _delogo(seg: Segment, w: int, h: int) -> str:
    p = [float(v.replace(",", ".")) for v in seg.mask.split(" ")[:4]]
    x, y, dw, dh = round(p[0] * w), round(p[1] * h), round(p[2] * w), round(p[3] * h)
    # secure the limits (like inside() in VB6): a >= 1 and a + b < max
    x, y = max(x, 1), max(y, 1)
    if x + dw >= w:
        dw = w - x - 1
    if y + dh >= h:
        dh = h - y - 1
    return f"delogo=x={x}:y={y}:w={dw}:h={dh},"


def mask_name(pos: int) -> str:
    return f"removelogo{pos:02d}.png"


def video_filter(seg: Segment, pos: int, profile: dict, opts: dict,
                 trim: Optional[tuple[Fraction, Fraction]], setsar: bool, extra: str = "") -> str:
    f = f"[{pos - 1}:v]"
    if trim:
        f += f"trim={fmt_seconds(trim[0])}:{fmt_seconds(trim[1])},"
    w, h = seg.width, seg.height
    if seg.has_png_mask:
        f += f"removelogo={mask_name(pos)},"
    elif seg.has_delogo:
        f += _delogo(seg, w, h)
    f += extra                                   # e.g. drawtext of the cut point preview (ends with a comma)
    c, w, h = _crop(seg, w, h, int(opts.get("crop", 0)))
    f += c
    sw_, sh_ = (int(v) for v in profile["scale"].split(":"))
    if profile.get("pad", opts.get("pad", "False")) == "True":         # pad belongs to the profile (formerly: options)
        if w * sh_ > h * sw_:
            f += f"pad={w}:{2 * _vb_idiv2(w / sw_ * sh_)}"
        else:
            f += f"pad={2 * _vb_idiv2(h / sh_ * sw_)}:{h}"
        f += ":(ow-iw)/2:(oh-ih)/2,"
    if w < h:                                    # portrait format: pad at the sides
        t = (h * sw_) // sh_
        f += f"pad={t}:ih:{t - 2 * w}:0,"
    f += f"scale={profile['scale']}" + (",setsar=1" if setsar else "") + ",setpts=PTS-STARTPTS"
    return f + f"[v{pos - 1}];"


def audio_filter(seg: Segment, pos: int, trim: Optional[tuple[Fraction, Fraction]]) -> str:
    f = f"[{pos - 1}:{seg.audio_sel}]"
    if trim:
        f += f"atrim={fmt_seconds(trim[0])}:{fmt_seconds(trim[1])},"
    return f + f"asetpts=PTS-STARTPTS[a{pos - 1}];"


_FILTERS: dict = {}


def has_filter(name: str, ffmpeg: str = "ffmpeg") -> bool:
    """Does this ffmpeg have the filter (e.g. drawtext needs libfreetype)? The list is read once per program."""
    if ffmpeg not in _FILTERS:
        try:
            out = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
        except OSError:
            out = ""
        _FILTERS[ffmpeg] = {parts[1] for parts in (line.split() for line in out.splitlines()) if len(parts) > 2 and len(parts[0]) <= 3}
    return name in _FILTERS[ffmpeg]


# ----------------------------------------------------------------------------- Main function
def write_masks(segments: list[Segment], directory: str) -> list[str]:
    """Writes the PNG masks (removelogoNN.png) into the working directory of ffmpeg."""
    names = []
    for pos, seg in enumerate(segments, 1):
        if seg.has_png_mask:
            with open(os.path.join(directory, mask_name(pos)), "wb") as fh:
                fh.write(base64.b64decode(seg.mask))
            names.append(mask_name(pos))
    return names


def build_command(job: Job, ffmpeg: str = "ffmpeg", chapters_file: Optional[str] = None,
                  path_map: Callable[[str], str] = lambda p: p, unify: bool = False,
                  stream_times: Union[dict, str, None] = "auto", origin: str = "container", video_extra: str = "") -> list[str]:
    """Returns the ffmpeg argument list.

        setsar=1 is only set for SEVERAL source files (needed for concat). With a single
        source file SAR/DAR of the recording are kept so that the aspect ratio is not distorted.

        unify=False: behaves like VB6 (with only ONE source file codec, sample rate and
                     minrate/maxrate are not set; ffmpeg defaults apply).
        stream_times: "auto" (default): start and video times of the sources are determined with ffprobe and
                     absolute timestamps are used (-copyts, trim with absolute times); the result then does not
                     depend on how the ffmpeg version treats -ss. A dict {source path: (container start,
                     video start)} specifies the times. None = like VB6 (-ss before -i, trim relative to it); this requires
                     that the ffmpeg version puts the time zero after -ss the way VB6 expects it.
        origin:      zero point of the frame numbers: "container" (default), "video" or "vb6" (see origin_base).
        unify=True:  sets codec, sample rate and minrate/maxrate also for only one source file
                     (SAR behaviour stays unchanged).
        video_extra: filter text (with a trailing comma) inserted into the video chain of every segment, after trim and logo filters.
    """
    prof, opts, segs = job.profile, job.options, job.segments
    if not segs:
        raise ValueError("Segment list is empty.")
    if opts.get("subtitle", "0") != "0" or opts.get("multilanguage", "False") == "True":
        raise NotImplementedError("Subtitles/multilanguage are not implemented yet.")

    if stream_times == "auto":
        stream_times = {p: stream_times_of(path_map(p)) for p in {s.path for s in segs}}
    multiple = len({s.path for s in segs}) > 1
    explicit = multiple or unify                  # set codec/bit rate parameters in full
    preroll = int(opts.get("floor", 2))

    args = [ffmpeg, "-y", "-hide_banner"] + (["-copyts"] if stream_times else [])
    filtr = ""
    for pos, seg in enumerate(segs, 1):
        whole = seg.end - seg.start >= seg.total_frames - seg.first_frame
        # A whole file is not trimmed (as in VB6). With several segments it is trimmed anyway: if the sound of the recording starts
        # before the first picture, concat would otherwise pad the picture of that segment with frozen frames.
        trimmed = not whole or len(segs) > 1
        trim = None
        if trimmed and stream_times:
            fmt0, vid0 = stream_times[seg.path]
            base = origin_base(seg.start, seg.fps, fmt0, vid0, origin, preroll)
            t0 = _ms_floor(base + Fraction(seg.start) / seg.fps)           # absolute start time
            trim = (t0, trim_end(t0, seg.frames, seg.fps))
            seek = max(0, floor(t0 - fmt0) - preroll)                      # -ss is relative to the container start
            if seek > 0:
                args += ["-ss", str(seek)]
        elif trimmed:
            seek, rest = split_seek(seg.start, seg.fps, preroll)
            trim = (rest, trim_end(rest, seg.frames, seg.fps))
            if seek > 0:
                args += ["-ss", str(seek)]
        args += ["-i", path_map(seg.path)]
        filtr += video_filter(seg, pos, prof, opts, trim, setsar=multiple, extra=video_extra)
        filtr += audio_filter(seg, pos, trim)

    if chapters_file:
        args += ["-i", chapters_file, "-map_metadata", str(len(segs))]

    n = len(segs)
    if n == 1:
        filtr = filtr[:-1]                                      # no concat needed
        maps = ["-map", "[v0]", "-map", "[a0]"]
    else:
        filtr += "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
        maps = ["-map", "[v]", "-map", "[a]"]

    args += ["-filter_complex", filtr, *maps, "-sws_flags", prof["sws_flags"]]
    if explicit:
        args += ["-ar", prof["ar"], "-codec:a", prof["acodec_out"], "-b:a", prof["ba"],
                 "-codec:v", "libx264", "-b:v", prof["bv"],
                 "-minrate", "1000k", "-maxrate", "6000k", "-r", prof["fps"]]
    else:
        args += ["-r", prof["fps"], "-b:v", prof["bv"], "-b:a", prof["ba"]]
    args.append(job.output)
    return args
