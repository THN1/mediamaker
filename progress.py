"""Progress display with percentage and estimated remaining time (port of track() and bar())."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Progress:
    percent: float                    # 0..100
    done: float                       # seconds processed so far (output length)
    total: float                      # total length of the output in seconds
    elapsed: float                    # elapsed time since the start in seconds
    speed: Optional[float] = None     # seconds of output per second of computing time (1.0 = real time), None = unknown
    eta: Optional[float] = None       # estimated remaining time in seconds, None = cannot be estimated yet
    frame: Optional[int] = None


class ProgressTracker:
    """Converts processed seconds into percent and remaining time.

        The remaining time comes from the speed of the last `window` seconds of computing time (moving
        average). It is shown only after at least `min_elapsed` seconds have passed and
        `min_percent` percent have been reached; before that the estimate would be too uncertain (start, seeking in the file).
    """

    def __init__(self, total_seconds: float, window: float = 30.0, min_elapsed: float = 3.0,
                 min_percent: float = 1.0, clock: Callable[[], float] = time.monotonic):
        self.total = max(float(total_seconds), 1e-9)
        self.window, self.min_elapsed, self.min_percent, self.clock = window, min_elapsed, min_percent, clock
        self.t0: Optional[float] = None
        self.samples: deque[tuple[float, float]] = deque()

    def start(self, now: Optional[float] = None) -> None:
        self.t0 = self.clock() if now is None else now
        self.samples.clear()
        self.samples.append((self.t0, 0.0))

    def update(self, done: float, now: Optional[float] = None, frame: Optional[int] = None) -> Progress:
        now = self.clock() if now is None else now
        if self.t0 is None:
            self.start(now)
        done = min(max(float(done), 0.0), self.total)
        self.samples.append((now, done))
        while len(self.samples) > 2 and now - self.samples[1][0] >= self.window:
            self.samples.popleft()                 # discard sampling points outside the time window
        percent = 100.0 * done / self.total
        elapsed = now - self.t0
        (t_a, d_a), (t_b, d_b) = self.samples[0], self.samples[-1]
        speed = (d_b - d_a) / (t_b - t_a) if t_b > t_a else None
        eta = None
        if done >= self.total:
            eta = 0.0
        elif speed and speed > 0 and elapsed >= self.min_elapsed and percent >= self.min_percent:
            eta = (self.total - done) / speed
        return Progress(percent, done, self.total, elapsed, speed, eta, frame)


def format_duration(seconds: float) -> str:
    """65 -> '1:05', 3725 -> '1:02:05'."""
    s = int(round(seconds))
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_progress(p: Progress, width: int = 30, message: str = "Saving") -> str:
    """A line of text like  'Saving [##########--------------------]  34.5 %  Remaining 0:42  (3.2x)'."""
    filled = int(width * p.percent / 100)
    bar = "#" * filled + "-" * (width - filled)
    eta = f"Remaining {format_duration(p.eta)}" if p.eta is not None else "Remaining: calculating"
    speed = f"  ({p.speed:.1f}x)" if p.speed else ""
    return f"{message} [{bar}] {p.percent:5.1f} %  {eta}{speed}"
