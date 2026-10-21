from . import _model
from ._model import Base, Enum, EnumGroup


class Signal:
    """Wie PySide6.QtCore.Signal: je Objekt ein eigenes Signal mit connect/emit."""

    def __init__(self, *types):
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return obj.__dict__.setdefault("_sig_" + self.name, _model.Signal())


class QObject(Base):
    methods = {"setObjectName", "installEventFilter", "setParent", "objectName", "setProperty"}

    def blockSignals(self, block):
        old = getattr(self, "_blocked", False)
        self._blocked = bool(block)
        return old


class QRect(Base):
    methods = {"moveCenter", "center", "topLeft", "contains"}


class QEvent(Base):
    Type = EnumGroup("QEvent.Type", {"ActivationChange", "MouseButtonPress", "MouseMove", "MouseButtonRelease",
                                      "MouseButtonDblClick", "KeyPress", "KeyRelease", "DragEnter", "DragMove", "Drop"})
    methods = {"type", "position", "button", "buttons", "modifiers", "key", "mimeData", "acceptProposedAction"}


class Qt:
    TextInteractionFlag = EnumGroup("Qt.TextInteractionFlag", {"TextSelectableByMouse"})
    AlignmentFlag = EnumGroup("Qt.AlignmentFlag", {"AlignLeft", "AlignRight", "AlignHCenter", "AlignTop", "AlignVCenter", "AlignCenter"})
    Orientation = EnumGroup("Qt.Orientation", {"Horizontal", "Vertical"})
    WindowType = EnumGroup("Qt.WindowType", {"WindowMaximizeButtonHint", "WindowMinimizeButtonHint", "FramelessWindowHint"})
    KeyboardModifier = EnumGroup("Qt.KeyboardModifier", {"ShiftModifier", "ControlModifier", "AltModifier"})
    MouseButton = EnumGroup("Qt.MouseButton", {"LeftButton", "RightButton", "MiddleButton"})
    CursorShape = EnumGroup("Qt.CursorShape", {"WaitCursor"})
    ScrollBarPolicy = EnumGroup("Qt.ScrollBarPolicy", {"ScrollBarAlwaysOff", "ScrollBarAsNeeded", "ScrollBarAlwaysOn"})


class QTimer(QObject):
    signals = {"timeout"}
    methods = {"setSingleShot", "setInterval", "stop"}
    pending = []                         # im Test: (ms, Funktion) von QTimer.singleShot

    @staticmethod
    def singleShot(ms, fn):
        QTimer.pending.append((ms, fn))

    def start(self, ms=None):
        self._active = True

    def isActive(self):
        return getattr(self, "_active", False)

    def fire(self):
        """Nur im Test: Ablauf des Zeitgebers."""
        self._active = False
        self.timeout.emit()


class QThread(QObject):
    """Im Test läuft run() sofort und im selben Thread."""
    methods = {"quit"}

    def start(self):
        self._running = True
        try:
            self.run()
        finally:
            self._running = False

    def isRunning(self):
        return getattr(self, "_running", False)

    def wait(self, ms=None):
        return True
