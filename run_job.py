"""Führt einen Schnittauftrag aus einer MediaMaker-Batchdatei (.bat/.sh) aus, mit Fortschritt und Restzeit.

Aufruf:  python3 run_job.py JOB.sh [--source-dir ORDNER] [--output AUSGABE.mp4]
Die Schnittliste, das Profil und die Optionen werden aus den Kommentarzeilen (J=, P=, T=, C=) gelesen.
Ohne --source-dir werden die Quellpfade aus dem ffmpeg-Aufruf der Batchdatei übernommen (sie müssen auf diesem
Rechner existieren); mit --source-dir werden die Quelldateien im ORDNER über ihren Dateinamen gesucht.
"""
import argparse
import os
import sys
import tempfile

from cutlist import extract_command, input_paths, metadata_input, parse_batch_header, resolve_source, split_args
from ffmpeg_cmd import build_command, write_masks
from progress import format_progress
from runner import expected_frames, run_ffmpeg, total_seconds, verify_output


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job")
    ap.add_argument("--source-dir")
    ap.add_argument("--output")
    ap.add_argument("--origin", default="container", choices=["container", "video", "vb6"])
    ap.add_argument("--overwrite", action="store_true", help="vorhandene Ausgabedatei überschreiben")
    args = ap.parse_args()

    text = open(args.job, encoding="latin-1").read()
    job = parse_batch_header(text)
    if not job.segments:
        sys.exit("Keine Schnittliste (C=) in der Datei gefunden.")
    if args.output:
        job.output = args.output
    chapters = None
    if args.source_dir:
        find = lambda p: os.path.join(args.source_dir, os.path.basename(p.replace("\\", "/")))
    else:
        line = extract_command(text)
        if not line:
            sys.exit("Kein ffmpeg-Aufruf in der Datei gefunden; bitte --source-dir angeben.")
        ref = split_args(line)
        meta, n = metadata_input(ref)
        chapters = meta if meta and os.path.exists(meta) else None
        sources = input_paths(ref)[:n]
        if len(sources) != len(job.segments):
            sys.exit("Eingabedateien im Aufruf und Segmente der Liste passen nicht zusammen; bitte --source-dir angeben.")
        table = {seg.path: sources[i] for i, seg in enumerate(job.segments)}
        find = lambda p: resolve_source(table[p])
        if not args.output:
            job.output = ref[-1]
    job.output = os.path.abspath(job.output)
    missing = [find(s.path) for s in job.segments if not os.path.exists(find(s.path))]
    if missing:
        hint = ("\nHinweis: Das Verzeichnis kio-fuse-... ändert sich mit jeder Sitzung; die Freigabe muss außerdem "
                "eingebunden sein (z. B. in Dolphin geöffnet). Alternativ mit --source-dir den aktuellen Ordner angeben."
                if not args.source_dir else "")
        sys.exit("Quelldatei nicht gefunden: " + ", ".join(sorted(set(missing))) + hint)
    if os.path.exists(job.output) and not args.overwrite:
        sys.exit(f"Die Ausgabedatei existiert bereits: {job.output}\n"
                 "Mit --output eine andere Datei wählen (oder --overwrite, wenn sie überschrieben werden darf).")

    with tempfile.TemporaryDirectory() as work:
        write_masks(job.segments, work)                        # removelogoNN.png für ffmpeg
        cmd = build_command(job, chapters_file=chapters, path_map=lambda p: os.path.abspath(find(p)), origin=args.origin)
        last = [""]

        def show(p):
            line = format_progress(p)
            print("\r" + line + " " * max(0, len(last[0]) - len(line)), end="", flush=True)
            last[0] = line

        print(f"{len(job.segments)} Segment(e), Ausgabe {total_seconds(job):.1f} s -> {job.output}")
        res = run_ffmpeg(cmd, total_seconds(job), show, cwd=work)
    print()
    if not res.ok:
        sys.exit(f"ffmpeg meldet einen Fehler (Code {res.returncode}):\n{res.errors}")
    ok, actual, msg = verify_output(job.output, expected_frames(job))
    print(f"Fertig in {res.elapsed:.0f} s. {msg}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
