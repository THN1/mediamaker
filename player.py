"""Playback: a small interface and two implementations (python-vlc and a replacement for tests).

The user interface only knows the class Player. It needs the same things the VB6 program used from the VLC control:
load, play, pause, stop, read and set time (in milliseconds), volume, aspect ratio and
five events (playing, pause, stop, end, time change). Another engine (e.g. QtMultimedia) can be inserted later
by another subclass.
"""
from __future__ import annotations

import ctypes
import os
import shlex
import sys
import threading
import time
from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets


class Player(QtCore.QObject):
    playing = QtCore.Signal()
    paused = QtCore.Signal()
    stopped = QtCore.Signal()
    ended = QtCore.Signal()
    time_changed = QtCore.Signal(int)          # milliseconds

    def attach(self, widget) -> None:
        """Set the video area (a control of the user interface)."""
        raise NotImplementedError

    def fit(self, widget) -> None:
        """The video area has got another size (the form is scaled after the player was attached): the picture follows."""

    def shutdown(self) -> None:
        """End playback and release all resources. Must run before the window is closed and may be
                called several times."""

    def load(self, path: str, size: Optional[tuple] = None) -> None:
        """Load a file. `size` = (width, height) of the video in pixels; only needed for players that deliver the pictures themselves."""
        raise NotImplementedError

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        """Stops and removes the last picture from the display (the list of segments was emptied: no film is shown any more)."""
        self.stop()

    def preview_image(self):
        """A copy of the picture the preview shows right now (QImage), or None (no picture, or the video is drawn by VLC itself)."""
        return None

    def show_at(self, ms: int) -> None:
        """Shows the picture at `ms` in the paused state (briefly start playback, jump, pause)."""
        raise NotImplementedError

    def play_at(self, ms: int) -> None:
        """Plays from `ms`. Used when the picture on screen did not come from the player (the pictures of a search stay on screen, see seek_done), so the player is not
        where the slider is, and may not even have been started."""
        self.set_time(ms)
        self.play()

    def describe(self) -> str:
        """What the player knows about itself, for the debug log."""
        return ""

    supports_images = False                                  # can the program put its own pictures into the preview (show_image)? Only the memory player.
    images_only = False                                      # True while a search shows its pictures: the player draws nothing of its own then (a late picture of VLC, e.g. the first
                                                             # picture of the segment, would flicker in between)

    def show_image(self, image) -> None:
        """Shows a picture (QImage) from outside in the preview (the still pictures of ffmpeg, see stills.py)."""

    @property
    def is_started(self) -> bool:
        """Is a film started in the player (running or paused at a position), so that it can be told to jump? Before that the first picture comes via show_at."""
        return False

    @property
    def is_playing(self) -> bool:
        raise NotImplementedError

    @property
    def has_media(self) -> bool:
        raise NotImplementedError

    def get_time(self) -> int:
        raise NotImplementedError

    def set_time(self, ms: int) -> None:
        raise NotImplementedError

    def set_volume(self, percent: int) -> None:
        raise NotImplementedError

    def set_aspect(self, ratio: str) -> None:
        raise NotImplementedError


class SeekThrottle(QtCore.QObject):
    """Combines rapid sequences of jumps.

        The first jump is executed immediately, further ones at most every `interval` milliseconds, always with the
        most recently requested value. This way dragging the slider does not flood the playback with jumps, and the
        end position is still reached reliably.
    """

    def __init__(self, action: Callable[[int], None], interval: int = 40):
        super().__init__()
        self.action, self.interval = action, interval
        self._pending: Optional[int] = None
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fire)

    def request(self, value: int) -> None:
        if self.timer.isActive():
            self._pending = value
        else:
            self.action(value)
            self.timer.start(self.interval)

    def _fire(self) -> None:
        if self._pending is not None:
            value, self._pending = self._pending, None
            self.action(value)
            self.timer.start(self.interval)


