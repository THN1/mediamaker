"""User interface of frmChapters - generated automatically by frm2qt.py from frmChapters.frm.

Do not change by hand: the file is overwritten when it is generated again.
Logic belongs in a derived class with the VB6 procedure names (see frmChapters.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmChaptersBase(QtWidgets.QDialog):
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
        self.setWindowTitle('Chapter Editor')
        self.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6 default font of the form
        self.resize(369, 313)

        # Label2: VB.Label
        w_Label2 = QtWidgets.QLabel(self)
        w_Label2.setText('Attention: Input file(s) MUST NOT HAVE CHAPTERS                  themselves, otherwise compilation will fail.')
        w_Label2.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.Label2 = w_Label2
        w_Label2.setGeometry(16, 280, 257, 33)
        w_Label2.setObjectName('Label2')
        w_Label2.setStyleSheet("#Label2 { color: rgb(255, 0, 0); }")

        # cmdOK: VB.CommandButton
        w_cmdOK = QtWidgets.QPushButton(self)
        w_cmdOK.setText('Close')
        w_cmdOK.setAutoDefault(False)
        self.cmdOK = w_cmdOK
        w_cmdOK.setGeometry(280, 280, 81, 25)
        w_cmdOK.setObjectName('cmdOK')

        # Frame1: VB.Frame
        w_Frame1 = vbqt.GroupFrame(self)
        w_Frame1.setTitle('Frame1')
        self.Frame1 = w_Frame1
        w_Frame1.setGeometry(8, 8, 353, 265)
        w_Frame1.setObjectName('Frame1')
        # Label1: VB.Label
        w_Label1 = QtWidgets.QLabel(w_Frame1)
        w_Label1.setText('Choose style:')
        w_Label1.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_Label1.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_Label1.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.Label1 = w_Label1
        w_Label1.setGeometry(8, 24, 73, 17)
        w_Label1.setObjectName('Label1')
        w_Label1.setStyleSheet("#Label1 { background-color: rgb(255, 255, 255); }")

        # lvwChapters: MSComctlLib.ListView
        w_lvwChapters = vbqt.ListView(w_Frame1)
        w_lvwChapters.setHeaderLabels(['Chapter'])
        w_lvwChapters.setHeaderHidden(True)
        self.lvwChapters = w_lvwChapters
        w_lvwChapters.setGeometry(8, 48, 337, 209)
        w_lvwChapters.setObjectName('lvwChapters')

        # cboStyle: VB.ComboBox
        w_cboStyle = QtWidgets.QComboBox(w_Frame1)
        w_cboStyle.addItem('Enumerated', 0)
        w_cboStyle.addItem('Named', 0)
        w_cboStyle.addItem('Named (short)', 0)
        w_cboStyle.addItem('Previous', 0)
        w_cboStyle.addItem('From Batch', 0)
        self.cboStyle = w_cboStyle
        w_cboStyle.setGeometry(88, 24, 113, 21)
        w_cboStyle.setObjectName('cboStyle')


        # chkActivate: VB.CheckBox
        w_chkActivate = QtWidgets.QCheckBox(self)
        w_chkActivate.setText('Add chapter(s) to target file')
        self.chkActivate = w_chkActivate
        w_chkActivate.setGeometry(16, 8, 153, 17)
        w_chkActivate.setObjectName('chkActivate')

        QtWidgets.QWidget.setTabOrder(w_lvwChapters, w_cboStyle)
        QtWidgets.QWidget.setTabOrder(w_cmdOK, w_chkActivate)
        vbqt.fit_labels(self)


    def _connect(self):
        self.cboStyle.activated.connect(self._call('cboStyle_Click'))
        self.chkActivate.clicked.connect(self._call('chkActivate_Click'))
        self.cmdOK.clicked.connect(self._call('cmdOK_Click'))
        # TODO: lvwChapters_AfterLabelEdit (MSComctlLib.ListView) has no automatic equivalent in Qt
        vbqt.on_key(self.lvwChapters, up=self._callv('lvwChapters_KeyUp'))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._vb('Form_Load')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._vb('Form_Resize')
