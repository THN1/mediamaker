"""Tests für Rand-Erkennung und Werbe-Suche mit einer synthetischen Aufnahme:
100 Bilder mit schwarzem Rand (72 Zeilen oben/unten, leichtes Rauschen (alls=3)), danach 100 Bilder ohne Rand ('Werbung')."""
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
    print("Bildgröße:", img.shape[1], "x", img.shape[0])
    b1, b2 = border_at(src, 50, FPS, opts), border_at(src, 150, FPS, opts)
    print(f"Rand bei Bild 50: {b1} (erwartet etwa 72); bei Bild 150 (ohne Rand): {b2} (erwartet 0)")
    assert abs(b1 - 72) <= 3 and b2 == 0   # Chroma-Unterabtastung und Kompression verwischen die Kante um 1-2 Zeilen
    calls = []
    def of(f):
        calls.append(f); return border_at(src, f, FPS, opts)
    # 'Werbung beginnt' (Rand verschwindet): ab Bild 10, Rand 72, equal=False
    a = where_border(of, 10, 199, 72, False, 50)
    print(f"Wechsel Film -> Werbung bei Bild {a} (erwartet 100), {len(calls)} Bildanalysen")
    assert abs(a - 100) <= 1
    calls.clear()
    # 'Werbung endet' (Rand kommt zurück) wird mit umgekehrter Reihenfolge geprüft: Rand = 0 ab Bild 100
    z = where_border(of, 10, 199, 0, True, 50)
    print(f"Erstes Bild ohne Rand ab Bild 10: {z} (erwartet 100), {len(calls)} Bildanalysen")
    assert abs(z - 100) <= 1
    print("OK")


main()
