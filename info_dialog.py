"""Dialog "Loaded segments information" (VB6: frmInfo): table of all segments with a summary; resizable."""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

import dialogs
from info import HEADERS, RIGHT_ALIGNED
from ui_frmInfo import frmInfoBase

QWIDGETSIZE_MAX = 16777215
SAMPLES = {0: "00", 2: "0.000.000.000", 3: "00:00:00", 4: "000000", 5: "000000", 6: "00:00:00.000", 7: "00:00:00.000",
           8: "00:00:00.000", 9: "0000x0000", 10: "00.000", 11: "00000", 12: "00000", 13: "00000"}
PADDING = 20
FILE_COLUMN = 1


class frmInfo(frmInfoBase):
    def __init__(self, rows: list, summary: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loaded segments information")
        # The size of the main window (UI_SCALE, see uiscale.py) counts here too: the font and the size of the dialog follow it.
        factor = getattr(parent, "UI_SCALE", 100) / 100
        if factor != 1:
            dialogs.scale_font(self, factor, parent)                      # the font of the main window (explicitly also for the controls of the design)
            for widget in (self.lvwInfo, self.cmdClose):
                widget.setFont(self.font())
        # The VB6 design has a fixed size and nine columns; here there are more columns and the window can be resized.
        self.setMinimumSize(round(520 * factor), round(240 * factor))
        self.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(round(1100 * factor), round(420 * factor))
        if factor != 1:
            self.cmdClose.resize(round(self.cmdClose.width() * factor), round(self.cmdClose.height() * factor))

        self.lvwInfo.setHeaderLabels(list(HEADERS))
        self.lvwInfo.set_rows(rows)
        metrics = self.lvwInfo.fontMetrics()
        widths = {col: max(metrics.horizontalAdvance(HEADERS[col]), metrics.horizontalAdvance(sample)) + PADDING
                  for col, sample in SAMPLES.items()}
        widths.update({col: metrics.horizontalAdvance(HEADERS[col]) + PADDING for col in range(len(HEADERS))
                       if col not in widths and col != FILE_COLUMN})
        self.lvwInfo.set_columns(widths, stretch_column=FILE_COLUMN)
        right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        for i in range(self.lvwInfo.row_count()):
            item = self.lvwInfo.topLevelItem(i)
            for col in RIGHT_ALIGNED:
                item.setTextAlignment(col, right)

        self.lblSummary = QtWidgets.QLabel(summary)
        self.lblSummary.setWordWrap(True)
        self.lblSummary.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self.lblSummary, 1)
        bottom.addWidget(self.cmdClose)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.lvwInfo, 1)
        layout.addLayout(bottom)

    def cmdClose_Click(self):
        self.close()
