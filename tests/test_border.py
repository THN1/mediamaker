"""Tests for border detection and commercial search with a synthetic recording:
100 frames with a black border (72 lines top/bottom, slight noise (alls=3)), then 100 frames without border ('commercial')."""
import os, subprocess, sys, tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from border import border_at, count_black_lines, where_border
from frames import grab_frame

FPS = Fraction(25)


def make_source(path):
    fc = ("[0:v]pad=720:576:0:72:black,noise=alls=3:allf=t[a];[1:v]noise=alls=3:allf=t[b];[a][b]concat=n=2:v=1:a=0[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=720x432:rate=25:duration=4",
                    "-f", "lavfi", "-i", "testsrc2=size=720x576:rate=25:duration=4", "-filter_complex", fc,
                    "-map", "[v]", "-c:v", "libx264", "-crf", "12", "-g", "12", "-pix_fmt", "yuv420p", "-f", "mpegts", path],
                   check=True)


def main():
    src = os.path.join(tempfile.gettempdir(), "mm_border_test.ts")
    make_source(src)
    opts = {"floor": "2", "blackness": "12", "allowance": "1000"}
    img = grab_frame(src, 50, FPS)
    print("frame size:", img.shape[1], "x", img.shape[0])
    b1, b2 = border_at(src, 50, FPS, opts), border_at(src, 150, FPS, opts)
    print(f"border at frame 50: {b1} (expected about 72); at frame 150 (without border): {b2} (expected 0)")
    assert abs(b1 - 72) <= 3 and b2 == 0   # chroma subsampling and compression blur the edge by 1-2 lines
    calls = []
    def of(f):
        calls.append(f); return border_at(src, f, FPS, opts)
    # 'commercial starts' (border disappears): from frame 10, border 72, equal=False
    a = where_border(of, 10, 199, 72, False, 50)
    print(f"change movie -> commercial at frame {a} (expected 100), {len(calls)} frame analyses")
    assert abs(a - 100) <= 1
    calls.clear()
    # 'commercial ends' (border returns) is tested with reversed order: border = 0 from frame 100
    z = where_border(of, 10, 199, 0, True, 50)
    print(f"first frame without border from frame 10: {z} (expected 100), {len(calls)} frame analyses")
    assert abs(z - 100) <= 1
    print("OK")


main()
