"""User interface of frmMain - generated automatically by frm2qt.py from frmMediaMaker.frm.

Do not change by hand: the file is overwritten when it is generated again.
Logic belongs in a derived class with the VB6 procedure names (see frmMain.py).
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

import vbqt

HERE = os.path.dirname(os.path.abspath(__file__))


class frmMainBase(QtWidgets.QMainWindow):
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
        self.fraCrop = vbqt.ControlArray()
        self.cmdCommand = vbqt.ControlArray()
        self.lblText = vbqt.ControlArray()
        self.lblLabel = vbqt.ControlArray()
        self.cmdPos = vbqt.ControlArray()
        self.mnuProfileList = vbqt.ControlArray()

        self.setWindowTitle('frmMain')
        self.setWindowIcon(QtGui.QIcon(os.path.join(HERE, 'icons', 'frmMediaMaker_0000.png')))
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, False)
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        central.setFont(vbqt.make_font('MS Sans Serif', 8.25, 400, 0, 0, 0))      # VB6 default font of the form (menu keeps the system font)
        central.setFixedSize(1089, 436)

        menubar = self.menuBar()
        w_mnuFile = menubar.addMenu('&File')
        self.mnuFile = w_mnuFile
        w_mnuOpen = QtGui.QAction('&Open', self)
        w_mnuOpen.setShortcut(QtGui.QKeySequence('Ctrl+O'))
        w_mnuFile.addAction(w_mnuOpen)
        self.mnuOpen = w_mnuOpen
        w_mnuClose = QtGui.QAction('C&lose all', self)
        w_mnuClose.setShortcut(QtGui.QKeySequence('Ctrl+L'))
        w_mnuFile.addAction(w_mnuClose)
        self.mnuClose = w_mnuClose
        w_mnuDelete = QtGui.QAction('Delete...', self)
        w_mnuDelete.setShortcut(QtGui.QKeySequence('Ctrl+J'))
        w_mnuFile.addAction(w_mnuDelete)
        self.mnuDelete = w_mnuDelete
        w_mnuFile.addSeparator()
        w_mnuInfo = QtGui.QAction('I&nformation...', self)
        w_mnuInfo.setShortcut(QtGui.QKeySequence('Ctrl+N'))
        w_mnuFile.addAction(w_mnuInfo)
        self.mnuInfo = w_mnuInfo
        w_mnuSaveMP4 = QtGui.QAction('&Save as MP4', self)
        w_mnuSaveMP4.setShortcut(QtGui.QKeySequence('Ctrl+S'))
        w_mnuFile.addAction(w_mnuSaveMP4)
        self.mnuSaveMP4 = w_mnuSaveMP4
        w_mnuSaveAVI = QtGui.QAction('Save as A&VI', self)
        w_mnuSaveAVI.setShortcut(QtGui.QKeySequence('Ctrl+V'))
        w_mnuFile.addAction(w_mnuSaveAVI)
        self.mnuSaveAVI = w_mnuSaveAVI
        w_mnuCancel = QtGui.QAction('&Cancel save', self)
        w_mnuCancel.setShortcut(QtGui.QKeySequence('Ctrl+C'))
        w_mnuCancel.setEnabled(False)
        w_mnuFile.addAction(w_mnuCancel)
        self.mnuCancel = w_mnuCancel
        w_mnuFile.addSeparator()
        w_mnuBatch = QtGui.QAction('&Batch...', self)
        w_mnuBatch.setShortcut(QtGui.QKeySequence('Ctrl+B'))
        w_mnuFile.addAction(w_mnuBatch)
        self.mnuBatch = w_mnuBatch
        w_mnuImport = QtGui.QAction('I&mport...', self)
        w_mnuImport.setShortcut(QtGui.QKeySequence('Ctrl+M'))
        w_mnuFile.addAction(w_mnuImport)
        self.mnuImport = w_mnuImport
        w_mnuFile.addSeparator()
        w_mnuBackupSession = QtGui.QAction('Backup session', self)
        w_mnuBackupSession.setShortcut(QtGui.QKeySequence('Ctrl+Q'))
        w_mnuFile.addAction(w_mnuBackupSession)
        self.mnuBackupSession = w_mnuBackupSession
        w_mnuRestoreSession = QtGui.QAction('Restore session...', self)
        w_mnuRestoreSession.setShortcut(QtGui.QKeySequence('Ctrl+Z'))
        w_mnuFile.addAction(w_mnuRestoreSession)
        self.mnuRestoreSession = w_mnuRestoreSession
        w_mnuDeleteSession = QtGui.QAction('Delete session(s)...', self)
        w_mnuDeleteSession.setShortcut(QtGui.QKeySequence('Ctrl+P'))
        w_mnuFile.addAction(w_mnuDeleteSession)
        self.mnuDeleteSession = w_mnuDeleteSession
        w_mnuFile.addSeparator()
        w_mnuExit = QtGui.QAction('E&xit', self)
        w_mnuExit.setShortcut(QtGui.QKeySequence('Ctrl+X'))
        w_mnuFile.addAction(w_mnuExit)
        self.mnuExit = w_mnuExit
        w_mnuEdit = menubar.addMenu('&Edit')
        self.mnuEdit = w_mnuEdit
        w_mnuProfile = QtGui.QAction('Pro&file...', self)
        w_mnuProfile.setShortcut(QtGui.QKeySequence('Ctrl+F'))
        w_mnuEdit.addAction(w_mnuProfile)
        self.mnuProfile = w_mnuProfile
        w_mnuLoadProfile = w_mnuEdit.addMenu('&Load profile')
        self.mnuLoadProfile = w_mnuLoadProfile
        w_mnuProfileList_0 = QtGui.QAction('', self)
        w_mnuLoadProfile.addAction(w_mnuProfileList_0)
        self.mnuProfileList[0] = w_mnuProfileList_0
        w_mnuSaveProfile = QtGui.QAction('S&ave profile', self)
        w_mnuSaveProfile.setShortcut(QtGui.QKeySequence('Ctrl+A'))
        w_mnuEdit.addAction(w_mnuSaveProfile)
        self.mnuSaveProfile = w_mnuSaveProfile
        w_mnuEdit.addSeparator()
        w_mnuCopyMode = QtGui.QAction('Copy mo&de', self)
        w_mnuCopyMode.setShortcut(QtGui.QKeySequence('Ctrl+D'))
        w_mnuEdit.addAction(w_mnuCopyMode)
        self.mnuCopyMode = w_mnuCopyMode
        w_mnuCalcVideo = QtGui.QAction('&Estimate video kb/s', self)
        w_mnuCalcVideo.setShortcut(QtGui.QKeySequence('Ctrl+E'))
        w_mnuEdit.addAction(w_mnuCalcVideo)
        self.mnuCalcVideo = w_mnuCalcVideo
        w_mnuCalcAudio = QtGui.QAction('Est&imate audio kb/s', self)
        w_mnuCalcAudio.setShortcut(QtGui.QKeySequence('Ctrl+I'))
        w_mnuEdit.addAction(w_mnuCalcAudio)
        self.mnuCalcAudio = w_mnuCalcAudio
        w_mnuReuse = QtGui.QAction('Reuse source A/V', self)
        w_mnuReuse.setShortcut(QtGui.QKeySequence('Ctrl+G'))
        w_mnuEdit.addAction(w_mnuReuse)
        self.mnuReuse = w_mnuReuse
        w_mnuAutoCrop = QtGui.QAction('Auto c&rop', self)
        w_mnuAutoCrop.setShortcut(QtGui.QKeySequence('Ctrl+R'))
        w_mnuEdit.addAction(w_mnuAutoCrop)
        self.mnuAutoCrop = w_mnuAutoCrop
        w_mnuEdit.addSeparator()
        w_mnuMediaInfo = QtGui.QAction('Media info', self)
        w_mnuMediaInfo.setShortcut(QtGui.QKeySequence('Ctrl+K'))
        w_mnuEdit.addAction(w_mnuMediaInfo)
        self.mnuMediaInfo = w_mnuMediaInfo
        w_mnuCutPoints = QtGui.QAction('Anal&yze cut point', self)
        w_mnuCutPoints.setShortcut(QtGui.QKeySequence('Ctrl+Y'))
        w_mnuEdit.addAction(w_mnuCutPoints)
        self.mnuCutPoints = w_mnuCutPoints
        w_cmdOverlap = QtGui.QAction('Overlap segments', self)
        w_cmdOverlap.setShortcut(QtGui.QKeySequence('Ctrl+F8'))
        w_mnuEdit.addAction(w_cmdOverlap)
        self.cmdOverlap = w_cmdOverlap
        w_mnuChapters = QtGui.QAction('C&hapters...', self)
        w_mnuChapters.setShortcut(QtGui.QKeySequence('Ctrl+H'))
        w_mnuEdit.addAction(w_mnuChapters)
        self.mnuChapters = w_mnuChapters
        w_mnuNext = QtGui.QAction('Seek next commercial', self)
        w_mnuNext.setShortcut(QtGui.QKeySequence('Ctrl+W'))
        w_mnuEdit.addAction(w_mnuNext)
        self.mnuNext = w_mnuNext
        w_mnuEnd = QtGui.QAction('Seek end of commercial', self)
        w_mnuEnd.setShortcut(QtGui.QKeySequence('Ctrl+U'))
        w_mnuEdit.addAction(w_mnuEnd)
        self.mnuEnd = w_mnuEnd
        w_mnuEdit.addSeparator()
        w_mnuOptions = QtGui.QAction('Op&tions...', self)
        w_mnuOptions.setShortcut(QtGui.QKeySequence('Ctrl+T'))
        w_mnuEdit.addAction(w_mnuOptions)
        self.mnuOptions = w_mnuOptions
        w_mnuDeploy = menubar.addMenu('&Deploy')
        self.mnuDeploy = w_mnuDeploy
        w_mnuSetup = QtGui.QAction('Edit setup values', self)
        w_mnuDeploy.addAction(w_mnuSetup)
        self.mnuSetup = w_mnuSetup
        w_mnuDefault = QtGui.QAction('Create default ini', self)
        w_mnuDeploy.addAction(w_mnuDefault)
        self.mnuDefault = w_mnuDefault

        # lblInfo: VB.Label
        w_lblInfo = QtWidgets.QLabel(central)
        w_lblInfo.setText('')
        w_lblInfo.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblInfo.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblInfo.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblInfo = w_lblInfo
        w_lblInfo.setGeometry(840, 328, 81, 17)
        w_lblInfo.setObjectName('lblInfo')
        w_lblInfo.setToolTip('Click to change frame')

        # Line1: VB.Line
        w_Line1 = QtWidgets.QFrame(central)
        w_Line1.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        w_Line1.setAutoFillBackground(True)
        w_Line1.setStyleSheet("background-color: rgb(255, 0, 0);")
        self.Line1 = w_Line1
        w_Line1.setGeometry(543, 352, 3, 64)
        w_Line1.setObjectName('Line1')

        # SP: MediaMaker.ShellPipe
        w_SP = QtWidgets.QWidget(central)      # ShellPipe: see runner.py
        w_SP.hide()
        self.SP = w_SP
        w_SP.setGeometry(1064, 328, 0, 0)
        w_SP.setObjectName('SP')

        # lblTime: VB.Label
        w_lblTime = QtWidgets.QLabel(central)
        w_lblTime.setText('')
        w_lblTime.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblTime.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblTime.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblTime = w_lblTime
        w_lblTime.setGeometry(928, 328, 105, 17)
        w_lblTime.setObjectName('lblTime')

        # picDummy: VB.PictureBox
        w_picDummy = vbqt.PictureBox(central)
        self.picDummy = w_picDummy
        w_picDummy.setGeometry(544, 0, 513, 289)
        w_picDummy.setObjectName('picDummy')
        w_picDummy.setEnabled(False)
        w_picDummy.hide()

        # VLC: AXVLCCtl.VLCPlugin2
        w_VLC = QtWidgets.QWidget(central)      # video area: playback later e.g. with python-vlc (set_xwindow(int(w_VLC.winId())))
        self.VLC = w_VLC
        w_VLC.setGeometry(544, 0, 513, 289)
        w_VLC.setObjectName('VLC')
        w_VLC.setStyleSheet("#VLC { background-color: rgb(0, 0, 0); }")

        # cmdLogo: VB.CommandButton
        w_cmdLogo = QtWidgets.QPushButton(central)
        w_cmdLogo.setText('L')
        w_cmdLogo.setAutoDefault(False)
        self.cmdLogo = w_cmdLogo
        w_cmdLogo.setGeometry(512, 192, 25, 25)
        w_cmdLogo.setObjectName('cmdLogo')
        w_cmdLogo.setToolTip('Create reference logo from current frame')

        # cmdCommand(6): VB.CommandButton
        w_cmdCommand_6 = QtWidgets.QPushButton(central)
        w_cmdCommand_6.setAutoDefault(False)
        w_cmdCommand_6.setIcon(QtGui.QIcon(os.path.join(HERE, 'icons', 'frmMediaMaker_5426.png')))
        self.cmdCommand[6] = w_cmdCommand_6
        w_cmdCommand_6.setGeometry(512, 160, 25, 25)
        w_cmdCommand_6.setObjectName('cmdCommand_6')
        w_cmdCommand_6.setToolTip('Open/close DeLogo dialog')

        # cmdPos(0): VB.CommandButton
        w_cmdPos_0 = QtWidgets.QPushButton(central)
        w_cmdPos_0.setText('|<')
        w_cmdPos_0.setAutoDefault(False)
        self.cmdPos[0] = w_cmdPos_0
        w_cmdPos_0.setGeometry(544, 328, 25, 25)
        w_cmdPos_0.setObjectName('cmdPos_0')
        w_cmdPos_0.setToolTip('Move to beginning')

        # cmdPos(1): VB.CommandButton
        w_cmdPos_1 = QtWidgets.QPushButton(central)
        w_cmdPos_1.setText('<<')
        w_cmdPos_1.setAutoDefault(False)
        self.cmdPos[1] = w_cmdPos_1
        w_cmdPos_1.setGeometry(568, 328, 25, 25)
        w_cmdPos_1.setObjectName('cmdPos_1')
        w_cmdPos_1.setToolTip('Move -5 seconds')

        # cmdPos(2): VB.CommandButton
        w_cmdPos_2 = QtWidgets.QPushButton(central)
        w_cmdPos_2.setText('<')
        w_cmdPos_2.setAutoDefault(False)
        self.cmdPos[2] = w_cmdPos_2
        w_cmdPos_2.setGeometry(592, 328, 25, 25)
        w_cmdPos_2.setObjectName('cmdPos_2')
        w_cmdPos_2.setToolTip('Move -1 frame')

        # cmdPos(3): VB.CommandButton
        w_cmdPos_3 = QtWidgets.QPushButton(central)
        w_cmdPos_3.setText('|>')
        w_cmdPos_3.setAutoDefault(False)
        self.cmdPos[3] = w_cmdPos_3
        w_cmdPos_3.setGeometry(616, 328, 25, 25)
        w_cmdPos_3.setObjectName('cmdPos_3')
        w_cmdPos_3.setToolTip('Play/Stop')

        # cmdPos(4): VB.CommandButton
        w_cmdPos_4 = QtWidgets.QPushButton(central)
        w_cmdPos_4.setText('>')
        w_cmdPos_4.setAutoDefault(False)
        self.cmdPos[4] = w_cmdPos_4
        w_cmdPos_4.setGeometry(640, 328, 25, 25)
        w_cmdPos_4.setObjectName('cmdPos_4')
        w_cmdPos_4.setToolTip('Move +1 frame')

        # cmdPos(5): VB.CommandButton
        w_cmdPos_5 = QtWidgets.QPushButton(central)
        w_cmdPos_5.setText('>>')
        w_cmdPos_5.setAutoDefault(False)
        self.cmdPos[5] = w_cmdPos_5
        w_cmdPos_5.setGeometry(664, 328, 25, 25)
        w_cmdPos_5.setObjectName('cmdPos_5')
        w_cmdPos_5.setToolTip('Move +5 seconds')

        # cmdPos(6): VB.CommandButton
        w_cmdPos_6 = QtWidgets.QPushButton(central)
        w_cmdPos_6.setText('>|')
        w_cmdPos_6.setAutoDefault(False)
        self.cmdPos[6] = w_cmdPos_6
        w_cmdPos_6.setGeometry(688, 328, 25, 25)
        w_cmdPos_6.setObjectName('cmdPos_6')
        w_cmdPos_6.setToolTip('Move to end')

        # Slider1: MSComctlLib.Slider
        w_Slider1 = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, central)
        w_Slider1.setRange(0, 1000)
        w_Slider1.setPageStep(100)
        self.Slider1 = w_Slider1
        w_Slider1.setGeometry(544, 288, 513, 33)
        w_Slider1.setObjectName('Slider1')

        # cmdPos(7): VB.CommandButton
        w_cmdPos_7 = QtWidgets.QPushButton(central)
        w_cmdPos_7.setText('[')
        w_cmdPos_7.setAutoDefault(False)
        self.cmdPos[7] = w_cmdPos_7
        w_cmdPos_7.setGeometry(712, 328, 25, 25)
        w_cmdPos_7.setObjectName('cmdPos_7')
        w_cmdPos_7.setToolTip('Set marker A')

        # cmdPos(8): VB.CommandButton
        w_cmdPos_8 = QtWidgets.QPushButton(central)
        w_cmdPos_8.setText(']')
        w_cmdPos_8.setAutoDefault(False)
        self.cmdPos[8] = w_cmdPos_8
        w_cmdPos_8.setGeometry(736, 328, 25, 25)
        w_cmdPos_8.setObjectName('cmdPos_8')
        w_cmdPos_8.setToolTip('Set marker B')

        # cmdPos(9): VB.CommandButton
        w_cmdPos_9 = QtWidgets.QPushButton(central)
        w_cmdPos_9.setText('A')
        w_cmdPos_9.setAutoDefault(False)
        self.cmdPos[9] = w_cmdPos_9
        w_cmdPos_9.setGeometry(760, 328, 25, 25)
        w_cmdPos_9.setObjectName('cmdPos_9')
        w_cmdPos_9.setToolTip('Go to marker A')

        # cmdPos(10): VB.CommandButton
        w_cmdPos_10 = QtWidgets.QPushButton(central)
        w_cmdPos_10.setText('B')
        w_cmdPos_10.setAutoDefault(False)
        self.cmdPos[10] = w_cmdPos_10
        w_cmdPos_10.setGeometry(784, 328, 25, 25)
        w_cmdPos_10.setObjectName('cmdPos_10')
        w_cmdPos_10.setToolTip('Go to marker B')

        # lvwSegments: MSComctlLib.ListView
        w_lvwSegments = vbqt.ListView(central)
        w_lvwSegments.setHeaderLabels(['#', 'Path', 'Title', 'First', 'Last', 'Time', 'Frames', 'FPS', 'width', 'height', 'bitrate video', 'bitrate audio', 'atrack', 'crop top', 'crop bottom', 'crop left', 'crop right', 'audio sampling rate', 'delogo'])
        self.lvwSegments = w_lvwSegments
        w_lvwSegments.setGeometry(0, 0, 505, 289)
        w_lvwSegments.setObjectName('lvwSegments')
        w_lvwSegments.setToolTip('Drag&drop files here, or chose File->Open')

        # cmdPos(11): VB.CommandButton
        w_cmdPos_11 = QtWidgets.QPushButton(central)
        w_cmdPos_11.setText('R')
        w_cmdPos_11.setAutoDefault(False)
        self.cmdPos[11] = w_cmdPos_11
        w_cmdPos_11.setGeometry(808, 328, 25, 25)
        w_cmdPos_11.setObjectName('cmdPos_11')
        w_cmdPos_11.setToolTip('Reset A/B markers to zero and EOF')

        # cmdCommand(0): VB.CommandButton
        w_cmdCommand_0 = QtWidgets.QPushButton(central)
        w_cmdCommand_0.setAutoDefault(False)
        w_cmdCommand_0.setIcon(QtGui.QIcon(os.path.join(HERE, 'icons', 'frmMediaMaker_475C.png')))
        self.cmdCommand[0] = w_cmdCommand_0
        w_cmdCommand_0.setGeometry(512, 0, 25, 25)
        w_cmdCommand_0.setObjectName('cmdCommand_0')
        w_cmdCommand_0.setToolTip('Remove selected segment')

        # cmdCommand(1): VB.CommandButton
        w_cmdCommand_1 = QtWidgets.QPushButton(central)
        w_cmdCommand_1.setAutoDefault(False)
        w_cmdCommand_1.setIcon(QtGui.QIcon(os.path.join(HERE, 'icons', 'frmMediaMaker_3A92.png')))
        self.cmdCommand[1] = w_cmdCommand_1
        w_cmdCommand_1.setGeometry(512, 32, 25, 25)
        w_cmdCommand_1.setObjectName('cmdCommand_1')
        w_cmdCommand_1.setToolTip('Shift selected segment up')

        # cmdCommand(2): VB.CommandButton
        w_cmdCommand_2 = QtWidgets.QPushButton(central)
        w_cmdCommand_2.setAutoDefault(False)
        w_cmdCommand_2.setIcon(QtGui.QIcon(os.path.join(HERE, 'icons', 'frmMediaMaker_2DC8.png')))
        self.cmdCommand[2] = w_cmdCommand_2
        w_cmdCommand_2.setGeometry(512, 64, 25, 25)
        w_cmdCommand_2.setObjectName('cmdCommand_2')
        w_cmdCommand_2.setToolTip('Shift selected segment down')

        # cmdCommand(3): VB.CommandButton
        w_cmdCommand_3 = QtWidgets.QPushButton(central)
        w_cmdCommand_3.setAutoDefault(False)
        w_cmdCommand_3.setIcon(QtGui.QIcon(os.path.join(HERE, 'icons', 'frmMediaMaker_20FE.png')))
        self.cmdCommand[3] = w_cmdCommand_3
        w_cmdCommand_3.setGeometry(512, 256, 25, 25)
        w_cmdCommand_3.setObjectName('cmdCommand_3')
        w_cmdCommand_3.setToolTip('Clear the list')

        # Frame1: VB.Frame
        w_Frame1 = vbqt.GroupFrame(central)
        w_Frame1.setTitle('Target output profile')
        self.Frame1 = w_Frame1
        w_Frame1.setGeometry(0, 288, 537, 65)
        w_Frame1.setObjectName('Frame1')
        # lblLabel(0): VB.Label
        w_lblLabel_0 = QtWidgets.QLabel(w_Frame1)
        w_lblLabel_0.setText('Total Playtime:')
        w_lblLabel_0.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_0.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_0.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[0] = w_lblLabel_0
        w_lblLabel_0.setGeometry(8, 16, 81, 17)
        w_lblLabel_0.setObjectName('lblLabel_0')

        # lblText(0): VB.Label
        w_lblText_0 = QtWidgets.QLabel(w_Frame1)
        w_lblText_0.setText('')
        w_lblText_0.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_0.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_0.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[0] = w_lblText_0
        w_lblText_0.setGeometry(96, 16, 81, 17)
        w_lblText_0.setObjectName('lblText_0')
        w_lblText_0.setStyleSheet("#lblText_0 { background-color: rgb(255, 255, 255); }")

        # lblLabel(1): VB.Label
        w_lblLabel_1 = QtWidgets.QLabel(w_Frame1)
        w_lblLabel_1.setText('Video Kb/sec:')
        w_lblLabel_1.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_1.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_1.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[1] = w_lblLabel_1
        w_lblLabel_1.setGeometry(8, 40, 81, 17)
        w_lblLabel_1.setObjectName('lblLabel_1')
        w_lblLabel_1.setToolTip('Click to edit profile')

        # lblText(1): VB.Label
        w_lblText_1 = QtWidgets.QLabel(w_Frame1)
        w_lblText_1.setText('')
        w_lblText_1.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_1.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_1.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[1] = w_lblText_1
        w_lblText_1.setGeometry(96, 40, 81, 17)
        w_lblText_1.setObjectName('lblText_1')
        w_lblText_1.setToolTip('Click to edit profile')
        w_lblText_1.setStyleSheet("#lblText_1 { background-color: rgb(255, 255, 255); }")

        # lblLabel(2): VB.Label
        w_lblLabel_2 = QtWidgets.QLabel(w_Frame1)
        w_lblLabel_2.setText('Scale:')
        w_lblLabel_2.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_2.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_2.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[2] = w_lblLabel_2
        w_lblLabel_2.setGeometry(184, 16, 81, 17)
        w_lblLabel_2.setObjectName('lblLabel_2')
        w_lblLabel_2.setToolTip('Click to edit profile')

        # lblText(2): VB.Label
        w_lblText_2 = QtWidgets.QLabel(w_Frame1)
        w_lblText_2.setText('')
        w_lblText_2.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_2.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_2.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[2] = w_lblText_2
        w_lblText_2.setGeometry(272, 16, 81, 17)
        w_lblText_2.setObjectName('lblText_2')
        w_lblText_2.setToolTip('Click to edit profile')
        w_lblText_2.setStyleSheet("#lblText_2 { background-color: rgb(255, 255, 255); }")

        # lblLabel(3): VB.Label
        w_lblLabel_3 = QtWidgets.QLabel(w_Frame1)
        w_lblLabel_3.setText('FPS:')
        w_lblLabel_3.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_3.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_3.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[3] = w_lblLabel_3
        w_lblLabel_3.setGeometry(184, 40, 81, 17)
        w_lblLabel_3.setObjectName('lblLabel_3')
        w_lblLabel_3.setToolTip('Click to edit profile')

        # lblText(3): VB.Label
        w_lblText_3 = QtWidgets.QLabel(w_Frame1)
        w_lblText_3.setText('')
        w_lblText_3.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_3.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_3.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[3] = w_lblText_3
        w_lblText_3.setGeometry(272, 40, 81, 17)
        w_lblText_3.setObjectName('lblText_3')
        w_lblText_3.setToolTip('Click to edit profile')
        w_lblText_3.setStyleSheet("#lblText_3 { background-color: rgb(255, 255, 255); }")

        # lblLabel(4): VB.Label
        w_lblLabel_4 = QtWidgets.QLabel(w_Frame1)
        w_lblLabel_4.setText('Audio sampling:')
        w_lblLabel_4.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_4.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_4.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[4] = w_lblLabel_4
        w_lblLabel_4.setGeometry(360, 16, 81, 17)
        w_lblLabel_4.setObjectName('lblLabel_4')
        w_lblLabel_4.setToolTip('Click to edit profile')

        # lblText(4): VB.Label
        w_lblText_4 = QtWidgets.QLabel(w_Frame1)
        w_lblText_4.setText('')
        w_lblText_4.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_4.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_4.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[4] = w_lblText_4
        w_lblText_4.setGeometry(448, 16, 81, 17)
        w_lblText_4.setObjectName('lblText_4')
        w_lblText_4.setToolTip('Click to edit profile')
        w_lblText_4.setStyleSheet("#lblText_4 { background-color: rgb(255, 255, 255); }")

        # lblLabel(5): VB.Label
        w_lblLabel_5 = QtWidgets.QLabel(w_Frame1)
        w_lblLabel_5.setText('Audio Kb/sec:')
        w_lblLabel_5.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblLabel_5.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblLabel_5.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblLabel[5] = w_lblLabel_5
        w_lblLabel_5.setGeometry(360, 40, 81, 17)
        w_lblLabel_5.setObjectName('lblLabel_5')
        w_lblLabel_5.setToolTip('Click to edit profile')

        # lblText(5): VB.Label
        w_lblText_5 = QtWidgets.QLabel(w_Frame1)
        w_lblText_5.setText('')
        w_lblText_5.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        w_lblText_5.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        w_lblText_5.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.lblText[5] = w_lblText_5
        w_lblText_5.setGeometry(448, 40, 81, 17)
        w_lblText_5.setObjectName('lblText_5')
        w_lblText_5.setToolTip('Click to edit profile')
        w_lblText_5.setStyleSheet("#lblText_5 { background-color: rgb(255, 255, 255); }")


        # picProgress: VB.PictureBox
        w_picProgress = vbqt.PictureBox(central)
        self.picProgress = w_picProgress
        w_picProgress.setGeometry(0, 416, 1089, 17)
        w_picProgress.setObjectName('picProgress')

        # cmdCommand(4): VB.CommandButton
        w_cmdCommand_4 = QtWidgets.QPushButton(central)
        w_cmdCommand_4.setAutoDefault(False)
        w_cmdCommand_4.setIcon(QtGui.QIcon(os.path.join(HERE, 'icons', 'frmMediaMaker_1434.png')))
        self.cmdCommand[4] = w_cmdCommand_4
        w_cmdCommand_4.setGeometry(512, 96, 25, 25)
        w_cmdCommand_4.setObjectName('cmdCommand_4')
        w_cmdCommand_4.setToolTip('Duplicate segment')

        # picTimeline: VB.PictureBox
        w_picTimeline = vbqt.PictureBox(central)
        self.picTimeline = w_picTimeline
        w_picTimeline.setGeometry(0, 360, 1089, 49)
        w_picTimeline.setObjectName('picTimeline')

        # cmdCommand(5): VB.CommandButton
        w_cmdCommand_5 = QtWidgets.QPushButton(central)
        w_cmdCommand_5.setAutoDefault(False)
        w_cmdCommand_5.setIcon(QtGui.QIcon(os.path.join(HERE, 'icons', 'frmMediaMaker_0CCA.png')))
        self.cmdCommand[5] = w_cmdCommand_5
        w_cmdCommand_5.setGeometry(512, 128, 25, 25)
        w_cmdCommand_5.setObjectName('cmdCommand_5')
        w_cmdCommand_5.setToolTip('Open cropping dialog')

        # vscVolume: VB.VScrollBar
        w_vscVolume = QtWidgets.QScrollBar(QtCore.Qt.Orientation.Vertical, central)
        w_vscVolume.setRange(0, 1023)
        w_vscVolume.setSingleStep(1)
        w_vscVolume.setPageStep(64)
        w_vscVolume.setValue(800)
        self.vscVolume = w_vscVolume
        w_vscVolume.setGeometry(1064, 0, 17, 321)
        w_vscVolume.setObjectName('vscVolume')

        # fraCrop(0): VB.Frame
        w_fraCrop_0 = vbqt.Container(central)
        w_fraCrop_0.setAutoFillBackground(True)
        self.fraCrop[0] = w_fraCrop_0
        w_fraCrop_0.setGeometry(560, 16, 25, 25)
        w_fraCrop_0.setObjectName('fraCrop_0')
        w_fraCrop_0.setStyleSheet("#fraCrop_0 { background-color: rgb(255, 0, 0); }")
        w_fraCrop_0.hide()

        # fraCrop(1): VB.Frame
        w_fraCrop_1 = vbqt.Container(central)
        w_fraCrop_1.setAutoFillBackground(True)
        self.fraCrop[1] = w_fraCrop_1
        w_fraCrop_1.setGeometry(592, 16, 25, 25)
        w_fraCrop_1.setObjectName('fraCrop_1')
        w_fraCrop_1.setStyleSheet("#fraCrop_1 { background-color: rgb(255, 0, 0); }")
        w_fraCrop_1.hide()

        # fraCrop(2): VB.Frame
        w_fraCrop_2 = vbqt.Container(central)
        w_fraCrop_2.setAutoFillBackground(True)
        self.fraCrop[2] = w_fraCrop_2
        w_fraCrop_2.setGeometry(624, 16, 25, 25)
        w_fraCrop_2.setObjectName('fraCrop_2')
        w_fraCrop_2.setStyleSheet("#fraCrop_2 { background-color: rgb(255, 0, 0); }")
        w_fraCrop_2.hide()

        # fraCrop(3): VB.Frame
        w_fraCrop_3 = vbqt.Container(central)
        w_fraCrop_3.setAutoFillBackground(True)
        self.fraCrop[3] = w_fraCrop_3
        w_fraCrop_3.setGeometry(656, 16, 25, 25)
        w_fraCrop_3.setObjectName('fraCrop_3')
        w_fraCrop_3.setStyleSheet("#fraCrop_3 { background-color: rgb(255, 0, 0); }")
        w_fraCrop_3.hide()

        # picLogo: VB.PictureBox
        w_picLogo = vbqt.PictureBox(central)
        self.picLogo = w_picLogo
        w_picLogo.setGeometry(506, 220, 64, 35)
        w_picLogo.setObjectName('picLogo')
        w_picLogo.setToolTip('Reference logo')
        w_picLogo.hide()

        QtWidgets.QWidget.setTabOrder(w_cmdPos_0, w_vscVolume)
        QtWidgets.QWidget.setTabOrder(w_vscVolume, w_cmdPos_2)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_2, w_cmdPos_3)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_3, w_cmdPos_4)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_4, w_cmdPos_5)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_5, w_cmdPos_6)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_6, w_Slider1)
        QtWidgets.QWidget.setTabOrder(w_Slider1, w_cmdPos_7)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_7, w_cmdPos_8)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_8, w_cmdPos_9)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_9, w_cmdPos_10)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_10, w_lvwSegments)
        QtWidgets.QWidget.setTabOrder(w_lvwSegments, w_cmdPos_11)
        QtWidgets.QWidget.setTabOrder(w_cmdPos_11, w_cmdCommand_0)
        QtWidgets.QWidget.setTabOrder(w_cmdCommand_0, w_cmdCommand_1)
        QtWidgets.QWidget.setTabOrder(w_cmdCommand_1, w_cmdCommand_2)
        QtWidgets.QWidget.setTabOrder(w_cmdCommand_2, w_cmdCommand_3)
        QtWidgets.QWidget.setTabOrder(w_cmdCommand_3, w_cmdCommand_4)
        QtWidgets.QWidget.setTabOrder(w_cmdCommand_4, w_cmdCommand_5)
        QtWidgets.QWidget.setTabOrder(w_cmdCommand_5, w_cmdCommand_6)
        QtWidgets.QWidget.setTabOrder(w_cmdCommand_6, w_cmdLogo)
        QtWidgets.QWidget.setTabOrder(w_cmdLogo, w_cmdPos_1)
        vbqt.fit_labels(central)


    def _connect(self):
        self.cmdCommand[0].clicked.connect(self._call('cmdCommand_Click', 0))
        self.cmdCommand[1].clicked.connect(self._call('cmdCommand_Click', 1))
        self.cmdCommand[2].clicked.connect(self._call('cmdCommand_Click', 2))
        self.cmdCommand[3].clicked.connect(self._call('cmdCommand_Click', 3))
        self.cmdCommand[4].clicked.connect(self._call('cmdCommand_Click', 4))
        self.cmdCommand[5].clicked.connect(self._call('cmdCommand_Click', 5))
        self.cmdCommand[6].clicked.connect(self._call('cmdCommand_Click', 6))
        vbqt.on_mouse(self.cmdCommand[0], down=self._callv('cmdCommand_MouseDown', 0))
        vbqt.on_mouse(self.cmdCommand[1], down=self._callv('cmdCommand_MouseDown', 1))
        vbqt.on_mouse(self.cmdCommand[2], down=self._callv('cmdCommand_MouseDown', 2))
        vbqt.on_mouse(self.cmdCommand[3], down=self._callv('cmdCommand_MouseDown', 3))
        vbqt.on_mouse(self.cmdCommand[4], down=self._callv('cmdCommand_MouseDown', 4))
        vbqt.on_mouse(self.cmdCommand[5], down=self._callv('cmdCommand_MouseDown', 5))
        vbqt.on_mouse(self.cmdCommand[6], down=self._callv('cmdCommand_MouseDown', 6))
        self.cmdLogo.clicked.connect(self._call('cmdLogo_Click'))
        self.cmdOverlap.triggered.connect(self._call('cmdOverlap_Click'))
        self.cmdPos[0].clicked.connect(self._call('cmdPos_Click', 0))
        self.cmdPos[1].clicked.connect(self._call('cmdPos_Click', 1))
        self.cmdPos[2].clicked.connect(self._call('cmdPos_Click', 2))
        self.cmdPos[3].clicked.connect(self._call('cmdPos_Click', 3))
        self.cmdPos[4].clicked.connect(self._call('cmdPos_Click', 4))
        self.cmdPos[5].clicked.connect(self._call('cmdPos_Click', 5))
        self.cmdPos[6].clicked.connect(self._call('cmdPos_Click', 6))
        self.cmdPos[7].clicked.connect(self._call('cmdPos_Click', 7))
        self.cmdPos[8].clicked.connect(self._call('cmdPos_Click', 8))
        self.cmdPos[9].clicked.connect(self._call('cmdPos_Click', 9))
        self.cmdPos[10].clicked.connect(self._call('cmdPos_Click', 10))
        self.cmdPos[11].clicked.connect(self._call('cmdPos_Click', 11))
        # TODO: VLC_MediaPlayerEndReached (AXVLCCtl.VLCPlugin2) has no automatic equivalent in Qt
        # TODO: VLC_MediaPlayerPaused (AXVLCCtl.VLCPlugin2) has no automatic equivalent in Qt
        # TODO: VLC_MediaPlayerPlaying (AXVLCCtl.VLCPlugin2) has no automatic equivalent in Qt
        # TODO: VLC_MediaPlayerStopped (AXVLCCtl.VLCPlugin2) has no automatic equivalent in Qt
        # TODO: VLC_MediaPlayerTimeChanged (AXVLCCtl.VLCPlugin2) has no automatic equivalent in Qt
        vbqt.on_mouse(self.fraCrop[0], down=self._callv('fraCrop_MouseDown', 0))
        vbqt.on_mouse(self.fraCrop[1], down=self._callv('fraCrop_MouseDown', 1))
        vbqt.on_mouse(self.fraCrop[2], down=self._callv('fraCrop_MouseDown', 2))
        vbqt.on_mouse(self.fraCrop[3], down=self._callv('fraCrop_MouseDown', 3))
        vbqt.on_mouse(self.fraCrop[0], move=self._callv('fraCrop_MouseMove', 0))
        vbqt.on_mouse(self.fraCrop[1], move=self._callv('fraCrop_MouseMove', 1))
        vbqt.on_mouse(self.fraCrop[2], move=self._callv('fraCrop_MouseMove', 2))
        vbqt.on_mouse(self.fraCrop[3], move=self._callv('fraCrop_MouseMove', 3))
        vbqt.on_mouse(self.fraCrop[0], up=self._callv('fraCrop_MouseUp', 0))
        vbqt.on_mouse(self.fraCrop[1], up=self._callv('fraCrop_MouseUp', 1))
        vbqt.on_mouse(self.fraCrop[2], up=self._callv('fraCrop_MouseUp', 2))
        vbqt.on_mouse(self.fraCrop[3], up=self._callv('fraCrop_MouseUp', 3))
        vbqt.on_click(self.lblInfo, self._call('lblInfo_Click'))
        vbqt.on_click(self.lblLabel[0], self._call('lblLabel_Click', 0))
        vbqt.on_click(self.lblLabel[1], self._call('lblLabel_Click', 1))
        vbqt.on_click(self.lblLabel[2], self._call('lblLabel_Click', 2))
        vbqt.on_click(self.lblLabel[3], self._call('lblLabel_Click', 3))
        vbqt.on_click(self.lblLabel[4], self._call('lblLabel_Click', 4))
        vbqt.on_click(self.lblLabel[5], self._call('lblLabel_Click', 5))
        vbqt.on_click(self.lblText[0], self._call('lblText_Click', 0))
        vbqt.on_click(self.lblText[1], self._call('lblText_Click', 1))
        vbqt.on_click(self.lblText[2], self._call('lblText_Click', 2))
        vbqt.on_click(self.lblText[3], self._call('lblText_Click', 3))
        vbqt.on_click(self.lblText[4], self._call('lblText_Click', 4))
        vbqt.on_click(self.lblText[5], self._call('lblText_Click', 5))
        self.lvwSegments.itemClicked.connect(self._call('lvwSegments_Click'))
        self.lvwSegments.itemDoubleClicked.connect(self._call('lvwSegments_DblClick'))
        vbqt.on_drop(self.lvwSegments, self._callv('lvwSegments_OLEDragDrop'))
        self.mnuAutoCrop.triggered.connect(self._call('mnuAutoCrop_Click'))
        self.mnuBackupSession.triggered.connect(self._call('mnuBackupSession_Click'))
        self.mnuBatch.triggered.connect(self._call('mnuBatch_Click'))
        self.mnuCalcAudio.triggered.connect(self._call('mnuCalcAudio_Click'))
        self.mnuCalcVideo.triggered.connect(self._call('mnuCalcVideo_Click'))
        self.mnuCancel.triggered.connect(self._call('mnuCancel_Click'))
        self.mnuChapters.triggered.connect(self._call('mnuChapters_Click'))
        self.mnuClose.triggered.connect(self._call('mnuClose_Click'))
        self.mnuCopyMode.triggered.connect(self._call('mnuCopyMode_Click'))
        self.mnuCutPoints.triggered.connect(self._call('mnuCutPoints_Click'))
        self.mnuDefault.triggered.connect(self._call('mnuDefault_Click'))
        self.mnuDelete.triggered.connect(self._call('mnuDelete_Click'))
        self.mnuEnd.triggered.connect(self._call('mnuEnd_Click'))
        self.mnuExit.triggered.connect(self._call('mnuExit_Click'))
        self.mnuImport.triggered.connect(self._call('mnuImport_Click'))
        self.mnuInfo.triggered.connect(self._call('mnuInfo_Click'))
        self.mnuMediaInfo.triggered.connect(self._call('mnuMediaInfo_Click'))
        self.mnuNext.triggered.connect(self._call('mnuNext_Click'))
        self.mnuOpen.triggered.connect(self._call('mnuOpen_Click'))
        self.mnuOptions.triggered.connect(self._call('mnuOptions_Click'))
        self.mnuProfile.triggered.connect(self._call('mnuProfile_Click'))
        self.mnuProfileList[0].triggered.connect(self._call('mnuProfileList_Click', 0))
        self.mnuDeleteSession.triggered.connect(self._call('mnuDeleteSession_Click'))
        self.mnuRestoreSession.triggered.connect(self._call('mnuRestoreSession_Click'))
        self.mnuReuse.triggered.connect(self._call('mnuReuse_Click'))
        self.mnuSaveAVI.triggered.connect(self._call('mnuSaveAVI_Click'))
        self.mnuSaveMP4.triggered.connect(self._call('mnuSaveMP4_Click'))
        self.mnuSaveProfile.triggered.connect(self._call('mnuSaveProfile_Click'))
        self.mnuSetup.triggered.connect(self._call('mnuSetup_Click'))
        vbqt.on_click(self.picTimeline, self._call('picTimeline_Click'))
        vbqt.on_mouse(self.picTimeline, move=self._callv('picTimeline_MouseMove'))
        self.Slider1.valueChanged.connect(self._call('Slider1_Change'))
        self.vscVolume.sliderMoved.connect(self._call('vscVolume_Scroll'))
        # TODO: SP_DataArrival (MediaMaker.ShellPipe) has no automatic equivalent in Qt

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            vbqt.center_on_screen(self)
            self._vb('Form_Load')

    def closeEvent(self, event):
        self._vb('Form_Unload')
        super().closeEvent(event)
