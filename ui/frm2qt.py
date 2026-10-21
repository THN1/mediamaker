"""Übersetzt VB6-Formulare (.frm) in PySide6-Code.

Aufruf:  python3 frm2qt.py Formular.frm [weitere.frm ...] [--out ORDNER] [--stub]

Für jedes Formular entsteht ui_<Formularname>.py mit der Klasse <Formularname>Base (Oberfläche, Menüs, Ereignisse).
Die Logik gehört nicht dorthin, sondern in eine abgeleitete Klasse mit den Prozedurnamen aus VB6, z. B.
cmdOK_Click(self). Mit --stub wird dafür eine Vorlage <Formularname>.py angelegt (vorhandene Dateien bleiben unberührt).
Symbole aus der .frx-Datei werden nach ORDNER/icons als PNG geschrieben. Am Ende steht ein Bericht über alles,
was nicht übernommen werden konnte.
"""
from __future__ import annotations

import argparse
import collections
import keyword
import os
import re
import sys

from frmparse import Control, Form, Resource, TWIPS_PER_PIXEL, container_scale, form_client_px, geometry_px, parse_frm, vb_color
from frx import picture_to_png, read_list, read_picture, read_text

# Eigenschaften, die entweder ausgewertet werden oder bewusst keine Entsprechung brauchen
IGNORED = {"Left", "Top", "Width", "Height", "TabIndex", "Index", "_ExtentX", "_ExtentY", "_Version", "LinkTopic",
           "ScaleHeight", "ScaleWidth", "ClientLeft", "ClientTop", "ClientWidth", "ClientHeight", "AutoRedraw",
           "ScaleMode", "OLEDropMode", "Appearance", "NumItems", "LabelWrap", "HideSelection", "TickStyle",
           "TickFrequency", "MultiRow", "Tag", "ExtentWidth", "ExtentHeight", "BaseURL", "AutoLoop", "AutoPlay",
           "Toolbar", "StartTime", "FullscreenEnabled", "Branding", "Volume", "MRL"}
HANDLED = {"Caption", "Text", "Visible", "Enabled", "ToolTipText", "BackColor", "ForeColor", "BorderStyle",
           "StartUpPosition", "MaxButton", "MinButton", "ShowInTaskbar", "Icon", "Picture", "Style", "Default",
           "Cancel", "MultiLine", "Max", "Min", "LargeChange", "SmallChange", "Value", "View", "FullRowSelect",
           "HideColumnHeaders", "Checkboxes", "List", "ItemData", "Shortcut", "Checked", "X1", "X2", "Y1", "Y2", "BorderColor",
           "BorderWidth", "Alignment", "BackStyle", "Locked", "MaxLength", "PasswordChar", "LabelEdit", "Sorted"}
RESERVED = {"show", "hide", "close", "move", "resize", "update", "size", "pos", "width", "height", "font", "parent",
            "window", "geometry", "rect", "layout", "menu", "style", "icon", "title", "text", "raise", "lower"}
SYSTEM_ROLES = {5: "base", 15: "window", 8: "text", 18: "button-text", 13: "highlight", 14: "highlighted-text",
                16: "mid", 17: "mid", 20: "light", 21: "dark", 4: "window", 0: "window"}
DEFAULT_BACK = {"VB.TextBox": 5, "VB.ComboBox": 5, "MSComctlLib.ListView": 5}
DEFAULT_FORE = {"VB.CommandButton": 18}
FOCUSABLE = {"VB.CommandButton", "VB.TextBox", "VB.ComboBox", "VB.CheckBox", "VB.OptionButton", "MSComctlLib.ListView",
             "VB.VScrollBar", "VB.HScrollBar", "MSComctlLib.Slider", "MSComctlLib.TabStrip"}

