"""Audio and subtitle tracks of the new file (option multitrack): the choice, how it is kept in a job, and the model behind the dialog.

The choice says which tracks of the source file go into the new file, in which order, and which language code each one gets:

    audio_tracks = "0:deu,3:mis"        (ffmpeg's 0:a:INDEX, then the code; the first one is the main track)
    subtitle_tracks = "2:fra,1:deu"     (0:s:INDEX; the teletext tracks are counted in the index, but cannot be chosen)

The two entries are part of the OPTIONS OF THE JOB, not of the settings: the batch file, a session and the import carry them, the INI file never holds them.
Without them (the option is off, or Cancel in the dialog) only the main audio track is processed, and no subtitles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import containers
import languages
from mediaprobe import Track, TrackList

AUDIO_KEY, SUBTITLE_KEY = "audio_tracks", "subtitle_tracks"
KEYS = (AUDIO_KEY, SUBTITLE_KEY)


def _parse(text: str) -> list:
    out = []
    for part in str(text or "").split(","):
        index, _, lang = part.strip().partition(":")
        if index.strip().isdigit():
            out.append((int(index), lang.strip().lower()))
    return out


def _join(items: list) -> str:
    return ",".join(f"{i}:{lang}" for i, lang in items)


@dataclass
class Choice:
    audio: list = field(default_factory=list)          # [(index of the audio stream, language code or "")]
    subtitles: list = field(default_factory=list)      # [(index of the subtitle stream, language code or "")]

    def options(self) -> dict:
        """The entries for the options of the job."""
        out = {}
        if self.audio:
            out[AUDIO_KEY] = _join(self.audio)
        if self.subtitles:
            out[SUBTITLE_KEY] = _join(self.subtitles)
        return out

    @staticmethod
    def from_options(options: dict) -> Optional["Choice"]:
        """None if the options hold neither entry (then only the main audio track is processed)."""
        choice = Choice(_parse(options.get(AUDIO_KEY, "")), _parse(options.get(SUBTITLE_KEY, "")))
        return choice if choice else None

    def __bool__(self) -> bool:
        return bool(self.audio or self.subtitles)


def strip(options: dict) -> dict:
    """The options without the entries of a choice."""
    return {k: v for k, v in options.items() if k not in KEYS}


def language_for(track: Track) -> str:
    """The code that a track has in the file, as ISO 639-2 T ('' if the file has none or one that does not exist)."""
    return languages.normalize(track.language) or ""


def default_choice(tracks: TrackList, main_audio: int = 0) -> Choice:
    """What the dialog starts with: the audio tracks with the main one first, then the others in their order; all subtitle tracks in their order."""
    order = [t for t in tracks.audio if t.index == main_audio] + [t for t in tracks.audio if t.index != main_audio]
    return Choice([(t.index, language_for(t)) for t in order], [(t.index, language_for(t)) for t in tracks.subtitles])


def fits(choice: Choice, tracks: TrackList) -> bool:
    """Does every track of the choice exist in this file?"""
    return (all(any(t.index == i for t in tracks.audio) for i, _ in choice.audio)
            and all(any(t.index == i for t in tracks.subtitles) for i, _ in choice.subtitles))


def needs_dialog(tracks: TrackList) -> bool:
    """Is there anything to choose: more than one audio track, or any subtitle track (without teletext)."""
    return len(tracks.audio) > 1 or bool(tracks.subtitles)


# ----------------------------------------------------------------------------- What the command takes from the choice
@dataclass
class Streams:
    """What the ffmpeg command needs from the choice and the file type of the new file."""
    audio: list = field(default_factory=list)          # [(index, language)]; empty: only the main audio track of the segment
    subtitles: list = field(default_factory=list)      # [(index, language, codec of the source, value of -c:s)]
    canvas: bool = False                               # a bitmap subtitle is converted: -canvas_size (the size of the picture) before the input

    def codecs(self) -> list:
        return [s[2] for s in self.subtitles]


def streams_for(options: dict, output: str, tracks: Optional[TrackList]) -> Streams:
    """The streams of the new file from the options of the job (no choice: an empty result). `tracks` (of the first source file) is needed for subtitles."""
    choice = Choice.from_options(options)
    if choice is None:
        return Streams()
    subtitles = []
    for index, lang in choice.subtitles:
        t = next((t for t in (tracks.subtitles if tracks else []) if t.index == index), None)
        if t is None:
            raise ValueError(f"The source file has no subtitle track with the index {index}.")
        value, _, error = containers.subtitle_plan(output, t.codec)
        if error:
            raise ValueError(error)
        subtitles.append((index, lang, t.codec, value))
    return Streams(list(choice.audio), subtitles, any(s[3] == "dvdsub" for s in subtitles))


def metadata_args(streams: Streams, output: str) -> list:
    """-metadata:s:a:N language=xxx for every track with a code (an AVI file has no field for it: the name of the track gets the code)."""
    key = "title" if (containers.info(output) and containers.info(output).ext == "avi") else "language"
    args = []
    for k, (_, lang) in enumerate(streams.audio):
        if lang:
            args += [f"-metadata:s:a:{k}", f"{key}={lang}"]
    for k, (_, lang, _, _) in enumerate(streams.subtitles):
        if lang:
            args += [f"-metadata:s:s:{k}", f"language={lang}"]
    return args


def subtitle_codec_args(streams: Streams) -> list:
    return [x for k, s in enumerate(streams.subtitles) for x in (f"-c:s:{k}", s[3])]


# ----------------------------------------------------------------------------- Texts
_CODEC_NAMES = {"dvb_subtitle": "DVB subtitle", "dvd_subtitle": "DVD subtitle", "subrip": "SubRip", "ass": "ASS", "ssa": "SSA", "webvtt": "WebVTT", "mov_text": "MOV text",
                "hdmv_pgs_subtitle": "PGS subtitle", "xsub": "XSUB"}
_CHANNELS = {1: "mono", 2: "stereo", 6: "5.1", 8: "7.1"}


def language_name(track: Track) -> str:
    code = language_for(track)
    if code in ("", "und"):
        return "language not given"
    if code in ("mis", "mul", "zxx"):
        return {"mis": "uncoded", "mul": "multiple languages", "zxx": "no language"}[code]
    return languages.name_of(code) or code


def label(track: Track) -> str:
    """The line for a track in the lists of the dialog: '1 · German · MP2 stereo, 192 kb/s' / '2 · French · DVB subtitle, hearing impaired'."""
    parts = [str(track.number), language_name(track)]
    if track.kind == "audio":
        detail = f"{track.codec.upper()} {_CHANNELS.get(track.channels, f'{track.channels} ch') if track.channels else ''}".strip()
        if track.bitrate:
            detail += f", {track.bitrate // 1000} kb/s"
        parts.append(detail)
        if track.hearing_impaired:
            parts[-1] += ", hearing impaired"
    else:
        detail = _CODEC_NAMES.get(track.codec, track.codec)
        if track.hearing_impaired:
            detail += ", hearing impaired"
        parts.append(detail)
    return " · ".join(parts)


def note(track: Track) -> str:
    """The text in the column 'Note': what the file says about the track."""
    if track.audio_description:
        return "audio description"
    if track.hearing_impaired:
        return "hearing impaired"
    return ""


def banner(kind: str, output: str) -> str:
    """The information under the list: what the file type of the new file means for these tracks."""
    c = containers.info(output)
    ext = c.ext if c else ""
    if kind == "audio":
        if ext == "avi":
            return "An AVI file has no field for the language of a track: the code is written into the name of the track."
        return f"A .{ext} file keeps the language code with each track." if ext else ""
    if ext == "mp4":
        return ("DVB subtitles are images of the text, shown at the bottom of the picture. MP4 cannot hold them as they are, so they are converted to dvd_subtitle (VobSub); "
                "text subtitles become mov_text.")
    if ext == "mkv":
        return "MKV holds every kind of subtitle as it is."
    if ext == "ts":
        return "TS holds only DVB subtitles, as they are."
    if ext == "avi":
        return "AVI cannot hold subtitles at all: choose another file type, or leave all positions unused."
    return ""


# ----------------------------------------------------------------------------- The model of the dialog
@dataclass
class Row:
    track: Optional[int] = None        # Track.index of the chosen track, None = "-" (unused)
    language: str = ""


class TracksModel:
    """What the dialog shows and what the user has changed, without any widget (so it can be tested). `kind` is "audio" or "subtitle"."""

    def __init__(self, tracks: TrackList, output: str, initial: Optional[Choice] = None, main_audio: int = 0):
        self.tracks, self.output = tracks, output
        choice = initial if initial and fits(initial, tracks) else default_choice(tracks, main_audio)
        self.rows = {"audio": [Row(i, lang) for i, lang in choice.audio], "subtitle": [Row(i, lang) for i, lang in choice.subtitles]}
        for kind in self.rows:                                  # as many positions as there are tracks (the rest unused)
            while len(self.rows[kind]) < len(self.of(kind)):
                self.rows[kind].append(Row())

    def of(self, kind: str) -> list:
        return self.tracks.audio if kind == "audio" else self.tracks.subtitles

    def track(self, kind: str, index: Optional[int]) -> Optional[Track]:
        return next((t for t in self.of(kind) if t.index == index), None)

    def position_label(self, kind: str, row: int) -> str:
        if kind == "audio":
            return "Main track" if row == 0 else f"{row + 1}{'nd' if row == 1 else 'rd' if row == 2 else 'th'} track"
        return f"{row + 1}{'st' if row == 0 else 'nd' if row == 1 else 'rd' if row == 2 else 'th'} subtitle"

    def track_labels(self, kind: str) -> list:
        """The entries of the list of a position: '-' first, then the tracks in their order."""
        return ["-"] + [label(t) for t in self.of(kind)]

    def selected(self, kind: str, row: int) -> int:
        """Position in track_labels() of what the row has chosen."""
        index = self.rows[kind][row].track
        return 0 if index is None else 1 + next(n for n, t in enumerate(self.of(kind)) if t.index == index)

    def select(self, kind: str, row: int, position: int) -> None:
        """The user chose entry `position` of track_labels() for the row: 0 = unused. The language becomes the one the track has in the file."""
        if position <= 0:
            self.rows[kind][row] = Row()
            return
        t = self.of(kind)[position - 1]
        self.rows[kind][row] = Row(t.index, language_for(t))

    def set_language(self, kind: str, row: int, text: str) -> None:
        self.rows[kind][row].language = text.strip()

    def language_choices(self, kind: str) -> list:
        """The codes that the source file has for these tracks (once each, in their order), for the drop-down list of the language."""
        out = []
        for t in self.of(kind):
            code = language_for(t)
            if code and code not in out:
                out.append(code)
        return out

    def note(self, kind: str, row: int) -> str:
        t = self.track(kind, self.rows[kind][row].track)
        return note(t) if t else ""

    def result_text(self, kind: str, row: int) -> str:
        """Subtitles: what the new file gets ('converted to dvd_subtitle'); the error text if the file type cannot hold it."""
        t = self.track(kind, self.rows[kind][row].track)
        if kind != "subtitle" or t is None:
            return ""
        _, text, error = containers.subtitle_plan(self.output, t.codec)
        return text or error

    def language_error(self, kind: str, row: int) -> str:
        r = self.rows[kind][row]
        if r.track is None or not r.language:
            return ""
        if languages.normalize(r.language):
            return ""
        hint = languages.suggestion(r.language)
        return f"“{r.language}” is not a language code of ISO 639-2" + (f" (did you mean {hint}?)" if hint else "") + "."

    def errors(self) -> list:
        """What stops OK: a language code that does not exist, a track chosen twice, a subtitle track that the file type cannot hold."""
        out = []
        for kind in ("audio", "subtitle"):
            seen = []
            for row, r in enumerate(self.rows[kind]):
                e = self.language_error(kind, row)
                if e:
                    out.append(e)
                if r.track is not None:
                    if r.track in seen:
                        t = self.track(kind, r.track)
                        out.append(f"{'Audio' if kind == 'audio' else 'Subtitle'} track {t.number} is used twice.")
                    seen.append(r.track)
                    if kind == "subtitle":
                        error = containers.subtitle_plan(self.output, self.track(kind, r.track).codec)[2]
                        if error and error not in out:
                            out.append(error)
        if not any(r.track is not None for r in self.rows["audio"]) and self.tracks.audio:
            out.append("At least one audio track is needed.")
        return out

    def choice(self) -> Choice:
        def collect(kind):
            return [(r.track, languages.normalize(r.language) or "") for r in self.rows[kind] if r.track is not None]
        return Choice(collect("audio"), collect("subtitle"))
