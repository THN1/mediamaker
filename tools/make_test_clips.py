"""Cuts short pieces out of a long recording, so that they can be sent for testing (e.g. around the places where the station logo or the
black border disappears). The pieces are copied without re-encoding (fast, same picture and sound, no loss).

Usage:
    python3 tools/make_test_clips.py FILE --at 1:23:45 [--at 2:01:10 ...] [--before 12] [--after 12] [--out DIR]
    python3 tools/make_test_clips.py FILE --list MediaMaker.json [--before 12] [--after 12] [--out DIR]
    python3 tools/make_test_clips.py FILE --frame 125998 [--frame ...]        (frame numbers as MediaMaker counts them in the saved list)

--at      time (hh:mm:ss or seconds, counted from the beginning of the recording as VLC shows it) that lies inside the piece, usually the cut
          between movie and commercial
--list    saved list of MediaMaker (MediaMaker.json): one piece around the end of every segment (the commercial begins) and one around the start of
          the next segment (the movie goes on); only segments of FILE are used
--before/--after   seconds before and behind the time (default 12 each; a piece of 24 seconds is about 15 MB at 5 MBit/s)
--out     folder for the pieces (default: clips next to the current directory)

Besides the pieces the folder gets clips_info.txt (what was cut from where, the position of the cut inside each piece, ffprobe data) and, with
--list, MediaMaker_clips.json. Please send the folder (zipped) together with MediaMaker.ini.
"""
import argparse
import json
import os
import subprocess
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ffmpeg_cmd import stream_times_of                    # noqa: E402
from frames import frame_time                             # noqa: E402


def parse_time(text: str) -> float:
    parts = [float(p) for p in text.replace(",", ".").split(":")]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def fmt(seconds: float) -> str:
    h, rest = divmod(max(0.0, seconds), 3600)
    m, sec = divmod(rest, 60)
    return f"{int(h)}:{int(m):02d}:{sec:06.3f}"


def probe_text(path: str) -> str:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=index,codec_type,codec_name,width,height,sample_aspect_ratio,"
                          "display_aspect_ratio,r_frame_rate,start_time,duration,bit_rate", "-show_entries", "format=start_time,duration,size",
                          "-of", "default=nw=1", path], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    return out.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--at", action="append", default=[], help="time in the file (hh:mm:ss or seconds)")
    ap.add_argument("--frame", action="append", default=[], type=int, help="frame number as in the saved list of MediaMaker")
    ap.add_argument("--list", help="saved list MediaMaker.json")
    ap.add_argument("--before", type=float, default=12.0)
    ap.add_argument("--after", type=float, default=12.0)
    ap.add_argument("--fps", default="25")
    ap.add_argument("--out", default="clips")
    args = ap.parse_args()
    path = os.path.abspath(args.file)
    fps = Fraction(args.fps)
    container, video = stream_times_of(path)
    places = []                                           # (name, seconds from the container start)
    for text in args.at:
        places.append((f"at_{text.replace(':', '-')}", parse_time(text)))
    for n in args.frame:
        places.append((f"frame_{n}", float(frame_time(n, fps, (container, video), "container", 0) - container)))
    kept = []
    if args.list:
        data = json.load(open(args.list, encoding="utf-8"))
        segs = [s for s in data["segments"] if os.path.basename(s["path"]) == os.path.basename(path)]
        for i, s in enumerate(segs, 1):
            f = Fraction(s.get("fps", "25/1"))
            for kind, n in (("end", s["end"]), ("start", s["start"])):
                if kind == "end" and n >= s["total_frames"]:
                    continue                                # the end of the movie, not a cut
                if kind == "start" and i == 1 and n <= s.get("first_frame", 0):
                    continue                                # the start of the file
                places.append((f"seg{i}_{kind}_frame{n}", float(frame_time(n, f, (container, video), "container", 0) - container)))
        kept = segs
    if not places:
        sys.exit("Nothing to cut: the list has no cut between segments of this file." if args.list else "Nothing to cut: give --at, --frame or --list (see --help).")
    os.makedirs(args.out, exist_ok=True)
    info = [f"source: {path}", f"container start {float(container):.3f} s, video start {float(video):.3f} s", ""]
    for i, (name, t) in enumerate(places, 1):
        start = max(0.0, t - args.before)
        out = os.path.join(args.out, f"clip{i:02d}_{name}.ts")
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", path, "-t", f"{args.before + args.after:.3f}", "-map", "0:v:0", "-map", "0:a?", "-c", "copy", out]
        res = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if res.returncode != 0 or not os.path.exists(out):
            print(f"{out}: ffmpeg failed: {res.stderr.strip()[-200:]}")
            continue
        size = os.path.getsize(out) / 1e6
        line = f"{os.path.basename(out)}: {size:.1f} MB, from {fmt(start)} in the file; the place {name} is at about {t - start:.1f} s in the piece"
        print(line)
        info.append(line)
        info.append(probe_text(out))
        info.append("")
    open(os.path.join(args.out, "clips_info.txt"), "w", encoding="utf-8").write("\n".join(info))
    if kept:
        json.dump({"format": "mediamaker-segments", "version": 1, "segments": kept}, open(os.path.join(args.out, "MediaMaker_clips.json"), "w", encoding="utf-8"), indent=2)
    print(f"\nDone: {len(places)} piece(s) in {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
