"""Checks step by step what the timeline does for a file, and shows times and errors.

Usage:  python3 tools/thumb_test.py FILE [first_frame] [count]     (default: frame 0, 10 frames)

Meant for files on a network drive for which the timeline shows no thumbnails. The output shows
which step fails or how long it takes:
  1. quick analysis (ffprobe: streams, duration)
  2. start times (ffprobe: start of the container and of the video)
  3. the thumbnails (ffmpeg) with their frame numbers
"""
import os
import sys
import time
import traceback
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ffmpeg_cmd import stream_times_of
from frames import grab_numbered
from mediaprobe import probe


def step(name):
    print(f"\n--- {name}")
    return time.monotonic()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    print("File:", path, "| exists:", os.path.exists(path))
    try:
        t = step("1. quick analysis")
        info = probe(path, exact_frames=False)
        v = info.video
        print(f"{v.codec} {v.width}x{v.height}, {float(v.fps):g} fps, {v.frames} frames ({v.frames_source}), "
              f"duration {info.duration:.1f} s, audio tracks: {len(info.audio)}  [{time.monotonic() - t:.1f} s]")
        t = step("2. start times")
        container, video = stream_times_of(path)
        print(f"container start {float(container):.3f} s, video start {float(video):.3f} s, difference "
              f"{float(video - container) * float(v.fps):.1f} frames  [{time.monotonic() - t:.1f} s]")
        t = step(f"3. thumbnails starting at frame {first} ({count} frames)")
        frames = grab_numbered(path, first, count, v.fps, (53, 42))
        numbers = sorted(frames)
        print(f"{len(frames)} frames, numbers: {numbers[:3]}{' ... ' if len(numbers) > 6 else ' '}{numbers[-3:] if len(numbers) > 3 else ''}"
              f"  [{time.monotonic() - t:.1f} s]")
        wanted = set(range(first, first + count))
        missing = sorted(wanted - set(frames))
        if missing:
            print(f"Requested numbers without a picture (shown as red crosses): {missing[:5]}{'...' if len(missing) > 5 else ''}")
    except Exception:
        print("\nFEHLER:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
