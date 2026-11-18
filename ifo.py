"""The language codes of a DVD: the VTS_nn_0.IFO file next to the VOB files of a title set knows which language every sound track and every subtitle track has.

The VOB files carry no language (ffprobe shows none for a DVD), the IFO file does: the attributes of the audio streams (offset 0x204, 8 bytes each) and of the subtitle streams (0x256,
6 bytes each) hold a code of two letters (ISO 639-1: "de", "fr"), and the program chain of the main title says which stream NUMBER every attribute has (the stream id in the VOB is
0x80 + number for AC3, 0x20 + number for a subtitle). Layout as in libdvdread (ifo_types.h): the checks below are made with an IFO file built by the test; a real file may differ.
"""
from __future__ import annotations

import os
import struct
from typing import Optional

import languages

AUDIO_BASE = {0: 0x80, 2: 0xC0, 3: 0xC0, 4: 0xA0, 6: 0x88}           # audio format of the attribute -> the first stream id (AC3, MPEG-1, MPEG-2, LPCM, DTS)
AUDIO_FORMAT = {0: "AC3", 2: "MPEG-1", 3: "MPEG-2", 4: "LPCM", 6: "DTS"}
SUBTITLE_EXTENSION = {1: "", 2: "large", 3: "children", 5: "closed captions", 6: "large closed captions", 7: "children closed captions", 9: "forced", 13: "director's comments",
                      14: "large director's comments", 15: "children director's comments"}
AUDIO_EXTENSION = {1: "", 2: "visually impaired", 3: "director's comments", 4: "alternate director's comments"}


def ifo_path(vob_path: str) -> Optional[str]:
    """VTS_nn_0.IFO in the folder of VTS_nn_k.VOB (the name may be in any case); None if there is none."""
    import dvd
    folder, name = os.path.split(vob_path)
    parts = dvd.split(name)
    if parts is None:
        return None
    wanted = (parts[0] + "0.ifo").lower()
    try:
        for entry in os.listdir(folder or "."):
            if entry.lower() == wanted:
                return os.path.join(folder, entry)
    except OSError:
        pass
    return None


def code_of(raw: bytes) -> str:
    """The language code of two letters of an attribute as ISO 639-2 (T): 'de' -> 'deu'; '' if there is none or it is not known."""
    try:
        two = raw.decode("ascii").lower()
    except UnicodeDecodeError:
        return ""
    return languages.ONE_TO_T.get(two, "") if two.isalpha() else ""


def parse(data: bytes) -> dict:
    """{"audio": {"0x80": (code, note)}, "subtitle": {"0x20": (code, note)}} from the bytes of a VTS_nn_0.IFO; the two dictionaries are empty if it is not one."""
    result = {"audio": {}, "subtitle": {}}
    if data[:12] != b"DVDVIDEO-VTS" or len(data) < 0x356 + 6:
        return result
    audio, subtitles, wide = [], [], (data[0x200] >> 2) & 3 == 3        # the aspect ratio of the video: 3 = 16:9
    for i in range(min(data[0x203], 8)):
        a = data[0x204 + 8 * i:0x204 + 8 * i + 8]
        audio.append((a[0] >> 5, code_of(a[2:4]) if (a[0] >> 2) & 3 == 1 else "", AUDIO_EXTENSION.get(a[5], "")))
    for i in range(min(data[0x255], 32)):
        a = data[0x256 + 6 * i:0x256 + 6 * i + 6]
        subtitles.append((code_of(a[2:4]) if a[0] & 3 == 1 else "", SUBTITLE_EXTENSION.get(a[5], "")))
    audio_numbers, subtitle_numbers = list(range(len(audio))), list(range(len(subtitles)))     # without a program chain: the streams in the order of the attributes
    pgc = main_pgc(data)
    if pgc is not None:
        audio_numbers = [(struct.unpack(">H", data[pgc + 0x0C + 2 * i:pgc + 0x0E + 2 * i])[0]) for i in range(len(audio))]
        audio_numbers = [((c >> 8) & 7) if c & 0x8000 else None for c in audio_numbers]
        raw = [struct.unpack(">I", data[pgc + 0x1C + 4 * i:pgc + 0x20 + 4 * i])[0] for i in range(len(subtitles))]
        four_three = [((c >> 24) & 0x1F) if c & 0x80000000 else None for c in raw]
        widescreen = [((c >> 16) & 0x1F) if c & 0x80000000 else None for c in raw]
        # the film is 16:9: the numbers for the wide screen; a DVD that fills only the numbers for 4:3 (the one of the user: 0x80 ...) is read with those
        subtitle_numbers = widescreen if wide and any(widescreen) else four_three
    for (fmt, code, note), number in zip(audio, audio_numbers):
        if number is not None and fmt in AUDIO_BASE:
            result["audio"][f"0x{AUDIO_BASE[fmt] + number:02x}"] = (code, note)
    for (code, note), number in zip(subtitles, subtitle_numbers):
        if number is not None:
            result["subtitle"][f"0x{0x20 + number:02x}"] = (code, note)
    return result


