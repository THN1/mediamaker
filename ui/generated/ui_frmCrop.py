"""Oberfläche von frmCrop - automatisch erzeugt von frm2qt.py aus frmCrop.frm.

Nicht von Hand ändern: Die Datei wird beim erneuten Erzeugen überschrieben.
Logik gehört in eine abgeleitete Klasse mit den VB6-Prozedurnamen (siehe frmCrop.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmCropBase(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._loaded = False
        self._build()
        self._connect()

    def _vb(self, procedure, *args):
        """Ruft die VB6-Prozedur (falls in der abgeleiteten Klasse vorhanden) auf."""
        fn = getattr(self, procedure, None)
        return fn(*args) if fn else None

    def _call(self, procedure, *fixed):
        return lambda *signal_args: self._vb(procedure, *fixed)

    def _callv(self, procedure, *fixed):
        """Wie _call, reicht aber die Argumente des Ereignisses weiter (Maus, Tasten, Dateien)."""
        return lambda *event_args: self._vb(procedure, *fixed, *event_args)

    def _build(self):
        self.VScroll = vbqt.ControlArray()
        self.HScroll = vbqt.ControlArray()
        self.txtCrop = vbqt.ControlArray()
        self.lblLabel = vbqt.ControlArray()

        self.setWindowTitle('Form1')
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6-Standardschrift des Formulars
        self.resize(281, 161)

        # lblLabel(0): VB.Label
        w_lblLabel_0 = QtWidgets.QLabel(self)
        w_lblLabel_0.setText('Top:')
        w_lblLabel_0.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_0.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_0.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[0] = w_lblLabel_0
        w_lblLabel_0.setGeometry(88, 24, 49, 17)
        w_lblLabel_0.setObjectName('lblLabel_0')
        w_lblLabel_0.setStyleSheet("#lblLabel_0 { background-color: rgb(255, 255, 255); }")

        # lblLabel(1): VB.Label
        w_lblLabel_1 = QtWidgets.QLabel(self)
        w_lblLabel_1.setText('Bottom:')
        w_lblLabel_1.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_1.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_1.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[1] = w_lblLabel_1
        w_lblLabel_1.setGeometry(88, 120, 49, 17)
        w_lblLabel_1.setObjectName('lblLabel_1')
        w_lblLabel_1.setStyleSheet("#lblLabel_1 { background-color: rgb(255, 255, 255); }")

        # lblLabel(2): VB.Label
        w_lblLabel_2 = QtWidgets.QLabel(self)
        w_lblLabel_2.setText('Left:')
        w_lblLabel_2.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_2.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_2.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[2] = w_lblLabel_2
        w_lblLabel_2.setGeometry(32, 72, 49, 17)
        w_lblLabel_2.setObjectName('lblLabel_2')
        w_lblLabel_2.setStyleSheet("#lblLabel_2 { background-color: rgb(255, 255, 255); }")

        # lblLabel(3): VB.Label
        w_lblLabel_3 = QtWidgets.QLabel(self)
        w_lblLabel_3.setText('Right:')
        w_lblLabel_3.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_3.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_3.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[3] = w_lblLabel_3
        w_lblLabel_3.setGeometry(144, 72, 49, 17)
        w_lblLabel_3.setObjectName('lblLabel_3')
        w_lblLabel_3.setStyleSheet("#lblLabel_3 { background-color: rgb(255, 255, 255); }")

        # HScroll(0): VB.HScrollBar
        w_HScroll_0 = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal, self)
        w_HScroll_0.setRange(0, 400)
        w_HScroll_0.setSingleStep(1)
        w_HScroll_0.setPageStep(20)
        self.HScroll[0] = w_HScroll_0
        w_HScroll_0.setGeometry(16, 0, 249, 17)
        w_HScroll_0.setObjectName('HScroll_0')

        # VScroll(0): VB.VScrollBar
        w_VScroll_0 = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical, self)
        w_VScroll_0.setRange(0, 250)
        w_VScroll_0.setSingleStep(1)
        w_VScroll_0.setPageStep(20)
        self.VScroll[0] = w_VScroll_0
        w_VScroll_0.setGeometry(0, 0, 17, 161)
        w_VScroll_0.setObjectName('VScroll_0')

        # txtCrop(0): VB.TextBox
        w_txtCrop_0 = QtWidgets.QLineEdit(self)
        w_txtCrop_0.setText('0')
        self.txtCrop[0] = w_txtCrop_0
        w_txtCrop_0.setGeometry(144, 24, 49, 19)
        w_txtCrop_0.setObjectName('txtCrop_0')
        w_txtCrop_0.setStyleSheet("#txtCrop_0 { background-color: rgb(255, 255, 128); }")

        # txtCrop(1): VB.TextBox
        w_txtCrop_1 = QtWidgets.QLineEdit(self)
        w_txtCrop_1.setText('0')
        self.txtCrop[1] = w_txtCrop_1
        w_txtCrop_1.setGeometry(144, 120, 49, 19)
        w_txtCrop_1.setObjectName('txtCrop_1')
        w_txtCrop_1.setStyleSheet("#txtCrop_1 { background-color: rgb(255, 255, 128); }")

        # txtCrop(2): VB.TextBox
        w_txtCrop_2 = QtWidgets.QLineEdit(self)
        w_txtCrop_2.setText('0')
        self.txtCrop[2] = w_txtCrop_2
        w_txtCrop_2.setGeometry(88, 72, 49, 19)
        w_txtCrop_2.setObjectName('txtCrop_2')
        w_txtCrop_2.setStyleSheet("#txtCrop_2 { background-color: rgb(255, 255, 128); }")

        # txtCrop(3): VB.TextBox
        w_txtCrop_3 = QtWidgets.QLineEdit(self)
        w_txtCrop_3.setText('0')
        self.txtCrop[3] = w_txtCrop_3
        w_txtCrop_3.setGeometry(200, 72, 49, 19)
        w_txtCrop_3.setObjectName('txtCrop_3')
        w_txtCrop_3.setStyleSheet("#txtCrop_3 { background-color: rgb(255, 255, 128); }")

        # HScroll(1): VB.HScrollBar
        w_HScroll_1 = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal, self)
        w_HScroll_1.setRange(0, 400)
        w_HScroll_1.setSingleStep(1)
        w_HScroll_1.setPageStep(20)
        self.HScroll[1] = w_HScroll_1
        w_HScroll_1.setGeometry(16, 144, 249, 17)
        w_HScroll_1.setObjectName('HScroll_1')

        # VScroll(1): VB.VScrollBar
        w_VScroll_1 = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical, self)
        w_VScroll_1.setRange(0, 250)
        w_VScroll_1.setSingleStep(1)
        w_VScroll_1.setPageStep(20)
        self.VScroll[1] = w_VScroll_1
        w_VScroll_1.setGeometry(264, 0, 17, 161)
        w_VScroll_1.setObjectName('VScroll_1')

        # cmdCancel: VB.CommandButton
        w_cmdCancel = QtWidgets.QPushButton(self)
        w_cmdCancel.setText('X')
        w_cmdCancel.setAutoDefault(False)
        self.cmdCancel = w_cmdCancel
        w_cmdCancel.setGeometry(240, 16, 25, 25)
        w_cmdCancel.setObjectName('cmdCancel')
        w_cmdCancel.setToolTip('Cancel')
        w_cmdCancel.setFont(vbqt.make_font('MS Sans Serif', 12.0, 700, 0, 0, 0))
        w_cmdCancel.setStyleSheet("#cmdCancel { background-color: rgb(255, 0, 0); }")

        # cmdOK: VB.CommandButton
        w_cmdOK = QtWidgets.QPushButton(self)
        w_cmdOK.setText('OK')
        w_cmdOK.setAutoDefault(False)
        self.cmdOK = w_cmdOK
        w_cmdOK.setGeometry(240, 120, 25, 25)
        w_cmdOK.setObjectName('cmdOK')
        w_cmdOK.setToolTip('OK')
        w_cmdOK.setStyleSheet("#cmdOK { background-color: rgb(0, 255, 0); }")

        # cmdReset: VB.CommandButton
        w_cmdReset = QtWidgets.QPushButton(self)
        w_cmdReset.setText('R')
        w_cmdReset.setAutoDefault(False)
        self.cmdReset = w_cmdReset
        w_cmdReset.setGeometry(216, 120, 25, 25)
        w_cmdReset.setObjectName('cmdReset')
        w_cmdReset.setToolTip('Set all to zero')
        w_cmdReset.setStyleSheet("#cmdReset { background-color: rgb(128, 128, 255); }")

        # chkAutoRatio: VB.CheckBox
        w_chkAutoRatio = QtWidgets.QCheckBox(self)
        w_chkAutoRatio.setText('16:9')
        self.chkAutoRatio = w_chkAutoRatio
        w_chkAutoRatio.setGeometry(216, 104, 41, 17)
        w_chkAutoRatio.setObjectName('chkAutoRatio')
        w_chkAutoRatio.setToolTip('Check to ensure 16:9 aspect ratio by adjusting width according to height')

        QtWidgets.QWidget.setTabOrder(w_txtCrop_0, w_txtCrop_2)
        QtWidgets.QWidget.setTabOrder(w_txtCrop_2, w_txtCrop_3)
        QtWidgets.QWidget.setTabOrder(w_txtCrop_3, w_txtCrop_1)
        QtWidgets.QWidget.setTabOrder(w_txtCrop_1, w_cmdCancel)
        QtWidgets.QWidget.setTabOrder(w_cmdCancel, w_cmdReset)
        QtWidgets.QWidget.setTabOrder(w_cmdReset, w_cmdOK)
        QtWidgets.QWidget.setTabOrder(w_cmdOK, w_HScroll_0)
        QtWidgets.QWidget.setTabOrder(w_HScroll_0, w_VScroll_0)
        QtWidgets.QWidget.setTabOrder(w_VScroll_0, w_HScroll_1)
        QtWidgets.QWidget.setTabOrder(w_HScroll_1, w_VScroll_1)
        QtWidgets.QWidget.setTabOrder(w_VScroll_1, w_chkAutoRatio)
        vbqt.fit_labels(self)


    def _connect(self):
        self.chkAutoRatio.clicked.connect(self._call('chkAutoRatio_Click'))
        self.cmdOK.clicked.connect(self._call('cmdOK_Click'))
        self.cmdReset.clicked.connect(self._call('cmdReset_Click'))
        self.cmdCancel.clicked.connect(self._call('cmdCancel_Click'))
        self.HScroll[0].valueChanged.connect(self._call('HScroll_Change', 0))
        self.HScroll[1].valueChanged.connect(self._call('HScroll_Change', 1))
        self.VScroll[0].valueChanged.connect(self._call('VScroll_Change', 0))
        self.VScroll[1].valueChanged.connect(self._call('VScroll_Change', 1))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._vb('Form_Load')

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.ActivationChange and self._loaded:
            if not self.isActiveWindow():
                self._vb('Form_LostFocus')
