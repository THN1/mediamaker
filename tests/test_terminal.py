"""Tests that the program leaves the terminal as it found it.

ffmpeg switches the terminal it inherits as standard input to a mode without echo. Several ffmpeg processes running at the same
time restore the terminal in the wrong order, so after quitting MediaMaker the console no longer showed the typed characters.
All external programs are therefore started with their standard input disconnected from the terminal (stdin=subprocess.DEVNULL).

(1) static: every call of subprocess.run/Popen/... in the program sources passes stdin=
(2) dynamic: several threads grab frames at the same time in a process that has a (pseudo) terminal as its console;
    afterwards ECHO and ICANON must still be set (Linux only)

Usage:  python3 tests/test_terminal.py
"""
import ast
import glob
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALLS = {"run", "Popen", "check_output", "check_call", "call"}


def static_check() -> list:
    missing = []
    files = [f for pattern in ("*.py", "tools/*.py", "ui/*.py") for f in glob.glob(os.path.join(ROOT, pattern))]
    for path in sorted(files):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in CALLS
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
                    and not any(k.arg == "stdin" for k in node.keywords)):
                missing.append(f"{os.path.relpath(path, ROOT)}:{node.lineno}")
    return missing


WORKER = r'''
import sys, threading
sys.path.insert(0, {root!r})
from fractions import Fraction
from frames import grab_frame
from mediaprobe import probe
def work(n):
    grab_frame({video!r}, n, Fraction(25))
    probe({video!r}, exact_frames=False)
threads = [threading.Thread(target=work, args=(5 + 3 * i,)) for i in range(8)]
[t.start() for t in threads]
[t.join() for t in threads]
'''


def dynamic_check() -> str:
    import pty
    import termios
    import time
    with tempfile.TemporaryDirectory() as tmp:
        video = os.path.join(tmp, "terminal_test.ts")
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=4", "-f", "lavfi",
                        "-i", "sine=frequency=440:sample_rate=48000:duration=4", "-c:v", "libx264", "-g", "12", "-c:a", "mp2",
                        "-shortest", "-f", "mpegts", video], check=True, stdin=subprocess.DEVNULL)
        pid, fd = pty.fork()
        if pid == 0:
            os.execvp(sys.executable, [sys.executable, "-c", WORKER.format(root=ROOT, video=video)])
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                os.read(fd, 4096)
            except OSError:
                break
        _, status = os.waitpid(pid, 0)
        flags = termios.tcgetattr(fd)[3]
        if os.waitstatus_to_exitcode(status) != 0:
            return "the test process failed"
        if not flags & termios.ECHO or not flags & termios.ICANON:
            return f"terminal changed: ECHO={bool(flags & termios.ECHO)}, ICANON={bool(flags & termios.ICANON)}"
    return ""


def main():
    missing = static_check()
    assert not missing, "subprocess calls without stdin=: " + ", ".join(missing)
    print("Static check: OK (every subprocess call passes stdin=)")
    if sys.platform.startswith("linux"):
        problem = dynamic_check()
        assert not problem, problem
        print("Terminal state: OK (echo and line mode are still on after concurrent ffmpeg runs)")
    print("OK")


if __name__ == "__main__":
    main()
