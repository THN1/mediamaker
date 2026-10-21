"""Checks how the ffmpeg version on this computer treats frame numbers with -ss (as in VB6).

Usage:  python3 check_seek.py "recording.ts" [frame_number ...]

For every frame number the picture is fetched
  - with the VB6 method:  -ss <seconds> before -i and trim relative to it (jump = round(n/fps) - 2 seconds)
  - and for comparison via absolute timestamps with the three possible zero points
    (video start, container start, VB6 pattern).
The output says which zero point the VB6 method corresponds to on this computer.
"""
import io
import subprocess
import sys

import numpy as np
from PIL import Image

from ffmpeg_cmd import fmt_seconds, split_seek
from frames import grab_frame, stream_times
from mediaprobe import probe


def grab_vb6(path, n, fps, preroll=2):
    seek, rest = split_seek(n, fps, preroll)
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(seek)] if seek > 0 else []) + ["-i", path, "-filter_complex",
           f"[0:v]trim={fmt_seconds(rest)},setpts=PTS-STARTPTS[v]", "-frames:v", "1", "-map", "[v]",
           "-f", "image2pipe", "-c:v", "png", "-"]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB")) if r.stdout else None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    v = probe(path).video
    fmt0, vid0 = stream_times(path)
    print(f"{path}: container start {float(fmt0):.3f} s, video start {float(vid0):.3f} s "
          f"(difference {float(vid0 - fmt0):.3f} s = {float((vid0 - fmt0) * v.fps):.1f} frames), {v.frames} frames")
    ns = [int(x) for x in sys.argv[2:]] or [20, 50, 80, 110, 140]
    counts = {}
    for n in ns:
        b = grab_vb6(path, n, v.fps)
        found = [o for o in ("video", "container") if b is not None and np.array_equal(b, grab_frame(path, n, v.fps, origin=o))]
        label = " and ".join({"video": "video start", "container": "container start"}[o] for o in found) or "neither"
        seek = split_seek(n, v.fps, 2)[0]
        print(f"  frame {n:6d} (jump {seek} s): VB6 method corresponds to zero point: {label}")
        counts[label] = counts.get(label, 0) + 1
    print("Summary:", ", ".join(f"{k}: {c}x" for k, c in counts.items()))
    print("Note: If 'video start' fails for small frame numbers and 'container start' for larger ones, VB6 works with\n"
          "the pattern origin=\"vb6\". 'neither' indicates a different -ss behaviour of the ffmpeg version.")


if __name__ == "__main__":
    main()
