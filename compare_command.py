"""Compares the ffmpeg call of a MediaMaker batch file (.bat/.sh) with the one produced by the Python building blocks.

Usage:  python3 compare_command.py JOB.sh

The segment list, the profile and the options are read from the comment lines (J=, P=, T=, C=) and the
call is rebuilt from them (the VB6 way, so that it is comparable character by character). The source paths are taken
from the call in the batch file. Time values may differ by 1 ms (VB6 calculates with floating point numbers).
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
        sys.exit("No segment list (C=) or no ffmpeg call found in the file.")
    ref = split_args(line)
    meta, n = metadata_input(ref)
    sources = input_paths(ref)[:n]
    if len(sources) != len(job.segments):
        sys.exit(f"Number of input files in the call ({len(sources)}) and segments in the list ({len(job.segments)}) do not match.")
    mapping = {seg.path: sources[i] for i, seg in enumerate(job.segments)}
    job.output = ref[-1]
    try:
        mine = build_command(job, ffmpeg=ref[0], chapters_file=meta, path_map=lambda p: mapping[p], stream_times=None)
    except NotImplementedError as e:
        sys.exit(f"Not implemented yet: {e}")
    print(f"Segments: {len(job.segments)} | Profile: {job.profile.get('description', '?')} | "
          f"crop={job.options.get('crop')} pad={job.options.get('pad')} floor={job.options.get('floor')}")
    diffs = []
    if len(mine) != len(ref):
        print(f"DIFFERENCE: number of arguments: Python {len(mine)}, batch file {len(ref)}")
        diffs.append("count")
    for i, (m, r) in enumerate(zip(mine, ref)):
        if m != r:
            diffs.append(i)
            if same(m, r):
                for x, y in zip(NUM.findall(m), NUM.findall(r)):
                    if x != y:
                        print(f"  time value differs by 1 ms (floating point noise in VB6): batch file {y} -> Python {x}")
            else:
                print(f"DIFFERENCE at argument {i}:\n  batch file: {r}\n  Python    : {m}")
    hard = [d for d in diffs if d == "count" or not same(mine[d], ref[d])]
    print("Result:", "Call matches." if not hard else f"{len(hard)} difference(s).")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
