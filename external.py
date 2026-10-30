"""Helper programs outside of MediaMaker (VLC, Avidemux): started in the background, the main window stays usable."""
from __future__ import annotations

import shlex
import shutil
import subprocess
from typing import Callable, Optional

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


TERMINALS = (("konsole", ["-e"]), ("gnome-terminal", ["--"]), ("xfce4-terminal", ["-x"]), ("mate-terminal", ["-x"]), ("lxterminal", ["-e"]),
             ("kitty", []), ("alacritty", ["-e"]), ("xterm", ["-e"]))


def terminal_command(script: str, custom: str = "", which: Callable = shutil.which) -> Optional[list]:
    """The command that runs a shell script in a window of its own (a terminal program): the first one of TERMINALS that is installed, or the command of the option
    `terminal` (e.g. "konsole --separate -e"; the script is appended). The window stays open after the script has ended until Enter is pressed, so the result can be read.
    None if there is no terminal program."""
    wrapper = f"bash {shlex.quote(script)}; echo; read -r -p 'Finished. Press Enter to close this window. ' _"
    if custom.strip():
        return shlex.split(custom) + ["bash", "-c", wrapper]
    for name, args in TERMINALS:
        if which(name):
            return [name, *args, "bash", "-c", wrapper]
    return None
