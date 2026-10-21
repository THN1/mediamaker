"""Prüft, ob die VLC-Vorschau bei vielen Sprüngen im angehaltenen Zustand stehen bleibt.

Aufruf:  python3 tools/vlc_seek_test.py Film.ts [--args "--avcodec-hw=none"] [--count 60]

Das Programm öffnet ein kleines Fenster, spielt den Film kurz ab, hält ihn an und springt dann `count`-mal im
angehaltenen Zustand an weit auseinanderliegende Stellen. Nach jedem Sprung wird ein Standbild gespeichert; sieht ein
Standbild genauso aus wie das vorige, obwohl die Stellen weit auseinander liegen, ist die Vorschau eingefroren.
Mit --args lassen sich VLC-Argumente ausprobieren, z. B.  --args ""   (VLC-Standard, Hardware-Dekodierung an)
oder  --args "--avcodec-hw=none"  oder  --args "--avcodec-hw=none --vout=xcb_x11".
"""
import hashlib
import os
import shlex
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6 import QtCore, QtWidgets
import vlc


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    vlc_args = shlex.split(args[args.index("--args") + 1]) if "--args" in args else []
    count = int(args[args.index("--count") + 1]) if "--count" in args else 60
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QWidget()
    window.resize(640, 360)
    window.show()
    instance = vlc.Instance("--quiet", *vlc_args)
    mp = instance.media_player_new()
    mp.set_xwindow(int(window.winId()))
    mp.set_media(instance.media_new_path(path))
    folder = tempfile.mkdtemp()
    state = {"i": 0, "last": None, "frozen": None}
    print(f"VLC-Argumente: {vlc_args or '(Standard)'}")

    def start():
        mp.set_pause(1)
        QtCore.QTimer.singleShot(500, step)

    def step():
        i = state["i"]
        if i >= count:
            return finish()
        length = mp.get_length() or 600000
        target = int((i * 7919 * 1000) % max(length - 5000, 1000))
        mp.set_time(target)
        QtCore.QTimer.singleShot(250, lambda: snapshot(i, target))

    def snapshot(i, target):
        shot = os.path.join(folder, f"s{i}.png")
        mp.video_take_snapshot(0, shot, 0, 0)
        QtCore.QTimer.singleShot(250, lambda: compare(i, target, shot))

    def compare(i, target, shot):
        digest = hashlib.md5(open(shot, "rb").read()).hexdigest() if os.path.exists(shot) else None
        same = digest is not None and digest == state["last"]
        verdict = "GLEICH WIE VORHER" if same else ("neu" if digest else "kein Bild")
        print(f"Sprung {i + 1:3d}: Ziel {target / 1000:8.1f} s, VLC-Zeit {mp.get_time() / 1000:8.1f} s, Bild: {verdict}")
        if (same or digest is None) and state["frozen"] is None:
            state["frozen"] = i + 1
        state["last"], state["i"] = digest, i + 1
        step()

    def finish():
        print("\nErgebnis:", f"Vorschau blieb bei Sprung {state['frozen']} stehen" if state["frozen"]
              else f"alle {count} Sprünge zeigten ein neues Bild")
        app.quit()

    mp.play()
    QtCore.QTimer.singleShot(2000, start)
    app.exec()


if __name__ == "__main__":
    main()
