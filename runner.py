"""ffmpeg ausführen: Fortschritt lesen, abbrechen, Ergebnis prüfen (Nachbau von SP_ExecuteAndWait und track)."""
from __future__ import annotations

import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Optional

from cutlist import Job
from mediaprobe import probe
from progress import Progress, ProgressTracker


def total_seconds(job: Job) -> float:
    """Länge der Ausgabe in Sekunden (Summe der Segmente)."""
    return float(sum(Fraction(s.frames) / s.fps for s in job.segments))


def expected_frames(job: Job) -> int:
    """Erwartete Bildanzahl der Ausgabe bei der Bildrate des Profils."""
    return round(sum(Fraction(s.frames) / s.fps for s in job.segments) * Fraction(job.profile["fps"]))


@dataclass
class RunResult:
    returncode: int
    cancelled: bool
    elapsed: float
    errors: str                       # Fehlermeldungen von ffmpeg (stderr)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.cancelled


def run_ffmpeg(cmd: list[str], total: float, on_progress: Optional[Callable[[Progress], None]] = None,
               cwd: Optional[str] = None, cancel: Optional[Callable[[], bool]] = None,
               tracker: Optional[ProgressTracker] = None, poll: float = 0.2) -> RunResult:
    """Startet ffmpeg, meldet den Fortschritt über on_progress und wartet auf das Ende.

    `total` = Länge der Ausgabe in Sekunden. Der Fortschritt kommt aus der maschinenlesbaren Ausgabe
    (-progress pipe:1), nicht aus dem Text der Statuszeile. `cancel` wird regelmäßig gefragt; liefert es True,
    wird ffmpeg beendet. on_progress wird im aufrufenden Thread aufgerufen (auch für GUI-Code geeignet,
    solange dieser Thread die Oberfläche bedient und zwischendurch Ereignisse verarbeitet).
    """
    full = [cmd[0], "-progress", "pipe:1", "-nostats", "-loglevel", "error", *cmd[1:]]
    tracker = tracker or ProgressTracker(total)
    proc = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    lines: queue.Queue = queue.Queue()
    err: list[str] = []

    def pump(stream, put):
        for line in stream:
            put(line)

    readers = [threading.Thread(target=pump, args=(proc.stdout, lines.put), daemon=True),
               threading.Thread(target=pump, args=(proc.stderr, err.append), daemon=True)]
    for t in readers:
        t.start()

    state: dict[str, str] = {}
    cancelled = False
    tracker.start()

    def emit():
        try:
            done = int(state.get("out_time_us", "")) / 1e6
        except ValueError:
            return                                             # zu Beginn "N/A"
        frame = int(state["frame"]) if state.get("frame", "").isdigit() else None
        if on_progress:
            on_progress(tracker.update(done, frame=frame))

    def handle(line: str):
        key, _, val = line.strip().partition("=")
        state[key] = val
        if key == "progress":                                  # Ende eines Meldungsblocks
            emit()

    while True:
        try:
            handle(lines.get(timeout=poll))
        except queue.Empty:
            pass
        if cancel and cancel():
            proc.terminate()
            cancelled = True
            break
        if proc.poll() is not None and lines.empty() and not readers[0].is_alive():
            break
    proc.wait()
    for t in readers:
        t.join(timeout=2)
    while not lines.empty():
        handle(lines.get_nowait())
    if proc.returncode == 0 and not cancelled and on_progress:
        on_progress(tracker.update(total))                     # 100 % melden
    return RunResult(proc.returncode, cancelled, time.monotonic() - tracker.t0, "".join(err).strip())


def verify_output(path: str, expected: int, tolerance: int = 1) -> tuple[bool, int, str]:
    """Prüft nach dem Lauf, ob die Ausgabedatei die erwartete Bildanzahl hat."""
    actual = probe(path).video.frames
    ok = abs(actual - expected) <= tolerance
    msg = (f"Bildanzahl stimmt: {actual}" if ok else
           f"Bildanzahl weicht ab: erwartet {expected}, erhalten {actual} (Schnitt oder Aufnahme prüfen)")
    return ok, actual, msg
