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
    methods = {"setObjectName", "installEventFilter", "setParent", "objectName", "setProperty", "isWidgetType"}

    def _ret_isWidgetType(self):
        return False

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
    TextFormat = EnumGroup("Qt.TextFormat", {"RichText", "PlainText", "AutoText", "MarkdownText"})
    TransformationMode = EnumGroup("Qt.TransformationMode", {"SmoothTransformation", "FastTransformation"})
    AlignmentFlag = EnumGroup("Qt.AlignmentFlag", {"AlignLeft", "AlignRight", "AlignHCenter", "AlignTop", "AlignVCenter", "AlignCenter"})
    Orientation = EnumGroup("Qt.Orientation", {"Horizontal", "Vertical"})
    FocusPolicy = EnumGroup("Qt.FocusPolicy", {"NoFocus", "StrongFocus", "ClickFocus", "TabFocus"})
    ItemFlag = EnumGroup("Qt.ItemFlag", {"ItemIsEditable", "ItemIsEnabled", "ItemIsSelectable"})
    WindowType = EnumGroup("Qt.WindowType", {"WindowMaximizeButtonHint", "WindowMinimizeButtonHint", "FramelessWindowHint", "Widget"})
    Key = EnumGroup("Qt.Key", {"Key_Shift", "Key_Left", "Key_Right", "Key_Space"})
    AspectRatioMode = EnumGroup("Qt.AspectRatioMode", {"KeepAspectRatio", "IgnoreAspectRatio"})
    KeyboardModifier = EnumGroup("Qt.KeyboardModifier", {"ShiftModifier", "ControlModifier", "AltModifier"})
    MouseButton = EnumGroup("Qt.MouseButton", {"LeftButton", "RightButton", "MiddleButton"})
    CursorShape = EnumGroup("Qt.CursorShape", {"WaitCursor", "ArrowCursor", "SizeHorCursor", "SizeVerCursor", "SizeAllCursor", "SizeFDiagCursor", "SizeBDiagCursor"})
    WidgetAttribute = EnumGroup("Qt.WidgetAttribute", {"WA_StyledBackground", "WA_TranslucentBackground"})
    ScrollBarPolicy = EnumGroup("Qt.ScrollBarPolicy", {"ScrollBarAlwaysOff", "ScrollBarAsNeeded", "ScrollBarAlwaysOn"})


class QSize(Base):
    def __init__(self, width=0, height=0):
        super().__init__(width, height)
        self._w, self._h = width, height

    def width(self):
        return self._w

    def height(self):
        return self._h


class QPoint(Base):
    def __init__(self, x=0, y=0):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


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
    signals = {"started", "finished"}                  # (as in Qt: finished is emitted when run() has ended, however it ended)

    def start(self):
        self._running = True
        try:
            self.run()
        finally:
            self._running = False
            self.finished.emit()

    def isRunning(self):
        return getattr(self, "_running", False)

    def wait(self, ms=None):
        return True
