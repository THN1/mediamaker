"""Batch files and file names (VB6: mnuBatch_Click, wenc, lvwSave, suggest).

A batch file is a shell script that cuts one job with ffmpeg. Besides the commands it carries the whole job as comments so that
it can be read again later ("Import"): J= the output file, P= the profile, T= the options and C= the segment list as CSV, and K= the chapters
(only if there are valid ones) and M=copy (copy mode was on: the job is saved without re-encoding, see copymode.py). P, T, C and K are the text encoded as UTF-16LE
and Base64, in lines of 72 characters (as VB6 wrote them). Masks for the removelogo filter, the chapters file and, in copy mode, the list of files for the concat
demuxer are created in the script itself, when it runs (also when the program has been closed long before), and removed afterwards.
"""
from __future__ import annotations

import base64
import binascii
import os
import re

import containers
from dataclasses import dataclass
from typing import Iterable, Optional

from cutlist import Job, Segment
from project import format_hms
from settings import format_kv

SHEBANG = "#!/bin/bash"
LINE = 72                                    # characters of encoded text per line
CLEANUP = "rm removelogo??.png 2>/dev/null"
OUTPUT_EXTENSIONS = containers.EXTENSIONS
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


CHAPTERS_END = "MEDIAMAKER_CHAPTERS_END"
LIST_END = "MEDIAMAKER_LIST_END"
COPY_MARK = "# M=copy"


def chapters_temp(output: str) -> str:
    """Where the script writes the chapters file while it runs: next to the target file (its folder can be written to anyway)."""
    return output + ".chapters.tmp"


def list_temp(output: str) -> str:
    """Where the script writes the list of files for the concat demuxer (copy mode) while it runs: next to the target file."""
    return output + ".files.tmp"


def job_lines(job: Job, command: list[str], chapters: Optional[str] = None, chapters_run: Optional[str] = None, copy_list: Optional[str] = None,
              copy_mode: bool = False) -> list[str]:
    """The lines of one job: comments with the whole job, masks, the files that the call needs, the ffmpeg call, clean-up.
    `chapters` is the text of the chapters file as it is kept in the program (the comment K= for a later import); `chapters_run` the text that the
    script writes for ffmpeg (it is the same, unless copy mode made other times: the whole files); the command then has to read chapters_temp(output).
    `copy_mode`: M=copy, no masks (copy mode has no filters); `copy_list`: the text of the list of files (the command then has to read list_temp(output))."""
    lines = [f"# J={job.output}"]
    lines += encode_block("P", format_kv(job.profile))
    lines += encode_block("T", format_kv(job.options))
    lines += encode_block("C", segments_to_csv(job.segments))
    if chapters:
        lines += encode_block("K", chapters)
    if copy_mode:
        lines.append(COPY_MARK)
    else:
        for i, seg in enumerate(job.segments, 1):
            if seg.has_png_mask:
                lines.append(f'base64 -d <<< "{seg.mask}" > removelogo{i:02d}.png')
    temps = []
    for text, path, end in ((copy_list, list_temp(job.output), LIST_END), (chapters_run if chapters_run is not None else chapters, chapters_temp(job.output), CHAPTERS_END)):
        if text:
            lines.append(f"cat > {bash_quote(path)} <<'{end}'")
            lines += text.rstrip("\n").split("\n")
            lines.append(end)
            temps.append(path)
    lines.append(command_line(command))
    lines.append(CLEANUP)
    for path in temps:
        lines.append(f"rm -f {bash_quote(path)}")
    return lines


@dataclass
class BatchJob:
    """A job that was read from a batch file (the comments J, P, T and C)."""
    number: int
    output: str
    profile: str = ""            # text of the profile: key="value" ...
    options: str = ""            # text of the options
    csv: str = ""                # the segment list as CSV
    chapters: str = ""           # the chapters file (empty if the job had no chapters)
    copy_mode: bool = False      # the job was made in copy mode
    error: str = ""              # not empty: the job cannot be imported

    def describe(self) -> str:
        """Line for the list of jobs (VB6: \"Job1:<output file>\")."""
        return f"Job{self.number}: {self.output}" + (f"   (damaged: {self.error})" if self.error else "")


def decode_block(chunks: list) -> str:
    """The text from the lines of one comment block (Base64 of UTF-16LE); the empty text if there are no lines."""
    data = "".join(chunks)
    return base64.b64decode(data, validate=True).decode("utf-16le") if data else ""


def parse_jobs(text: str) -> list:
    """All jobs of a batch file, whether they are switched off (REMed with '# ') or not: their comments are the same. A job begins with the
    line '# J=<output file>' and has the blocks P (profile), T (options) and C (segment list)."""
    jobs: list = []
    current, blocks = None, {}

    def close() -> None:
        if current is None:
            return
        try:
            current.profile, current.options, current.csv, current.chapters = (decode_block(blocks.get(k, [])) for k in ("P", "T", "C", "K"))
            for key, label in (("P", "profile"), ("C", "segment list")):
                if not blocks.get(key):
                    raise ValueError(f"no {label}")
        except (binascii.Error, UnicodeDecodeError, ValueError) as e:
            current.error = str(e) if isinstance(e, ValueError) and not isinstance(e, binascii.Error) else "the text cannot be decoded"
        jobs.append(current)

    for line in text.splitlines():
        if line.startswith("# J="):
            close()
            current, blocks = BatchJob(number=len(jobs) + 1, output=line[4:].strip()), {}
        elif current is not None and line.strip() == COPY_MARK:
            current.copy_mode = True
        elif current is not None and line[:4] in ("# P=", "# T=", "# C=", "# K="):
            blocks.setdefault(line[2], []).append(line[4:].strip())
    close()
    return jobs


def build_script(job: Job, command: list[str], old_text: Optional[str] = None, chapters: Optional[str] = None, chapters_run: Optional[str] = None,
                 copy_list: Optional[str] = None, copy_mode: bool = False) -> str:
    """Text of the batch file. With `old_text` (the existing file) its earlier jobs are kept but switched off: every line that is
    not a comment gets '# ' in front (the comments stay, so the old jobs can still be imported)."""
    lines = [SHEBANG]
    if old_text:
        old = old_text.splitlines()
        if old and old[0].startswith("#!"):
            old = old[1:]
        lines += [line if line.startswith("#") else "# " + line for line in old]
    lines += job_lines(job, command, chapters, chapters_run, copy_list, copy_mode)
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
