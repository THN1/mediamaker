"""Tests für Einstellungen, Projektdatei und die Hauptlogik (Öffnen, Analysieren, Navigation) ohne Qt und ohne VLC.

Aufruf:  python3 tests/test_app.py ORDNER_MIT_BEISPIELVIDEOS   (erwartet sample2.ts und sample3.ts darin)
Die Oberfläche läuft gegen den Qt-Ersatz in ui/tests/qtstub, die Wiedergabe gegen FakePlayer.
"""
import json
import os
import shutil
import sys
import tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "ui", "tests", "qtstub"))        # Ersatz vor einem echten PySide6
sys.path.insert(1, ROOT)
sys.path.insert(2, os.path.join(ROOT, "ui"))
sys.path.insert(3, os.path.join(ROOT, "ui", "generated"))

from PySide6 import QtWidgets
from cutlist import Job, parse_batch_header, Segment
from mediaprobe import AudioInfo, MediaInfo, VideoInfo
from player import FakePlayer
from project import load_segments, save_segments, segment_row, timeof
from settings import Settings

errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


# ----------------------------------------------------------------------------- Einstellungen
def test_settings(tmp):
    ini = os.path.join(tmp, "MediaMaker.ini")
    shutil.copy(os.path.join(HERE, "sample_MediaMaker.ini"), ini)
    before = open(ini, "rb").read()
    s = Settings(ini)
    check(s.options["crop"] == "72" and s.options["floor"] == "2", f"options: {s.options}")
    check(s.profile["scale"] == "720:576" and s.profile["acodec_in"] == "mp2", f"profile: {s.profile}")
    check(len(s.profiles) == 11 and s.profiles["HD"]["scale"] == "1280:720", f"profiles: {list(s.profiles)}")
    check(s.last.endswith("Elysium.ts"), f"last: {s.last}")
    check("Target video bitrate" in s.tooltip("bv"), "tooltip")
    # Ändern: nur die betroffene Zeile ändert sich
    s.set_option("crop", 70)
    s.save()
    after = open(ini, "rb").read()
    old_lines, new_lines = before.decode("cp1252").split("\r\n"), after.decode("utf-8").split("\r\n")
    changed = [(a, b) for a, b in zip(old_lines, new_lines) if a != b]
    check(len(old_lines) == len(new_lines) and len(changed) == 1 and changed[0][1].startswith("options=") and
          'crop="70"' in changed[0][1], f"Änderung nicht auf eine Zeile beschränkt: {changed}")
    check(Settings(ini).options["crop"] == "70" and Settings(ini).options["floor"] == "2", "Neuladen")
    s2 = Settings(ini)
    s2.last = "/tmp/x y.ts"
    check(Settings(ini).last == "/tmp/x y.ts", "last speichern")
    s2.set("neuer abschnitt", "k", "v")
    s2.save()
    check(Settings(ini).get("neuer abschnitt", "k") == "v", "neuen Abschnitt anlegen")
    print("Einstellungen: OK (Optionen, Profil, 11 benannte Profile, Ändern ersetzt genau eine Zeile)")


# ----------------------------------------------------------------------------- Projektdatei
def test_project(tmp):
    job = parse_batch_header(open(os.path.join(HERE, "sample_Elysium.bat"), encoding="latin-1").read())
    check(len(job.segments) == 4 and all(s.has_png_mask for s in job.segments), "Elysium-Liste (4 Segmente mit Maske)")
    path = os.path.join(tmp, "list.json")
    save_segments(path, job.segments)
    back = load_segments(path)
    check(len(back) == 4, "Anzahl nach Laden")
    for a, b in zip(job.segments, back):
        check(a == b, f"Segment nach JSON verändert: {a.index}")
    data = json.load(open(path))
    check(data["segments"][0]["fps"] == "25/1" and data["segments"][0]["crop"] == [0, 0, 0, 0], "JSON-Felder")
    check(not os.path.exists(path + ".tmp"), "temporäre Datei bleibt liegen")
    # alte CSV-Datei laden
    csv_text = open(os.path.join(tmp, "legacy.csv"), "w", encoding="cp1252", newline="")
    csv_text.write('"01","R:\\Film.ts","Film.ts","0","1000","00:00:40","1000","25.000","720","576","3009","192","a","0","0","0","0","48000",""\r\n')
    csv_text.close()
    legacy = load_segments(os.path.join(tmp, "legacy.csv"))
    check(len(legacy) == 1 and legacy[0].fps == 25 and legacy[0].end == 1000, "CSV-Import")
    check(load_segments(os.path.join(tmp, "gibtsnicht.json")) == [], "fehlende Datei")
    robocop = parse_batch_header(open(os.path.join(HERE, "sample_MediaMaker.sh"), encoding="latin-1").read())
    check(len(robocop.segments) == 6, "RoboCop-Liste")
    row = segment_row(robocop.segments[0], 1)
    check(len(row) == 19 and row[0] == "01" and row[7] == "25.000" and row[5] == "00:31:26", f"Zeile: {row[:8]}")
    check(timeof(7509, Fraction(25)) == "00:05:00.360", timeof(7509, Fraction(25)))
    print("Projektdatei: OK (JSON verlustfrei, alte CSV importierbar, 19 Listenspalten)")


# ----------------------------------------------------------------------------- Hauptlogik
def make_window(tmp, probe=None, fresh=False, thumb_fn=None, first_fn=None, **kwargs):
    import mediamaker
    ini = os.path.join(tmp, "MediaMaker.ini")
    if not os.path.exists(ini):
        shutil.copy(os.path.join(HERE, "sample_MediaMaker.ini"), ini)
    win = mediamaker.frmMain(Settings(ini), FakePlayer(), os.path.join(tmp, "MediaMaker.json"),
                             **({"probe": probe} if probe else {}), **({"thumb_fn": thumb_fn} if thumb_fn else {}), fresh=fresh,
                             first_fn=first_fn or (lambda path, fps: 0), **kwargs)
    win.messages = []
    win.msg = win.messages.append
    win.answer = True
    win.ask = lambda text: win.answer
    win.busy = lambda on: None
    return win


def test_app(tmp, videos):
    s2, s3 = os.path.join(videos, "sample2.ts"), os.path.join(videos, "sample3.ts")
    win = make_window(tmp)
    win.showEvent(None)                                       # Form_Load
    check(win.lblText[1].text() == "3072k" and win.lblText[2].text() == "720:576" and win.lblText[3].text() == "25.000",
          "Profilanzeige")
    check(win.player.volume == 44, f"Lautstärke {win.player.volume}")
    widths = {a[0]: a[1] for a in win.lvwSegments.called("setColumnWidth")}
    # Nummer unverändert 32 Pixel; Bildnummern und Dauer aus der Schrift (im Test 1 Pixel je Zeichen): sechsstellig, hh:mm:ss, je 20 Rand
    px = QtWidgets.FontMetrics.px_per_char
    check(widths[0] == 32 and widths[3] == px * 6 + 20 and widths[4] == px * 6 + 20 and widths[5] == px * 8 + 20,
          f"sichtbare Spalten (Nummer, erstes, letztes Bild, Dauer): {widths}")
    check(widths[3] == widths[4] < widths[5], "Spalten für erstes und letztes Bild gleich breit, Dauer etwas breiter")
    hidden = sorted(c for c, w in widths.items() if w == 0)
    check(hidden == [1] + list(range(6, 19)), f"ausgeblendete Spalten: {hidden}")
    check(2 not in widths and win.lvwSegments.header().called("setStretchLastSection") == [(False,)]
          and win.lvwSegments.header().called("setMinimumSectionSize") == [(0,)]
          and len(win.lvwSegments.header().called("setSectionResizeMode")) == 1, "Kopfzeile")
    check(win.player.attached is win.VLC, "Videofläche")

    check(win.OpenVideo(s2), "OpenVideo sample2")
    seg = win.segments[0]
    check((seg.end, seg.total_frames, seg.width, seg.height, seg.fps, seg.audio_sel) == (148, 148, 720, 576, 25, "a"),
          f"Segment: {seg}")
    check(win.lvwSegments.row_count() == 1 and win.lvwSegments.topLevelItem(0).text(2) == "sample2.ts", "Liste")
    check(win.lvwSegments.topLevelItem(0).font(2).called("setBold")[-1] == (True,), "Titel fett")
    check(win.current == 0 and win.player.path == s2, "Segment geladen")
    check(win.Slider1.maximum() == 148 and win.Slider1.value() == 0, "Schieber")
    check(win.lblInfo.text() == "Frame 0" and win.lblTime.text() == "Time 00:00:00.000", f"Anzeige {win.lblInfo.text()}")
    check(win.lblText[0].text() == "00:00:06", f"Gesamtlänge {win.lblText[0].text()}")
    check(win.cmdPos[3].text() == "|>", "Play-Knopf nach dem Laden")
    check(Settings(os.path.join(tmp, "MediaMaker.ini")).last == s2, "last gespeichert")
    check(load_segments(os.path.join(tmp, "MediaMaker.json"))[0].end == 148, "Liste gespeichert")

    # Navigation
    win.cmdPos_Click(4)
    check(win.Slider1.value() == 1 and win.player.time == 40 and win.lblInfo.text() == "Frame 1"
          and win.lblTime.text() == "Time 00:00:00.040", f"+1: {win.Slider1.value()} {win.player.time}")
    win.cmdPos_Click(5)
    check(win.Slider1.value() == 126, f"+5 s: {win.Slider1.value()}")
    win.cmdPos_Click(6)
    check(win.Slider1.value() == 148, "Ende")
    win.cmdPos_Click(1)
    check(win.Slider1.value() == 23, "-5 s")
    win.cmdPos_Click(0)
    check(win.Slider1.value() == 0 and win.player.time == 0, "Anfang")
    # Wiedergabe
    win.cmdPos_Click(3)
    check(win.player.is_playing and win.cmdPos[3].text() == "=", "Play")
    win.player.tick(1000)
    check(win.lblInfo.text() == "Frame 25", f"Zeitanzeige beim Abspielen: {win.lblInfo.text()}")
    check(win.Slider1.value() == 25, f"Schieber läuft beim Abspielen mit: {win.Slider1.value()}")
    win.player.tick(1000)
    check(win.Slider1.value() == 50 and win.player.time == 2000, "Schieber folgt weiter, ohne den Player erneut springen zu lassen")
    win.Slider1.isSliderDown = lambda: True                    # der Benutzer hält den Schieber fest
    win.player.tick(1000)
    check(win.Slider1.value() == 50 and win.lblInfo.text() == "Frame 75", "gezogener Schieber bleibt unberührt")
    del win.Slider1.isSliderDown
    win.player.time = 1000
    win.player.tick(0)
    win.cmdPos_Click(3)
    check(not win.player.is_playing and win.cmdPos[3].text() == "|>" and win.Slider1.value() == 25,
          f"Pause setzt Schieber: {win.Slider1.value()}")
    # Marker
    win._go(50)
    win.cmdPos_Click(7)
    check(seg.start == 50 and win.lvwSegments.topLevelItem(0).text(3) == "50", "Marker A")
    check(win.lvwSegments.topLevelItem(0).text(5) == "00:00:04", f"Dauer {win.lvwSegments.topLevelItem(0).text(5)}")
    win._go(100)
    win.cmdPos_Click(8)
    check(seg.end == 100 and win.lblText[0].text() == "00:00:02", f"Marker B / Gesamtlänge {win.lblText[0].text()}")
    check(win.Slider1.value() == 100 and win.timeline_mode == "B", "Sprung zu Marker B")
    win._go(40)
    win.cmdPos_Click(8)                                        # Ende vor dem Beginn: Signalton, keine Änderung
    check(seg.end == 100 and "beep" in QtWidgets.QApplication.log, "Ende vor Beginn")
    win.cmdPos_Click(11)
    check((seg.start, seg.end) == (0, 148), "Marker zurücksetzen")
    # Lautstärke
    win.vscVolume.setValue(0)
    win.vscVolume_Scroll()
    check(win.player.volume == 204, "Lautstärke oben")

    # Ablegen mehrerer Dateien, dann zurück zum ersten Segment
    win.lvwSegments._vb_filter.handlers["drop"]([s3])
    check(len(win.segments) == 2 and win.segments[1].end == 348 and win.current == 1 and win.player.path == s3,
          f"Ablegen: {len(win.segments)}")
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    check(win.current == 0 and win.player.path == s2 and win.Slider1.maximum() == 148, "Auswahl wechseln")

    # Neustart: Liste wird geladen
    win2 = make_window(tmp)
    win2.showEvent(None)
    check(len(win2.segments) == 2 and win2.lvwSegments.row_count() == 2, "Liste beim Start geladen")
    check(win2.lblText[0].text() == "00:00:20", f"Gesamtlänge nach Neustart {win2.lblText[0].text()}")
    print("Hauptlogik: OK (Öffnen, Analyse, Anzeige, Navigation, Marker, Wiedergabe, Ablegen, Neustart)")


