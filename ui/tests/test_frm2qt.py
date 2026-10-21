"""Test von frm2qt.py ohne installiertes Qt: erzeugt den Code für alle Formulare und führt ihn gegen einen streng
modellierten Qt-Ersatz (tests/qtstub) aus. Geprüft werden Klassen, Lage, Texte, Sichtbarkeit, Elternbeziehung,
Stapelreihenfolge, Menüs, Tastenkürzel, Tabulatorreihenfolge und die Verbindung der Ereignisse.

Aufruf:  python3 tests/test_frm2qt.py ORDNER_MIT_FRM_DATEIEN
Dieser Test ersetzt keinen Lauf mit PySide6; er findet aber Fehler in der Umsetzung und erfundene Qt-Methoden.
"""
import glob
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "qtstub"))        # der Ersatz hat Vorrang vor einem echten PySide6
sys.path.insert(1, os.path.dirname(HERE))

import frm2qt
from frmparse import geometry_px
from PySide6 import QtGui, QtWidgets

EXPECT = {"VB.CommandButton": QtWidgets.QPushButton, "VB.Label": QtWidgets.QLabel, "VB.CheckBox": QtWidgets.QCheckBox,
          "VB.OptionButton": QtWidgets.QRadioButton, "VB.ComboBox": QtWidgets.QComboBox,
          "VB.VScrollBar": QtWidgets.QScrollBar, "VB.HScrollBar": QtWidgets.QScrollBar,
          "MSComctlLib.Slider": QtWidgets.QSlider, "MSComctlLib.TabStrip": QtWidgets.QTabBar,
          "VB.Line": QtWidgets.QFrame}
TEXT_TYPES = {"VB.CommandButton", "VB.Label", "VB.CheckBox", "VB.OptionButton"}
errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


