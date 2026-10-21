"""Prüft Schritt für Schritt, was die Zeitleiste für eine Datei tut, und zeigt Zeiten und Fehler.

Aufruf:  python3 tools/thumb_test.py DATEI [erstes_Bild] [Anzahl]     (Standard: Bild 0, 10 Bilder)

Gedacht für Dateien auf einem Netzlaufwerk, bei denen die Zeitleiste keine Vorschaubilder zeigt. Die Ausgabe zeigt,
welcher Schritt scheitert oder wie lange er dauert:
  1. schnelle Analyse (ffprobe: Streams, Dauer)
  2. Startzeiten (ffprobe: Beginn des Containers und des Videos)
  3. die Vorschaubilder (ffmpeg) mit ihren Bildnummern
"""
import os
import sys
import time
import traceback
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ffmpeg_cmd import stream_times_of
from frames import grab_numbered
from mediaprobe import probe


def step(name):
    print(f"\n--- {name}")
    return time.monotonic()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    print("Datei:", path, "| vorhanden:", os.path.exists(path))
    try:
        t = step("1. schnelle Analyse")
        info = probe(path, exact_frames=False)
        v = info.video
        print(f"{v.codec} {v.width}x{v.height}, {float(v.fps):g} fps, {v.frames} Bilder ({v.frames_source}), "
              f"Dauer {info.duration:.1f} s, Tonspuren: {len(info.audio)}  [{time.monotonic() - t:.1f} s]")
        t = step("2. Startzeiten")
        container, video = stream_times_of(path)
        print(f"Containerbeginn {float(container):.3f} s, Videobeginn {float(video):.3f} s, Unterschied "
              f"{float(video - container) * float(v.fps):.1f} Bilder  [{time.monotonic() - t:.1f} s]")
        t = step(f"3. Vorschaubilder ab Bild {first} ({count} Stück)")
        frames = grab_numbered(path, first, count, v.fps, (53, 42))
        numbers = sorted(frames)
        print(f"{len(frames)} Bilder, Nummern: {numbers[:3]}{' ... ' if len(numbers) > 6 else ' '}{numbers[-3:] if len(numbers) > 3 else ''}"
              f"  [{time.monotonic() - t:.1f} s]")
        wanted = set(range(first, first + count))
        missing = sorted(wanted - set(frames))
        if missing:
            print(f"Angeforderte Nummern ohne Bild (erscheinen als rote Kreuze): {missing[:5]}{'...' if len(missing) > 5 else ''}")
    except Exception:
        print("\nFEHLER:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
