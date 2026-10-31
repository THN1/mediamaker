"""Detection of black borders (letterbox) and search for commercial breaks using the border.

Port of border() and where_border() from VB6.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Callable, Optional

import numpy as np

from frames import grab_frame


def count_black_lines(img: np.ndarray, blackness: int = 12, allowance: int = 1000) -> int:
    """Counts the black lines at the BOTTOM edge of the picture.

        For every line all colour values (R, G, B separately) larger than `blackness` are summed up
        (the brightness itself, not just the count). If this sum is larger than `allowance`, the line
        is no longer black. At most 25 % of the picture height is examined. A result of 0 means:
        no border found (or the whole examined area is black, e.g. in a black frame).
    """
    h = img.shape[0]
    rows = img[::-1][: h // 4 + 1].astype(np.int32)           # from bottom to top
    sums = np.where(rows > blackness, rows, 0).sum(axis=(1, 2))
    over = np.flatnonzero(sums > allowance)
    return int(over[0]) if over.size else 0


def border_at(path: str, frame: int, fps: Fraction, opts: dict, ffmpeg: str = "ffmpeg", on_image=None) -> int:
    """The black border of a frame. `on_image(frame, rgb)` gets the picture that was read for it (the search shows it in the preview: no second read)."""
    img = grab_frame(path, frame, fps, int(opts.get("floor", 2)), ffmpeg)
    if on_image is not None:
        on_image(frame, img)
    return count_black_lines(img, int(opts.get("blackness", 12)), int(opts.get("allowance", 1000)))


def where_border(border_of: Callable[[int], int], pos: int, last: int, value: int,
                 equal: bool, stepping: int, lim: int = 3, probe: Optional[Callable[[int], None]] = None) -> int:
    """Starting at frame `pos`, searches for the next frame whose border matches `value` (equal=True)
        or differs from it (equal=False). Coarse to fine: large steps; on a hit one step
        back and the step width is reduced until it reaches 1.

        VB6 calls: 'end of commercial' = where_border(crop, True, 1000); 'next commercial' = (crop, False, 6000).
        MediaMaker takes the step widths from the options step_end / step_next instead.
        Prerequisite (as in VB6): from the place where it is found the condition holds permanently.
    """
    while stepping > 0:
        if pos + stepping > last:
            stepping = (stepping + 8) // 10          # end of file: only reduce the step width
            continue
        pos += stepping
        if probe is not None:
            probe(stepping)                          # (the step width of the frame that is looked at now)
        diff = abs(border_of(pos) - value)
        if (equal and diff < lim) or (not equal and diff > lim):
            pos -= stepping
            stepping = (stepping + 8) // 10          # reaches 1 in any case before 0
    return min(pos + 1, last)
