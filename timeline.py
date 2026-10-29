"""Timeline (VB6: picTimeline): 20 thumbnails around the marker, red crosses for missing frames, red cut line.

The frame to the RIGHT of the line has the number of the marker (marker A: first frame of the segment; marker B: the segment ends with
the frame to the LEFT of the line). A click on a frame moves the marker so that the line lies directly next to this frame;
the two frames right at the line do nothing.
"""
from __future__ import annotations

import time
from math import floor
from typing import Optional

from PySide6 import QtCore, QtGui

from player import debug_log

RANGE = 20                       # number of thumbnails
LINE_WIDTH = 3                   # width of the cut line in pixels


def window_numbers(center: int, count: int = RANGE) -> list:
    """Frame numbers of the timeline: from center - count/2 to center + count/2 - 1; the frame right of the line is `center`."""
    start = center - count // 2
    return list(range(start, start + count))


def cell_width(width: int, count: int = RANGE) -> int:
    return max(width // count, 1)


def click_delta(index: int) -> int:
    """Shift of the marker on a click on the frame with index 0..19 (from the left): like picTimeline_Click in VB6."""
    if index < 9:
        return index - 9
    if index > 10:
        return index - 10
    return 0


def click_index(x: int, width: int, count: int = RANGE) -> int:
    """Index (0..count-1) of the frame under x (pixels from the left edge of the drawing area).

        The calculation uses the cell width that is also used for drawing (VB6 divided by the whole width and was off by up to half a
        frame at the right edge); the remainder to the right outside the cells counts as the last frame.
    """
    return max(0, min(count - 1, x // cell_width(width, count)))


def thumb_size(src_width: int, src_height: int, cell: int) -> tuple:
    """Size of a thumbnail: longest side = cell width - 1, the pixel aspect of the source is kept (like FreeImage)."""
    side = max(cell - 1, 1)
    if src_width >= src_height:
        return side, max(1, round(side * src_height / src_width))
    return max(1, round(side * src_width / src_height)), side


def frame_number(pts: float, container_start: float, fps: float) -> int:
    return floor((pts - container_start) * fps + 1e-3)


def draw_strip(painter, rect, cells: list) -> None:
    """Draws the timeline. cells = 20 pairs (state, QImage): "image", "cross" (missing) or "pending" (being loaded)."""
    cw = cell_width(rect.width(), len(cells))
    top, height = rect.y(), rect.height()
    red = QtGui.QColor(255, 0, 0)
    for i, (state, image) in enumerate(cells):
        x0 = rect.x() + i * cw
        if state == "image" and image is not None:
            painter.drawImage(x0, top, image)
        elif state == "pending":                            # still being loaded: light grey area
            painter.fillRect(x0, top, cw - 1, height, QtGui.QColor(215, 215, 215))
        elif state == "cross":
            painter.setPen(red)
            painter.drawLine(x0, top, x0 + cw, top + height)
            painter.drawLine(x0, top + height, x0 + cw, top)
    # (the red line is NOT drawn here: it is the control Line1 of the form, which lies BEHIND the timeline like a line of VB6, so it shows in the gap between the two
    # pictures of the cut and above and below the strip, but not over the pictures)


class ThumbLoader(QtCore.QThread):
    """Fetches the thumbnails in the background (one call of ffmpeg); cancelling terminates ffmpeg."""

    loaded = QtCore.Signal(int, object, object)          # token, {number: array}, (first, last requested number)
    failed = QtCore.Signal(int, str)                     # token, error message

    def __init__(self, token: int, path: str, first: int, last: int, fps, size: tuple, grab_fn):
        super().__init__()
        self.token, self.path, self.first, self.last = token, path, first, last
        self.fps, self.size, self.grab_fn = fps, size, grab_fn
        self._proc = None
        self.cancelled = False

    def _remember(self, proc) -> None:
        self._proc = proc
        if self.cancelled:
            proc.terminate()

    def cancel(self) -> None:
        self.cancelled = True
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()

    def run(self) -> None:
        started = time.monotonic()
        try:
            frames = self.grab_fn(self.path, self.first, self.last - self.first + 1, self.fps, self.size,
                                  on_start=self._remember)
        except Exception as e:                             # not readable (or cancelled): report it, do not swallow it
            if not self.cancelled:
                debug_log(f"thumbnails {self.first}..{self.last} failed: {e!r}")
                self.failed.emit(self.token, f"{type(e).__name__}: {e}")
            return
        debug_log(f"thumbnails {self.first}..{self.last}: {len(frames)} frames in {time.monotonic() - started:.1f} s")
        if not self.cancelled:
            self.loaded.emit(self.token, frames, (self.first, self.last))
