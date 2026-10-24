"""Dialog for choosing sessions: the list of the saved sessions (newest first), one or several can be selected; when restoring, the parts
to be restored (segment list, settings) can be chosen."""
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets


class SessionDialog(QtWidgets.QDialog):
    def __init__(self, parent, title: str, prompt: str, infos: list, multi: bool, with_parts: bool):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.infos = infos
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(prompt)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.list = QtWidgets.QListWidget()
        mode = QtWidgets.QAbstractItemView.SelectionMode
        self.list.setSelectionMode(mode.ExtendedSelection if multi else mode.SingleSelection)
        for info in infos:
            self.list.addItem(info.describe())
        self.list.setMinimumWidth(560)
        self.list.setMinimumHeight(220)
        layout.addWidget(self.list, 1)
        self.chkList = self.chkIni = None
        if with_parts:
            self.chkList = QtWidgets.QCheckBox("Segment list")
            self.chkIni = QtWidgets.QCheckBox("Settings (INI file: profiles, options, tool paths)")
            self.chkList.setChecked(True)
            self.chkIni.setChecked(True)
            layout.addWidget(self.chkList)
            layout.addWidget(self.chkIni)
        button = QtWidgets.QDialogButtonBox.StandardButton
        buttons = QtWidgets.QDialogButtonBox(button.Ok | button.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if infos and not multi:
            self.list.setCurrentRow(0)

    def selected(self) -> list:
        rows = sorted({index.row() for index in self.list.selectedIndexes()})
        return [self.infos[r] for r in rows if 0 <= r < len(self.infos)]

    def parts(self) -> tuple:
        if self.chkList is None:
            return ("ini", "list")
        return tuple(name for name, box in (("list", self.chkList), ("ini", self.chkIni)) if box.isChecked())


def choose_sessions(parent, title: str, prompt: str, infos: list, multi: bool = False, with_parts: bool = False) -> Optional[tuple]:
    """Shows the dialog. Returns (selected sessions, parts) or None on cancel / nothing selected / no part chosen."""
    dialog = SessionDialog(parent, title, prompt, infos, multi, with_parts)
    try:
        if not dialog.exec():
            return None
        chosen, parts = dialog.selected(), dialog.parts()
        return (chosen, parts) if chosen and parts else None
    finally:
        dialog.deleteLater()
