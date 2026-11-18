"""Own dialogs (Qt): editing of key-value pairs for profile and options."""
from __future__ import annotations

import os
import re
import textwrap
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from profiles import wrapped_lines

FIELD_WIDTH = 230                  # width of the input fields in pixels; longer values are wrapped
LONG_TEXT_KEYS = ("description", "path_map")  # keys with long free text: always multi-line (at least 2 lines)
_ENTER_KEYS = (0x01000004, 0x01000005)


def ui_factor(parent) -> float:
    """Size of the main window (UI_SCALE in percent, see uiscale.py) as a factor; 1 without a main window."""
    return getattr(parent, "UI_SCALE", 100) / 100


def scale_font(widget, factor: float, parent=None) -> None:
    """The dialog gets the font of the main window (its central widget: the font of the form, scaled by UI_SCALE, see uiscale.py), so that the dialogs match it. Without a main
    window that has such a font the font of `widget` is made `factor` times as big; nothing changes at 1."""
    if factor == 1:
        return
    central = getattr(parent, "centralWidget", None)
    window_font = central().font() if callable(central) else None
    if window_font is not None and window_font.pointSizeF() > 0:
        widget.setFont(window_font)
        return
    font = widget.font()
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * factor)
        widget.setFont(font)


class WrappedEdit(QtWidgets.QPlainTextEdit):
    """Multi-line input field for long values. The line wrapping is only for display: the value stays one line,
        Enter confirms the dialog, Tab jumps to the next field."""

    def __init__(self, text: str, on_enter, width: int = FIELD_WIDTH):
        super().__init__()
        self._on_enter = on_enter
        self.setPlainText(text)
        self.setTabChangesFocus(True)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumWidth(width)
        fm = self.fontMetrics()
        lines = wrapped_lines(fm.horizontalAdvance(text), width, min_lines=2, max_lines=4)
        self.setFixedHeight(lines * fm.lineSpacing() + 2 * self.frameWidth() + 2 * int(self.document().documentMargin()) + 2)

    def keyPressEvent(self, event):
        if event.key() in _ENTER_KEYS:
            self._on_enter()
            return
        super().keyPressEvent(event)

    def value(self) -> str:
        return self.toPlainText().replace("\n", " ")


TOOLTIP_WIDTH = 70               # characters per line in tooltips


def wrap_tooltip(text: str, width: int = TOOLTIP_WIDTH) -> str:
    """Wraps a long tooltip text into several lines. Qt does not wrap plain text in a tooltip by itself; line breaks
        in the text are kept, though. Words (also long addresses) are not split."""
    if not text:
        return ""
    return "\n".join(textwrap.fill(line, width=width, break_long_words=False, break_on_hyphens=False) if line.strip() else ""
                     for line in text.split("\n"))


TAB_PADDING = 40                 # pixels per tab for the space around its text (depends on the style, generous)
TAB_MARGIN = 40                  # room for the frame of the tab widget and the margins of the dialog


def fit_tabs(dialog, tabs, labels, factor: float = 1) -> None:
    """Makes sure all tabs are completely visible: no elided text, no scroll buttons, and the dialog is at least as wide as all
    the tabs side by side (otherwise Qt would elide the names or hide tabs behind scroll arrows)."""
    tabs.setUsesScrollButtons(False)
    tabs.setElideMode(QtCore.Qt.TextElideMode.ElideNone)
    metrics = tabs.fontMetrics()
    dialog.setMinimumWidth(sum(metrics.horizontalAdvance(label) + round(TAB_PADDING * factor) for label in labels) + round(TAB_MARGIN * factor))


NAV_STYLE = "tabs"               # "tabs": tabs along the top, "list": list of the groups on the left (INI: dialog_style)
LIST_PADDING = 40                # pixels around the longest name in the list on the left


def set_style(value) -> str:
    """Sets the style of the dialogs with several pages from the INI value dialog_style ("list" or anything else for "tabs")."""
    global NAV_STYLE
    NAV_STYLE = "list" if (value or "").strip().lower() == "list" else "tabs"
    return NAV_STYLE