def log_line(text: str, now: Optional[float] = None) -> str:
    """A line of the debug log: time with milliseconds (the steps of a preview follow each other within fractions of a second), then the text."""
    now = time.time() if now is None else now
    return f"{time.strftime('%H:%M:%S', time.localtime(now))}.{int((now % 1) * 1000):03d} {text}\n"


def debug_log(text) -> None:
    """With MEDIAMAKER_DEBUG=1 events and jumps of the playback are logged in mediamaker_debug.log. `text` can be a function that makes the text: it is only called
    when the log is on (what it asks of VLC costs time and must not happen otherwise)."""
    if os.environ.get("MEDIAMAKER_DEBUG"):
        with open(__import__("version").debug_log_path(), "a") as fh:
            fh.write(log_line(text() if callable(text) else text))


class FakePlayer(Player):
    """Replacement without picture and sound: only stores state and time and triggers the events (for tests)."""

    def __init__(self):
        super().__init__()
        self.path: Optional[str] = None
        self.time = 0
        self.volume = 100
        self.aspect = ""
        self._state = "stopped"
        self.attached = None
        self.fitted = []
        self.shut_down = False
        self.log: list[str] = []

    def shutdown(self) -> None:
        self.shut_down = True
        self._state = "stopped"

    def attach(self, widget) -> None:
        self.attached = widget

    def fit(self, widget) -> None:
        self.fitted.append(widget)

    def load(self, path: str, size: Optional[tuple] = None) -> None:
        self.path, self.time, self.size = path, 0, size
        self.log.append(f"load {path}")

    def play(self) -> None:
        self._state = "playing"
        self.log.append("play")
        self.playing.emit()

    def pause(self) -> None:
        if self._state == "playing":
            self._state = "paused"
            self.log.append("pause")
            self.paused.emit()

    def stop(self) -> None:
        self._state = "stopped"
        self.log.append("stop")
        self.stopped.emit()

    def clear(self) -> None:
        self.log.append("clear")
        self.stop()

    def preview_image(self):
        return getattr(self, "preview", None)

    supports_images = True

    def show_image(self, image) -> None:
        self.log.append("image")
        self.preview = image

    @property
    def is_started(self) -> bool:
        return self._state in ("playing", "paused")

    def show_at(self, ms: int) -> None:
        self.log.append(f"show_at {ms}")
        self.time = ms
        self._state = "paused"
        self.time_changed.emit(ms)
        self.paused.emit()

    def play_at(self, ms: int) -> None:
        self.log.append(f"play_at {ms}")
        self.time = ms
        self._state = "playing"
        self.time_changed.emit(ms)

    @property
    def is_playing(self) -> bool:
        return self._state == "playing"

    @property
    def has_media(self) -> bool:
        return self.path is not None

    def get_time(self) -> int:
        return self.time

    def set_time(self, ms: int) -> None:
        self.time = ms
        self.time_changed.emit(ms)

    def set_volume(self, percent: int) -> None:
        self.volume = percent

    def set_aspect(self, ratio: str) -> None:
        self.aspect = ratio

    def tick(self, ms: int) -> None:
        """Simulates playback time."""
        self.time += ms
        self.time_changed.emit(self.time)


