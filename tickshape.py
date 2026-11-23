"""The shape and the colours of the green tick in menu entries (see menustyle.py); no Qt here, so that it can be tested."""

TICK_GREEN = (46, 158, 68)                    # the tick on the normal menu background
TICK_ON_HIGHLIGHT = (126, 230, 142)           # lighter green, with a white edge, on the blue highlight of the entry under the mouse
POINTS = ((0.17, 0.55), (0.41, 0.79), (0.85, 0.25))      # the corner points of the tick in a square of side 1
LINE = 0.17                                   # width of the stroke, in parts of the side of the square


def tick_points(size: float) -> list:
    """The three points of the tick for a square of side `size` (pixels)."""
    return [(x * size, y * size) for x, y in POINTS]


def tick_menu_wanted(environ=None) -> bool:
    """The green ticks are off unless MEDIAMAKER_TICK_MENU=1 is set (and MEDIAMAKER_PLAIN_MENU is not): the style is a Python override of drawControl, which Qt calls for
    every button, slider and menu on every repaint; with PySide6 on openSUSE the reference count of None went down with it until the program aborted
    ("Fatal Python error: none_dealloc: deallocating None", menustyle.py in drawControl)."""
    import os
    environ = os.environ if environ is None else environ
    return bool(environ.get("MEDIAMAKER_TICK_MENU")) and not environ.get("MEDIAMAKER_PLAIN_MENU")
