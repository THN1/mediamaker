"""Tests for progress/remaining time (with a simulated clock) and for the real ffmpeg run with cancel."""
import os, subprocess, sys, tempfile, time
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from cutlist import Job, Segment, parse_batch_header
from ffmpeg_cmd import build_command
from progress import ProgressTracker, format_duration, format_progress
from runner import expected_frames, run_ffmpeg, total_seconds, verify_output


def test_tracker():
    t = ProgressTracker(100.0)
    t.start(now=0.0)
    # Evenly 2 seconds of output per second of computing time: after 10 s of computing time 20 s are done
    first = t.update(2.0, now=1.0)
    assert first.eta is None, "remaining time must not be shown yet after 1 s"
    for sec in range(2, 11):
        p = t.update(2.0 * sec, now=float(sec))
    assert abs(p.percent - 20.0) < 1e-9 and abs(p.speed - 2.0) < 1e-9
    assert abs(p.eta - 40.0) < 1e-6, p.eta                     # 80 s remaining at speed 2 -> 40 s
    # Speed halves (more demanding scene): the estimate follows after the time window
    done = 20.0
    for sec in range(11, 60):
        done += 1.0
        p = t.update(done, now=float(sec))
    assert abs(p.speed - 1.0) < 0.05, p.speed
    assert abs(p.eta - (100 - done) / p.speed) < 1e-6
    assert t.update(100.0, now=100.0).eta == 0.0
    assert format_duration(65) == "1:05" and format_duration(3725) == "1:02:05"
    line = format_progress(p)
    assert "Remaining" in line and "%" in line
    print("Progress/remaining time (simulated clock): OK  |", line)


def make_source(path, seconds=240):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=720x576:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", str(seconds),
                    "-c:v", "libx264", "-preset", "ultrafast", "-g", "12", "-pix_fmt", "yuv420p", "-c:a", "mp2",
                    "-f", "mpegts", path], check=True)


def test_real_run():
    src = os.path.join(tempfile.gettempdir(), "mm_runner_src.ts")
    if not os.path.exists(src):
        make_source(src)
    ref = parse_batch_header(open(os.path.join(HERE, "sample_MediaMaker.sh"), encoding="latin-1").read())
    prof = dict(ref.profile, scale="720:576", fps="25.000")
    def seg(i, a, b):
        return Segment(i, src, "src.ts", a, b, 6000, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out.mp4")
        job = Job(out, prof, ref.options, [seg(1, 100, 1900), seg(2, 3000, 4500)])
        cmd = build_command(job, unify=True)
        seen = []
        res = run_ffmpeg(cmd, total_seconds(job), seen.append, cwd=d)
        assert res.ok, res.errors
        pcts = [p.percent for p in seen]
        etas = [p for p in seen if p.eta is not None and p.percent < 100]
        assert pcts == sorted(pcts) and pcts[-1] == 100.0
        print(f"Run: {len(seen)} messages, {res.elapsed:.1f} s, first remaining time at {etas[0].percent:.0f} %" if etas
              else f"Run: {len(seen)} messages, {res.elapsed:.1f} s, run too short for a remaining time")
        ok, actual, msg = verify_output(out, expected_frames(job))
        print(msg)
        assert ok and actual == 3300
        # cancel
        cancel_at = time.monotonic() + 1.0
        res = run_ffmpeg(cmd, total_seconds(job), cwd=d, cancel=lambda: time.monotonic() > cancel_at)
        assert res.cancelled and not res.ok
        print(f"Cancel after {res.elapsed:.1f} s: OK")
        # error case: source missing
        bad = Job(out, prof, ref.options, [Segment(1, "/not/there.ts", "x", 0, 50, 100, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")])
        res = run_ffmpeg([ "ffmpeg", "-y", "-i", "/not/there.ts", out], 2.0, cwd=d)
        assert not res.ok and "not/there.ts" in res.errors
        print("Error case (source missing): error message arrives: OK")


if __name__ == "__main__":
    test_tracker()
    test_real_run()
