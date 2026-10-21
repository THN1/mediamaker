"""Own dialogs (Qt): editing of key-value pairs for profile and options."""
from __future__ import annotations

import textwrap
from typing import Optional

from PySide6 import QtCore, QtWidgets

from profiles import wrapped_lines

FIELD_WIDTH = 230                  # width of the input fields in pixels; longer values are wrapped
LONG_TEXT_KEYS = ("description",)  # keys with long free text: always multi-line (at least 2 lines)
_ENTER_KEYS = (0x01000004, 0x01000005)


class WrappedEdit(QtWidgets.QPlainTextEdit):
    """Multi-line input field for long values. The line wrapping is only for display: the value stays one line,
        Enter confirms the dialog, Tab jumps to the next field."""

    def __init__(self, text: str, on_enter):
        super().__init__()
        self._on_enter = on_enter
        self.setPlainText(text)
        self.setTabChangesFocus(True)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumWidth(FIELD_WIDTH)
        fm = self.fontMetrics()
        lines = wrapped_lines(fm.horizontalAdvance(text), FIELD_WIDTH, min_lines=2, max_lines=4)
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


def edit_pairs(parent, title: str, pairs: dict, tooltips: dict, presets: dict, groups=None) -> Optional[dict]:
    """Shows one row per key (caption with explanation, input field, a selection list for suggestions).

        Returns: the changed values as a dictionary or None on cancel. Replaces frmProfile from VB6, without enlarging the window
        by hand at run time: a layout takes care of the arrangement; long values (e.g. the description)
        wrap in a multi-line field so that the dialog stays narrow.

        groups = ((heading, (key, ...)), ...) arranges the rows under headings; keys that do not occur in any group
        follow at the end under "Other". Without groups all rows appear in the order of `pairs`.
    """
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    layout = QtWidgets.QVBoxLayout(dialog)
    form = QtWidgets.QFormLayout()
    getters = {}
    if groups:
        grouped = [(heading, [k for k in keys if k in pairs]) for heading, keys in groups]
        rest = [k for k in pairs if not any(k in keys for _, keys in groups)]
        if rest:
            grouped.append(("Other", rest))
        plan = [(heading, keys) for heading, keys in grouped if keys]
    else:
        plan = [(None, list(pairs))]
    rows = [(heading if i == 0 else None, key) for heading, keys in plan for i, key in enumerate(keys)]
    for heading, key in rows:
        value = pairs[key]
        if heading is not None:
            caption = QtWidgets.QLabel(f"<b>{heading}</b>")
            form.addRow(caption)
        tip = wrap_tooltip(tooltips.get(key, ""))
        label = QtWidgets.QLabel(key)
        if key in presets:
            editor = QtWidgets.QComboBox()
            editor.setEditable(True)
            editor.addItems(presets[key])
            editor.setCurrentText(value)
            editor.setMinimumWidth(FIELD_WIDTH)
            getters[key] = editor.currentText
        elif key in LONG_TEXT_KEYS or QtWidgets.QLabel(value).fontMetrics().horizontalAdvance(value) > FIELD_WIDTH - 12:
            editor = WrappedEdit(value, dialog.accept)
            getters[key] = editor.value
        else:
            editor = QtWidgets.QLineEdit(value)
            editor.setMinimumWidth(FIELD_WIDTH)
            getters[key] = editor.text
        label.setToolTip(tip)
        editor.setToolTip(tip)
        form.addRow(label, editor)
    layout.addLayout(form)
    button = QtWidgets.QDialogButtonBox.StandardButton
    buttons = QtWidgets.QDialogButtonBox(button.Ok | button.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if not dialog.exec():                                      # 1 = accepted, 0 = cancelled
        return None
    return {key: getter().strip() for key, getter in getters.items()}


class WaitDialog(QtWidgets.QDialog):
    """Message "..., please wait..." during a longer task (VB6: frmWait). Cancel (button or Esc) calls on_cancel."""

    def __init__(self, parent, message: str, on_cancel):
        super().__init__(parent)
        self._on_cancel = on_cancel
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)
        self.setModal(True)
        self.setStyleSheet("QDialog { background-color: rgb(0, 64, 192); } "
                           "QLabel { background-color: white; border: 1px solid gray; padding: 6px; }")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QtWidgets.QLabel(f"{message}, please wait...")
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setMinimumWidth(360)
        self.label = label
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(lambda *args: self.reject())
        layout.addWidget(label)
        layout.addWidget(cancel)

    def set_text(self, text: str) -> None:
        self.label.setText(text)

    def reject(self) -> None:
        self._on_cancel()
        super().reject()


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


def ask_int_box(parent, title: str, prompt: str, value: int, low: int, high: int) -> Optional[int]:
    """Enter a whole number. None on cancel."""
    box = _input_box(parent, title, prompt, QtWidgets.QInputDialog.InputMode.IntInput)
    box.setIntRange(low, high)
    box.setIntValue(value)
    return box.intValue() if box.exec() else None
