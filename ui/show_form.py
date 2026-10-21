"""Zeigt ein erzeugtes Formular zur Ansicht (ohne Logik) oder speichert ein Bild davon.

Aufruf:  python3 show_form.py frmRemoveLogo [--dir ORDNER] [--shot bild.png]
ORDNER enthält die von frm2qt.py erzeugten Dateien (Standard: generated). Mit --shot wird das Fenster einmal
auf dem Bildschirm aufgebaut und als PNG gespeichert; so lässt sich die Ansicht mit der VB6-IDE vergleichen.
Das Fenster erscheint immer hell (Fusion-Stil); mit --system-theme gilt stattdessen das Thema des Desktops.
Mit --offscreen geschieht das ohne sichtbares Fenster; dann gelten aber andere Schriften und es erscheint die
Meldung "This plugin does not support propagateSizeHints()" (harmlos).
"""
import importlib
import os
import sys

if "--offscreen" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6 import QtCore, QtWidgets


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--") and sys.argv[sys.argv.index(a) - 1] not in ("--dir", "--shot")]
    if not args:
        sys.exit(__doc__)
    name = args[0]
    folder = sys.argv[sys.argv.index("--dir") + 1] if "--dir" in sys.argv else os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")
    sys.path.insert(0, os.path.abspath(folder))
    sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)))      # vbqt.py
    app = QtWidgets.QApplication(sys.argv)
    import vbqt
    if "--system-theme" not in sys.argv:
        vbqt.apply_light_theme(app)
    module = importlib.import_module(f"ui_{name}")
    window = getattr(module, f"{name}Base")()
    window.show()
    if "--shot" in sys.argv:
        out = sys.argv[sys.argv.index("--shot") + 1]
        app.processEvents()
        window.grab().save(out)
        print("gespeichert:", out)
        return
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
