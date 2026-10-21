"""Oberfläche von frmInfo - automatisch erzeugt von frm2qt.py aus frmInfo.frm.

Nicht von Hand ändern: Die Datei wird beim erneuten Erzeugen überschrieben.
Logik gehört in eine abgeleitete Klasse mit den VB6-Prozedurnamen (siehe frmInfo.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmInfoBase(QtWidgets.QDialog):
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
        self.setWindowTitle('Loaded segments information')
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6-Standardschrift des Formulars
        self.setFixedSize(865, 321)

        # cmdClose: VB.CommandButton
        w_cmdClose = QtWidgets.QPushButton(self)
        w_cmdClose.setText('&Close')
        w_cmdClose.setAutoDefault(False)
        w_cmdClose.setDefault(True)
        vbqt.set_cancel(self, w_cmdClose)
        self.cmdClose = w_cmdClose
        w_cmdClose.setGeometry(776, 288, 81, 25)
        w_cmdClose.setObjectName('cmdClose')

        # lvwInfo: MSComctlLib.ListView
        w_lvwInfo = vbqt.ListView(self)
        w_lvwInfo.setHeaderLabels(['File', 'FileSize', 'Duration', 'Start time', 'Size', 'FPS', 'Sampling', 'KB/s (v)', 'KB/s (A)'])
        self.lvwInfo = w_lvwInfo
        w_lvwInfo.setGeometry(0, 0, 857, 281)
        w_lvwInfo.setObjectName('lvwInfo')

        QtWidgets.QWidget.setTabOrder(w_cmdClose, w_lvwInfo)
        vbqt.fit_labels(self)


    def _connect(self):
        self.cmdClose.clicked.connect(self._call('cmdClose_Click'))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
