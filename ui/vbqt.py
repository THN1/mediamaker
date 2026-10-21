"""Laufzeithilfen für die von frm2qt.py erzeugten Oberflächen (PySide6).

Sie bilden Eigenheiten von VB6 nach, die Qt nicht direkt kennt: Steuerelement-Arrays, die PictureBox,
Mausereignisse mit VB6-Parametern (Button, Shift, x, y), Tastencodes, Drag & Drop von Dateien.
Koordinaten in Ereignissen sind Pixel (VB6 lieferte Twips).
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


class ControlArray(dict):
    """VB6-Steuerelement-Array: arr[index] liefert das Element; Iteration über die Elemente in Indexreihenfolge."""

    def __iter__(self):
        return iter(self[k] for k in sorted(dict.keys(self)))

    @property
    def count(self) -> int:
        return len(self)

    def indexes(self):
        return sorted(dict.keys(self))


class PictureBox(QtWidgets.QFrame):
    """Ersatz für VB.PictureBox: Fläche mit 3D-Rahmen und optionalem Bild; eigene Zeichnung über paint_hook."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.setAutoFillBackground(True)
        self.pixmap = None
        self.paint_hook = None          # optional: Funktion(painter, rect), zeichnet den Inhalt

    def set_picture(self, pixmap) -> None:
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        if self.pixmap is not None:
            painter.drawPixmap(self.contentsRect(), self.pixmap)
        if self.paint_hook:
            self.paint_hook(painter, self.contentsRect())
        painter.end()


class Container(QtWidgets.QFrame):
    """Frame ohne Rahmen und Titel (VB.Frame mit BorderStyle = 0)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)


class GroupFrame(QtWidgets.QWidget):
    """Ersatz für VB.Frame mit Rahmen und Titel.

    Wie in VB6 liegt die Rahmenlinie auf halber Höhe der Schrift, der Titel steht links darauf, und die
    Koordinaten der Kinder gelten ab der linken oberen Ecke des Steuerelements. QGroupBox ordnet je nach Stil
    den Titel innerhalb des Rahmens an und würde die Kinder überdecken.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""

    def setTitle(self, text: str) -> None:
        self._title = text
        self.update()

    def title(self) -> str:
        return self._title

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        palette = self.palette()
        role = QtGui.QPalette.ColorRole
        fm = self.fontMetrics()
        top = fm.height() // 2
        right, bottom = self.width() - 2, self.height() - 2
        text = self._title.replace("&&", "\0").replace("&", "").replace("\0", "&")
        gap = (6, 9 + fm.horizontalAdvance(text) + 3) if text else None     # Lücke der Oberkante für den Titel

        def top_line(y, x0, x1):
            """Oberkante; hinter dem Titel bleibt sie unterbrochen. Es wird nichts übermalt, auch nicht benachbarte
            Steuerelemente, die um einen Pixel in dieses Steuerelement hineinragen."""
            segments = [(x0, x1)] if gap is None else [(x0, min(x1, gap[0] - 1)), (max(x0, gap[1]), x1)]
            for a, b in segments:
                if a <= b:
                    painter.drawLine(a, y, b, y)

        painter.setPen(palette.color(role.Mid))                  # eingeritzter Rahmen: dunkle und helle Linie
        top_line(top, 0, right)
        painter.drawLine(0, top, 0, bottom)
        painter.drawLine(0, bottom, right, bottom)
        painter.drawLine(right, top, right, bottom)
        painter.setPen(palette.color(role.Light))
        top_line(top + 1, 1, right + 1)
        painter.drawLine(1, top + 1, 1, bottom + 1)
        painter.drawLine(1, bottom + 1, right + 1, bottom + 1)
        painter.drawLine(right + 1, top + 1, right + 1, bottom + 1)
        if text:
            painter.setPen(palette.color(role.WindowText))
            painter.drawText(9, fm.ascent(), text)
        painter.end()


