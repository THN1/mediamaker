"""Tests für Fortschritt/Restzeit (mit simulierter Uhr) und für den echten ffmpeg-Lauf mit Abbruch."""
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
    # Gleichmäßig 2 Ausgabesekunden pro Sekunde Rechenzeit: nach 10 s Rechenzeit sind 20 s fertig
    first = t.update(2.0, now=1.0)
    assert first.eta is None, "Restzeit darf nach 1 s noch nicht angezeigt werden"
    for sec in range(2, 11):
        p = t.update(2.0 * sec, now=float(sec))
    assert abs(p.percent - 20.0) < 1e-9 and abs(p.speed - 2.0) < 1e-9
    assert abs(p.eta - 40.0) < 1e-6, p.eta                     # 80 s Rest bei Tempo 2 -> 40 s
    # Tempo halbiert sich (aufwendigere Szene): die Schätzung folgt nach dem Zeitfenster
    done = 20.0
    for sec in range(11, 60):
        done += 1.0
        p = t.update(done, now=float(sec))
    assert abs(p.speed - 1.0) < 0.05, p.speed
    assert abs(p.eta - (100 - done) / p.speed) < 1e-6
    assert t.update(100.0, now=100.0).eta == 0.0
    assert format_duration(65) == "1:05" and format_duration(3725) == "1:02:05"
    line = format_progress(p)
    assert "Restzeit" in line and "%" in line
    print("Fortschritt/Restzeit (simulierte Uhr): OK  |", line)


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
        print(f"Lauf: {len(seen)} Meldungen, {res.elapsed:.1f} s, erste Restzeit bei {etas[0].percent:.0f} %" if etas
              else f"Lauf: {len(seen)} Meldungen, {res.elapsed:.1f} s, Lauf zu kurz für eine Restzeit")
        ok, actual, msg = verify_output(out, expected_frames(job))
        print(msg)
        assert ok and actual == 3300
        # Abbruch
        cancel_at = time.monotonic() + 1.0
        res = run_ffmpeg(cmd, total_seconds(job), cwd=d, cancel=lambda: time.monotonic() > cancel_at)
        assert res.cancelled and not res.ok
        print(f"Abbruch nach {res.elapsed:.1f} s: OK")
        # Fehlerfall: Quelle fehlt
        bad = Job(out, prof, ref.options, [Segment(1, "/nicht/da.ts", "x", 0, 50, 100, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")])
        res = run_ffmpeg([ "ffmpeg", "-y", "-i", "/nicht/da.ts", out], 2.0, cwd=d)
        assert not res.ok and "nicht/da.ts" in res.errors
        print("Fehlerfall (Quelle fehlt): Fehlermeldung kommt an: OK")


if __name__ == "__main__":
    test_tracker()
    test_real_run()
