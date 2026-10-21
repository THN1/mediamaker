"""User interface of frmImport - generated automatically by frm2qt.py from frmImport.frm.

Do not change by hand: the file is overwritten when it is generated again.
Logic belongs in a derived class with the VB6 procedure names (see frmImport.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmImportBase(QtWidgets.QDialog):
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
        self.optJob = vbqt.ControlArray()

        self.setWindowTitle('Import')
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6 default font of the form
        self.setFixedSize(402, 90)

        # OKButton: VB.CommandButton
        w_OKButton = QtWidgets.QPushButton(self)
        w_OKButton.setText('OK')
        w_OKButton.setAutoDefault(False)
        self.OKButton = w_OKButton
        w_OKButton.setGeometry(312, 8, 81, 25)
        w_OKButton.setObjectName('OKButton')

        # CancelButton: VB.CommandButton
        w_CancelButton = QtWidgets.QPushButton(self)
        w_CancelButton.setText('Cancel')
        w_CancelButton.setAutoDefault(False)
        self.CancelButton = w_CancelButton
        w_CancelButton.setGeometry(312, 40, 81, 25)
        w_CancelButton.setObjectName('CancelButton')

        # Frame1: VB.Frame
        w_Frame1 = vbqt.GroupFrame(self)
        w_Frame1.setTitle('Select which job to import from batch file')
        self.Frame1 = w_Frame1
        w_Frame1.setGeometry(8, 8, 297, 73)
        w_Frame1.setObjectName('Frame1')
        # optJob(0): VB.OptionButton
        w_optJob_0 = QtWidgets.QRadioButton(w_Frame1)
        w_optJob_0.setText('')
        self.optJob[0] = w_optJob_0
        w_optJob_0.setGeometry(16, 24, 265, 33)
        w_optJob_0.setObjectName('optJob_0')


        QtWidgets.QWidget.setTabOrder(w_OKButton, w_CancelButton)
        vbqt.fit_labels(self)


    def _connect(self):
        self.CancelButton.clicked.connect(self._call('CancelButton_Click'))
        self.OKButton.clicked.connect(self._call('OKButton_Click'))
        self.optJob[0].clicked.connect(self._call('optJob_Click', 0))
        vbqt.on_double_click(self.optJob[0], self._call('optJob_DblClick', 0))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._vb('Form_Load')
