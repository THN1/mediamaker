"""The multitrack dialog (option multitrack): which audio and subtitle tracks of the source file go into the new file, in which order, and with which language code.

Two tabs (Audio, Subtitles); a row for every position: a list of the tracks of the source file ("-" = unused) and the language code (a drop-down list of the codes of the
source file; a code can also be typed and is checked against ISO 639-2). Everything that decides is in tracks.TracksModel (tested without widgets); this only shows it.
OK is not possible while there is an error. Cancel: only the main audio track is processed, and no subtitles (said in the dialog).
"""
from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

import containers
import tracks

BANNER_STYLE = "background: #e1effa; color: #17354d; border: 1px solid #9bc9ec; border-radius: 3px; padding: 8px;"
ERROR_STYLE = "color: #b3261e;"
MUTED_STYLE = "color: gray;"
DEFAULTS = "defaults"                  # what run_dialog returns when the button Defaults is pressed (a choice, None and DEFAULTS are the three outcomes)
BUTTON_TEXT = ("OK: use this choice. Defaults: only the main audio track, no subtitles (the normal way without this dialog). "
               "Cancel: stop saving, no file is written.")


class TracksDialog(QtWidgets.QDialog):
    def __init__(self, model: tracks.TracksModel, file_text: str, parent=None, source_note: str = ""):
        super().__init__(parent)
        self.model = model
        self.defaults = False                                            # True: the button Defaults closed the dialog
        self.setWindowTitle("Audio and subtitle tracks")
        c = containers.info(model.output)
        target = f"Saving as {model.output.replace(chr(92), '/').rsplit('/', 1)[-1]}" + (f" · {c.name}" if c else "")
        layout = QtWidgets.QVBoxLayout(self)
        head = QtWidgets.QLabel(file_text)
        head.setStyleSheet("font-weight: bold;")
        layout.addWidget(head)
        sub = QtWidgets.QLabel(target)
        sub.setStyleSheet(MUTED_STYLE)
        layout.addWidget(sub)
        if source_note:
            self.source_label = QtWidgets.QLabel(source_note)
            self.source_label.setStyleSheet(MUTED_STYLE)
            layout.addWidget(self.source_label)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        self.widgets: dict = {"audio": [], "subtitle": []}              # per kind: one dict per row (track, language, note)
        for kind, title, intro in (("audio", "Audio", "Choose the audio tracks for the new file and put them in the order you want. The first one is the main track. "
                                                       "Select “-” to leave a position unused. The language code can be picked from the codes of the source file or typed; it is checked."),
                                   ("subtitle", "Subtitles", "Choose the subtitle tracks for the new file and put them in the order you want. Select “-” to leave a position unused. "
                                                             "Teletext tracks are ignored.")):
            count = len(model.of(kind))
            if count == 0:
                continue
            self.tabs.addTab(self.page(kind, intro), f"{title} ({count} track{'s' if count != 1 else ''})")
        self.error = QtWidgets.QLabel("")                               # under the tabs: an error of the other tab must not be overlooked
        self.error.setWordWrap(True)
        self.error.setStyleSheet(ERROR_STYLE)
        layout.addWidget(self.error)
        bottom = QtWidgets.QHBoxLayout()
        note = QtWidgets.QLabel(BUTTON_TEXT)
        note.setWordWrap(True)
        note.setStyleSheet(MUTED_STYLE)
        bottom.addWidget(note, 1)
        self.defaults_button = QtWidgets.QPushButton("Defaults")
        self.defaults_button.setToolTip("Go on with only the main audio track and no subtitles")
        self.defaults_button.clicked.connect(self.use_defaults)
        bottom.addWidget(self.defaults_button)
        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        bottom.addWidget(self.buttons)
        layout.addLayout(bottom)
        self.resize(780, self.sizeHint().height() if hasattr(self, "sizeHint") else 560)
        self.refresh()

    # ------------------------------------------------------------------ one tab
    def page(self, kind: str, intro: str) -> QtWidgets.QWidget:
        model = self.model
        page = QtWidgets.QWidget()
        box = QtWidgets.QVBoxLayout(page)
        text = QtWidgets.QLabel(intro)
        text.setWordWrap(True)
        box.addWidget(text)
        grid = QtWidgets.QGridLayout()
        grid.setColumnStretch(1, 1)
        last = "In the new file" if kind == "subtitle" else "Note"
        for col, title in enumerate(("Position", "Track of the source file", "Language code", last)):
            label = QtWidgets.QLabel(title)
            label.setStyleSheet("font-weight: bold;" + MUTED_STYLE)
            grid.addWidget(label, 0, col)
        for row in range(len(model.rows[kind])):
            track = QtWidgets.QComboBox()
            track.addItems(model.track_labels(kind))
            track.setCurrentIndex(model.selected(kind, row))
            language = QtWidgets.QComboBox()
            language.setEditable(True)
            language.addItems(model.language_choices(kind))
            language.setCurrentText(model.rows[kind][row].language)
            note = QtWidgets.QLabel("")
            note.setStyleSheet(MUTED_STYLE)
            grid.addWidget(QtWidgets.QLabel(model.position_label(kind, row)), row + 1, 0)
            grid.addWidget(track, row + 1, 1)
            grid.addWidget(language, row + 1, 2)
            grid.addWidget(note, row + 1, 3)
            track.currentIndexChanged.connect(lambda position, k=kind, r=row: self.track_chosen(k, r, position))
            language.editTextChanged.connect(lambda value, k=kind, r=row: self.language_typed(k, r, value))
            self.widgets[kind].append({"track": track, "language": language, "note": note})
        box.addLayout(grid)
        banner = QtWidgets.QLabel(tracks.banner(kind, model.output))
        banner.setWordWrap(True)
        banner.setStyleSheet(BANNER_STYLE)
        banner.setVisible(bool(tracks.banner(kind, model.output)))
        box.addWidget(banner)
        box.addStretch(1)
        return page

    # ------------------------------------------------------------------ reactions
    def track_chosen(self, kind: str, row: int, position: int) -> None:
        self.model.select(kind, row, position)
        language = self.widgets[kind][row]["language"]
        language.setCurrentText(self.model.rows[kind][row].language)       # the code the track has in the file
        self.refresh()

    def language_typed(self, kind: str, row: int, text: str) -> None:
        self.model.set_language(kind, row, text)
        self.refresh()

    def refresh(self) -> None:
        """The note or result of every row, the error line and OK."""
        model = self.model
        for kind, rows in self.widgets.items():
            for row, w in enumerate(rows):
                used = model.rows[kind][row].track is not None
                w["language"].setEnabled(used)
                w["note"].setText(model.result_text(kind, row) if kind == "subtitle" else model.note(kind, row))
        self.error.setText("\n".join(model.errors()))
        ok = self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setEnabled(not model.errors())

    def use_defaults(self) -> None:
        """The button Defaults: go on without a choice (the caller decides what the defaults are)."""
        self.defaults = True
        self.accept()

    def choice(self) -> tracks.Choice:
        return self.model.choice()


def run_dialog(parent, track_list, output: str, file_text: str, initial: Optional[tracks.Choice] = None, main_audio: int = 0, dvd: bool = False, source_note: str = ""):
    """Shows the dialog. Returns the choice (OK), DEFAULTS (the button Defaults: go on with the defaults) or None (Cancel: stop saving). dvd (DVD mode): the stream id of every track
    is part of its line. source_note: where the languages come from (DVD mode: the IFO file), shown under the file name."""
    dialog = TracksDialog(tracks.TracksModel(track_list, output, initial, main_audio, dvd), file_text, parent, source_note)
    try:
        if not dialog.exec():
            return None
        return DEFAULTS if dialog.defaults else dialog.choice()
    finally:
        dialog.deleteLater()
