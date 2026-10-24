from . import _model
from ._model import Base, Enum, EnumGroup


class Signal:
    """Like PySide6.QtCore.Signal: every object gets its own signal with connect/emit."""

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
                                      "MouseButtonDblClick", "KeyPress", "KeyRelease", "DragEnter", "DragMove", "Drop", "Enter", "Leave", "ToolTip"})
    methods = {"type", "position", "button", "buttons", "modifiers", "key", "mimeData", "acceptProposedAction"}


class Qt:
    TextElideMode = EnumGroup("Qt.TextElideMode", {"ElideNone", "ElideLeft", "ElideRight", "ElideMiddle"})
    TextInteractionFlag = EnumGroup("Qt.TextInteractionFlag", {"TextSelectableByMouse"})
    TransformationMode = EnumGroup("Qt.TransformationMode", {"SmoothTransformation", "FastTransformation"})
    AlignmentFlag = EnumGroup("Qt.AlignmentFlag", {"AlignLeft", "AlignRight", "AlignHCenter", "AlignTop", "AlignVCenter", "AlignCenter"})
    Orientation = EnumGroup("Qt.Orientation", {"Horizontal", "Vertical"})
    WindowType = EnumGroup("Qt.WindowType", {"WindowMaximizeButtonHint", "WindowMinimizeButtonHint", "FramelessWindowHint"})
    Key = EnumGroup("Qt.Key", {"Key_Shift"})
    KeyboardModifier = EnumGroup("Qt.KeyboardModifier", {"ShiftModifier", "ControlModifier", "AltModifier"})
    MouseButton = EnumGroup("Qt.MouseButton", {"LeftButton", "RightButton", "MiddleButton"})
    CursorShape = EnumGroup("Qt.CursorShape", {"WaitCursor", "ArrowCursor", "SizeHorCursor", "SizeVerCursor", "SizeAllCursor", "SizeFDiagCursor", "SizeBDiagCursor"})
    WidgetAttribute = EnumGroup("Qt.WidgetAttribute", {"WA_StyledBackground", "WA_TranslucentBackground"})
    ScrollBarPolicy = EnumGroup("Qt.ScrollBarPolicy", {"ScrollBarAlwaysOff", "ScrollBarAsNeeded", "ScrollBarAlwaysOn"})


class QUrl(Base):
    @staticmethod
    def fromLocalFile(path):
        return ("file", path)


class QTimer(QObject):
    signals = {"timeout"}
    methods = {"setSingleShot", "setInterval"}
    pending = []                         # in the test: (ms, function) of QTimer.singleShot

    @staticmethod
    def singleShot(ms, fn):
        QTimer.pending.append((ms, fn))

    def start(self, ms=None):
        self._active = True
        self.__dict__.setdefault("starts_", []).append(ms)

    def stop(self):
        self._active = False
        self.__dict__["stops_"] = self.__dict__.get("stops_", 0) + 1

    def isActive(self):
        return getattr(self, "_active", False)

    def fire(self):
        """Test only: run of the timer."""
        self._active = False
        self.timeout.emit()


class QThread(QObject):
    """In the test run() runs immediately and in the same thread."""
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
