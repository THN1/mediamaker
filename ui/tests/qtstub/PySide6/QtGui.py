from ._model import Base, EnumGroup
from .QtCore import QObject


class QFont(Base):
    methods = {"setFamily", "setPointSizeF", "setBold", "setItalic", "setUnderline", "setStrikeOut"}


class QIcon(Base):
    pass


class QKeySequence(Base):
    pass


class QPainter(Base):
    RenderHint = EnumGroup("QPainter.RenderHint", {"SmoothPixmapTransform", "Antialiasing"})
    methods = {"drawPixmap", "end", "fillRect", "setRenderHint", "drawImage"}


class QImage(Base):
    Format = EnumGroup("QImage.Format", {"Format_RGB32", "Format_RGB888"})
    methods = {"copy"}

    def _ret_copy(self):
        return self


class QAction(QObject):
    methods = {"setShortcut", "setCheckable", "setChecked", "setEnabled", "setVisible", "setText"}
    signals = {"triggered", "toggled"}


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
    pass


QFontDatabase.SystemFont = EnumGroup("QFontDatabase.SystemFont", {"FixedFont", "GeneralFont"})


def _system_font(kind):
    return QFont()


QFontDatabase.systemFont = staticmethod(_system_font)
