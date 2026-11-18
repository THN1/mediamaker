"""Builds the ffmpeg command line from segment list, profile and options.

Port of the VB6 functions build(), multi(), crop(), delogo(), floor(), inc().
Differences from the VB6 version:
  * The return value is an argument list (not a string): no quoting problems with spaces,
    umlauts or quotation marks in file names, directly usable for subprocess.
  * Time values are calculated with exact fractions (Fraction) instead of floating point numbers.
    This removes the 1 ms noise (e.g. 2.479 instead of 2.480 at frame 199662 @ 25 fps).

NOT included yet (raises NotImplementedError): DVD mode,
copy mode. The rest corresponds to the two normal VB6 branches (one or several source files).
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from fractions import Fraction
from functools import lru_cache
from math import floor
from typing import Callable, Optional, Union

import dvd
import mediaprobe
import tracks
from cutlist import Job, Segment
from profiles import is_on


# ----------------------------------------------------------------------------- Start times
def _start_fraction(value, default: Fraction) -> Fraction:
    """Start time from the output of ffprobe; missing or unknown values ("N/A", empty) result in `default`."""
    try:
        return Fraction(str(value)).limit_denominator(1_000_000)
    except (ValueError, ZeroDivisionError, TypeError):
        return default


_VERSIONS: dict = {}


def ffmpeg_version(ffmpeg: str = "ffmpeg", run: Callable = subprocess.run) -> Optional[tuple]:
    """(major, minor) of the ffmpeg program ("ffmpeg version 4.4.2-0ubuntu0.22.04.1", "n6.1", "7.0.1" ...); None if it cannot be found out or is a build from the
    repository ("N-12345-g...", which is a new one). Asked once per program."""
    if ffmpeg not in _VERSIONS:
        version = None
        try:
            out = run([ffmpeg, "-version"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=15).stdout or ""
            m = re.match(r"\s*ffmpeg version n?(\d+)\.(\d+)", out)
            version = (int(m.group(1)), int(m.group(2))) if m else None
        except (OSError, subprocess.SubprocessError):
            pass
        _VERSIONS[ffmpeg] = version
    return _VERSIONS[ffmpeg]


def passthrough_args(ffmpeg: str = "ffmpeg", run: Callable = subprocess.run) -> list:
    """Every frame is passed on as it is (no frame dropped or repeated): `-fps_mode passthrough` since ffmpeg 5.1, before that `-vsync 0` (the same, an older name)."""
    version = ffmpeg_version(ffmpeg, run)
    return ["-vsync", "0"] if version is not None and version < (5, 1) else ["-fps_mode", "passthrough"]


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
                 trim: Optional[tuple[Fraction, Fraction]], setsar: bool, extra: str = "", regen: bool = False) -> str:
    f = f"[{pos - 1}:v]"
    if regen:                                    # DVD: the times of the pictures are made from their COUNT (N), see build_command
        f += f"setpts=N*{seg.fps.denominator}/{seg.fps.numerator}/TB,"
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
    if is_on(profile.get("pad", opts.get("pad", "off"))):         # pad belongs to the profile (formerly: options)
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


def audio_filter(seg: Segment, pos: int, trim: Optional[tuple[Fraction, Fraction]], selector: Optional[str] = None, label: Optional[str] = None, regen: bool = False) -> str:
    """The chain of one audio track of a segment. selector: e.g. "a:2" (default: the audio track of the segment); label: name of the result (default a<pos-1>).
    regen (DVD): the times are made from the count of the samples (N / sample rate)."""
    f = f"[{pos - 1}:{selector or seg.audio_sel}]"
    if regen:
        f += f"asetpts=N/{seg.sample_rate or 'SR'}/TB,"
    if trim:
        f += f"atrim={fmt_seconds(trim[0])}:{fmt_seconds(trim[1])},"
    return f + f"asetpts=PTS-STARTPTS[{label or f'a{pos - 1}'}];"


def source_of(seg: Segment, path_map: Callable[[str], str] = lambda p: p) -> str:
    """What ffmpeg opens for the segment: its file, or for a run of parts of a DVD (dvd.effective_segments) 'concat:a|b' (the bytes of the parts one after the other)."""
    files = dvd.files_of(seg.path)
    return dvd.CONCAT + "|".join(path_map(f) for f in files) if len(files) > 1 else path_map(seg.path)


def source_parts(seg: Segment, path_map: Callable[[str], str] = lambda p: p) -> list:
    """[(file name for ffmpeg, number of its first picture)] of the pieces of a segment between two jumps of the time stamps; the pieces of the parts of a run follow each other, the
    numbers go on through the parts."""
    result, base = [], 0
    for path in dvd.files_of(seg.path):
        real = path_map(path)
        scan = dvd.scan_of(real)
        result += [(piece.url(real), base + piece.first_picture) for piece in scan.pieces]
        base += len(scan.picture_bytes)
    return result


def _quote(path: str) -> str:
    return "'" + path.replace("'", "'\\''") + "'"


SUBTITLE_START = "@SUBTITLE_START@"     # in the command, behind -itsoffset: the start time of the list of subtitles, which is filled in when the command is run (see subtitle_start)


def subtitle_start_args(list_path: str) -> list:
    """The ffprobe command that asks for the start time of the input made of the list of subtitles (what ffmpeg will subtract from its times)."""
    return ["ffprobe", "-v", "error", "-protocol_whitelist", "file,subfile,crypto,data", "-f", "concat", "-safe", "0", "-i", list_path, "-show_entries", "format=start_time", "-of", "csv=p=0"]


def subtitle_start(list_path: str, run=None) -> float:
    """The start time of the input made of the list of subtitles, as ffprobe (of the same build as ffmpeg) sees it; 0.0 if there is none. ffmpeg subtracts the start time of EVERY input from
    its times (without -copyts): ffmpeg 6.1 says -0.08 s for such a list, ffmpeg 9 says 16.8 s (the time of the first subtitle, a list has nothing else), and the subtitles came 16.8 s too early.
    -itsoffset with this time gives it back, so that the times are those of the list: counted from the first picture of the segment."""
    import subprocess
    try:
        out = (run or subprocess.run)(subtitle_start_args(list_path), capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60).stdout.strip().split("\n")[0].strip(",")
        return float(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def fill_subtitle_start(command: list, list_path: str, run=None) -> list:
    """The command with the placeholder for the start time of the list of subtitles replaced by the real time (unchanged if there is none in it)."""
    if SUBTITLE_START not in command:
        return command
    value = f"{subtitle_start(list_path, run):.3f}"
    return [value if a == SUBTITLE_START else a for a in command]


def subtitle_list_text(entries: list, stream_ids: Optional[list] = None) -> str:
    """The list for the concat demuxer that cuts the subtitles like the video: [(file, in point, out point or None, length or None)] in seconds (absolute times, as the
    stream has them: with -copyts the subtitles then meet the picture exactly; measured). The demuxer puts the pieces one after the other with the given lengths.

    stream_ids (DVD mode: the ids of the subtitle streams, "0x21"): the list declares the streams (stream / exact_stream_id), so that every file contributes the stream with THIS id,
    wherever it stands in that file. Without them the demuxer takes the n-th stream of every file, and the first file decides what that is (see tracks.py)."""
    out = "ffconcat version 1.0\n"
    for stream_id in stream_ids or []:
        out += f"stream\nexact_stream_id {stream_id}\n"
    for path, t0, t1, length in entries:
        out += f"file {_quote(path)}\ninpoint {fmt_seconds(t0)}\n"
        if t1 is not None:
            out += f"outpoint {fmt_seconds(t1)}\nduration {fmt_seconds(length)}\n"
    return out


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
                  stream_times: Union[dict, str, None] = "auto", origin: str = "container", video_extra: str = "",
                  subtitle_list: Optional[str] = None, files: Optional[dict] = None, track_list=None) -> list[str]:
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
        Tracks (options audio_tracks / subtitle_tracks of the job, see tracks.py): several audio tracks are cut and joined like the first one (concat with a=K),
        with their language codes; subtitles (the concat FILTER cannot join them) come from a second input, the concat DEMUXER with a list (`subtitle_list`: the path
        of the list file; its text is put into `files[subtitle_list]`, the caller writes it), which cuts them with the same times as the video.
        track_list: the tracks of the first source file (read with ffprobe if the subtitles need it).
    """
    prof, opts, segs = job.profile, job.options, job.segments
    if not segs:
        raise ValueError("Segment list is empty.")
    choice = tracks.Choice.from_options(opts)
    # DVD: the times of the stream jump (a new cell, a new program chain: the time starts again somewhere in the file). With -copyts ffmpeg does not correct that, and cutting by
    # absolute times then loses every picture after the jump (measured: a file of two pieces of 8 s each gave 202 of 400 frames). Without -copyts ffmpeg makes the times continuous,
    # so DVD mode cuts by relative times, as the VB6 program did (-ss, then trim). The subtitles then need the start times of the files for their list.
    relative = stream_times == "auto" and dvd.is_dvd_structure([s.path for s in segs])
    if relative:
        stream_times = None
        segs = dvd.effective_segments(segs, path_map)        # neighbouring parts that continue each other are read as ONE stream (the seam loses nothing then), see dvd.mergeable
    # ... and not only the cutting: ffmpeg 8 does NOT make the time continuous in a filter graph any more (measured by the user on a DVD: decoding alone 35133 frames, 23:25; the graph with
    # trim and -r 25: 17777 frames, 17357 dropped, the time after the jump starts again; ffmpeg 6.1 corrects it in both). So in DVD mode the times of the pictures and of the samples are made
    # from their count before anything else (setpts=N/(fps*TB), asetpts=N/(rate*TB)): continuous whatever the stream says.
    if choice and choice.subtitles:
        if not stream_times and not relative:
            raise NotImplementedError("Subtitles need the absolute times (stream_times).")
        if not subtitle_list or files is None:
            raise ValueError("Subtitles need subtitle_list (the path of the list) and files (where its text is put).")
        if track_list is None:
            track_list = mediaprobe.track_list(path_map(dvd.files_of(segs[0].path)[0]))
    streams = tracks.streams_for(opts, job.output, track_list)
    selectors = [tracks.audio_spec(index) for index, _ in streams.audio] or [None]        # None: the audio track of the segment (a:3 by position, i:0x80 by stream id: DVD)
    n_audio = len(selectors)
    sub_entries = []

    if stream_times == "auto":
        stream_times = {p: stream_times_of(path_map(p)) for p in {s.path for s in segs}}
    file_times = stream_times or ({s.path: stream_times_of(path_map(dvd.files_of(s.path)[0])) for s in segs} if relative and streams.subtitles else {})    # (container start, video start)
    pieces = {s.path: source_parts(s, path_map) for s in segs} if relative and streams.subtitles else {}      # the pieces between jumps of the time stamps (DVD)
    piece_times = stream_times_of
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
        trim_v = None                              # the time span of the PICTURE (only differs from the span of the sound in DVD mode, see below)
        shift = 0                                  # relative cutting: the times of the list of subtitles are those in the file = start of the file + the jump of -ss
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
            if relative and seek > 0:
                # No -ss in DVD mode: the times of a VOB stream jump (see above) and ffmpeg seeks by those times, so it lands in the wrong piece or behind the end (a cut at 23:20 of a title
                # whose time starts again at picture 17777 gave a clip without any stream). The pictures are counted from the start (setpts=N...), so the start is reached by trim alone.
                seek, rest = 0, _ms_floor(Fraction(seg.start) / seg.fps)
            trim = (rest, trim_end(rest, seg.frames, seg.fps))
            if relative and seek == 0:
                # The counted time of the PICTURE starts with the first picture, which has the number first_frame; the counted time of the SOUND starts with its first sample, at the start of
                # the container (the sound of a DVD part often begins before the picture: 0.48 s in a part of queen.vob). So the picture needs its own span: from (start - first_frame) frames.
                rest_v = _ms_floor(Fraction(max(seg.start - seg.first_frame, 0)) / seg.fps)
                trim_v = (rest_v, trim_end(rest_v, seg.frames, seg.fps))
            if seek > 0:
                args += ["-ss", str(seek)]
            if streams.subtitles:
                shift = file_times[seg.path][0] + seek
        if relative:
            # The parts of a DVD differ in the colour space (smpte170m / bt470bg) and in the order of the fields (progressive / bottom first), sometimes within ONE file at a cell; newer
            # ffmpeg builds the WHOLE filter graph anew when that changes ("Reconfiguring filter graph because video parameters changed", in the log of the user's batch run), and all
            # counters start again (setpts=N, trim, concat): the sound runs from the start again ("Non-monotonic DTS"), the frames behind it are thrown away. -reinit_filter 0: never.
            args += ["-reinit_filter", "0"]
        args += ["-i", source_of(seg, path_map)]
        filtr += video_filter(seg, pos, prof, opts, trim_v or trim, setsar=multiple, extra=video_extra, regen=relative)
        for k, selector in enumerate(selectors):
            filtr += audio_filter(seg, pos, trim, selector, f"a{pos - 1}" if n_audio == 1 else f"a{pos - 1}_{k}", regen=relative)
        if streams.subtitles:                                             # the same times as the picture, so that the subtitles meet it
            first = seg.start - seg.first_frame + dvd.undecodable_head(path_map(dvd.files_of(seg.path)[0]))      # its first picture as a place among the PACKETS of the file (the first ones cannot be decoded)
            parts = pieces.get(seg.path, [])
            if relative and len(parts) > 1 and first + seg.frames > parts[1][1]:
                # DVD: the segment reaches behind a jump of the time stamps of its file (or into the next part of a run). The demuxer of the list does not correct jumps (the subtitles
                # behind it then all get one time, or the time of the wrapped stream): every piece between two jumps goes into the list as a file of its own (protocol subfile), with the
                # length of its pictures.
                for k, (url, part_first) in enumerate(parts):
                    next_first = parts[k + 1][1] if k + 1 < len(parts) else first + seg.frames
                    lo, hi = max(first, part_first), min(first + seg.frames, next_first)
                    if hi <= lo:
                        continue
                    length = Fraction(hi - lo) / seg.fps
                    if lo == first and k == 0:
                        begin = trim[0] + shift if trim else file_times[seg.path][1]
                    else:
                        begin = piece_times(url)[1] + Fraction(lo - part_first) / seg.fps
                    sub_entries.append((url, begin, begin + length, length))
            elif trim:
                sub_entries.append((source_of(seg, path_map), trim[0] + shift, trim[1] + shift, trim[1] - trim[0]))
            else:
                sub_entries.append((source_of(seg, path_map), file_times[seg.path][1], None, None))          # a whole file: from its first picture

    if chapters_file:
        # (-map_chapters: the chapters come from THIS file, also if a source file has chapters itself; without it ffmpeg takes the first input that has any)
        args += ["-i", chapters_file, "-map_metadata", str(len(segs)), "-map_chapters", str(len(segs))]

    n = len(segs)
    if n_audio == 1:
        alabels = [lambda i, k: f"a{i}"]
        outs = ["a"]
    else:
        alabels = [lambda i, k: f"a{i}_{k}"]
        outs = [f"aout{k}" for k in range(n_audio)]
    alabel = alabels[0]
    if n == 1:
        filtr = filtr[:-1]                                      # no concat needed
        maps = ["-map", "[v0]"] + [x for k in range(n_audio) for x in ("-map", f"[{alabel(0, k)}]")]
    else:
        filtr += "".join(f"[v{i}]" + "".join(f"[{alabel(i, k)}]" for k in range(n_audio)) for i in range(n)) + f"concat=n={n}:v=1:a={n_audio}[v]" + "".join(f"[{o}]" for o in outs)
        maps = ["-map", "[v]"] + [x for o in outs for x in ("-map", f"[{o}]")]
    if streams.subtitles:
        sub_input = len(segs) + (1 if chapters_file else 0)                 # (after the segments and the file of the chapters)
        by_id = [index for index, *_ in streams.subtitles if isinstance(index, str)]
        files[subtitle_list] = subtitle_list_text(sub_entries, by_id or None)
        args += (["-canvas_size", f"{segs[0].width}x{segs[0].height}"] if streams.canvas else []) + (["-protocol_whitelist", "file,subfile,crypto,data"] if any(len(v) > 1 for v in pieces.values()) else []) + (["-itsoffset", SUBTITLE_START] if relative else []) + ["-f", "concat", "-safe", "0", "-i", subtitle_list]
        if by_id:                                      # the list declares the streams (by id): they are the subtitle streams 0, 1, ... of the input, in the order of the choice
            maps += [x for k in range(len(by_id)) for x in ("-map", f"{sub_input}:s:{k}")]
        else:
            maps += [x for index, *_ in streams.subtitles for x in ("-map", f"{sub_input}:s:{index}")]

    args += ["-filter_complex", filtr, *maps, "-sws_flags", prof["sws_flags"]]
    if explicit:
        args += ["-ar", prof["ar"], "-codec:a", prof["acodec_out"], "-b:a", prof["ba"],
                 "-codec:v", "libx264", "-b:v", prof["bv"],
                 "-minrate", "1000k", "-maxrate", "6000k", "-r", prof["fps"]]
    else:
        args += ["-r", prof["fps"], "-b:v", prof["bv"], "-b:a", prof["ba"]]
    args += tracks.subtitle_codec_args(streams) + tracks.metadata_args(streams, job.output)
    args.append(job.output)
    return args
