"""The internal viewer for the clip around a cut point (in every mode): every picture of the clip can be looked at one by one, and the clip can be
played with sound.

Everything that decides is in ClipController (no Qt, tested with FakePlayer): the pictures are written by ffmpeg as JPEG files, the controller knows which one is shown, steps
forwards and backwards, jumps, and follows the time of the player while it plays. ClipViewer (the dialog) only shows it: the picture, a slider, the buttons.
"""
from __future__ import annotations

import glob
import os
import subprocess
from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ffmpeg_cmd import passthrough_args

DEFAULT_FPS = 25.0
STAGE_WIDTH = 720                   # the width of the picture on the screen; its height follows from the display format


def frames_command(clip: str, folder: str, ffmpeg: str = "ffmpeg") -> list:
    """ffmpeg writes every picture of the clip (no picture is left out or repeated) as folder/f00001.jpg, f00002.jpg ..."""
    return [ffmpeg, "-v", "error", "-y", "-i", clip, "-map", "0:v:0", "-an", *passthrough_args(ffmpeg), "-q:v", "2", os.path.join(folder, "f%05d.jpg")]


def extract_frames(clip: str, folder: str, ffmpeg: str = "ffmpeg", run: Callable = subprocess.run) -> list:
    """Writes the pictures of the clip into `folder` and returns their file names in the order of the clip. RuntimeError with the message of ffmpeg if there are none."""
    res = run(frames_command(clip, folder, ffmpeg), stdin=subprocess.DEVNULL, capture_output=True)
    files = sorted(glob.glob(os.path.join(folder, "f*.jpg")))
    if res.returncode != 0 or not files:
        text = (res.stderr or b"").decode(errors="replace").strip()[-300:] if isinstance(res.stderr, bytes) else str(res.stderr or "")
        raise RuntimeError(f"No pictures could be read from the clip: {text or res.returncode}")
    return files


class ClipController:
    """The state of the viewer: the picture files, the number of the shown picture (from 0), whether the clip is playing."""

    def __init__(self, files: list, fps: float = DEFAULT_FPS, player=None, aspect: str = "16:9"):
        self.files = list(files)
        self.aspect = aspect                     # the display format ("4:3", "16:9"): the shape of the picture and of the video area
        self.fps = float(fps) if fps and fps > 0 else DEFAULT_FPS
        self.player = player
        self.index = 0
        self.playing = False

    @property
    def count(self) -> int:
        return len(self.files)

    def ms_of(self, index: int) -> int:
        return round(index * 1000.0 / self.fps)

    def index_of(self, ms: int) -> int:
        return self.clamp(int(ms * self.fps / 1000.0 + 1e-6))

    def clamp(self, index: int) -> int:
        return max(0, min(self.count - 1, int(index)))

    def file(self) -> str:
        return self.files[self.index]

    def show(self, index: int) -> int:
        """Shows picture `index` (limited to the clip); a playing clip is paused first. Returns the number shown."""
        if self.playing:
            self.pause()
        self.index = self.clamp(index)
        return self.index

    def step(self, delta: int) -> int:
        return self.show(self.index + delta)

    def label(self) -> str:
        return f"Picture {self.index + 1} of {self.count}   ·   {self.ms_of(self.index) / 1000.0:.2f} s"

    def play(self) -> None:
        """Plays with sound from the shown picture (from the beginning when the end is shown)."""
        if self.player is None:
            return
        if self.index >= self.count - 1:
            self.index = 0
        self.playing = True
        self.player.play_at(self.ms_of(self.index))

    def pause(self) -> None:
        """Pauses; the picture at the time of the player stays shown."""
        if self.player is not None and self.playing:
            self.index = self.index_of(self.player.get_time())
            self.player.pause()
        self.playing = False

    def toggle(self) -> bool:
        self.pause() if self.playing else self.play()
        return self.playing

    def follow(self) -> bool:
        """Called often while playing: the picture follows the time of the player. Returns False when the clip is over (then the last picture stays)."""
        if not self.playing or self.player is None:
            return False
        self.index = self.index_of(self.player.get_time())
        if self.player.is_playing and self.index < self.count - 1:
            return True
        return False

    def ended(self) -> None:
        """The player reached the end of the clip."""
        self.index = self.count - 1
        self.playing = False