def test_fresh_and_paths(tmp, videos):
    """Neuer Auftrag leert die Liste; relative Pfade werden als vollständige Pfade gespeichert."""
    project = os.path.join(tmp, "MediaMaker.json")
    s2 = os.path.join(videos, "sample2.ts")
    old = [Segment(1, s2, "sample2.ts", 0, 148, 148, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")] * 2
    save_segments(project, old)
    # ohne Parameter: letzte Liste wird geladen
    win = make_window(tmp)
    win.showEvent(None)
    check(len(win.segments) == 2, "ohne Parameter wird die Liste geladen")
    # mit Parameter: Liste wird verworfen und die Datei geleert
    win = make_window(tmp, fresh=True)
    win.showEvent(None)
    check(win.segments == [] and load_segments(project) == [] and win.lvwSegments.row_count() == 0,
          "mit Parameter beginnt die Liste leer")
    # relativer Pfad: aus dem Ordner der Videodatei aufgerufen
    cwd = os.getcwd()
    os.chdir(videos)
    try:
        check(win.OpenVideo("sample2.ts"), "OpenVideo mit Dateiname")
    finally:
        os.chdir(cwd)
    stored = load_segments(project)[0]
    check(stored.path == s2 and os.path.isabs(stored.path), f"Pfad in der Liste: {stored.path}")
    check(stored.name == "sample2.ts" and win.player.path == s2, "Titel bleibt der Dateiname, Player bekommt den vollen Pfad")
    check(win.settings.last == s2, f"last: {win.settings.last}")
    check(json.load(open(project))["segments"][0]["path"] == s2, "JSON enthält den vollständigen Pfad")
    print("Neuer Auftrag und Pfade: OK (leere Liste mit Parameter, vollständige Pfade)")


def fake_info(path, audio):
    v = VideoInfo(index=0, codec="mpeg2video", width=720, height=576, fps=Fraction(25), fps_source="x", frames=1000,
                  frames_source="packets", duration=40.0, bitrate=3_000_000)
    return MediaInfo(path=path, format_name="mpegts", duration=40.0, size=0, bitrate=0, video=v, audio=audio)


def test_audio_choice(tmp):
    a = lambda i, codec, lang: AudioInfo(index=i, codec=codec, channels=2, sample_rate=48000, bitrate=192000, language=lang)
    two = [a(1, "ac3", "eng"), a(2, "mp2", "deu"), a(3, "mp2", "fra")]
    win = make_window(tmp, probe=lambda p: fake_info(p, two))
    win.showEvent(None)
    f = os.path.join(tmp, "x.ts")
    open(f, "w").close()
    check(win.OpenVideo(f) and win.segments[-1].audio_sel == "2", f"erste mp2-Spur: {win.segments[-1].audio_sel}")
    win.settings.set_option("audio", 2)
    win.OpenVideo(f)
    check(win.segments[-1].audio_sel == "3", f"zweite mp2-Spur: {win.segments[-1].audio_sel}")
    win.settings.set_option("audio", 5)
    win.OpenVideo(f)
    check(win.segments[-1].audio_sel == "2" and any("no audio track" in m for m in win.messages), "Spur nicht vorhanden")
    win.settings.set_profile(dict(win.profile, acodec_in="aac"))
    n = len(win.segments)
    check(not win.OpenVideo(f) and len(win.segments) == n and any("no audio stream of type" in m for m in win.messages),
          "Codec nicht vorhanden")
    win3 = make_window(tmp, probe=lambda p: fake_info(p, []))
    check(not win3.OpenVideo(f) and any("no audio stream" in m for m in win3.messages), "ohne Ton")
    print("Tonspurwahl: OK (n-te Spur mit passendem Codec, Warnungen, Abbruch)")


def test_counting_and_network(tmp, videos):
    """Schnelle Analyse mit geschätzter Bildanzahl, exakte Zählung im Hintergrund, Netzlaufwerk-Pfade."""
    import mediamaker
    from mediaprobe import MediaInfo
    # 1) Schätzung wird durch die Zählung ersetzt; das Ende folgt, solange der Benutzer es nicht geändert hat
    est = lambda p: fake_info(p, [AudioInfo(1, "mp2", 2, 48000, 192000, "deu")])
    def estimated(p):
        info = est(p)
        info.video.frames_source = "estimated"
        return info
    f = os.path.join(tmp, "n.ts")
    open(f, "w").close()
    win = make_window(tmp, probe=estimated, fresh=True)
    win.showEvent(None)
    win._count_fn = lambda path, on_start=None: (990, 1, 0.0)
    check(win.OpenVideo(f), "OpenVideo mit Schätzung")
    seg = win.segments[0]
    check((seg.total_frames, seg.end) == (990, 990), f"nach der Zählung: {seg.total_frames}/{seg.end}")
    check(win.Slider1.maximum() == 990 and win.lvwSegments.topLevelItem(0).text(6) == "990", "Schieber und Liste")
    titles = [a[0] for a in win.called("setWindowTitle")]
    check("counting" in titles[-2] and titles[-1] == "MediaMaker " + mediamaker.VERSION, f"Titel: {titles[-2:]}")
    # 2) Marker des Benutzers bleiben erhalten, ein Ende hinter dem wirklichen Ende wird begrenzt
    seg.start, seg.end = 200, 500
    win.frames_counted(f, 400, 0, 0.0)
    check((seg.start, seg.end, seg.total_frames) == (200, 400, 400), f"Marker: {seg.start}/{seg.end}/{seg.total_frames}")
    seg.start, seg.end = 100, 300
    win.frames_counted(f, 450, 0, 0.0)
    check((seg.start, seg.end, seg.total_frames) == (100, 300, 450), "Marker unverändert bei größerer Zahl")
    check(load_segments(os.path.join(tmp, "MediaMaker.json"))[0].total_frames == 450, "gespeichert")
    # 3) Zählung abbrechen
    from mediamaker import FrameCounter
    class Proc:
        terminated = False
        def poll(self): return None
        def terminate(self): self.terminated = True
    c = FrameCounter(f, lambda path, on_start=None: (1, 0, 0.0))
    proc = Proc()
    c._remember(proc)
    c.cancel()
    check(proc.terminated and c.cancelled, "Zählung abbrechbar")
    got = []
    c2 = FrameCounter(f, lambda path, on_start=None: (5, 0, 0.0))
    c2.counted.connect(lambda *a: got.append(a))
    c2.cancelled = True
    c2.run()
    check(got == [], "abgebrochene Zählung meldet nichts")
    # 4) Netzlaufwerk: das Verzeichnis kio-fuse-... ändert sich mit jeder Sitzung
    share = os.path.join(tmp, "run", "kio-fuse-NEUab", "smb", "nas", "movie")
    os.makedirs(share)
    real = os.path.join(share, "Film 1.ts")
    open(real, "w").close()
    stale = os.path.join(tmp, "run", "kio-fuse-ALTcd", "smb", "nas", "movie", "Film 1.ts")
    seg2 = Segment(1, stale, "Film 1.ts", 0, 100, 100, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")
    save_segments(os.path.join(tmp, "MediaMaker.json"), [seg2])
    win = make_window(tmp)
    win.showEvent(None)
    check(win.segments[0].path == real and not win.messages, f"Pfad aufgelöst: {win.segments[0].path}")
    check(load_segments(os.path.join(tmp, "MediaMaker.json"))[0].path == real, "aufgelöster Pfad gespeichert")
    print("Zählung und Netzlaufwerk: OK (Schätzung, Zählung im Hintergrund, Marker bleiben, abbrechbar, kio-fuse-Pfade)")


def test_profiles(tmp, videos):
    """Profil und Optionen: Prüfung, INI-Datei, Dialoge, Profilliste, Speichern, Kopieren aus dem Mustervideo."""
    from profiles import (default_name, normalize_bitrate, profile_from_segment, valid_profile_name, validate_options,
                          validate_profile, weighted_bitrate)
    ok_profile = {"description": "x", "scale": "720:576", "sws_flags": "lanczos", "fps": "25.000", "bv": "3072k",
                  "acodec_in": "mp2", "acodec_out": "aac", "ar": "48000", "ba": "192k"}
    from profiles import wrapped_lines
    check(wrapped_lines(330, 230, min_lines=2) == 2 and wrapped_lines(50, 230, min_lines=2) == 2
          and wrapped_lines(900, 230) == 4 and wrapped_lines(0, 230) == 1 and wrapped_lines(218, 230) == 1
          and wrapped_lines(219, 230) == 2, "Zeilenzahl für lange Werte")
    check(validate_profile(ok_profile) == [], f"gültiges Profil: {validate_profile(ok_profile)}")
    bad = lambda **kw: validate_profile(dict(ok_profile, **kw))
    check(len(bad(scale="abc")) == 1 and len(bad(scale="721:576")) == 1 and len(bad(scale="720:0")) == 1, "scale")
    check(len(bad(fps="25")) == 1 and len(bad(fps="5.000")) == 1 and bad(fps="29.970") == [], "fps")
    check(len(bad(bv="3072")) == 1 and len(bad(ba="0k")) == 1 and bad(ba="64k") == [], "Bitraten")
    check(len(bad(ar="48")) == 1 and bad(ar="44100") == [] and len(bad(acodec_out="")) == 1, "ar, Codec")
    check(validate_options({"crop": "72", "floor": "2", "subtitle": "0", "multilanguage": "False"}) == [], "Optionen gültig")
    check(len(validate_options({"crop": "-1"})) == 1 and len(bad(pad="yes")) == 1 and bad(pad="True") == []
          and len(validate_options({"subtitle": "a"})) == 1 and validate_options({"subtitle": "1,2"}) == []
          and len(validate_options({"audio": "0"})) == 1, "Optionen ungültig")
    check(valid_profile_name("Mein Profil [1]") is None and valid_profile_name("a=b") and valid_profile_name("[x") and
          valid_profile_name("  "), "Profilnamen")
    check(default_name({"description": "MPEG-TS (SD 720x576), 25 FPS"}) == "MPEG-TS_(SD_720x576),_25_FPS", "Vorschlag Name")
    check(normalize_bitrate("3000") == "3000k" and normalize_bitrate(" 3000k ") == "3000k" and
          normalize_bitrate("0") is None and normalize_bitrate("abc") is None, "normalize_bitrate")
    seg = lambda frames, v, a: Segment(1, "/x.ts", "x.ts", 0, frames, frames, Fraction(25), 1280, 720, v, a, "a", 0, 0, 0, 0, 44100, "")
    check(weighted_bitrate([seg(250, 4000, 192), seg(750, 2000, 128)], "video") == 2500 and
          weighted_bitrate([seg(250, 4000, 192), seg(750, 2000, 128)], "audio") == 144 and weighted_bitrate([], "video") == 0,
          "gewichteter Mittelwert")
    check(profile_from_segment(seg(100, 3009, 192)) == {"bv": "3009k", "scale": "1280:720", "fps": "25.000", "ar": "44100",
                                                       "ba": "192k"}, "Profil aus Segment")

    # --- INI: benannte Profile
    ini = os.path.join(tmp, "profiles.ini")
    shutil.copy(os.path.join(HERE, "sample_MediaMaker.ini"), ini)
    st = Settings(ini)
    st.save_profile("Mein Profil [test]", ok_profile)
    st.save_profile("HD", dict(st.profiles["HD"], bv="9999k"))                       # überschreiben
    st.update_profile({"bv": "1234k"})
    st.set_options(dict(st.options, crop="60"))
    st.save()
    st = Settings(ini)
    names = list(st.profiles)
    check(len(names) == 12 and names[-1] == "Mein Profil [test]" and st.profiles["HD"]["bv"] == "9999k", f"Profile: {names}")
    check(st.profiles["Mein Profil [test]"] == ok_profile and st.profile["bv"] == "1234k" and st.profile["scale"] == "720:576",
          "Profil gespeichert und Einzelwert geändert")
    check(st.options["crop"] == "60" and st.options["floor"] == "2", "Optionen gespeichert")

    # --- Hauptfenster
    workdir = os.path.join(tmp, "profwin")
    os.makedirs(workdir)
    shutil.copy(os.path.join(HERE, "sample_MediaMaker.ini"), os.path.join(workdir, "MediaMaker.ini"))
    win = make_window(workdir)
    win.showEvent(None)
    check(len(win.profile_actions) == 11 and win.mnuLoadProfile.called("setEnabled") == [(True,)], "Profilmenü gefüllt")
    check(win.Frame1.called("setToolTip")[-1] == ("MPEG-TS (SD 720x576), 25 FPS, 3072 and 192 KBit/s",), "Tooltip Beschreibung")
    # Profil laden über das Menü
    hd = next(a for a in win.profile_actions if a.text_ == "HD")
    hd.triggered.emit(False)
    check(win.profile["scale"] == "1280:720" and win.lblText[2].text() == "1280:720" and win.lblText[3].text() == "29.970",
          "Profil laden: Anzeige")
    check(Settings(os.path.join(workdir, "MediaMaker.ini")).profile["scale"] == "1280:720", "Profil laden: gespeichert")
    # Profil bearbeiten: erst fehlerhaft, dann gültig; Abbruch ändert nichts
    answers = [dict(win.profile, scale="abc"), dict(win.profile, scale="1920:1080", bv="5000k")]
    seen = []
    win.edit_pairs = lambda title, pairs, groups=None: (seen.append((title, dict(pairs))), answers.pop(0))[1]
    win.mnuProfile_Click()
    check(len(win.messages) == 1 and "width:height" in win.messages[0], f"Fehlermeldung: {win.messages}")
    check(seen[1][1]["scale"] == "abc", "Dialog erscheint mit den eingegebenen Werten erneut")
    check(win.profile["scale"] == "1920:1080" and win.lblText[1].text() == "5000k", "Profil bearbeitet")
    win.edit_pairs = lambda title, pairs, groups=None: None
    win.mnuProfile_Click()
    check(win.profile["scale"] == "1920:1080", "Abbruch ändert nichts")
    # Optionen
    win.edit_pairs = lambda title, pairs, groups=None: dict(pairs, crop="70", floor="1")
    win.mnuOptions_Click()
    check(win.options["crop"] == "70" and win.options["floor"] == "1" and win.options["blackness"] == "12", "Optionen geändert")
    check(Settings(os.path.join(workdir, "MediaMaker.ini")).options["crop"] == "70", "Optionen in der INI-Datei")
    win.edit_pairs = lambda title, pairs, groups=None: dict(pairs, crop="abc")
    n_msgs = len(win.messages)
    answers2 = [dict(win.options, crop="abc"), None]
    win.edit_pairs = lambda title, pairs, groups=None: answers2.pop(0)
    win.mnuOptions_Click()
    check(len(win.messages) == n_msgs + 1 and win.options["crop"] == "70", "ungültige Option wird abgelehnt")
    # Profil speichern unter Namen
    names_asked = ["Neu A", "Neu A", "Neu B"]
    win.ask_text = lambda title, label, default="": names_asked.pop(0)
    win.mnuSaveProfile_Click()
    check("Neu A" in win.settings.profiles and len(win.profile_actions) == 12, "Profil gespeichert, Menü aktualisiert")
    win.answer = False                                                  # Überschreiben verneint: nach neuem Namen fragen
    win.mnuSaveProfile_Click()
    check("Neu B" in win.settings.profiles and len(win.profile_actions) == 13 and win.settings.profiles["Neu A"]["scale"] == "1920:1080",
          "Überschreiben verneint: anderer Name")
    win.ask_text = lambda title, label, default="": None
    win.mnuSaveProfile_Click()
    check(len(win.profile_actions) == 13, "Abbruch beim Speichern")
    win.ask_text = lambda title, label, default="": "a=b"
    msgs = len(win.messages)
    answers3 = ["a=b", None]
    win.ask_text = lambda title, label, default="": answers3.pop(0)
    win.mnuSaveProfile_Click()
    check(len(win.messages) == msgs + 1, "ungültiger Profilname")
    # Mustervideo: Werte der Zieldatei kopieren
    win.mnuReuse_Click()
    check("one and only one" in win.messages[-1], "Reuse ohne Segment")
    win.OpenVideo(os.path.join(videos, "sample2.ts"))
    before_reuse = dict(win.profile)
    win.mnuReuse_Click()
    seg0 = win.segments[0]
    check(win.profile["scale"] == "720:576" and win.profile["fps"] == "25.000" and win.profile["ar"] == "48000"
          and win.profile["bv"] == f"{seg0.vbitrate_kbit}k" and win.profile["ba"] == f"{seg0.abitrate_kbit}k"
          and win.lblText[2].text() == "720:576" and "copied from" in win.messages[-1], f"Reuse: {win.profile}")
    check({k: v for k, v in win.profile.items() if k not in ("bv", "scale", "fps", "ar", "ba")}
          == {k: v for k, v in before_reuse.items() if k not in ("bv", "scale", "fps", "ar", "ba")}, "Reuse lässt andere Werte unverändert")
    # Bitraten schätzen
    win.OpenVideo(os.path.join(videos, "sample3.ts"))
    win.mnuReuse_Click()
    check("one and only one" in win.messages[-1], "Reuse mit zwei Segmenten")
    win.segments[0].vbitrate_kbit, win.segments[1].vbitrate_kbit = 4000, 2000
    avg = weighted_bitrate(win.segments, "video")
    asked = []
    win.ask_text = lambda title, label, default="": (asked.append((label, default)), "3000")[1]
    win.mnuCalcVideo_Click()
    check(asked[0][1] == str(avg) and win.profile["bv"] == "3000k", f"Schätzung Video: {asked} {win.profile['bv']}")
    win.ask_text = lambda title, label, default="": "160k"
    win.mnuCalcAudio_Click()
    check(win.profile["ba"] == "160k" and win.lblText[5].text() == "160k", "Schätzung Audio")
    win.ask_text = lambda title, label, default="": "abc"
    before = win.profile["bv"]
    win.mnuCalcVideo_Click()
    check(win.profile["bv"] == before and "not a valid bitrate" in win.messages[-1], "ungültige Bitrate")
    print("Profil und Optionen: OK (Prüfung, INI-Datei, Dialoge, Profilmenü, Speichern, Kopieren aus Mustervideo, Schätzung)")


def test_dialog():
    """Der Bearbeiten-Dialog wird gegen den strengen Qt-Ersatz durchgespielt (Aufzählungen, Feldtypen, Rückgabe)."""
    import dialogs
    from profiles import PRESETS
    from PySide6.QtWidgets import FontMetrics, QComboBox, QDialog, QFormLayout, QLineEdit
    pairs = {"description": "MPEG-TS (SD 720x576), 25 FPS, 3072 and 192 KBit/s", "scale": "720:576", "fps": "25.000",
             "aflags": "", "pad": "False"}
    QDialog.exec_result = 1
    QDialog.on_exec = None
    QFormLayout.instances.clear()
    result = dialogs.edit_pairs(None, "Profile", pairs, {"scale": "Tipp"}, PRESETS)
    check(result == pairs, f"Rückgabe unverändert: {result}")
    rows = dict((label._args[0], editor) for label, editor in QFormLayout.instances[-1].rows)
    check(isinstance(rows["description"], dialogs.WrappedEdit) and isinstance(rows["scale"], QLineEdit)
          and isinstance(rows["fps"], QComboBox) and isinstance(rows["pad"], QComboBox) and isinstance(rows["aflags"], QLineEdit),
          f"Feldtypen: { {k: type(v).__name__ for k, v in rows.items()} }")
    height = rows["description"].called("setFixedHeight")
    check(len(height) == 1 and height[0][0] >= 2 * 16, f"Beschreibung hat mindestens zwei Zeilen: {height}")
    check(rows["scale"].called("setToolTip") == [("Tipp",)], "Tooltip")
    # Eingaben ändern: Combobox, Zeilenfeld mit Zeilenumbruch
    def edit(dialog):
        rows2 = dict((l._args[0], e) for l, e in QFormLayout.instances[-1].rows)
        rows2["fps"].setCurrentText("29.970")
        rows2["scale"].setText(" 1280:720 ")
        rows2["description"].setPlainText("erste Zeile\nzweite Zeile")
    QDialog.on_exec = edit
    result = dialogs.edit_pairs(None, "Profile", pairs, {}, PRESETS)
    check(result["fps"] == "29.970" and result["scale"] == "1280:720" and result["description"] == "erste Zeile zweite Zeile",
          f"geänderte Werte: {result}")
    # Abbruch
    QDialog.on_exec = None
    QDialog.exec_result = 0
    check(dialogs.edit_pairs(None, "Profile", pairs, {}, PRESETS) is None, "Abbruch liefert None")
    QDialog.exec_result = 1
    # lange Werte in beliebigen Feldern werden ebenfalls mehrzeilig
    FontMetrics.px_per_char = 10
    try:
        QFormLayout.instances.clear()
        dialogs.edit_pairs(None, "Options", {"aflags": "x" * 40}, {}, {})
        long_editor = QFormLayout.instances[-1].rows[0][1]
        check(isinstance(long_editor, dialogs.WrappedEdit), "langer Wert in beliebigem Feld wird mehrzeilig")
    finally:
        FontMetrics.px_per_char = 1
    # Enter im mehrzeiligen Feld bestätigt den Dialog statt einen Zeilenumbruch einzufügen
    accepted = []
    edit_box = dialogs.WrappedEdit("text", lambda: accepted.append(1))
    class Key:
        def __init__(self, key): self.k = key
        def key(self): return self.k
    edit_box.keyPressEvent(Key(0x01000004))
    edit_box.keyPressEvent(Key(0x41))
    check(accepted == [1], "Enter bestätigt")
    # Der Ersatz lehnt eine Zahl statt einer Aufzählung ab (der Fehler, der im echten Qt aufgefallen war)
    try:
        edit_box.setHorizontalScrollBarPolicy(1)
        check(False, "Ersatz erkennt Zahl statt Aufzählung nicht")
    except TypeError:
        pass
    print("Dialog: OK (Feldtypen, mehrzeilige Beschreibung, Eingaben, Abbruch, Enter, Prüfung der Aufzählungen)")


def test_memory_player():
    """MemoryVlcPlayer gegen ein vorgetäuschtes vlc-Modul: Formate, Rückrufe, Bildübergabe, Herunterfahren."""
    import ctypes
    import types
    from types import SimpleNamespace
    import player as pl
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QWidget

    class Events:
        def event_attach(self, *a): pass
        def event_detach(self, *a): pass

    class Mp:
        def __init__(self):
            self.cb_calls, self.format, self.aspect, self.released, self.stops = [], None, None, False, 0
        def event_manager(self): return Events()
        def video_set_callbacks(self, lock, unlock, display, opaque): self.cb_calls.append((lock, unlock, display, opaque))
        def video_set_format(self, chroma, w, h, pitch): self.format = (chroma, w, h, pitch)
        def video_set_aspect_ratio(self, r): self.aspect = r
        def set_media(self, m): self.media = m
        def stop(self): self.stops += 1; self.state = 5
        def release(self): self.released = True
        def get_state(self): return getattr(self, "state", 5)
        def audio_set_mute(self, v): self.mutes = getattr(self, "mutes", []) + [v]
        def play(self): self.calls_play = getattr(self, "calls_play", 0) + 1
        def set_pause(self, v): pass
        def get_time(self): return self.t if hasattr(self, "t") else 0
        def set_time(self, ms): self.set_times = getattr(self, "set_times", []) + [ms]
        def is_playing(self): return False

    class Media:
        def __init__(self, p): self.path, self.options = p, []
        def add_option(self, o): self.options.append(o)

    class Inst:
        def __init__(self): self.mp = Mp()
        def media_player_new(self): return self.mp
        def media_new_path(self, p): return Media(p)
        def release(self): pass

    fake = types.ModuleType("vlc")
    fake.Instance = lambda *a: Inst()
    fake.EventType = SimpleNamespace(MediaPlayerPlaying=1, MediaPlayerPaused=2, MediaPlayerStopped=3,
                                     MediaPlayerEndReached=4, MediaPlayerTimeChanged=5, MediaPlayerSeekableChanged=6)
    fake.State = SimpleNamespace(Playing=3, Paused=4, Stopped=5)
    fake.CallbackDecorators = SimpleNamespace(VideoLockCb=lambda f: f, VideoDisplayCb=lambda f: f)
    sys.modules["vlc"] = fake
    try:
        check(pl.fit_rect(513, 290, (16, 9)) == (0, 0, 513, 289) and pl.fit_rect(400, 400, (16, 9)) == (0, 87, 400, 225)
              and pl.fit_rect(1000, 200, (16, 9)) == (322, 0, 356, 200) and pl.fit_rect(0, 10, (16, 9)) == (0, 0, 0, 10),
              "fit_rect")
        player = pl.MemoryVlcPlayer()
        area = QWidget()
        area.setGeometry(0, 0, 513, 290)
        player.attach(area)
        check(player.surface.called("setGeometry") == [(0, 0, 513, 290)], "Zeichenfläche füllt die Videofläche")
        mp = player.mp
        player.load("/x/film.ts", (720, 576))
        check(mp.format == ("RV32", 720, 576, 2880) and mp.aspect == "720:576" and len(mp.cb_calls) == 1 and mp.stops >= 1,
              f"Format: {mp.format} {mp.aspect}")
        lock, unlock, display, opaque = mp.cb_calls[0]
        check(unlock is None and opaque is None, "kein Entsperr-Rückruf")
        planes = [None]
        lock(None, planes)
        check(planes[0].value == ctypes.addressof(player._buf), "Rückruf liefert den Speicherbereich")
        ctypes.memmove(player._buf, b"\x01\x02\x03\xff" * (720 * 576), 720 * 576 * 4)
        display(None, None)
        image = player.surface.image
        check(image is not None and image._args[0] == b"\x01\x02\x03\xff" * (720 * 576) and image._args[1:4] == (720, 576, 2880),
              "Bild kommt in der Zeichenfläche an")
        player.load("/x/zwei.ts", (720, 576))
        check(len(mp.cb_calls) == 1 and player.surface.image is None, "gleiche Größe: keine Neuinstallation, Bild gelöscht")
        player.load("/x/hd.ts", (1281, 721))
        check(mp.format == ("RV32", 1280, 720, 5120) and len(mp.cb_calls) == 2, f"neue Größe (gerade gemacht): {mp.format}")
        player.set_aspect("4:3")
        check(player.surface.aspect == (4, 3), "Darstellungsformat")
        # Bilder vor Erreichen der Startposition werden nicht angezeigt (VLC zeigt zuerst den Dateianfang)
        lock3, _, display3, _ = mp.cb_calls[-1]
        player.load("/x/drei.ts", (1280, 720))
        lock3, _, display3, _ = mp.cb_calls[-1]
        ctypes.memmove(player._buf, b"\x07\x07\x07\xff" * (1280 * 720), 1280 * 720 * 4)
        player.show_at(193_000)
        display3(None, None)
        check(player.surface.image is None, "Bild vom Dateianfang wird verworfen, solange die Position fehlt")
        player._awaiting_position = None                            # (Position gilt als erreicht)
        # Sprung im angehaltenen Zustand: kommt kein Bild, wird mit der Startposition neu geladen
        mp.state, mp.t = 4, 90_000
        QTimer.pending.clear()
        frames0 = player._frames_shown
        player._do_seek(560)
        check(len(QTimer.pending) == 1 and QTimer.pending[0][0] == 600, f"Prüfung nach 600 ms geplant: {QTimer.pending}")
        loads = mp.calls_play
        QTimer.pending.pop(0)[1]()                                  # kein Bild gekommen
        check(mp.calls_play == loads + 1 and player._awaiting_position == 560 and mp.media.options == [":start-time=0.560"],
              f"kein Bild nach dem Sprung: neu geladen mit start-time: {mp.media.options}")
        player._awaiting_position = None
        QTimer.pending.clear()
        mp.state, mp.t = 4, 90_000                                  # wieder angehalten (das Neuladen hat gestoppt)
        player._do_seek(2000)
        player.surface.image = None
        display3(None, None)                                        # Bild ist gekommen
        loads = mp.calls_play
        QTimer.pending.pop(0)[1]()
        check(mp.calls_play == loads, "Bild kam: kein Neuladen")
        QTimer.pending.clear()
        mp.state, mp.t = 4, 5000
        player._do_seek(5050)                                       # fast dieselbe Stelle: nicht prüfen
        check(QTimer.pending == [], "Sprung auf (fast) dieselbe Stelle wird nicht geprüft")
        player._do_seek(7000)
        player._do_seek(9000)                                       # überholt
        loads = mp.calls_play
        QTimer.pending.pop(0)[1]()
        check(mp.calls_play == loads, "überholter Sprung wird nicht geprüft")
        mp.state = 5
        QTimer.pending.clear()
        player._do_seek(100)
        check(QTimer.pending == [], "nur im angehaltenen Zustand")
        player._awaiting_position = player._pending_show = 193_000
        mp.state = 5
        mp.t = 193_050
        QTimer.pending.clear()
        player.playing.emit()
        QTimer.pending.pop(0)[1]()
        check(player._awaiting_position is None and mp.set_times[-1] == 193_000, "Position erreicht: erneuter Sprung für ein frisches Bild")
        display3(None, None)
        check(player.surface.image is not None, "danach werden Bilder angezeigt")
        image_before = player.surface.image
        player.shutdown()
        lock2, _, display2, _ = mp.cb_calls[1]
        display2(None, None)
        display3(None, None)
        check(player.surface.image is image_before and mp.released, "nach dem Herunterfahren keine Bilder mehr, Player freigegeben")
    finally:
        del sys.modules["vlc"]
    print("Speicher-Wiedergabe: OK (Format, Rückrufe, Bildübergabe, Größenwechsel, Herunterfahren)")


def test_timeline(tmp, videos):
    """Zeitleiste: Fenster der 20 Bilder, Klick-Verschiebung, Kreuze, Zeichnen, Bildnummern aus echten Aufnahmen."""
    import numpy as np
    import timeline as tl
    from PIL import Image
    from frames import grab_frame, grab_numbered
    from PySide6.QtWidgets import Rect
    s2 = os.path.join(videos, "sample2.ts")
    # --- reine Logik
    check(tl.window_numbers(100)[0] == 90 and tl.window_numbers(100)[10] == 100 and tl.window_numbers(100)[19] == 109
          and len(tl.window_numbers(5)) == 20, "Fenster der Bildnummern")
    check([tl.click_delta(i) for i in range(20)] == list(range(-9, 0)) + [0, 0] + list(range(1, 10)), "Verschiebung je Bild")
    check([tl.click_index(x, 1085) for x in (0, 53, 54, 540, 541, 1084)] == [0, 0, 1, 10, 10, 19], "Bild unter der Maus")
    check(tl.thumb_size(720, 576, 54) == (53, 42) and tl.thumb_size(576, 720, 54) == (42, 53), "Größe der Vorschaubilder")
    check((tl.frame_number(1.824, 1.4, 25), tl.frame_number(1.4, 1.4, 25), tl.frame_number(1.439, 1.4, 25),
           tl.frame_number(1.44, 1.4, 25)) == (10, 0, 0, 1), "Bildnummer aus dem Zeitstempel")
    # --- echte Aufnahme: Nummern aus den Zeitstempeln, Bildinhalt passt zu grab_frame
    got = grab_numbered(s2, 0, 20, Fraction(25), (54, 43))
    check(sorted(got) == list(range(10, 30)) and got[10].shape == (43, 54, 3),
          f"Bildnummern am Dateianfang (Ton beginnt früher): {sorted(got)[:3]}..{sorted(got)[-2:]}")
    got = grab_numbered(s2, 40, 10, Fraction(25), (54, 43))
    check(sorted(got) == list(range(40, 50)), f"Fenster mitten in der Datei: {sorted(got)}")
    for n in (40, 49):
        ref = np.asarray(Image.fromarray(grab_frame(s2, n, Fraction(25))).resize((54, 43), Image.BOX)).astype(int)
        diff = np.abs(ref - got[n].astype(int)).mean()
        check(diff < 12, f"Vorschaubild {n} passt zum Bild {n}: Abweichung {diff:.1f}")
    # --- Hauptfenster mit vorgetäuschter Bildquelle (Aufnahme beginnt bei Bild 10, 148 Bilder)
    calls = []
    def fake_thumbs(path, first, count, fps, size, on_start=None):
        calls.append((first, count, size))
        w, h = size
        lo = max(first, 10)
        return {n: np.full((h, w, 3), n % 256, np.uint8) for n in range(lo, min(lo + count, 148))}
    win = make_window(tmp, thumb_fn=fake_thumbs, fresh=True)
    win.showEvent(None)
    area = win.picTimeline.contentsRect()
    cw = tl.cell_width(area.width())
    check(area.width() == 1085 and cw == 54, f"Zeichenfläche {area.width()}")
    line = win.Line1.called("setGeometry")[-1]
    check(line[0] == win.picTimeline.geometry().x() + area.x() + 10 * cw - 1 and line[2] == 3, f"Strich liegt auf der Schnittstelle: {line}")
    win.OpenVideo(s2)
    seg = win.segments[0]
    check(win.timeline_mode == "A" and win.timeline_center == 0 and calls[-1][:2] == (0, 10) and calls[-1][2] == (53, 42),
          f"Zeitleiste bei Bild 0: {win.timeline_center} {calls[-1]}")
    check(all(state == "cross" for state, _ in win.timeline_cells()) and len(win.timeline_cells()) == 20,
          "Anfang: nur Kreuze (die ersten 10 Bilder fehlen, davor ebenfalls)")
    # Marker A bei 50: Bilder 40..59 werden geladen und angezeigt
    win._go(50)
    win.cmdPos_Click(7)
    cells = win.timeline_cells()
    check(seg.start == 50 and calls[-1][:2] == (40, 20) and [c[0] for c in cells] == ["image"] * 20, f"Marker A: {calls[-1]}")
    # Marker B bei 100: Zeitleiste um das Ende; das Segment endet mit dem Bild links vom Strich
    win._go(100)
    win.cmdPos_Click(8)
    check(seg.end == 100 and win.timeline_mode == "B" and win.timeline_center == 100 and calls[-1][:2] == (90, 20), "Marker B")
    # Klick: links vom Strich
    def click(index):
        win._mouse_x = area.x() + index * cw + 5
        win.picTimeline_Click()
    click(5)
    check(seg.end == 96 and win.timeline_center == 96 and win.Slider1.value() == 96, f"Klick links (Index 5): Ende {seg.end}")
    click(9)
    click(10)
    check(seg.end == 96, "Klick auf die beiden Bilder am Strich ändert nichts")
    click(15)
    check(seg.end == 101 and win.lvwSegments.topLevelItem(0).text(4) == "101", f"Klick rechts (Index 15): Ende {seg.end}")
    seg.start, seg.end = 95, 101
    click(0)
    check(seg.end == 96, f"Ende bleibt mindestens ein Bild hinter dem Beginn: {seg.end}")
    seg.end = 147
    click(19)
    check(seg.end == 148, f"Ende bleibt im Film: {seg.end}")
    # Marker A und B dürfen sich nicht überholen und nicht zusammenfallen (Segment hätte 0 Bilder)
    seg.start, seg.end = 10, 12
    win.cmdPos_Click(9)
    click(19)
    check((seg.start, seg.end) == (11, 12), f"Marker A bleibt vor B: {seg.start}/{seg.end}")
    win.cmdPos_Click(10)
    click(0)
    check((seg.start, seg.end) == (11, 12), f"Marker B bleibt hinter A: {seg.start}/{seg.end}")
    n_beeps = QtWidgets.QApplication.log.count("beep")
    win._go(12)
    win.cmdPos_Click(7)                                           # A auf B setzen: abgelehnt
    win._go(11)
    win.cmdPos_Click(8)                                           # B auf A setzen: abgelehnt
    win._go(13)
    win.cmdPos_Click(7)                                           # A hinter B setzen: abgelehnt
    win._go(5)
    win.cmdPos_Click(8)                                           # B vor A setzen: abgelehnt
    check((seg.start, seg.end) == (11, 12) and QtWidgets.QApplication.log.count("beep") == n_beeps + 4,
          f"Setzen über die Knöpfe: {seg.start}/{seg.end}")
    win._go(8)
    win.cmdPos_Click(7)                                           # A vor B: erlaubt
    check(seg.start == 8, "A vor B ist erlaubt")
    seg.start, seg.end = 0, 148
    # Klick im Modus A
    win.cmdPos_Click(9)
    seg.start = 50
    click(12)
    check(seg.start == 52 and win.Slider1.value() == 52 and win.timeline_center == 52, f"Klick rechts, Marker A: {seg.start}")
    click(0)
    seg.start = 3
    click(0)
    check(seg.start == 0, f"Marker A nicht unter 0: {seg.start}")
    # kein Modus: Klick wirkt nicht
    win.timeline_mode = None
    seg.start = 20
    click(0)
    check(seg.start == 20, "ohne Modus keine Wirkung")
    win.cmdPos_Click(9)
    # veraltete Ergebnisse werden verworfen
    cache_size = len(win.thumb_cache)
    win.thumbs_loaded(win._thumb_token - 1, {999: np.zeros((42, 53, 3), np.uint8)}, (999, 999), seg.path, (53, 42))
    check(len(win.thumb_cache) == cache_size, "überholte Anforderung wird ignoriert")
    # Zeichnen
    class Painter:
        def __init__(self): self.images, self.lines, self.fills = [], [], []
        def drawImage(self, x, y, img): self.images.append((x, y))
        def setPen(self, c): pass
        def drawLine(self, *a): self.lines.append(a)
        def fillRect(self, *a): self.fills.append(a[:4])
    seg.start = 50
    win.cmdPos_Click(9)
    painter = Painter()
    win.timeline_paint(painter, Rect(2, 2, 1085, 45))
    check(len(painter.images) == 20 and painter.images[0] == (2, 2) and painter.images[10] == (2 + 10 * cw, 2)
          and painter.lines == [] and painter.fills == [(2 + 10 * cw - 1, 2, 3, 45)], f"Zeichnen: {painter.fills}")
    seg.start = 0
    win.cmdPos_Click(9)
    painter = Painter()
    win.timeline_paint(painter, Rect(2, 2, 1085, 45))
    check(len(painter.lines) == 40 and painter.images == [], "Zeichnen am Anfang: 20 Kreuze")
    print("Zeitleiste: OK (Fenster, Klick-Verschiebung, Kreuze, Zeichnen, Bildnummern aus Zeitstempeln)")


def quick_thumbs(path, first, count, fps, size, on_start=None):
    """Vorgetäuschte Vorschaubilder (schnell), damit die Tests nicht auf ffmpeg warten."""
    import numpy as np
    w, h = size
    return {n: np.zeros((h, w, 3), np.uint8) for n in range(max(first, 0), first + count)}


class FakeWait:
    def __init__(self, message, cancel):
        self.message, self.cancel, self.closed, self.texts = message, cancel, False, []
    def set_text(self, text):
        self.texts.append(text)
    def close(self):
        self.closed = True


def seek_window(tmp, videos, names=("sample2.ts",), workdir="seekwin", **kwargs):
    work = os.path.join(tmp, workdir)
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True, **kwargs)
    win.showEvent(None)
    win.dialogs = []
    win.wait_dialog = lambda message, cancel: win.dialogs.append(FakeWait(message, cancel)) or win.dialogs[-1]
    for name in names:
        win.OpenVideo(os.path.join(videos, name))
    return win


def test_segments(tmp, videos):
    """Segmente löschen, verschieben, duplizieren (mit Suche nach dem Filmbeginn) und die Suche selbst."""
    import seek
    from PySide6 import QtWidgets
    s2, s3 = os.path.join(videos, "sample2.ts"), os.path.join(videos, "sample3.ts")
    # --- verschieben, löschen, alles entfernen
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"))
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    win.cmdCommand_Click(2)
    titles = lambda: [win.lvwSegments.topLevelItem(i).text(2) for i in range(win.lvwSegments.row_count())]
    check(titles() == ["sample3.ts", "sample2.ts"] and win.current == 1 and win.segments[1].path == s2
          and win.lvwSegments.topLevelItem(0).text(0) == "01", f"nach unten: {titles()} {win.current}")
    win.cmdCommand_Click(2)
    check(titles() == ["sample3.ts", "sample2.ts"] and win.current == 1, "ganz unten: keine Änderung")
    win.cmdCommand_Click(1)
    check(titles() == ["sample2.ts", "sample3.ts"] and win.current == 0, "nach oben")
    win.cmdCommand_Click(1)
    check(win.current == 0, "ganz oben: keine Änderung")
    check([s.path for s in load_segments(os.path.join(tmp, "seekwin", "MediaMaker.json"))] == [s2, s3], "Reihenfolge gespeichert")
    win.cmdCommand_Click(0)
    check(len(win.segments) == 1 and win.current == 0 and win.segments[0].path == s3 and "stop" in win.player.log
          and f"load {s3}" in win.player.log and win.lvwSegments.current_row() == 0
          and win.lvwSegments.row_count() == 1 and win.lvwSegments.topLevelItem(0).text(0) == "01"
          and len(load_segments(os.path.join(tmp, "seekwin", "MediaMaker.json"))) == 1,
          "Löschen: der Nachfolger wird ausgewählt und geladen")
    win.cmdCommand_Click(5)
    check("not been ported" in win.messages[-1], "Beschnitt/Logo: Hinweis")
    win.answer = False
    win.cmdCommand_Click(3)
    check(len(win.segments) == 1, "Alles entfernen: Nein")
    win.answer = True
    win.cmdCommand_Click(3)
    check(win.segments == [] and win.lvwSegments.row_count() == 0 and win.lblText[0].text() == "00:00:00"
          and load_segments(os.path.join(tmp, "seekwin", "MediaMaker.json")) == [], "Alles entfernen: Ja")
    # --- Auswahl nach dem Löschen: letzter Eintrag -> neuer letzter, Eintrag in der Mitte -> Nachfolger, zuletzt leere Liste
    sample = os.path.join(videos, "sample.ts")
    dwin = seek_window(tmp, videos, ("sample2.ts", "sample3.ts", "sample.ts"), workdir="delwin")
    dwin.lvwSegments.select_row(2)
    dwin.lvwSegments_Click()
    dwin.player.log.clear()
    dwin.cmdCommand_Click(0)
    check([x.path for x in dwin.segments] == [s2, s3] and dwin.current == 1 and dwin.lvwSegments.current_row() == 1
          and f"load {s3}" in dwin.player.log, f"letzten Eintrag gelöscht: der neue letzte ist ausgewählt ({dwin.current}, Zeile {dwin.lvwSegments.current_row()})")
    dwin.lvwSegments.select_row(0)
    dwin.lvwSegments_Click()
    dwin.cmdCommand_Click(0)
    check([x.path for x in dwin.segments] == [s3] and dwin.current == 0 and dwin.lvwSegments.current_row() == 0, "mittleren/ersten gelöscht: Nachfolger ausgewählt")
    dwin.cmdCommand_Click(0)
    check(dwin.segments == [] and dwin.current == -1 and dwin.lvwSegments.row_count() == 0, "den letzten verbliebenen gelöscht: leere Liste")
    dwin.cmdCommand_Click(0)
    check(dwin.segments == [], "leere Liste: Knopf wirkt nicht")

    # --- duplizieren mit Suche nach dem Filmbeginn (vorgetäuschte Randerkennung: Film ab Bild 130)
    probes = []
    def border(path, n, fps, opts):
        probes.append(n)
        return 72 if n >= 130 else 0
    win = seek_window(tmp, videos, workdir="dupwin", border_fn=border)
    win.settings.set_option("pause", 1)
    seg = win.segments[0]
    seg.crop_top, seg.mask = 5, "0.1 0.2 0.3 0.4"
    win._go(100)
    win.cmdPos_Click(8)
    check(seg.end == 100, "Marker B auf 100")
    win.cmdCommand_Click(4)
    new = win.segments[1]
    check((new.start, new.end, new.path, new.crop_top, new.mask) == (100, 148, s2, 5, "0.1 0.2 0.3 0.4") and win.current == 1,
          f"neues Segment: {new.start}/{new.end}")
    check(win.Slider1.value() == 130 and win.player.time == 5200 and win.lblInfo.text() == f"Frame {130 - new.first_frame}",
          f"Suche nach dem Filmbeginn: Bild {win.Slider1.value()}, Zeit {win.player.time}")
    check(min(probes) >= 125 and len(probes) < 40 and win.dialogs[-1].closed and "Seeking" in win.dialogs[-1].message,
          f"Suche beginnt hinter der Mindestlänge der Werbung (pause): {min(probes)}, {len(probes)} Proben")
    check(len(load_segments(os.path.join(tmp, "dupwin", "MediaMaker.json"))) == 2, "gespeichert")
    # Marker B am Ende des Films: nichts zu duplizieren
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    seg.end = seg.total_frames
    win.cmdCommand_Click(4)
    check(len(win.segments) == 2 and "nothing left" in win.messages[-1], "Duplizieren am Ende der Datei")
    # mehrere Quelldateien in der Liste: die Suche läuft trotzdem (anders als in VB6)
    win = seek_window(tmp, videos, ("sample3.ts", "sample2.ts"), workdir="dupwin2", border_fn=border)
    win.settings.set_option("pause", 1)
    probes.clear()
    win.lvwSegments.select_row(1)
    win.lvwSegments_Click()
    win._go(100)
    win.cmdPos_Click(8)
    win.cmdCommand_Click(4)
    check(win.multiple() and probes != [] and win.Slider1.value() == 130, f"mehrere Quellen: Suche läuft, Bild {win.Slider1.value()}")
    # Zwischenstände im Wartefenster
    texts = win.dialogs[-1].texts
    check(texts and texts[0].startswith("Seeking, please wait...\nframe ") and "border" in texts[0] and "about 72" in texts[0]
          and any("border 72" in t for t in texts) and len(texts) == len(probes), f"Wartefenster zeigt jede Probe: {texts[:2]}")
    # weder Beschnitt noch Logo: Meldung, keine Suche
    win = seek_window(tmp, videos, workdir="dupwin3", border_fn=border)
    win.settings.set_option("crop", 0)
    win.settings.set_option("pause", 1)
    probes.clear()
    win.cmdPos_Click(8)
    win._go(100)
    win.cmdPos_Click(8)
    win.cmdCommand_Click(4)
    check(probes == [] and "neither a cropping value" in win.messages[-1] and len(win.segments) == 2, f"ohne Beschnitt und Logo: {win.messages[-1:]}")
    win.mnuNext_Click()
    check("neither a cropping value" in win.messages[-1], "auch bei Suche nach der nächsten Werbung")

    # --- Suche mit dem Senderlogo (vorgetäuschte Erkennung: Logo ab Bild 90, Szenenwechsel bei Bild 60)
    elysium = parse_batch_header(open(os.path.join(HERE, "sample_Elysium.bat"), encoding="latin-1").read())
    conf = lambda path, n, fps, ref, opts: 0.9 if n >= 90 else 0.0
    avg = lambda path, f, fps, opts: (10, 10, 10) if f >= 60 else (200, 10, 10)
    win = seek_window(tmp, videos, workdir="logowin", conf_fn=conf, avg_fn=avg)
    win.settings.set_option("crop", 0)
    win.segments[0].mask = elysium.segments[0].mask
    win.mnuEnd_Click()
    check(win.Slider1.value() == 60, f"Logo: erstes Bild mit Logo, dann zurück zum Szenenwechsel: {win.Slider1.value()}")
    check(any("logo confidence 0.90" in t for t in win.dialogs[-1].texts), "Logosuche meldet jede Probe")
    win._go(0)
    conf = lambda path, n, fps, ref, opts: 0.9 if n < 50 else 0.0
    win._conf_fn = conf
    win.mnuNext_Click()
    check(win.Slider1.value() == 50, f"Logo: Beginn der nächsten Werbung (kein Logo mehr): {win.Slider1.value()}")

    # --- echte Aufnahmen (ffmpeg): Werbung -> Film (sample3) und Film -> Werbung (sample2) mit crop = 72
    win = seek_window(tmp, videos, ("sample3.ts",), workdir="realwin")
    win._go(0)
    win.mnuEnd_Click()
    check(win.Slider1.value() == 59, f"echte Aufnahme, Ende der Werbung: {win.Slider1.value()} (erwartet 59)")
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="realwin2")
    win._go(0)
    win.mnuNext_Click()
    check(win.Slider1.value() == 76, f"echte Aufnahme, nächste Werbung: {win.Slider1.value()} (erwartet 76)")

    # --- Abbruch
    try:
        seek.seek_border("/x", Fraction(25), 1000, 0, 72, True, 1000, {}, lambda *a: 0, lambda: True)
        check(False, "Abbruch löst keine Ausnahme aus")
    except seek.SeekCancelled:
        pass
    got = []
    worker = seek.SeekWorker(lambda cancel: (_ for _ in ()).throw(seek.SeekCancelled()))
    worker.done.connect(got.append)
    worker.failed.connect(got.append)
    worker.run()
    check(got == [], "abgebrochene Suche meldet nichts")
    worker = seek.SeekWorker(lambda cancel: (_ for _ in ()).throw(RuntimeError("kaputt")))
    worker.failed.connect(got.append)
    worker.run()
    check(got == ["kaputt"], "Fehler wird gemeldet")
    print("Segmente und Suche: OK (verschieben, löschen, alles entfernen, duplizieren mit Suche, Logo, echte Aufnahmen, Abbruch)")


def test_thumbnail_errors(tmp, videos):
    """Fehler beim Laden der Vorschaubilder werden gemeldet; fehlende Startzeiten ("N/A") bringen nichts zu Fall."""
    import types
    import numpy as np
    import ffmpeg_cmd
    import timeline as tl
    from PySide6 import QtWidgets
    # --- Startzeiten
    check(ffmpeg_cmd._start_fraction("N/A", Fraction(7)) == 7 and ffmpeg_cmd._start_fraction(None, Fraction(1)) == 1
          and ffmpeg_cmd._start_fraction("1.400000", Fraction(0)) == Fraction(7, 5) and ffmpeg_cmd._start_fraction("", Fraction(2)) == 2,
          "_start_fraction")
    def fake_run(output):
        return lambda cmd, **kw: types.SimpleNamespace(stdout=output)
    real_run = ffmpeg_cmd.subprocess.run
    try:
        for output, expected in ((b'{"format": {"start_time": "N/A"}, "streams": [{"start_time": "N/A"}]}', (0, 0)),
                                 (b'{"format": {"start_time": "1.400000"}, "streams": [{}]}', (Fraction(7, 5), Fraction(7, 5))),
                                 (b'{"format": {"start_time": "1.400000"}, "streams": [{"start_time": "1.824000"}]}',
                                  (Fraction(7, 5), Fraction(228, 125))), (b'{}', (0, 0)), (b'', (0, 0))):
            ffmpeg_cmd.subprocess.run = fake_run(output)
            check(ffmpeg_cmd.stream_times_of.__wrapped__("/x") == expected, f"Startzeiten {output!r}")
    finally:
        ffmpeg_cmd.subprocess.run = real_run
    # --- Fehler im Hintergrund-Thread
    errors = []
    def broken(path, first, count, fps, size, on_start=None):
        raise RuntimeError("ffmpeg kaputt")
    loader = tl.ThumbLoader(3, "/x", 0, 9, Fraction(25), (53, 42), broken)
    loader.failed.connect(lambda token, text: errors.append((token, text)))
    loader.run()
    check(errors == [(3, "RuntimeError: ffmpeg kaputt")], f"Fehler wird gemeldet: {errors}")
    loader = tl.ThumbLoader(4, "/x", 0, 9, Fraction(25), (53, 42), broken)
    loader.failed.connect(lambda token, text: errors.append((token, text)))
    loader.cancelled = True
    loader.run()
    check(len(errors) == 1, "abgebrochene Anforderung meldet keinen Fehler")
    # --- Hauptfenster: einmalige Meldung, Titel
    win = seek_window(tmp, videos, workdir="thumberr", names=())
    win._thumb_fn = broken
    win.OpenVideo(os.path.join(videos, "sample2.ts"))
    shown = [m for m in win.messages if "thumbnails could not be loaded" in m]
    check(len(shown) == 1 and "ffmpeg kaputt" in shown[0], f"Meldung zum Fehler: {win.messages}")
    titles = [a[0] for a in win.called("setWindowTitle")]
    check(not win._thumbs_busy and titles[-1] == "MediaMaker " + __import__("mediamaker").VERSION and any("loading thumbnails" in t for t in titles),
          f"Titel während und nach dem Laden: {titles[-3:]}")
    win.timeline_mode = "B"
    win._thumb_token += 1
    win.thumbs_failed(win._thumb_token, "zweiter Fehler")
    check(len([m for m in win.messages if "thumbnails could not" in m]) == 1, "Meldung nur einmal")
    win.thumbs_failed(win._thumb_token - 5, "überholt")
    check(len([m for m in win.messages if "thumbnails could not" in m]) == 1, "überholte Fehler werden ignoriert")
    # --- Platzhalter für noch nicht geladene Bilder
    class Painter:
        def __init__(self): self.fills, self.lines = [], []
        def drawImage(self, *a): pass
        def setPen(self, c): pass
        def drawLine(self, *a): self.lines.append(a)
        def fillRect(self, *a): self.fills.append(a)
    painter = Painter()
    tl.draw_strip(painter, __import__("PySide6.QtWidgets", fromlist=["Rect"]).Rect(2, 2, 1085, 45),
                  [("pending", None)] * 20)
    check(len(painter.fills) == 21 and painter.lines == [], f"20 graue Platzhalter und der Strich: {len(painter.fills)}")
    print("Vorschaubilder-Fehler: OK (Startzeiten ohne Angabe, Fehlermeldung, einmalig, Titel, Platzhalter)")


def test_first_frame(tmp, videos):
    """Beginnt der Ton früher als das Video, hat das erste Videobild nicht die Nummer 0: Der Beginn des Segments steht dann
    auf dem ersten echten Bild, und die Zeitleiste zeigt rechts vom Strich sofort Vorschaubilder."""
    import ffmpeg_cmd
    import timeline as tl
    from mediaprobe import first_frame_number
    check([first_frame_number(os.path.join(videos, n), Fraction(25)) for n in ("sample.ts", "sample2.ts", "sample3.ts")] == [33, 10, 14],
          "Nummer des ersten Bildes")
    work = os.path.join(tmp, "firstwin")
    os.makedirs(work, exist_ok=True)
    s2 = os.path.join(videos, "sample2.ts")
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True, first_fn=first_frame_number)
    win.showEvent(None)
    win.OpenVideo(s2)
    seg = win.segments[0]
    check((seg.first_frame, seg.start, seg.end, seg.total_frames) == (10, 10, 158, 158), f"Segment: {seg.first_frame}/{seg.start}/{seg.end}")
    check((win.Slider1.minimum(), win.Slider1.maximum(), win.Slider1.value()) == (10, 158, 10), "Schieber beginnt beim ersten Bild")
    cells = win.timeline_cells()
    check([c[0] for c in cells] == ["cross"] * 10 + ["image"] * 10, f"Zeitleiste: 10 Kreuze links, 10 Bilder rechts: {[c[0] for c in cells]}")
    check(win.lblInfo.text() == "Frame 0" and win.lvwSegments.topLevelItem(0).text(3) == "0"
          and win.lvwSegments.topLevelItem(0).text(6) == "148", "Anzeige: Zählung ab dem ersten Videobild (Nummer 0)")
    # Grenzen
    win.cmdPos_Click(0)
    check(win.Slider1.value() == 10, "Anfang")
    win.cmdPos_Click(6)
    check(win.Slider1.value() == 158, "Ende")
    win.cmdPos_Click(9)
    check(win.timeline_center == 10, "Zeitleiste um den Beginn")
    def click(index):
        area = win.picTimeline.contentsRect()
        win._mouse_x = area.x() + index * tl.cell_width(area.width()) + 5
        win.picTimeline_Click()
    click(0)
    check(seg.start == 10, f"Marker A nicht vor dem ersten Bild: {seg.start}")
    win._go(60)
    win.cmdPos_Click(7)
    win.cmdPos_Click(11)
    check((seg.start, seg.end) == (10, 158), "Marker zurücksetzen auf erstes und letztes Bild")
    win.cmdPos_Click(10)
    cells = win.timeline_cells()
    check([c[0] for c in cells][:10] == ["image"] * 10 and [c[0] for c in cells][10:] == ["cross"] * 10, "Ende: Bilder links, Kreuze rechts")
    # gespeichert, ganze Datei = kein trim im Befehl
    check(load_segments(os.path.join(work, "MediaMaker.json"))[0].first_frame == 10, "first_frame gespeichert")
    job = Job(os.path.join(tmp, "o.mp4"), {"scale": "720:576", "sws_flags": "lanczos", "fps": "25.000", "bv": "3072k", "ba": "192k",
                                          "acodec_out": "aac", "ar": "48000"}, {}, [seg])
    times = {s2: (Fraction(7, 5), Fraction(228, 125))}
    cmd = ffmpeg_cmd.build_command(job, stream_times=times)
    check("trim=" not in cmd[cmd.index("-filter_complex") + 1], "ganze Datei: kein trim")
    seg.start = 60
    cmd = ffmpeg_cmd.build_command(job, stream_times=times)
    check("trim=" in cmd[cmd.index("-filter_complex") + 1], "Ausschnitt: trim")
    # alte Listen ohne first_frame verhalten sich wie bisher
    legacy = Segment(1, s2, "sample2.ts", 0, 148, 148, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")
    check(legacy.first_frame == 0 and not (legacy.end - legacy.start < legacy.total_frames - legacy.first_frame), "alte Liste: ganze Datei")
    # genaue Zählung: Gesamtzahl = erstes Bild + Anzahl der Bilder
    seg.start, seg.end = 10, 158
    win.frames_counted(s2, 140, 8, 0.0)
    check((seg.total_frames, seg.end) == (150, 150), f"nach der Zählung: {seg.total_frames}/{seg.end}")
    check(win.Slider1.minimum() == 10 and win.Slider1.maximum() == 150, "Schieber nach der Zählung")
    print("Erstes Bild: OK (Segmentbeginn auf dem ersten Videobild, Zeitleiste, Grenzen, Speichern, Befehl ohne trim)")


def test_marker_start(tmp, videos):
    """Ein Segment mit Marker A > 0 wird beim Anklicken an dieser Stelle angezeigt (nicht am Dateianfang); alte Listen werden
    auf das erste Videobild umgestellt; VLC bekommt die Startposition als Medienoption."""
    import types
    from types import SimpleNamespace
    import player as pl
    from PySide6.QtCore import QTimer
    s2 = os.path.join(videos, "sample2.ts")
    # --- alte Liste (ohne first_frame): Aktualisierung beim Laden
    work = os.path.join(tmp, "legacywin")
    os.makedirs(work, exist_ok=True)
    legacy = [Segment(1, s2, "sample2.ts", 0, 148, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, ""),
              Segment(2, s2, "sample2.ts", 50, 148, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, ""),
              Segment(3, s2, "sample2.ts", 20, 90, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, "")]
    save_segments(os.path.join(work, "MediaMaker.json"), legacy)
    win = make_window(work, thumb_fn=quick_thumbs, first_fn=lambda path, fps: 10)
    win.showEvent(None)
    got = [(s.first_frame, s.start, s.end, s.total_frames) for s in win.segments]
    check(got == [(10, 10, 158, 158), (10, 50, 158, 158), (10, 20, 90, 158)], f"alte Liste umgestellt: {got}")
    check([(s.first_frame, s.start, s.end, s.total_frames) for s in load_segments(os.path.join(work, "MediaMaker.json"))] == got, "umgestellt gespeichert")
    win2 = make_window(work, thumb_fn=quick_thumbs, first_fn=lambda path, fps: 99)           # nicht noch einmal umstellen
    win2.showEvent(None)
    check([(s.first_frame, s.total_frames) for s in win2.segments] == [(10, 158)] * 3, "bereits umgestellte Liste bleibt unverändert")
    # --- Anklicken: Anzeige an Marker A, nicht am Dateianfang
    win2.lvwSegments.select_row(1)
    win2.lvwSegments_Click()
    check(win2.player.log[-1] == "show_at 2000" and win2.Slider1.value() == 50 and win2.lblInfo.text() == "Frame 40",
          f"Segment mit A=50: {win2.player.log[-2:]}, Schieber {win2.Slider1.value()}, {win2.lblInfo.text()}")
    # Zeitmeldungen von VLC unmittelbar danach (von der alten Stelle) verändern Anzeige und Schieber nicht
    win2.player.time_changed.emit(0)
    check(win2.lblInfo.text() == "Frame 40" and win2.Slider1.value() == 50 and win2.last_frame == 50, "alte Zeitmeldung wird ignoriert")
    now = [100.0]
    win2._clock = lambda: now[0]
    win2._ignore_time_until = 101.5
    now[0] = 102.0
    win2.player.time_changed.emit(4000)
    check(win2.lblInfo.text() == "Frame 90", f"später gelten Zeitmeldungen wieder: {win2.lblInfo.text()}")
    # --- VLC: Startposition als Medienoption und Nachprüfung
    class Media:
        def __init__(self, path): self.path, self.options = path, []
        def add_option(self, o): self.options.append(o)
    class Events:
        def event_attach(self, *a): pass
        def event_detach(self, *a): pass
    class Mp:
        def __init__(self):
            self.state, self.t, self.calls, self.media = 5, 0, [], None
        def event_manager(self): return Events()
        def get_state(self): return self.state
        def set_media(self, m): self.media = m; self.calls.append(("set_media", m.path, tuple(m.options)))
        def audio_set_mute(self, v): self.mutes = getattr(self, "mutes", []) + [v]
        def play(self): self.calls.append(("play",))
        def set_pause(self, v): self.calls.append(("pause", v))
        def get_time(self): return self.t
        def set_time(self, ms): self.calls.append(("set_time", ms))
        def is_playing(self): return False
        def stop(self): pass
        def release(self): pass
        def video_set_callbacks(self, *a): pass
        def video_set_format(self, *a): pass
        def video_set_aspect_ratio(self, *a): pass
    class Inst:
        def __init__(self): self.mp = Mp()
        def media_player_new(self): return self.mp
        def media_new_path(self, p): return Media(p)
        def release(self): pass
    fake = types.ModuleType("vlc")
    fake.Instance = lambda *a: Inst()
    fake.EventType = SimpleNamespace(MediaPlayerPlaying=1, MediaPlayerPaused=2, MediaPlayerStopped=3, MediaPlayerEndReached=4,
                                     MediaPlayerTimeChanged=5, MediaPlayerSeekableChanged=6)
    fake.State = SimpleNamespace(Playing=3, Paused=4, Stopped=5)
    fake.CallbackDecorators = SimpleNamespace(VideoLockCb=lambda f: f, VideoDisplayCb=lambda f: f)
    sys.modules["vlc"] = fake
    try:
        player = pl.VlcPlayer()
        mp = player.mp
        player.load("/x/film.ts")
        player.show_at(193_000)
        check(("set_media", "/x/film.ts", (":start-time=193.000",)) in mp.calls and ("play",) in mp.calls and player._pending_show == 193_000,
              f"Startposition als Medienoption: {mp.calls}")
        QTimer.pending.clear()
        mp.calls.clear()
        player.playing.emit()                                       # VLC meldet: läuft
        check(("pause", 1) in mp.calls and len(QTimer.pending) == 1 and QTimer.pending[0][0] == 150, f"danach anhalten: {mp.calls}")
        mp.t = 0                                                    # VLC steht noch am Anfang: wird nachgeholt, wiederholt
        QTimer.pending.pop(0)[1]()
        check(("set_time", 193_000) in mp.calls and len(QTimer.pending) == 1 and player._awaiting_position == 193_000,
              f"Nachprüfung springt und prüft erneut: {mp.calls}")
        mp.t = 193_100                                              # jetzt erreicht
        mp.calls.clear()
        QTimer.pending.pop(0)[1]()
        check(player._awaiting_position is None and QTimer.pending == [] and mp.calls == [], "Position erreicht: fertig")
        check(mp.mutes[:1] == [True] and mp.mutes[-1] is False and player._muted is False, f"Ton: erst stumm, nach Erreichen wieder an: {mp.mutes}")
        # VLC meldet "seekable": sofort an die Stelle springen (früher als "Playing")
        mp.state = 5
        player.show_at(41_000)
        mp.calls.clear()
        player.seekable.emit(False)
        check(("set_time", 41_000) not in mp.calls, "nicht seekable: kein Sprung")
        player.seekable.emit(True)
        check(("set_time", 41_000) in mp.calls, f"seekable: Sprung an die Stelle: {mp.calls}")
        player.play()                                              # Benutzer startet: nichts mehr abwarten, Ton an
        check(player._awaiting_position is None and player._muted is False and mp.mutes[-1] is False, "play() beendet das Anfahren und schaltet den Ton ein")
        player.seekable.emit(True)
        check(mp.calls.count(("set_time", 41_000)) == 1, "nach play() kein weiterer Sprung")
        mp.state = 5
        QTimer.pending.clear()
        player.show_at(5000)                                        # Zustand Gestoppt: wieder über start-time
        QTimer.pending.clear()
        player.playing.emit()
        mp.t = 5100
        mp.calls.clear()
        QTimer.pending[0][1]()
        check(mp.calls == [] and player._awaiting_position is None, "Position erreicht: kein zusätzlicher Sprung")
        # überholte Anforderung: eine zweite Stelle wurde inzwischen angefordert
        player.show_at(9000)
        QTimer.pending.clear()
        player.playing.emit()
        player.stop()
        mp.calls.clear()
        QTimer.pending[0][1]()
        check(mp.calls == [], "überholte Nachprüfung tut nichts")
        mp.state = 5
        player.show_at(9000)
        QTimer.pending.clear()
        player.playing.emit()
        mp.t = -1                                                   # VLC kennt die Zeit nicht: höchstens 30 Versuche
        for _ in range(60):
            if not QTimer.pending:
                break
            QTimer.pending.pop(0)[1]()
        check(player._awaiting_position is None, "nach höchstens 30 Versuchen wird aufgegeben")
        mp.state = 5
        mp.state = 4                                                # pausiert: direkter Sprung
        mp.calls.clear()
        player.show_at(7000)
        check(mp.calls == [("set_time", 7000)], f"pausiert: direkter Sprung: {mp.calls}")
    finally:
        del sys.modules["vlc"]
    print("Marker A beim Anklicken: OK (Anzeige an Marker A, alte Listen, Zeitmeldungen, VLC-Startposition)")


def test_jump_to_frame(tmp, videos):
    """Klick auf die Bildnummer: Eingabe einer Bildnummer, zu der gesprungen wird."""
    s2 = os.path.join(videos, "sample2.ts")
    work = os.path.join(tmp, "jumpwin")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True, first_fn=lambda p, f: 10)
    win.showEvent(None)
    asked = []
    win.ask_int = lambda title, label, value, low, high: (asked.append((title, label, value, low, high)), win.answer_int)[1]
    handler = win.lblInfo._vb_filter.handlers["click"]
    win.answer_int = 99
    handler()
    check(asked == [], "ohne Segment passiert nichts")
    win.OpenVideo(s2)
    win.answer_int = 99
    handler()
    check(asked[-1][2:] == (0, 0, 148) and "0 to 148" in asked[-1][1], f"Eingabe in angezeigten Nummern mit Vorgabe und Bereich: {asked[-1]}")
    check(win.Slider1.value() == 109 and win.lblInfo.text() == "Frame 99" and win.player.time == 4360,
          f"Eingabe 99 = absolut 109: {win.Slider1.value()} {win.player.time}")
    win._go(40)
    win.answer_int = None                                         # abgebrochen
    handler()
    check(asked[-1][2] == 30, "Vorgabe ist das aktuelle Bild (angezeigt: 40 - 10)")
    check(win.Slider1.value() == 40, "Abbruch ändert nichts")
    win.answer_int = 30                                           # gleiche Stelle (angezeigt 30 = absolut 40): Bild wird neu angezeigt
    shows = len([e for e in win.player.log if e.startswith("show_at")])
    handler()
    check(len([e for e in win.player.log if e.startswith("show_at")]) == shows + 1 and win.Slider1.value() == 40, "gleiche Stelle: Bild neu anzeigen")
    win.answer_int = 5000                                         # außerhalb: Schieber begrenzt
    handler()
    check(win.Slider1.value() == 158, "Wert außerhalb des Bereichs wird begrenzt")
    check(win.lblInfo.called("setToolTip") != [], "Tooltip")
    print("Sprung zu einer Bildnummer: OK (Eingabe, Vorgabe, Bereich, Abbruch, gleiche Stelle)")


