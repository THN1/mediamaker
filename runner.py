"""Run ffmpeg: read progress, cancel, check the result (port of SP_ExecuteAndWait and track)."""
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
    """Length of the output in seconds (sum of the segments)."""
    return float(sum(Fraction(s.frames) / s.fps for s in job.segments))


def expected_frames(job: Job) -> int:
    """Expected number of frames of the output at the frame rate of the profile."""
    return round(sum(Fraction(s.frames) / s.fps for s in job.segments) * Fraction(job.profile["fps"]))


@dataclass
class RunResult:
    returncode: int
    cancelled: bool
    elapsed: float
    errors: str                       # error messages from ffmpeg (stderr)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.cancelled


def run_ffmpeg(cmd: list[str], total: float, on_progress: Optional[Callable[[Progress], None]] = None,
               cwd: Optional[str] = None, cancel: Optional[Callable[[], bool]] = None,
               tracker: Optional[ProgressTracker] = None, poll: float = 0.2) -> RunResult:
    """Starts ffmpeg, reports the progress via on_progress and waits for the end.

        `total` = length of the output in seconds. The progress comes from the machine-readable output
        (-progress pipe:1), not from the text of the status line. `cancel` is asked regularly; if it returns True,
        ffmpeg is terminated. on_progress is called in the calling thread (also suitable for GUI code,
        as long as this thread serves the user interface and processes events in between).
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
            return                                             # "N/A" at the beginning
        frame = int(state["frame"]) if state.get("frame", "").isdigit() else None
        if on_progress:
            on_progress(tracker.update(done, frame=frame))

    def handle(line: str):
        key, _, val = line.strip().partition("=")
        state[key] = val
        if key == "progress":                                  # end of a message block
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
        on_progress(tracker.update(total))                     # report 100 %
    return RunResult(proc.returncode, cancelled, time.monotonic() - tracker.t0, "".join(err).strip())


def verify_output(path: str, expected: int, tolerance: int = 1) -> tuple[bool, int, str]:
    """Checks after the run whether the output file has the expected number of frames."""
    actual = probe(path).video.frames
    ok = abs(actual - expected) <= tolerance
    msg = (f"Frame count is correct: {actual}" if ok else
           f"Frame count differs: expected {expected}, got {actual} (check the cut or the recording)")
    return ok, actual, msg
