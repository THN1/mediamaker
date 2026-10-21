"""Test der Logo-Funktionen mit einer echten Aufnahme, die einen (fast) schwarzen Frame mit Senderlogo enthält.

Aufruf:  python3 tests/test_logo.py "Pfad/zu/sample.ts" [Bildnummer mit Logo]
"""
import os, subprocess, sys, tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import numpy as np
from PIL import Image, ImageDraw
from cutlist import Job, Segment
from ffmpeg_cmd import build_command, write_masks
from frames import grab_frame
from logo import (bottom_line_average, confidence_at, isolate_logo, logo_confidence, make_mask,
                  mask_to_png_b64, rewind, where_logo)
from mediaprobe import probe

if len(sys.argv) < 2:
    sys.exit(__doc__)
SRC = sys.argv[1]
FRAME = int(sys.argv[2]) if len(sys.argv) > 2 else 50
OUT = os.path.join(tempfile.gettempdir(), "mm_logo")
os.makedirs(OUT, exist_ok=True)
info = probe(SRC).video
FPS, N = info.fps, info.frames
opts = {"floor": "2"}

# 1) Maske und Logo isolieren
img = grab_frame(SRC, FRAME, FPS)
mask = make_mask(img)
print(f"Bild {FRAME}: {mask.sum()} weiße Pixel ({mask.mean()*100:.2f} %)")
ref = isolate_logo(mask)
assert ref is not None, "Logo konnte nicht isoliert werden"
l, t, r, b = ref.rect
print(f"Logo-Rechteck (links, oben, rechts, unten): {ref.rect}  = {r-l} x {b-t} Pixel; Referenzkanten: {ref.ones}")
b64 = mask_to_png_b64(mask)
print(f"PNG-Maske als Base64: {len(b64)} Zeichen, beginnt mit '{b64[:8]}'")

# Kontrollbild: Original mit Rechteck, daneben die Maske
vis = Image.fromarray(img).convert("RGB")
ImageDraw.Draw(vis).rectangle([l, t, r - 1, b - 1], outline=(255, 0, 0))
vis.crop((520, 0, 720, 120)).resize((800, 480)).save(os.path.join(OUT, "logo_rect.png"))
Image.fromarray(mask).save(os.path.join(OUT, "mask.png"))

# 2) Übereinstimmung entlang der Aufnahme
print("Übereinstimmung (Schwelle 0.2):")
confs = {}
for f in range(0, N, 10):
    confs[f] = confidence_at(SRC, f, FPS, ref, opts)
print("  " + "  ".join(f"{f}:{c:.2f}" for f, c in confs.items()))

# 3) Suche
calls = []
def conf_of(f):
    calls.append(f); return confidence_at(SRC, f, FPS, ref, opts)
first_logo = where_logo(conf_of, 0, N - 1, True, 10)
print(f"erstes Bild mit Logo ab Bild 0 (Schritt 10, ohne rewind): {first_logo}  ({len(calls)} Bildanalysen)")
calls.clear()
gone = where_logo(conf_of, FRAME, N - 1, False, 10)
print(f"erstes Bild OHNE Logo ab Bild {FRAME}: {gone}  ({len(calls)} Bildanalysen)")

# 4) removelogo-Filter mit der Maske
seg = Segment(1, SRC, os.path.basename(SRC), 30, 90, N, FPS, info.width, info.height, 0, 0, "a", 0, 0, 0, 0, 48000, b64)
ref_job = Job(os.path.join(OUT, "out.mp4"), {"scale": f"{info.width}:{info.height}", "sws_flags": "lanczos", "fps": "25.000",
              "bv": "3072k", "ba": "192k", "acodec_out": "aac", "ar": "48000"}, {}, [seg])
write_masks(ref_job.segments, OUT)
res = subprocess.run(build_command(ref_job), cwd=OUT, capture_output=True)
assert res.returncode == 0, res.stderr.decode()[-600:]
after = grab_frame(os.path.join(OUT, "out.mp4"), 10, FPS)
before_max = int(to_grey_max := np.asarray(img)[t:b, l:r].max())
after_max = int(after[t:b, l:r].max())
print(f"Helligkeit im Logo-Rechteck: vorher max {before_max}, nach removelogo max {after_max}")
assert after_max < before_max // 2, "Logo wurde nicht entfernt"
print("OK  (Kontrollbilder in", OUT + ")")
