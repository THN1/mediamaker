"""Progress bar for the main window (VB6: bar()): a filled area with centred text."""
from __future__ import annotations

from PySide6 import QtCore, QtGui

BACKGROUND = (240, 240, 240)             # VB6: light grey
FILL = (0, 120, 215)                     # VB6: medium blue (&HD77800 in BGR)


def draw_bar(painter, rect, percent: float, text: str) -> None:
    """Draws the bar: grey background, blue fill up to `percent`; the text is black on the grey and white on the blue part."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    fill = max(0, min(w, round(w * percent / 100)))
    painter.fillRect(x, y, w, h, QtGui.QColor(*BACKGROUND))
    painter.fillRect(x, y, fill, h, QtGui.QColor(*FILL))
    area = QtCore.QRect(x, y, w, h)
    centre = QtCore.Qt.AlignmentFlag.AlignCenter
    painter.setPen(QtGui.QColor(0, 0, 0))
    painter.drawText(area, centre, text)
    if fill > 0:
        painter.save()
        painter.setClipRect(QtCore.QRect(x, y, fill, h))
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.drawText(area, centre, text)
        painter.restore()