class VlcPlayer(Player):
    """Playback with libvlc (python-vlc). Under Linux it draws into an X11 window (under Wayland via
        XWayland, i.e. with QT_QPA_PLATFORM=xcb)."""

    seekable = QtCore.Signal(bool)                               # VLC can seek (or no longer can)

    def __init__(self, extra_args: str = ""):
        super().__init__()
        import vlc                                              # only here, so that the module can be loaded without VLC
        self._vlc = vlc
        # Hardware decoding off: when jumping in the paused state the preview got stuck after about 20 frames
        # (the supply of hardware surfaces is limited). Software decoding is enough for SD/HD television recordings.
        # More arguments: entry vlc_args= in the section [settings] of the INI file (permanent) or environment variable
        # MEDIAMAKER_VLC_ARGS (for experiments), e.g. "--vout=xcb_x11". Later specifications override earlier ones.
        args = (["--quiet", "--no-video-title-show", "--avcodec-hw=none"] + shlex.split(extra_args)
                + shlex.split(os.environ.get("MEDIAMAKER_VLC_ARGS", "")))
        debug_log(f"VLC arguments: {args}")
        self.instance = vlc.Instance(*args)
        self._pending_show: Optional[int] = None
        self._awaiting_position: Optional[int] = None         # still picture is requested, VLC is not there yet
        self._path: Optional[str] = None
        self._closed = False
        self._throttle = SeekThrottle(self._do_seek)
        self._widget = None                                     # window of the video output (for a new media player)
        self._progress = 0                                      # counts what VLC reports (events, pictures): the watchdog looks at it
        self._watch_token = 0
        self._last_show: Optional[int] = None                   # last position that was requested for a new medium
        self.recoveries = 0                                     # how often the media player had to be replaced
        self._old_callbacks: list = []                          # libvlc may still call the functions of replaced media players
        self._old_players: list = []
        self._new_media_player()
        self.playing.connect(self._after_playing)
        self.seekable.connect(self._after_seekable)
        self._muted = False

    def _new_media_player(self) -> None:
        """Creates the libvlc media player and attaches the events (at the start and after a recovery)."""
        vlc = self._vlc
        self.mp = self.instance.media_player_new()
        self._callbacks = []                                    # keep references, otherwise Python cleans up the functions
        self._event_types = []
        events = self.mp.event_manager()
        T = vlc.EventType
        for event_type, signal in ((T.MediaPlayerPlaying, self.playing), (T.MediaPlayerPaused, self.paused),
                                   (T.MediaPlayerStopped, self.stopped), (T.MediaPlayerEndReached, self.ended)):
            cb = (lambda event, sig=signal, name=str(event_type): self._on_event(sig, name))
            self._callbacks.append(cb)
            self._event_types.append(event_type)
            events.event_attach(event_type, cb)
        sk = (lambda event: self._on_seekable(bool(event.u.new_seekable)))
        self._callbacks.append(sk)
        self._event_types.append(T.MediaPlayerSeekableChanged)
        events.event_attach(T.MediaPlayerSeekableChanged, sk)
        tc = (lambda event: self._on_time(int(event.u.new_time)))
        self._callbacks.append(tc)
        self._event_types.append(T.MediaPlayerTimeChanged)
        events.event_attach(T.MediaPlayerTimeChanged, tc)

    # These functions run in the VLC thread; after shutdown they must not trigger Qt signals any more.
    def _on_event(self, signal, name: str) -> None:
        if not self._closed:
            self._progress += 1
            debug_log(f"event {name}")
            signal.emit()

    def _on_time(self, ms: int) -> None:
        if not self._closed:
            self._progress += 1
            self.time_changed.emit(ms)

    def _on_seekable(self, flag: bool) -> None:
        if not self._closed:
            self._progress += 1
            debug_log(f"event seekable={flag}")
            self.seekable.emit(flag)

    def _after_seekable(self, flag: bool) -> None:
        """In the Qt thread: as soon as VLC can seek (this is usually earlier than "Playing"), it jumps to the requested position,
                so that as little as possible of the start of the file is heard or seen."""
        if flag and self._awaiting_position is not None and not self._closed:
            debug_log(f"seekable: jumping to {self._awaiting_position} ms")
            self.mp.set_time(self._awaiting_position)

    def _mute(self, on: bool) -> None:
        """Mute the sound while approaching a position (only works if the audio output already exists)."""
        try:
            self.mp.audio_set_mute(bool(on))
            self._muted = bool(on)
        except Exception:
            self._muted = False

    def shutdown(self) -> None:
        """Orderly shutdown: first detach the callbacks, then stop (waits until VLC no longer draws the picture),
                then release. When the window is closed in the middle of playback otherwise: memory access error, because VLC draws into a
                window that Qt has already torn down, or a callback addresses a Qt object that no longer exists."""
        if self._closed:
            return
        self._closed = True
        debug_log("shutdown")
        self._watch_token += 1
        self._pending_show = None
        self._throttle.timer.stop()
        try:
            events = self.mp.event_manager()
            for event_type in self._event_types:
                events.event_detach(event_type)
            self.mp.stop()
            self.mp.release()
            self.instance.release()
        except Exception as e:                                  # never fail with an error during shutdown
            debug_log(f"Error during shutdown: {e}")
        self._callbacks.clear()

    def _after_playing(self) -> None:
        """In the Qt thread, as soon as VLC reports that playback is running: pause and wait for the start position."""
        if self._pending_show is not None and not self._closed:
            ms, self._pending_show = self._pending_show, None
            debug_log(lambda: f"VLC plays: pausing, waiting for {ms} ms ({self.describe()})")
            self.mp.set_pause(1)
            self._mute(True)
            self._await_position(ms, 0)

    # The start position comes via the media option start-time. If VLC ignores it (a jump right after the
    # start is often ignored), it is checked every 150 ms and, if necessary, jumped again until VLC is at the position.
    POSITION_TOLERANCE_MS = 1500
    POSITION_TRIES = 30                                      # about 4.5 seconds

    def _await_position(self, ms: int, tries: int) -> None:
        QtCore.QTimer.singleShot(150, lambda: self._check_position(ms, tries))

    def _check_position(self, ms: int, tries: int) -> None:
        if self._closed or self._awaiting_position != ms:
            return                                           # superseded (another frame requested, stopped)
        now = self.mp.get_time()
        if abs(now - ms) <= self.POSITION_TOLERANCE_MS or tries >= self.POSITION_TRIES:
            self._position_reached(ms)
            return
        debug_log(f"start position {ms} ms not reached yet (VLC is at {now} ms): jumping, attempt {tries + 1}")
        self.mp.set_time(ms)
        self._await_position(ms, tries + 1)

    def _position_reached(self, ms: int) -> None:
        debug_log(lambda: f"position {ms} ms reached ({self.describe()})")
        self._awaiting_position = None
        if self._muted:
            self._mute(False)

    # ------------------------------------------------------------------ Recovery of a stuck preview
    # With a recording on a network drive (slow, sometimes blocking reads) libvlc can get stuck: the opening of a medium never ends, no picture comes
    # any more, and further jumps change nothing. If nothing is reported for WATCHDOG_MS after a medium was started, the media player is replaced by
    # a new one (the old one is stopped in a thread of its own, because stopping can block) and the last position is requested again.
    WATCHDOG_MS = 8000

    def _start_watchdog(self) -> None:
        self._watch_token += 1
        token, progress = self._watch_token, self._progress
        QtCore.QTimer.singleShot(self.WATCHDOG_MS, lambda: self._watchdog(token, progress))

    def _watchdog(self, token: int, progress: int) -> None:
        if self._closed or token != self._watch_token:
            return                                               # superseded (stopped, another request, shutdown)
        if self._progress == progress:
            self.recover(f"nothing reported by VLC for {self.WATCHDOG_MS} ms")

    def recover(self, reason: str) -> None:
        """Replaces the media player by a new one and requests the last position again."""
        if self._closed:
            return
        self.recoveries += 1
        debug_log(f"RECOVERY {self.recoveries} ({reason}): new media player")
        old = self.mp
        try:
            events = old.event_manager()
            for event_type in self._event_types:
                events.event_detach(event_type)
        except Exception as e:
            debug_log(f"detaching the events of the old media player failed: {e}")
        self._old_callbacks.extend(self._callbacks)              # libvlc may still call them
        self._old_players.append(old)                            # kept alive for the same reason
        threading.Thread(target=self._dispose, args=(old,), daemon=True).start()
        self._pending_show = self._awaiting_position = None
        self._muted = False
        self._watch_token += 1
        self._new_media_player()
        self._after_recover()
        if self._path and self._last_show is not None:
            self.show_at(self._last_show)

    @staticmethod
    def _dispose(old) -> None:
        """Stops and releases a replaced media player (may block, therefore not in the Qt thread)."""
        try:
            old.stop()
            old.release()
        except Exception as e:
            debug_log(f"disposing of the old media player failed: {e}")

    def _after_recover(self) -> None:
        """The new media player needs its video output again."""
        if self._widget is not None:
            self.attach(self._widget)

    def attach(self, widget) -> None:
        self._widget = widget
        win_id = int(widget.winId())
        if sys.platform.startswith("linux"):
            self.mp.set_xwindow(win_id)
        elif sys.platform == "win32":
            self.mp.set_hwnd(win_id)
        elif sys.platform == "darwin":
            self.mp.set_nsobject(win_id)

    def load(self, path: str, size: Optional[tuple] = None) -> None:
        self._path = path
        self.mp.set_media(self.instance.media_new_path(path))

    def play(self) -> None:
        self._awaiting_position = None                         # the user starts: stop waiting, sound on
        if self._muted:
            self._mute(False)
        self.mp.play()

    def pause(self) -> None:
        if self.mp.is_playing():
            self.mp.set_pause(1)

    def stop(self) -> None:
        self._pending_show = None
        self._awaiting_position = None
        self._watch_token += 1
        if self._muted:
            self._mute(False)
        self.mp.stop()

    def describe(self) -> str:
        try:
            return (f"state={self.mp.get_state()} playing={self.mp.is_playing()} time={self.mp.get_time()} awaiting={self._awaiting_position} "
                    f"pending={self._pending_show} muted={self._muted}")
        except Exception as e:
            return f"(not readable: {e})"

    def show_at(self, ms: int) -> None:
        State = self._vlc.State
        if self.mp.get_state() in (State.Playing, State.Paused):
            debug_log(lambda: f"show_at {ms} ms: the medium is started already, jump without flags ({self.describe()})")
            self.mp.set_time(ms)
            if self.mp.is_playing():
                self.mp.set_pause(1)
        else:
            # New medium: a jump right after the start is often ignored by VLC. The reliable way is the
            # media option start-time, with which playback starts at the desired position right away.
            self._pending_show = ms
            self._awaiting_position = ms
            self._last_show = ms
            debug_log(f"show_at {ms} ms (Medium {self._path})")
            if self._path:
                media = self.instance.media_new_path(self._path)
                media.add_option(f":start-time={ms / 1000:.3f}")
                self.mp.set_media(media)
            self.mp.play()
            self._mute(True)
            self._start_watchdog()

    def play_at(self, ms: int) -> None:
        """Plays from `ms`: a medium that is started jumps there and goes on; one that was only loaded (never started) starts there (media option start-time, as in show_at,
        but without the pause afterwards)."""
        State = self._vlc.State
        if self.mp.get_state() in (State.Playing, State.Paused):
            debug_log(lambda: f"play_at {ms} ms: the medium is started, jump and play ({self.describe()})")
            self.mp.set_time(ms)
            self.play()
        else:
            debug_log(lambda: f"play_at {ms} ms: new medium {self._path} ({self.describe()})")
            self._pending_show = self._awaiting_position = None
            self._last_show = ms
            if self._path:
                media = self.instance.media_new_path(self._path)
                media.add_option(f":start-time={ms / 1000:.3f}")
                self.mp.set_media(media)
            self.mp.play()
            self._start_watchdog()

    @property
    def is_playing(self) -> bool:
        return bool(self.mp.is_playing())

    @property
    def has_media(self) -> bool:
        return self.mp.get_media() is not None

    def get_time(self) -> int:
        return int(self.mp.get_time())

    def set_time(self, ms: int) -> None:
        self._throttle.request(int(ms))

    def _do_seek(self, ms: int) -> None:
        if self._closed:
            return
        debug_log(f"set_time {ms} (state {self.mp.get_state()})")
        self.mp.set_time(ms)

    def set_volume(self, percent: int) -> None:
        self.mp.audio_set_volume(int(percent))

    def set_aspect(self, ratio: str) -> None:
        self.mp.video_set_aspect_ratio(ratio)


