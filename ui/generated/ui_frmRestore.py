"""Oberfläche von frmRestore - automatisch erzeugt von frm2qt.py aus frmRestore.frm.

Nicht von Hand ändern: Die Datei wird beim erneuten Erzeugen überschrieben.
Logik gehört in eine abgeleitete Klasse mit den VB6-Prozedurnamen (siehe frmRestore.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmRestoreBase(QtWidgets.QDialog):
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
        self.chkSession = vbqt.ControlArray()
        self.optSession = vbqt.ControlArray()

        self.setWindowTitle('Restore timestamp')
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6-Standardschrift des Formulars
        self.setFixedSize(273, 73)

        # Frame1: VB.Frame
        w_Frame1 = vbqt.GroupFrame(self)
        w_Frame1.setTitle('Select session to restore')
        self.Frame1 = w_Frame1
        w_Frame1.setGeometry(8, 8, 169, 57)
        w_Frame1.setObjectName('Frame1')
        # optSession(0): VB.OptionButton
        w_optSession_0 = QtWidgets.QRadioButton(w_Frame1)
        w_optSession_0.setText('')
        self.optSession[0] = w_optSession_0
        w_optSession_0.setGeometry(16, 16, 145, 25)
        w_optSession_0.setObjectName('optSession_0')
        w_optSession_0.hide()

        # chkSession(0): VB.CheckBox
        w_chkSession_0 = QtWidgets.QCheckBox(w_Frame1)
        w_chkSession_0.setText('')
        self.chkSession[0] = w_chkSession_0
        w_chkSession_0.setGeometry(16, 16, 145, 25)
        w_chkSession_0.setObjectName('chkSession_0')
        w_chkSession_0.hide()


        # CancelButton: VB.CommandButton
        w_CancelButton = QtWidgets.QPushButton(self)
        w_CancelButton.setText('Cancel')
        w_CancelButton.setAutoDefault(False)
        self.CancelButton = w_CancelButton
        w_CancelButton.setGeometry(184, 40, 81, 25)
        w_CancelButton.setObjectName('CancelButton')

        # OKButton: VB.CommandButton
        w_OKButton = QtWidgets.QPushButton(self)
        w_OKButton.setText('OK')
        w_OKButton.setAutoDefault(False)
        self.OKButton = w_OKButton
        w_OKButton.setGeometry(184, 8, 81, 25)
        w_OKButton.setObjectName('OKButton')

        QtWidgets.QWidget.setTabOrder(w_optSession_0, w_chkSession_0)
        QtWidgets.QWidget.setTabOrder(w_CancelButton, w_OKButton)
        vbqt.fit_labels(self)


    def _connect(self):
        self.CancelButton.clicked.connect(self._call('CancelButton_Click'))
        self.OKButton.clicked.connect(self._call('OKButton_Click'))
        self.optSession[0].clicked.connect(self._call('optSession_Click', 0))
        vbqt.on_double_click(self.optSession[0], self._call('optSession_DblClick', 0))
        self.chkSession[0].clicked.connect(self._call('chkSession_Click', 0))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._vb('Form_Load')
