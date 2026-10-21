"""Vergleicht den ffmpeg-Aufruf einer MediaMaker-Batchdatei (.bat/.sh) mit dem, den die Python-Bausteine erzeugen.

Aufruf:  python3 compare_command.py JOB.sh

Die Schnittliste, das Profil und die Optionen werden aus den Kommentarzeilen (J=, P=, T=, C=) gelesen und daraus der
Aufruf neu gebaut (im VB6-Verfahren, damit er Zeichen für Zeichen vergleichbar ist). Die Quellpfade werden aus dem
Aufruf der Batchdatei übernommen. Zeitwerte dürfen um 1 ms abweichen (VB6 rechnet mit Gleitkommazahlen).
"""
import re
import sys

from cutlist import extract_command, input_paths, metadata_input, parse_batch_header, split_args
from ffmpeg_cmd import build_command

NUM = re.compile(r"\d+\.\d{3}")


def same(a: str, b: str, tol: float = 0.0015) -> bool:
    if NUM.sub("#", a) != NUM.sub("#", b):
        return False
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(NUM.findall(a), NUM.findall(b)))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    text = open(sys.argv[1], encoding="latin-1").read()
    job = parse_batch_header(text)
    line = extract_command(text)
    if not line or not job.segments:
        sys.exit("Keine Schnittliste (C=) oder kein ffmpeg-Aufruf in der Datei gefunden.")
    ref = split_args(line)
    meta, n = metadata_input(ref)
    sources = input_paths(ref)[:n]
    if len(sources) != len(job.segments):
        sys.exit(f"Anzahl der Eingabedateien im Aufruf ({len(sources)}) und Segmente in der Liste ({len(job.segments)}) passt nicht.")
    mapping = {seg.path: sources[i] for i, seg in enumerate(job.segments)}
    job.output = ref[-1]
    try:
        mine = build_command(job, ffmpeg=ref[0], chapters_file=meta, path_map=lambda p: mapping[p], stream_times=None)
    except NotImplementedError as e:
        sys.exit(f"Noch nicht umgesetzt: {e}")
    print(f"Segmente: {len(job.segments)} | Profil: {job.profile.get('description', '?')} | "
          f"crop={job.options.get('crop')} pad={job.options.get('pad')} floor={job.options.get('floor')}")
    diffs = []
    if len(mine) != len(ref):
        print(f"UNTERSCHIED: Anzahl der Argumente: Python {len(mine)}, Batchdatei {len(ref)}")
        diffs.append("anzahl")
    for i, (m, r) in enumerate(zip(mine, ref)):
        if m != r:
            diffs.append(i)
            if same(m, r):
                for x, y in zip(NUM.findall(m), NUM.findall(r)):
                    if x != y:
                        print(f"  Zeitwert mit 1 ms Unterschied (Gleitkomma-Rauschen in VB6): Batchdatei {y} -> Python {x}")
            else:
                print(f"UNTERSCHIED bei Argument {i}:\n  Batchdatei: {r}\n  Python    : {m}")
    hard = [d for d in diffs if d == "anzahl" or not same(mine[d], ref[d])]
    print("Ergebnis:", "Aufruf stimmt überein." if not hard else f"{len(hard)} Unterschied(e).")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
