"""Dialog "Media info" (VB6: frmMediaInfo): one page per section of the report (tabs along the top or a list on the left, see
dialogs.Sections), selectable and copyable text.

The window can be resized and is at least as wide as all tabs side by side; the text fills the rest.
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import dialogs
import mediainfo
from ui_frmMediaInfo import frmMediaInfoBase

QWIDGETSIZE_MAX = 16777215


class frmMediaInfo(frmMediaInfoBase):
    def __init__(self, title: str, sections: list, parent=None):
        self.sections = sections
        self.file_title = title
        super().__init__(parent)
        self.setWindowTitle(f"Media info for {title}")
        factor = dialogs.ui_factor(parent)                       # the size of the main window (UI_SCALE): font and window
        dialogs.scale_font(self, factor, parent)
        # The VB6 window has a fixed size; here it should be resizable.
        width, height = round(self.width() * factor), round(self.height() * factor)
        self.setMinimumSize(round(360 * factor), round(240 * factor))
        self.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(width, height)

        # The elements of the design (tab strip, caption) are replaced by a tab widget with one text field per section.
        self.TabStrip1.hide()
        self.lblMediaInfo.hide()
        self.nav = dialogs.Sections()
        self.tabs = self.nav.tabs                                  # None with the list on the left (dialog_style=list)
        self.editors = []
        fixed = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        if factor != 1 and fixed.pointSizeF() > 0:
            fixed.setPointSizeF(fixed.pointSizeF() * factor)
        for name, text in sections:
            editor = QtWidgets.QPlainTextEdit()
            editor.setReadOnly(True)
            editor.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
            editor.setFont(fixed)
            editor.setPlainText(text)
            self.nav.add(name, editor)
            self.editors.append(editor)
        self.nav.fit(self)

        self.cmdCopy = QtWidgets.QPushButton("Copy &all")
        self.cmdCopy.clicked.connect(self.copy_all)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self.cmdCopy)
        bottom.addWidget(self.cmdClose)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.nav.widget, 1)
        layout.addLayout(bottom)
        self.show_tab(0)

    def show_tab(self, index: int) -> None:
        if 0 <= index < len(self.sections):
            self.nav.set_current(index)

    def cmdClose_Click(self):
        self.close()

    def copy_all(self) -> None:
        QtWidgets.QApplication.clipboard().setText(mediainfo.full_text(self.sections))