# (Steuerelementtyp, Ereignis) -> Code zum Verbinden; {w} = Steuerelement, {cb} = Funktion
EVENTS = {
    ("VB.CommandButton", "Click"): "{w}.clicked.connect({cb})",
    ("VB.CommandButton", "MouseDown"): "vbqt.on_mouse({w}, down={cbv})",
    ("VB.CheckBox", "Click"): "{w}.clicked.connect({cb})",
    ("VB.OptionButton", "Click"): "{w}.clicked.connect({cb})",
    ("VB.OptionButton", "DblClick"): "vbqt.on_double_click({w}, {cb})",
    ("VB.ComboBox", "Click"): "{w}.activated.connect({cb})",
    ("VB.HScrollBar", "Change"): "{w}.valueChanged.connect({cb})",
    ("VB.VScrollBar", "Change"): "{w}.valueChanged.connect({cb})",
    ("VB.VScrollBar", "Scroll"): "{w}.sliderMoved.connect({cb})",
    ("VB.HScrollBar", "Scroll"): "{w}.sliderMoved.connect({cb})",
    ("MSComctlLib.Slider", "Change"): "{w}.valueChanged.connect({cb})",
    ("MSComctlLib.TabStrip", "Click"): "{w}.currentChanged.connect({cb})",
    ("MSComctlLib.ListView", "Click"): "{w}.itemClicked.connect({cb})",
    ("MSComctlLib.ListView", "DblClick"): "{w}.itemDoubleClicked.connect({cb})",
    ("MSComctlLib.ListView", "ItemCheck"): "{w}.itemChanged.connect({cb})",
    ("MSComctlLib.ListView", "KeyUp"): "vbqt.on_key({w}, up={cbv})",
    ("MSComctlLib.ListView", "OLEDragDrop"): "vbqt.on_drop({w}, {cbv})",
    ("VB.Label", "Click"): "vbqt.on_click({w}, {cb})",
    ("VB.PictureBox", "Click"): "vbqt.on_click({w}, {cb})",
    ("VB.PictureBox", "MouseMove"): "vbqt.on_mouse({w}, move={cbv})",
    ("VB.Frame", "MouseDown"): "vbqt.on_mouse({w}, down={cbv})",
    ("VB.Frame", "MouseMove"): "vbqt.on_mouse({w}, move={cbv})",
    ("VB.Frame", "MouseUp"): "vbqt.on_mouse({w}, up={cbv})",
    ("VB.Menu", "Click"): "{w}.triggered.connect({cb})",
}
FORM_EVENTS = ("Load", "Activate", "LostFocus", "Resize", "Unload")
KNOWN_EVENTS = {"Click", "DblClick", "Change", "Scroll", "MouseDown", "MouseMove", "MouseUp", "KeyDown", "KeyUp",
                "KeyPress", "GotFocus", "LostFocus", "ItemClick", "ItemCheck", "ColumnClick", "AfterLabelEdit",
                "BeforeLabelEdit", "OLEDragDrop", "OLEDragOver", "Paint", "Timer", "Validate", "DragDrop",
                "MediaPlayerEndReached", "MediaPlayerPaused", "MediaPlayerPlaying", "MediaPlayerStopped",
                "MediaPlayerTimeChanged", "DataArrival"}


def ident(name: str) -> str:
    return name + "_" if keyword.iskeyword(name) or name in RESERVED else name


def css_color(value, default_system=None):
    """Wert aus der .frm -> Stylesheet-Farbe ('rgb(...)' oder 'palette(...)'), None = Standard/unbekannt."""
    c = vb_color(value)
    if c is None:
        return None
    if c[0] == "system":
        if c[1] == default_system:
            return None
        role = SYSTEM_ROLES.get(c[1])
        return f"palette({role})" if role else None
    return "rgb(%d, %d, %d)" % c


