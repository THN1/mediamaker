"""Test von stderrfilter.py in einem eigenen Prozess (das Filter ersetzt die Fehlerausgabe des Prozesses)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = r'''
import os, sys
sys.path.insert(0, {root!r})
from stderrfilter import install
f = install(["zusatz"])
os.write(2, b"Failed to open VDPAU backend libvdpau_nvidia.so: Kann die Shared-Object-Datei nicht oeffnen\n")
print("normale Meldung", file=sys.stderr)
os.write(2, b"ein Zusatzmuster: zusatz im Text\n")
os.write(2, b"zweite normale Zeile\n")
os.write(2, b"Failed to open VDPAU backend nochmal\n")
for i in range(20000):
    os.write(2, b"Failed to open VDPAU backend %d\n" % i if i % 2 else b"Zeile %d\n" % i)
os.write(2, b"letzte Zeile ohne Zeilenende")
f.close()
'''


def main():
    res = subprocess.run([sys.executable, "-c", SCRIPT.format(root=ROOT)], capture_output=True, timeout=60)
    lines = res.stderr.decode().split("\n")
    expected = ["normale Meldung", "zweite normale Zeile"] + [f"Zeile {i}" for i in range(0, 20000, 2)]
    ok = lines[:-1] == expected + [] and lines[-1].endswith("letzte Zeile ohne Zeilenende")
    ok = ok or (lines[:len(expected)] == expected and lines[len(expected)] == "letzte Zeile ohne Zeilenende")
    if res.returncode != 0 or not ok or b"VDPAU" in res.stderr or b"zusatz" in res.stderr:
        print("FEHLER: Ausgabe weicht ab; Anfang:", lines[:5], "Ende:", lines[-3:], "Code", res.returncode)
        sys.exit(1)
    print(f"Fehlerausgabe-Filter: OK ({len(expected)} Zeilen weitergegeben, 10003 Zeilen mit VDPAU/Zusatz entfernt, Rest ohne Zeilenende erhalten)")


if __name__ == "__main__":
    main()