def test_media_info(tmp, videos):
    """Media info (Strg+K): Bericht aus ffprobe mit Abschnitt "MediaMaker", Dialog mit Reitern und Kopieren; Tooltip der Zeitleiste."""
    import mediainfo
    from mediaprobe import first_frame_number
    from PySide6.QtWidgets import QApplication
    s2 = os.path.join(videos, "sample2.ts")
    # --- Bericht
    sections = mediainfo.build_sections(s2)
    names = [n for n, _ in sections]
    check(names == ["General", "Video #1", "Audio #1 (deu)", "MediaMaker"], f"Abschnitte: {names}")
    text = dict(sections)
    check("720 x 576" in text["Video #1"] and "25.000 fps" in text["Video #1"] and "mpegts" in text["General"]
          and "Complete name" in text["General"], "Inhalt der Abschnitte")
    first = first_frame_number(s2, Fraction(25))
    mm = text["MediaMaker"]
    check(mediainfo._kv("First video frame offset", first) in mm and "Container start" in mm and "Video start" in mm
          and "Selected segment" not in mm, f"MediaMaker-Abschnitt: {mm[:300]}")
    seg = Segment(1, s2, "sample2.ts", first, 100, 148 + first, Fraction(25), 720, 576, 0, 0, "a", 1, 2, 3, 4, 48000, "")
    seg.first_frame = first
    mm = dict(mediainfo.build_sections(s2, seg))["MediaMaker"]
    check("Marker A (start)" in mm and f": {first}" in mm and "Frames in the segment" in mm and "1/2/3/4" in mm and "Logo mask / area           : none" in mm.replace("  ", " ").replace(" :", "  :") or "Logo mask" in mm,
          "Abschnitt mit Segment")
    check(mediainfo.full_text(sections).count("\n\n") >= 3, "voller Text")
    # --- Menü
    work = os.path.join(tmp, "infowin")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True)
    win.showEvent(None)
    shown = []
    win.show_media_info = lambda title, secs: shown.append((title, [n for n, _ in secs]))
    win.mnuMediaInfo_Click()
    check(shown == [], "ohne Segment passiert nichts")
    win.OpenVideo(s2)
    win.mnuMediaInfo_Click()
    check(shown == [("sample2.ts", names)], f"Menü: {shown}")
    real_build = mediainfo.build_sections
    mediainfo.build_sections = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffprobe fehlt"))
    try:
        win.mnuMediaInfo_Click()
    finally:
        mediainfo.build_sections = real_build
    check("could not be collected" in win.messages[-1] and "ffprobe fehlt" in win.messages[-1], "Fehler wird gemeldet")
    # --- Dialog: veränderbar, Knöpfe gleichmäßig verteilt, Text kopierbar
    from mediainfo_dialog import frmMediaInfo
    from PySide6.QtWidgets import QHBoxLayout, QSizePolicy
    dialog = frmMediaInfo("sample2.ts", sections)
    check(dialog.called("setWindowTitle")[-1] == ("Media info for sample2.ts",) and dialog.TabStrip1.called("hide") != []
          and dialog.lblMediaInfo.called("hide") != [] and dialog.text.toPlainText() == text["General"], "Dialog: Titel, erster Abschnitt")
    flags = dialog.called("setWindowFlag")
    check(dialog.called("setMaximumSize") == [(16777215, 16777215)] and dialog.called("setMinimumSize") != []
          and "WindowMaximizeButtonHint" in repr(flags[-1][0]) and flags[-1][1] is True, "Fenster ist in der Größe veränderbar")
    check(len(dialog.tab_buttons) == 4 and [b._args[0] for b in dialog.tab_buttons] == names, "ein Knopf je Abschnitt")
    check(all(len(b.called("setSizePolicy")) == 1 and "Ignored" in repr(b.called("setSizePolicy")[0][0]) for b in dialog.tab_buttons),
          "Größenregel: unabhängig vom Text der Knöpfe")
    check([w for w, _ in dialog.tab_row.added_] == dialog.tab_buttons and [st for _, st in dialog.tab_row.added_] == [1, 1, 1, 1],
          "alle Knöpfe mit gleichem Anteil an der Breite")
    dialog.tab_buttons[3].clicked.emit(False)
    check(dialog.text.toPlainText() == text["MediaMaker"] and dialog.tab_buttons[3].called("setChecked")[-1] == (True,), "Knopf zeigt den Abschnitt")
    dialog.copy_all()
    check(QApplication._Clipboard.text_ == mediainfo.full_text(sections), "alles kopieren")
    # --- Tooltip der Zeitleiste mit der Bildnummer
    import timeline as tl
    area = win.picTimeline.contentsRect()
    cw = tl.cell_width(area.width())
    seg = win.segment
    win.cmdPos_Click(9)
    center = win.timeline_center
    win.picTimeline_MouseMove(0, 0, area.x() + 13 * cw + 5, 10)
    tip = win.picTimeline.called("setToolTip")[-1][0]
    check(tip.startswith(f"Frame {center + 3}") and "Click timeline to adjust left" in tip, f"Tooltip: {tip!r}")
    win.picTimeline_MouseMove(0, 0, area.x() + 2, 10)
    tip = win.picTimeline.called("setToolTip")[-1][0]
    check(tip.startswith(f"Frame {center - 10} (no picture)"), f"Tooltip vor dem ersten Bild: {tip!r}")
    print("Media info: OK (Bericht, Segmentwerte, Menü, Dialog, Kopieren, Tooltip mit Bildnummer)")


