"""Oberfläche von frmRemoveLogo - automatisch erzeugt von frm2qt.py aus frmRemoveLogo.frm.

Nicht von Hand ändern: Die Datei wird beim erneuten Erzeugen überschrieben.
Logik gehört in eine abgeleitete Klasse mit den VB6-Prozedurnamen (siehe frmRemoveLogo.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmRemoveLogoBase(QtWidgets.QDialog):
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
        self.cmdNavigate = vbqt.ControlArray()

        self.setWindowTitle("Select frame for ffmpeg's removelogo filter")
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6-Standardschrift des Formulars
        self.setFixedSize(609, 385)

        # lblFrame: VB.Label
        w_lblFrame = QtWidgets.QLabel(self)
        w_lblFrame.setText('')
        w_lblFrame.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblFrame.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblFrame.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblFrame = w_lblFrame
        w_lblFrame.setGeometry(88, 360, 89, 17)
        w_lblFrame.setObjectName('lblFrame')

        # Picture1: VB.PictureBox
        w_Picture1 = vbqt.PictureBox(self)
        self.Picture1 = w_Picture1
        w_Picture1.setGeometry(8, 8, 593, 337)
        w_Picture1.setObjectName('Picture1')

        # cmdOK: VB.CommandButton
        w_cmdOK = QtWidgets.QPushButton(self)
        w_cmdOK.setText('&OK')
        w_cmdOK.setAutoDefault(False)
        w_cmdOK.setDefault(True)
        self.cmdOK = w_cmdOK
        w_cmdOK.setGeometry(520, 352, 81, 25)
        w_cmdOK.setObjectName('cmdOK')

        # cmdCancel: VB.CommandButton
        w_cmdCancel = QtWidgets.QPushButton(self)
        w_cmdCancel.setText('&Cancel')
        w_cmdCancel.setAutoDefault(False)
        vbqt.set_cancel(self, w_cmdCancel)
        self.cmdCancel = w_cmdCancel
        w_cmdCancel.setGeometry(432, 352, 81, 25)
        w_cmdCancel.setObjectName('cmdCancel')

        # cmdNavigate(0): VB.CommandButton
        w_cmdNavigate_0 = QtWidgets.QPushButton(self)
        w_cmdNavigate_0.setText('<')
        w_cmdNavigate_0.setAutoDefault(False)
        self.cmdNavigate[0] = w_cmdNavigate_0
        w_cmdNavigate_0.setGeometry(48, 352, 35, 27)
        w_cmdNavigate_0.setObjectName('cmdNavigate_0')
        w_cmdNavigate_0.setToolTip('Previous frame')
        w_cmdNavigate_0.setFont(vbqt.make_font('MS Sans Serif', 13.5, 700, 0, 0, 0))

        # cmdNavigate(1): VB.CommandButton
        w_cmdNavigate_1 = QtWidgets.QPushButton(self)
        w_cmdNavigate_1.setText('>')
        w_cmdNavigate_1.setAutoDefault(False)
        self.cmdNavigate[1] = w_cmdNavigate_1
        w_cmdNavigate_1.setGeometry(184, 352, 35, 27)
        w_cmdNavigate_1.setObjectName('cmdNavigate_1')
        w_cmdNavigate_1.setToolTip('Next frame')
        w_cmdNavigate_1.setFont(vbqt.make_font('MS Sans Serif', 13.5, 700, 0, 0, 0))

        # cmdNavigate(2): VB.CommandButton
        w_cmdNavigate_2 = QtWidgets.QPushButton(self)
        w_cmdNavigate_2.setText('<<')
        w_cmdNavigate_2.setAutoDefault(False)
        self.cmdNavigate[2] = w_cmdNavigate_2
        w_cmdNavigate_2.setGeometry(8, 352, 35, 27)
        w_cmdNavigate_2.setObjectName('cmdNavigate_2')
        w_cmdNavigate_2.setToolTip('Go 10 frames left')
        w_cmdNavigate_2.setFont(vbqt.make_font('MS Sans Serif', 13.5, 700, 0, 0, 0))

        # cmdNavigate(3): VB.CommandButton
        w_cmdNavigate_3 = QtWidgets.QPushButton(self)
        w_cmdNavigate_3.setText('>>')
        w_cmdNavigate_3.setAutoDefault(False)
        self.cmdNavigate[3] = w_cmdNavigate_3
        w_cmdNavigate_3.setGeometry(224, 352, 35, 27)
        w_cmdNavigate_3.setObjectName('cmdNavigate_3')
        w_cmdNavigate_3.setToolTip('Go 10 frames right')
        w_cmdNavigate_3.setFont(vbqt.make_font('MS Sans Serif', 13.5, 700, 0, 0, 0))

        # hscBlend: VB.HScrollBar
        w_hscBlend = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Horizontal, self)
        w_hscBlend.setRange(0, 1800)
        w_hscBlend.setSingleStep(1)
        w_hscBlend.setPageStep(100)
        self.hscBlend = w_hscBlend
        w_hscBlend.setGeometry(264, 360, 161, 17)
        w_hscBlend.setObjectName('hscBlend')

        # fraBlend: VB.Frame
        w_fraBlend = vbqt.Container(self)
        w_fraBlend.setAutoFillBackground(True)
        self.fraBlend = w_fraBlend
        w_fraBlend.setGeometry(10, 344, 589, 1)
        w_fraBlend.setObjectName('fraBlend')
        w_fraBlend.setStyleSheet("#fraBlend { background-color: rgb(255, 0, 0); }")
        w_fraBlend.hide()

        QtWidgets.QWidget.setTabOrder(w_cmdOK, w_cmdCancel)
        QtWidgets.QWidget.setTabOrder(w_cmdCancel, w_cmdNavigate_0)
        QtWidgets.QWidget.setTabOrder(w_cmdNavigate_0, w_cmdNavigate_1)
        QtWidgets.QWidget.setTabOrder(w_cmdNavigate_1, w_cmdNavigate_2)
        QtWidgets.QWidget.setTabOrder(w_cmdNavigate_2, w_cmdNavigate_3)
        QtWidgets.QWidget.setTabOrder(w_cmdNavigate_3, w_hscBlend)
        vbqt.fit_labels(self)


    def _connect(self):
        self.cmdNavigate[0].clicked.connect(self._call('cmdNavigate_Click', 0))
        self.cmdNavigate[1].clicked.connect(self._call('cmdNavigate_Click', 1))
        self.cmdNavigate[2].clicked.connect(self._call('cmdNavigate_Click', 2))
        self.cmdNavigate[3].clicked.connect(self._call('cmdNavigate_Click', 3))
        self.cmdCancel.clicked.connect(self._call('cmdCancel_Click'))
        self.cmdOK.clicked.connect(self._call('cmdOK_Click'))
        self.hscBlend.valueChanged.connect(self._call('hscBlend_Change'))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._vb('Form_Load')
            self._vb('Form_Activate')

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.ActivationChange and self._loaded:
            if self.isActiveWindow():
                self._vb('Form_Activate')
