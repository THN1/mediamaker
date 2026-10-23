"""Shows how the first frame of a video file is found and whether the thumbnails agree.

Usage:  python3 tools/first_frame_check.py FILE [FPS]

Prints the start times, the first packets (decoding order), the first frames that the decoder delivers, the number MediaMaker takes as the
first frame, and the numbers of the pictures that the timeline loader really delivers around it. If the loader's first picture is later
than the first frame, MediaMaker corrects that when the file is opened (and says so).
"""
import os
import subprocess
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mediaprobe                                        # noqa: E402
from ffmpeg_cmd import stream_times_of                   # noqa: E402
from frames import grab_numbered                         # noqa: E402


def ffprobe(*args) -> str:
    return subprocess.run(["ffprobe", "-v", "error", *args], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    fps = Fraction(sys.argv[2]) if len(sys.argv) > 2 else Fraction(25)
    container, video = stream_times_of(path)
    print(f"container start {float(container):.3f} s, video stream start {float(video):.3f} s, frame rate {fps}")
    print("first video packets (pts, dts, flags):")
    for line in ffprobe("-select_streams", "v:0", "-read_intervals", "%+#8", "-show_entries", "packet=pts_time,dts_time,flags", "-of", "csv=p=0", path).splitlines()[:8]:
        print("   ", line)
    print("first frames the decoder delivers (pts, type):")
    for line in ffprobe("-select_streams", "v:0", "-read_intervals", "%+#14", "-show_entries", "frame=pts_time,pict_type", "-of", "csv=p=0", path).splitlines()[:6]:
        print("   ", line)
    first = mediaprobe.first_frame_number(path, fps)
    print(f"first frame taken by MediaMaker: {first}  (decoder: pts {mediaprobe.decoded_first_pts(path)})")
    got = sorted(grab_numbered(path, max(0, first - 10), 20, fps, (32, 24)))
    print(f"timeline loader, window {max(0, first - 10)}..{max(0, first - 10) + 19}: pictures {got[0] if got else None}..{got[-1] if got else None} ({len(got)})")
    if got and got[0] > first:
        print(f"-> the pictures begin {got[0] - first} frame(s) after the first frame; MediaMaker moves the first frame to {got[0]} when it opens the file")
    elif got and got[0] == first:
        print("-> the first frame and the first picture agree")


if __name__ == "__main__":
    main()