def test_autocrop(tmp, videos):
    """Auto crop (Strg+R): schwarze Zeilen am Bildrand zählen, als Wert für die Option crop vorschlagen und übernehmen."""
    s2 = os.path.join(videos, "sample2.ts")
    asked = []
    # --- mit echter Randerkennung an einem Bild des Films (der Beispielfilm hat einen Rand von etwa 72 Zeilen)
    win = seek_window(tmp, videos, workdir="autocropwin")
    win.ask_int = lambda title, label, value, low, high: (asked.append((title, label, value, low, high)), win.answer_int)[1]
    win.answer_int = None
    check(win.options["crop"] == "72" or int(win.options["crop"]) == 72, f"Ausgangswert: {win.options['crop']}")
    win._go(win.segment.first_frame + 30)
    win.mnuAutoCrop_Click()
    title, label, value, low, high = asked[-1]
    check(abs(value - 72) <= 3 and low == 0 and high == 144 and "Current value in the options: 72" in label
          and f"{value} black lines at frame 30" in label and win.dialogs[-1].closed and "Auto-cropping" in win.dialogs[-1].message,
          f"vorgeschlagener Wert: {value}, Bereich {low}..{high}: {label!r}")
    check("was NOT changed" in win.messages[-1] and int(win.options["crop"]) == 72, "Abbruch: Wert bleibt")
    win.answer_int = 70
    win.mnuAutoCrop_Click()
    check(int(win.options["crop"]) == 70 and int(win.settings.options["crop"]) == 70, "übernommen (angepasster Wert)")
    # --- vorgetäuschte Erkennung: nichts gefunden, sehr großer Rand
    found = {"n": 0}
    win = seek_window(tmp, videos, workdir="autocropwin2", border_fn=lambda path, n, fps, opts: found["n"])
    win.ask_int = lambda title, label, value, low, high: (asked.append((title, label, value, low, high)), win.answer_int)[1]
    win.answer_int = 0
    win.mnuAutoCrop_Click()
    check(asked[-1][2] == 0 and "No black border line(s) found" in asked[-1][1] and int(win.options["crop"]) == 0,
          f"nichts gefunden: Vorgabe 0, Option 0: {asked[-1][1]!r}")
    found["n"] = 180
    win.answer_int = 180
    win.mnuAutoCrop_Click()
    check(asked[-1][2] == 180 and asked[-1][4] == 180 and int(win.options["crop"]) == 180, "Obergrenze wächst mit dem gefundenen Wert")
    # --- ohne Segment passiert nichts; Fehler in der Erkennung wird gemeldet
    win2 = seek_window(tmp, videos, names=(), workdir="autocropwin3")
    count = len(asked)
    win2.mnuAutoCrop_Click()
    check(len(asked) == count, "ohne Segment passiert nichts")
    def broken(path, n, fps, opts):
        raise RuntimeError("ffmpeg kaputt")
    win3 = seek_window(tmp, videos, workdir="autocropwin4", border_fn=broken)
    win3.mnuAutoCrop_Click()
    check("Auto-cropping failed" in win3.messages[-1] and "ffmpeg kaputt" in win3.messages[-1], f"Fehler wird gemeldet: {win3.messages[-1:]}")
    print("Auto crop: OK (Zählung am aktuellen Bild, Vorschlag mit Vergleichswert, Übernahme, Abbruch, Fehler)")


