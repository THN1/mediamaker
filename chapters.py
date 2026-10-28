"""Chapters (VB6: frmChapters, savetxt): a text file for ffmpeg that divides the target file into chapters, one per segment.

The file is in ffmpeg's metadata format (";FFMETADATA1", [CHAPTER] blocks with TIMEBASE, START, END and title). The times follow from the segments
(their lengths, in the order of the list), so the file is only valid as long as the segments are the same: not deleted, not loaded again, not moved
and with the same cut points. Cropping, rescaling and the parameters of the target output profile change nothing about its length. To find out whether
a file is still valid the file carries a SIGNATURE of the segments in a comment line (comments are ignored by ffmpeg). It is the same file that
is written into the batch file and into a session backup, so that it can be restored from there.

    ;FFMETADATA1
    ;MEDIAMAKER chapters signature=<hex>
    [CHAPTER]
    TIMEBASE=1/1000
    START=0
    END=12480
    title=Scene 1

(VB6 wrote the times in microseconds under TIMEBASE=1/1000, i.e. a factor of 1000 too long; here they are milliseconds.)
"""
from __future__ import annotations

import hashlib
import os
from fractions import Fraction
from typing import Iterable, Optional

HEADER = ";FFMETADATA1"
MARK = ";MEDIAMAKER chapters signature="
STYLES = ("Enumerated", "Named", "Named (short)", "Previous", "From Batch")


def signature(segments: Iterable) -> str:
    """What the times of the chapters depend on: for every segment the file, the cut points (counted from the first video frame, so that a
    correction of the first frame does not change them) and the frame rate, in the order of the list."""
    text = "\n".join(f"{s.path}|{s.start - s.first_frame}|{s.end - s.first_frame}|{s.fps}" for s in segments)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def style_titles(style: int, segments: list) -> list:
    """The names for the styles 0 (Enumerated), 1 (Named: "Scene from <file>") and 2 (Named (short): <file>)."""
    base = lambda s: os.path.splitext(s.name)[0]
    if style == 0:
        return [f"Scene {i}" for i in range(1, len(segments) + 1)]
    if style == 1:
        return [f"Scene from {base(s)}" for s in segments]
    if style == 2:
        return [base(s) for s in segments]
    raise ValueError(f"style {style} has no generated names")


def fit_titles(titles: list, segments: list) -> list:
    """Exactly one name per segment: surplus names are dropped, missing ones become "Scene n"."""
    return [(titles[i] if i < len(titles) else f"Scene {i + 1}") for i in range(len(segments))]


def escape(text: str) -> str:
    """A value in the metadata file: = ; # and \\ are written with a backslash, a line break cannot be in a name."""
    text = " ".join(text.split("\n")).replace("\r", "")
    return "".join("\\" + c if c in "=;#\\" else c for c in text)


def unescape(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 1
        out.append(text[i])
        i += 1
    return "".join(out)


def milliseconds(segments: list) -> list:
    """[(start, end)] in milliseconds; every chapter begins where the one before it ended."""
    marks, total = [], Fraction(0)
    for s in segments:
        begin = total
        total += Fraction(s.frames) / s.fps
        marks.append((round(begin * 1000), round(total * 1000)))
    return marks


def build_text(titles: list, segments: list) -> str:
    """The text of the chapters file for these segments (one chapter per segment, see fit_titles)."""
    names = fit_titles(titles, segments)
    lines = [HEADER, MARK + signature(segments)]
    for (start, end), name in zip(milliseconds(segments), names):
        lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={start}", f"END={end}", f"title={escape(name)}"]
    return "\n".join(lines) + "\n"


def parse_titles(text: str) -> list:
    """The names in a chapters file (TITLE= or title=, in the order of the chapters)."""
    titles = []
    for line in text.splitlines():
        line = line.strip()
        if line[:6].lower() == "title=":
            titles.append(unescape(line[6:]))
    return titles


def file_signature(text: str) -> Optional[str]:
    """The signature in the file, or None if it has none (a file that was not made by this program)."""
    for line in text.splitlines():
        if line.startswith(MARK):
            return line[len(MARK):].strip()
    return None


def is_valid(text: str, segments: list) -> bool:
    return bool(segments) and file_signature(text) == signature(segments)


def read(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def write(path: str, titles: list, segments: list) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_text(titles, segments))
