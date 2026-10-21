"""Liest VB6-Formulardateien (.frm): Steuerelemente, Eigenschaften, Menüs und Ereignisprozeduren.

Das Ergebnis ist ein Baum aus Control-Objekten; er ist die Grundlage für die Vorschau (frm_preview.py) und
für die Umsetzung nach Qt (frm2qt.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

TWIPS_PER_PIXEL = 15            # VB6 bei 96 dpi (Screen.TwipsPerPixelX/Y)


@dataclass
class Resource:
    """Verweis auf Binärdaten in der .frx-Datei, z. B. "frmMediaMaker.frx":0CCA"""
    file: str
    offset: int


@dataclass
class Control:
    type: str                                   # z. B. "VB.CommandButton", "MSComctlLib.ListView"
    name: str
    props: dict = field(default_factory=dict)   # rohe Eigenschaften (Text ohne Anführungszeichen, Resource, ...)
    sub: dict = field(default_factory=dict)     # BeginProperty-Blöcke, z. B. "Font", "ColumnHeader(1)"
    children: list = field(default_factory=list)
    parent: Optional["Control"] = None

    @property
    def index(self) -> Optional[int]:
        return int(self.props["Index"]) if "Index" in self.props else None

    def get(self, key: str, default=None):
        return self.props.get(key, default)

    def flag(self, key: str, default: bool = False) -> bool:
        v = self.props.get(key)
        return default if v is None else str(v).strip() not in ("0", "False")

    def num(self, key: str, default: int = 0) -> int:
        try:
            return int(float(self.props[key]))
        except (KeyError, ValueError):
            return default

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


@dataclass
class Handler:
    control: str
    event: str
    params: str


@dataclass
class Form:
    root: Control
    path: str
    handlers: list = field(default_factory=list)       # Ereignisprozeduren aus dem Code
    code_lines: int = 0

    @property
    def name(self) -> str:
        return self.root.name


_BEGIN = re.compile(r"^Begin\s+(\{[0-9A-Fa-f-]+\}|[\w.]+)\s+(\w+)\s*$")
_PROP = re.compile(r"^(\w+)\s*=\s*(.*)$")
_BEGINPROP = re.compile(r"^BeginProperty\s+(.+?)\s*$")
_RES = re.compile(r'^"((?:[^"]|"")*)"\s*:\s*([0-9A-Fa-f]+)\s*$')
_HANDLER = re.compile(r"^(?:Private|Public|Friend)?\s*Sub\s+(\w+?)_(\w+)\s*\((.*)\)\s*$", re.I)


def parse_value(raw: str):
    """'-1  'True' -> '-1'; '"Text"' -> 'Text'; '"a.frx":0CCA' -> Resource."""
    s = raw.strip()
    m = _RES.match(s.split(" '")[0].strip()) if s.startswith('"') and ".fr" in s else None
    if m:
        return Resource(m.group(1), int(m.group(2), 16))
    if s.startswith('"'):
        out, i = [], 1
        while i < len(s):
            if s[i] == '"':
                if i + 1 < len(s) and s[i + 1] == '"':
                    out.append('"'); i += 2; continue
                break
            out.append(s[i]); i += 1
        return "".join(out)
    return re.split(r"\s+'", s, maxsplit=1)[0].strip()


def parse_frm(path: str) -> Form:
    text = open(path, encoding="cp1252", errors="replace").read().replace("\r", "")
    lines = text.split("\n")
    stack: list[Control] = []
    prop_stack: list[tuple[str, dict]] = []
    root: Optional[Control] = None
    code_start = len(lines)
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith("Attribute VB_Name"):
            code_start = i
            break
        m = _BEGIN.match(s)
        if m:
            c = Control(m.group(1), m.group(2))
            if stack:
                c.parent = stack[-1]
                stack[-1].children.append(c)
            else:
                root = root or c
            stack.append(c)
            continue
        m = _BEGINPROP.match(s)
        if m and stack:
            prop_stack.append((m.group(1), {}))
            continue
        if s == "EndProperty" and prop_stack:
            name, d = prop_stack.pop()
            target = prop_stack[-1][1] if prop_stack else stack[-1].sub
            target[name] = d
            continue
        if s == "End" and stack:
            stack.pop()
            continue
        m = _PROP.match(s)
        if m and stack:
            (prop_stack[-1][1] if prop_stack else stack[-1].props)[m.group(1)] = parse_value(m.group(2))
    if root is None:
        raise ValueError(f"{path}: kein Formular gefunden")
    handlers = []
    for raw in lines[code_start:]:
        m = _HANDLER.match(raw.strip())
        if m:
            handlers.append(Handler(m.group(1), m.group(2), m.group(3)))
    return Form(root, path, handlers, len(lines) - code_start)


# ----------------------------------------------------------------------------- Maße und Farben
def container_scale(c: Control) -> float:
    """Pixel pro Einheit der Koordinaten, die in diesem Container für seine Kinder gelten."""
    if c.type in ("VB.PictureBox", "VB.Form") and c.get("ScaleMode") == "3":
        return 1.0
    return 1.0 / TWIPS_PER_PIXEL


def geometry_px(c: Control) -> tuple[int, int, int, int]:
    """(links, oben, breite, höhe) in Pixeln relativ zum Elterncontainer."""
    k = container_scale(c.parent) if c.parent and c.parent.type != "VB.Menu" else 1.0 / TWIPS_PER_PIXEL
    return (round(c.num("Left") * k), round(c.num("Top") * k), round(c.num("Width") * k), round(c.num("Height") * k))


def form_client_px(form: Form) -> tuple[int, int]:
    r = form.root
    return round(r.num("ClientWidth") / TWIPS_PER_PIXEL), round(r.num("ClientHeight") / TWIPS_PER_PIXEL)


SYSTEM_COLORS = {0: (200, 200, 200), 1: (92, 92, 92), 2: (0, 84, 227), 3: (122, 150, 223), 4: (240, 240, 240),
                 5: (255, 255, 255), 6: (100, 100, 100), 7: (0, 0, 0), 8: (0, 0, 0), 9: (255, 255, 255),
                 10: (212, 208, 200), 11: (212, 208, 200), 12: (128, 128, 128), 13: (49, 106, 197),
                 14: (255, 255, 255), 15: (240, 240, 240), 16: (160, 160, 160), 17: (128, 128, 128),
                 18: (0, 0, 0), 20: (255, 255, 255), 21: (105, 105, 105), 22: (227, 227, 227),
                 23: (0, 0, 0), 24: (255, 255, 225)}


def vb_color(value, default=None):
    """Farbwert aus einer .frm-Datei: '&H000000FF&', '&H8000000F&' oder Dezimalzahl wie '-2147483640'.

    Rückgabe: (r, g, b) oder, bei Systemfarben, ("system", Nummer); sonst `default`.
    """
    v = None
    m = re.match(r"^&H([0-9A-Fa-f]+)&?$", str(value or ""))
    if m:
        v = int(m.group(1), 16)
    elif re.match(r"^-?\d+$", str(value or "")):
        v = int(value) & 0xFFFFFFFF
    if v is None:
        return default
    if v & 0x80000000:
        return ("system", v & 0xFF)
    return (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF)


def vb_color_rgb(value, default=None):
    """Wie vb_color, aber Systemfarben werden durch feste RGB-Näherungen ersetzt (für die Vorschau)."""
    c = vb_color(value)
    if c is None:
        return default
    if c[0] == "system":
        return SYSTEM_COLORS.get(c[1], default)
    return c