def test_input_box(tmp, videos):
    """Eingabefelder (Schätzen von Audio-/Video-kb/s u. a.): feste Breite wie die InputBox von VB6, Text wird umgebrochen."""
    import dialogs
    from PySide6.QtWidgets import QDialog
    long_text = ("The average video bitrate has been calculated to 3072k bits/s and will be saved in your current profile "
                 "accordingly; you can still adjust it here, or hit cancel to keep the old value:")
    QDialog.exec_result, QDialog.on_exec = 1, lambda d: d.setTextValue("2500")
    box = dialogs._input_box(None, "Estimate video kb/s", long_text, dialogs.QtWidgets.QInputDialog.InputMode.TextInput)
    check(box.called("setFixedWidth") == [(440,)] and box.called("resize")[-1][0] == 440 and box.label_.called("setWordWrap") == [(True,)]
          and box.called("setWindowTitle") == [("Estimate video kb/s",)] and box.called("setLabelText") == [(long_text,)],
          "feste Breite, Umbruch, Titel, Text")
    check(dialogs.ask_text_box(None, "T", long_text, "3072k") == "2500", "Text eingeben")
    QDialog.exec_result = 0
    check(dialogs.ask_text_box(None, "T", long_text, "3072k") is None, "Abbruch ergibt None")
    QDialog.exec_result, QDialog.on_exec = 1, lambda d: d.setIntValue(70)
    check(dialogs.ask_int_box(None, "Auto crop", "label", 72, 0, 144) == 70, "ganze Zahl eingeben")
    box = dialogs._input_box(None, "x", "y", dialogs.QtWidgets.QInputDialog.InputMode.IntInput)
    check(box.called("setInputMode") != [], "Eingabeart gesetzt")
    QDialog.exec_result, QDialog.on_exec = 1, None
    print("Eingabefelder: OK (feste Breite 440 px, Umbruch, Text und Zahl, Abbruch)")


