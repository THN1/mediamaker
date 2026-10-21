"""Datenmodell (Schnittliste, Profil, Optionen) und Import der Batch-Kopfzeilen.

Die VB6-Version speichert in der .bat/.sh-Datei als Kommentar (REM bzw. #):
  J=  Ausgabedatei (Klartext)
  P=  Profil    (Base64, UTF-16LE, Form: key="value" key="value" ...)
  T=  Optionen  (Base64, UTF-16LE, gleiche Form)
  C=  Schnittliste als CSV (Base64, UTF-16LE), eine Zeile pro Segment
"""
from __future__ import annotations

import base64
import csv
import glob
import io
import os
import re
import shlex
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

from mediaprobe import KNOWN_FPS


def snap_fps(text: str) -> Fraction:
    """'29.970' -> 30000/1001, '25.000' -> 25 (exakte Bruchwerte statt gerundeter Dezimalzahlen)."""
    f = Fraction(text.strip().replace(",", "."))
    for k in KNOWN_FPS:
        if abs(f - k) < Fraction(1, 500):
            return k
    return f


@dataclass
class Segment:
    index: int                  # 1-basiert wie in der VB6-Liste
    path: str                   # Quelldatei (so wie gespeichert, ggf. Windows-Pfad)
    name: str
    start: int                  # erster Frame (inklusive)
    end: int                    # Endframe; end-start Frames werden übernommen
    total_frames: int           # Bildnummer hinter dem letzten Videobild (= first_frame + Anzahl der Bilder)
    fps: Fraction
    width: int
    height: int
    vbitrate_kbit: int
    abitrate_kbit: int
    audio_sel: str              # Streamauswahl für Audio, z. B. "a"
    crop_top: int
    crop_bottom: int
    crop_left: int
    crop_right: int
    sample_rate: int
    mask: str = ""              # Base64-PNG (removelogo) oder "x y w h" als Bruchteile (delogo)
    first_frame: int = 0        # Nummer des ersten Videobildes der Datei (Zählung ab Containerbeginn; 0 bei alten Listen)

    @property
    def frames(self) -> int:
        return self.end - self.start

    @property
    def has_png_mask(self) -> bool:
        return self.mask.startswith("i")      # wie isPNG() in VB6

    @property
    def has_delogo(self) -> bool:
        return bool(self.mask) and not self.has_png_mask


def parse_kv(text: str) -> dict[str, str]:
    """key="value" key2="value2" ... -> dict"""
    return dict(re.findall(r'(\w+)="([^"]*)"', text))


def _decode(b64: str) -> str:
    return base64.b64decode(b64).decode("utf-16le")


def parse_segments(csv_text: str) -> list[Segment]:
    segs = []
    for row in csv.reader(io.StringIO(csv_text)):
        if len(row) < 18:
            continue
        r = row + [""] * (19 - len(row))
        segs.append(Segment(
            index=int(r[0]), path=r[1], name=r[2], start=int(r[3]), end=int(r[4]),
            total_frames=int(r[6]), fps=snap_fps(r[7]), width=int(r[8]), height=int(r[9]),
            vbitrate_kbit=int(r[10] or 0), abitrate_kbit=int(r[11] or 0), audio_sel=r[12],
            crop_top=int(r[13] or 0), crop_bottom=int(r[14] or 0),
            crop_left=int(r[15] or 0), crop_right=int(r[16] or 0),
            sample_rate=int(r[17] or 0), mask=r[18]))
    return segs


@dataclass
class Job:
    output: str
    profile: dict[str, str]
    options: dict[str, str]
    segments: list[Segment] = field(default_factory=list)


def parse_batch_header(text: str) -> Job:
    """Liest J/P/T/C aus einer .bat (REM ...) oder .sh (# ...) Datei von MediaMaker."""
    parts = {"P": "", "T": "", "C": ""}
    output = ""
    for line in text.splitlines():
        m = re.match(r"^(?:#|REM)\s+([JPTC])=(.*)$", line.strip(), re.IGNORECASE)
        if not m:
            continue
        key, val = m.group(1).upper(), m.group(2).strip()
        if key == "J":
            output = val
        else:
            parts[key] += val
    return Job(output=output,
               profile=parse_kv(_decode(parts["P"])) if parts["P"] else {},
               options=parse_kv(_decode(parts["T"])) if parts["T"] else {},
               segments=parse_segments(_decode(parts["C"])) if parts["C"] else [])


# ----------------------------------------------------------------------------- ffmpeg-Aufruf in der Batchdatei
def extract_command(text: str) -> Optional[str]:
    """Die Zeile der .bat/.sh, die ffmpeg mit dem Filtergraphen aufruft (nicht die Kommentarzeilen)."""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.upper().startswith("REM ") and " -filter_complex " in s:
            return s
    return None


def split_args(line: str) -> list[str]:
    """Zerlegt die Kommandozeile in Argumente (bash- oder Windows-Schreibweise)."""
    if re.search(r"[A-Za-z]:\\", line):                    # Windows-Pfade: Backslashes nicht als Escape behandeln
        return [t[1:-1] if len(t) > 1 and t[0] == t[-1] == '"' else t for t in shlex.split(line, posix=False)]
    return shlex.split(line)


def input_paths(args: list[str]) -> list[str]:
    return [args[i + 1] for i, a in enumerate(args[:-1]) if a == "-i"]


def metadata_input(args: list[str]) -> tuple[Optional[str], int]:
    """(Pfad der Kapitel-Metadatendatei oder None, Anzahl der Schnitt-Quellen)."""
    paths = input_paths(args)
    if "-map_metadata" in args:
        n = int(args[args.index("-map_metadata") + 1])
        return paths[n], n
    return None, len(paths)


def resolve_source(path: str) -> str:
    """Liefert den Pfad einer Quelldatei; findet sie auch, wenn sich ein KDE-kio-fuse-Verzeichnis geändert hat.

    Unter KDE lauten Netzwerkfreigaben etwa /run/user/1000/kio-fuse-sFijsz/smb/... ; der Teil hinter "kio-fuse-"
    ist zufällig und ändert sich mit jeder Sitzung. Existiert der Pfad nicht, wird mit beliebigem Zufallsteil gesucht
    (bei mehreren Treffern gilt das zuletzt geänderte Verzeichnis). Nichts gefunden: der Pfad bleibt unverändert.
    """
    if os.path.exists(path):
        return path
    m = re.search(r"/kio-fuse-[^/]+", path)
    if m:
        pattern = glob.escape(path[:m.start()]) + "/kio-fuse-*" + glob.escape(path[m.end():])
        found = sorted(glob.glob(pattern), key=os.path.getmtime)
        if found:
            return found[-1]
    return path