# ----------------------------------------------------------------------------- Playback into memory
def fit_rect(width: int, height: int, aspect: tuple) -> tuple:
    """Largest rectangle with the aspect ratio `aspect` (width, height) that fits into width x height, centred."""
    num, den = aspect
    if width <= 0 or height <= 0 or num <= 0 or den <= 0:
        return (0, 0, max(width, 0), max(height, 0))
    if width * den > height * num:                              # area is wider than the picture: the height decides
        rw, rh = round(height * num / den), height
    else:
        rw, rh = width, round(width * den / num)
    return ((width - rw) // 2, (height - rh) // 2, rw, rh)


class VideoSurface(QtWidgets.QWidget):
    """Drawing area for the player's pictures; fills the video area of the window, black border for another format."""

    def __init__(self, parent):
        super().__init__(parent)
        self.image = None
        self.aspect = (16, 9)

    def set_image(self, image) -> None:
        self.image = image
        self.update()

    def clear(self) -> None:
        self.image = None
        self.update()

    def set_aspect(self, num: int, den: int) -> None:
        self.aspect = (num, den)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0))
        if self.image is not None:
            x, y, w, h = fit_rect(self.width(), self.height(), self.aspect)
            painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(QtCore.QRect(x, y, w, h), self.image)
        painter.end()


