"""Baut die ffmpeg-Kommandozeile aus Schnittliste, Profil und Optionen.

Nachbau der VB6-Funktionen build(), multi(), crop(), delogo(), floor(), inc().
Unterschiede zur VB6-Version:
  * Rückgabe ist eine Argumentliste (kein String): kein Quoting-Problem mit Leerzeichen,
    Umlauten oder Anführungszeichen in Dateinamen, direkt für subprocess geeignet.
  * Zeitwerte werden mit exakten Brüchen gerechnet (Fraction) statt mit Gleitkommazahlen.
    Dadurch entfällt das 1-ms-Rauschen (z. B. 2.479 statt 2.480 bei Frame 199662 @ 25 fps).

Noch NICHT enthalten (löst NotImplementedError aus): DVD-Modus, Untertitel, Mehrsprachigkeit,
Copy-Modus. Der Rest entspricht den beiden normalen VB6-Zweigen (eine bzw. mehrere Quelldateien).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from fractions import Fraction
from functools import lru_cache
from math import floor
from typing import Callable, Optional, Union

from cutlist import Job, Segment


# ----------------------------------------------------------------------------- Startzeiten
def _start_fraction(value, default: Fraction) -> Fraction:
    """Startzeit aus der Ausgabe von ffprobe; fehlende oder unbekannte Werte ("N/A", leer) ergeben `default`."""
    try:
        return Fraction(str(value)).limit_denominator(1_000_000)
    except (ValueError, ZeroDivisionError, TypeError):
        return default


@lru_cache(maxsize=64)
def stream_times_of(path: str, ffprobe: str = "ffprobe") -> tuple[Fraction, Fraction]:
    """(Containerbeginn, Videobeginn) in Sekunden, exakt als Bruch. TV-Aufnahmen beginnen selten bei 0.

    Fehlt dem Container oder dem Videostream die Startzeit (ffprobe meldet dann "N/A"), gilt 0 bzw. der Containerbeginn.
    """
    out = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-select_streams", "v:0",
                          "-show_entries", "format=start_time:stream=start_time", path],
                         capture_output=True, check=True).stdout
    d = json.loads(out or b"{}")
    fmt = _start_fraction(d.get("format", {}).get("start_time"), Fraction(0))
    vid = _start_fraction((d.get("streams") or [{}])[0].get("start_time"), fmt)
    return fmt, vid


# ----------------------------------------------------------------------------- Zeitrechnung
def _ms_floor(x: Fraction) -> Fraction:
    return Fraction(floor(x * 1000), 1000)


def _ms_round(x: Fraction) -> Fraction:
    return Fraction(floor(x * 1000 + Fraction(1, 2)), 1000)


def fmt_seconds(x: Fraction) -> str:
    ms = int(x * 1000)
    return f"{ms // 1000}.{ms % 1000:03d}"


def split_seek(start_frame: int, fps: Fraction, preroll: int) -> tuple[int, Fraction]:
    """Teilt den Startzeitpunkt in einen groben Sprung (-ss vor -i) und einen Rest für trim.

    Der Sprung liegt `preroll` Sekunden früher (Sicherheitsabstand zum Keyframe);
    der Rest wird danach von trim exakt (auf die Millisekunde abgeschnitten) erreicht.
    """
    start = Fraction(start_frame) / fps
    seek = max(0, round(start) - preroll)       # round(): kaufmännisch wie CLng in VB6 (Bankers Rounding)
    return seek, _ms_floor(start - seek)


def trim_end(rest: Fraction, frames: int, fps: Fraction) -> Fraction:
    return _ms_round(rest + Fraction(frames) / fps)


def origin_base(start_frame: int, fps: Fraction, container_start: Fraction, video_start: Fraction,
                origin: str = "container", preroll: int = 2) -> Fraction:
    """Zeitpunkt, ab dem Bildnummern gezählt werden.

    "video"     Videobeginn (erstes Videopaket).
    "container" Containerbeginn (frühester Stream, bei TV-Aufnahmen oft der Ton).
    "vb6"       Nachbildung des VB6-Verhaltens, wie es sich mit der ffmpeg-Version des Anwenders darstellt:
                ohne -ss (Sprung 0 s) zählt trim ab Videobeginn, mit -ss ab Containerbeginn + Sprung.
                Dadurch liefert dieselbe Bildnummer bei Aufnahmen, in denen Ton und Video nicht gleichzeitig
                beginnen, je nach Position unterschiedlich verschobene Bilder (Sprung bei etwa 2,5 s).
    """
    if origin == "video":
        return video_start
    if origin == "container":
        return container_start
    if origin == "vb6":
        return video_start if split_seek(start_frame, fps, preroll)[0] == 0 else container_start
    raise ValueError(f"origin muss 'video', 'container' oder 'vb6' sein, nicht {origin!r}")


# ----------------------------------------------------------------------------- Filterteile
def _vb_idiv2(x: float) -> int:
    """VB6 '\\ 2': Operand wird zuerst gerundet, dann ganzzahlig geteilt."""
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
    # Grenzen sichern (wie inside() in VB6): a >= 1 und a + b < max
    x, y = max(x, 1), max(y, 1)
    if x + dw >= w:
        dw = w - x - 1
    if y + dh >= h:
        dh = h - y - 1
    return f"delogo=x={x}:y={y}:w={dw}:h={dh},"


def mask_name(pos: int) -> str:
    return f"removelogo{pos:02d}.png"


def video_filter(seg: Segment, pos: int, profile: dict, opts: dict,
                 trim: Optional[tuple[Fraction, Fraction]], setsar: bool) -> str:
    f = f"[{pos - 1}:v]"
    if trim:
        f += f"trim={fmt_seconds(trim[0])}:{fmt_seconds(trim[1])},"
    w, h = seg.width, seg.height
    if seg.has_png_mask:
        f += f"removelogo={mask_name(pos)},"
    elif seg.has_delogo:
        f += _delogo(seg, w, h)
    c, w, h = _crop(seg, w, h, int(opts.get("crop", 0)))
    f += c
    sw_, sh_ = (int(v) for v in profile["scale"].split(":"))
    if profile.get("pad", opts.get("pad", "False")) == "True":         # pad gehört zum Profil (früher: Optionen)
        if w * sh_ > h * sw_:
            f += f"pad={w}:{2 * _vb_idiv2(w / sw_ * sh_)}"
        else:
            f += f"pad={2 * _vb_idiv2(h / sh_ * sw_)}:{h}"
        f += ":(ow-iw)/2:(oh-ih)/2,"
    if w < h:                                    # Hochformat: seitlich auffüllen
        t = (h * sw_) // sh_
        f += f"pad={t}:ih:{t - 2 * w}:0,"
    f += f"scale={profile['scale']}" + (",setsar=1" if setsar else "") + ",setpts=PTS-STARTPTS"
    return f + f"[v{pos - 1}];"


def audio_filter(seg: Segment, pos: int, trim: Optional[tuple[Fraction, Fraction]]) -> str:
    f = f"[{pos - 1}:{seg.audio_sel}]"
    if trim:
        f += f"atrim={fmt_seconds(trim[0])}:{fmt_seconds(trim[1])},"
    return f + f"asetpts=PTS-STARTPTS[a{pos - 1}];"


# ----------------------------------------------------------------------------- Hauptfunktion
def write_masks(segments: list[Segment], directory: str) -> list[str]:
    """Schreibt die PNG-Masken (removelogoNN.png) in das Arbeitsverzeichnis von ffmpeg."""
    names = []
    for pos, seg in enumerate(segments, 1):
        if seg.has_png_mask:
            with open(os.path.join(directory, mask_name(pos)), "wb") as fh:
                fh.write(base64.b64decode(seg.mask))
            names.append(mask_name(pos))
    return names


def build_command(job: Job, ffmpeg: str = "ffmpeg", chapters_file: Optional[str] = None,
                  path_map: Callable[[str], str] = lambda p: p, unify: bool = False,
                  stream_times: Union[dict, str, None] = "auto", origin: str = "container") -> list[str]:
    """Liefert die ffmpeg-Argumentliste.

    setsar=1 wird nur bei MEHREREN Quelldateien gesetzt (nötig für concat). Bei einer einzigen
    Quelldatei bleiben SAR/DAR der Aufnahme erhalten, damit das Seitenverhältnis nicht verzerrt wird.

    unify=False: verhält sich wie VB6 (bei nur EINER Quelldatei werden Codec, Samplerate und
                 minrate/maxrate nicht gesetzt; ffmpeg-Standardwerte greifen).
    stream_times: "auto" (Standard): Start- und Videozeiten der Quellen werden mit ffprobe ermittelt und es
                 werden absolute Zeitstempel benutzt (-copyts, trim mit absoluten Zeiten); das Ergebnis hängt dann
                 nicht davon ab, wie die ffmpeg-Version -ss behandelt. Ein dict {Quellpfad: (Containerbeginn,
                 Videobeginn)} gibt die Zeiten vor. None = wie in VB6 (-ss vor -i, trim relativ dazu); das setzt
                 voraus, dass die ffmpeg-Version den Zeitnullpunkt nach -ss so legt, wie VB6 es erwartet.
    origin:      Nullpunkt der Bildnummern: "container" (Standard), "video" oder "vb6" (siehe origin_base).
    unify=True:  setzt Codec, Samplerate und minrate/maxrate auch bei nur einer Quelldatei
                 (SAR-Verhalten bleibt unverändert).
    """
    prof, opts, segs = job.profile, job.options, job.segments
    if not segs:
        raise ValueError("Schnittliste ist leer.")
    if opts.get("subtitle", "0") != "0" or opts.get("multilanguage", "False") == "True":
        raise NotImplementedError("Untertitel/Mehrsprachigkeit sind noch nicht umgesetzt.")

    if stream_times == "auto":
        stream_times = {p: stream_times_of(path_map(p)) for p in {s.path for s in segs}}
    multiple = len({s.path for s in segs}) > 1
    explicit = multiple or unify                  # Codec/Bitrate-Parameter ausführlich setzen
    preroll = int(opts.get("floor", 2))

    args = [ffmpeg, "-y", "-hide_banner"] + (["-copyts"] if stream_times else [])
    filtr = ""
    for pos, seg in enumerate(segs, 1):
        trimmed = seg.end - seg.start < seg.total_frames - seg.first_frame   # sonst: ganze Datei, kein trim
        trim = None
        if trimmed and stream_times:
            fmt0, vid0 = stream_times[seg.path]
            base = origin_base(seg.start, seg.fps, fmt0, vid0, origin, preroll)
            t0 = _ms_floor(base + Fraction(seg.start) / seg.fps)           # absoluter Startzeitpunkt
            trim = (t0, trim_end(t0, seg.frames, seg.fps))
            seek = max(0, floor(t0 - fmt0) - preroll)                      # -ss ist relativ zum Containerbeginn
            if seek > 0:
                args += ["-ss", str(seek)]
        elif trimmed:
            seek, rest = split_seek(seg.start, seg.fps, preroll)
            trim = (rest, trim_end(rest, seg.frames, seg.fps))
            if seek > 0:
                args += ["-ss", str(seek)]
        args += ["-i", path_map(seg.path)]
        filtr += video_filter(seg, pos, prof, opts, trim, setsar=multiple)
        filtr += audio_filter(seg, pos, trim)

    if chapters_file:
        args += ["-i", chapters_file, "-map_metadata", str(len(segs))]

    n = len(segs)
    if n == 1:
        filtr = filtr[:-1]                                      # kein concat nötig
        maps = ["-map", "[v0]", "-map", "[a0]"]
    else:
        filtr += "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
        maps = ["-map", "[v]", "-map", "[a]"]

    args += ["-filter_complex", filtr, *maps, "-sws_flags", prof["sws_flags"]]
    if explicit:
        args += ["-ar", prof["ar"], "-codec:a", prof["acodec_out"], "-b:a", prof["ba"],
                 "-codec:v", "libx264", "-b:v", prof["bv"],
                 "-minrate", "1000k", "-maxrate", "6000k", "-r", prof["fps"]]
    else:
        args += ["-r", prof["fps"], "-b:v", prof["bv"], "-b:a", prof["ba"]]
    args.append(job.output)
    return args
