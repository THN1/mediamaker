"""Copy mode: saving WITHOUT re-encoding (ffmpeg `-c copy`; VB6: mnuCopyMode, SaveVideo with the concat demuxer).

What is possible depends on the videos in the segment list (the decisive number is that of different SOURCE FILES):

* ONE video with ONE segment: it is cut at a keyframe, without any filter and without trim: the start is the first keyframe that is not before
  the marker (that is how ffmpeg cuts when copying), the end is the marker. The aspect ratio of the source stays (no setsar=1).
  A segment that is the whole file is copied as it is.
* SEVERAL videos (at least two different files): EVERY item of the list is joined in full length, in the order of the list, with ffmpeg's concat demuxer
  (as in VB6; the same file may be in the list several times). This only works for videos with identical characteristics (size, frame rate, sound,
  codecs). The cut markers, cropping, logo filters, rescaling and the settings of the output profile are ignored.
* In both cases the sound track and the subtitles are chosen by the options (`audio`, `multilanguage`, `subtitle`) and chapters can be added.

Several segments of ONE video only (no other file in the list) can be joined if none of them has cut markers (the whole video several times); if one has, the job
would be cutting AND joining, which is not possible without encoding: CopyModeError.
"""
from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

from cutlist import Job, Segment
from ffmpeg_cmd import fmt_seconds, stream_times_of


class CopyModeError(Exception):
    """The job cannot be made in copy mode; the text says why."""


@dataclass
class CopyPlan:
    kind: str                         # "copy" (whole file), "cut" (one segment of one video) or "concat" (several videos)
    files: list                       # the source files: cut / copy one, concat one for EVERY item of the list (in its order; a file can be there twice)
    segment: Optional[Segment]        # kind copy / cut: the segment
    seconds: float                    # length of the result (for the progress)
    ignored: list = field(default_factory=list)       # what of the job could not be taken into account


def is_whole(seg: Segment) -> bool:
    return seg.end - seg.start >= seg.total_frames - seg.first_frame


def differences(segments: list) -> list:
    """What differs between the videos (the first segment of each file against the first file): size, frame rate, sample rate."""
    first, found = segments[0], []
    seen = {first.path}
    for seg in segments[1:]:
        if seg.path in seen:
            continue
        seen.add(seg.path)
        for what, a, b in (("size", f"{first.width}x{first.height}", f"{seg.width}x{seg.height}"), ("frame rate", f"{float(first.fps):.3f}", f"{float(seg.fps):.3f}"),
                           ("sample rate", str(first.sample_rate), str(seg.sample_rate))):
            if a != b:
                found.append(f"{os.path.basename(seg.path)}: {what} {b} (the first file: {a})")
    return found


def make_plan(segments: list, options: dict) -> CopyPlan:
    if not segments:
        raise CopyModeError("There are no segments in the list.")
    files = list(dict.fromkeys(s.path for s in segments))
    global_crop = int(options.get("crop", 0) or 0) > 0
    if len(files) == 1 and len(segments) > 1:
        cut = [i for i, s in enumerate(segments, 1) if not is_whole(s)]
        if cut:                                                     # (the whole file several times is joined below, like several files)
            raise CopyModeError(f"The list has {len(segments)} segments of the same video, and {'segment' if len(cut) == 1 else 'segments'} "
                                f"{', '.join(map(str, cut))} {'has' if len(cut) == 1 else 'have'} cut markers. In copy mode a video can be cut only once (cutting AND "
                                f"joining is not possible without encoding): remove all but one segment, or remove the cut markers (then the whole video is joined "
                                f"{len(segments)} times), or switch off copy mode.")
    if len(files) == 1 and len(segments) == 1:
        seg = segments[0]
        ignored = [text for text, hit in (("cropping", global_crop or seg.crop_top + seg.crop_bottom + seg.crop_left + seg.crop_right > 0),
                                          ("the logo filter", bool(seg.mask))) if hit]
        whole = is_whole(seg)
        return CopyPlan("copy" if whole else "cut", files, seg, float(Fraction(seg.frames) / seg.fps), ignored)
    found = differences(segments)
    if found:
        raise CopyModeError("Copy mode joins videos with identical characteristics only (size, frame rate, sample rate ...), but:\n" + "\n".join(found))
    ignored = [text for text, hit in (("the cut markers", any(not is_whole(s) for s in segments)),
                                      ("cropping", global_crop or any(s.crop_top + s.crop_bottom + s.crop_left + s.crop_right > 0 for s in segments)),
                                      ("the logo filter", any(s.mask for s in segments))) if hit]
    seconds = float(sum(Fraction(s.total_frames - s.first_frame) / s.fps for s in segments))
    return CopyPlan("concat", [s.path for s in segments], None, seconds, ignored)


