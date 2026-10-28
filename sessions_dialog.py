"""Dialog for choosing sessions: the list of the saved sessions (newest first), one or several can be selected; when restoring, the parts
to be restored (segment list, settings) can be chosen. When one session is chosen (restoring), a double click on it is the same as OK."""
from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets


class SessionDialog(QtWidgets.QDialog):
    def __init__(self, parent, title: str, prompt: str, infos: list, multi: bool, with_parts: bool, with_backup: bool = False, backup_default: bool = True):
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
        if not multi:
            self.list.itemDoubleClicked.connect(lambda item: self.accept())       # a double click on the wanted session is OK (not for deleting)
        self.chkList = self.chkIni = self.chkChapters = None
        if with_parts:
            self.chkList = QtWidgets.QCheckBox("Segment list")
            self.chkIni = QtWidgets.QCheckBox("Settings (INI file: profiles, options, tool paths)")
            self.chkChapters = QtWidgets.QCheckBox("Chapters (if the session has them; they only fit the segment list of the session)")
            self.chkList.setChecked(True)
            self.chkIni.setChecked(True)
            self.chkChapters.setChecked(True)
            layout.addWidget(self.chkList)
            layout.addWidget(self.chkIni)
            layout.addWidget(self.chkChapters)
        self.chkBackup = None
        if with_backup:
            self.chkBackup = QtWidgets.QCheckBox("Save the current state as a session first (so that you can go back)")
            self.chkBackup.setChecked(bool(backup_default))               # the last choice (option restore_backup); the other two boxes are always ticked
            layout.addWidget(self.chkBackup)
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

    def backup(self) -> bool:
        """Save the current state first? (the check box is ticked at first; True if there is none)"""
        return True if self.chkBackup is None else bool(self.chkBackup.isChecked())

    def parts(self) -> tuple:
        if self.chkList is None:
            return ("ini", "list")
        return tuple(name for name, box in (("list", self.chkList), ("ini", self.chkIni), ("chapters", self.chkChapters)) if box.isChecked())


def choose_sessions(parent, title: str, prompt: str, infos: list, multi: bool = False, with_parts: bool = False, with_backup: bool = False,
                    backup_default: bool = True) -> Optional[tuple]:
    """Shows the dialog. Returns (selected sessions, parts), with `with_backup` (selected sessions, parts, save the current state first), or None on
    cancel / nothing selected / no part chosen."""
    dialog = SessionDialog(parent, title, prompt, infos, multi, with_parts, with_backup, backup_default)
    try:
        if not dialog.exec():
            return None
        chosen, parts = dialog.selected(), dialog.parts()
        if not (chosen and parts):
            return None
        return (chosen, parts, dialog.backup()) if with_backup else (chosen, parts)
    finally:
        dialog.deleteLater()
