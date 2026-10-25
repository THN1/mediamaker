"""Helper programs outside of MediaMaker (VLC, Avidemux): started in the background, the main window stays usable."""
from __future__ import annotations

import subprocess
from typing import Callable

from PySide6 import QtCore


def run_external(cmd: list) -> tuple:
    """Runs the program and waits for it to end. Returns (return code, error text); the error text is empty on success. A program that
    does not exist or cannot be started gives return code -1 and the reason."""
    try:
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except OSError as e:
        return -1, str(e)
    return res.returncode, res.stderr.decode(errors="replace")[-300:] if res.returncode else ""


class ExternalWorker(QtCore.QThread):
    """Runs a program in a thread; `completed(return code, error text)` arrives in the Qt thread when the program has ended."""

    completed = QtCore.Signal(int, str)

    def __init__(self, cmd: list, run_fn: Callable[[list], tuple] = run_external):
        super().__init__()
        self.cmd, self.run_fn = cmd, run_fn

    def run(self) -> None:
        self.completed.emit(*self.run_fn(self.cmd))


class BackgroundWorker(QtCore.QThread):
    """Runs a function in a thread; `finished_with(result)` arrives in the Qt thread (the result is the exception if the function raised one)."""

    finished_with = QtCore.Signal(object)

    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as e:                                       # reported to the caller, not lost in the thread
            result = e
        self.finished_with.emit(result)