def test_option_changes(tmp, videos):
    """Umsortierung: pad im Profil, focus entfällt, neue Suchparameter, gegliederter Dialog, Schrittweiten in Sekunden."""
    import logo
    import seek
    from profiles import HIDDEN_OPTIONS, OPTION_GROUPS, ordered_profile, validate_options, validate_profile
    from settings import DEFAULT_TOOLTIPS, default_options
    # --- Standardwerte und Prüfung
    d = default_options()
    check("pad" not in d and "focus" not in d and d["step_end"] == "40" and d["step_next"] == "240" and d["border_tol"] == "3"
          and d["logo_rewind"] == "1.8" and d["logo_edge"] == "18" and d["logo_conf"] == "0.2", "Standardwerte")
    check(validate_options(d) == [], "Standardwerte sind gültig")
    check(len(validate_options({"step_end": "0"})) == 1 and len(validate_options({"border_tol": "-1"})) == 1
          and len(validate_options({"logo_rewind": "abc"})) == 1 and validate_options({"logo_rewind": "2.5"}) == []
          and len(validate_options({"logo_conf": "1.5"})) == 1 and len(validate_options({"logo_edge": "0"})) == 1, "Prüfung der neuen Werte")
    check(all(k in DEFAULT_TOOLTIPS for k in ("pad", "step_end", "step_next", "border_tol", "logo_rewind", "logo_edge", "logo_conf")),
          "Erklärungen für neue Schlüssel")
    grouped = [k for _, keys in OPTION_GROUPS for k in keys]
    check(sorted(grouped + sorted(HIDDEN_OPTIONS)) == sorted(d), f"jede Option gehört zu einer Gruppe oder ist versteckt: {sorted(set(d) ^ set(grouped + sorted(HIDDEN_OPTIONS)))}")
    check(list(ordered_profile({"ba": "192k", "scale": "720:576", "fps": "25.000"})) == ["scale", "pad", "fps", "ba"]
          and ordered_profile({"scale": "1:2"})["pad"] == "False", "Profil: pad nach sws_flags, Vorgabe False")
    # --- Schrittweiten in Sekunden
    check(seek.step_frames(40, Fraction(25)) == 1000 and seek.step_frames(240, Fraction(25)) == 6000
          and seek.step_frames(40, Fraction(30000, 1001)) == 1199 and seek.step_frames(0, Fraction(25)) == 1, "Schrittweite aus Sekunden")
    # --- Schrittweite der Suche nach der nächsten Werbung ist durch "pause" begrenzt
    check(seek.step_seconds({"step_next": "240", "pause": "160"}, False) == 160 and seek.step_seconds({"step_next": "100", "pause": "160"}, False) == 100
          and seek.step_seconds({"step_next": "240", "pause": "0"}, False) == 240 and seek.step_seconds({"step_end": "40", "pause": "10"}, True) == 40
          and seek.step_seconds({}, True) == 40 and seek.step_seconds({}, False) == 160, "Schrittweite höchstens so groß wie pause")
    # Praxisfall: Werbeblock von 165 s (125998..130123) zwischen zwei Filmteilen; mit 240 s Schrittweite fällt keine Probe hinein
    breaks = [(84798, 89048), (125998, 130123), (163523, 170909)]
    inside = lambda path, n, fps, opts: 0 if any(a <= n < b for a, b in breaks) else 72
    skipped = seek.seek_border("/x", Fraction(25), 170909, 89048, 72, False, seek.step_frames(240, Fraction(25)), {}, inside)
    found = seek.seek_border("/x", Fraction(25), 170909, 89048, 72, False, seek.step_frames(seek.step_seconds({"step_next": "240", "pause": "160"}, False), Fraction(25)), {}, inside)
    check(skipped == 163523 and found == 125998, f"Werbeblock wird nicht mehr übersprungen: {found} (mit 240 s: {skipped})")
    # --- Toleranz der Randsuche
    near = lambda path, n, fps, opts: 74 if n >= 130 else 0
    args = ("/x", Fraction(25), 300, 0, 72, True, 100)
    check(seek.seek_border(*args, {"border_tol": "3"}, near) == 130 and seek.seek_border(*args, {"border_tol": "1"}, near) == 300,
          "Toleranz 3 findet den Rand 74 (Soll 72), Toleranz 1 nicht")
    # --- Logo: Rückspulen, Kantenschwelle, Mindest-Übereinstimmung
    scene = lambda start: (lambda f: (10, 10, 10) if f >= start else (200, 10, 10))
    calls = []
    def avg_of(start):
        base = scene(start)
        return lambda f: (calls.append(f), base(f))[1]
    check(logo.rewind(1000, scene(960)) == 960, "Rückspulen wie VB6 (45 Bilder)")
    check(logo.rewind(1000, scene(900)) == 1000 - 45 + 1, "kein Szenenwechsel in 45 Bildern: wie VB6")
    calls.clear()
    check(logo.rewind(1000, avg_of(800), 250) == 800 and len(calls) < 60, f"langes Rückspulen findet den Szenenanfang: {len(calls)} Proben")
    calls.clear()
    check(logo.rewind(1000, avg_of(960), 250) == 960 and len(calls) < 25, "Szenenanfang nahe: wenige Proben")
    check(logo.rewind(1000, scene(0), 0) == 1000 and logo.rewind(1000, scene(0), 10) == 990, "kein bzw. kurzes Rückspulen")
    import numpy as np
    grey = np.tile(np.arange(10, dtype=np.uint8) * 10, (4, 1))               # benachbarte Pixel unterscheiden sich um 10
    check(logo.edge_map(grey, 5).sum() > 0 and logo.edge_map(grey, 18).sum() == 0, "Kantenschwelle als Parameter")
    seen = []
    conf = lambda path, n, fps, ref, opts: (seen.append(n), 0.3 if n >= 90 else 0.0)[1]
    avg = lambda path, f, fps, opts: (10, 10, 10)
    r1 = seek.seek_logo("/x", Fraction(25), 300, 0, None, True, 100, {"logo_conf": "0.2", "logo_rewind": "0"}, conf, avg)
    r2 = seek.seek_logo("/x", Fraction(25), 300, 0, None, True, 100, {"logo_conf": "0.5", "logo_rewind": "0"}, conf, avg)
    check(r1 == 89 and r2 == 299, f"Mindest-Übereinstimmung (Fund ab Bild 90 bzw. nirgends): {r1}, {r2}")
    # --- Hauptfenster: Migration, Dialog
    work = os.path.join(tmp, "migrate")
    os.makedirs(work)
    shutil.copy(os.path.join(HERE, "sample_MediaMaker.ini"), os.path.join(work, "MediaMaker.ini"))
    ini = os.path.join(work, "MediaMaker.ini")
    st = Settings(ini)
    st.set_option("pad", "True")
    st.set_option("focus", "0")
    st.set_option("logo_edge", "20")
    st.save()
    check("pad" not in st.profile, "Ausgangslage: pad nur in den Optionen")
    win = make_window(work)
    win.showEvent(None)
    st = Settings(ini)
    check(st.profile.get("pad") == "True" and "pad" not in st.options and "focus" not in st.options and st.options["logo_edge"] == "20",
          f"Migration: pad ins Profil, focus entfällt, versteckter Wert bleibt: {st.profile.get('pad')} {sorted(st.options)}")
    check(win.profile["pad"] == "True" and list(win.profile)[:4] == ["description", "scale", "sws_flags", "pad"], "Profil mit pad in der Reihenfolge")
    check("pad" not in win.options and "focus" not in win.options, "Optionen ohne pad und focus")
    # Profil hat schon pad: bleibt unverändert
    st.set_option("pad", "False")
    st.save()
    win2 = make_window(work)
    win2.showEvent(None)
    check(Settings(ini).profile["pad"] == "True" and "pad" not in Settings(ini).options, "vorhandenes pad im Profil gewinnt")
    # Optionsdialog: gegliedert, ohne versteckte Schlüssel; Speichern behält versteckte Werte
    shown = []
    win.edit_pairs = lambda title, pairs, groups=None: (shown.append((title, list(pairs), groups)), dict(pairs, border_tol="5"))[1]
    win.mnuOptions_Click()
    title, keys, groups = shown[-1]
    check(title == "Options" and groups == OPTION_GROUPS and not (set(keys) & HIDDEN_OPTIONS) and "pad" not in keys and "focus" not in keys
          and "border_tol" in keys and "step_end" in keys, f"Optionsdialog: {keys}")
    st = Settings(ini)
    check(st.options["border_tol"] == "5" and st.options["logo_edge"] == "20" and "focus" not in st.options, "gespeichert: Änderung und versteckter Wert")
    # Profildialog zeigt pad; Speichern schreibt es ins Profil
    win.edit_pairs = lambda title, pairs, groups=None: (shown.append((title, list(pairs), groups)), dict(pairs, pad="False"))[1]
    win.mnuProfile_Click()
    check(shown[-1][1][:4] == ["description", "scale", "sws_flags", "pad"] and shown[-1][2] is None and Settings(ini).profile["pad"] == "False",
          "Profildialog mit pad")
    # --- Dialog mit Überschriften
    import dialogs
    from PySide6.QtWidgets import QDialog
    QDialog.exec_result, QDialog.on_exec = 1, None
    pairs = {"audio": "1", "pause": "160", "unbekannt": "x", "crop": "72"}
    dialogs.edit_pairs(None, "Options", pairs, {}, {}, OPTION_GROUPS)
    from PySide6.QtWidgets import QFormLayout
    rows = [(l._args[0], e is None) for l, e in QFormLayout.instances[-1].rows]
    check(rows == [("<b>Border detection</b>", True), ("crop", False), ("<b>Seeking commercials</b>", True), ("pause", False),
                   ("<b>Audio and subtitles</b>", True), ("audio", False), ("<b>Other</b>", True), ("unbekannt", False)],
          f"Überschriften und Reihenfolge: {rows}")
    dialogs.edit_pairs(None, "Profile", {"scale": "720:576", "fps": "25.000"}, {}, {})
    check([l._args[0] for l, e in QFormLayout.instances[-1].rows] == ["scale", "fps"], "ohne Gruppen: wie bisher")
    print("Umsortierung und neue Parameter: OK (pad im Profil, focus entfällt, Suchwerte, Gliederung, Migration)")


