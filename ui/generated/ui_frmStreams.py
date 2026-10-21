"""Oberfläche von frmStreams - automatisch erzeugt von frm2qt.py aus frmStreams.frm.

Nicht von Hand ändern: Die Datei wird beim erneuten Erzeugen überschrieben.
Logik gehört in eine abgeleitete Klasse mit den VB6-Prozedurnamen (siehe frmStreams.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmStreamsBase(QtWidgets.QDialog):
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
        self.setWindowTitle('Select and map DVD streams')
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6-Standardschrift des Formulars
        self.setFixedSize(513, 297)

        # lvwStreams: MSComctlLib.ListView
        w_lvwStreams = vbqt.ListView(self)
        w_lvwStreams.setHeaderLabels(['Stream ID', 'Type', 'Properties', 'Language'])
        self.lvwStreams = w_lvwStreams
        w_lvwStreams.setGeometry(8, 128, 497, 161)
        w_lvwStreams.setObjectName('lvwStreams')

        # Frame1: VB.Frame
        w_Frame1 = vbqt.GroupFrame(self)
        w_Frame1.setTitle('Notes')
        self.Frame1 = w_Frame1
        w_Frame1.setGeometry(8, 8, 409, 113)
        w_Frame1.setObjectName('Frame1')
        # txtNotes: VB.TextBox
        w_txtNotes = QtWidgets.QPlainTextEdit(w_Frame1)
        w_txtNotes.setPlainText("When converting/encoding DVD's, all of the following applies:\r\n- all segments are processed in their natural sequence\r\n- when set, a global cropping will be applied to remove black borders\r\n- all other filtering (resizing, DeLogo) is disabled and inactive\r\n- you can select the audio and subtitle streams (tracks) here below, and assign \r\nthem proper language codes (if not automatically detected)\r\n\t\r\n")
        self.txtNotes = w_txtNotes
        w_txtNotes.setGeometry(8, 16, 393, 89)
        w_txtNotes.setObjectName('txtNotes')
        w_txtNotes.setStyleSheet("#txtNotes { background-color: rgb(255, 255, 128); }")


        # cmdOK: VB.CommandButton
        w_cmdOK = QtWidgets.QPushButton(self)
        w_cmdOK.setText('&OK')
        w_cmdOK.setAutoDefault(False)
        w_cmdOK.setDefault(True)
        self.cmdOK = w_cmdOK
        w_cmdOK.setGeometry(424, 96, 81, 25)
        w_cmdOK.setObjectName('cmdOK')

        # cmdCancel: VB.CommandButton
        w_cmdCancel = QtWidgets.QPushButton(self)
        w_cmdCancel.setText('Cancel')
        w_cmdCancel.setAutoDefault(False)
        vbqt.set_cancel(self, w_cmdCancel)
        self.cmdCancel = w_cmdCancel
        w_cmdCancel.setGeometry(424, 64, 81, 25)
        w_cmdCancel.setObjectName('cmdCancel')

        QtWidgets.QWidget.setTabOrder(w_lvwStreams, w_cmdOK)
        QtWidgets.QWidget.setTabOrder(w_cmdOK, w_cmdCancel)
        vbqt.fit_labels(self)


    def _connect(self):
        self.cmdCancel.clicked.connect(self._call('cmdCancel_Click'))
        self.cmdOK.clicked.connect(self._call('cmdOK_Click'))
        self.lvwStreams.itemDoubleClicked.connect(self._call('lvwStreams_DblClick'))
        self.lvwStreams.itemChanged.connect(self._call('lvwStreams_ItemCheck'))

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
