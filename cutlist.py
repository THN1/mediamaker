"""Data model (segment list, profile, options) and import of the batch header lines.

The VB6 version stores in the .bat/.sh file as comments (REM or #):
  J=  output file (plain text)
  P=  profile   (Base64, UTF-16LE, form: key="value" key="value" ...)
  T=  options   (Base64, UTF-16LE, same form)
  C=  segment list as CSV (Base64, UTF-16LE), one line per segment
"""
from __future__ import annotations

import base64
import csv
import glob
import io
import os
import re
import shlex
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

from mediaprobe import KNOWN_FPS


def snap_fps(text: str) -> Fraction:
    """'29.970' -> 30000/1001, '25.000' -> 25 (exact fractions instead of rounded decimal numbers)."""
    f = Fraction(text.strip().replace(",", "."))
    for k in KNOWN_FPS:
        if abs(f - k) < Fraction(1, 500):
            return k
    return f


@dataclass
class Segment:
    index: int                  # 1-based as in the VB6 list
    path: str                   # source file (as stored, possibly a Windows path)
    name: str
    start: int                  # first frame (inclusive)
    end: int                    # end frame; end-start frames are taken over
    total_frames: int           # frame number behind the last video frame (= first_frame + number of frames)
    fps: Fraction
    width: int
    height: int
    vbitrate_kbit: int
    abitrate_kbit: int
    audio_sel: str              # stream selection for audio, e.g. "a"
    crop_top: int
    crop_bottom: int
    crop_left: int
    crop_right: int
    sample_rate: int
    mask: str = ""              # Base64 PNG (removelogo) or "x y w h" as fractions (delogo)
    first_frame: int = 0        # number of the first video frame of the file (counted from the container start; 0 for old lists)

    @property
    def frames(self) -> int:
        return self.end - self.start

    @property
    def has_png_mask(self) -> bool:
        return self.mask.startswith("i")      # like isPNG() in VB6

    @property
    def has_delogo(self) -> bool:
        return bool(self.mask) and not self.has_png_mask


def parse_kv(text: str) -> dict[str, str]:
    """key="value" key2="value2" ... -> dict"""
    return dict(re.findall(r'(\w+)="([^"]*)"', text))


def _decode(b64: str) -> str:
    return base64.b64decode(b64).decode("utf-16le")


def parse_segments(csv_text: str) -> list[Segment]:
    segs = []
    for row in csv.reader(io.StringIO(csv_text)):
        if len(row) < 18:
            continue
        r = row + [""] * (19 - len(row))
        segs.append(Segment(
            index=int(r[0]), path=r[1], name=r[2], start=int(r[3]), end=int(r[4]),
            total_frames=int(r[6]), fps=snap_fps(r[7]), width=int(r[8]), height=int(r[9]),
            vbitrate_kbit=int(r[10] or 0), abitrate_kbit=int(r[11] or 0), audio_sel=r[12],
            crop_top=int(r[13] or 0), crop_bottom=int(r[14] or 0),
            crop_left=int(r[15] or 0), crop_right=int(r[16] or 0),
            sample_rate=int(r[17] or 0), mask=r[18]))
    return segs


@dataclass
class Job:
    output: str
    profile: dict[str, str]
    options: dict[str, str]
    segments: list[Segment] = field(default_factory=list)


def parse_batch_header(text: str) -> Job:
    """Reads J/P/T/C from a .bat (REM ...) or .sh (# ...) file of MediaMaker."""
    parts = {"P": "", "T": "", "C": ""}
    output = ""
    for line in text.splitlines():
        m = re.match(r"^(?:#|REM)\s+([JPTC])=(.*)$", line.strip(), re.IGNORECASE)
        if not m:
            continue
        key, val = m.group(1).upper(), m.group(2).strip()
        if key == "J":
            output = val
        else:
            parts[key] += val
    return Job(output=output,
               profile=parse_kv(_decode(parts["P"])) if parts["P"] else {},
               options=parse_kv(_decode(parts["T"])) if parts["T"] else {},
               segments=parse_segments(_decode(parts["C"])) if parts["C"] else [])


# ----------------------------------------------------------------------------- ffmpeg call in the batch file
def extract_command(text: str) -> Optional[str]:
    """The line of the .bat/.sh that calls ffmpeg with the filter graph (not the comment lines)."""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.upper().startswith("REM ") and " -filter_complex " in s:
            return s
    return None


def split_args(line: str) -> list[str]:
    """Splits the command line into arguments (bash or Windows notation)."""
    if re.search(r"[A-Za-z]:\\", line):                    # Windows paths: do not treat backslashes as escapes
        return [t[1:-1] if len(t) > 1 and t[0] == t[-1] == '"' else t for t in shlex.split(line, posix=False)]
    return shlex.split(line)


def input_paths(args: list[str]) -> list[str]:
    return [args[i + 1] for i, a in enumerate(args[:-1]) if a == "-i"]


def metadata_input(args: list[str]) -> tuple[Optional[str], int]:
    """(path of the chapter metadata file or None, number of cut sources)."""
    paths = input_paths(args)
    if "-map_metadata" in args:
        n = int(args[args.index("-map_metadata") + 1])
        return paths[n], n
    return None, len(paths)


def resolve_source(path: str) -> str:
    """Returns the path of a source file; also finds it if a KDE kio-fuse directory has changed.

        Under KDE network shares look like /run/user/1000/kio-fuse-sFijsz/smb/... ; the part after "kio-fuse-"
        is random and changes with every session. If the path does not exist, it is searched with any random part
        (with several hits the most recently changed directory wins). Nothing found: the path stays unchanged.
    """
    if os.path.exists(path):
        return path
    m = re.search(r"/kio-fuse-[^/]+", path)
    if m:
        pattern = glob.escape(path[:m.start()]) + "/kio-fuse-*" + glob.escape(path[m.end():])
        found = sorted(glob.glob(pattern), key=os.path.getmtime)
        if found:
            return found[-1]
    return path
