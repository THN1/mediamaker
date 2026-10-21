"""Dialog "Media info" (VB6: frmMediaInfo): one tab per section of the report, selectable and copyable text.

The window can be resized and is at least as wide as all tabs side by side; the text fills the rest.
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

import dialogs
from ui_frmMediaInfo import frmMediaInfoBase

QWIDGETSIZE_MAX = 16777215


class frmMediaInfo(frmMediaInfoBase):
    def __init__(self, title: str, sections: list, parent=None):
        self.sections = sections
        self.file_title = title
        super().__init__(parent)
        self.setWindowTitle(f"Media info for {title}")
        # The VB6 window has a fixed size; here it should be resizable.
        width, height = self.width(), self.height()
        self.setMinimumSize(360, 240)
        self.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(width, height)

        # The elements of the design (tab strip, caption) are replaced by a tab widget with one text field per section.
        self.TabStrip1.hide()
        self.lblMediaInfo.hide()
        self.tabs = QtWidgets.QTabWidget()
        self.editors = []
        fixed = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        for name, text in sections:
            editor = QtWidgets.QPlainTextEdit()
            editor.setReadOnly(True)
            editor.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
            editor.setFont(fixed)
            editor.setPlainText(text)
            self.tabs.addTab(editor, name)
            self.editors.append(editor)
        dialogs.fit_tabs(self, self.tabs, [name for name, _ in sections])

        self.cmdCopy = QtWidgets.QPushButton("Copy &all")
        self.cmdCopy.clicked.connect(self.copy_all)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self.cmdCopy)
        bottom.addWidget(self.cmdClose)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(bottom)
        self.show_tab(0)

    def show_tab(self, index: int) -> None:
        if 0 <= index < len(self.sections):
            self.tabs.setCurrentIndex(index)

    def cmdClose_Click(self):
        self.close()

    def copy_all(self) -> None:
        QtWidgets.QApplication.clipboard().setText("\n\n".join(text for _, text in self.sections))
