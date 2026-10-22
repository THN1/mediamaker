"""Dialog "Select frame for ffmpeg's removelogo filter" (VB6: frmRemoveLogo).

Shows a frame as a black/white picture, lets the user move to the left or right by 1 or 10 frames until a frame is found that only
contains the station logo, and offers a slider that blackens the centre of the picture (title, names ...). OK stores the mask as a
1-bit PNG, base64 encoded, in `result`; Cancel leaves `result` empty. The picture shows the mask as it will be stored: dark areas inside
the logo filled (option mask_fill) and the white areas grown (option mask_grow).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

import logo
from ui_frmRemoveLogo import frmRemoveLogoBase

PICTURE_WIDTH = 593                     # width of the picture box; the height follows from the proportions of the picture
MIN_HEIGHT, MAX_HEIGHT = 120, 700       # limits of the height of the picture box (extreme proportions)
HINT_HEIGHT = 24                        # room for the line of explanation below the buttons
HINT = "Slider: blackens a band in the middle of the picture, e.g. to hide the title or names (red band)"


def band_style(opacity: int) -> str:
    """Stylesheet of the red band; `opacity` in percent."""
    alpha = round(255 * max(0, min(100, opacity)) / 100)
    return (f"#fraBlend {{ background-color: rgba(255, 0, 0, {alpha}); border-top: 1px solid rgb(255, 0, 0); "
            f"border-bottom: 1px solid rgb(255, 0, 0); }}")


class frmRemoveLogo(frmRemoveLogoBase):
    NAVIGATE_STEPS = (-1, 1, -10, 10)           # buttons "<", ">", "<<", ">>"

    def __init__(self, grab_frame: Callable[[int], np.ndarray], frame: int, first: int, last: int,
                 shown: Callable[[int], int] = lambda n: n, parent=None, opacity: int = 35, fill: bool = True, grow: int = 0):
        """grab_frame(n) returns frame n as an RGB array; first..last are the valid frame numbers; shown(n) is the number displayed;
        opacity (percent) is that of the red band; fill = enclosed black areas become white; grow = pixels by which the white areas are
        made bigger (see logo.fill_holes and logo.grow_mask)."""
        super().__init__(parent)
        self.grab_frame, self.first, self.last, self.shown = grab_frame, first, last, shown
        self.frame = max(first, min(frame, last))
        self.result = ""
        self.fill, self.grow = fill, grow
        self.mask: np.ndarray | None = None             # black/white picture of the frame (threshold)
        self.final: np.ndarray | None = None            # the mask as it is stored (without the blackened centre): filled, grown
        self.image = None
        self.Picture1.paint_hook = self.paint_picture
        self.fraBlend.setAutoFillBackground(False)
        self.fraBlend.setStyleSheet(band_style(opacity))   # translucent red band: the picture below stays visible
        self.fraBlend.hide()
        # Line of explanation below the buttons; the window grows by its height. The picture box and everything below it move
        # when the proportions of the picture are known (fit_to_picture).
        base_width, base_height = self.width(), self.height()
        self.lblHint = QtWidgets.QLabel(HINT, self)
        self.lblHint.setGeometry(8, base_height, PICTURE_WIDTH, 17)
        self.hscBlend.setToolTip(HINT)
        self.lblHint.setToolTip(HINT)
        self._base_size = (base_width, base_height + HINT_HEIGHT)
        self.setFixedSize(*self._base_size)
        g = self.Picture1.geometry()
        self._picture_base = (g.x(), g.y(), g.width(), g.height())
        self._lower = []                                # controls below the picture: (widget, original geometry)
        for widget in (self.lblFrame, self.cmdOK, self.cmdCancel, *self.cmdNavigate, self.hscBlend, self.lblHint):
            g = widget.geometry()
            self._lower.append((widget, (g.x(), g.y(), g.width(), g.height())))

    def exec_dialog(self) -> str:
        """Shows the dialog (the frame is loaded as soon as it is visible) and returns the mask, or "" if cancelled."""
        QtCore.QTimer.singleShot(0, self.load_frame)
        self.exec()
        return self.result

    def inform(self, text: str) -> None:
        QtWidgets.QMessageBox.warning(self, "MediaMaker", text)

    # ------------------------------------------------------------------ frame
    def load_frame(self) -> bool:
        """Gets the current frame and shows it as a black/white picture (VB6: click())."""
        self.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            try:
                rgb = self.grab_frame(self.frame)
            except Exception:
                rgb = None
            if rgb is None:
                self.inform(f"Could not get frame at frame {self.shown(self.frame)}")
                return False
            self.mask = logo.monochrome_mask(rgb)
            self.final = logo.fill_holes(self.mask) if self.fill else self.mask
            self.final = logo.grow_mask(self.final, self.grow)
            self.lblFrame.setText(f"Frame: {self.shown(self.frame)}")
            height, width = self.final.shape
            self.fit_to_picture(width, height)
            data = np.ascontiguousarray((self.final * 255).astype(np.uint8))
            self.image = QtGui.QImage(data.tobytes(), width, height, width, QtGui.QImage.Format.Format_Grayscale8).copy()
            self.Picture1.update()
            return True
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.setEnabled(True)

    def fit_to_picture(self, width: int, height: int) -> None:
        """Keeps the width of the picture box and makes its height fit the proportions of the picture (the picture is not distorted);
        the controls below move along and the window gets the height it needs."""
        x, y, w, h = self._picture_base
        box = max(MIN_HEIGHT, min(MAX_HEIGHT, round(PICTURE_WIDTH * height / width)))
        shift = box - h
        self.Picture1.setGeometry(x, y, w, box)
        for widget, (wx, wy, ww, wh) in self._lower:
            widget.setGeometry(wx, wy + shift, ww, wh)
        self.setFixedSize(self._base_size[0], self._base_size[1] + shift)

    def paint_picture(self, painter, rect) -> None:
        if self.image is not None:
            try:
                painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
            except AttributeError:
                pass
            painter.drawImage(rect, self.image)             # the box has the proportions of the picture

    def cmdNavigate_Click(self, index: int):
        target = max(self.first, min(self.frame + self.NAVIGATE_STEPS[index], self.last))     # VB6 did not check the limits
        if target != self.frame:
            self.frame = target
            self.load_frame()

    # ------------------------------------------------------------------ blackening the centre
    def hscBlend_Change(self, *args):
        """The red band shows which part of the picture will be blackened."""
        picture = self.Picture1.geometry()
        half = round(picture.height() / logo.BLEND_MAX * self.hscBlend.value() / 2)
        if half > 0:
            self.fraBlend.setGeometry(picture.x(), picture.y() + picture.height() // 2 - half, picture.width(), 2 * half)
            self.fraBlend.show()
            self.fraBlend.raise_()
        else:
            self.fraBlend.hide()

    # ------------------------------------------------------------------ OK / Cancel
    def cmdOK_Click(self):
        if self.mask is None:
            return
        self.fraBlend.hide()
        self.result = logo.mask_to_png_b64(logo.blacken_center(self.final, self.hscBlend.value(), logo.BLEND_MAX))
        self.accept()

    def cmdCancel_Click(self):
        self.result = ""
        self.reject()
