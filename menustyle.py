"""Menu entries with a check mark (Copy mode, the profile in use in Load profile) show a small green tick, drawn by the program, and no check box.

Qt's styles draw the check mark of a menu entry in their own way (Fusion: a box around it, in some versions for every entry, in others only when the mouse is on it).
This style sits on top of the style in use (QProxyStyle): for entries that can be ticked it makes the entry an ordinary one with an icon, and the icon is the tick (a
transparent one of the same size if the entry is not ticked, so the texts stay in line). Everything else (colours, the highlight, the shortcuts) is the work of the style below.
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from tickshape import LINE, POINTS, TICK_GREEN, TICK_ON_HIGHLIGHT, tick_points


def tick_pixmap(size: int, ratio: float = 1.0, highlighted: bool = False, ticked: bool = True) -> QtGui.QPixmap:
    """The picture of the tick (transparent without one) in a square of `size` device independent pixels, sharp on screens with a pixel ratio."""
    pixels = max(1, round(size * ratio))
    pixmap = QtGui.QPixmap(pixels, pixels)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(ratio)
    if not ticked:
        return pixmap
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    path = QtGui.QPainterPath()
    (x0, y0), *rest = tick_points(size)
    path.moveTo(x0, y0)
    for x, y in rest:
        path.lineTo(x, y)
    round_ends = (QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin)
    if highlighted:
        edge = QtGui.QPen(QtGui.QColor(255, 255, 255, 235), size * (LINE + 0.12), QtCore.Qt.PenStyle.SolidLine, *round_ends)
        painter.setPen(edge)
        painter.drawPath(path)
    green = TICK_ON_HIGHLIGHT if highlighted else TICK_GREEN
    painter.setPen(QtGui.QPen(QtGui.QColor(*green), size * LINE, QtCore.Qt.PenStyle.SolidLine, *round_ends))
    painter.drawPath(path)
    painter.end()
    return pixmap


class TickMenuStyle(QtWidgets.QProxyStyle):
    """The style in use, except that ticked menu entries get a green tick as their icon instead of a check box."""

    def __init__(self, base=None):
        super().__init__(base)
        self._icons: dict = {}

    def _icon(self, size: int, ratio: float, ticked: bool) -> QtGui.QIcon:
        key = (size, ratio, ticked)
        if key not in self._icons:
            icon = QtGui.QIcon()
            icon.addPixmap(tick_pixmap(size, ratio, False, ticked), QtGui.QIcon.Mode.Normal)
            icon.addPixmap(tick_pixmap(size, ratio, True, ticked), QtGui.QIcon.Mode.Selected)
            icon.addPixmap(tick_pixmap(size, ratio, True, ticked), QtGui.QIcon.Mode.Active)
            self._icons[key] = icon
        return self._icons[key]

    def _plain_item(self, option, widget):
        """A copy of the menu entry without a check box and with the tick as its icon; None if the entry has no check box or already has an icon of its own
        (or if anything goes wrong here: then the entry looks as the style below draws it)."""
        try:
            return self._make_plain_item(option, widget)
        except Exception:
            return None

    def _make_plain_item(self, option, widget):
        if not hasattr(option, "checkType") or not isinstance(option, QtWidgets.QStyleOptionMenuItem):
            return None
        if option.checkType == QtWidgets.QStyleOptionMenuItem.CheckType.NotCheckable or not option.icon.isNull():
            return None
        size = max(12, option.fontMetrics.height() - 2)
        ratio = widget.devicePixelRatioF() if widget is not None and hasattr(widget, "devicePixelRatioF") else 1.0
        copy = QtWidgets.QStyleOptionMenuItem(option)
        copy.checkType = QtWidgets.QStyleOptionMenuItem.CheckType.NotCheckable
        copy.icon = self._icon(size, ratio, bool(option.checked))
        copy.maxIconWidth = max(copy.maxIconWidth, size)
        return copy

    def drawControl(self, element, option, painter, widget=None):
        if element == QtWidgets.QStyle.ControlElement.CE_MenuItem:
            plain = self._plain_item(option, widget)
            if plain is not None:
                option = plain
        super().drawControl(element, option, painter, widget)

    def sizeFromContents(self, contents, option, size, widget=None):
        if contents == QtWidgets.QStyle.ContentsType.CT_MenuItem:
            plain = self._plain_item(option, widget)
            if plain is not None:
                option = plain
        return super().sizeFromContents(contents, option, size, widget)


_style = None                                 # the style object must stay alive as long as the program runs


def install(app) -> bool:
    """Puts the style on the style of the application. False (nothing changed) if that does not work or MEDIAMAKER_PLAIN_MENU=1 is set (the check boxes of Qt's own style)."""
    import os
    if os.environ.get("MEDIAMAKER_PLAIN_MENU"):
        return False
    global _style
    try:
        _style = TickMenuStyle(QtWidgets.QStyleFactory.create(app.style().objectName() or "Fusion"))
        app.setStyle(_style)
        return True
    except Exception as e:                                          # never prevent the start because of the look of a menu
        import sys
        print(f"menu tick style not used: {e!r}", file=sys.stderr)
        return False
