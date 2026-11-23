"""Scaling of the main window (frmMain.UI_SCALE, in percent).

The form from the VB6 IDE has fixed pixel positions (central widget 1089 x 436). For a larger display the whole form is scaled by the same factor: the positions and
sizes of all controls, the font (which all controls inherit) and the symbols of the buttons. The width is then pulled to a usual screen width (e.g. 125 % = 1361 px -> 1366 px):
the few missing or surplus pixels go into the two gaps next to the column of buttons between the list and the preview, so nothing else changes its proportions."""

BASE_WIDTH = 1089                              # width of the central widget in the form (pixels at 100 %)
COLUMN_X = (512, 544)                          # left edge of the column of buttons and of the preview in the form; the surplus pixels are put in front of these two
STANDARD_WIDTHS = (1280, 1366, 1440, 1600, 1920)
SNAP = 0.01                                    # a usual width is taken if the scaled width differs from it by at most 1 %


def target_width(percent: int) -> int:
    """Width of the central widget: BASE_WIDTH scaled, or the usual width that lies within 1 % of it."""
    exact = round(BASE_WIDTH * percent / 100)
    for width in STANDARD_WIDTHS:
        if abs(width - exact) <= exact * SNAP:
            return width
    return exact


class Scaler:
    """Maps positions of the form to the scaled form (pure arithmetic, no Qt)."""

    def __init__(self, percent: int):
        self.factor = percent / 100
        self.extra = target_width(percent) - round(BASE_WIDTH * self.factor)
        self.width = target_width(percent)

    def x(self, value: int) -> int:
        """Horizontal position of the form: scaled, plus the surplus pixels in front of the column of buttons (half) and the preview (the rest)."""
        shift = 0
        if value >= COLUMN_X[0]:
            shift += self.extra // 2
        if value >= COLUMN_X[1]:
            shift += self.extra - self.extra // 2
        return round(value * self.factor) + shift

    def y(self, value: int) -> int:
        return round(value * self.factor)

    def inner(self, value: int) -> int:
        """Position or size inside a container (no surplus pixels)."""
        return round(value * self.factor)

    def icon(self, size: int) -> int:
        return max(1, round(size * self.factor))


def apply(window, central, percent: int) -> Scaler:
    """Scales the central widget `central` of `window`: size, controls (one level of containers below them) and font. Returns the Scaler (for the symbol size)."""
    scaler = Scaler(percent)
    if percent == 100:
        return scaler
    font = central.font()
    scaled_font = None
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * scaler.factor)
        central.setFont(font)
        scaled_font = font
    central_size = central.size()
    central.setFixedSize(scaler.width, scaler.y(central_size.height()))
    for child in central.children():
        if not child.isWidgetType():
            continue
        g = child.geometry()
        left, right = scaler.x(g.x()), scaler.x(g.x() + g.width())
        top, bottom = scaler.y(g.y()), scaler.y(g.y() + g.height())
        child.setGeometry(left, top, right - left, bottom - top)
        if scaled_font is not None:
            child.setFont(scaled_font)                                    # (explicitly: a control with a style sheet, e.g. the white value fields, would keep the old size)
        for sub in child.children():                                     # (only the labels of the frame; the inner parts of a list or a slider are not touched)
            if sub.isWidgetType() and type(child).__name__ in ("QGroupBox", "QFrame", "GroupFrame"):
                s = sub.geometry()
                sub.setGeometry(scaler.inner(s.x()), scaler.inner(s.y()), scaler.inner(s.width()), scaler.inner(s.height()))
                if scaled_font is not None:
                    sub.setFont(scaled_font)
    return scaler


def scale_form(form, factor: float, font=None) -> None:
    """Scales a fixed VB6 form (dialog) by `factor`: the positions and sizes of its controls (one level of containers below them) and, if `font` is given, the font of all of them.
    The size of the form itself is the business of the caller. Nothing happens at 1."""
    if factor == 1:
        return
    if font is not None:
        form.setFont(font)
    for child in form.children():
        if not child.isWidgetType():
            continue
        g = child.geometry()
        child.setGeometry(round(g.x() * factor), round(g.y() * factor), round(g.width() * factor), round(g.height() * factor))
        if font is not None:
            child.setFont(font)
        if type(child).__name__ in ("QGroupBox", "QFrame", "GroupFrame"):
            for sub in child.children():
                if sub.isWidgetType():
                    s = sub.geometry()
                    sub.setGeometry(round(s.x() * factor), round(s.y() * factor), round(s.width() * factor), round(s.height() * factor))
                    if font is not None:
                        sub.setFont(font)


def window_font(form):
    """The font of `form` if it has a usable (point) size, else None."""
    font = form.font()
    return font if font.pointSizeF() > 0 else None
