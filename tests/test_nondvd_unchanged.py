"""Jobs that are NOT in DVD mode must be built exactly as they were before the DVD mode: the command of ffmpeg, the copy mode command and the batch script are made with an earlier commit
(default 864e58d, the last one before the DVD work) and with the program as it is now, and the texts are compared.  python3 tests/test_nondvd_unchanged.py <folder of the test videos> [commit]

Skipped (exit 0) if the commit is not in the repository (a copy without the history)."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DUMP = r'''
import json, os, sys
from fractions import Fraction
tree, videos = sys.argv[1], sys.argv[2]
sys.path.insert(0, tree)
from cutlist import Job, Segment, parse_batch_header
import ffmpeg_cmd, mediaprobe, copymode, batch
out = {}

def seg(i, name, a, b, mask="", first=0):
    info = mediaprobe.probe(os.path.join(videos, name))
    v = info.video
    return Segment(i, os.path.join(videos, name), name, a, b, v.frames + first, v.fps, v.width, v.height, 0, 0, "a", 0, 0, 0, 0, 48000, mask, first)

ref = parse_batch_header(open(os.path.join(tree, "tests", "sample_MediaMaker.sh"), encoding="latin-1").read())
profile, options = dict(ref.profile), dict(ref.options)
png_mask = ref.segments[0].mask

def case(name, fn):
    try:
        out[name] = fn()
    except Exception as e:
        out[name] = "ERROR " + type(e).__name__ + ": " + str(e)

def job_of(segments, ext="mp4", extra=None):
    return Job("/o/film." + ext, dict(profile), {**options, **(extra or {})}, segments)

one = lambda: [seg(1, "sample.ts", 0, 148)]
two = lambda: [seg(1, "sample.ts", 10, 60), seg(2, "sample2.ts", 5, 90)]
cut = lambda: [seg(1, "sample.ts", 25, 100, png_mask), seg(2, "sample.ts", 110, 140, "0.8 0.1 0.05 0.05")]
case("whole_auto", lambda: ffmpeg_cmd.build_command(job_of(one())))
case("whole_vb6", lambda: ffmpeg_cmd.build_command(job_of(one()), stream_times=None))
case("two_files_auto", lambda: ffmpeg_cmd.build_command(job_of(two())))
case("two_files_vb6", lambda: ffmpeg_cmd.build_command(job_of(two()), stream_times=None))
case("cuts_masks_auto", lambda: ffmpeg_cmd.build_command(job_of(cut())))
case("cuts_masks_vb6", lambda: ffmpeg_cmd.build_command(job_of(cut()), stream_times=None))
case("crop", lambda: ffmpeg_cmd.build_command(job_of(cut(), extra={"crop": "60"})))
case("mkv", lambda: ffmpeg_cmd.build_command(job_of(two(), "mkv")))
case("avi", lambda: ffmpeg_cmd.build_command(job_of(two(), "avi")))
case("ts", lambda: ffmpeg_cmd.build_command(job_of(two(), "ts")))
case("chapters", lambda: ffmpeg_cmd.build_command(job_of(two()), chapters_file="/w/chapters.txt"))
case("path_map", lambda: ffmpeg_cmd.build_command(job_of(two()), path_map=lambda p: os.path.join(videos, os.path.basename(p))))

# multitrack: test_3.ts has four audio tracks, Teletext and four DVB subtitle tracks
def multi(extra, ext="mp4", times="auto"):
    segs = [seg(1, "test_3.ts", 0, 100)]
    files = {}
    tl = mediaprobe.track_list(os.path.join(videos, "test_3.ts"))
    cmd = ffmpeg_cmd.build_command(job_of(segs, ext, extra), subtitle_list="/w/subs.ffconcat", files=files, track_list=tl, **({} if times == "auto" else {"stream_times": times}))
    return {"command": cmd, "files": files}
case("multi_audio", lambda: multi({"audio_tracks": "1:fra,0:deu"}))
case("multi_subs_mkv", lambda: multi({"audio_tracks": "0:deu", "subtitle_tracks": "1:fra,2:eng"}, "mkv"))
case("multi_subs_mp4", lambda: multi({"audio_tracks": "0:deu", "subtitle_tracks": "1:fra"}, "mp4"))
def multi_two():
    segs = [seg(1, "test_3.ts", 0, 60), seg(2, "test_3.ts", 70, 120)]
    files = {}
    tl = mediaprobe.track_list(os.path.join(videos, "test_3.ts"))
    cmd = ffmpeg_cmd.build_command(job_of(segs, "mkv", {"audio_tracks": "1:fra", "subtitle_tracks": "1:fra"}), subtitle_list="/w/subs.ffconcat", files=files, track_list=tl)
    return {"command": cmd, "files": files}
case("multi_two_segments", multi_two)

# copy mode
def copy_cut():
    segs = [seg(1, "sample.ts", 20, 100)]
    j = job_of(segs, "mkv", {"copymode": "on"})
    plan = copymode.make_plan(segs, j.options)
    return {"kind": plan.kind, "command": copymode.build_copy_command(plan, j, "/w/files.txt" if plan.kind == "concat" else None)}
case("copy_cut", copy_cut)
def copy_join():
    segs = [seg(1, "sample.ts", 0, 148), seg(2, "sample2.ts", 0, 100)]
    j = job_of(segs, "mkv", {"copymode": "on"})
    plan = copymode.make_plan(segs, j.options)
    return {"kind": plan.kind, "list": copymode.list_text(plan, lambda p: p), "command": copymode.build_copy_command(plan, j, "/w/files.txt" if plan.kind == "concat" else None)}
case("copy_join", copy_join)

# the batch file
def script():
    j = job_of(two())
    cmd = ffmpeg_cmd.build_command(j, path_map=lambda p: p)
    return batch.build_script(j, cmd)
case("batch_script", script)
def script_multi():
    segs = [seg(1, "test_3.ts", 0, 100)]
    j = job_of(segs, "mkv", {"audio_tracks": "0:deu", "subtitle_tracks": "1:fra"})
    files = {}
    tl = mediaprobe.track_list(os.path.join(videos, "test_3.ts"))
    cmd = ffmpeg_cmd.build_command(j, subtitle_list=batch.subtitles_temp(j.output), files=files, track_list=tl)
    return batch.build_script(j, cmd, extra_files=files)
case("batch_script_multi", script_multi)
print(json.dumps(out, sort_keys=True))
'''


def dump(tree: str, videos: str) -> dict:
    done = subprocess.run([sys.executable, "-c", DUMP, tree, videos], capture_output=True, text=True, cwd=tree, stdin=subprocess.DEVNULL, timeout=250)
    if done.returncode != 0:
        raise RuntimeError(f"the commands could not be made in {tree}:\n{done.stderr[-800:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def main() -> int:
    videos = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
    base = sys.argv[2] if len(sys.argv) > 2 else "864e58d"
    if subprocess.run(["git", "-C", ROOT, "cat-file", "-e", base + "^{commit}"], capture_output=True).returncode != 0:
        print(f"Commit {base} is not in this repository: the comparison is skipped")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        old = os.path.join(tmp, "base")
        os.makedirs(old)
        archive = subprocess.run(["git", "-C", ROOT, "archive", base], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", old], input=archive, check=True)
        # a copy of the program as it is now (without the history), so that both are made the same way
        new = os.path.join(tmp, "now")
        os.makedirs(new)
        files = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True).stdout.split("\n")
        tracked = [f for f in files if f and os.path.exists(os.path.join(ROOT, f))]
        subprocess.run(["tar", "-c", "-C", ROOT, *tracked], stdout=(tar := open(os.path.join(tmp, "now.tar"), "wb")), check=True)
        tar.close()
        subprocess.run(["tar", "-x", "-C", new, "-f", os.path.join(tmp, "now.tar")], check=True)
        before, now = dump(old, videos), dump(new, videos)
        # a control: the same comparison must find a change that is made on purpose (else it would find nothing at all)
        path = os.path.join(new, "ffmpeg_cmd.py")
        text = open(path, encoding="utf-8").read()
        control = None
        if '"-sws_flags"' in text:
            open(path, "w", encoding="utf-8").write(text.replace('"-sws_flags"', '"-sws_flagz"'))
            control = dump(new, videos)
            open(path, "w", encoding="utf-8").write(text)
        found = sum(1 for k in before if control is not None and before[k] != control.get(k))
        if control is None or found == 0:
            print("The control did not find the change that was made on purpose: the comparison cannot be trusted")
            return 1
        print(f"(control: a change made on purpose is found in {found} of {len(before)} cases)")
    bad = [k for k in sorted(before) if before[k] != now.get(k)]
    errors = [k for k in before if isinstance(before[k], str) and before[k].startswith("ERROR")]
    for k in bad:
        print(f"DIFFERENT: {k}\n  before: {json.dumps(before[k])[:500]}\n  now:    {json.dumps(now.get(k))[:500]}")
    if errors:
        print("Cases that cannot be made (also before):", errors)
    print(f"Jobs without DVD mode: {len(before)} cases compared with {base}: " + ("all texts are identical" if not bad else f"{len(bad)} differ"))
    return 1 if bad or set(before) != set(now) else 0


if __name__ == "__main__":
    sys.exit(main())
