"""Quick test of a recording: analysis (ffprobe) and border detection at several positions.

Usage:  python3 check_recording.py "recording.m2t" [frame_number ...]
Without frame numbers five evenly spaced positions are checked.
Options for the border detection: environment variables BLACKNESS (default 12), ALLOWANCE (1000), FLOOR (2).
"""
import os
import sys

from border import border_at
from mediaprobe import probe


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    info = probe(path)
    v = info.video
    print(f"{os.path.basename(path)}")
    print(f"  Video : {v.codec} {v.width}x{v.height}, {float(v.fps):g} fps ({v.fps_source}), "
          f"{'interlaced' if v.interlaced else 'progressive'}")
    print(f"  Frames: {v.frames} (source: {v.frames_source}), video duration {v.duration:.2f} s, container {info.duration:.2f} s")
    for a in info.audio:
        print(f"  Audio : stream {a.index}: {a.codec}, {a.channels} channels, {a.sample_rate} Hz, "
              f"{a.bitrate // 1000} kbit/s, language '{a.language or '-'}'")
    for w in info.warnings:
        print("  Note:", w)

    opts = {"blackness": os.environ.get("BLACKNESS", "12"), "allowance": os.environ.get("ALLOWANCE", "1000"),
            "floor": os.environ.get("FLOOR", "2")}
    frames = [int(x) for x in sys.argv[2:]] or [int(v.frames * k / 6) for k in range(1, 6)]
    print(f"  border (black lines at the bottom; blackness={opts['blackness']}, allowance={opts['allowance']}):")
    for f in frames:
        print(f"    frame {f:6d}: {border_at(path, f, v.fps, opts)}")


if __name__ == "__main__":
    main()
