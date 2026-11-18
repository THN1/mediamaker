"""DVD mode: a list whose segments all come from the VOB files of one title set of a VIDEO_TS folder.

A DVD keeps a film in VTS_nn_1.VOB, VTS_nn_2.VOB, ... (nn = the title set; parts of at most 1 GB of ONE continuous program stream). VTS_nn_0.VOB (the menu of the title set) and
VIDEO_TS.VOB (the main menu) are not films and do not count. When such a list is saved (interactively or as a batch file) the program is in DVD mode, as the VB6 program was
(DVDMode()):

  * ffprobe reads the streams of the first file and the dialog for the tracks (tracks_dialog, which took the place of frmStreams) offers the sound tracks and the subtitles;
    Cancel stops saving;
  * the chosen tracks are named by their stream id (0x80 ...), not by their position, because every part is a file of its own whose streams are numbered in the order of their
    first packets: in one part of a DVD the second sound track can come first (see tracks.py);
  * ffmpeg runs with the concat filter, also if copy mode is switched on (DVD mode has precedence, as in VB6).
"""
from __future__ import annotations

import os
import re
import subprocess
import dataclasses
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional

PART = re.compile(r"^(?P<stem>.*VTS_\d\d_)(?P<part>\d+)\.vob$", re.IGNORECASE)

# ffprobe looks at the beginning of a file only for as long as its defaults allow (5 MB, 5 s of the stream); a subtitle track that does not show up before the first dialogue
# would be missing in the dialog. A DVD part is up to 1 GB: look at the first 100 MB, about the first minutes of the film.
PROBE_ARGS = ("-analyzeduration", "100M", "-probesize", "100M")


def split(path: str) -> Optional[tuple]:
    """(the path without the number of the part and the extension, the number of the part) for VTS_nn_k.VOB with k >= 1; None for every other file (also for VTS_nn_0.VOB)."""
    m = PART.match(path)
    if m is None or int(m.group("part")) < 1:
        return None
    return m.group("stem"), int(m.group("part"))


def is_dvd_structure(paths: list) -> bool:
    """Are all of these files VOB files of the same title set (the same folder, the same nn)? As in VB6: every file is .VOB, and all names are the same up to the number of the part."""
    stems = set()
    for path in paths:
        parts = split(path)
        if parts is None:
            return False
        stems.add(parts[0].lower())
    return len(stems) == 1


def title_set(path: str) -> str:
    """'VTS_02' for .../VTS_02_3.VOB ('' for other files)."""
    parts = split(path)
    return parts[0][-7:-1] if parts else ""


# ----------------------------------------------------------------------------- jumps of the time stamps inside one file
SECTOR = 2048                  # a DVD keeps a pack in every sector: a piece that starts at a sector border starts with a pack header
JUMP_BACK = 1.0                # a time stamp that goes back by more than this between two neighbouring packets of the same stream is a jump (the time starts again: a new cell);
JUMP_FORWARD = 10.0            # one that moves forward by more than this is one too (a wrapped counter)


@dataclass(frozen=True)
class Piece:
    """The part of a VOB file between two jumps of the time stamps: bytes [start_byte, end_byte), its first picture is picture number `first_picture` (counted from the beginning of the file)."""
    start_byte: int
    end_byte: int
    first_picture: int

    def url(self, path: str) -> str:
        """The piece as a file name for ffmpeg/ffprobe (protocol subfile): it opens like a file of its own whose time stamps start at the jump."""
        return f"subfile,,start,{self.start_byte},end,{self.end_byte},,:{path}"


@dataclass(frozen=True)
class Scan:
    """What one reading of all packets of a file gives: the pieces between the jumps and the byte of every picture (None: the packet has no position)."""
    pieces: list
    picture_bytes: list


_PIECES: dict = {}


def is_jump(step: float) -> bool:
    """Is this step of the time stamps between two neighbouring packets of one stream a jump? (Video and audio do not go back by seconds, nor forward by more than ten.)"""
    return step < -JUMP_BACK or step > JUMP_FORWARD


