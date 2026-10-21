"""User interface of frmMediaInfo - generated automatically by frm2qt.py from frmMediaInfo.frm.

Do not change by hand: the file is overwritten when it is generated again.
Logic belongs in a derived class with the VB6 procedure names (see frmMediaInfo.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmMediaInfoBase(QtWidgets.QDialog):
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
        self.setWindowTitle('Media Info for ')
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6 default font of the form
        self.setFixedSize(697, 538)

        # lblMediaInfo: VB.Label
        w_lblMediaInfo = QtWidgets.QLabel(self)
        w_lblMediaInfo.setText('')
        w_lblMediaInfo.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblMediaInfo.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblMediaInfo.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblMediaInfo = w_lblMediaInfo
        w_lblMediaInfo.setGeometry(8, 32, 681, 465)
        w_lblMediaInfo.setObjectName('lblMediaInfo')
        w_lblMediaInfo.setFont(vbqt.make_font('Fixedsys', 9.0, 400, 0, 0, 0))

        # TabStrip1: MSComctlLib.TabStrip
        w_TabStrip1 = QtWidgets.QTabBar(self)
        self.TabStrip1 = w_TabStrip1
        w_TabStrip1.setGeometry(8, 8, 745, 25)
        w_TabStrip1.setObjectName('TabStrip1')

        # cmdClose: VB.CommandButton
        w_cmdClose = QtWidgets.QPushButton(self)
        w_cmdClose.setText('Cl&ose')
        w_cmdClose.setAutoDefault(False)
        w_cmdClose.setDefault(True)
        vbqt.set_cancel(self, w_cmdClose)
        self.cmdClose = w_cmdClose
        w_cmdClose.setGeometry(608, 504, 81, 25)
        w_cmdClose.setObjectName('cmdClose')

        QtWidgets.QWidget.setTabOrder(w_TabStrip1, w_cmdClose)
        vbqt.fit_labels(self)


    def _connect(self):
        self.cmdClose.clicked.connect(self._call('cmdClose_Click'))
        self.TabStrip1.currentChanged.connect(self._call('TabStrip1_Click'))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._vb('Form_Activate')

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.ActivationChange and self._loaded:
            if self.isActiveWindow():
                self._vb('Form_Activate')
