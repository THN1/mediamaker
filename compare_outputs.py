"""Vergleicht zwei fertige Videodateien (z. B. das Ergebnis des VB6-Skripts mit dem der Python-Bausteine).

Aufruf:  python3 compare_outputs.py A.mp4 B.mp4 [--job JOB.sh]

Mit --job (die Batchdatei mit Schnittliste) werden die Nahtstellen zwischen den Segmenten besonders genau geprüft,
denn dort fallen Schnittfehler am ehesten auf. Verglichen werden Eigenschaften (Bildanzahl, Größe, Seitenverhältnis,
Codecs, Dauer von Bild und Ton) und das Bild an etwa 30 Stellen. Für jede Stelle wird geprüft, ob Bild n in A
am besten zu Bild n in B passt oder zu einem Bild bis 30 Bilder davor oder danach (= Schnitt verschoben).
"""
import json
import subprocess
import sys

import numpy as np

from cutlist import parse_batch_header
from frames import grab_window
from mediaprobe import probe


def describe(path: str) -> dict:
    info = probe(path)
    v = info.video
    meta = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_entries",
         "stream=codec_type,sample_aspect_ratio,display_aspect_ratio,duration", path],
        capture_output=True, text=True).stdout)["streams"]
    sar = next((s for s in meta if s["codec_type"] == "video"), {})
    aud = next((s for s in meta if s["codec_type"] == "audio"), {})
    return {"frames": v.frames, "fps": float(v.fps), "size": f"{v.width}x{v.height}", "vcodec": v.codec,
            "sar": sar.get("sample_aspect_ratio", "?"), "dar": sar.get("display_aspect_ratio", "?"),
            "vdur": float(sar.get("duration") or v.duration), "adur": float(aud.get("duration") or 0),
            "acodec": info.audio[0].codec if info.audio else "-", "path": path}


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return 99.0 if mse < 1e-9 else 10 * np.log10(255.0 ** 2 / mse)


def positions(total: int, boundaries: list[int], evenly: int = 12) -> list[int]:
    pos = {0, 1, total - 2, total - 1}
    for b in boundaries:
        pos.update({b - 2, b - 1, b, b + 1})
    pos.update(int(total * k / (evenly + 1)) for k in range(1, evenly + 1))
    return sorted(p for p in pos if 0 <= p < total)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    a_path, b_path = args[0], args[1]
    boundaries = []
    if "--job" in sys.argv:
        job = parse_batch_header(open(sys.argv[sys.argv.index("--job") + 1], encoding="latin-1").read())
        fps_out = float(job.profile.get("fps", "25"))
        acc = 0.0
        for seg in job.segments[:-1]:
            acc += seg.frames / float(seg.fps) * fps_out
            boundaries.append(round(acc))
    A, B = describe(a_path), describe(b_path)
    print(f"{'':22s}{'A':>24s}{'B':>24s}")
    for key, label in (("frames", "Bilder"), ("size", "Größe"), ("fps", "Bildrate"), ("sar", "Pixelseitenverh. (SAR)"),
                       ("dar", "Seitenverh. (DAR)"), ("vcodec", "Videocodec"), ("acodec", "Audiocodec"),
                       ("vdur", "Videodauer (s)"), ("adur", "Tondauer (s)")):
        a, b = A[key], B[key]
        mark = "" if a == b else "   <-- verschieden"
        fa, fb = (f"{a:.3f}" if isinstance(a, float) else str(a)), (f"{b:.3f}" if isinstance(b, float) else str(b))
        print(f"{label:22s}{fa:>24s}{fb:>24s}{mark}")
    total = min(A["frames"], B["frames"])
    fps = probe(a_path).video.fps
    pos = positions(total, boundaries)
    print(f"\nBildvergleich an {len(pos)} Stellen" + (f" (Nähte bei Bild {boundaries})" if boundaries else "") + ":")
    shifted, scores = [], []
    WIN = 30                                           # Suchfenster für Versätze: +-30 Bilder
    for n in pos:
        _, ga = grab_window(a_path, n, 1, fps, origin="video")
        start, bw = grab_window(b_path, n - WIN, 2 * WIN + 1, fps, origin="video")
        cand = {start + k: psnr(ga[0], bw[k]) for k in range(len(bw))}
        same_nr = cand.get(n, 0.0)
        best = max(cand, key=cand.get)
        scores.append(same_nr)
        if best != n and cand[best] > same_nr + 3:
            shifted.append((n, best - n, cand[best], same_nr))
    print(f"  PSNR bei gleicher Bildnummer (verkleinerte Bilder): kleinster Wert {min(scores):.1f} dB, "
          f"Mittel {np.mean(scores):.1f} dB (ab etwa 35 dB gilt das Bild als gleich)")
    if shifted:
        offs = sorted({o for _, o, _, _ in shifted})
        print(f"  {len(shifted)} von {len(pos)} Stellen passen besser zu einem anderen Bild von B (Suchfenster +-30 Bilder):")
        for n, o, good, now in shifted[:12]:
            print(f"    Bild {n}: A entspricht Bild {n + o} in B (Versatz {o:+d}; PSNR {good:.1f} dB statt {now:.1f} dB)")
        if len(shifted) > 12:
            print(f"    ... und {len(shifted) - 12} weitere; aufgetretene Versätze: {offs}")
    ok = A["frames"] == B["frames"] and not shifted and min(scores) >= 30
    print("\nErgebnis:", "Die Dateien stimmen überein." if ok else "Es gibt Unterschiede (siehe oben).")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
