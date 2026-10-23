"""Filters known, harmless messages out of the program's error output (stderr).

Some libraries write directly to the error output, without Python or Qt being able to influence it; one
example is the VDPAU library, which on computers without an NVIDIA card reports "Failed to open VDPAU backend libvdpau_nvidia.so"
even though VLC then uses another video output. For this the filter replaces the error output (file number 2)
by a pipe, reads it line by line and passes on all lines that contain none of the patterns.
Programs started by MediaMaker also write through the filter.
"""
from __future__ import annotations

import atexit
import faulthandler
import os
import threading
from typing import Iterable

DEFAULT_PATTERNS = (
    "Failed to open VDPAU backend",
    # Qt on Wayland: harmless warning when a menu of the menu bar is clicked a second time
    "This plugin supports grabbing the mouse only for popup windows",
    # KDE file dialog (KIO): warning of its directory model when a file in a watched folder disappears again, e.g. temporary
    # files of the TV receiver on the network drive or MediaMaker's own temporary files. Harmless.
    "kf.kio.widgets.kdirmodel: No node found for item",
    # KDE job tracker at the end of the program (the file dialog of the desktop had a job on a network drive that never ended). Harmless.
    "kf.jobwidgets: Cannot register a job with KUiServerV2JobTracker",
    "KUiServerV2JobTracker instance contains",
)


class StderrFilter:
    def __init__(self, patterns: Iterable[str]):
        self.patterns = [p.encode("utf-8") for p in patterns if p]
        self._orig = os.dup(2)                    # original error output, everything wanted goes here
        self._restore = os.dup(2)                 # second copy, to reset the output at the end
        read_end, write_end = os.pipe()
        self._read = read_end
        os.dup2(write_end, 2)
        os.close(write_end)
        # crash messages from Python (faulthandler) should bypass the pipe and be printed immediately
        self._fault_file = os.fdopen(os.dup(self._orig), "w")
        faulthandler.enable(file=self._fault_file)
        self._closed = False
        self._thread = threading.Thread(target=self._pump, name="stderr-filter", daemon=True)
        self._thread.start()

    def _wanted(self, line: bytes) -> bool:
        return not any(p in line for p in self.patterns)

    def _pump(self) -> None:
        buf = b""
        while True:
            try:
                chunk = os.read(self._read, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            *lines, buf = buf.split(b"\n")
            out = b"".join(line + b"\n" for line in lines if self._wanted(line))
            if out:
                os.write(self._orig, out)
        if buf and self._wanted(buf):
            os.write(self._orig, buf)
        os.close(self._read)

    def close(self) -> None:
        """Restores the original error output and prints what is left. Calling it several times is harmless."""
        if self._closed:
            return
        self._closed = True
        os.dup2(self._restore, 2)                 # closes the write end of the pipe -> the read function ends
        self._thread.join(timeout=2)
        faulthandler.disable()
        self._fault_file.close()
        os.close(self._orig)
        os.close(self._restore)


def install(extra_patterns: Iterable[str] = ()) -> StderrFilter:
    f = StderrFilter(list(DEFAULT_PATTERNS) + list(extra_patterns))
    atexit.register(f.close)
    return f
