"""Robuste Medienanalyse für TV-Aufnahmen (.ts) auf Basis von ffprobe.

Ersetzt die VB6-Funktion minfo() (MediaInfo). Idee: Die Frame-Anzahl wird nicht
mehr aus Dauer * FPS geraten, sondern aus den Paketen des Videostreams gezählt
(schnell, ohne Dekodierung). Alle Werte tragen eine Herkunftsangabe, damit das
Programm unsichere Werte erkennen und anzeigen kann.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

# gängige TV-Bildraten; dient nur zur Plausibilisierung von FPS-Werten
KNOWN_FPS = [Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001),
             Fraction(30), Fraction(50), Fraction(60000, 1001), Fraction(60)]


class ProbeError(Exception):
    pass


@dataclass
class VideoInfo:
    index: int
    codec: str
    width: int
    height: int
    fps: Fraction
    fps_source: str                 # 'avg_frame_rate' | 'r_frame_rate' | 'fallback'
    frames: int
    frames_source: str              # 'nb_frames' | 'packets' | 'estimated'  (packets = ab erstem Keyframe)
    duration: float                 # Sekunden
    bitrate: int                    # bit/s, 0 = unbekannt
    start_time: float = 0.0
    interlaced: bool = False
    leading_packets: int = 0         # nicht dekodierbare Pakete am Anfang (nicht mitgezählt)
    first_frame_offset: float = 0.0  # Zeit des ersten dekodierbaren Bildes ab Videobeginn (= ffmpeg-Zeit 0 beim Schneiden)


@dataclass
class AudioInfo:
    index: int                      # absoluter Stream-Index
    codec: str
    channels: int
    sample_rate: int
    bitrate: int                    # bit/s, 0 = unbekannt
    language: str = ""


@dataclass
class MediaInfo:
    path: str
    format_name: str
    duration: float
    size: int
    bitrate: int
    video: VideoInfo
    audio: list[AudioInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _run_ffprobe(args: list[str], ffprobe: str) -> dict:
    cmd = [ffprobe, "-v", "error", "-print_format", "json", *args]
    try:
        res = subprocess.run(cmd, capture_output=True, check=True)
    except FileNotFoundError as e:
        raise ProbeError(f"ffprobe nicht gefunden: {ffprobe}") from e
    except subprocess.CalledProcessError as e:
        raise ProbeError(e.stderr.decode(errors="replace").strip() or "ffprobe fehlgeschlagen") from e
    return json.loads(res.stdout or b"{}")


def _int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fraction(v: Optional[str]) -> Optional[Fraction]:
    """'25/1' -> Fraction(25); '0/0' oder Unsinn -> None."""
    if not v or "/" not in str(v):
        try:
            f = Fraction(str(v)) if v else None
        except (ValueError, ZeroDivisionError):
            return None
    else:
        try:
            f = Fraction(*[int(x) for x in str(v).split("/")])
        except (ValueError, ZeroDivisionError):
            return None
    return f if f and f > 0 else None


def _plausible(f: Optional[Fraction]) -> bool:
    return f is not None and any(abs(f - k) / k < Fraction(1, 200) for k in KNOWN_FPS)


def _pick_fps(stream: dict, interlaced: bool) -> tuple[Fraction, str]:
    avg = _fraction(stream.get("avg_frame_rate"))
    r = _fraction(stream.get("r_frame_rate"))
    # r_frame_rate meldet bei interlaced TS oft die Halbbildrate (50 statt 25)
    if _plausible(avg):
        return avg, "avg_frame_rate"
    if _plausible(r):
        return (r / 2 if interlaced and r >= 50 else r), "r_frame_rate"
    if avg or r:
        return (avg or r), "r_frame_rate"
    return Fraction(25), "fallback"


def count_video_packets(path: str, ffprobe: str = "ffprobe", on_start=None) -> tuple[int, int, float]:
    """Zählt die dekodierbaren Videobilder über die Pakete (liest die ganze Datei, dekodiert aber nicht).

    Rückgabe: (nutzbare Pakete, verworfene Pakete, PTS des ersten Keyframes).
    Nicht nutzbar sind (1) Pakete vor dem ersten Keyframe, wenn die Aufnahme mitten in einer Bildgruppe
    beginnt, und (2) führende B-Bilder direkt nach dem ersten Keyframe, deren Zeit VOR dem Keyframe liegt
    und die auf ein fehlendes Vorgängerbild verweisen. Player und Schnittprogramme zeigen diese Pakete
    nicht an. Gibt es gar keinen Keyframe, werden alle Pakete gezählt.

    on_start(prozess) erhält den gestarteten ffprobe-Prozess, damit der Aufrufer ihn bei Bedarf beenden kann
    (die Zählung dauert bei langen Aufnahmen auf einem Netzlaufwerk Minuten).
    """
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time,flags",
           "-of", "csv=p=0", path]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as e:
        raise ProbeError(f"ffprobe nicht gefunden: {ffprobe}") from e
    if on_start:
        on_start(proc)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise ProbeError(err.strip() or "ffprobe fehlgeschlagen oder abgebrochen")
    rows = [line.split(",") for line in out.splitlines() if line.strip()]
    first_key = next((i for i, r in enumerate(rows) if len(r) > 1 and "K" in r[1]), None)
    if first_key is None:
        return len(rows), 0, 0.0
    key_pts = _float(rows[first_key][0])
    usable = sum(1 for r in rows[first_key:] if _float(r[0], key_pts) >= key_pts - 1e-6)
    return usable, len(rows) - usable, key_pts


def first_frame_number(path: str, fps, ffprobe: str = "ffprobe", packets: int = 300) -> int:
    """Nummer des ersten dekodierbaren Videobildes, gezählt ab dem Containerbeginn (wie die Bildnummern im Programm).

    Beginnt in einer TV-Aufnahme der Ton früher als das Video, hat das erste Bild nicht die Nummer 0. Gelesen werden nur
    die ersten Pakete (schnell, auch auf einem Netzlaufwerk). Das erste Bild ist das erste Keyframe-Paket; B-Bilder davor
    sind nicht dekodierbar. Ohne Keyframe unter den ersten Paketen gilt der Beginn des Videostreams.
    """
    from math import floor
    from ffmpeg_cmd import stream_times_of
    container, video = stream_times_of(path)
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+#{packets}", "-show_entries",
           "packet=pts_time,flags", "-of", "csv=p=0", path]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        out = ""
    pts = video
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) > 1 and "K" in parts[1] and _float(parts[0], -1.0) >= 0:
            pts = _float(parts[0])
            break
    return max(0, floor((float(pts) - float(container)) * float(fps) + 1e-3))


def probe(path: str, ffprobe: str = "ffprobe", exact_frames: bool = True) -> MediaInfo:
    data = _run_ffprobe(["-show_format", "-show_streams", path], ffprobe)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    warnings: list[str] = []

    vstreams = [s for s in streams if s.get("codec_type") == "video"
                and not s.get("disposition", {}).get("attached_pic")]
    if not vstreams:
        raise ProbeError("Kein Videostream gefunden.")
    v = vstreams[0]

    interlaced = v.get("field_order", "progressive") not in ("progressive", "unknown", "")
    fps, fps_src = _pick_fps(v, interlaced)
    if fps_src == "fallback":
        warnings.append("Bildrate nicht erkennbar, 25 fps angenommen.")

    fmt_dur = _float(fmt.get("duration"))
    v_dur = _float(v.get("duration")) or fmt_dur
    if fmt_dur and v_dur and abs(fmt_dur - v_dur) > 2:
        warnings.append(f"Dauer weicht ab (Container {fmt_dur:.1f}s, Video {v_dur:.1f}s).")
    duration = v_dur or fmt_dur
    estimated = round(duration * float(fps)) if duration else 0

    # --- Frame-Anzahl: Metadaten > Paketzählung ab erstem Keyframe > Schätzung ---------
    frames, frames_src = _int(v.get("nb_frames")), "nb_frames"
    leading, key_pts = 0, 0.0
    if exact_frames and frames <= 0:
        frames, leading, key_pts = count_video_packets(path, ffprobe)
        frames_src = "packets"
    if frames <= 0:
        frames, frames_src = estimated, "estimated"
        warnings.append("Frame-Anzahl nur aus Dauer*FPS geschätzt.")
    elif estimated and abs(frames + leading - estimated) > max(5, 0.02 * estimated):
        warnings.append(f"Frame-Anzahl ({frames + leading}) weicht deutlich von Dauer*FPS ({estimated}) ab.")
    first_offset = max(0.0, key_pts - _float(v.get("start_time"))) if key_pts else 0.0
    if leading:
        warnings.append(f"{leading} Videopakete am Anfang (vor dem ersten Keyframe bzw. führende B-Bilder) sind "
                        f"nicht dekodierbar und nicht mitgezählt; das erste Bild erscheint bei "
                        f"{first_offset:.2f} s (ffmpeg-Zeit).")

    # --- Audio -----------------------------------------------------------------
    audio = [AudioInfo(index=s["index"], codec=s.get("codec_name", ""),
                       channels=_int(s.get("channels")), sample_rate=_int(s.get("sample_rate")),
                       bitrate=_int(s.get("bit_rate")),
                       language=s.get("tags", {}).get("language", ""))
             for s in streams if s.get("codec_type") == "audio"]

    # --- Videobitrate: Stream > Container minus Audio, minus Overhead ------------
    v_br = _int(v.get("bit_rate"))
    fmt_br = _int(fmt.get("bit_rate"))
    if not v_br and fmt_br:
        v_br = max(0, int(0.95 * (fmt_br - sum(a.bitrate for a in audio))))
        warnings.append("Videobitrate aus Container-Bitrate abgeleitet.")

    video = VideoInfo(index=v["index"], codec=v.get("codec_name", ""),
                      width=_int(v.get("width")), height=_int(v.get("height")),
                      fps=fps, fps_source=fps_src, frames=frames, frames_source=frames_src,
                      duration=duration, bitrate=v_br,
                      start_time=_float(v.get("start_time")), interlaced=interlaced,
                      leading_packets=leading, first_frame_offset=first_offset)
    return MediaInfo(path=path, format_name=fmt.get("format_name", ""), duration=fmt_dur or duration,
                     size=_int(fmt.get("size")), bitrate=fmt_br, video=video,
                     audio=audio, warnings=warnings)


if __name__ == "__main__":
    import sys
    info = probe(sys.argv[1])
    print(json.dumps(info, default=lambda o: float(o) if isinstance(o, Fraction) else o.__dict__,
                     indent=2, ensure_ascii=False))
