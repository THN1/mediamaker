"""Search for the end or the start of a commercial (VB6: mnuEnd_Click / mnuNext_Click with where_border / where_logo).

The search starts with a fixed step width (options step_end / step_next in seconds; VB6: 1000 and 6000 frames at 25 FPS) and
refines it by a factor of 10 each time until it reaches 1. It runs in the background and can be cancelled.
"""
from __future__ import annotations

from typing import Optional, Callable

from PySide6 import QtCore

import numpy as np

from border import border_at, where_border
from frames import grab_numbered
from logo import bottom_line_average, confidence_at, rewind, where_logo
from player import debug_log

DEFAULT_STEP_END_S = 40              # step width for "Seek end of commercial" in seconds (VB6: 1000 frames at 25 FPS)
DEFAULT_STEP_NEXT_S = 240            # step width for "Seek next commercial" in seconds (VB6: 6000 frames at 25 FPS)


def step_seconds(opts: dict, end: bool) -> float:
    """Initial step width of a search in seconds. When looking for the next commercial the step must not exceed the minimum
    length of a commercial break (option "pause"): with a larger step a short break could fall between two probes and be
    skipped (a 165 s break is missed by a 240 s step)."""
    seconds = float(opts.get("step_end" if end else "step_next", DEFAULT_STEP_END_S if end else DEFAULT_STEP_NEXT_S))
    if not end:
        pause = float(opts.get("pause", 160))
        if pause > 0:
            seconds = min(seconds, pause)
    return seconds


def step_frames(seconds, fps) -> int:
    """Step width in frames from seconds and frame rate (at least 1)."""
    return max(1, round(float(seconds) * float(fps)))


class SeekCancelled(Exception):
    pass


CUT_SIZE = (64, 48)                  # size of the pictures used to look for a hard cut