def chapter_durations(plan: CopyPlan, duration_fn) -> Optional[list]:
    """For chapters when files are joined: the length of every file as the container gives it (`duration_fn(path)`, seconds). The concat demuxer
    moves each file by the duration of the one before it, so these are the places where the parts begin (the length of the picture alone would be
    too short when the sound starts before the picture, 1.2 s with a recording). None if a duration cannot be had (then the lengths of the segments are used)."""
    try:
        cache = {}
        return [cache.setdefault(path, duration_fn(path)) for path in plan.files]
    except Exception:
        return None


def write_list(plan: CopyPlan, path: str) -> None:
    """The list of files for the concat demuxer (`file '<path>'`, a quote in a name is written as '\\'' )."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for name in plan.files:
            f.write("file '" + name.replace("'", "'\\''") + "'\n")


def subtitle_numbers(options: dict) -> list:
    """The numbers (1, 2 ...) from the option subtitle (\"1,3\"); 0 or empty: none."""
    numbers = []
    for part in str(options.get("subtitle", "0")).split(","):
        part = part.strip()
        if part.isdigit() and int(part) > 0:
            numbers.append(int(part))
    return numbers


def stream_maps(options: dict, audio_sel: str) -> list:
    """-map options: the first video stream, the chosen sound track (all of them with multilanguage), and the chosen subtitles. What is not
    mapped is deleted."""
    maps = ["-map", "0:v:0"]
    if options.get("multilanguage", "False") == "True":
        maps += ["-map", "0:a"]
    else:
        maps += ["-map", "0:" + ("a:0" if audio_sel in ("a", "") else audio_sel)]
    for n in subtitle_numbers(options):
        maps += ["-map", f"0:s:{n - 1}"]
    return maps


def build_copy_command(plan: CopyPlan, job: Job, list_path: Optional[str] = None, ffmpeg: str = "ffmpeg", chapters_file: Optional[str] = None,
                       container_start: Optional[Fraction] = None) -> list:
    """The ffmpeg command: no filter, -c copy.

    cut: -copyts -seek_timestamp 1 -ss <start> -i <file> -to <end> ... -avoid_negative_ts make_zero. Both times are ABSOLUTE (container start +
    frame number / frame rate): a time that is counted from the cut or from the first keyframe would end the cut early by the lead of the sound
    (measured: 0.4 s with a TV recording)."""
    options, out = job.options, job.output
    audio_sel = (plan.segment or job.segments[0]).audio_sel
    maps = stream_maps(options, audio_sel)
    codecs = ["-c", "copy"]
    if subtitle_numbers(options) and out.lower().endswith(".mp4"):
        codecs += ["-c:s", "mov_text"]                         # (text subtitles; bitmap subtitles can be copied into mkv only)
    args = [ffmpeg, "-y", "-hide_banner"]
    if plan.kind == "concat":
        args += ["-f", "concat", "-safe", "0", "-i", list_path]
        trimmed = False
    else:
        seg = plan.segment
        trimmed = plan.kind == "cut"
        if trimmed:
            c0 = container_start if container_start is not None else stream_times_of(seg.path)[0]
            start, end = Fraction(c0) + Fraction(seg.start) / seg.fps, Fraction(c0) + Fraction(seg.end) / seg.fps
            args += ["-copyts", "-seek_timestamp", "1", "-ss", fmt_seconds(start)]
        args += ["-i", seg.path]
        if trimmed:
            args += ["-to", fmt_seconds(end)]
    if chapters_file:
        args += ["-i", chapters_file, "-map_chapters", "1"]
    args += maps + codecs
    if trimmed:
        args += ["-avoid_negative_ts", "make_zero"]
    args.append(out)
    return args