class Generator:
    def __init__(self, form: Form, out_dir: str):
        self.form = form
        self.out_dir = out_dir
        self.frm_dir = os.path.dirname(os.path.abspath(form.path))
        self.lines: list[str] = []
        self.report = collections.defaultdict(set)         # Kategorie -> Einträge
        self.icons: list[str] = []
        self.tab_orders: list[list[tuple[int, str]]] = []
        self.arrays = self._find_arrays()
        self.menu_items = [c for c in form.root.children if c.type == "VB.Menu"]
        self.is_main_window = bool(self.menu_items)

    # ------------------------------------------------------------------ Hilfen
    def emit(self, text: str = "", indent: int = 2):
        self.lines.append("    " * indent + text if text else "")

    def _find_arrays(self) -> set:
        count = collections.Counter(c.name for c in self.form.root.walk() if c is not self.form.root)
        return {c.name for c in self.form.root.walk() if c is not self.form.root and (c.index is not None or count[c.name] > 1)}

    def var(self, c: Control) -> str:
        return "w_" + re.sub(r"\W", "_", c.name) + (f"_{c.index}" if c.index is not None else "")

    def target(self, c: Control) -> str:
        n = ident(c.name)
        return f"self.{n}[{c.index}]" if c.name in self.arrays else f"self.{n}"

    def icon_file(self, res: Resource) -> str | None:
        raw = read_picture(os.path.join(self.frm_dir, res.file), res.offset)
        if not raw:
            self.report["Bild nicht lesbar"].add(f"{res.file}:{res.offset:04X}")
            return None
        try:
            png = picture_to_png(raw)
        except Exception as e:                              # nicht unterstütztes Bildformat
            self.report["Bild nicht lesbar"].add(f"{res.file}:{res.offset:04X} ({e})")
            return None
        name = f"{os.path.splitext(res.file)[0]}_{res.offset:04X}.png"
        os.makedirs(os.path.join(self.out_dir, "icons"), exist_ok=True)
        with open(os.path.join(self.out_dir, "icons", name), "wb") as fh:
            fh.write(png)
        self.icons.append(name)
        return name

    def text(self, c: Control, key: str, default: str = "") -> str:
        """Texteigenschaft; liegt der Text in der .frx-Datei, wird er von dort gelesen."""
        v = c.get(key, default)
        if isinstance(v, Resource):
            r = read_text(os.path.join(self.frm_dir, v.file), v.offset)
            if r is None:
                self.report["Text nicht lesbar (.frx)"].add(f"{c.name}.{key}")
                return default
            return r
        return v

    def font_line(self, c: Control, w: str):
        f = c.sub.get("Font")
        if not f:
            return
        self.emit(f"{w}.setFont(vbqt.make_font({f.get('Name', 'MS Sans Serif')!r}, {float(f.get('Size', 8.25))}, "
                  f"{int(float(f.get('Weight', 400)))}, {int(f.get('Italic', 0) not in ('0', 0))}, "
                  f"{int(f.get('Underline', 0) not in ('0', 0))}, {int(f.get('Strikethrough', 0) not in ('0', 0))}))")

    def style_line(self, c: Control, w: str):
        parts = []
        back = css_color(c.get("BackColor"), DEFAULT_BACK.get(c.type, 15))
        fore = css_color(c.get("ForeColor"), DEFAULT_FORE.get(c.type, 8))
        if back and not (c.type == "VB.Label" and c.get("BackStyle") == "0"):
            parts.append(f"background-color: {back};")
        if fore:
            parts.append(f"color: {fore};")
        if parts:
            self.emit(f"{w}.setStyleSheet(\"#{self.var(c)[2:]} {{ {' '.join(parts)} }}\")")

    def common(self, c: Control, w: str):
        self.emit(f"{w}.setObjectName({self.var(c)[2:]!r})")
        tip = self.text(c, "ToolTipText")
        if tip:
            self.emit(f"{w}.setToolTip({tip!r})")
        self.font_line(c, w)
        self.style_line(c, w)
        if not c.flag("Enabled", True):
            self.emit(f"{w}.setEnabled(False)")
        if not c.flag("Visible", True):
            self.emit(f"{w}.hide()")

    def geometry(self, c: Control, w: str):
        x, y, wd, ht = getattr(c, "px_override", None) or geometry_px(c)
        self.emit(f"{w}.setGeometry({x}, {y}, {wd}, {ht})")

    def unhandled(self, c: Control):
        for k in c.props:
            if k not in IGNORED and k not in HANDLED:
                self.report[f"Eigenschaft nicht übernommen ({c.type})"].add(k)

    # ------------------------------------------------------------------ Steuerelemente
    def build_children(self, parent: Control, parent_var: str):
        chain = []
        # In der .frm steht das oberste Steuerelement zuerst; in Qt liegt das zuletzt erzeugte oben.
        for c in reversed(parent.children):
            if c.type == "VB.Menu":
                continue
            self.build_control(c, parent_var)
            if c.type in FOCUSABLE and c.flag("TabStop", True):
                chain.append((c.num("TabIndex"), self.var(c)))
        if len(chain) > 1:
            self.tab_orders.append(sorted(chain))

    def build_control(self, c: Control, parent: str):
        w = self.var(c)
        t = c.type
        self.emit(f"# {c.name}" + (f"({c.index})" if c.index is not None else "") + f": {t}", 2)
        make = getattr(self, "make_" + re.sub(r"\W", "_", t), None)
        if make is None:
            self.report["Unbekannter Steuerelementtyp (als leere Fläche)"].add(t)
            self.emit(f"{w} = QtWidgets.QWidget({parent})")
            self.emit(f"{w}.setToolTip({t + ' (nicht übersetzt)'!r})")
        else:
            make(c, w, parent)
        self.emit(f"{self.target(c)} = {w}")
        self.geometry(c, w)
        self.common(c, w)
        self.unhandled(c)
        if c.children and t in ("VB.Frame", "VB.PictureBox"):
            self.build_children(c, w)
        self.emit()

    def make_VB_CommandButton(self, c, w, parent):
        self.emit(f"{w} = QtWidgets.QPushButton({parent})")
        if self.text(c, "Caption"):
            self.emit(f"{w}.setText({self.text(c, 'Caption')!r})")
        self.emit(f"{w}.setAutoDefault(False)")
        pic = c.get("Picture")
        if c.get("Style") == "1" and isinstance(pic, Resource):
            name = self.icon_file(pic)
            if name:
                self.emit(f"{w}.setIcon(QtGui.QIcon(os.path.join(HERE, 'icons', {name!r})))")
        if c.flag("Default"):
            self.emit(f"{w}.setDefault(True)")
        if c.flag("Cancel"):
            self.emit(f"vbqt.set_cancel(self, {w})")

    def make_VB_Label(self, c, w, parent):
        self.emit(f"{w} = QtWidgets.QLabel({parent})")
        self.emit(f"{w}.setText({self.text(c, 'Caption')!r})")
        align = {"1": "AlignRight", "2": "AlignHCenter"}.get(c.get("Alignment"), "AlignLeft")
        self.emit(f"{w}.setAlignment(QtCore.Qt.AlignmentFlag.{align} | QtCore.Qt.AlignmentFlag.AlignTop)")
        if c.get("BorderStyle") == "1":
            self.emit(f"{w}.setFrameShape(QtWidgets.QFrame.Shape.Panel)")
            self.emit(f"{w}.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)")

    def make_VB_TextBox(self, c, w, parent):
        if c.flag("MultiLine"):
            self.emit(f"{w} = QtWidgets.QPlainTextEdit({parent})")
            self.emit(f"{w}.setPlainText({self.text(c, 'Text')!r})")
        else:
            self.emit(f"{w} = QtWidgets.QLineEdit({parent})")
            self.emit(f"{w}.setText({self.text(c, 'Text')!r})")
            if c.num("MaxLength"):
                self.emit(f"{w}.setMaxLength({c.num('MaxLength')})")
        if c.flag("Locked"):
            self.emit(f"{w}.setReadOnly(True)")

    def make_VB_ComboBox(self, c, w, parent):
        self.emit(f"{w} = QtWidgets.QComboBox({parent})")
        if c.get("Style", "0") in ("0", "1"):
            self.emit(f"{w}.setEditable(True)")
        items = data = None
        for key in ("List", "ItemData"):
            res = c.get(key)
            if isinstance(res, Resource):
                got = read_list(os.path.join(self.frm_dir, res.file), res.offset)
                if key == "List":
                    items = got
                else:
                    data = got
        for i, text in enumerate(items or []):
            extra = ""
            if data and i < len(data) and re.match(r"^-?\d+$", data[i]):
                extra = f", {int(data[i])}"
            self.emit(f"{w}.addItem({text!r}{extra})")
        if self.text(c, "Text"):
            self.emit(f"{w}.setCurrentText({self.text(c, 'Text')!r})")

    def make_VB_CheckBox(self, c, w, parent):
        self.emit(f"{w} = QtWidgets.QCheckBox({parent})")
        self.emit(f"{w}.setText({self.text(c, 'Caption')!r})")

    def make_VB_OptionButton(self, c, w, parent):
        self.emit(f"{w} = QtWidgets.QRadioButton({parent})")
        self.emit(f"{w}.setText({self.text(c, 'Caption')!r})")
        if c.flag("Value"):
            self.emit(f"{w}.setChecked(True)")

    def make_VB_Frame(self, c, w, parent):
        if self.text(c, "Caption") and c.get("BorderStyle", "1") != "0":
            self.emit(f"{w} = vbqt.GroupFrame({parent})")
            self.emit(f"{w}.setTitle({self.text(c, 'Caption')!r})")
        else:
            self.emit(f"{w} = vbqt.Container({parent})")
            if css_color(c.get("BackColor"), 15):
                self.emit(f"{w}.setAutoFillBackground(True)")

    def make_VB_PictureBox(self, c, w, parent):
        self.emit(f"{w} = vbqt.PictureBox({parent})")

    def _scrollbar(self, c, w, parent, orientation):
        self.emit(f"{w} = QtWidgets.QScrollBar(QtCore.Qt.Orientation.{orientation}, {parent})")
        self.emit(f"{w}.setRange({c.num('Min', 0)}, {c.num('Max', 32767)})")
        self.emit(f"{w}.setSingleStep({c.num('SmallChange', 1)})")
        self.emit(f"{w}.setPageStep({c.num('LargeChange', 1)})")
        if c.get("Value"):
            self.emit(f"{w}.setValue({c.num('Value')})")

    def make_VB_VScrollBar(self, c, w, parent):
        self._scrollbar(c, w, parent, "Vertical")

    def make_VB_HScrollBar(self, c, w, parent):
        self._scrollbar(c, w, parent, "Horizontal")

    def make_MSComctlLib_Slider(self, c, w, parent):
        self.emit(f"{w} = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, {parent})")
        self.emit(f"{w}.setRange({c.num('Min', 0)}, {c.num('Max', 10)})")
        self.emit(f"{w}.setPageStep({c.num('LargeChange', 5)})")

    def make_MSComctlLib_TabStrip(self, c, w, parent):
        self.emit(f"{w} = QtWidgets.QTabBar({parent})")
        for block in c.sub.values():
            tabs = sorted((k, v) for k, v in block.items() if re.match(r"Tab\d+$", k) and isinstance(v, dict))
            for _, tab in sorted(tabs, key=lambda kv: int(kv[0][3:])):
                self.emit(f"{w}.addTab({tab.get('Caption', '')!r})")

    def make_MSComctlLib_ListView(self, c, w, parent):
        self.emit(f"{w} = vbqt.ListView({parent})")
        cols = sorted(((int(re.search(r"\((\d+)\)", k).group(1)), v) for k, v in c.sub.items() if k.startswith("ColumnHeader")))
        if cols:
            self.emit(f"{w}.setHeaderLabels({[v.get('Text', '') for _, v in cols]!r})")
            for i, (_, v) in enumerate(cols):
                width = v.get("Object.Width") or v.get("Width")
                if width:
                    self.emit(f"{w}.setColumnWidth({i}, {round(float(width) / TWIPS_PER_PIXEL)})")
        if c.flag("HideColumnHeaders"):
            self.emit(f"{w}.setHeaderHidden(True)")
        if c.flag("Sorted"):
            self.report["ListView sortiert (Sorted): Sortierung im Code umsetzen"].add(c.name)
        if c.flag("Checkboxes"):
            self.report["ListView mit Kontrollkästchen: Elemente beim Anlegen mit ItemIsUserCheckable versehen"].add(c.name)

    def make_AXVLCCtl_VLCPlugin2(self, c, w, parent):
        self.emit(f"{w} = QtWidgets.QWidget({parent})      # Videofläche: Wiedergabe später z. B. mit python-vlc "
                  f"(set_xwindow(int({w}.winId())))")
        self.report["VLC-Steuerelement (Videofläche): Platzhalter, Wiedergabe noch einzubinden"].add(c.name)

    def make_VB_Line(self, c, w, parent):
        """Linie als schmales gefülltes Rechteck: Farbe (BorderColor) und Dicke (BorderWidth, in Pixeln) wie in VB6."""
        k = container_scale(c.parent)
        x1, x2, y1, y2 = (round(c.num(n) * k) for n in ("X1", "X2", "Y1", "Y2"))
        bw = max(c.num("BorderWidth", 1), 1)
        self.emit(f"{w} = QtWidgets.QFrame({parent})")
        self.emit(f"{w}.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)")
        color = css_color(c.get("BorderColor")) or "rgb(0, 0, 0)"
        self.emit(f"{w}.setAutoFillBackground(True)")
        self.emit(f"{w}.setStyleSheet(\"background-color: {color};\")")   # ohne Kennung: gilt für das Steuerelement selbst
        if abs(y2 - y1) >= abs(x2 - x1):                     # senkrecht: die Dicke zentriert um x
            c.px_override = (min(x1, x2) - bw // 2, min(y1, y2), bw, max(abs(y2 - y1), 1))
        else:                                                # waagerecht
            c.px_override = (min(x1, x2), min(y1, y2) - bw // 2, max(abs(x2 - x1), 1), bw)

    def make_MediaMaker_ShellPipe(self, c, w, parent):
        self.report["ShellPipe (nicht sichtbar): ersetzt durch runner.py"].add(c.name)
        self.emit(f"{w} = QtWidgets.QWidget({parent})      # ShellPipe: siehe runner.py")
        self.emit(f"{w}.hide()")

    # ------------------------------------------------------------------ Menüs
    @staticmethod
    def shortcut(value: str | None) -> str | None:
        if not value:
            return None
        m = re.match(r"^([\^+%]*)(?:\{(\w+)\}|(.))$", value)
        if not m:
            return None
        mods = {"^": "Ctrl", "+": "Shift", "%": "Alt"}
        return "+".join([mods[ch] for ch in m.group(1)] + [(m.group(2) or m.group(3)).upper()])

    def build_menus(self):
        if not self.menu_items:
            return
        self.emit("menubar = self.menuBar()", 2)
        for m in self.menu_items:
            self.build_menu(m, "menubar", True)
        self.emit()

    def build_menu(self, m: Control, parent: str, top: bool):
        w = self.var(m)
        caption = self.text(m, "Caption")
        if caption == "-":
            self.emit(f"{parent}.addSeparator()")
            return
        sub = [c for c in m.children if c.type == "VB.Menu"]
        if sub:
            self.emit(f"{w} = {parent}.addMenu({caption!r})")
            self.emit(f"{self.target(m)} = {w}")
            for s in sub:
                self.build_menu(s, w, False)
            return
        self.emit(f"{w} = QtGui.QAction({caption!r}, self)")
        sc = self.shortcut(m.get("Shortcut"))
        if m.get("Shortcut") and not sc:
            self.report["Tastenkürzel nicht übersetzt"].add(f"{m.name}: {m.get('Shortcut')}")
        if sc:
            self.emit(f"{w}.setShortcut(QtGui.QKeySequence({sc!r}))")
        if m.flag("Checked"):
            self.emit(f"{w}.setCheckable(True)")
            self.emit(f"{w}.setChecked(True)")
        if not m.flag("Enabled", True):
            self.emit(f"{w}.setEnabled(False)")
        if not m.flag("Visible", True):
            self.emit(f"{w}.setVisible(False)")
        self.emit(f"{parent}.addAction({w})")
        self.emit(f"{self.target(m)} = {w}")

    # ------------------------------------------------------------------ Formular
    def generate(self) -> str:
        form, root = self.form, self.form.root
        name = root.name
        base = "QtWidgets.QMainWindow" if self.is_main_window else "QtWidgets.QDialog"
        cw, ch = form_client_px(form)
        fixed = root.get("BorderStyle", "2") in ("1", "3")

        out = [
            f'"""Oberfläche von {name} - automatisch erzeugt von frm2qt.py aus {os.path.basename(form.path)}.',
            "",
            "Nicht von Hand ändern: Die Datei wird beim erneuten Erzeugen überschrieben.",
            f"Logik gehört in eine abgeleitete Klasse mit den VB6-Prozedurnamen (siehe {name}.py).",
            '"""',
            "import os",
            "",
            "from PySide6 import QtCore, QtGui, QtWidgets",
            "",
            "import vbqt",
            "",
            "HERE = os.path.dirname(os.path.abspath(__file__))",
            "",
            "",
            f"class {name}Base({base}):",
            "    def __init__(self, parent=None):",
            "        super().__init__(parent)",
            "        self._loaded = False",
            "        self._build()",
            "        self._connect()",
            "",
            "    def _vb(self, procedure, *args):",
            '        """Ruft die VB6-Prozedur (falls in der abgeleiteten Klasse vorhanden) auf."""',
            "        fn = getattr(self, procedure, None)",
            "        return fn(*args) if fn else None",
            "",
            "    def _call(self, procedure, *fixed):",
            "        return lambda *signal_args: self._vb(procedure, *fixed)",
            "",
            "    def _callv(self, procedure, *fixed):",
            '        """Wie _call, reicht aber die Argumente des Ereignisses weiter (Maus, Tasten, Dateien)."""',
            "        return lambda *event_args: self._vb(procedure, *fixed, *event_args)",
            "",
            "    def _build(self):",
        ]
        self.lines = []
        arrays_done = set()
        for c in root.walk():
            if c is not root and c.name in self.arrays and c.name not in arrays_done:
                self.emit(f"self.{ident(c.name)} = vbqt.ControlArray()")
                arrays_done.add(c.name)
        if arrays_done:
            self.emit()
        self.emit(f"self.setWindowTitle({self.text(root, 'Caption', name)!r})")
        icon = root.get("Icon")
        if isinstance(icon, Resource):
            n = self.icon_file(icon)
            if n:
                self.emit(f"self.setWindowIcon(QtGui.QIcon(os.path.join(HERE, 'icons', {n!r})))")
        if root.get("MaxButton") == "0" or fixed:
            self.emit("self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)")
        if root.get("MinButton") == "0" or root.get("BorderStyle") == "3":
            self.emit("self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)")
        if root.get("BorderStyle") == "0":
            self.emit("self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)")
        if root.get("ShowInTaskbar") == "0":
            self.report["ShowInTaskbar = False: nicht übernommen"].add(name)
        css = css_color(root.get("BackColor"), 15)
        f = root.sub.get("Font") or {}
        font_expr = (f"vbqt.make_font({f.get('Name', 'MS Sans Serif')!r}, {float(f.get('Size', 8.25))}, "
                     f"{int(float(f.get('Weight', 400)))}, {int(f.get('Italic', 0) not in ('0', 0))}, "
                     f"{int(f.get('Underline', 0) not in ('0', 0))}, {int(f.get('Strikethrough', 0) not in ('0', 0))})")
        if self.is_main_window:
            self.emit("central = QtWidgets.QWidget(self)")
            self.emit("self.setCentralWidget(central)")
            self.emit(f"central.setFont({font_expr})      # VB6-Standardschrift des Formulars (Menü behält die Systemschrift)")
            self.emit(f"central.{'setFixedSize' if fixed else 'setMinimumSize'}({cw}, {ch})")
            parent = "central"
        else:
            self.emit(f"self.setFont({font_expr})      # VB6-Standardschrift des Formulars")
            self.emit(f"self.{'setFixedSize' if fixed else 'resize'}({cw}, {ch})")
            parent = "self"
        if css:
            self.emit(f"self.setStyleSheet(\"#{name} {{ background-color: {css}; }}\")")
            self.emit(f"self.setObjectName({name!r})")
        self.emit()
        self.build_menus()
        # Elternelement der Steuerelemente ist der Clientbereich
        self.root_parent = parent
        self.build_children(root, parent)
        for chain in self.tab_orders:
            for a, b in zip(chain, chain[1:]):
                self.emit(f"QtWidgets.QWidget.setTabOrder({a[1]}, {b[1]})")
        self.emit(f"vbqt.fit_labels({parent})")
        self.lines += [""]
        out += self.lines
        out += self._connect_code()
        out += self._form_events_code()
        out.append("")
        return "\n".join(out)

    def _connect_code(self) -> list[str]:
        types = {c.name: c.type for c in self.form.root.walk()}
        self.lines = []
        self.emit("def _connect(self):", 1)
        n_before = len(self.lines)
        for h in self.form.handlers:
            if h.control == "Form" or h.control not in types:
                continue
            t = types[h.control]
            template = EVENTS.get((t, h.event))
            proc = f"{h.control}_{h.event}"
            if not template:
                if h.event in KNOWN_EVENTS:
                    self.report["Ereignis nicht verbunden (im Code nachbilden)"].add(f"{proc} ({t})")
                    self.emit(f"# TODO: {proc} ({t}) hat keine automatische Entsprechung in Qt")
                continue
            if h.control in self.arrays:
                elems = [c for c in self.form.root.walk() if c.name == h.control and c is not self.form.root]
                for c in sorted(elems, key=lambda e: e.index if e.index is not None else 0):
                    idx = c.index if c.index is not None else 0
                    self.emit(template.format(w=self.target(c), cb=f"self._call({proc!r}, {idx})",
                                              cbv=f"self._callv({proc!r}, {idx})"))
            else:
                c = next(c for c in self.form.root.walk() if c.name == h.control)
                if t == "VB.Menu" and any(k.type == "VB.Menu" for k in c.children):
                    template = "{w}.aboutToShow.connect({cb})"       # Menü mit Untermenü: öffnet sich beim Klick
                self.emit(template.format(w=self.target(c), cb=f"self._call({proc!r})", cbv=f"self._callv({proc!r})"))
        if len(self.lines) == n_before:
            self.emit("pass")
        return [""] + self.lines

    def _form_events_code(self) -> list[str]:
        have = {h.event for h in self.form.handlers if h.control == "Form"}
        out = []
        if have & {"Load", "Activate"} or self.form.root.get("StartUpPosition") in ("1", "2"):
            out += ["", "    def showEvent(self, event):", "        super().showEvent(event)", "        if not self._loaded:",
                    "            self._loaded = True"]
            if self.form.root.get("StartUpPosition") == "2":
                out.append("            vbqt.center_on_screen(self)")
            if "Load" in have:
                out.append("            self._vb('Form_Load')")
            if "Activate" in have:
                out.append("            self._vb('Form_Activate')")
        if "Activate" in have or "LostFocus" in have:
            out += ["", "    def changeEvent(self, event):", "        super().changeEvent(event)",
                    "        if event.type() == QtCore.QEvent.Type.ActivationChange and self._loaded:"]
            if "Activate" in have and "LostFocus" in have:
                out += ["            self._vb('Form_Activate' if self.isActiveWindow() else 'Form_LostFocus')"]
            elif "Activate" in have:
                out += ["            if self.isActiveWindow():", "                self._vb('Form_Activate')"]
            else:
                out += ["            if not self.isActiveWindow():", "                self._vb('Form_LostFocus')"]
        if "Resize" in have:
            out += ["", "    def resizeEvent(self, event):", "        super().resizeEvent(event)", "        self._vb('Form_Resize')"]
        if "Unload" in have:
            out += ["", "    def closeEvent(self, event):", "        self._vb('Form_Unload')", "        super().closeEvent(event)"]
        return out

    def stub(self) -> str:
        name = self.form.root.name
        lines = [f'"""Logik von {name}: Prozeduren mit den VB6-Namen; Vorlage von frm2qt.py."""',
                 f"from ui_{name} import {name}Base", "", "", f"class {name}({name}Base):"]
        seen = set()
        for h in self.form.handlers:
            proc = f"{h.control}_{h.event}"
            if proc in seen or (h.control != "Form" and h.control not in {c.name for c in self.form.root.walk()}):
                continue
            seen.add(proc)
            args = ", index" if re.search(r"\bIndex\b", h.params, re.I) else ""
            lines += [f"    def {proc}(self{args}):", f"        # VB6: Sub {proc}({h.params})", "        pass", ""]
        if not seen:
            lines += ["    pass", ""]
        return "\n".join(lines)


def convert(path: str, out_dir: str, stub: bool = False) -> dict:
    form = parse_frm(path)
    gen = Generator(form, out_dir)
    code = gen.generate()
    os.makedirs(out_dir, exist_ok=True)
    mod = os.path.join(out_dir, f"ui_{form.name}.py")
    with open(mod, "w", encoding="utf-8") as fh:
        fh.write(code)
    stub_path = None
    if stub:
        stub_path = os.path.join(out_dir, f"{form.name}.py")
        if not os.path.exists(stub_path):
            with open(stub_path, "w", encoding="utf-8") as fh:
                fh.write(gen.stub())
    return {"form": form, "module": mod, "stub": stub_path, "report": gen.report, "icons": gen.icons}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("frm", nargs="+")
    ap.add_argument("--out", default="ui_out")
    ap.add_argument("--stub", action="store_true", help="Vorlage für die Logik anlegen (vorhandene Dateien bleiben)")
    args = ap.parse_args()
    for p in args.frm:
        r = convert(p, args.out, args.stub)
        n = len(list(r["form"].root.walk())) - 1
        print(f"{os.path.basename(p)} -> {r['module']}  ({n} Steuerelemente, {len(r['icons'])} Symbole)")
        for cat, items in sorted(r["report"].items()):
            print(f"   - {cat}: {', '.join(sorted(items))}")


if __name__ == "__main__":
    main()