def load(path):
    spec = importlib.util.spec_from_file_location("gen_" + os.path.basename(path)[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def widget_of(obj, c, arrays):
    n = frm2qt.ident(c.name)
    attr = getattr(obj, n)
    return attr[c.index] if c.name in arrays else attr


def test_fit_labels():
    """fit_labels verbreitert zu schmale Beschriftungen, aber nie über einen Nachbarn in derselben Zeile hinaus."""
    import vbqt
    from PySide6 import QtCore
    from PySide6.QtWidgets import FontMetrics
    FontMetrics.px_per_char = 8
    try:
        for neighbour_left, expected in ((70, 60), (None, 15 * 8 + 2 + 6), (60, 50)):
            parent = QtWidgets.QWidget()
            label = QtWidgets.QLabel(parent)
            label.setText("Audio sampling:")
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
            label.setGeometry(8, 10, 50, 17)
            if neighbour_left is not None:
                box = QtWidgets.QLineEdit(parent)
                box.setGeometry(neighbour_left, 10, 80, 17)
                hidden = QtWidgets.QLineEdit(parent)       # versteckte Nachbarn zählen nicht
                hidden.setGeometry(55, 10, 20, 17)
                hidden.hide()
            vbqt.fit_labels(parent)
            width = label.geometry().width()
            check(width == expected, f"fit_labels: Nachbar bei {neighbour_left}: Breite {width} statt {expected}")
    finally:
        FontMetrics.px_per_char = 1


def main():
    test_fit_labels()
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = tempfile.mkdtemp()
    sys.path.insert(2, out)
    total = collections = 0
    for path in sorted(glob.glob(os.path.join(sys.argv[1], "*.frm"))):
        QtWidgets.QWidget.setTabOrder_calls.clear()
        res = frm2qt.convert(path, out, stub=False)
        form = res["form"]
        mod = load(res["module"])
        cls = getattr(mod, form.name + "Base")
        obj = cls()
        gen = frm2qt.Generator(form, out)                     # nur für arrays/Menüs der Prüfung
        arrays = gen.arrays
        n_checked = 0
        for c in form.root.walk():
            if c is form.root or c.type in ("VB.Menu",):
                continue
            tag = f"{form.name}.{c.name}" + (f"({c.index})" if c.index is not None else "")
            w = widget_of(obj, c, arrays)
            n_checked += 1
            want_geo = getattr(c, "px_override", None) or geometry_px(c)
            check(w.called("setGeometry") == [want_geo], f"{tag}: Lage {w.called('setGeometry')} statt {want_geo}")
            if c.type in EXPECT:
                check(isinstance(w, EXPECT[c.type]), f"{tag}: Klasse {type(w).__name__} statt {EXPECT[c.type].__name__}")
            if c.type in TEXT_TYPES and c.get("Caption") is not None and c.type != "VB.Label":
                check(w.called("setText") == [(c.get("Caption"),)], f"{tag}: Text {w.called('setText')}")
            if not c.flag("Visible", True):
                check(w.called("hide") != [], f"{tag}: unsichtbares Steuerelement wird nicht versteckt")
            # Elternbeziehung
            if c.parent is form.root:
                expected_parent = obj.centralWidget_ if hasattr(obj, "centralWidget_") else obj
                central = [x for x in obj.children_ if type(x).__name__ == "QWidget"]
                ok = w.parent_ is obj or (gen.is_main_window and w.parent_ in central)
                check(ok, f"{tag}: falsches Elternelement")
            else:
                check(w.parent_ is widget_of(obj, c.parent, arrays), f"{tag}: Elternelement ist nicht {c.parent.name}")
        # Stapelreihenfolge: zuletzt in der Datei = zuerst erzeugt
        top = [c for c in form.root.children if c.type != "VB.Menu"]
        if len(top) > 1:
            parent_w = widget_of(obj, top[0], arrays).parent_
            created = [x for x in parent_w.children_ if any(widget_of(obj, t, arrays) is x for t in top)]
            expected = [widget_of(obj, t, arrays) for t in reversed(top)]
            check(created == expected, f"{form.name}: Stapelreihenfolge stimmt nicht")
        # Menüs
        leaves = [m for m in form.root.walk() if m.type == "VB.Menu" and m.get("Caption") != "-" and
                  not any(k.type == "VB.Menu" for k in m.children)]
        for m in leaves:
            act = widget_of(obj, m, arrays)
            check(isinstance(act, QtGui.QAction), f"{form.name}.{m.name}: kein QAction")
            sc = gen.shortcut(m.get("Shortcut"))
            if sc:
                got = act.called("setShortcut")
                check(len(got) == 1 and got[0][0]._args == (sc,), f"{form.name}.{m.name}: Tastenkürzel {got} statt {sc}")
        # Ereignisse: Unterklasse mit Aufzeichnung der Aufrufe
        calls = []
        procs = {f"{h.control}_{h.event}" for h in form.handlers}
        Sub = type("Sub", (cls,), {p: (lambda self, *a, _p=p: calls.append((_p, a))) for p in procs})
        sub = Sub()
        types = {c.name: c.type for c in form.root.walk()}
        for h in form.handlers:
            if h.control not in types:
                continue
            tpl = frm2qt.EVENTS.get((types[h.control], h.event))
            if not tpl or ".connect(" not in tpl:
                continue
            sig_name = tpl.split(".")[1].split(".")[0] if False else tpl.split("{w}.")[1].split(".connect")[0]
            elems = [c for c in form.root.walk() if c.name == h.control and c is not form.root]
            for c in elems:
                calls.clear()
                w = widget_of(sub, c, arrays)
                if types[h.control] == "VB.Menu" and any(k.type == "VB.Menu" for k in c.children):
                    sig = w.aboutToShow
                else:
                    sig = getattr(w, sig_name)
                sig.emit(1)
                expected = (f"{h.control}_{h.event}", (c.index,) if h.control in arrays else ())
                check(calls == [expected], f"{form.name}: {h.control}_{h.event}: Aufruf {calls} statt {[expected]}")
                collections += 1
        total += n_checked
        print(f"{os.path.basename(path):20s} {n_checked:3d} Steuerelemente, {len(leaves):2d} Menüeinträge, "
              f"{len(QtWidgets.QWidget.setTabOrder_calls):2d} Tabulatorschritte, {len(form.handlers):2d} Ereignisprozeduren")
    print(f"\nGeprüft: {total} Steuerelemente, {collections} Ereignisverbindungen (Signal -> Prozedur mit Index)")
    if errors:
        print(f"\n{len(errors)} FEHLER:")
        for e in errors[:40]:
            print("  -", e)
        sys.exit(1)
    print("Alle Prüfungen bestanden.")


if __name__ == "__main__":
    main()
