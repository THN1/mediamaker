"""Checks whether the VLC preview gets stuck after many jumps in the paused state.

Usage:  python3 tools/vlc_seek_test.py film.ts [--args "--avcodec-hw=none"] [--count 60]

The program opens a small window, plays the film briefly, pauses it and then jumps `count` times to widely separated positions
while paused. After every jump a still image is saved; if a still looks exactly like the previous one although the positions
are far apart, the preview is frozen.
With --args you can try VLC arguments, e.g.  --args ""   (VLC default, hardware decoding on)
or  --args "--avcodec-hw=none"  or  --args "--avcodec-hw=none --vout=xcb_x11".
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
    print(f"VLC arguments: {vlc_args or '(default)'}")

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
        verdict = "SAME AS BEFORE" if same else ("new" if digest else "no image")
        print(f"jump {i + 1:3d}: target {target / 1000:8.1f} s, VLC time {mp.get_time() / 1000:8.1f} s, image: {verdict}")
        if (same or digest is None) and state["frozen"] is None:
            state["frozen"] = i + 1
        state["last"], state["i"] = digest, i + 1
        step()

    def finish():
        print("\nErgebnis:", f"preview stopped at jump {state['frozen']}" if state["frozen"]
              else f"all {count} jumps showed a new image")
        app.quit()

    mp.play()
    QtCore.QTimer.singleShot(2000, start)
    app.exec()


if __name__ == "__main__":
    main()
