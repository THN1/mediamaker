from ._model import Base, EnumGroup
from .QtCore import QObject


class QFont(Base):
    methods = {"setFamily", "setPointSizeF", "setBold", "setItalic", "setUnderline", "setStrikeOut", "pointSizeF"}
    _points = 8.25

    def _ret_setPointSizeF(self, value):
        self._points = value

    def _ret_pointSizeF(self):
        return self._points


class QIcon(Base):
    pass


class QKeySequence(Base):
    SequenceFormat = EnumGroup("QKeySequence.SequenceFormat", {"PortableText", "NativeText"})

    def isEmpty(self):
        return not self._args or not self._args[0]

    def toString(self, fmt=None):
        return self._args[0] if self._args else ""


class QPainter(Base):
    RenderHint = EnumGroup("QPainter.RenderHint", {"SmoothPixmapTransform", "Antialiasing"})
    methods = {"drawPixmap", "end", "fillRect", "setRenderHint", "drawImage"}


class QImage(Base):
    Format = EnumGroup("QImage.Format", {"Format_RGB32", "Format_RGB888", "Format_Grayscale8"})
    methods = {"copy", "scaledToWidth"}

    def _ret_copy(self):
        return self

    def _ret_scaledToWidth(self, *args):
        return self


class QPixmap(Base):
    methods = {"scaled"}

    def _ret_scaled(self, *args):
        return self

    @staticmethod
    def fromImage(image):
        return QPixmap()


class QAction(QObject):
    methods = {"setShortcut", "setCheckable", "setChecked", "setEnabled", "setVisible", "setText", "isChecked", "shortcut", "text", "isEnabled"}
    signals = {"triggered", "toggled"}

    def _ret_isEnabled(self):
        done = self.called("setEnabled")
        return bool(done[-1][0]) if done else True

    def _ret_shortcut(self):
        done = self.called("setShortcut")
        return done[-1][0] if done else QKeySequence()

    def _ret_text(self):
        done = self.called("setText")
        return done[-1][0] if done else (self._args[0] if self._args else "")

    def _ret_isChecked(self):
        args = self.called("setChecked")
        return bool(args[-1][0]) if args else False


class QShortcut(QObject):
    signals = {"activated"}


class QFontDatabase(Base):
    @staticmethod
    def families():
        return ["DejaVu Sans", "Liberation Sans"]


class QPalette(Base):
    ColorRole = None
    methods = {"color", "setColor"}


class QColor(Base):
    pass


class QCursor(Base):
    @staticmethod
    def pos():
        return (0, 0)

    pass


QFontDatabase.SystemFont = EnumGroup("QFontDatabase.SystemFont", {"FixedFont", "GeneralFont"})


def _system_font(kind):
    return QFont()


QFontDatabase.systemFont = staticmethod(_system_font)
