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
