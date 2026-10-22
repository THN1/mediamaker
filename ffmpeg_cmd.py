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


FILL_FEATHER = 1.2                  # soft edge of the patch in pixels
FILL_FLOOR = 200                    # smallest weight (of 65535) that is divided by: keeps the division stable far from the known pixels
MASK_EXTRA_SECONDS = 5              # the looped mask picture is this much longer than the segment (the picture decides the end)


def logo_region(mask, width: int, height: int, sigma: float) -> tuple[int, int, int, int]:
    """(x, y, w, h) of the part of the picture the smooth fill works on: the bounding box of the white pixels of the mask plus a margin
    of about three times sigma (the known pixels that the fill is made of), limited to the picture, with even position and size (4:2:0)."""
    import numpy as np
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return 0, 0, width - width % 2, height - height % 2
    margin = int(3 * sigma) + 2
    x0, x1 = max(0, int(xs.min()) - margin), min(width, int(xs.max()) + 1 + margin)
    y0, y1 = max(0, int(ys.min()) - margin), min(height, int(ys.max()) + 1 + margin)
    x0, y0 = x0 - x0 % 2, y0 - y0 % 2
    w, h = min(width - x0, x1 - x0), min(height - y0, y1 - y0)
    return x0, y0, w - w % 2, h - h % 2


def smooth_fill(seg: Segment, pos: int, trim_text: str, duration: float, sigma: float) -> str:
    """The part of the video chain of a segment that replaces the logo by a smooth fill instead of ffmpeg's removelogo filter.

    removelogo copies the pixels of the nearest edge into the masked area, which gives the typical X-shaped streaks. Here the masked
    area is filled with the average of the known pixels around it, weighted with a Gauss curve (a normalized convolution:
    blur(picture * known) / blur(known)), and the patch is blended in with a soft edge. The work is done on the small part of the
    picture around the logo, in RGB with 16 bits. The mask comes from the PNG file (movie filter), repeated for the whole segment.
    Returns the statements up to and including the overlay, ending with a comma so that the usual filters can follow."""
    from logo import mask_from_png_b64
    n = pos - 1
    x, y, w, h = logo_region(mask_from_png_b64(seg.mask), seg.width, seg.height, sigma)
    s = f"{sigma:g}"
    return (f"[{n}:v]{trim_text}setpts=PTS-STARTPTS,split=2[sa{n}][sb{n}];"
            f"[sb{n}]crop={w}:{h}:{x}:{y},format=gbrp16le,split=2[rc{n}][rd{n}];"
            f"movie={mask_name(pos)},format=gray,loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB,trim=end={duration + MASK_EXTRA_SECONDS:.3f},"
            f"crop={w}:{h}:{x}:{y},format=gbrp16le,split=3[mk{n}][ml{n}][mm{n}];"
            f"[mk{n}]negate,split=2[w1{n}][w2{n}];"
            f"[rc{n}][w1{n}]blend=all_expr='A*B/65535':shortest=1[kn{n}];"
            f"[kn{n}]gblur=sigma={s}:steps=4[gk{n}];[w2{n}]gblur=sigma={s}:steps=4[gw{n}];"
            f"[gk{n}][gw{n}]blend=all_expr='min(65535,A*65535/max(B,{FILL_FLOOR}))':shortest=1[fl{n}];"
            f"[ml{n}]gblur=sigma={FILL_FEATHER}[mf{n}];[mm{n}]gblur=sigma={FILL_FEATHER},negate[nm{n}];"
            f"[fl{n}][mf{n}]blend=all_expr='A*B/65535':shortest=1[fm{n}];"
            f"[rd{n}][nm{n}]blend=all_expr='A*B/65535':shortest=1[rm{n}];"
            f"[fm{n}][rm{n}]blend=all_expr='A+B':shortest=1[pt{n}];"
            f"[sa{n}][pt{n}]overlay={x}:{y}:shortest=1,format=yuv420p,")


def video_filter(seg: Segment, pos: int, profile: dict, opts: dict,
                 trim: Optional[tuple[Fraction, Fraction]], setsar: bool) -> str:
    trim_text = f"trim={fmt_seconds(trim[0])}:{fmt_seconds(trim[1])}," if trim else ""
    w, h = seg.width, seg.height
    if seg.has_png_mask and opts.get("logo_fill", "removelogo") == "smooth":
        f = smooth_fill(seg, pos, trim_text, float(seg.frames / seg.fps), float(opts.get("fill_sigma", 6)))
    else:
        f = f"[{pos - 1}:v]" + trim_text
    if seg.has_png_mask and opts.get("logo_fill", "removelogo") != "smooth":
        f += f"removelogo={mask_name(pos)},"
    elif seg.has_delogo:
        f += _delogo(seg, w, h)
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
                  stream_times: Union[dict, str, None] = "auto", origin: str = "container") -> list[str]:
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
        filtr += video_filter(seg, pos, prof, opts, trim, setsar=multiple)
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
