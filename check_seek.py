"""Prüft, wie die ffmpeg-Version auf diesem Rechner Bildnummern mit -ss (wie in VB6) behandelt.

Aufruf:  python3 check_seek.py "Aufnahme.ts" [Bildnummer ...]

Für jede Bildnummer wird das Bild geholt
  - mit dem VB6-Verfahren:  -ss <Sekunden> vor -i und trim relativ dazu (Sprung = round(n/fps) - 2 Sekunden)
  - und zum Vergleich über absolute Zeitstempel mit den drei möglichen Nullpunkten
    (Videobeginn, Containerbeginn, VB6-Muster).
Die Ausgabe sagt, welchem Nullpunkt das VB6-Verfahren auf diesem Rechner entspricht.
"""
import io
import subprocess
import sys

import numpy as np
from PIL import Image

from ffmpeg_cmd import fmt_seconds, split_seek
from frames import grab_frame, stream_times
from mediaprobe import probe


def grab_vb6(path, n, fps, preroll=2):
    seek, rest = split_seek(n, fps, preroll)
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(seek)] if seek > 0 else []) + ["-i", path, "-filter_complex",
           f"[0:v]trim={fmt_seconds(rest)},setpts=PTS-STARTPTS[v]", "-frames:v", "1", "-map", "[v]",
           "-f", "image2pipe", "-c:v", "png", "-"]
    r = subprocess.run(cmd, capture_output=True)
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB")) if r.stdout else None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    v = probe(path).video
    fmt0, vid0 = stream_times(path)
    print(f"{path}: Containerbeginn {float(fmt0):.3f} s, Videobeginn {float(vid0):.3f} s "
          f"(Unterschied {float(vid0 - fmt0):.3f} s = {float((vid0 - fmt0) * v.fps):.1f} Bilder), {v.frames} Bilder")
    ns = [int(x) for x in sys.argv[2:]] or [20, 50, 80, 110, 140]
    counts = {}
    for n in ns:
        b = grab_vb6(path, n, v.fps)
        found = [o for o in ("video", "container") if b is not None and np.array_equal(b, grab_frame(path, n, v.fps, origin=o))]
        label = " und ".join({"video": "Videobeginn", "container": "Containerbeginn"}[o] for o in found) or "weder noch"
        seek = split_seek(n, v.fps, 2)[0]
        print(f"  Bild {n:6d} (Sprung {seek} s): VB6-Verfahren entspricht Nullpunkt: {label}")
        counts[label] = counts.get(label, 0) + 1
    print("Zusammenfassung:", ", ".join(f"{k}: {c}x" for k, c in counts.items()))
    print("Hinweis: Fällt bei kleinen Bildnummern 'Videobeginn' und bei größeren 'Containerbeginn' aus, rechnet VB6 mit\n"
          "dem Muster origin=\"vb6\". 'weder noch' deutet auf ein anderes -ss-Verhalten der ffmpeg-Version hin.")


if __name__ == "__main__":
    main()
