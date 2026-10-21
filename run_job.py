"""Runs a cutting job from a MediaMaker batch file (.bat/.sh), with progress and remaining time.

Usage:  python3 run_job.py JOB.sh [--source-dir FOLDER] [--output OUTPUT.mp4]
The segment list, the profile and the options are read from the comment lines (J=, P=, T=, C=).
Without --source-dir the source paths are taken from the ffmpeg call of the batch file (they must exist on this
computer); with --source-dir the source files are searched in FOLDER by their file names.
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
    ap.add_argument("--overwrite", action="store_true", help="overwrite an existing output file")
    args = ap.parse_args()

    text = open(args.job, encoding="latin-1").read()
    job = parse_batch_header(text)
    if not job.segments:
        sys.exit("No segment list (C=) found in the file.")
    if args.output:
        job.output = args.output
    chapters = None
    if args.source_dir:
        find = lambda p: os.path.join(args.source_dir, os.path.basename(p.replace("\\", "/")))
    else:
        line = extract_command(text)
        if not line:
            sys.exit("No ffmpeg call found in the file; please give --source-dir.")
        ref = split_args(line)
        meta, n = metadata_input(ref)
        chapters = meta if meta and os.path.exists(meta) else None
        sources = input_paths(ref)[:n]
        if len(sources) != len(job.segments):
            sys.exit("Input files in the call and segments of the list do not match; please give --source-dir.")
        table = {seg.path: sources[i] for i, seg in enumerate(job.segments)}
        find = lambda p: resolve_source(table[p])
        if not args.output:
            job.output = ref[-1]
    job.output = os.path.abspath(job.output)
    missing = [find(s.path) for s in job.segments if not os.path.exists(find(s.path))]
    if missing:
        hint = ("\nNote: The directory kio-fuse-... changes with every session; the share must also be "
                "mounted (e.g. opened in Dolphin). Alternatively give the current folder with --source-dir."
                if not args.source_dir else "")
        sys.exit("Source file not found: " + ", ".join(sorted(set(missing))) + hint)
    if os.path.exists(job.output) and not args.overwrite:
        sys.exit(f"The output file already exists: {job.output}\n"
                 "Choose another file with --output (or --overwrite if it may be overwritten).")

    with tempfile.TemporaryDirectory() as work:
        write_masks(job.segments, work)                        # removelogoNN.png for ffmpeg
        cmd = build_command(job, chapters_file=chapters, path_map=lambda p: os.path.abspath(find(p)), origin=args.origin)
        last = [""]

        def show(p):
            line = format_progress(p)
            print("\r" + line + " " * max(0, len(last[0]) - len(line)), end="", flush=True)
            last[0] = line

        print(f"{len(job.segments)} segment(s), output {total_seconds(job):.1f} s -> {job.output}")
        res = run_ffmpeg(cmd, total_seconds(job), show, cwd=work)
    print()
    if not res.ok:
        sys.exit(f"ffmpeg reported an error (code {res.returncode}):\n{res.errors}")
    ok, actual, msg = verify_output(job.output, expected_frames(job))
    print(f"Done in {res.elapsed:.0f} s. {msg}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
