"""Dialog "Media info" (VB6: frmMediaInfo): Knöpfe für die Abschnitte des Berichts, Text auswählbar und kopierbar.

Das Fenster ist in der Größe veränderbar; die Knöpfe für General, Video, Audio ... teilen sich die ganze Fensterbreite zu
gleichen Teilen, das Textfeld füllt den Rest.
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ui_frmMediaInfo import frmMediaInfoBase

QWIDGETSIZE_MAX = 16777215


class frmMediaInfo(frmMediaInfoBase):
    def __init__(self, title: str, sections: list, parent=None):
        self.sections = sections
        self.file_title = title
        super().__init__(parent)
        self.setWindowTitle(f"Media info for {title}")
        # Das VB6-Fenster hat feste Größe; hier soll es sich verändern lassen.
        width, height = self.width(), self.height()
        self.setMinimumSize(360, 240)
        self.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, True)
        self.resize(width, height)

        # Die Elemente des Entwurfs (Reiter, Beschriftung) werden durch Knöpfe und ein Textfeld ersetzt.
        self.TabStrip1.hide()
        self.lblMediaInfo.hide()
        self.text = QtWidgets.QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont))

        self.tab_group = QtWidgets.QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_buttons = []
        tabs = QtWidgets.QHBoxLayout()
        tabs.setSpacing(2)
        for index, (name, _) in enumerate(sections):
            button = QtWidgets.QPushButton(name)
            button.setCheckable(True)
            # "Ignored": die Größe richtet sich nicht nach dem Text, alle Knöpfe bekommen gleich viel Breite
            button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda checked=False, i=index: self.show_tab(i))
            self.tab_group.addButton(button, index)
            self.tab_buttons.append(button)
            tabs.addWidget(button, 1)

        self.cmdCopy = QtWidgets.QPushButton("Copy &all")
        self.cmdCopy.clicked.connect(self.copy_all)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self.cmdCopy)
        bottom.addWidget(self.cmdClose)

        self.tab_row = tabs
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(tabs)
        layout.addWidget(self.text, 1)
        layout.addLayout(bottom)
        self.show_tab(0)

    def show_tab(self, index: int) -> None:
        if 0 <= index < len(self.sections):
            self.text.setPlainText(self.sections[index][1])
            self.tab_buttons[index].setChecked(True)

    def cmdClose_Click(self):
        self.close()

    def copy_all(self) -> None:
        QtWidgets.QApplication.clipboard().setText("\n\n".join(text for _, text in self.sections))