def snap_to_cut(path, fps, pos, window, threshold, frames_fn=grab_numbered, cancel=lambda: False, shown=lambda n: n) -> int:
    """Moves a result of the border search to the hard cut right before it, if there is one.

    The border changes a little later than the picture: the first frame of a commercial may still have (almost) the border of the
    movie, then the border search is one or two frames late. Looks at the frames pos-window..pos for the latest hard cut (mean
    difference to the preceding frame of at least `threshold` on a scale of 0..255 and at least three times the usual difference)
    and returns its first frame; without such a cut `pos` stays.
    """
    note = getattr(cancel, "note", None)
    first = max(pos - window - 3, 0)             # a few frames more before the window give the usual difference
    if cancel():
        raise SeekCancelled()
    if note:
        note(f"frame {shown(pos)}: looking for a cut in the last {window} frames")
    try:
        frames = frames_fn(path, first, pos - first + 1, fps, CUT_SIZE)
    except Exception as e:                       # best effort: the unrefined result is still useful
        debug_log(f"cut search failed: {e!r}")
        return pos
    grey = {n: f.astype(np.float32).mean(axis=2) for n, f in frames.items()}
    diffs = {n: float(np.abs(grey[n] - grey[n - 1]).mean()) for n in grey if n - 1 in grey and n <= pos}
    if len(diffs) < 3:
        return pos
    usual = sorted(diffs.values())[len(diffs) // 2]
    cuts = [n for n, d in diffs.items() if pos - window <= n and d >= threshold and d >= 3 * max(usual, 1.0)]
    debug_log(f"cut search before frame {shown(pos)}: differences { {shown(n): round(d, 1) for n, d in sorted(diffs.items())} }, "
              f"cuts {[shown(n) for n in sorted(cuts)]}")
    return max(cuts) if cuts else pos


def seek_border(path, fps, total, pos, value, equal, stepping, opts, border_fn=border_at, cancel=lambda: False,
                shown=lambda n: n, frames_fn=grab_numbered, stats: Optional[dict] = None) -> int:
    """Starting at frame `pos`, searches for the first frame whose black border matches `value` (equal=True: movie starts) or
        differs from it (equal=False: commercial starts). `shown` converts frame numbers for display; every probe is reported in the
        wait window (cancel.note) and in the log.
    """
    note = getattr(cancel, "note", None)
    debug_log(f"border search from frame {shown(pos)}: looking for {'border about' if equal else 'border different from'} {value} "
              f"(tolerance {int(opts.get('border_tol', 3))}), step width {stepping}, end at {shown(total)}")

    def border_of(n: int) -> int:
        if cancel():
            raise SeekCancelled()
        found = border_fn(path, n, fps, opts)
        if stats is not None:
            stats.setdefault("borders", []).append((n, int(found)))
        text = f"frame {shown(n)}: border {found} (looking for {'about ' if equal else 'not '}{value})"
        debug_log(f"border search: {text}")
        if note:
            note(text)
        return found
    tolerance = int(opts.get("border_tol", 3))
    result = where_border(border_of, pos, total, value, equal, stepping, lim=tolerance)
    debug_log(f"border search: result frame {shown(result)}")
    window = int(opts.get("cut_window", 5))
    if window > 0:
        refined = snap_to_cut(path, fps, result, window, int(opts.get("cut_diff", 30)), frames_fn, cancel, shown)
        if refined != result:
            debug_log(f"border search: moved to the cut at frame {shown(refined)}")
        result = refined
    if stats is not None:
        stats["result"] = result
    return result


def seek_logo(path, fps, total, pos, ref, equal, stepping, opts, conf_fn=confidence_at, avg_fn=bottom_line_average,
              cancel=lambda: False, shown=lambda n: n, stats: Optional[dict] = None) -> int:
    """Like seek_border, but with the station logo: equal=True looks for the next frame WITH logo and then goes back a bit
        (the logo often appears only some seconds after the movie has started), equal=False for the next frame WITHOUT logo.
        stats (dict) receives "confidences" = [(frame, confidence)] of all frames that were examined, and "result"."""
    def check() -> None:
        if cancel():
            raise SeekCancelled()

    note = getattr(cancel, "note", None)
    debug_log(f"logo search from frame {shown(pos)}: looking for {'logo present' if equal else 'logo missing'}, step width {stepping}")

    def conf_of(n: int) -> float:
        check()
        found = conf_fn(path, n, fps, ref, opts)
        if stats is not None:
            stats.setdefault("confidences", []).append((n, float(found)))
        text = f"frame {shown(n)}: logo confidence {found:.2f}"
        debug_log(f"logo search: {text}")
        if note:
            note(text)
        return found

    max_back = round(float(opts.get("logo_rewind", 1.8)) * float(fps))
    min_conf = float(opts.get("logo_conf", 0.2))

    def rewind_fn(p: int) -> int:
        if max_back <= 0:
            return p + 1                                  # no rewinding (option logo_rewind = 0): the first frame WITH logo (p is the last one without)
        return rewind(p, lambda f: (check(), avg_fn(path, f, fps, opts))[1], max_back)

    result = where_logo(conf_of, pos, total, equal, stepping, rewind_fn, min_conf)
    debug_log(f"logo search: result frame {shown(result)}")
    if stats is not None:
        stats["result"] = result
    return result


class SeekWorker(QtCore.QThread):
    """Runs a search in the background."""

    done = QtCore.Signal(int)                       # frame found
    failed = QtCore.Signal(str)
    progress = QtCore.Signal(str)                   # intermediate result for the wait window

    def __init__(self, job: Callable[[Callable[[], bool]], int]):
        super().__init__()
        self.job = job
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def note(self, text: str) -> None:
        self.progress.emit(text)

    def run(self) -> None:
        worker = self

        class Control:                              # callable like a function (cancelled?) and with .note for messages
            def __call__(self) -> bool:
                return worker.cancelled

            def note(self, text: str) -> None:
                worker.note(text)
        try:
            result = self.job(Control())
        except SeekCancelled:
            return
        except Exception as e:                      # e.g. file not readable
            if not self.cancelled:
                self.failed.emit(str(e))
            return
        if not self.cancelled:
            self.done.emit(int(result))