def main_pgc(data: bytes) -> Optional[int]:
    """The offset of the longest program chain (the film) in the bytes of the IFO file, or None. VTS_PGCITI: number of chains (2 bytes), then 8 bytes for every chain, the last 4 of
    them the offset of the chain relative to the table; the playing time of a chain is 4 bytes BCD (hours, minutes, seconds, frames) at +4."""
    try:
        table = struct.unpack(">I", data[0xCC:0xD0])[0] * 2048
        count = struct.unpack(">H", data[table:table + 2])[0]
        best, best_time = None, -1
        for i in range(count):
            start = struct.unpack(">I", data[table + 8 + 8 * i + 4:table + 8 + 8 * i + 8])[0]
            pgc = table + start
            h, m, s = (((b >> 4) * 10) + (b & 15) for b in data[pgc + 4:pgc + 7])
            seconds = h * 3600 + m * 60 + s
            if seconds > best_time and pgc + 0x1C + 128 <= len(data):
                best, best_time = pgc, seconds
        return best
    except (struct.error, IndexError):
        return None


def read_languages(vob_path: str) -> dict:
    """What the IFO file next to this VOB file says (see parse); empty dictionaries if there is none or it cannot be read."""
    path = ifo_path(vob_path)
    if path is None:
        return {"audio": {}, "subtitle": {}}
    try:
        with open(path, "rb") as f:
            return parse(f.read())
    except OSError:
        return {"audio": {}, "subtitle": {}}


def video_aspect(vob_path: str) -> str:
    """The display format of the title from the IFO file next to the VOB file: "4:3" or "16:9"; "" if there is no IFO file or it says neither (0 = 4:3, 3 = 16:9)."""
    path = ifo_path(vob_path)
    if path is None:
        return ""
    try:
        with open(path, "rb") as f:
            data = f.read(0x204)
    except OSError:
        return ""
    if data[:12] != b"DVDVIDEO-VTS" or len(data) < 0x201:
        return ""
    return {0: "4:3", 3: "16:9"}.get((data[0x200] >> 2) & 3, "")


def note(vob_path: str, count: int) -> str:
    """The line for the track dialog that tells where the languages come from: `count` is what apply returned."""
    path = ifo_path(vob_path)
    if count > 0:
        return f"Languages retrieved from {os.path.basename(path)}"
    if path is None:
        import dvd
        parts = dvd.split(os.path.basename(vob_path))
        name = f"{parts[0]}0.IFO" if parts else "VTS_nn_0.IFO"
        return f"No valid IFO file found ({name}): the language codes have to be chosen by hand"
    known = read_languages(vob_path)
    if not (known["audio"] or known["subtitle"]):
        return f"No valid IFO file found ({os.path.basename(path)} cannot be read): the language codes have to be chosen by hand"
    return f"{os.path.basename(path)} gives no language for these tracks (or they have one already)"


def apply(track_list, vob_path: str) -> int:
    """Fills the language of the tracks that have none (a DVD has none in the VOB file) from the IFO file; returns how many were set. Tracks are found by their stream id."""
    known = read_languages(vob_path)
    count = 0
    for kind, tracks_of_kind in (("audio", track_list.audio), ("subtitle", track_list.subtitles)):
        for track in tracks_of_kind:
            entry = known[kind].get((track.stream_id or "").lower())
            if entry and entry[0] and not track.language:
                track.language = entry[0]
                count += 1
    return count
