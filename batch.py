"""Batch files and file names (VB6: mnuBatch_Click, wenc, lvwSave, suggest).

A batch file is a shell script that cuts one job with ffmpeg. Besides the commands it carries the whole job as comments so that
it can be read again later ("Import"): J= the output file, P= the profile, T= the options and C= the segment list as CSV. P, T
and C are the text encoded as UTF-16LE and Base64, in lines of 72 characters (as VB6 wrote them). Masks for the removelogo filter
are created from Base64 text in the script itself.
"""
from __future__ import annotations

import base64
import os
import re
from typing import Iterable, Optional

from cutlist import Job, Segment
from project import format_hms
from settings import format_kv

SHEBANG = "#!/bin/bash"
LINE = 72                                    # characters of encoded text per line
CLEANUP = "rm removelogo??.png 2>/dev/null"
OUTPUT_EXTENSIONS = ("mp4", "mkv", "avi")
SAFE = re.compile(r"^[A-Za-z0-9_@%+=:,./-]+$")


def bash_quote(arg: str) -> str:
    """Argument for a bash command line: left as it is if it is harmless, otherwise in double quotes."""
    if SAFE.match(arg):
        return arg
    return '"' + re.sub(r'(["\\$`])', r"\\\1", arg) + '"'


def command_line(args: Iterable[str]) -> str:
    return " ".join(bash_quote(a) for a in args)


def encode_block(prefix: str, text: str) -> list[str]:
    """Comment lines  '# P=<Base64>'  for a text (UTF-16LE, 72 characters per line)."""
    data = base64.b64encode(text.encode("utf-16le")).decode("ascii")
    chunks = [data[i:i + LINE] for i in range(0, len(data), LINE)] or [""]
    return [f"# {prefix}={chunk}" for chunk in chunks]


def csv_rows(segments: Iterable[Segment]) -> list[list[str]]:
    """The 19 columns of the VB6 list file. Frame numbers count from the start of the container; the total is the number of
    decodable frames (as VB6 wrote it); the first video frame is found again when the list is imported."""
    return [[f"{i:02d}", s.path, s.name, str(s.start), str(s.end), format_hms(s.frames / float(s.fps)),
             str(s.total_frames - s.first_frame), f"{float(s.fps):.3f}", str(s.width), str(s.height), str(s.vbitrate_kbit),
             str(s.abitrate_kbit), s.audio_sel, str(s.crop_top), str(s.crop_bottom), str(s.crop_left), str(s.crop_right),
             str(s.sample_rate), s.mask] for i, s in enumerate(segments, 1)]


def segments_to_csv(segments: Iterable[Segment]) -> str:
    return "".join(",".join('"' + f.replace('"', '""') + '"' for f in row) + "\r\n" for row in csv_rows(segments))


def job_lines(job: Job, command: list[str]) -> list[str]:
    """The lines of one job: comments with the whole job, masks, the ffmpeg call, clean-up."""
    lines = [f"# J={job.output}"]
    lines += encode_block("P", format_kv(job.profile))
    lines += encode_block("T", format_kv(job.options))
    lines += encode_block("C", segments_to_csv(job.segments))
    for i, seg in enumerate(job.segments, 1):
        if seg.has_png_mask:
            lines.append(f'base64 -d <<< "{seg.mask}" > removelogo{i:02d}.png')
    lines.append(command_line(command))
    lines.append(CLEANUP)
    return lines


def build_script(job: Job, command: list[str], old_text: Optional[str] = None) -> str:
    """Text of the batch file. With `old_text` (the existing file) its earlier jobs are kept but switched off: every line that is
    not a comment gets '# ' in front (the comments stay, so the old jobs can still be imported)."""
    lines = [SHEBANG]
    if old_text:
        old = old_text.splitlines()
        if old and old[0].startswith("#!"):
            old = old[1:]
        lines += [line if line.startswith("#") else "# " + line for line in old]
    lines += job_lines(job, command)
    return "\n".join(lines) + "\n"


def suggest_name(path: str, kind: str = "mp4", multiple: bool = False) -> str:
    """Suggestion for the target file from the name of a TV recording (VB6: suggest()).

    'D/20261015 0053 - kabel eins - Elysium.ts'  ->  'D/Elysium (YYYY) TVRip kabel eins'  (the year is for the user to fill in;
    the extension is added by the file dialog). Other names: the same name with the extension of the target. With several
    source files: 'output.<kind>' in the folder of the last file."""
    folder = os.path.dirname(path)
    if multiple:
        return os.path.join(folder, f"output.{kind}")
    parts = path.split(" - ")
    count = len(parts) - 1
    if count in (2, 3):
        tail = parts[2] if count == 2 else parts[2] + " - " + parts[3]
        name = os.path.join(folder, tail.split(".")[0] + f" (YYYY) TVRip {parts[1]}")
    else:
        root, ext = os.path.splitext(path)
        name = root + "." + kind if ext else path + "." + kind
    return name.replace("_ ", " - ")


def parse_path_map(text: str) -> list:
    """Rules "source=target;source=target" -> [(pattern, target)]. In a source `*` stands for any characters except "/" (the
    KDE directory kio-fuse-XXXXXX changes with every session). Entries without "=" are ignored."""
    rules = []
    for part in (text or "").split(";"):
        source, equals, target = part.partition("=")
        source, target = source.strip(), target.strip()
        if equals and source:
            rules.append((re.compile("^" + "".join("[^/]*" if c == "*" else re.escape(c) for c in source)), target))
    return rules


def map_path(path: str, rules: list) -> str:
    """Replaces the beginning of `path` according to the first matching rule (no rule matches: unchanged)."""
    for pattern, target in rules:
        m = pattern.match(path)
        if m:
            return target + path[m.end():]
    return path


def map_sources(command: list, rules: list) -> list:
    """The ffmpeg arguments with the paths of the source files (after -i) mapped; the batch file may run where the files are
    mounted elsewhere."""
    mapped = list(command)
    for i, arg in enumerate(mapped[:-1]):
        if arg == "-i":
            mapped[i + 1] = map_path(mapped[i + 1], rules)
    return mapped


def with_extension(name: str, allowed: Iterable[str], default: str) -> str:
    """Appends `default` as extension if the name does not end with one of the `allowed` extensions."""
    return name if os.path.splitext(name)[1].lstrip(".").lower() in allowed else name + "." + default
