"""Runs ffmpeg for a job in the background (VB6: SaveVideo, SP_ExecuteAndWait, track)."""
from __future__ import annotations

from PySide6 import QtCore

from runner import run_ffmpeg


class RenderWorker(QtCore.QThread):
    """Starts ffmpeg, reports the progress and the result; cancel() ends ffmpeg."""

    progress = QtCore.Signal(object)                # progress.Progress
    done = QtCore.Signal(object)                    # runner.RunResult
    failed = QtCore.Signal(str)

    def __init__(self, command: list, total: float, cwd: str, run_fn=run_ffmpeg):
        super().__init__()
        self.command, self.total, self.cwd, self.run_fn = command, total, cwd, run_fn
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def run(self) -> None:
        try:
            result = self.run_fn(self.command, self.total, self.progress.emit, cwd=self.cwd, cancel=lambda: self.cancelled)
        except Exception as e:                       # ffmpeg missing, cannot be started ...
            self.failed.emit(f"{type(e).__name__}: {e}")
            return
        self.done.emit(result)
