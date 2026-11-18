"""Run ffmpeg: read progress, cancel, check the result (port of SP_ExecuteAndWait and track)."""
from __future__ import annotations

import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Callable, Optional

import dvd
from cutlist import Job
from mediaprobe import probe
from progress import Progress, ProgressTracker


def total_seconds(job: Job) -> float:
    """Length of the output in seconds (sum of the segments)."""
    return float(sum(Fraction(s.frames) / s.fps for s in dvd.effective_segments(job.segments)))


def expected_frames(job: Job) -> int:
    """Expected number of frames of the output at the frame rate of the profile."""
    return round(sum(Fraction(s.frames) / s.fps for s in dvd.effective_segments(job.segments)) * Fraction(job.profile["fps"]))


@dataclass
class RunResult:
    returncode: int
    cancelled: bool
    elapsed: float
    errors: str                       # messages from ffmpeg (stderr; errors, and warnings if the command asks for -loglevel warning)
    progress: dict = field(default_factory=dict)      # the last block of the progress (-progress): frame, drop_frames, dup_frames, out_time_us ...

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.cancelled


def output_fps(cmd: list) -> Optional[float]:
    """The frame rate of the output as the command gives it (-r 25.000), None if it does not say (stream copy)."""
    try:
        return float(Fraction(str(cmd[cmd.index("-r") + 1]))) or None
    except (ValueError, IndexError, ZeroDivisionError):
        return None


def progress_seconds(state: dict, fps: Optional[float]) -> Optional[float]:
    """How far the output has got, in seconds, from a block of the progress of ffmpeg. From the NUMBER OF FRAMES written, when the frame rate is known (frames / rate): out_time is the
    largest time of ALL the streams, and a stream with times that run ahead (the subtitles of a DVD behind a jump in its time) made the bar jump from 41 to 84 % and stay there. Else from
    out_time_us; None as long as there is nothing ('N/A' at the beginning)."""
    frame = state.get("frame")
    if fps and frame is not None:                              # (a block with "frame=N/A" or 0 has no usable time yet: out_time may already be that of the stream that runs ahead)
        return int(frame) / fps if frame.isdigit() else None
    try:
        return int(state.get("out_time_us", "")) / 1e6
    except ValueError:
        return None


def run_ffmpeg(cmd: list[str], total: float, on_progress: Optional[Callable[[Progress], None]] = None,
               cwd: Optional[str] = None, cancel: Optional[Callable[[], bool]] = None,
               tracker: Optional[ProgressTracker] = None, poll: float = 0.2, frame_progress: bool = False) -> RunResult:
    """Starts ffmpeg, reports the progress via on_progress and waits for the end.

        `total` = length of the output in seconds. The progress comes from the machine-readable output
        (-progress pipe:1), not from the text of the status line. `cancel` is asked regularly; if it returns True,
        ffmpeg is terminated. on_progress is called in the calling thread (also suitable for GUI code,
        as long as this thread serves the user interface and processes events in between).
    """
    full = [cmd[0], "-progress", "pipe:1", "-nostats", "-loglevel", "error", *cmd[1:]]
    tracker = tracker or ProgressTracker(total)
    proc = subprocess.Popen(full, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
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

    fps = output_fps(cmd) if frame_progress else None            # (DVD mode only: the progress from the frames written; otherwise from out_time as before)

    def emit():
        done = progress_seconds(state, fps)
        if done is None:
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
    return RunResult(proc.returncode, cancelled, time.monotonic() - tracker.t0, "".join(err).strip(), dict(state))


def verify_output(path: str, expected: int, tolerance: int = 1) -> tuple[bool, int, str]:
    """Checks after the run whether the output file has the expected number of frames."""
    actual = probe(path).video.frames
    ok = abs(actual - expected) <= tolerance
    msg = (f"Frame count is correct: {actual}" if ok else
           f"Frame count differs: expected {expected}, got {actual} (check the cut or the recording)")
    return ok, actual, msg