class MemoryVlcPlayer(VlcPlayer):
    """libvlc decodes into a memory area (no VLC window, no VLC video output); Qt draws the pictures.

        Advantages over embedding into an X11 window: runs natively under Wayland (no XWayland needed), and the
        freezing of the preview after about 20 jumps, which came from the video output of VLC, can no longer occur.
    """

    FRAME_POLL_MS = 8                                            # how often the Qt thread looks for a new picture of VLC

    def __init__(self, extra_args: str = ""):
        super().__init__(extra_args)
        self.surface: Optional[VideoSurface] = None
        self._frames_shown = 0                                   # counter of the pictures shown (for checking jumps)
        self._reloads = 0                                        # reloads in a row that did not bring a picture
        self._last_seek: Optional[int] = None
        self._size = (0, 0)
        self._buf = None
        self._video_callbacks = []                               # never release: libvlc might still call them
        # The VLC thread only stores the picture (plain Python, no Qt call at all: a Qt signal with a Python object from a thread that Qt does not know
        # damaged reference counts - "free(): invalid pointer", "deallocating None" at the end of the program); the Qt thread fetches it with a timer.
        self._frame_lock = threading.Lock()
        self._latest_frame = None
        self._frame_timer = QtCore.QTimer(self)
        self._frame_timer.setInterval(self.FRAME_POLL_MS)
        self._frame_timer.timeout.connect(self._poll_frame)
        self._frame_timer.start()

    def attach(self, widget) -> None:
        self.surface = VideoSurface(widget)
        self.surface.setGeometry(0, 0, widget.width(), widget.height())
        self.surface.show()

    def fit(self, widget) -> None:
        if self.surface is not None:
            self.surface.setGeometry(0, 0, widget.width(), widget.height())

    def _install(self, width: int, height: int) -> None:
        """Set up memory area and callbacks for a video of this size (only call in the paused state)."""
        width, height = int(width) & ~1, int(height) & ~1
        if (width, height) == self._size:
            return
        self._size = (width, height)
        self._buf = (ctypes.c_ubyte * (width * height * 4))()
        pointer = ctypes.cast(self._buf, ctypes.c_void_p)
        buf = self._buf
        deco = self._vlc.CallbackDecorators

        @deco.VideoLockCb
        def lock(opaque, planes):                                # VLC asks: where should the next picture go?
            planes[0] = pointer
            return None

        @deco.VideoDisplayCb
        def display(opaque, picture):                            # runs in the VLC thread: pass a copy on to Qt
            if not self._closed:
                frame = (bytes(buf), width, height)
                with self._frame_lock:
                    self._latest_frame = frame

        self._video_callbacks.append((lock, display, buf))
        self.mp.video_set_callbacks(lock, None, display, None)
        self.mp.video_set_format("RV32", width, height, width * 4)
        self.mp.video_set_aspect_ratio(f"{width}:{height}")      # picture fills the memory area without black borders of its own
        debug_log(f"memory output {width}x{height}")

    def shutdown(self) -> None:
        self._frame_timer.stop()
        super().shutdown()

    def _after_recover(self) -> None:
        size, self._size = self._size, (0, 0)                    # the new media player knows nothing yet: install the video callbacks again
        self._reloads = 0
        if size != (0, 0):
            self._install(*size)

    def _position_reached(self, ms: int) -> None:
        """Position reached: show pictures again. The picture VLC has already delivered was discarded; another
                jump in the paused state delivers one for this position."""
        super()._position_reached(ms)
        self.mp.set_time(ms)

    def _poll_frame(self) -> None:
        """In the Qt thread: shows the newest picture that the VLC thread has stored (pictures that came in between are not needed)."""
        with self._frame_lock:
            frame, self._latest_frame = self._latest_frame, None
        if frame is not None and not self._closed:
            self._on_frame(frame)

    def _on_frame(self, frame) -> None:
        data, width, height = frame
        self._progress += 1
        if self._awaiting_position is not None:
            return                                           # VLC still shows the wrong position (e.g. the start of the file)
        if self.images_only:
            return                                           # a search shows its own pictures: nothing of VLC in between
        self._reloads = 0
        if self.surface is not None and not self._closed:
            image = QtGui.QImage(data, width, height, width * 4, QtGui.QImage.Format.Format_RGB32).copy()
            self.surface.set_image(image)
            self._frames_shown += 1

    SEEK_CHECK_MS = 600                                          # how long to wait for the picture after a jump
    MAX_RELOADS = 2                                              # reloads of the medium in a row before the media player is replaced
    SEEK_CHECK_MIN_DISTANCE_MS = 100                             # closer jumps sometimes deliver no new picture

    def _do_seek(self, ms: int) -> None:
        """Jump as in the base class; in the paused state a picture must arrive afterwards. VLC ignores some jumps
                (e.g. to the start of the file); then the medium is reloaded with the start position."""
        before, here = self._frames_shown, self.mp.get_time()
        super()._do_seek(ms)
        self._last_seek = ms
        if self.mp.get_state() == self._vlc.State.Paused and abs(here - ms) > self.SEEK_CHECK_MIN_DISTANCE_MS:
            QtCore.QTimer.singleShot(self.SEEK_CHECK_MS, lambda: self._verify_seek(ms, before))

    def _verify_seek(self, ms: int, frames_before: int) -> None:
        if self._closed or self._awaiting_position is not None or self._last_seek != ms or self.images_only:
            return                                               # superseded: another jump has come in the meantime
        if self._frames_shown == frames_before and self.mp.get_state() == self._vlc.State.Paused:
            self._reloads += 1
            self._last_show = ms
            if self._reloads > self.MAX_RELOADS:                 # reloading does not help: replace the media player
                self.recover(f"{self._reloads - 1} reloads in a row brought no picture")
                return
            debug_log(f"jump to {ms} ms delivered no picture: reloading the medium")
            self.stop()
            self.show_at(ms)

    def clear(self) -> None:
        """Stops and removes the last picture from the drawing area."""
        self.stop()
        if self.surface is not None:
            self.surface.clear()

    def preview_image(self):
        image = self.surface.image if self.surface is not None else None
        return image.copy() if image is not None and hasattr(image, "copy") else image

    supports_images = True

    def show_image(self, image) -> None:
        if self.surface is not None and not self._closed:
            self.surface.set_image(image)

    @property
    def is_started(self) -> bool:
        State = self._vlc.State
        return not self._closed and self._awaiting_position is None and self.mp.get_state() in (State.Playing, State.Paused)

    def load(self, path: str, size: Optional[tuple] = None) -> None:
        self.stop()                                              # change the memory only without running playback
        self._install(*(size or (720, 576)))
        if self.surface is not None:
            self.surface.clear()
        super().load(path, size)

    def set_aspect(self, ratio: str) -> None:
        """Display format in the video area, e.g. "16:9" (the pictures are stretched accordingly)."""
        if self.surface is not None:
            num, _, den = ratio.partition(":")
            self.surface.set_aspect(int(num), int(den))