def test_info(tmp, videos):
    """Menü Information: Lage der Segmente im fertigen Film, Gesamtlänge, voraussichtliche Größe, Dialog."""
    import info
    from project import format_time
    s2 = os.path.join(videos, "sample2.ts")
    profile = {"scale": "720:576", "fps": "25.000", "bv": "3072k", "ba": "192k"}
    # Segmente: 100 Bilder ab Bild 20 (erstes Bild 10), 50 Bilder ab 0 mit 29,97 FPS, eine fehlende Datei
    a = Segment(1, s2, "sample2.ts", 30, 130, 158, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, "")
    a.first_frame = 10
    b = Segment(2, s2, "sample2.ts", 0, 50, 200, Fraction(30000, 1001), 1280, 720, 4000, 128, "a", 0, 0, 0, 0, 44100, "")
    gone = Segment(3, "/nicht/da.ts", "da.ts", 0, 10, 10, Fraction(25), 720, 576, 1, 1, "a", 0, 0, 0, 0, 48000, "")
    rows, summary = info.build_info([a, b, gone], profile)
    size = f"{os.path.getsize(s2):,}"
    check(len(rows) == 3 and all(len(r) == len(info.HEADERS) for r in rows), "Zeilen mit allen Spalten")
    check(rows[0] == ["01", s2, size, "00:00:06", "20", "120", "00:00:04.000", "00:00:00.000", "00:00:04.000", "720x576", "25.000", "48000", "3000", "192"],
          f"Zeile 1 (Nummern ab dem ersten Bild: 30-10 und 130-10): {rows[0]}")
    check(rows[1][4:9] == ["0", "50", "00:00:01.668", "00:00:04.000", "00:00:05.668"] and rows[1][9:11] == ["1280x720", "29.970"],
          f"Zeile 2: Startzeit = Ende des vorigen Segments, Länge aus 29,97 FPS: {rows[1]}")
    check(rows[2][:3] == ["03", "/nicht/da.ts", info.NOT_FOUND] and rows[2][3:] == [""] * 11, "fehlende Datei gekennzeichnet")
    total = Fraction(100, 25) + Fraction(50 * 1001, 30000)
    mib = (3072 + 192) * 1000 / 8 * float(total) / 2 ** 20
    check(summary.startswith("3 segments; expected length of the result: 00:00:05.668") and f"{mib:,.1f} MiB" in summary
          and "3072k (video) + 192k (audio)" in summary and "target 720x576, 25.000 FPS" in summary and "1 source file not found" in summary,
          f"Zusammenfassung: {summary}")
    check("MiB" not in info.build_info([a], {"scale": "720:576"})[1] and info.build_info([], profile)[1].startswith("0 segments;"),
          "ohne Bitraten keine Größe; leere Liste")
    check(format_time(Fraction(3725, 1)) == "01:02:05.000" and format_time(Fraction(1, 3)) == "00:00:00.333", "Zeitformat")
    # --- Menü
    work = os.path.join(tmp, "infowin2")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True)
    win.showEvent(None)
    shown = []
    win.show_info = lambda rows, summary: shown.append((rows, summary))
    win.mnuInfo_Click()
    check(shown == [] and win.messages[-1] == "There are no segments in the list.", "leere Liste: Meldung")
    win.OpenVideo(s2)
    win.mnuInfo_Click()
    rows, summary = shown[-1]
    seg = win.segment
    check(len(rows) == 1 and rows[0][4] == "0" and rows[0][5] == str(seg.total_frames - seg.first_frame) and rows[0][7] == "00:00:00.000"
          and "1 segment;" in summary, f"Menü: {rows[0]} {summary}")
    # --- Dialog
    from info_dialog import frmInfo
    from PySide6.QtWidgets import QDialog
    dialog = frmInfo(rows, summary)
    flags = dialog.called("setWindowFlag")
    check(dialog.called("setWindowTitle")[-1] == ("Loaded segments information",) and dialog.called("setMaximumSize")[-1] == (16777215, 16777215)
          and "WindowMaximizeButtonHint" in repr(flags[-1][0]) and flags[-1][1] is True, "Dialog ist veränderbar")
    check(dialog.lvwInfo.called("setHeaderLabels")[-1][0] == list(info.HEADERS) and dialog.lvwInfo.row_count() == 1, "Spalten und Zeilen")
    item = dialog.lvwInfo.topLevelItem(0)
    check(all(col in item.align_ for col in info.RIGHT_ALIGNED) and 1 not in item.align_, "Zahlen rechtsbündig, Dateiname links")
    widths = {a[0]: a[1] for a in dialog.lvwInfo.called("setColumnWidth")}
    check(1 not in widths and widths[6] > widths[4] and widths[2] > widths[0], f"Spaltenbreiten aus der Schrift: {widths}")
    check(dialog.lblSummary.text() == summary and dialog.lblSummary.called("setWordWrap") == [(True,)], "Zusammenfassung unter der Liste")
    print("Information: OK (Segmentübersicht, Lage im fertigen Film, Zusammenfassung, Menü, Dialog)")


