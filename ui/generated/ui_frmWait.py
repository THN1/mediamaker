"""User interface of frmWait - generated automatically by frm2qt.py from frmWait.frm.

Do not change by hand: the file is overwritten when it is generated again.
Logic belongs in a derived class with the VB6 procedure names (see frmWait.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmWaitBase(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._loaded = False
        self._build()
        self._connect()

    def _vb(self, procedure, *args):
        """Calls the VB6 procedure (if present in the derived class)."""
        fn = getattr(self, procedure, None)
        return fn(*args) if fn else None

    def _call(self, procedure, *fixed):
        return lambda *signal_args: self._vb(procedure, *fixed)

    def _callv(self, procedure, *fixed):
        """Like _call, but passes on the arguments of the event (mouse, keys, files)."""
        return lambda *event_args: self._vb(procedure, *fixed, *event_args)

    def _build(self):
        self.setWindowTitle('Form1')
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6 default font of the form
        self.resize(225, 78)
        self.setStyleSheet("#frmWait { background-color: rgb(192, 64, 0); }")
        self.setObjectName('frmWait')

        # lblWait: VB.Label
        w_lblWait = QtWidgets.QLabel(self)
        w_lblWait.setText('')
        w_lblWait.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblWait.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblWait.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblWait = w_lblWait
        w_lblWait.setGeometry(480, 480, 2295, 255)
        w_lblWait.setObjectName('lblWait')
        w_lblWait.setStyleSheet("#lblWait { background-color: rgb(255, 255, 255); }")

        vbqt.fit_labels(self)


    def _connect(self):
        pass

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
