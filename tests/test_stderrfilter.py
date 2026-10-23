"""Test of stderrfilter.py in a process of its own (the filter replaces the error output of the process)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = r'''
import os, sys
sys.path.insert(0, {root!r})
from stderrfilter import install
f = install(["extra"])
os.write(2, b"Failed to open VDPAU backend libvdpau_nvidia.so: cannot open shared object file\n")
print("normal message", file=sys.stderr)
os.write(2, b"an extra pattern: extra in the text\n")
os.write(2, b"second normal line\n")
os.write(2, b"Failed to open VDPAU backend again\n")
for i in range(20000):
    os.write(2, b"Failed to open VDPAU backend %d\n" % i if i % 2 else b"line %d\n" % i)
os.write(2, b"last line without line end")
f.close()
'''


def main():
    res = subprocess.run([sys.executable, "-c", SCRIPT.format(root=ROOT)], capture_output=True, timeout=60)
    lines = res.stderr.decode().split("\n")
    expected = ["normal message", "second normal line"] + [f"line {i}" for i in range(0, 20000, 2)]
    ok = lines[:-1] == expected + [] and lines[-1].endswith("last line without line end")
    ok = ok or (lines[:len(expected)] == expected and lines[len(expected)] == "last line without line end")
    if res.returncode != 0 or not ok or b"VDPAU" in res.stderr or b"extra" in res.stderr:
        print("ERROR: output differs; start:", lines[:5], "end:", lines[-3:], "code", res.returncode)
        sys.exit(1)
    print(f"Error output filter: OK ({len(expected)} lines passed on, 10003 lines with VDPAU/extra removed, remainder without line end kept)")


if __name__ == "__main__":
    main()


def test_default_patterns():
    """The messages of the KDE file dialog and of Qt on Wayland are among the filtered ones."""
    sys.path.insert(0, ROOT)
    from stderrfilter import DEFAULT_PATTERNS
    for line in ('kf.kio.widgets.kdirmodel: No node found for item that was just removed: QUrl("file:///a/b.ts")',
                 "kf.kio.widgets.kdirmodel: No node found for item that was just added: QUrl()",
                 "kf.jobwidgets: Cannot register a job with KUiServerV2JobTracker without QGuiApplication::desktopFileName",
                 "A KUiServerV2JobTracker instance contains 1 stalled jobs",
                 "This plugin supports grabbing the mouse only for popup windows",
                 "Failed to open VDPAU backend libvdpau_nvidia.so: cannot open shared object file"):
        assert any(p in line for p in DEFAULT_PATTERNS), line
    assert not any(p in "kf.kio.widgets.kdirmodel: something else entirely" for p in DEFAULT_PATTERNS)
    print("Default patterns: OK (KDE file dialog, Wayland, VDPAU)")


test_default_patterns()
