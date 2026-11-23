"""How long does it take to read a recording once? (No Qt.)

Subtitles come from a second input of ffmpeg (a list of the cuts for the concat demuxer, see ffmpeg_cmd.py). ffmpeg lets the picture run only as far as the
subtitle tracks have delivered packets; tracks with few or no events make it read the WHOLE recording before the first picture is made (measured: 13 GB on a NAS,
7.5 minutes without any sign of life). That cannot be avoided without a second pass, so the program says it beforehand and estimates the time here: it reads a
small piece in the middle of the file (not the beginning, which the player has read just now and may be in the cache) and divides the size of the files by the speed.
"""
from __future__ import annotations

import os
import time
from typing import Callable, Optional

SAMPLE = 4 * 1024 * 1024        # how much is read for the measurement
CHUNK = 256 * 1024
TIME_CAP = 2.0                  # seconds: a slow drive must not keep the program waiting
WARN_SECONDS = 60               # below this the wait is not worth a question


def measure(path: str, size: Optional[int] = None, opener=open, clock: Callable[[], float] = time.monotonic) -> Optional[float]:
    """The reading speed in bytes per second of the file at `path` (None if it cannot be measured)."""
    try:
        size = os.path.getsize(path) if size is None else size
        with opener(path, "rb") as fh:
            fh.seek(max(0, size // 3 - SAMPLE // 2))
            got, t0 = 0, clock()
            while got < SAMPLE and clock() - t0 < TIME_CAP:
                data = fh.read(CHUNK)
                if not data:
                    break
                got += len(data)
            elapsed = max(clock() - t0, 1e-6)
    except OSError:
        return None
    return got / elapsed if got else None


def subtitle_wait(paths, measure_fn=measure, size_fn=os.path.getsize) -> Optional[tuple]:
    """(seconds, total bytes, bytes per second) for reading all the files once; the speed is measured on the biggest one. None if it cannot be found out."""
    try:
        sizes = {p: size_fn(p) for p in dict.fromkeys(paths)}
        if not sizes:
            return None
        biggest = max(sizes, key=sizes.get)
        speed = measure_fn(biggest, sizes[biggest])
    except OSError:
        return None
    total = sum(sizes.values())
    if not speed or total <= 0:
        return None
    return total / speed, total, speed


def format_wait(seconds: float) -> str:
    """'about 40 seconds', 'about 7 minutes', 'about 2.5 hours'."""
    if seconds < 90:
        return f"about {max(10, round(seconds / 10) * 10)} seconds"
    if seconds < 90 * 60:
        return f"about {round(seconds / 60)} minutes"
    return f"about {seconds / 3600:.1f} hours"


def format_size(nbytes: float) -> str:
    return f"{nbytes / 1e9:.1f} GB" if nbytes >= 1e9 else f"{nbytes / 1e6:.0f} MB"


def warning_text(seconds: float, total: float, speed: float) -> str:
    return (f"The subtitles are taken from the whole recording ({format_size(total)}, measured speed {speed / 1e6:.0f} MB/s). ffmpeg has to read it once completely "
            f"before the picture starts: this takes {format_wait(seconds)}, and the progress bar stays at 0 % meanwhile (\"Reading subtitles...\").\n\n"
            "Save anyway? (Without subtitles the saving starts at once.)")


def dialog_text(seconds: float, total: float, speed: float) -> str:
    """The warning in the multitrack dialog while a subtitle track is chosen."""
    return (f"Subtitles are taken from the whole recording ({format_size(total)}, measured speed {speed / 1e6:.0f} MB/s): ffmpeg has to read it once completely before the picture "
            f"starts. This takes {format_wait(seconds)}, and the progress bar stays at 0 % meanwhile (\"Reading subtitles...\"). Without subtitles the saving starts at once.")
