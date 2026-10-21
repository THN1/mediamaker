"""Cut accuracy: does a cut [start, end) land on the frames one expects?

Usage:  python3 tests/test_cut_accuracy.py "recording.ts" start end [origin]
origin = zero point of the frame numbers: video (default), container or vb6.
The cut is made once as in VB6 (-ss before -i, trim relative) and once with absolute timestamps.
The first/last frame of the produced MP4 is assigned to the source frames (similarity on reduced pictures).
Frame numbers in the output count from the video start.
"""
import math, os, subprocess, sys, tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import numpy as np
from cutlist import Job, Segment, parse_batch_header
from ffmpeg_cmd import build_command
from frames import frame_time, stream_times
from mediaprobe import probe

if len(sys.argv) < 4:
    sys.exit(__doc__)
SRC, START, END = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ORIGIN = sys.argv[4] if len(sys.argv) > 4 else "video"
info = probe(SRC).video
FPS = info.fps
times = stream_times(SRC)
ref_job = parse_batch_header(open(os.path.join(HERE, "sample_MediaMaker.sh"), encoding="latin-1").read())
profile = dict(ref_job.profile, scale=f"{info.width}:{info.height}", fps=f"{float(FPS):.3f}")

def decode(path):
    """All frames in decoding order, reduced to 180x144 greyscale."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0", "-vf", "scale=180:144,format=gray",
                        "-fps_mode", "passthrough", "-f", "rawvideo", "-"], capture_output=True)
    size = 180 * 144
    return [np.frombuffer(p.stdout[i:i + size], np.uint8).astype(np.int16) for i in range(0, len(p.stdout) - size + 1, size)]

src = decode(SRC)
OFF = round(info.first_frame_offset * FPS)       # frame number (from the video start) of the first decodable frame

def number(img):                                  # frame number from the video start
    return OFF + min(range(len(src)), key=lambda j: np.abs(img - src[j]).mean())

def expected(origin, n):                          # frame number from the video start that belongs to n at this zero point
    return math.ceil((frame_time(n, FPS, times, origin) - times[1]) * FPS - Fraction(1, 20))   # first frame from this point in time

def expected_range(origin):                       # end = start + length: as in VB6 the calculation starts at the start time
    first = expected(origin, START)
    return first, first + (END - 1 - START)

print(f"cut {START}..{END-1} ({END-START} frames) in {os.path.basename(SRC)}; zero point of the frame numbers: {ORIGIN}")
print("expected frames (numbers from the video start): " + ", ".join(
    f"{o}: {expected_range(o)[0]}..{expected_range(o)[1]}" for o in ("video", "container", "vb6")))
if expected_range(ORIGIN)[0] < OFF:
    print(f"Note: The start time lies before the first decodable frame (number {OFF}); the cut starts there.")
ok = True
for label, st in (("VB6 method (relative)      ", None), ("absolute timestamps        ", {SRC: times})):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "cut.mp4")
        seg = Segment(1, SRC, os.path.basename(SRC), START, END, info.frames, FPS, info.width, info.height,
                      0, 0, "a", 0, 0, 0, 0, 48000, "")
        res = subprocess.run(build_command(Job(out, profile, ref_job.options, [seg]), unify=True,
                                           stream_times=st, origin=ORIGIN), capture_output=True)
        assert res.returncode == 0, res.stderr.decode()[-500:]
        frames = decode(out)
        first, last = number(frames[0]), number(frames[-1])
        match = [o for o in ("video", "container", "vb6") if expected_range(o) == (first, last)]
        want = expected_range(ORIGIN)
        good = (first, last) == want and len(frames) == END - START or want[0] < OFF
        if st:
            ok &= good
        print(f"{label}: got {first}..{last} ({len(frames)} frames) -> corresponds to zero point: "
              f"{', '.join(match) or 'none'}" + ("  OK" if good else "  DEVIATION"))
sys.exit(0 if ok else 1)
