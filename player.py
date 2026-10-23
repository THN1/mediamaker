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

    def show_at(self, ms: int) -> None:
        """Shows the picture at `ms` in the paused state (briefly start playback, jump, pause)."""
        raise NotImplementedError

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


def debug_log(text: str) -> None:
    """With MEDIAMAKER_DEBUG=1 events and jumps of the playback are logged in mediamaker_debug.log."""
    if os.environ.get("MEDIAMAKER_DEBUG"):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mediamaker_debug.log"), "a") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {text}\n")


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
        self.shut_down = False
        self.log: list[str] = []

    def shutdown(self) -> None:
        self.shut_down = True
        self._state = "stopped"

    def attach(self, widget) -> None:
        self.attached = widget

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

    def show_at(self, ms: int) -> None:
        self.log.append(f"show_at {ms}")
        self.time = ms
        self._state = "paused"
        self.time_changed.emit(ms)
        self.paused.emit()

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
        self._dispose_thread = None
        self._volume: Optional[int] = None
        self._slow = False                                      # jumps in the open medium are slow (network drive): every jump reloads the medium
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
        self._replace_player()
        if self._path and self._last_show is not None:
            self.show_at(self._last_show)

    def _replace_player(self) -> None:
        """Puts a new media player in place of the old one without waiting for it: libvlc's stop() blocks as long as the input thread is busy
        (on a slow network drive a jump can take seconds), and that would freeze the window. The old one is stopped and released in a thread."""
        old = self.mp
        try:
            events = old.event_manager()
            for event_type in self._event_types:
                events.event_detach(event_type)
        except Exception as e:
            debug_log(f"detaching the events of the old media player failed: {e}")
        self._old_callbacks.extend(self._callbacks)              # libvlc may still call them
        self._old_players.append(old)                            # kept alive for the same reason
        self._dispose_thread = threading.Thread(target=self._dispose, args=(old,), daemon=True)
        self._dispose_thread.start()
        self._pending_show = self._awaiting_position = None
        self._muted = False
        self._watch_token += 1
        self._new_media_player()
        self._after_recover()
        if self._volume is not None:
            self.mp.audio_set_volume(self._volume)

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
        if self._slow and not self._closed:
            self._replace_player()                               # stopping would block for seconds: new media player instead
            return
        if self._muted:
            self._mute(False)
        self.mp.stop()

    def show_at(self, ms: int) -> None:
        State = self._vlc.State
        if self.mp.get_state() in (State.Playing, State.Paused):
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
        self._volume = int(percent)
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

    frame_ready = QtCore.Signal(object)                          # (bytes, width, height) in the Qt thread

    def __init__(self, extra_args: str = ""):
        super().__init__(extra_args)
        self.surface: Optional[VideoSurface] = None
        self._frames_shown = 0                                   # counter of the pictures shown (for checking jumps)
        self._reload_busy = False                                # slow medium: a reload is running, jumps are collected
        self._reload_for: Optional[int] = None                   # position that the running reload was started for
        self._reload_target: Optional[int] = None                # latest position that was asked for in the meantime
        self._seek_time: Optional[float] = None                  # when the last jump or reload was started (log of the delay)
        self._last_seek: Optional[int] = None
        self._size = (0, 0)
        self._buf = None
        self._video_callbacks = []                               # never release: libvlc might still call them
        self.frame_ready.connect(self._on_frame)

    def attach(self, widget) -> None:
        self.surface = VideoSurface(widget)
        self.surface.setGeometry(0, 0, widget.width(), widget.height())
        self.surface.show()

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
                self.frame_ready.emit((bytes(buf), width, height))

        self._video_callbacks.append((lock, display, buf))
        self.mp.video_set_callbacks(lock, None, display, None)
        self.mp.video_set_format("RV32", width, height, width * 4)
        self.mp.video_set_aspect_ratio(f"{width}:{height}")      # picture fills the memory area without black borders of its own
        debug_log(f"memory output {width}x{height}")

    def _after_recover(self) -> None:
        size, self._size = self._size, (0, 0)                    # the new media player knows nothing yet: install the video callbacks again
        if size != (0, 0):
            self._install(*size)

    def _position_reached(self, ms: int) -> None:
        """Position reached: show pictures again. The picture VLC has already delivered was discarded; another
                jump in the paused state delivers one for this position."""
        super()._position_reached(ms)
        self.mp.set_time(ms)

    def _on_frame(self, frame) -> None:
        data, width, height = frame
        self._progress += 1
        if self._awaiting_position is not None:
            return                                           # VLC still shows the wrong position (e.g. the start of the file)
        if self._seek_time is not None:
            debug_log(f"picture {1000 * (time.monotonic() - self._seek_time):.0f} ms after the {'reload' if self._reload_busy else 'jump'}")
            self._seek_time = None
        if self.surface is not None and not self._closed:
            image = QtGui.QImage(data, width, height, width * 4, QtGui.QImage.Format.Format_RGB32).copy()
            self.surface.set_image(image)
            self._frames_shown += 1
        self._reload_finished()

    SEEK_CHECK_MS = 600                                          # how long to wait for the picture after a jump
    SEEK_CHECK_MIN_DISTANCE_MS = 100                             # closer jumps sometimes deliver no new picture

    RELOAD_MAX_MS = 6000                                         # a reload that brings no picture for so long is given up (the watchdog replaces the player)

    def _request_reload(self, ms: int) -> None:
        """Slow medium: the medium is opened anew at the position (that is fast, while a jump in the open medium takes seconds). While a reload
        is running further requests only keep the latest position; it is reloaded as soon as the picture of the running one has arrived."""
        self._reload_target = ms
        if self._reload_busy:
            return
        self._start_reload(ms)

    def _start_reload(self, ms: int) -> None:
        self._reload_busy = True
        self._reload_for = ms
        self._last_seek = ms
        self._seek_time = time.monotonic()
        debug_log(f"slow medium: reloading at {ms} ms")
        self._replace_player()
        self.show_at(ms)
        token = self._watch_token
        QtCore.QTimer.singleShot(self.RELOAD_MAX_MS, lambda: self._reload_timeout(token))

    def _reload_finished(self) -> None:
        """A picture has arrived: the running reload is done; the latest position asked for meanwhile is reloaded next."""
        if not self._reload_busy or self._awaiting_position is not None or self._closed:
            return
        self._reload_busy = False
        if self._reload_target is not None and self._reload_target != self._reload_for:
            self._start_reload(self._reload_target)

    def _reload_timeout(self, token: int) -> None:
        if self._reload_busy and token == self._watch_token and not self._closed:
            self._reload_busy = False                            # give up this one; the watchdog has looked at the player already
            if self._reload_target is not None and self._reload_target != self._reload_for:
                self._start_reload(self._reload_target)

    def _do_seek(self, ms: int) -> None:
        """Jump as in the base class; in the paused state a picture must arrive afterwards. VLC ignores some jumps
                (e.g. to the start of the file); then the medium is reloaded with the start position."""
        if self._slow and self.mp.get_state() in (self._vlc.State.Paused, self._vlc.State.Stopped, self._vlc.State.Playing):
            self._request_reload(ms)
            return
        before, here = self._frames_shown, self.mp.get_time()
        self._seek_time = time.monotonic()
        super()._do_seek(ms)
        self._last_seek = ms
        if self.mp.get_state() == self._vlc.State.Paused and abs(here - ms) > self.SEEK_CHECK_MIN_DISTANCE_MS:
            QtCore.QTimer.singleShot(self.SEEK_CHECK_MS, lambda: self._verify_seek(ms, before))

    def _verify_seek(self, ms: int, frames_before: int) -> None:
        if self._closed or self._awaiting_position is not None or self._last_seek != ms:
            return                                               # superseded: another jump has come in the meantime
        if self._frames_shown == frames_before and self.mp.get_state() == self._vlc.State.Paused:
            self._last_show = ms
            debug_log(f"jump to {ms} ms delivered no picture: the medium is slow, reloading it from now on for every jump")
            self._slow = True
            self._request_reload(ms)

    def load(self, path: str, size: Optional[tuple] = None) -> None:
        self.stop()                                              # change the memory only without running playback
        self._slow = False                                       # a new file: judge its speed anew
        self._reload_busy = False
        self._reload_target = None
        self._install(*(size or (720, 576)))
        if self.surface is not None:
            self.surface.clear()
        super().load(path, size)

    def set_aspect(self, ratio: str) -> None:
        """Display format in the video area, e.g. "16:9" (the pictures are stretched accordingly)."""
        if self.surface is not None:
            num, _, den = ratio.partition(":")
            self.surface.set_aspect(int(num), int(den))
