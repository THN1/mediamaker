"""Removing a duplicate scene at the cut between two segments (Edit => Dedup scene, Ctrl+F8; VB6: mnuDeDup_Click with match() and far(); it was
called "Overlap segments" at first; the option was `overlap` and is `dedup` now).

If a broadcaster repeats the last seconds of the movie after the commercials, the end of one segment and the start of the next show the same
pictures. Marker B (end) of the first and marker A (start) of the second segment are then moved towards each other, one frame at a time,
alternately (B back, A forward), until the picture at B equals the picture at A. At that point the repeated part has been cut in the middle
and the cut is clean: the first segment ends just before the picture that the second segment begins with.

A picture is compared with the other by ONE line in the middle of the picture, from 20 % to 80 % of its width (no disturbances at the
edges, no logos at the top and the bottom). The pictures are equal if no colour value (R, G or B) of the line is `far` from the other
one (VB6: far(a, b) = (a - b) \\ 24 > 0, i.e. a difference of 24 or more).

The two example segments (a recording that repeats 8.8 s) were measured: of the 222 pairs that really belong together 219 pass this test
(the others have single pixels that differ by up to 32), and pairs that are one frame apart pass in only 2.5 %. Over 6156 starting positions of
the markers the search found the right pair every time, so the test stayed as it is in VB6.
"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np

FAR = 24                      # colour values that differ by this much or more are "far" (VB6)
FROM, TO = 0.2, 0.8           # the part of the line that is compared


def far(a: int, b: int) -> bool:
    """Are two colour values (0..255) far from each other? (VB6: (a - b) \\ 24 > 0)"""
    return abs(int(a) - int(b)) // FAR > 0


def scan_range(width: int) -> tuple:
    """First and last pixel (both included) of the compared part of the line, as in the VB6 loop `For x = 0.2 * w To 0.8 * w`."""
    return round(FROM * width), int(TO * width)


def scan_row(height: int) -> int:
    """The line in the middle of the picture (VB6: y = h \\ 2)."""
    return height // 2


def lines_match(line1: np.ndarray, line2: np.ndarray) -> bool:
    """Are two lines (arrays width x 3, or 1 x width x 3) equal: is no colour value of one far from that of the other?"""
    a, b = np.asarray(line1, dtype=np.int16).reshape(-1, 3), np.asarray(line2, dtype=np.int16).reshape(-1, 3)
    return a.shape == b.shape and not bool((np.abs(a - b) // FAR > 0).any())


def frames_needed(b: int, a: int, limit: int) -> tuple:
    """The frames that the search can look at: (first, last) of the first segment (counting down from marker B) and of the second one
    (counting up from marker A) for at most `limit` steps."""
    return (b - limit // 2, b), (a, a + (limit - 1) // 2)


def search(line1: Callable[[int], Optional[np.ndarray]], line2: Callable[[int], Optional[np.ndarray]], b: int, a: int, limit: int,
           progress: Optional[Callable[[int], None]] = None, b_min: Optional[int] = None, a_max: Optional[int] = None) -> Optional[tuple]:
    """The search of VB6: at step i the picture i1 of the first and i2 of the second segment are compared (first i1 = B, i2 = A); if they
    do not match, i1 is decreased at odd steps and i2 increased at even steps. `line1(n)` and `line2(n)` give the line of frame n or None
    if there is no such frame (then it does not match). Returns (i1, i2, step) of the first match, or None after `limit` steps.
    The markers must not cross their segments: the search ends when i1 would reach `b_min` (the start of the first segment) or i2 would
    reach `a_max` (the end of the second one), so that no segment becomes empty."""
    i1, i2 = b, a
    for step in range(1, limit + 1):
        if (b_min is not None and i1 <= b_min) or (a_max is not None and i2 >= a_max):
            return None
        if progress:
            progress(step)
        l1, l2 = line1(i1), line2(i2)
        if l1 is not None and l2 is not None and lines_match(l1, l2):
            return i1, i2, step
        if step % 2 == 1:
            i1 -= 1
        else:
            i2 += 1
    return None