class ListView(QtWidgets.QTreeWidget):
    """MSComctlLib.ListView in der Ansicht "Bericht": Zeilen mit Textspalten (die Daten liegen in der Anwendung)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)

    def set_columns(self, widths: dict, stretch_column=None) -> None:
        """Spaltenbreiten in Pixeln; 0 blendet eine Spalte aus (wie Breite 0 in VB6). `stretch_column` füllt den Rest.

        Der Kopfbereich darf die Mindestbreite 0 haben, sonst würde Qt jede Spalte auf mindestens etwa 20 Pixel
        verbreitern, und die letzte Spalte wird nicht mehr automatisch auf die restliche Breite gezogen.
        """
        header = self.header()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(0)
        for col, width in widths.items():
            self.setColumnWidth(col, width)
        if stretch_column is not None:
            header.setSectionResizeMode(stretch_column, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def set_rows(self, rows) -> None:
        self.clear()
        for row in rows:
            self.addTopLevelItem(QtWidgets.QTreeWidgetItem([str(x) for x in row]))

    def row_count(self) -> int:
        return self.topLevelItemCount()

    def current_row(self) -> int:
        """Index der gewählten Zeile (0-basiert), -1 = keine."""
        item = self.currentItem()
        return -1 if item is None else self.indexOfTopLevelItem(item)

    def select_row(self, i: int) -> None:
        item = self.topLevelItem(i)
        if item is not None:
            self.setCurrentItem(item)
            self.scrollToItem(item)

    def set_row(self, i: int, values) -> None:
        item = self.topLevelItem(i)
        for col, value in enumerate(values):
            item.setText(col, str(value))

    def set_bold(self, i: int, col: int, bold: bool) -> None:
        item = self.topLevelItem(i)
        if item is not None:
            font = item.font(col)
            font.setBold(bold)
            item.setFont(col, font)


# ----------------------------------------------------------------------------- Schrift, Fenster
_DEFAULT_FAMILIES = {"ms sans serif", "ms shell dlg", "ms shell dlg 2", "microsoft sans serif", "tahoma", "arial"}
# Schriften mit den Maßen von Arial; MS Sans Serif ist ähnlich schmal. DejaVu Sans u. a. sind deutlich breiter
# und schneiden die fest bemessenen VB6-Beschriftungen ab.
_PREFERRED = ("Liberation Sans", "Arimo", "Arial", "Nimbus Sans", "Helvetica")
_family_cache = []


def windows_font_family() -> str:
    """Passende Ersatzschrift für die Windows-Standardschriften ('' = Systemschrift behalten)."""
    if not _family_cache:
        have = set(QtGui.QFontDatabase.families())
        _family_cache.append(next((f for f in _PREFERRED if f in have), ""))
    return _family_cache[0]


def make_font(name: str, size: float, weight: int = 400, italic: int = 0, underline: int = 0, strike: int = 0):
    """VB6-Schrift -> QFont. Die Windows-Standardschriften werden durch eine ähnlich breite Schrift ersetzt
    (Liberation Sans o. ä.), sonst durch die Systemschrift; die Größe bleibt."""
    font = QtGui.QFont(QtWidgets.QApplication.font())
    if name.lower() in _DEFAULT_FAMILIES:
        family = windows_font_family()
        if family:
            font.setFamily(family)
    else:
        font.setFamily(name)
    font.setPointSizeF(size)
    font.setBold(weight >= 700)
    font.setItalic(bool(italic))
    font.setUnderline(bool(underline))
    font.setStrikeOut(bool(strike))
    return font


def center_on_screen(widget) -> None:
    geometry = widget.screen().availableGeometry()
    frame = widget.frameGeometry()
    frame.moveCenter(geometry.center())
    widget.move(frame.topLeft())


def set_cancel(window, button) -> None:
    """VB6: Cancel = True. Esc löst den Knopf aus."""
    shortcut = QtGui.QShortcut(QtGui.QKeySequence("Esc"), window)
    shortcut.activated.connect(button.click)


# ----------------------------------------------------------------------------- Ereignisse im VB6-Stil
_KEYS = {0x01000000: 27, 0x01000001: 9, 0x01000003: 8, 0x01000004: 13, 0x01000005: 13, 0x01000006: 45,
         0x01000007: 46, 0x01000010: 36, 0x01000011: 35, 0x01000012: 37, 0x01000013: 38, 0x01000014: 39,
         0x01000015: 40, 0x01000016: 33, 0x01000017: 34}


def vb_keycode(qt_key: int) -> int:
    """Qt-Tastencode -> VB6-KeyCode (Buchstaben/Ziffern sind gleich, F1..F12 = 112..123)."""
    if qt_key in _KEYS:
        return _KEYS[qt_key]
    if 0x01000030 <= qt_key <= 0x0100003B:
        return 112 + qt_key - 0x01000030
    return qt_key if qt_key < 256 else 0


def vb_shift(modifiers) -> int:
    """Umschalttasten: 1 = Shift, 2 = Strg, 4 = Alt (wie in VB6)."""
    m = QtCore.Qt.KeyboardModifier
    return (1 if modifiers & m.ShiftModifier else 0) | (2 if modifiers & m.ControlModifier else 0) | \
           (4 if modifiers & m.AltModifier else 0)


def vb_button(buttons) -> int:
    """Maustasten: 1 = links, 2 = rechts, 4 = Mitte (wie in VB6)."""
    b = QtCore.Qt.MouseButton
    return (1 if buttons & b.LeftButton else 0) | (2 if buttons & b.RightButton else 0) | \
           (4 if buttons & b.MiddleButton else 0)


class _Filter(QtCore.QObject):
    """Ein Ereignisfilter pro Steuerelement; leitet Ereignisse an Funktionen im VB6-Stil weiter."""

    def __init__(self, widget):
        super().__init__(widget)
        self.widget = widget
        self.handlers = {}
        widget.installEventFilter(self)
        if hasattr(widget, "viewport"):
            widget.viewport().installEventFilter(self)

    def eventFilter(self, obj, ev):
        t = ev.type()
        E = QtCore.QEvent.Type
        h = self.handlers
        try:
            if t == E.MouseButtonPress and "down" in h:
                p = ev.position()
                h["down"](vb_button(ev.button()), vb_shift(ev.modifiers()), int(p.x()), int(p.y()))
            elif t == E.MouseMove and "move" in h:
                p = ev.position()
                h["move"](vb_button(ev.buttons()), vb_shift(ev.modifiers()), int(p.x()), int(p.y()))
            elif t == E.MouseButtonRelease:
                p = ev.position()
                if "up" in h:
                    h["up"](vb_button(ev.button()), vb_shift(ev.modifiers()), int(p.x()), int(p.y()))
                if "click" in h and ev.button() == QtCore.Qt.MouseButton.LeftButton and self.widget.rect().contains(p.toPoint()):
                    h["click"]()
            elif t == E.MouseButtonDblClick and "dblclick" in h:
                h["dblclick"]()
            elif t == E.KeyPress and "keydown" in h:
                h["keydown"](vb_keycode(ev.key()), vb_shift(ev.modifiers()))
            elif t == E.KeyRelease and "keyup" in h:
                h["keyup"](vb_keycode(ev.key()), vb_shift(ev.modifiers()))
            elif t == E.DragEnter and "drop" in h:
                if ev.mimeData().hasUrls():
                    ev.acceptProposedAction()
                    return True
            elif t == E.DragMove and "drop" in h:
                ev.acceptProposedAction()
                return True
            elif t == E.Drop and "drop" in h:
                files = [u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()]
                h["drop"](files)
                ev.acceptProposedAction()
                return True
        except Exception:                                  # Fehler im Handler dürfen die Oberfläche nicht lahmlegen
            import traceback
            traceback.print_exc()
        return False


def _filter(widget) -> _Filter:
    f = getattr(widget, "_vb_filter", None)
    if f is None:
        f = widget._vb_filter = _Filter(widget)
    return f


def on_mouse(widget, down=None, move=None, up=None) -> None:
    """Handler(button, shift, x, y); x und y in Pixeln relativ zum Steuerelement."""
    f = _filter(widget)
    if move:
        widget.setMouseTracking(True)
    for key, fn in (("down", down), ("move", move), ("up", up)):
        if fn:
            f.handlers[key] = fn


def on_click(widget, fn) -> None:
    _filter(widget).handlers["click"] = fn


def on_double_click(widget, fn) -> None:
    _filter(widget).handlers["dblclick"] = fn


def on_key(widget, down=None, up=None) -> None:
    """Handler(keycode, shift) mit VB6-Tastencodes."""
    f = _filter(widget)
    if down:
        f.handlers["keydown"] = down
    if up:
        f.handlers["keyup"] = up


def on_drop(widget, fn) -> None:
    """Handler(dateiliste): Dateien, die auf das Steuerelement gezogen werden (OLEDragDrop)."""
    widget.setAcceptDrops(True)
    if hasattr(widget, "viewport"):
        widget.viewport().setAcceptDrops(True)
    _filter(widget).handlers["drop"] = fn


def fit_labels(root, margin: int = 6) -> None:
    """Verbreitert linksbündige Beschriftungen, deren Text nicht hineinpasst, soweit rechts daneben Platz ist.

    Linux-Schriften sind etwas breiter als MS Sans Serif; die fest bemessenen VB6-Beschriftungen würden sonst
    (z. B. beim Doppelpunkt) abgeschnitten. Nachbarn in derselben Zeile werden nicht überdeckt.
    """
    for label in root.findChildren(QtWidgets.QLabel):
        text = label.text()
        parent = label.parentWidget()
        if not text or parent is None or label.wordWrap():
            continue
        if not (label.alignment() & QtCore.Qt.AlignmentFlag.AlignLeft):
            continue
        need = label.fontMetrics().horizontalAdvance(text.replace("&", "")) + 2 * label.frameWidth() + margin
        g = label.geometry()
        if need <= g.width():
            continue
        limit = None
        for sib in parent.children():
            if sib is label or not isinstance(sib, QtWidgets.QWidget) or sib.isHidden():
                continue
            r = sib.geometry()
            if r.left() >= g.left() + g.width() and r.top() < g.top() + g.height() and r.top() + r.height() > g.top():
                limit = r.left() if limit is None else min(limit, r.left())
        width = need if limit is None else min(need, limit - 2 - g.left())
        if width > g.width():
            label.setGeometry(g.left(), g.top(), width, g.height())


# ----------------------------------------------------------------------------- Erscheinungsbild
def apply_light_theme(app) -> None:
    """Helles Erscheinungsbild unabhängig vom Desktop-Thema (Fusion-Stil mit festen Windows-ähnlichen Farben)."""
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):                     # ab Qt 6.8
        hints.setColorScheme(QtCore.Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    P = QtGui.QPalette
    R, G, C = P.ColorRole, P.ColorGroup, QtGui.QColor
    palette = P()
    for role, color in ((R.Window, C(240, 240, 240)), (R.WindowText, C(0, 0, 0)), (R.Base, C(255, 255, 255)),
                        (R.AlternateBase, C(245, 245, 245)), (R.ToolTipBase, C(255, 255, 225)),
                        (R.ToolTipText, C(0, 0, 0)), (R.Text, C(0, 0, 0)), (R.Button, C(240, 240, 240)),
                        (R.ButtonText, C(0, 0, 0)), (R.BrightText, C(255, 0, 0)), (R.Link, C(0, 0, 255)),
                        (R.Highlight, C(49, 106, 197)), (R.HighlightedText, C(255, 255, 255)),
                        (R.PlaceholderText, C(128, 128, 128)), (R.Light, C(255, 255, 255)),
                        (R.Midlight, C(227, 227, 227)), (R.Mid, C(160, 160, 160)), (R.Dark, C(105, 105, 105))):
        palette.setColor(role, color)
    for role in (R.WindowText, R.Text, R.ButtonText):
        palette.setColor(G.Disabled, role, C(128, 128, 128))
    app.setPalette(palette)
