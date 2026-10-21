"""Test of the logo functions with a real recording that contains an (almost) black frame with a station logo.

Usage:  python3 tests/test_logo.py "path/to/sample.ts" [frame number with logo]
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

# 1) isolate mask and logo
img = grab_frame(SRC, FRAME, FPS)
mask = make_mask(img)
print(f"frame {FRAME}: {mask.sum()} white pixels ({mask.mean()*100:.2f} %)")
ref = isolate_logo(mask)
assert ref is not None, "logo could not be isolated"
l, t, r, b = ref.rect
print(f"logo rectangle (left, top, right, bottom): {ref.rect}  = {r-l} x {b-t} pixels; reference edges: {ref.ones}")
b64 = mask_to_png_b64(mask)
print(f"PNG mask as Base64: {len(b64)} characters, starts with '{b64[:8]}'")

# check picture: original with rectangle, next to it the mask
vis = Image.fromarray(img).convert("RGB")
ImageDraw.Draw(vis).rectangle([l, t, r - 1, b - 1], outline=(255, 0, 0))
vis.crop((520, 0, 720, 120)).resize((800, 480)).save(os.path.join(OUT, "logo_rect.png"))
Image.fromarray(mask).save(os.path.join(OUT, "mask.png"))

# 2) match along the recording
print("match (threshold 0.2):")
confs = {}
for f in range(0, N, 10):
    confs[f] = confidence_at(SRC, f, FPS, ref, opts)
print("  " + "  ".join(f"{f}:{c:.2f}" for f, c in confs.items()))

# 3) search
calls = []
def conf_of(f):
    calls.append(f); return confidence_at(SRC, f, FPS, ref, opts)
first_logo = where_logo(conf_of, 0, N - 1, True, 10)
print(f"first frame with logo from frame 0 (step 10, without rewind): {first_logo}  ({len(calls)} frame analyses)")
calls.clear()
gone = where_logo(conf_of, FRAME, N - 1, False, 10)
print(f"first frame WITHOUT logo from frame {FRAME}: {gone}  ({len(calls)} frame analyses)")

# 4) removelogo filter with the mask
seg = Segment(1, SRC, os.path.basename(SRC), 30, 90, N, FPS, info.width, info.height, 0, 0, "a", 0, 0, 0, 0, 48000, b64)
ref_job = Job(os.path.join(OUT, "out.mp4"), {"scale": f"{info.width}:{info.height}", "sws_flags": "lanczos", "fps": "25.000",
              "bv": "3072k", "ba": "192k", "acodec_out": "aac", "ar": "48000"}, {}, [seg])
write_masks(ref_job.segments, OUT)
res = subprocess.run(build_command(ref_job), cwd=OUT, capture_output=True)
assert res.returncode == 0, res.stderr.decode()[-600:]
after = grab_frame(os.path.join(OUT, "out.mp4"), 10, FPS)
before_max = int(to_grey_max := np.asarray(img)[t:b, l:r].max())
after_max = int(after[t:b, l:r].max())
print(f"brightness in the logo rectangle: before max {before_max}, after removelogo max {after_max}")
assert after_max < before_max // 2, "logo was not removed"
print("OK  (control pictures in", OUT + ")")
