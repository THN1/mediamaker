"""File types (containers) of the target file and what each one can hold.

The file type follows from the extension of the target file, ffmpeg chooses the container with it. All combinations of the usual video and
audio codecs are accepted by ffmpeg in all four containers (measured with ffmpeg 6.1.1: h264, mpeg2video, mpeg4, hevc with aac, mp2, mp3, ac3,
pcm in mp4, mkv, avi and ts), so the codecs are not checked. What does differ:

* chapters: mp4 and mkv hold them; avi and ts do not (ffmpeg leaves them out without a word);
* subtitles: mkv copies every kind; mp4 only text subtitles, converted with `-c:s mov_text` (a plain copy is an ERROR of ffmpeg, bitmap subtitles cannot be
  converted); avi cannot hold subtitles at all (ERROR: "Not yet implemented in FFmpeg"); ts holds the DVB ones of a recording (a text subtitle is muxed as
  "private data" that no player knows);
* -movflags (mp4 only) is not used by the program.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

TEXT_SUBTITLES = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text", "text", "microdvd", "subviewer", "sami"}
BITMAP_SUBTITLES = {"dvb_subtitle", "dvd_subtitle", "hdmv_pgs_subtitle", "xsub", "dvb_teletext"}


@dataclass(frozen=True)
class Container:
    ext: str                    # without the dot
    name: str                   # as in the file dialog
    chapters: bool              # can hold chapters
    subtitles: str              # "" none, "text" only text subtitles (mp4), "dvb" only DVB ones (ts), "all"
    subtitle_codec: str = ""    # value of -c:s for subtitles that are taken over ("" = copy)


CONTAINERS = (Container("mp4", "MP4 video file", True, "text", "mov_text"),
              Container("mkv", "Matroska video file", True, "all"),
              Container("avi", "A/V Interleave file", False, ""),
              Container("ts", "MPEG transport stream", False, "dvb"))
EXTENSIONS = tuple(c.ext for c in CONTAINERS)


def info(path_or_ext: str) -> Optional[Container]:
    """The container for a file name or an extension (None: not one that the program offers)."""
    ext = os.path.splitext(path_or_ext)[1] if "." in path_or_ext else "." + path_or_ext
    ext = ext.lstrip(".").lower()
    return next((c for c in CONTAINERS if c.ext == ext), None)


def filters(first: str = "mp4") -> str:
    """The list of file types for the file dialog, `first` at the top (that is the one that is selected)."""
    ordered = sorted(CONTAINERS, key=lambda c: c.ext != first)
    return ";;".join(f"{c.name} (*.{c.ext})" for c in ordered) + ";;All files (*)"


def extension_of_filter(selected: str) -> Optional[str]:
    """'MP4 video file (*.mp4)' -> 'mp4' (None for 'All files (*)' or an empty text)."""
    m = re.search(r"\(\*\.(\w+)\)", selected or "")
    return m.group(1).lower() if m and info(m.group(1)) else None


def subtitle_codec(path: str) -> str:
    """-c:s for subtitles taken over into this file ('' = plain copy)."""
    c = info(path)
    return c.subtitle_codec if c else ""


def check(output: str, chapters: bool = False, subtitles: Optional[list] = None, copy_mode: bool = False) -> tuple:
    """What the target file type does not allow. Returns (errors, warnings): errors cannot be saved at all, warnings can (something is left out).

    chapters:  chapters are to be saved;
    subtitles: the codec names of the subtitle tracks that were chosen (the option subtitle), only given in copy mode; None = not asked."""
    errors, warnings = [], []
    c = info(output)
    if c is None:
        ext = os.path.splitext(output)[1] or "(none)"
        return [f"The file type {ext} is not supported: use one of {', '.join('.' + e for e in EXTENSIONS)}."], warnings
    if chapters and not c.chapters:
        warnings.append(f"A .{c.ext} file cannot hold chapters: they are left out (mp4 and mkv can hold them).")
    for codec in subtitles or []:
        if c.subtitles == "":
            errors.append(f"A .{c.ext} file cannot hold subtitles (mkv can; mp4 only text subtitles).")
            break
        kind = "text" if codec in TEXT_SUBTITLES else "bitmap" if codec in BITMAP_SUBTITLES else "other"
        if c.subtitles == "text" and kind != "text":
            errors.append(f"A .{c.ext} file can hold only text subtitles, the chosen track is {codec} (mkv can hold it).")
        elif c.subtitles == "dvb" and codec not in ("dvb_subtitle", "dvb_teletext"):
            errors.append(f"A .{c.ext} file can hold only the DVB subtitles of a recording, the chosen track is {codec} (mkv can hold it).")
    return errors, warnings