class Sections:
    """Named pages in one widget: tabs along the top (NAV_STYLE "tabs") or a list of the names on the left with the page next to it
    ("list", like the settings dialogs of many programs). Used by the options dialog and the Media info dialog."""

    def __init__(self, style=None):
        self.style = style or NAV_STYLE
        self.names: list = []
        self.tabs = None
        if self.style == "list":
            self.widget = QtWidgets.QWidget()
            row = QtWidgets.QHBoxLayout(self.widget)
            row.setContentsMargins(0, 0, 0, 0)
            self.list = QtWidgets.QListWidget()
            self.stack = QtWidgets.QStackedWidget()
            self.list.currentRowChanged.connect(self.stack.setCurrentIndex)
            row.addWidget(self.list)
            row.addWidget(self.stack, 1)
        else:
            self.tabs = self.widget = QtWidgets.QTabWidget()

    def add(self, name: str, page) -> None:
        self.names.append(name)
        if self.tabs is not None:
            self.tabs.addTab(page, name)
        else:
            self.list.addItem(name)
            self.stack.addWidget(page)

    def set_current(self, index: int) -> None:
        index = max(0, min(index, len(self.names) - 1))
        if self.tabs is not None:
            self.tabs.setCurrentIndex(index)
        else:
            self.list.setCurrentRow(index)
            self.stack.setCurrentIndex(index)

    def current(self) -> int:
        return self.tabs.currentIndex() if self.tabs is not None else self.list.currentRow()

    def fit(self, dialog, factor: float = 1) -> None:
        """Makes sure all names are completely visible (tabs: dialog at least as wide as all tabs; list: wide enough for the longest). `factor`: size of the main window."""
        if self.tabs is not None:
            fit_tabs(dialog, self.tabs, self.names, factor)
        else:
            metrics = self.list.fontMetrics()
            self.list.setFixedWidth(max(metrics.horizontalAdvance(n) for n in self.names) + round(LIST_PADDING * factor))


def group_plan(pairs: dict, groups) -> list:
    """[(heading, [keys])] of the tabs: the groups with the keys that are present, then the keys of no group under "Other"."""
    plan = [(heading, [k for k in keys if k in pairs]) for heading, keys in groups]
    rest = [k for k in pairs if not any(k in keys for _, keys in groups)]
    if rest:
        plan.append(("Other", rest))
    return [(heading, keys) for heading, keys in plan if keys]


def error_in_advanced(errors: list, advanced) -> bool:
    """Does one of the error messages ('"logo_conf" must be ...') name an advanced option? (Then the dialog has to show the advanced options again.)"""
    keys = {k for names in (advanced or {}).values() for k in names}
    return any(m and m.group(1) in keys for m in (re.search(r'"(\w+)"', message) for message in errors))


def set_row_visible(form, label, editor, on: bool) -> None:
    """Shows or hides a row of a form and makes it editable only while it is shown. (QFormLayout.setRowVisible, new in Qt 6.4, also takes the room of the row away.)"""
    try:
        form.setRowVisible(editor, on)
    except (AttributeError, TypeError):
        pass
    label.setVisible(on)
    editor.setVisible(on)
    editor.setEnabled(on)


def tab_of_error(errors: list, pairs: dict, groups) -> int:
    """Index of the tab that holds the first key named in the error messages (messages look like '"crop" must be ...')."""
    for message in errors:
        m = re.search(r'"(\w+)"', message)
        if m:
            for i, (_, keys) in enumerate(group_plan(pairs, groups)):
                if m.group(1) in keys:
                    return i
    return 0


LIST_DIALOG_WIDTH = 0.6          # of the width that the dialog would have by itself (the descriptions of the profiles are long)


def narrowed_size(width: int, height: int, height_for_width, factor: float = LIST_DIALOG_WIDTH) -> tuple:
    """(width, height) of a dialog that is made narrower: `factor` of its own width; the height is what the text needs at that width (the label wraps), but at least
    the height it had. `height_for_width` is a function width -> height (or returns -1 if the layout does not know)."""
    new_width = max(1, round(width * factor))
    needed = height_for_width(new_width)
    return new_width, max(height, needed if needed and needed > 0 else height)


def choose_from_list(parent, title: str, label: str, items: list, current: int = 0, factor: float = LIST_DIALOG_WIDTH) -> Optional[int]:
    """The user picks one entry of a list (`current` is preselected) in a dialog that is `factor` as wide as it would be by itself; None if it is cancelled."""
    dialog = QtWidgets.QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setComboBoxItems(items)
    dialog.setComboBoxEditable(False)
    dialog.setTextValue(items[current] if 0 <= current < len(items) else items[0])
    for text_label in dialog.findChildren(QtWidgets.QLabel):               # (the text must wrap, otherwise its longest line decides the width)
        text_label.setWordWrap(True)
    hint = dialog.sizeHint()
    layout = dialog.layout()
    width, height = narrowed_size(hint.width(), hint.height(), (lambda w: layout.totalHeightForWidth(w)) if layout is not None else (lambda w: -1), factor)
    dialog.resize(width, height)
    if not dialog.exec():
        return None
    text = dialog.textValue()
    return items.index(text) if text in items else None