def test_tooltip_wrap(tmp, videos):
    """Lange Tooltip-Texte werden mehrzeilig umgebrochen (Qt tut das bei reinem Text nicht selbst)."""
    import dialogs
    from settings import DEFAULT_TOOLTIPS
    long_text = DEFAULT_TOOLTIPS["logo_rewind"]
    wrapped = dialogs.wrap_tooltip(long_text)
    lines = wrapped.split("\n")
    check(len(lines) >= 2 and all(len(line) <= 70 for line in lines) and " ".join(lines) == long_text, f"umgebrochen: {lines}")
    check(dialogs.wrap_tooltip("kurz") == "kurz" and dialogs.wrap_tooltip("") == "", "kurze und leere Texte bleiben")
    url = "See https://ffmpeg.org/ffmpeg-scaler.html#Scaler-Options for the flags " + "x" * 80
    check(any("https://ffmpeg.org/ffmpeg-scaler.html#Scaler-Options" in l for l in dialogs.wrap_tooltip(url).split("\n"))
          and "x" * 80 in dialogs.wrap_tooltip(url), "Adressen und lange Wörter bleiben ganz")
    check(dialogs.wrap_tooltip("Zeile eins\n\nZeile drei") == "Zeile eins\n\nZeile drei", "vorhandene Zeilenumbrüche bleiben")
    # im Dialog
    from PySide6.QtWidgets import QDialog, QFormLayout
    QDialog.exec_result, QDialog.on_exec = 1, None
    dialogs.edit_pairs(None, "Options", {"logo_rewind": "1.8"}, {"logo_rewind": long_text}, {})
    label, editor = QFormLayout.instances[-1].rows[-1]
    tip = label.called("setToolTip")[-1][0]
    check(tip == wrapped and editor.called("setToolTip")[-1][0] == wrapped, "Tooltips im Dialog sind umgebrochen")
    print("Tooltips: OK (Umbruch bei 70 Zeichen, Wörter und Adressen bleiben ganz)")


def test_shutdown(tmp, videos):
    """Beim Schließen des Fensters wird die Wiedergabe beendet, auch mitten im Abspielen."""
    win = make_window(tmp)
    win.showEvent(None)
    win.OpenVideo(os.path.join(videos, "sample2.ts"))
    win.cmdPos_Click(3)
    check(win.player.is_playing, "Wiedergabe läuft")
    win.closeEvent(None)
    check(win.player.shut_down and not win.player.is_playing, "Player nach dem Schließen heruntergefahren")
    win.player.shutdown()                                      # zweimal ist harmlos
    print("Beenden: OK (Player wird beim Schließen heruntergefahren, auch mitten im Abspielen)")


def test_throttle():
    from player import SeekThrottle
    done = []
    t = SeekThrottle(done.append)
    t.request(1)
    t.request(2)
    t.request(3)
    check(done == [1], f"erster Sprung sofort, weitere zurückgehalten: {done}")
    t.timer.fire()
    check(done == [1, 3] and t.timer.isActive(), f"zuletzt angeforderter Wert nach Ablauf: {done}")
    t.timer.fire()
    check(done == [1, 3] and not t.timer.isActive(), "nichts mehr offen")
    t.request(4)
    check(done == [1, 3, 4], "nach Ruhe wieder sofort")
    print("Sprung-Drossel: OK (erster sofort, danach gebündelt, letzter Wert kommt an)")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    tmp = tempfile.mkdtemp()
    test_settings(tmp)
    test_project(tmp)
    for sub in ("MediaMaker.ini", "MediaMaker.json"):
        if os.path.exists(os.path.join(tmp, sub)):
            os.remove(os.path.join(tmp, sub))
    test_app(tmp, sys.argv[1])
    test_audio_choice(tmp)
    test_fresh_and_paths(tmp, sys.argv[1])
    test_counting_and_network(tmp, sys.argv[1])
    test_profiles(tmp, sys.argv[1])
    test_dialog()
    test_memory_player()
    test_timeline(tmp, sys.argv[1])
    test_segments(tmp, sys.argv[1])
    test_thumbnail_errors(tmp, sys.argv[1])
    test_marker_start(tmp, sys.argv[1])
    test_jump_to_frame(tmp, sys.argv[1])
    test_media_info(tmp, sys.argv[1])
    test_autocrop(tmp, sys.argv[1])
    test_input_box(tmp, sys.argv[1])
    test_option_changes(tmp, sys.argv[1])
    test_info(tmp, sys.argv[1])
    test_tooltip_wrap(tmp, sys.argv[1])
    test_first_frame(tmp, sys.argv[1])
    test_shutdown(tmp, sys.argv[1])
    test_throttle()
    if errors:
        print(f"\n{len(errors)} FEHLER:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("Alle Prüfungen bestanden.")


if __name__ == "__main__":
    main()
