"""Dialog "Select frame for ffmpeg's removelogo filter" (VB6: frmRemoveLogo).

Shows a frame as a black/white picture, lets the user move to the left or right by 1 or 10 frames until a frame is found that only
contains the station logo, and offers a slider that blackens the centre of the picture (title, names ...). OK stores the mask as a
1-bit PNG, base64 encoded, in `result`; Cancel leaves `result` empty.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

import logo
from ui_frmRemoveLogo import frmRemoveLogoBase

BAND_COLOR = "#fraBlend { background-color: rgba(255, 0, 0, 90); border-top: 1px solid rgb(255, 0, 0); border-bottom: 1px solid rgb(255, 0, 0); }"


class frmRemoveLogo(frmRemoveLogoBase):
    NAVIGATE_STEPS = (-1, 1, -10, 10)           # buttons "<", ">", "<<", ">>"

    def __init__(self, grab_frame: Callable[[int], np.ndarray], frame: int, first: int, last: int,
                 shown: Callable[[int], int] = lambda n: n, parent=None):
        """grab_frame(n) returns frame n as an RGB array; first..last are the valid frame numbers; shown(n) is the number displayed."""
        super().__init__(parent)
        self.grab_frame, self.first, self.last, self.shown = grab_frame, first, last, shown
        self.frame = max(first, min(frame, last))
        self.result = ""
        self.mask: np.ndarray | None = None
        self.image = None
        self.Picture1.paint_hook = self.paint_picture
        self.fraBlend.setAutoFillBackground(False)
        self.fraBlend.setStyleSheet(BAND_COLOR)         # translucent red band: the picture below stays visible
        self.hscBlend.setToolTip("Blacken the centre of the picture to hide the title, names ... that are shown there")
        self.fraBlend.hide()

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
            self.lblFrame.setText(f"Frame: {self.shown(self.frame)}")
            height, width = self.mask.shape
            data = np.ascontiguousarray((self.mask * 255).astype(np.uint8))
            self.image = QtGui.QImage(data.tobytes(), width, height, width, QtGui.QImage.Format.Format_Grayscale8).copy()
            self.Picture1.update()
            return True
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.setEnabled(True)

    def paint_picture(self, painter, rect) -> None:
        if self.image is not None:
            try:
                painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
            except AttributeError:
                pass
            painter.drawImage(rect, self.image)             # stretched to the box, as the picture of VB6

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
        self.result = logo.mask_to_png_b64(logo.blacken_center(self.mask, self.hscBlend.value(), logo.BLEND_MAX))
        self.accept()

    def cmdCancel_Click(self):
        self.result = ""
        self.reject()
