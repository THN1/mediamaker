"""Eigene Dialoge (Qt): Bearbeiten von Schlüssel-Wert-Paaren für Profil und Optionen."""
from __future__ import annotations

import textwrap
from typing import Optional

from PySide6 import QtCore, QtWidgets

from profiles import wrapped_lines

FIELD_WIDTH = 230                  # Breite der Eingabefelder in Pixeln; längere Werte werden umbrochen
LONG_TEXT_KEYS = ("description",)  # Schlüssel mit langem Freitext: immer mehrzeilig (mindestens 2 Zeilen)
_ENTER_KEYS = (0x01000004, 0x01000005)


class WrappedEdit(QtWidgets.QPlainTextEdit):
    """Mehrzeiliges Eingabefeld für lange Werte. Der Zeilenumbruch gilt nur der Anzeige: Der Wert bleibt eine Zeile,
    Enter bestätigt den Dialog, Tab springt zum nächsten Feld."""

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


TOOLTIP_WIDTH = 70               # Zeichen je Zeile in Tooltips


def wrap_tooltip(text: str, width: int = TOOLTIP_WIDTH) -> str:
    """Bricht einen langen Tooltip-Text in mehrere Zeilen um. Qt bricht reinen Text im Tooltip nicht selbst um; Zeilenumbrüche
    im Text bleiben aber erhalten. Wörter (auch lange Adressen) werden nicht getrennt."""
    if not text:
        return ""
    return "\n".join(textwrap.fill(line, width=width, break_long_words=False, break_on_hyphens=False) if line.strip() else ""
                     for line in text.split("\n"))


def edit_pairs(parent, title: str, pairs: dict, tooltips: dict, presets: dict, groups=None) -> Optional[dict]:
    """Zeigt je Schlüssel eine Zeile (Beschriftung mit Erklärung, Eingabefeld, bei Vorschlägen eine Auswahlliste).

    Rückgabe: die geänderten Werte als Wörterbuch oder None bei Abbruch. Ersetzt frmProfile aus VB6, ohne das Fenster
    zur Laufzeit von Hand zu vergrößern: Die Anordnung übernimmt ein Layout; lange Werte (z. B. die Beschreibung)
    brechen in einem mehrzeiligen Feld um, damit der Dialog schmal bleibt.

    groups = ((Überschrift, (Schlüssel, ...)), ...) gliedert die Zeilen unter Überschriften; Schlüssel, die in keiner Gruppe
    vorkommen, folgen am Ende unter "Other". Ohne groups erscheinen alle Zeilen in der Reihenfolge von `pairs`.
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
    if not dialog.exec():                                      # 1 = angenommen, 0 = abgebrochen
        return None
    return {key: getter().strip() for key, getter in getters.items()}


class WaitDialog(QtWidgets.QDialog):
    """Meldung "..., please wait..." während einer längeren Arbeit (VB6: frmWait). Abbrechen (Knopf oder Esc) ruft on_cancel."""

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


# ----------------------------------------------------------------------------- Eingabefelder wie die InputBox von VB6
INPUT_BOX_WIDTH = 440            # Breite in Pixeln (etwa die einer VB6-InputBox); lange Texte werden umgebrochen


def _input_box(parent, title: str, prompt: str, mode) -> QtWidgets.QInputDialog:
    """Eingabedialog mit fester Breite und umgebrochenem Text. Qt macht den Dialog sonst so breit wie die längste Zeile
    des Textes, was bei den langen Erklärungen (z. B. beim Schätzen der Bitrate) viel zu breit wird."""
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
    """Text eingeben (VB6: InputBox). None bei Abbruch."""
    box = _input_box(parent, title, prompt, QtWidgets.QInputDialog.InputMode.TextInput)
    box.setTextValue(default)
    return box.textValue() if box.exec() else None


def ask_int_box(parent, title: str, prompt: str, value: int, low: int, high: int) -> Optional[int]:
    """Ganze Zahl eingeben. None bei Abbruch."""
    box = _input_box(parent, title, prompt, QtWidgets.QInputDialog.InputMode.IntInput)
    box.setIntRange(low, high)
    box.setIntValue(value)
    return box.intValue() if box.exec() else None
