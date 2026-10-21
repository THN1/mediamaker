"""Einzelbild aus einer Aufnahme holen (Nachbau von oneframe() ohne temporäre BMP-Datei).

Adressierung: Bild n ist das Bild zum Zeitpunkt  Videobeginn + n / fps  (origin="video"),
Containerbeginn + n / fps (origin="container", Standard) oder nach dem Muster von VB6 (origin="vb6", siehe
origin_base()). Der Sprung per -ss ist nur eine Beschleunigung;
das Zielbild wird mit absoluten Zeitstempeln (-copyts + trim) bestimmt. Dadurch hängt das Ergebnis
nicht davon ab, wie die jeweilige ffmpeg-Version -ss und Startzeiten behandelt (siehe check_seek.py).
"""
from __future__ import annotations

import io
import re
import subprocess
from fractions import Fraction
from math import floor

import numpy as np
from PIL import Image

from ffmpeg_cmd import fmt_seconds, origin_base, stream_times_of


stream_times = stream_times_of      # Name für ältere Aufrufer


def frame_time(frame: int, fps: Fraction, times: tuple[Fraction, Fraction], origin: str = "container",
               preroll: int = 2) -> Fraction:
    """Absoluter Zeitstempel (Sekunden, auf Millisekunden abgeschnitten) von Bild `frame`."""
    t = origin_base(frame, fps, times[0], times[1], origin, preroll) + Fraction(frame) / fps
    return Fraction(floor(t * 1000), 1000)


def seek_before(target: Fraction, container_start: Fraction, preroll: int) -> int:
    """Ganze Sekunden für -ss (relativ zum Containerbeginn), `preroll` Sekunden vor dem Ziel."""
    return max(0, floor(target - container_start) - preroll)


def grab_frame(path: str, frame: int, fps: Fraction, preroll: int = 2, ffmpeg: str = "ffmpeg",
               origin: str = "container") -> np.ndarray:
    """Liefert Bild `frame` als RGB-Array (Höhe x Breite x 3, Zeile 0 = OBERE Bildkante)."""
    times = stream_times_of(path)
    t = frame_time(frame, fps, times, origin, preroll)
    d = seek_before(t, times[0], preroll)
    cmd = [ffmpeg, "-v", "error", "-hide_banner", "-copyts"]
    if d > 0:
        cmd += ["-ss", str(d)]
    cmd += ["-i", path, "-filter_complex", f"[0:v]trim=start={fmt_seconds(t)},setpts=PTS-STARTPTS[v]",
            "-frames:v", "1", "-map", "[v]", "-f", "image2pipe", "-c:v", "png", "-"]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0 or not res.stdout:
        raise RuntimeError(f"Bild {frame} konnte nicht gelesen werden: {res.stderr.decode(errors='replace')[-300:]}")
    return np.asarray(Image.open(io.BytesIO(res.stdout)).convert("RGB"))


def grab_window(path: str, first: int, count: int, fps: Fraction, size: tuple[int, int] = (180, 144),
                preroll: int = 2, ffmpeg: str = "ffmpeg", origin: str = "container") -> tuple[int, np.ndarray]:
    """Holt `count` aufeinanderfolgende Bilder ab Bild `first` in einem Aufruf, verkleinert auf `size`.

    Rückgabe: (Nummer des ersten gelieferten Bildes, Array Anzahl x Höhe x Breite x 3). Beginnt das Fenster vor
    dem Dateianfang, wird bei Bild 0 begonnen; am Dateiende können weniger Bilder kommen.
    """
    first = max(0, first)
    times = stream_times_of(path)
    t = frame_time(first, fps, times, origin, preroll)
    d = seek_before(t, times[0], preroll)
    w, h = size
    cmd = [ffmpeg, "-v", "error", "-hide_banner", "-copyts"] + (["-ss", str(d)] if d > 0 else []) + [
        "-i", path, "-filter_complex", f"[0:v]trim=start={fmt_seconds(t)},setpts=PTS-STARTPTS,scale={w}:{h}:flags=area[v]",
        "-frames:v", str(count), "-map", "[v]", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    res = subprocess.run(cmd, capture_output=True)
    n = len(res.stdout) // (w * h * 3)
    return first, np.frombuffer(res.stdout[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def grab_numbered(path: str, first: int, count: int, fps: Fraction, size: tuple, preroll: int = 2,
                  ffmpeg: str = "ffmpeg", on_start=None) -> dict:
    """Holt bis zu `count` aufeinanderfolgende Bilder ab Bild `first` (Nummern ab Containerbeginn) in einem Aufruf.

    Rückgabe: {Bildnummer: Array Höhe x Breite x 3}, verkleinert auf `size` = (Breite, Höhe). Die Nummer jedes Bildes wird aus
    seinem Zeitstempel bestimmt, nicht aus der Reihenfolge. Liegt `first` vor dem ersten Bild der Datei (Aufnahmen, in denen der
    Ton früher beginnt als das Video) oder hinter dem Ende, fehlen die entsprechenden Nummern im Ergebnis.
    on_start(prozess) erhält den ffmpeg-Prozess, damit der Aufrufer ihn abbrechen kann.
    """
    times = stream_times_of(path)
    first = max(0, first)
    t = frame_time(first, fps, times, "container", preroll)
    d = seek_before(t, times[0], preroll)
    w, h = size
    cmd = [ffmpeg, "-v", "info", "-hide_banner", "-nostats", "-copyts"] + (["-ss", str(d)] if d > 0 else []) + [
        "-i", path, "-filter_complex",
        f"[0:v]trim=start={fmt_seconds(t)},showinfo,setpts=PTS-STARTPTS,scale={w}:{h}:flags=area[v]",
        "-frames:v", str(count), "-map", "[v]", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if on_start:
        on_start(proc)
    out, err = proc.communicate()
    if proc.returncode != 0 and not out:
        raise RuntimeError(f"Bilder konnten nicht gelesen werden: {err.decode(errors='replace')[-300:]}")
    pts = [float(x) for x in re.findall(r"pts_time:\s*(-?[0-9.]+)", err.decode(errors="replace"))]
    n = len(out) // (w * h * 3)
    frames = np.frombuffer(out[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)
    container, rate = float(times[0]), float(fps)
    return {floor((pts[i] - container) * rate + 1e-3): frames[i] for i in range(min(n, len(pts)))}
