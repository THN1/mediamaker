"""Suche nach dem Ende bzw. dem Beginn einer Werbung (VB6: mnuEnd_Click / mnuNext_Click mit where_border / where_logo).

Die Suche beginnt mit einer festen Schrittweite (1000 Bilder für "Ende der Werbung", 6000 für "nächste Werbung") und verfeinert
sie jeweils um den Faktor 10, bis sie 1 erreicht. Sie läuft im Hintergrund und lässt sich abbrechen.
"""
from __future__ import annotations

from typing import Callable

from PySide6 import QtCore

from border import border_at, where_border
from logo import bottom_line_average, confidence_at, rewind, where_logo
from player import debug_log

DEFAULT_STEP_END_S = 40              # Schrittweite für "Seek end of commercial" in Sekunden (VB6: 1000 Bilder bei 25 FPS)
DEFAULT_STEP_NEXT_S = 240            # Schrittweite für "Seek next commercial" in Sekunden (VB6: 6000 Bilder bei 25 FPS)


def step_frames(seconds, fps) -> int:
    """Schrittweite in Bildern aus Sekunden und Bildrate (mindestens 1)."""
    return max(1, round(float(seconds) * float(fps)))


class SeekCancelled(Exception):
    pass


def seek_border(path, fps, total, pos, value, equal, stepping, opts, border_fn=border_at, cancel=lambda: False,
                shown=lambda n: n) -> int:
    """Sucht ab Bild `pos` das erste Bild, dessen schwarzer Rand zu `value` passt (equal=True: Film beginnt) bzw. davon
    abweicht (equal=False: Werbung beginnt). `shown` rechnet Bildnummern für die Anzeige um; jede Probe wird im Wartefenster
    (cancel.note) und im Protokoll gemeldet."""
    note = getattr(cancel, "note", None)
    debug_log(f"Randsuche ab Bild {shown(pos)}: gesucht {'Rand ungefähr' if equal else 'Rand abweichend von'} {value} "
              f"(Toleranz {int(opts.get('border_tol', 3))}), Schrittweite {stepping}, Ende bei {shown(total)}")

    def border_of(n: int) -> int:
        if cancel():
            raise SeekCancelled()
        found = border_fn(path, n, fps, opts)
        text = f"frame {shown(n)}: border {found} (looking for {'about ' if equal else 'not '}{value})"
        debug_log(f"Randsuche: {text}")
        if note:
            note(text)
        return found
    tolerance = int(opts.get("border_tol", 3))
    result = where_border(border_of, pos, total, value, equal, stepping, lim=tolerance)
    debug_log(f"Randsuche: Ergebnis Bild {shown(result)}")
    return result


def seek_logo(path, fps, total, pos, ref, equal, stepping, opts, conf_fn=confidence_at, avg_fn=bottom_line_average,
              cancel=lambda: False, shown=lambda n: n) -> int:
    """Wie seek_border, aber mit dem Senderlogo: equal=True sucht das nächste Bild MIT Logo und geht dann ein Stück zurück
    (das Logo erscheint oft erst einige Sekunden nach Beginn des Films), equal=False das nächste Bild OHNE Logo."""
    def check() -> None:
        if cancel():
            raise SeekCancelled()

    note = getattr(cancel, "note", None)
    debug_log(f"Logosuche ab Bild {shown(pos)}: gesucht {'Logo vorhanden' if equal else 'Logo fehlt'}, Schrittweite {stepping}")

    def conf_of(n: int) -> float:
        check()
        found = conf_fn(path, n, fps, ref, opts)
        text = f"frame {shown(n)}: logo confidence {found:.2f}"
        debug_log(f"Logosuche: {text}")
        if note:
            note(text)
        return found

    max_back = round(float(opts.get("logo_rewind", 1.8)) * float(fps))
    min_conf = float(opts.get("logo_conf", 0.2))

    def rewind_fn(p: int) -> int:
        return rewind(p, lambda f: (check(), avg_fn(path, f, fps, opts))[1], max_back)

    result = where_logo(conf_of, pos, total, equal, stepping, rewind_fn, min_conf)
    debug_log(f"Logosuche: Ergebnis Bild {shown(result)}")
    return result


class SeekWorker(QtCore.QThread):
    """Führt eine Suche im Hintergrund aus."""

    done = QtCore.Signal(int)                       # gefundenes Bild
    failed = QtCore.Signal(str)
    progress = QtCore.Signal(str)                   # Zwischenstand für das Wartefenster

    def __init__(self, job: Callable[[Callable[[], bool]], int]):
        super().__init__()
        self.job = job
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def note(self, text: str) -> None:
        self.progress.emit(text)

    def run(self) -> None:
        worker = self

        class Control:                              # abfragbar wie eine Funktion (abgebrochen?) und mit .note für Meldungen
            def __call__(self) -> bool:
                return worker.cancelled

            def note(self, text: str) -> None:
                worker.note(text)
        try:
            result = self.job(Control())
        except SeekCancelled:
            return
        except Exception as e:                      # z. B. Datei nicht lesbar
            if not self.cancelled:
                self.failed.emit(str(e))
            return
        if not self.cancelled:
            self.done.emit(int(result))