class ClipViewer(QtWidgets.QDialog):
    """The dialog: picture, slider, Previous / Next picture, Play with sound / Pause, Close. Keys: left and right arrow = one picture, space = play / pause."""

    def __init__(self, controller: ClipController, title: str = "Cut point", parent=None):
        super().__init__(parent)
        self.ctl = controller
        self.setWindowTitle(title)
        layout = QtWidgets.QVBoxLayout(self)
        num, _, den = controller.aspect.partition(":")
        self.stage_size = (STAGE_WIDTH, round(STAGE_WIDTH * int(den or 9) / int(num or 16)))
        # The stage has a fixed size and its two children (the picture, the video area of the player) fill it without a layout: the size of the dialog does not depend on what is
        # shown (a label that scales its picture to its own size, or a video area that grows with the video, made the dialog grow to the height of the screen).
        self.stage = QtWidgets.QWidget()
        self.stage.setFixedSize(*self.stage_size)
        self.picture = QtWidgets.QLabel(self.stage)
        self.picture.setGeometry(0, 0, *self.stage_size)
        self.video = QtWidgets.QWidget(self.stage)                    # the video area of the player while it plays
        self.video.setGeometry(0, 0, *self.stage_size)
        self.video.hide()
        layout.addWidget(self.stage)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, max(0, controller.count - 1))
        self.slider.valueChanged.connect(self.slider_moved)
        layout.addWidget(self.slider)
        self.caption = QtWidgets.QLabel()
        layout.addWidget(self.caption)
        row = QtWidgets.QHBoxLayout()
        self.previous = QtWidgets.QPushButton("◀ Previous picture (←)")
        self.next = QtWidgets.QPushButton("Next picture (→) ▶")
        self.play_button = QtWidgets.QPushButton("Play with sound (Space)")
        self.close_button = QtWidgets.QPushButton("Close")
        self.previous.clicked.connect(lambda: self.step(-1))
        self.next.clicked.connect(lambda: self.step(1))
        self.play_button.clicked.connect(self.toggle)
        self.close_button.clicked.connect(self.close)
        for b in (self.previous, self.next, self.play_button, self.close_button):
            row.addWidget(b)
        layout.addLayout(row)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tick)
        if controller.player is not None:
            controller.player.attach(self.video)
            controller.player.set_aspect(controller.aspect)
            controller.player.ended.connect(self.clip_ended)
        self.refresh()

    def refresh(self) -> None:
        """Shows the picture the controller points to."""
        pixmap = QtGui.QPixmap(self.ctl.file())
        self.picture.setPixmap(pixmap.scaled(*self.stage_size, QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                                             QtCore.Qt.TransformationMode.SmoothTransformation))
        self.slider.blockSignals(True)
        self.slider.setValue(self.ctl.index)
        self.slider.blockSignals(False)
        self.caption.setText(self.ctl.label())
        self.play_button.setText("Pause (Space)" if self.ctl.playing else "Play with sound (Space)")

    def show_video(self, on: bool) -> None:
        self.video.setVisible(on)
        self.picture.setVisible(not on)

    def step(self, delta: int) -> None:
        self.timer.stop()
        self.ctl.step(delta)
        self.show_video(False)
        self.refresh()

    def slider_moved(self, value: int) -> None:
        self.timer.stop()
        self.ctl.show(value)
        self.show_video(False)
        self.refresh()

    def toggle(self) -> None:
        if self.ctl.toggle():
            self.show_video(True)
            self.timer.start()
        else:
            self.timer.stop()
            self.show_video(False)
        self.refresh()

    def tick(self) -> None:
        if self.ctl.playing and not self.ctl.follow():
            self.clip_ended()
            return
        self.caption.setText(self.ctl.label())
        self.slider.blockSignals(True)
        self.slider.setValue(self.ctl.index)
        self.slider.blockSignals(False)

    def clip_ended(self) -> None:
        self.timer.stop()
        self.ctl.ended()
        self.show_video(False)
        self.refresh()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == QtCore.Qt.Key.Key_Left:
            self.step(-1)
        elif key == QtCore.Qt.Key.Key_Right:
            self.step(1)
        elif key == QtCore.Qt.Key.Key_Space:
            self.toggle()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.timer.stop()
        if self.ctl.player is not None:
            self.ctl.player.shutdown()
        super().closeEvent(event)