def edit_pairs(parent, title: str, pairs: dict, tooltips: dict, presets: dict, groups=None, start: int = 0,
               texts=None, advanced=None, show_advanced: bool = False) -> Optional[dict]:
    """Shows one row per key (caption with explanation, input field, a selection list for suggestions).

        Returns: the changed values as a dictionary or None on cancel. Replaces frmProfile from VB6, without enlarging the window
        by hand at run time: a layout takes care of the arrangement; long values (e.g. the description)
        wrap in a multi-line field so that the dialog stays narrow.

        groups = ((heading, (key, ...)), ...) puts the rows on tabs along the top, one tab per group; keys that do not occur in any
        group follow at the end on the tab "Other"; `start` is the tab shown first; texts = {heading: one line of explanation} is
        shown above the rows of the page. Without groups all rows appear in one list in the order of `pairs` (the profile).

        advanced = {heading: (key, ...)}: on such a page these keys follow the other rows under a check box "Show advanced options", which is OFF every time the dialog
        opens (show_advanced=True: ON, used when an advanced value was wrong); the rows appear when it is ticked, and only then can they be changed (their values are
        returned unchanged otherwise).
    """
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    factor = ui_factor(parent)                                 # like the main window: font, fields and window are larger when UI_SCALE is (see uiscale.py)
    scale_font(dialog, factor, parent)                         # the font of the main window (before the widgets exist: they take the font of the dialog)
    field_width = round(FIELD_WIDTH * factor)
    layout = QtWidgets.QVBoxLayout(dialog)
    getters = {}

    def add_rows(form, keys):
        made = []
        for key in keys:
            value = pairs[key]
            tip = wrap_tooltip(tooltips.get(key, ""))
            label = QtWidgets.QLabel(key)
            if key in presets:
                editor = QtWidgets.QComboBox()
                editor.setEditable(True)
                editor.addItems(presets[key])
                editor.setCurrentText(value)
                editor.setMinimumWidth(field_width)
                getters[key] = editor.currentText
            elif key in LONG_TEXT_KEYS or QtWidgets.QLabel(value).fontMetrics().horizontalAdvance(value) > field_width - round(12 * factor):
                editor = WrappedEdit(value, dialog.accept, field_width)
                getters[key] = editor.value
            else:
                editor = QtWidgets.QLineEdit(value)
                editor.setMinimumWidth(field_width)
                getters[key] = editor.text
            label.setToolTip(tip)
            editor.setToolTip(tip)
            form.addRow(label, editor)
            made.append((label, editor))
        return made

    if groups:
        sections = Sections()
        for heading, keys in group_plan(pairs, groups):
            page = QtWidgets.QWidget()
            # The rows sit at the top of the page: a stretch below them takes the free space (otherwise a page with a single
            # multi-line field, e.g. path_map, gets all of it and the row ends up in the middle).
            outer = QtWidgets.QVBoxLayout(page)
            if texts and texts.get(heading):
                note = QtWidgets.QLabel(texts[heading])
                note.setWordWrap(True)
                outer.addWidget(note)
            form = QtWidgets.QFormLayout()
            form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
            advanced_keys = [k for k in keys if k in (advanced or {}).get(heading, ())]
            add_rows(form, [k for k in keys if k not in advanced_keys])
            if advanced_keys:
                tick = QtWidgets.QCheckBox("Show advanced options")
                tick.setChecked(show_advanced)
                form.addRow(tick)
                rows = add_rows(form, advanced_keys)
                tick.toggled.connect(lambda on, rows=rows, form=form: [set_row_visible(form, label, editor, bool(on)) for label, editor in rows])
                for label, editor in rows:
                    set_row_visible(form, label, editor, show_advanced)
            outer.addLayout(form)
            outer.addStretch(1)
            sections.add(heading, page)
        sections.fit(dialog, factor)
        sections.set_current(start)
        layout.addWidget(sections.widget)
    else:
        form = QtWidgets.QFormLayout()
        add_rows(form, list(pairs))
        layout.addLayout(form)
    button = QtWidgets.QDialogButtonBox.StandardButton
    buttons = QtWidgets.QDialogButtonBox(button.Ok | button.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if not dialog.exec():                                      # 1 = accepted, 0 = cancelled
        return None
    return {key: getter().strip() for key, getter in getters.items()}


# ----------------------------------------------------------------------------- input fields like the InputBox of VB6
INPUT_BOX_WIDTH = 440            # width in pixels (about that of a VB6 InputBox); long texts are wrapped


def _input_box(parent, title: str, prompt: str, mode) -> QtWidgets.QInputDialog:
    """Input dialog with a fixed width and wrapped text. Otherwise Qt makes the dialog as wide as the longest line
        of the text, which gets far too wide with the long explanations (e.g. when estimating the bit rate)."""
    box = QtWidgets.QInputDialog(parent)
    box.setWindowTitle(title)
    box.setInputMode(mode)
    box.setLabelText(prompt)
    for label in box.findChildren(QtWidgets.QLabel):
        label.setWordWrap(True)
    box.setFixedWidth(INPUT_BOX_WIDTH)
    layout = box.layout()
    height = box.sizeHint().height()
    if layout is not None and layout.hasHeightForWidth():
        height = max(height, layout.totalHeightForWidth(INPUT_BOX_WIDTH))
    box.resize(INPUT_BOX_WIDTH, height)
    return box


def ask_text_box(parent, title: str, prompt: str, default: str = "") -> Optional[str]:
    """Enter text (VB6: InputBox). None on cancel."""
    box = _input_box(parent, title, prompt, QtWidgets.QInputDialog.InputMode.TextInput)
    box.setTextValue(default)
    return box.textValue() if box.exec() else None


def array_pixmap(rgb, width: int = 0):
    """QPixmap from an RGB array (height, width, 3), optionally scaled to `width` (smooth)."""
    import numpy as np
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    height, wide = rgb.shape[:2]
    image = QtGui.QImage(rgb.data, wide, height, 3 * wide, QtGui.QImage.Format.Format_RGB888).copy()
    if width and width != wide:
        image = image.scaledToWidth(width, QtCore.Qt.TransformationMode.SmoothTransformation)
    return QtGui.QPixmap.fromImage(image)


def reference_logo_box(parent, text: str, rgb, rect: tuple, edges) -> None:
    """Message about the new reference logo with pictures: the whole frame it was taken from (the rectangle marked), the area of the logo
    enlarged, and its edges."""
    import numpy as np
    left, top, right, bottom = rect
    marked = np.array(rgb, dtype=np.uint8)
    marked[top:top + 2, left:right], marked[max(bottom - 2, 0):bottom, left:right] = (255, 0, 0), (255, 0, 0)
    marked[top:bottom, left:left + 2], marked[top:bottom, max(right - 2, 0):right] = (255, 0, 0), (255, 0, 0)
    area = np.array(rgb[max(0, top - 6):bottom + 6, max(0, left - 6):right + 6], dtype=np.uint8)
    width = max(area.shape[1] * 4, 1)
    edge_picture = np.repeat(np.asarray(edges, dtype=np.uint8)[..., None] * 255, 3, axis=2)
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle("Reference logo")
    layout = QtWidgets.QVBoxLayout(dialog)
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    layout.addWidget(label)
    row = QtWidgets.QHBoxLayout()
    left_column = QtWidgets.QVBoxLayout()
    left_column.addWidget(QtWidgets.QLabel("Picture taken (the rectangle is marked):"))
    picture = QtWidgets.QLabel()
    picture.setPixmap(array_pixmap(marked, 360))
    left_column.addWidget(picture)
    row.addLayout(left_column)
    right_column = QtWidgets.QVBoxLayout()
    for caption, array in (("Area of the logo:", area), ("Its edges (white) that are searched for:", edge_picture)):
        right_column.addWidget(QtWidgets.QLabel(caption))
        holder = QtWidgets.QLabel()
        holder.setPixmap(array_pixmap(array, width))
        right_column.addWidget(holder)
    row.addLayout(right_column)
    layout.addLayout(row)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    try:
        dialog.exec()
    finally:
        dialog.deleteLater()


def confirm_with_checkbox(parent, text: str, checkbox_text: str) -> tuple:
    """Yes/No question with a check box that is NOT ticked at first and No as the default button. Returns (answered Yes, box ticked)."""
    box = QtWidgets.QMessageBox(parent)
    button = QtWidgets.QMessageBox.StandardButton
    box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    box.setWindowTitle("MediaMaker")
    box.setText(text)
    box.setStandardButtons(button.Yes | button.No)
    box.setDefaultButton(button.No)
    check = QtWidgets.QCheckBox(checkbox_text)
    check.setChecked(False)
    box.setCheckBox(check)
    try:
        answer = box.exec()
        return answer == button.Yes, bool(check.isChecked())
    finally:
        box.deleteLater()


def notice_with_checkbox(parent, text: str, checkbox_text: str, checked: bool = True) -> bool:
    """A warning with an OK button and a check box under the text (ticked at first). Returns whether the box is ticked when the window is closed."""
    box = QtWidgets.QMessageBox(parent)
    button = QtWidgets.QMessageBox.StandardButton
    box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    box.setWindowTitle("MediaMaker")
    box.setText(text)
    box.setStandardButtons(button.Ok)
    box.setDefaultButton(button.Ok)
    check = QtWidgets.QCheckBox(checkbox_text)
    check.setChecked(checked)
    box.setCheckBox(check)
    try:
        box.exec()
        return bool(check.isChecked())
    finally:
        box.deleteLater()


class OutputFileDialog(QtWidgets.QDialog):
    """Dialog for the target file: the folder in an editable selection list (the folders used recently) with a "Browse..." button, and the file name."""

    def __init__(self, parent, title: str, prompt: str, folders: list, folder: str, name: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(prompt)
        label.setWordWrap(True)
        layout.addWidget(label)
        form = QtWidgets.QFormLayout()
        self.combo = QtWidgets.QComboBox()
        self.combo.setEditable(True)
        self.combo.addItems([folder] + [f for f in folders if f != folder] if folder else list(folders))
        self.combo.setCurrentText(folder)
        self.combo.setMinimumWidth(FIELD_WIDTH * 2)
        self.combo.setToolTip(wrap_tooltip("Folders used recently; a folder can also be typed in"))
        browse = QtWidgets.QPushButton("Browse...")
        browse.clicked.connect(self.choose_folder)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.combo, 1)
        row.addWidget(browse)
        form.addRow("Folder:", row)
        self.edit = QtWidgets.QLineEdit(name)
        form.addRow("File name:", self.edit)
        layout.addLayout(form)
        button = QtWidgets.QDialogButtonBox.StandardButton
        buttons = QtWidgets.QDialogButtonBox(button.Ok | button.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_folder(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder", self.combo.currentText())
        if chosen:
            self.combo.setCurrentText(chosen)

    def path(self) -> Optional[str]:
        name = self.edit.text().strip()
        if not name:
            return None
        directory = os.path.expanduser(self.combo.currentText().strip())
        return os.path.join(directory, name) if directory else name


def ask_output_file(parent, title: str, prompt: str, folders: list, folder: str, name: str) -> Optional[str]:
    """Enter the target file: the folder in a selection list of the folders used recently and the file name. Returns the whole path or
    None on cancel (or without a file name). The dialog is deleted after use."""
    dialog = OutputFileDialog(parent, title, prompt, folders, folder, name)
    try:
        return dialog.path() if dialog.exec() else None
    finally:
        dialog.deleteLater()


class BitrateDialog(QtWidgets.QDialog):
    """One dialog for both bit rates (estimate): video and audio, each in its own field."""

    def __init__(self, parent, title: str, prompt: str, video: str, audio: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(INPUT_BOX_WIDTH)
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(prompt)
        label.setWordWrap(True)
        layout.addWidget(label)
        form = QtWidgets.QFormLayout()
        self.video = QtWidgets.QLineEdit(video)
        self.audio = QtWidgets.QLineEdit(audio)
        form.addRow("Video kb/s:", self.video)
        form.addRow("Audio kb/s:", self.audio)
        self.video.setFocus()
        self.video.selectAll()                                               # the number of the first field is selected (and the cursor is at its end), as in the old input box
        layout.addLayout(form)
        button = QtWidgets.QDialogButtonBox.StandardButton
        buttons = QtWidgets.QDialogButtonBox(button.Ok | button.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple:
        return self.video.text(), self.audio.text()


def ask_bitrates(parent, title: str, prompt: str, video: str, audio: str) -> Optional[tuple]:
    """Enter video and audio bit rate in one dialog. Returns (video text, audio text) or None on cancel."""
    dialog = BitrateDialog(parent, title, prompt, video, audio)
    try:
        return dialog.values() if dialog.exec() else None
    finally:
        dialog.deleteLater()


def ask_int_box(parent, title: str, prompt: str, value: int, low: int, high: int) -> Optional[int]:
    """Enter a whole number. None on cancel."""
    box = _input_box(parent, title, prompt, QtWidgets.QInputDialog.InputMode.IntInput)
    box.setIntRange(low, high)
    box.setIntValue(value)
    return box.intValue() if box.exec() else None
