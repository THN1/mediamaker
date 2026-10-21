"""User interface of frmLangSelect - generated automatically by frm2qt.py from frmLangSelect.frm.

Do not change by hand: the file is overwritten when it is generated again.
Logic belongs in a derived class with the VB6 procedure names (see frmLangSelect.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmLangSelectBase(QtWidgets.QDialog):
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
        self.cboCode = vbqt.ControlArray()
        self.lblText = vbqt.ControlArray()

        self.setWindowTitle('Audio language selection')
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6 default font of the form
        self.setFixedSize(289, 161)

        # lblText(0): VB.Label
        w_lblText_0 = QtWidgets.QLabel(self)
        w_lblText_0.setText('Primary audio language code:')
        w_lblText_0.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_0.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_0.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[0] = w_lblText_0
        w_lblText_0.setGeometry(8, 8, 185, 17)
        w_lblText_0.setObjectName('lblText_0')
        w_lblText_0.setStyleSheet("#lblText_0 { background-color: rgb(255, 255, 255); }")
        w_lblText_0.hide()

        # lblText(1): VB.Label
        w_lblText_1 = QtWidgets.QLabel(self)
        w_lblText_1.setText('Secondary audio language 1 code:')
        w_lblText_1.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_1.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_1.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[1] = w_lblText_1
        w_lblText_1.setGeometry(8, 32, 185, 17)
        w_lblText_1.setObjectName('lblText_1')
        w_lblText_1.setStyleSheet("#lblText_1 { background-color: rgb(255, 255, 255); }")
        w_lblText_1.hide()

        # lblText(2): VB.Label
        w_lblText_2 = QtWidgets.QLabel(self)
        w_lblText_2.setText('Secondary audio language 2 code:')
        w_lblText_2.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_2.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_2.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[2] = w_lblText_2
        w_lblText_2.setGeometry(8, 56, 185, 17)
        w_lblText_2.setObjectName('lblText_2')
        w_lblText_2.setStyleSheet("#lblText_2 { background-color: rgb(255, 255, 255); }")
        w_lblText_2.hide()

        # lblText(3): VB.Label
        w_lblText_3 = QtWidgets.QLabel(self)
        w_lblText_3.setText('Secondary audio language 3 code:')
        w_lblText_3.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_3.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_3.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[3] = w_lblText_3
        w_lblText_3.setGeometry(8, 80, 185, 17)
        w_lblText_3.setObjectName('lblText_3')
        w_lblText_3.setStyleSheet("#lblText_3 { background-color: rgb(255, 255, 255); }")
        w_lblText_3.hide()

        # lblText(4): VB.Label
        w_lblText_4 = QtWidgets.QLabel(self)
        w_lblText_4.setText('Secondary audio language 4 code:')
        w_lblText_4.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_4.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_4.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[4] = w_lblText_4
        w_lblText_4.setGeometry(8, 104, 185, 17)
        w_lblText_4.setObjectName('lblText_4')
        w_lblText_4.setStyleSheet("#lblText_4 { background-color: rgb(255, 255, 255); }")
        w_lblText_4.hide()

        # cmdOK: VB.CommandButton
        w_cmdOK = QtWidgets.QPushButton(self)
        w_cmdOK.setText('OK')
        w_cmdOK.setAutoDefault(False)
        w_cmdOK.setDefault(True)
        self.cmdOK = w_cmdOK
        w_cmdOK.setGeometry(200, 128, 81, 25)
        w_cmdOK.setObjectName('cmdOK')

        # cboCode(0): VB.ComboBox
        w_cboCode_0 = QtWidgets.QComboBox(self)
        self.cboCode[0] = w_cboCode_0
        w_cboCode_0.setGeometry(200, 8, 81, 21)
        w_cboCode_0.setObjectName('cboCode_0')
        w_cboCode_0.setToolTip('Select "-" to leave the track unused')
        w_cboCode_0.hide()

        # cboCode(1): VB.ComboBox
        w_cboCode_1 = QtWidgets.QComboBox(self)
        self.cboCode[1] = w_cboCode_1
        w_cboCode_1.setGeometry(200, 32, 81, 21)
        w_cboCode_1.setObjectName('cboCode_1')
        w_cboCode_1.setToolTip('Select "-" to leave the track unused')
        w_cboCode_1.hide()

        # cboCode(2): VB.ComboBox
        w_cboCode_2 = QtWidgets.QComboBox(self)
        self.cboCode[2] = w_cboCode_2
        w_cboCode_2.setGeometry(200, 56, 81, 21)
        w_cboCode_2.setObjectName('cboCode_2')
        w_cboCode_2.setToolTip('Select "-" to leave the track unused')
        w_cboCode_2.hide()

        # cboCode(3): VB.ComboBox
        w_cboCode_3 = QtWidgets.QComboBox(self)
        self.cboCode[3] = w_cboCode_3
        w_cboCode_3.setGeometry(200, 80, 81, 21)
        w_cboCode_3.setObjectName('cboCode_3')
        w_cboCode_3.setToolTip('Select "-" to leave the track unused')
        w_cboCode_3.hide()

        # cboCode(4): VB.ComboBox
        w_cboCode_4 = QtWidgets.QComboBox(self)
        self.cboCode[4] = w_cboCode_4
        w_cboCode_4.setGeometry(200, 104, 81, 21)
        w_cboCode_4.setObjectName('cboCode_4')
        w_cboCode_4.setToolTip('Select "-" to leave the track unused')
        w_cboCode_4.hide()

        # cmdCancel: VB.CommandButton
        w_cmdCancel = QtWidgets.QPushButton(self)
        w_cmdCancel.setText('Cancel')
        w_cmdCancel.setAutoDefault(False)
        vbqt.set_cancel(self, w_cmdCancel)
        self.cmdCancel = w_cmdCancel
        w_cmdCancel.setGeometry(112, 128, 81, 25)
        w_cmdCancel.setObjectName('cmdCancel')

        QtWidgets.QWidget.setTabOrder(w_cmdOK, w_cboCode_0)
        QtWidgets.QWidget.setTabOrder(w_cboCode_0, w_cboCode_1)
        QtWidgets.QWidget.setTabOrder(w_cboCode_1, w_cboCode_2)
        QtWidgets.QWidget.setTabOrder(w_cboCode_2, w_cboCode_3)
        QtWidgets.QWidget.setTabOrder(w_cboCode_3, w_cboCode_4)
        QtWidgets.QWidget.setTabOrder(w_cboCode_4, w_cmdCancel)
        vbqt.fit_labels(self)


    def _connect(self):
        self.cmdCancel.clicked.connect(self._call('cmdCancel_Click'))
        self.cmdOK.clicked.connect(self._call('cmdOK_Click'))

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
