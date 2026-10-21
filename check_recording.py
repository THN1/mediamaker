"""Schnelltest für eine Aufnahme: Analyse (ffprobe) und Rand-Erkennung an mehreren Stellen.

Aufruf:  python3 check_recording.py "Aufnahme.m2t" [Bildnummer ...]
Ohne Bildnummern werden fünf gleichmäßig verteilte Stellen geprüft.
Optionen für die Rand-Erkennung: Umgebungsvariablen BLACKNESS (Standard 12), ALLOWANCE (1000), FLOOR (2).
"""
import os
import sys

from border import border_at
from mediaprobe import probe


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    info = probe(path)
    v = info.video
    print(f"{os.path.basename(path)}")
    print(f"  Video : {v.codec} {v.width}x{v.height}, {float(v.fps):g} fps ({v.fps_source}), "
          f"{'interlaced' if v.interlaced else 'progressiv'}")
    print(f"  Frames: {v.frames} (Quelle: {v.frames_source}), Videodauer {v.duration:.2f} s, Container {info.duration:.2f} s")
    for a in info.audio:
        print(f"  Audio : Stream {a.index}: {a.codec}, {a.channels} Kanäle, {a.sample_rate} Hz, "
              f"{a.bitrate // 1000} kbit/s, Sprache '{a.language or '-'}'")
    for w in info.warnings:
        print("  Hinweis:", w)

    opts = {"blackness": os.environ.get("BLACKNESS", "12"), "allowance": os.environ.get("ALLOWANCE", "1000"),
            "floor": os.environ.get("FLOOR", "2")}
    frames = [int(x) for x in sys.argv[2:]] or [int(v.frames * k / 6) for k in range(1, 6)]
    print(f"  Rand (schwarze Zeilen unten; blackness={opts['blackness']}, allowance={opts['allowance']}):")
    for f in frames:
        print(f"    Bild {f:6d}: {border_at(path, f, v.fps, opts)}")


if __name__ == "__main__":
    main()
