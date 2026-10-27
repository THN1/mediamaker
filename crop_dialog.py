"""Small window for the cropping of one segment (VB6: frmCrop).

Four scroll bars set the margins (top, bottom: 0..400; left, right: 0..250), the text boxes show the values (and can be typed into). Three
buttons: OK (R is "reset": everything to zero; X is cancel). The check box 16:9 sets left and right automatically so that the picture that is
left has the proportions 16:9 (and keeps them when top or bottom change). While the window is open the main window shows the margins as red
bands over the preview (signal `changed`). `status`: 1 = open, 0 = OK, -1 = cancelled (as in VB6).
"""
from __future__ import annotations

from fractions import Fraction

from PySide6 import QtCore, QtWidgets

import cropping
from ui_frmCrop import frmCropBase


class frmCrop(frmCropBase):
    changed = QtCore.Signal()

    def __init__(self, parent=None, width: int = 720, height: int = 576, sar=1):
        """width, height: size of the source picture in pixels; sar: sample aspect ratio (for 16:9)."""
        super().__init__(parent)
        self.source = (int(width), int(height), Fraction(sar))
        self.status = 1                                              # running
        self.notify = lambda text: QtWidgets.QMessageBox.warning(self, "MediaMaker", text)
        self.setModal(True)
        for i in range(4):
            self.txtCrop[i].editingFinished.connect(lambda i=i: self.typed(i))

    # ------------------------------------------------------------------ values
    def scroll(self, index: int):
        """The scroll bar of a margin: 0 top, 1 bottom (horizontal), 2 left, 3 right (vertical)."""
        return self.HScroll[index] if index < 2 else self.VScroll[index - 2]

    def values(self) -> tuple:
        """(top, bottom, left, right)"""
        return tuple(int(self.scroll(i).value()) for i in range(4))

    def set_values(self, top: int, bottom: int, left: int, right: int) -> None:
        for i, v in enumerate((top, bottom, left, right)):
            self.scroll(i).setValue(max(0, int(v)))                  # (the scroll bar keeps it inside its range)
            self.txtCrop[i].setText(str(self.scroll(i).value()))

    def typed(self, index: int) -> None:
        """A number typed into a text box moves the scroll bar; anything else is replaced by the value of the scroll bar."""
        text = self.txtCrop[index].text().strip()
        if text.lstrip("-").isdigit():
            self.scroll(index).setValue(max(0, int(text)))
        self.txtCrop[index].setText(str(self.scroll(index).value()))

    def apply_ratio(self) -> None:
        """16:9: left and right from top and bottom."""
        width, height, sar = self.source
        side = cropping.ratio_side(width, height, sar, self.HScroll[0].value(), self.HScroll[1].value())
        self.VScroll[0].setValue(side)
        self.VScroll[1].setValue(side)

    # ------------------------------------------------------------------ VB6 procedures
    def chkAutoRatio_Click(self):
        if self.chkAutoRatio.isChecked():
            self.apply_ratio()

    def cmdOK_Click(self):
        width, height, _ = self.source
        if not cropping.valid(width, height, *self.values()):
            self.notify(f"Nothing would be left of the picture ({width}x{height} pixels): the top and the bottom margin together must be smaller than "
                        f"{height}, and the left and the right one together smaller than {width}.")
            return
        self.status = 0                                              # normal end
        self.accept()

    def cmdReset_Click(self):
        for i in range(4):
            self.scroll(i).setValue(0)
        self.chkAutoRatio.setChecked(False)

    def cmdCancel_Click(self):
        self.status = -1                                             # cancelled
        self.reject()

    def HScroll_Change(self, index):
        self.txtCrop[index].setText(str(self.HScroll[index].value()))
        if self.chkAutoRatio.isChecked():
            self.apply_ratio()
        self.changed.emit()

    def VScroll_Change(self, index):
        self.txtCrop[index + 2].setText(str(self.VScroll[index].value()))
        self.changed.emit()
