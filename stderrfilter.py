"""Filtert bekannte, harmlose Meldungen aus der Fehlerausgabe (stderr) des Programms heraus.

Manche Bibliotheken schreiben direkt auf die Fehlerausgabe, ohne dass Python oder Qt das beeinflussen können; ein
Beispiel ist die VDPAU-Bibliothek, die auf Rechnern ohne NVIDIA-Karte "Failed to open VDPAU backend libvdpau_nvidia.so"
meldet, obwohl VLC danach eine andere Bildausgabe nimmt. Das Filter ersetzt dafür die Fehlerausgabe (Dateinummer 2)
durch eine Leitung, liest sie zeilenweise und gibt alle Zeilen weiter, die keines der Muster enthalten.
Auch Programme, die MediaMaker startet, schreiben durch das Filter.
"""
from __future__ import annotations

import atexit
import faulthandler
import os
import threading
from typing import Iterable

DEFAULT_PATTERNS = (
    "Failed to open VDPAU backend",
    # Qt unter Wayland: harmlose Warnung, wenn ein Menü der Menüleiste ein zweites Mal angeklickt wird
    "This plugin supports grabbing the mouse only for popup windows",
)


class StderrFilter:
    def __init__(self, patterns: Iterable[str]):
        self.patterns = [p.encode("utf-8") for p in patterns if p]
        self._orig = os.dup(2)                    # ursprüngliche Fehlerausgabe, hierhin geht alles Gewollte
        self._restore = os.dup(2)                 # zweite Kopie, um die Ausgabe am Ende zurückzusetzen
        read_end, write_end = os.pipe()
        self._read = read_end
        os.dup2(write_end, 2)
        os.close(write_end)
        # Absturzmeldungen von Python (faulthandler) sollen die Leitung umgehen und sofort ausgegeben werden
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
        """Stellt die ursprüngliche Fehlerausgabe wieder her und gibt Reste aus. Mehrfacher Aufruf ist harmlos."""
        if self._closed:
            return
        self._closed = True
        os.dup2(self._restore, 2)                 # schließt das Schreibende der Leitung -> die Lesefunktion endet
        self._thread.join(timeout=2)
        faulthandler.disable()
        self._fault_file.close()
        os.close(self._orig)
        os.close(self._restore)


def install(extra_patterns: Iterable[str] = ()) -> StderrFilter:
    f = StderrFilter(list(DEFAULT_PATTERNS) + list(extra_patterns))
    atexit.register(f.close)
    return f
