"""Single pictures from ffmpeg for the preview while the film is STOPPED (option paused_preview = ffmpeg).

libvlc can get stuck when it is asked to jump again and again in the paused state (after about ten jumps the picture no longer follows the slider). While
the film runs this does not happen. So while it is stopped the pictures come from ffmpeg: one process for one picture, frame exact and with the same frame
numbers as the thumbnails and the cut (VLC has been seen to show a picture that was 17 frames later). VLC is only told where to continue when Play is pressed.

StillPreview does one request at a time: while a picture is being read, newer requests replace each other (only the newest is read next), so that scrubbing with
the slider does not start a process for every pixel; each picture that arrives is shown (a little behind the slider), the last one is the one that counts.
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui

from player import debug_log


class StillWorker(QtCore.QThread):
    loaded = QtCore.Signal(str, int, object)        # file, frame number, picture (RGB array)
    ended = QtCore.Signal(object)                   # always when the thread ends (a picture that could not be read is just not shown)

    def __init__(self, path: str, frame: int, fps, grab_fn):
        super().__init__()
        self.path, self.frame, self.fps, self.grab_fn = path, frame, fps, grab_fn

    def run(self) -> None:
        try:
            try:
                array = self.grab_fn(self.path, self.frame, self.fps)
            except Exception as e:
                debug_log(f"still picture of frame {self.frame} could not be read: {e}")
                return
            self.loaded.emit(self.path, self.frame, array)
        finally:
            self.ended.emit(self)


class StillPreview(QtCore.QObject):
    ready = QtCore.Signal(str, int, object)         # file, frame number, QImage

    def __init__(self, grab_fn, parent=None):
        super().__init__(parent)
        self.grab_fn = grab_fn
        self._worker = None
        self._wanted = None                          # (file, frame, fps) of the newest request
        self._started = None                         # what the running thread reads

    def request(self, path: str, frame: int, fps) -> None:
        self._wanted = (path, frame, fps)
        self._next()

    def cancel(self) -> None:
        """Nothing more is wanted (another film, the list is cleared); a picture that is being read is not shown any more."""
        self._wanted = None

    @property
    def busy(self) -> bool:
        return self._worker is not None

    def _next(self) -> None:
        if self._worker is not None or self._wanted is None or self._wanted == self._started:
            return
        self._started = self._wanted
        path, frame, fps = self._wanted
        worker = StillWorker(path, frame, fps, self.grab_fn)
        worker.loaded.connect(self._loaded)
        worker.ended.connect(self._ended)
        self._worker = worker
        worker.start()

    def _loaded(self, path: str, frame: int, array) -> None:
        if self._wanted is None:
            return                                   # cancelled meanwhile
        height, width = array.shape[0], array.shape[1]
        data = array.tobytes()                       # must stay alive until after copy()
        self.ready.emit(path, frame, QtGui.QImage(data, width, height, width * 3, QtGui.QImage.Format.Format_RGB888).copy())

    def _ended(self, worker) -> None:
        keep = self._worker
        self._worker = None
        if keep is not None and keep.isRunning():
            keep.wait(2000)
        self._next()                                 # a newer request came in while the picture was being read

    def shutdown(self) -> None:
        """Before the program ends: a thread that is still running would crash it."""
        self._wanted = None
        if self._worker is not None:
            self._worker.wait(5000)