def jumps_from_packets(rows: list, kinds: dict) -> list:
    """[byte, ...]: where the jumps are in a list of packets [(stream index, time in seconds or None, byte or None)] in the order of the file. kinds: {stream index: 'video' | 'audio' |
    'data' ...}. Only video, audio and data (the navigation packs) are looked at: a subtitle stream is silent for minutes, which is no jump. The byte of a jump is the first packet of ANY
    of these streams that is behind it (one that has a byte), rounded down to the sector (the pack header)."""
    last: dict = {}
    count: dict = {}                       # stream -> number of jumps seen so far
    found: dict = {}                       # number of the jump -> its byte (None: not known yet)
    for index, time, byte in rows:
        if kinds.get(index) in (None, "subtitle"):
            continue
        if time is not None:
            if index in last and is_jump(time - last[index]):
                number = count[index] = count.get(index, 0) + 1
                found.setdefault(number, None)
                if byte is not None:
                    found[number] = byte if found[number] is None else min(found[number], byte)
            last[index] = time
        if byte is not None:
            for number, value in found.items():
                if value is None:
                    found[number] = byte
    return [byte // SECTOR * SECTOR for _, byte in sorted(found.items()) if byte is not None]


def pieces_of(path: str, ffprobe: str = "ffprobe", run=None) -> list:
    """The pieces of a file (one piece if the time stamps never jump); see scan_of."""
    return scan_of(path, ffprobe, run).pieces


def scan_of(path: str, ffprobe: str = "ffprobe", run=None) -> Scan:
    """The pieces of a file and the byte of every picture. Reads every packet of the file once with ffprobe (about 10 to 30 s for 1 GB); the result is kept for the next call
    (the same file, size and date)."""
    run = run or subprocess.run
    stat = os.stat(path)
    key = (path, stat.st_size, int(stat.st_mtime))
    if key in _PIECES:
        return _PIECES[key]
    info = run([ffprobe, "-v", "error", "-show_entries", "stream=index,codec_type", "-of", "csv=p=0", path], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    kinds = {}
    for line in info.splitlines():
        parts = line.strip().strip(",").split(",")
        if len(parts) >= 2 and parts[0].isdigit():
            kinds[int(parts[0])] = parts[1]
    out = run([ffprobe, "-v", "error", "-show_entries", "packet=stream_index,dts_time,pos", "-of", "csv=p=0", path], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout

    def number(text):
        try:
            return float(text)
        except ValueError:
            return None                    # "N/A": a packet without a time stamp or a position (counted, but nothing else)
    rows = []
    for line in out.splitlines():
        parts = line.strip().split(",")
        if len(parts) == 3 and parts[0].isdigit():
            byte = number(parts[2])
            rows.append((int(parts[0]), number(parts[1]), None if byte is None else int(byte)))
    cuts = jumps_from_packets(rows, kinds)
    pieces = []
    start = 0
    for byte in cuts:
        if byte > start:
            pieces.append((start, byte))
            start = byte
    pieces.append((start, stat.st_size))
    # the number of the first picture of every piece: the video packets in front of the jump of its time stamps (a packet without a time stamp counts as a picture)
    first = [0]
    pictures = 0
    previous = None
    picture_bytes = []
    for index, time, byte in rows:
        if kinds.get(index) != "video":
            continue
        picture_bytes.append(byte)
        if time is not None:
            if previous is not None and is_jump(time - previous):
                first.append(pictures)
            previous = time
        pictures += 1
    first = first[:len(pieces)] + [pictures] * max(0, len(pieces) - len(first))
    result = Scan([Piece(b0, b1, n) for (b0, b1), n in zip(pieces, first)], picture_bytes)
    _PIECES[key] = result
    return result


# ----------------------------------------------------------------------------- consecutive parts are ONE stream (the seam)
CONCAT = "concat:"          # the protocol of ffmpeg that joins files BYTE for BYTE; a path that starts with it is a run of several parts
CROP_TOLERANCE = 2          # the crops of two neighbouring parts may differ by this many pixels (autocrop: 13 and 14 in the parts of one film) and still be one run


def files_of(path: str) -> list:
    """The files of a path of a run ('concat:a|b|c' -> [a, b, c]); a plain path is its own list."""
    return path[len(CONCAT):].split("|") if path.startswith(CONCAT) else [path]


def mergeable(a, b) -> bool:
    """Do segment a and the next segment b continue each other across the seam of two parts of a title set? a goes to the end of its part, b begins at the first picture of the next
    part (or earlier), everything else that shapes the picture is the same. A DVD splits its stream at 1 GB in the middle of a group of pictures and of an AC3 block: read as two files
    the pictures in front of the first key frame of the next part (about one second) and the first sound block cannot be decoded and are lost; read as one stream nothing is lost."""
    pa, pb = split(files_of(a.path)[-1]), split(b.path)
    if pa is None or pb is None or pa[0].lower() != pb[0].lower() or pb[1] != pa[1] + 1:
        return False
    return (a.end >= a.total_frames and b.start <= b.first_frame and a.mask == b.mask and a.fps == b.fps and (a.width, a.height) == (b.width, b.height)
            and a.audio_sel == b.audio_sel and a.sample_rate == b.sample_rate and "|" not in b.path
            and all(abs(getattr(a, f) - getattr(b, f)) <= CROP_TOLERANCE for f in ("crop_top", "crop_bottom", "crop_left", "crop_right")))


_HEAD: dict = {}


def undecodable_head(path: str, ffprobe: str = "ffprobe", run=None, packets: int = 400) -> int:
    """How many video packets at the beginning of a part cannot be decoded when the part is read on its own: the packets before the first key frame (a part of a DVD begins in the middle
    of a group of pictures) and the B-frames behind it that show a time before the key frame (they refer to the picture in the part before). Read as one stream with the part before,
    all of them can be decoded. Only the first packets are looked at (fast, also on a network drive); 0 if the file cannot be read. This is what the program's frame numbers leave out:
    first_frame counts from the first picture that IS decoded."""
    if path in _HEAD:
        return _HEAD[path]
    run = run or subprocess.run
    count = 0
    try:
        out = run([ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+#{packets}", "-show_entries", "packet=pts_time,flags", "-of", "csv=p=0", path],
                  capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
        rows = [line.strip().split(",") for line in out.splitlines() if line.strip()]
        first_key = next((i for i, r in enumerate(rows) if len(r) > 1 and "K" in r[1]), None)
        if first_key is not None:
            try:
                key_pts = float(rows[first_key][0])
            except ValueError:
                key_pts = None
            if key_pts is not None:
                def late(row):
                    try:
                        return float(row[0]) >= key_pts - 1e-6
                    except ValueError:
                        return True            # a packet without a time stamp is counted as usable (as count_video_packets does)
                count = len(rows) - sum(1 for r in rows[first_key:] if late(r))
    except OSError:
        count = 0
    _HEAD[path] = count
    return count


def effective_segments(segments: list, path_map=None) -> list:
    """The segments as they are read: neighbours that continue each other (see mergeable) become one segment whose path is 'concat:part1|part2' and whose picture numbers run on through
    the parts. Only for a list in DVD structure; other lists come back unchanged.

    The numbers of a part count from its first picture that can be decoded ON ITS OWN (first_frame, total_frames = first_frame + decoded pictures D). Read behind the part before, the first
    U pictures (undecodable_head) of the next part can be decoded too: a part contributes U + D pictures, and the number n of a picture of part L stands at the place
    (pictures of the parts before) + U_L + (n - first_frame_L) of the run. The merged segment keeps first_frame and start of the first one; its end and total_frames are made so that
    end - start is the number of pictures of the run."""
    if not is_dvd_structure([s.path for s in segments]):
        return list(segments)
    path_map = path_map or (lambda p: p)
    result = []                         # [(segment, pictures of all parts of the run so far)]
    for seg in segments:
        if result and mergeable(result[-1][0], seg):
            first, before = result[-1]
            head = undecodable_head(path_map(seg.path))
            end = first.first_frame + before + head + (seg.end - seg.first_frame)
            after = before + head + (seg.total_frames - seg.first_frame)
            merged = dataclasses.replace(first, path=(first.path if first.path.startswith(CONCAT) else CONCAT + first.path) + "|" + seg.path, end=end, total_frames=first.first_frame + after)
            result[-1] = (merged, after)
        else:
            result.append((seg, seg.total_frames - seg.first_frame))
    return [seg for seg, _ in result]
