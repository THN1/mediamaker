from ._model import Base, Enum, EnumGroup
from .QtCore import QObject
from .QtGui import QAction


class Rect:
    def __init__(self, x, y, w, h):
        self.x_, self.y_, self.w_, self.h_ = x, y, w, h

    def left(self):
        return self.x_

    def x(self):
        return self.x_

    def y(self):
        return self.y_

    def top(self):
        return self.y_

    def width(self):
        return self.w_

    def height(self):
        return self.h_

    def center(self):
        return (self.x_ + self.w_ // 2, self.y_ + self.h_ // 2)

    def moveCenter(self, c):
        pass

    def topLeft(self):
        return (self.x_, self.y_)


class Screen:
    def availableGeometry(self):
        return Rect(0, 0, 1920, 1080)


class FontMetrics:
    px_per_char = 1                      # small, so that the default test does not widen any caption

    def horizontalAdvance(self, text):
        return self.px_per_char * len(text)

    def lineSpacing(self):
        return 16


class QWidget(QObject):
    methods = {"setMinimumHeight", "setMinimumWidth", "deleteLater", "underMouse", "setAttribute", "setCursor", "unsetCursor", "raise_", "fontMetrics", "setMinimumSize", "setMaximumSize", "setSizePolicy", "setGeometry", "geometry", "resize", "setFixedSize", "setMinimumSize", "move", "hide", "show", "setVisible",
               "setEnabled", "isEnabled", "setToolTip", "setFont", "setStyleSheet", "setAutoFillBackground",
               "setMouseTracking", "setAcceptDrops", "setWindowTitle", "setWindowFlag", "setWindowIcon", "winId", "rect",
               "frameGeometry", "screen", "isActiveWindow", "update", "contentsRect", "width", "height", "setFocusPolicy",
               "close", "isVisible", "windowTitle", "findChildren", "children", "parentWidget", "isHidden", "fontMetrics", "setFocus", "screen",
               "setFixedHeight", "setMinimumWidth", "setFixedWidth",
               "showEvent", "changeEvent", "resizeEvent", "closeEvent"}
    setTabOrder_calls = []

    def showEvent(self, event):
        pass

    def keyPressEvent(self, event):
        pass

    def changeEvent(self, event):
        pass

    def resizeEvent(self, event):
        pass

    def closeEvent(self, event):
        pass

    def _ret_geometry(self):
        for name, args in reversed(self.calls):             # the latest of the calls that set position and/or size
            if name == "setGeometry":
                return Rect(*args)
            if name in ("setFixedSize", "resize") and len(args) == 2:
                return Rect(0, 0, *args)
        return Rect(0, 0, 0, 0)

    def _ret_underMouse(self):
        return self.__dict__.get("under_mouse_", False)

    def _ret_isVisible(self):
        for name, args in reversed(self.calls):
            if name == "show":
                return True
            if name == "hide":
                return False
            if name == "setVisible":
                return bool(args[0])
        return False

    def _ret_contentsRect(self):
        g = self._ret_geometry()
        return Rect(2, 2, g.width() - 4, g.height() - 4)

    def _ret_width(self):
        return self._ret_geometry().width()

    def _ret_height(self):
        return self._ret_geometry().height()

    def _ret_parentWidget(self):
        return self.parent_

    def _ret_children(self):
        return list(self.children_)

    def _ret_isHidden(self):
        return bool(self.called("hide"))

    def _ret_fontMetrics(self):
        return FontMetrics()

    def _ret_screen(self):
        return Screen()

    def _ret_frameGeometry(self):
        return Rect(0, 0, 100, 100)

    def _ret_findChildren(self, cls):
        out = []
        for c in self.children_:
            if isinstance(c, cls):
                out.append(c)
            out.extend(c._ret_findChildren(cls) if hasattr(c, "_ret_findChildren") else [])
        return out

    @staticmethod
    def setTabOrder(a, b):
        QWidget.setTabOrder_calls.append((a, b))


class QFrame(QWidget):
    Shape = EnumGroup("QFrame.Shape", {"Panel", "Box", "HLine", "VLine", "NoFrame", "StyledPanel"})
    Shadow = EnumGroup("QFrame.Shadow", {"Sunken", "Raised", "Plain"})
    methods = {"setFrameShape", "setFrameShadow", "setLineWidth", "frameWidth"}

    def _ret_frameWidth(self):
        return 1


class QLabel(QFrame):
    methods = {"setText", "setAlignment", "text", "wordWrap", "alignment", "setWordWrap", "setTextInteractionFlags", "setPixmap"}

    def _ret_text(self):
        args = self.called("setText")
        if args:
            return args[-1][0]
        return self._args[0] if self._args and isinstance(self._args[0], str) else ""

    def _ret_wordWrap(self):
        return False

    def _ret_alignment(self):
        args = self.called("setAlignment")
        return args[-1][0] if args else Enum("AlignLeft")


class QAbstractButton(QWidget):
    methods = {"setText", "setIcon", "setIconSize", "click", "setChecked", "setCheckable", "isChecked", "text"}
    signals = {"clicked", "toggled"}

    def _ret_text(self):
        args = self.called("setText")
        return args[-1][0] if args else ""

    def _ret_isChecked(self):
        args = self.called("setChecked")
        return bool(args[-1][0]) if args else False


class QPushButton(QAbstractButton):
    methods = {"setAutoDefault", "setDefault"}


class QCheckBox(QAbstractButton):
    pass


class QRadioButton(QAbstractButton):
    pass


class QGroupBox(QWidget):
    methods = {"setTitle"}


class QLineEdit(QWidget):
    methods = {"setText", "text", "setMaxLength", "setReadOnly"}
    signals = {"textChanged"}

    def _ret_text(self):
        args = self.called("setText")
        if args:
            return args[-1][0]
        return self._args[0] if self._args and isinstance(self._args[0], str) else ""


class _Doc:
    def documentMargin(self):
        return 4.0


class QPlainTextEdit(QFrame):
    LineWrapMode = EnumGroup("QPlainTextEdit.LineWrapMode", {"WidgetWidth", "NoWrap"})
    methods = {"setPlainText", "setReadOnly", "toPlainText", "setTabChangesFocus", "setLineWrapMode",
               "setHorizontalScrollBarPolicy", "setVerticalScrollBarPolicy", "document"}

    def _ret_toPlainText(self):
        args = self.called("setPlainText")
        return args[-1][0] if args else ""

    def _ret_document(self):
        return _Doc()


class QComboBox(QWidget):
    methods = {"setEditable", "setCurrentText", "addItem", "addItems", "currentText"}
    signals = {"activated", "editTextChanged", "currentIndexChanged"}

    def _ret_currentText(self):
        args = self.called("setCurrentText")
        return args[-1][0] if args else ""


class QAbstractSlider(QWidget):
    methods = {"setSingleStep", "setPageStep", "setTickInterval"}
    signals = {"valueChanged", "sliderMoved"}

    def setRange(self, a, b):
        self.calls.append(("setRange", (a, b)))
        self._min, self._max = a, b
        self._val = max(a, min(b, getattr(self, "_val", a)))

    def setValue(self, v):
        self.calls.append(("setValue", (v,)))
        lo, hi = getattr(self, "_min", 0), getattr(self, "_max", 99)
        v = max(lo, min(hi, v))
        if v != getattr(self, "_val", lo):
            self._val = v
            if not getattr(self, "_blocked", False):
                self.valueChanged.emit(v)
        self._val = v

    def value(self):
        return getattr(self, "_val", getattr(self, "_min", 0))

    def minimum(self):
        return getattr(self, "_min", 0)

    def maximum(self):
        return getattr(self, "_max", 99)


class QScrollBar(QAbstractSlider):
    pass


class QSlider(QAbstractSlider):
    pass


class QTabBar(QWidget):
    methods = set()
    signals = {"currentChanged"}

    def addTab(self, text):
        self.__dict__.setdefault("tabs_", []).append(text)
        return len(self.tabs_) - 1

    def removeTab(self, i):
        del self.tabs_[i]

    def count(self):
        return len(self.__dict__.get("tabs_", []))

    def currentIndex(self):
        return self.__dict__.get("cur_", 0)

    def setCurrentIndex(self, i):
        self.cur_ = i


class QTabWidget(QWidget):
    instances = []
    methods = {"setUsesScrollButtons", "setElideMode"}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.tabs_ = []
        QTabWidget.instances.append(self)

    def addTab(self, page, label):
        self.tabs_.append((page, label))
        return len(self.tabs_) - 1

    def setCurrentIndex(self, i):
        self.cur_ = i

    def currentIndex(self):
        return self.__dict__.get("cur_", 0)


class QAbstractItemView(QWidget):
    SelectionMode = EnumGroup("QAbstractItemView.SelectionMode", {"SingleSelection", "ExtendedSelection", "MultiSelection", "NoSelection"})


class QListWidget(QAbstractItemView):
    signals = {"currentRowChanged", "itemDoubleClicked"}
    methods = {"setFixedWidth", "setSelectionMode", "setMinimumWidth", "setMinimumHeight"}

    def selectedIndexes(self):
        return [type("Index", (), {"row": (lambda self, r=r: r)})() for r in self.__dict__.get("sel_", [])]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.items_ = []

    def addItem(self, text):
        self.items_.append(text)

    def setCurrentRow(self, i):
        self.row_ = i
        self.sel_ = [i]
        self.currentRowChanged.emit(i)

    def currentRow(self):
        return self.__dict__.get("row_", -1)


class QStackedWidget(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.widgets_ = []

    def addWidget(self, widget):
        self.widgets_.append(widget)

    def setCurrentIndex(self, i):
        self.index_ = i

    def currentIndex(self):
        return self.__dict__.get("index_", 0)


class QHeaderView(Base):
    ResizeMode = EnumGroup("QHeaderView.ResizeMode", {"Stretch", "Interactive", "Fixed", "ResizeToContents"})
    methods = {"setStretchLastSection", "setMinimumSectionSize", "setSectionResizeMode"}


class QTreeWidgetItem(Base):
    def __init__(self, texts=None):
        super().__init__()
        self._texts = list(texts or [])
        self._fonts = {}

    def text(self, col):
        return self._texts[col] if col < len(self._texts) else ""

    def setText(self, col, value):
        while len(self._texts) <= col:
            self._texts.append("")
        self._texts[col] = value

    def setTextAlignment(self, col, flags):
        self.__dict__.setdefault("align_", {})[col] = flags

    def font(self, col):
        from .QtGui import QFont
        return self._fonts.setdefault(col, QFont())

    def setFont(self, col, font):
        self._fonts[col] = font


class QTreeWidget(QWidget):
    methods = {"setHeaderLabels", "setColumnWidth", "setHeaderHidden", "setRootIsDecorated", "setUniformRowHeights",
               "viewport", "scrollToItem"}

    def header(self):
        if not hasattr(self, "_header"):
            self._header = QHeaderView()
        return self._header

    def clear(self):
        self._items, self._current = [], None

    def addTopLevelItem(self, item):
        self.__dict__.setdefault("_items", []).append(item)

    def topLevelItemCount(self):
        return len(self.__dict__.get("_items", []))

    def topLevelItem(self, i):
        items = self.__dict__.get("_items", [])
        return items[i] if 0 <= i < len(items) else None

    def indexOfTopLevelItem(self, item):
        return self.__dict__.get("_items", []).index(item)

    def currentItem(self):
        return self.__dict__.get("_current")

    def setCurrentItem(self, item):
        self._current = item
    signals = {"itemClicked", "itemDoubleClicked", "itemChanged"}

    def _ret_viewport(self):
        if not hasattr(self, "_vp"):
            self._vp = QWidget(self)
        return self._vp


class QMenu(QWidget):
    methods = {"addMenu", "addAction", "addSeparator", "clear"}
    signals = {"aboutToShow"}

    def _ret_addMenu(self, title):
        m = QMenu(self)
        m.title_ = title
        return m

    def _ret_addAction(self, action):
        if isinstance(action, str):                    # addAction("text") creates an entry and returns it
            from .QtGui import QAction
            made = QAction(action, self)
            made.text_ = action
            self.__dict__.setdefault("actions_", []).append(made)
            return made
        return action

    def _ret_clear(self):
        self.actions_ = []

    def addMenu(self, title):
        self.calls.append(("addMenu", (title,)))
        return self._ret_addMenu(title)


class QMenuBar(QMenu):
    pass


class QLayout(Base):
    SizeConstraint = EnumGroup("QLayout.SizeConstraint", {"SetDefaultConstraint", "SetFixedSize", "SetMinimumSize", "SetMaximumSize",
                                                          "SetMinAndMaxSize", "SetNoConstraint"})
    methods = {"setSizeConstraint"}


class QMainWindow(QWidget):
    methods = {"menuBar", "setCentralWidget"}

    def layout(self):
        if not hasattr(self, "_layout"):
            self._layout = QLayout()
        return self._layout

    def menuBar(self):
        if not hasattr(self, "_menubar"):
            self._menubar = QMenuBar(self)
        self.calls.append(("menuBar", ()))
        return self._menubar


class QDialog(QWidget):
    methods = {"accept", "reject", "setModal"}
    exec_result = 1                      # adjustable in the test: 1 = accepted, 0 = cancelled
    on_exec = None                       # adjustable in the test: function(dialog), e.g. to change inputs

    def exec(self):
        if QDialog.on_exec:
            QDialog.on_exec(self)
        return QDialog.exec_result


class QInputDialog(QDialog):
    """Input dialog as an instance (not the static getText/getInt): stores texts and values."""
    InputMode = EnumGroup("QInputDialog.InputMode", {"TextInput", "IntInput", "DoubleInput"})
    methods = {"setInputMode", "setLabelText", "setFixedWidth", "resize", "setWindowTitle", "setIntRange"}

    def __init__(self, *args):
        super().__init__(*args)
        self.label_ = QLabel()
        self.text_, self.int_ = "", 0

    def setTextValue(self, v):
        self.text_ = v

    def textValue(self):
        return self.text_

    def setIntValue(self, v):
        self.int_ = v

    def intValue(self):
        return self.int_

    def findChildren(self, cls):
        return [self.label_]

    def layout(self):
        return None

    def sizeHint(self):
        return Rect(0, 0, 300, 120)


class QSizePolicy(Base):
    Policy = EnumGroup("QSizePolicy.Policy", {"Ignored", "Expanding", "Fixed", "Preferred", "Minimum", "Maximum"})


class QVBoxLayout(Base):
    methods = {"addLayout", "addWidget", "addStretch", "setSpacing", "setContentsMargins"}
    instances = []

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        QVBoxLayout.instances.append(self)

    def addWidget(self, widget, stretch=0):
        self.__dict__.setdefault("added_", []).append((widget, stretch))

    def addLayout(self, layout):
        self.__dict__.setdefault("added_", []).append((layout, 0))


class QHBoxLayout(QVBoxLayout):
    pass


class QButtonGroup(Base):
    methods = {"setExclusive"}

    def addButton(self, button, i):
        self.__dict__.setdefault("buttons_", {})[i] = button


class QFormLayout(Base):
    instances = []
    methods = {"setLabelAlignment"}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rows = []
        QFormLayout.instances.append(self)

    def addRow(self, label, editor=None):
        self.rows.append((label, editor))


class QDialogButtonBox(Base):
    StandardButton = EnumGroup("QDialogButtonBox.StandardButton", {"Ok", "Cancel"})
    signals = {"accepted", "rejected"}


class QToolTip:
    shown = []

    @staticmethod
    def isVisible():
        return bool(QToolTip.shown)

    @staticmethod
    def showText(pos, text, widget=None):
        QToolTip.shown.append((pos, text, widget))


class QApplication(Base):
    log = []

    @staticmethod
    def instance():
        return None

    @staticmethod
    def font():
        from .QtGui import QFont
        return QFont()

    @staticmethod
    def beep():
        QApplication.log.append("beep")

    @staticmethod
    def setOverrideCursor(cursor):
        QApplication.log.append("busy")

    @staticmethod
    def restoreOverrideCursor():
        QApplication.log.append("idle")

    @staticmethod
    def processEvents():
        pass

    class _Clipboard:
        text_ = ""

        def setText(self, t):
            QApplication._Clipboard.text_ = t

    @staticmethod
    def clipboard():
        return QApplication._Clipboard()


class QMessageBox(Base):
    StandardButton = EnumGroup("QMessageBox.StandardButton", {"Yes", "No"})
    Icon = EnumGroup("QMessageBox.Icon", {"Warning", "Information"})
    methods = {"setIcon", "setWindowTitle", "setText", "setStandardButtons", "setDefaultButton", "setCheckBox", "deleteLater", "exec"}
    shown = []
    answer = "Yes"
    on_exec = None                           # in the test: called with the box before it "returns", to tick the check box

    def _ret_exec(self, *args):
        QMessageBox.shown.append(self.called("setText")[-1][0])
        if QMessageBox.on_exec:
            QMessageBox.on_exec(self)
        return Enum("QMessageBox.StandardButton." + QMessageBox.answer)

    @staticmethod
    def warning(parent, title, text):
        QMessageBox.shown.append(text)

    @staticmethod
    def question(parent, title, text, buttons):
        QMessageBox.shown.append(text)
        return Enum("QMessageBox.StandardButton." + QMessageBox.answer)


class QFileDialog(Base):
    result = ""

    @staticmethod
    def getOpenFileName(parent, caption, directory, filters):
        return QFileDialog.result, ""
