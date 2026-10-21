"""Tests: (1) Vergleich mit dem echten VB6-Aufruf aus sample_MediaMaker.sh,
(2) Ende-zu-Ende-Lauf mit ffmpeg auf einer synthetischen .ts-Datei (Frame-Genauigkeit)."""
import os, re, shlex, subprocess, sys, tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from cutlist import Job, Segment, parse_batch_header
from ffmpeg_cmd import build_command, write_masks
from mediaprobe import probe

NUM = re.compile(r"\d+\.\d{3}")


def same_with_tolerance(a: str, b: str, tol=0.0015) -> bool:
    """Gleich, außer dass dreistellige Zeitwerte um höchstens tol abweichen dürfen."""
    if NUM.sub("#", a) != NUM.sub("#", b):
        return False
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(NUM.findall(a), NUM.findall(b)))


def test_matches_vb6_sample():
    text = open(os.path.join(HERE, "sample_MediaMaker.sh"), encoding="latin-1").read()
    job = parse_batch_header(text)
    assert len(job.segments) == 6 and job.profile["scale"] == "720:576"
    base = "/run/user/1000/kio-fuse-sFijsz/smb/root@gbue4k/harddisk/movie//"
    mine = build_command(job, path_map=lambda p: base + p.split("\\")[-1], stream_times=None)   # None = VB6-Verfahren
    ref = shlex.split([l for l in text.splitlines() if l.startswith("ffmpeg ")][0])
    assert len(mine) == len(ref), (len(mine), len(ref))
    diffs = []
    for m, r in zip(mine, ref):
        if m != r:
            assert same_with_tolerance(m, r), f"Abweichung:\n  neu: {m}\n  VB6: {r}"
            diffs.append((m, r))
    print(f"OK: Kommandozeile identisch ({len(mine)} Argumente); {len(diffs)} Argument(e) mit ≤1 ms Abweichung")
    for m, r in diffs:
        for x, y in zip(NUM.findall(m), NUM.findall(r)):
            if x != y:
                print(f"    VB6 {y}  ->  neu {x}")


def make_source(path):
    """Synthetische 'TV-Aufnahme': 720x576, 25 fps, interlaced, 10 s, Keyframe alle 12 Bilder (wie im Rundfunk)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=720x576:rate=25",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "10",
                    "-c:v", "libx264", "-g", "12", "-bf", "2", "-pix_fmt", "yuv420p", "-flags", "+ilme+ildct",
                    "-c:a", "mp2", "-f", "mpegts", path], check=True)


def test_end_to_end(unify):
    src = os.path.join(tempfile.gettempdir(), "mm_test_gop12.ts")
    if not os.path.exists(src):
        make_source(src)
    ref = parse_batch_header(open(os.path.join(HERE, "sample_MediaMaker.sh"), encoding="latin-1").read())
    mask = ref.segments[0].mask                       # echte PNG-Maske aus dem Beispiel (720x576)
    def seg(i, a, b, m=""):
        return Segment(i, src, "test.ts", a, b, 250, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, m)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out.mp4")
        job = Job(out, ref.profile, ref.options, [seg(1, 25, 100, mask), seg(2, 150, 225)])
        write_masks(job.segments, d)
        cmd = build_command(job, unify=unify)
        res = subprocess.run(cmd, cwd=d, capture_output=True)
        assert res.returncode == 0, res.stderr.decode()[-800:]
        info = probe(out)
        print(f"unify={unify}: erwartet 150 Frames, erhalten {info.video.frames} "
              f"({info.video.frames_source}), {info.video.width}x{info.video.height}, {info.video.fps} fps, "
              f"Codec {info.video.codec}/{info.audio[0].codec}, Warnungen: {info.warnings}")
        assert info.video.frames == 150


def _sar(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=sample_aspect_ratio,display_aspect_ratio", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return out


def test_sar_handling():
    """Eine Quelle: SAR/DAR der Aufnahme bleiben erhalten. Mehrere Quellen: concat funktioniert (setsar=1)."""
    tmp = tempfile.gettempdir()
    srcs = []
    for n, sar in enumerate(["64/45", "16/15"]):                 # 16:9 und 4:3 (PAL)
        f = os.path.join(tmp, f"mm_sar{n}.ts")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=720x576:rate=25,setsar={sar}",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "6",
                        "-c:v", "libx264", "-g", "12", "-pix_fmt", "yuv420p", "-c:a", "mp2", "-f", "mpegts", f], check=True)
        srcs.append(f)
    ref = parse_batch_header(open(os.path.join(HERE, "sample_MediaMaker.sh"), encoding="latin-1").read())
    def seg(i, f, a, b):
        return Segment(i, f, os.path.basename(f), a, b, 150, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")
    with tempfile.TemporaryDirectory() as d:
        out1 = os.path.join(d, "one.mp4")
        job = Job(out1, ref.profile, ref.options, [seg(1, srcs[0], 25, 50), seg(2, srcs[0], 75, 100)])
        cmd = build_command(job)
        assert "setsar=1" not in cmd[cmd.index("-filter_complex") + 1]
        assert subprocess.run(cmd, cwd=d, capture_output=True).returncode == 0
        print("eine Quelle  : SAR/DAR =", _sar(out1), "(Quelle: 64:45 / 16:9)")
        assert _sar(out1).startswith("64:45")
        out2 = os.path.join(d, "two.mp4")
        job = Job(out2, ref.profile, ref.options, [seg(1, srcs[0], 25, 50), seg(2, srcs[1], 25, 50)])
        cmd = build_command(job)
        assert "setsar=1" in cmd[cmd.index("-filter_complex") + 1]
        res = subprocess.run(cmd, cwd=d, capture_output=True)
        assert res.returncode == 0, res.stderr.decode()[-500:]
        print("zwei Quellen : concat OK, Frames =", probe(out2).video.frames, ", SAR/DAR =", _sar(out2))
        assert probe(out2).video.frames == 50


if __name__ == "__main__":
    test_matches_vb6_sample()
    test_end_to_end(False)
    test_end_to_end(True)
    test_sar_handling()
