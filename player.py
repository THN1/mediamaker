"""Wiedergabe: eine kleine Schnittstelle und zwei Umsetzungen (python-vlc und ein Ersatz für Tests).

Die Oberfläche kennt nur die Klasse Player. Sie braucht dieselben Dinge, die das VB6-Programm vom VLC-Steuerelement
benutzte: laden, abspielen, Pause, Stopp, Zeit lesen und setzen (in Millisekunden), Lautstärke, Seitenverhältnis und
fünf Ereignisse (Abspielen, Pause, Stopp, Ende, Zeitänderung). Eine andere Engine (z. B. QtMultimedia) lässt sich später
durch eine weitere Unterklasse einsetzen.
"""
from __future__ import annotations

import ctypes
import os
import shlex
import sys
import time
from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets


class Player(QtCore.QObject):
    playing = QtCore.Signal()
    paused = QtCore.Signal()
    stopped = QtCore.Signal()
    ended = QtCore.Signal()
    time_changed = QtCore.Signal(int)          # Millisekunden

    def attach(self, widget) -> None:
        """Videofläche festlegen (ein Steuerelement der Oberfläche)."""
        raise NotImplementedError

    def shutdown(self) -> None:
        """Wiedergabe beenden und alle Ressourcen freigeben. Muss vor dem Schließen des Fensters laufen und darf
        mehrfach aufgerufen werden."""

    def load(self, path: str, size: Optional[tuple] = None) -> None:
        """Datei laden. `size` = (Breite, Höhe) des Videos in Pixeln; nur für Spieler nötig, die selbst Bilder liefern."""
        raise NotImplementedError

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def show_at(self, ms: int) -> None:
        """Zeigt das Bild bei `ms` im angehaltenen Zustand (Wiedergabe kurz starten, springen, anhalten)."""
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
    """Fasst schnelle Folgen von Sprüngen zusammen.

    Der erste Sprung wird sofort ausgeführt, weitere höchstens alle `interval` Millisekunden, und zwar immer mit dem
    zuletzt angeforderten Wert. So überschwemmt das Ziehen am Schieber die Wiedergabe nicht mit Sprüngen, und die
    Endposition wird trotzdem sicher erreicht.
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
    """Mit MEDIAMAKER_DEBUG=1 werden Ereignisse und Sprünge der Wiedergabe in mediamaker_debug.log protokolliert."""
    if os.environ.get("MEDIAMAKER_DEBUG"):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mediamaker_debug.log"), "a") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {text}\n")


class FakePlayer(Player):
    """Ersatz ohne Bild und Ton: speichert nur Zustand und Zeit und löst die Ereignisse aus (für Tests)."""

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
        """Simuliert Wiedergabezeit."""
        self.time += ms
        self.time_changed.emit(self.time)


class VlcPlayer(Player):
    """Wiedergabe mit libvlc (python-vlc). Unter Linux wird in ein X11-Fenster gezeichnet (unter Wayland über
    XWayland, also mit QT_QPA_PLATFORM=xcb)."""

    seekable = QtCore.Signal(bool)                               # VLC kann springen (oder nicht mehr)

    def __init__(self, extra_args: str = ""):
        super().__init__()
        import vlc                                              # erst hier, damit das Modul auch ohne VLC ladbar ist
        self._vlc = vlc
        # Hardware-Dekodierung aus: Bei Sprüngen im angehaltenen Zustand blieb die Vorschau nach etwa 20 Bildern stehen
        # (der Vorrat an Hardware-Oberflächen ist begrenzt). Für SD-/HD-Fernsehaufnahmen reicht die Software-Dekodierung.
        # Weitere Argumente: Eintrag vlc_args= im Abschnitt [settings] der INI-Datei (dauerhaft) oder Umgebungsvariable
        # MEDIAMAKER_VLC_ARGS (für Versuche), z. B. "--vout=xcb_x11". Spätere Angaben überstimmen frühere.
        args = (["--quiet", "--no-video-title-show", "--avcodec-hw=none"] + shlex.split(extra_args)
                + shlex.split(os.environ.get("MEDIAMAKER_VLC_ARGS", "")))
        debug_log(f"VLC-Argumente: {args}")
        self.instance = vlc.Instance(*args)
        self.mp = self.instance.media_player_new()
        self._pending_show: Optional[int] = None
        self._awaiting_position: Optional[int] = None         # Standbild wird angefordert, VLC ist noch nicht dort
        self._path: Optional[str] = None
        self._closed = False
        self._throttle = SeekThrottle(self._do_seek)
        self._callbacks = []                                    # Referenzen halten, sonst räumt Python die Funktionen ab
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
        self.playing.connect(self._after_playing)
        self.seekable.connect(self._after_seekable)
        self._muted = False

    # Diese Funktionen laufen im VLC-Thread; nach dem Herunterfahren dürfen sie keine Qt-Signale mehr auslösen.
    def _on_event(self, signal, name: str) -> None:
        if not self._closed:
            debug_log(f"Ereignis {name}")
            signal.emit()

    def _on_time(self, ms: int) -> None:
        if not self._closed:
            self.time_changed.emit(ms)

    def _on_seekable(self, flag: bool) -> None:
        if not self._closed:
            debug_log(f"Ereignis seekable={flag}")
            self.seekable.emit(flag)

    def _after_seekable(self, flag: bool) -> None:
        """Im Qt-Thread: Sobald VLC springen kann (das ist meist früher als "Playing"), wird an die gewünschte Stelle gesprungen,
        damit vom Dateianfang möglichst nichts mehr zu hören oder zu sehen ist."""
        if flag and self._awaiting_position is not None and not self._closed:
            debug_log(f"seekable: springe zu {self._awaiting_position} ms")
            self.mp.set_time(self._awaiting_position)

    def _mute(self, on: bool) -> None:
        """Ton während des Anfahrens einer Stelle stumm schalten (wirkt nur, wenn die Tonausgabe schon besteht)."""
        try:
            self.mp.audio_set_mute(bool(on))
            self._muted = bool(on)
        except Exception:
            self._muted = False

    def shutdown(self) -> None:
        """Geordnetes Beenden: erst die Rückrufe lösen, dann anhalten (wartet, bis VLC das Bild nicht mehr zeichnet),
        dann freigeben. Beim Schließen des Fensters mitten in der Wiedergabe sonst: Speicherzugriffsfehler, weil VLC in ein
        Fenster zeichnet, das Qt schon abgebaut hat, oder ein Rückruf ein Qt-Objekt anspricht, das nicht mehr existiert."""
        if self._closed:
            return
        self._closed = True
        debug_log("shutdown")
        self._pending_show = None
        self._throttle.timer.stop()
        try:
            events = self.mp.event_manager()
            for event_type in self._event_types:
                events.event_detach(event_type)
            self.mp.stop()
            self.mp.release()
            self.instance.release()
        except Exception as e:                                  # beim Beenden nie an einem Fehler scheitern
            debug_log(f"Fehler beim Beenden: {e}")
        self._callbacks.clear()

    def _after_playing(self) -> None:
        """Im Qt-Thread, sobald VLC meldet, dass die Wiedergabe läuft: anhalten und die Startposition abwarten."""
        if self._pending_show is not None and not self._closed:
            ms, self._pending_show = self._pending_show, None
            self.mp.set_pause(1)
            self._mute(True)
            self._await_position(ms, 0)

    # Die Startposition kommt über die Medienoption start-time. Falls VLC sie nicht beachtet (ein Sprung unmittelbar nach dem
    # Start wird oft ignoriert), wird alle 150 ms nachgeprüft und notfalls erneut gesprungen, bis VLC an der Stelle steht.
    POSITION_TOLERANCE_MS = 1500
    POSITION_TRIES = 30                                      # etwa 4,5 Sekunden

    def _await_position(self, ms: int, tries: int) -> None:
        QtCore.QTimer.singleShot(150, lambda: self._check_position(ms, tries))

    def _check_position(self, ms: int, tries: int) -> None:
        if self._closed or self._awaiting_position != ms:
            return                                           # überholt (anderes Bild angefordert, gestoppt)
        now = self.mp.get_time()
        if abs(now - ms) <= self.POSITION_TOLERANCE_MS or tries >= self.POSITION_TRIES:
            self._position_reached(ms)
            return
        debug_log(f"Startposition {ms} ms noch nicht erreicht (VLC steht bei {now} ms): springe, Versuch {tries + 1}")
        self.mp.set_time(ms)
        self._await_position(ms, tries + 1)

    def _position_reached(self, ms: int) -> None:
        self._awaiting_position = None
        if self._muted:
            self._mute(False)

    def attach(self, widget) -> None:
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
        self._awaiting_position = None                         # der Benutzer startet: nichts mehr abwarten, Ton an
        if self._muted:
            self._mute(False)
        self.mp.play()

    def pause(self) -> None:
        if self.mp.is_playing():
            self.mp.set_pause(1)

    def stop(self) -> None:
        self._pending_show = None
        self._awaiting_position = None
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
            # Neues Medium: ein Sprung unmittelbar nach dem Start wird von VLC oft ignoriert. Zuverlässig ist die
            # Medienoption start-time, mit der die Wiedergabe gleich an der gewünschten Stelle beginnt.
            self._pending_show = ms
            self._awaiting_position = ms
            debug_log(f"show_at {ms} ms (Medium {self._path})")
            if self._path:
                media = self.instance.media_new_path(self._path)
                media.add_option(f":start-time={ms / 1000:.3f}")
                self.mp.set_media(media)
            self.mp.play()
            self._mute(True)

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
        debug_log(f"set_time {ms} (Zustand {self.mp.get_state()})")
        self.mp.set_time(ms)

    def set_volume(self, percent: int) -> None:
        self.mp.audio_set_volume(int(percent))

    def set_aspect(self, ratio: str) -> None:
        self.mp.video_set_aspect_ratio(ratio)


# ----------------------------------------------------------------------------- Wiedergabe in den Arbeitsspeicher
def fit_rect(width: int, height: int, aspect: tuple) -> tuple:
    """Größtes Rechteck mit dem Seitenverhältnis `aspect` (Breite, Höhe), das in width x height passt, zentriert."""
    num, den = aspect
    if width <= 0 or height <= 0 or num <= 0 or den <= 0:
        return (0, 0, max(width, 0), max(height, 0))
    if width * den > height * num:                              # Fläche ist breiter als das Bild: Höhe bestimmt
        rw, rh = round(height * num / den), height
    else:
        rw, rh = width, round(width * den / num)
    return ((width - rw) // 2, (height - rh) // 2, rw, rh)


class VideoSurface(QtWidgets.QWidget):
    """Zeichenfläche für die Bilder des Spielers; füllt die Videofläche des Fensters, schwarzer Rand bei anderem Format."""

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
    """libvlc dekodiert in einen Speicherbereich (kein VLC-Fenster, keine VLC-Bildausgabe); die Bilder zeichnet Qt.

    Vorteile gegenüber dem Einbetten in ein X11-Fenster: läuft nativ unter Wayland (kein XWayland nötig), und das
    Einfrieren der Vorschau nach etwa 20 Sprüngen, das von der Bildausgabe von VLC ausging, kann nicht mehr auftreten.
    """

    frame_ready = QtCore.Signal(object)                          # (Bytes, Breite, Höhe) im Qt-Thread

    def __init__(self, extra_args: str = ""):
        super().__init__(extra_args)
        self.surface: Optional[VideoSurface] = None
        self._frames_shown = 0                                   # Zähler der angezeigten Bilder (für die Prüfung von Sprüngen)
        self._last_seek: Optional[int] = None
        self._size = (0, 0)
        self._buf = None
        self._video_callbacks = []                               # nie freigeben: libvlc könnte sie noch aufrufen
        self.frame_ready.connect(self._on_frame)

    def attach(self, widget) -> None:
        self.surface = VideoSurface(widget)
        self.surface.setGeometry(0, 0, widget.width(), widget.height())
        self.surface.show()

    def _install(self, width: int, height: int) -> None:
        """Speicherbereich und Rückrufe für ein Video dieser Größe einrichten (nur im angehaltenen Zustand aufrufen)."""
        width, height = int(width) & ~1, int(height) & ~1
        if (width, height) == self._size:
            return
        self._size = (width, height)
        self._buf = (ctypes.c_ubyte * (width * height * 4))()
        pointer = ctypes.cast(self._buf, ctypes.c_void_p)
        buf = self._buf
        deco = self._vlc.CallbackDecorators

        @deco.VideoLockCb
        def lock(opaque, planes):                                # VLC fragt: wohin soll das nächste Bild?
            planes[0] = pointer
            return None

        @deco.VideoDisplayCb
        def display(opaque, picture):                            # läuft im VLC-Thread: Kopie an Qt weiterreichen
            if not self._closed:
                self.frame_ready.emit((bytes(buf), width, height))

        self._video_callbacks.append((lock, display, buf))
        self.mp.video_set_callbacks(lock, None, display, None)
        self.mp.video_set_format("RV32", width, height, width * 4)
        self.mp.video_set_aspect_ratio(f"{width}:{height}")      # Bild füllt den Speicherbereich ohne eigene schwarze Ränder
        debug_log(f"Speicherausgabe {width}x{height}")

    def _position_reached(self, ms: int) -> None:
        """Position erreicht: Bilder wieder anzeigen. Das Bild, das VLC schon geliefert hat, wurde verworfen; ein erneuter
        Sprung im angehaltenen Zustand liefert eines für diese Stelle."""
        super()._position_reached(ms)
        self.mp.set_time(ms)

    def _on_frame(self, frame) -> None:
        data, width, height = frame
        if self._awaiting_position is not None:
            return                                           # VLC zeigt noch die falsche Stelle (z. B. den Dateianfang)
        if self.surface is not None and not self._closed:
            image = QtGui.QImage(data, width, height, width * 4, QtGui.QImage.Format.Format_RGB32).copy()
            self.surface.set_image(image)
            self._frames_shown += 1

    SEEK_CHECK_MS = 600                                          # so lange auf das Bild nach einem Sprung warten
    SEEK_CHECK_MIN_DISTANCE_MS = 100                             # nähere Sprünge liefern manchmal kein neues Bild

    def _do_seek(self, ms: int) -> None:
        """Sprung wie in der Basisklasse; im angehaltenen Zustand muss danach ein Bild kommen. VLC ignoriert manche Sprünge
        (z. B. an den Dateianfang); dann wird das Medium mit der Startposition neu geladen."""
        before, here = self._frames_shown, self.mp.get_time()
        super()._do_seek(ms)
        self._last_seek = ms
        if self.mp.get_state() == self._vlc.State.Paused and abs(here - ms) > self.SEEK_CHECK_MIN_DISTANCE_MS:
            QtCore.QTimer.singleShot(self.SEEK_CHECK_MS, lambda: self._verify_seek(ms, before))

    def _verify_seek(self, ms: int, frames_before: int) -> None:
        if self._closed or self._awaiting_position is not None or self._last_seek != ms:
            return                                               # überholt: inzwischen kam ein anderer Sprung
        if self._frames_shown == frames_before and self.mp.get_state() == self._vlc.State.Paused:
            debug_log(f"Sprung zu {ms} ms lieferte kein Bild: Medium wird neu geladen")
            self.stop()
            self.show_at(ms)

    def load(self, path: str, size: Optional[tuple] = None) -> None:
        self.stop()                                              # Umstellen des Speichers nur ohne laufende Wiedergabe
        self._install(*(size or (720, 576)))
        if self.surface is not None:
            self.surface.clear()
        super().load(path, size)

    def set_aspect(self, ratio: str) -> None:
        """Darstellungsformat in der Videofläche, z. B. "16:9" (die Bilder werden entsprechend gestreckt)."""
        if self.surface is not None:
            num, _, den = ratio.partition(":")
            self.surface.set_aspect(int(num), int(den))
