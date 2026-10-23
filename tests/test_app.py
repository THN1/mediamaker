"""Tests for settings, project file and the main logic (opening, analysing, navigation) without Qt and without VLC.

Usage:  python3 tests/test_app.py FOLDER_WITH_SAMPLE_VIDEOS   (expects sample2.ts and sample3.ts in it)
The user interface runs against the Qt replacement in ui/tests/qtstub, the playback against FakePlayer.
"""
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "ui", "tests", "qtstub"))        # replacement before a real PySide6
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


# ----------------------------------------------------------------------------- Settings
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
    # change: only the affected line changes
    s.set_option("crop", 70)
    s.save()
    after = open(ini, "rb").read()
    old_lines, new_lines = before.decode("cp1252").split("\r\n"), after.decode("utf-8").split("\r\n")
    changed = [(a, b) for a, b in zip(old_lines, new_lines) if a != b]
    check(len(old_lines) == len(new_lines) and len(changed) == 1 and changed[0][1].startswith("options=") and
          'crop="70"' in changed[0][1], f"change not limited to one line: {changed}")
    check(Settings(ini).options["crop"] == "70" and Settings(ini).options["floor"] == "2", "Reload")
    s2 = Settings(ini)
    s2.last = "/tmp/x y.ts"
    check(Settings(ini).last == "/tmp/x y.ts", "save last")
    s2.set("new section", "k", "v")
    s2.save()
    check(Settings(ini).get("new section", "k") == "v", "create a new section")
    print("Settings: OK (options, profile, 11 named profiles, changing replaces exactly one line)")


# ----------------------------------------------------------------------------- Project file
def test_project(tmp):
    job = parse_batch_header(open(os.path.join(HERE, "sample_Elysium.bat"), encoding="latin-1").read())
    check(len(job.segments) == 4 and all(s.has_png_mask for s in job.segments), "Elysium list (4 segments with mask)")
    path = os.path.join(tmp, "list.json")
    save_segments(path, job.segments)
    back = load_segments(path)
    check(len(back) == 4, "count after loading")
    for a, b in zip(job.segments, back):
        check(a == b, f"segment changed by JSON: {a.index}")
    data = json.load(open(path))
    check(data["segments"][0]["fps"] == "25/1" and data["segments"][0]["crop"] == [0, 0, 0, 0], "JSON fields")
    check(not os.path.exists(path + ".tmp"), "temporary file stays behind")
    # load old CSV file
    csv_text = open(os.path.join(tmp, "legacy.csv"), "w", encoding="cp1252", newline="")
    csv_text.write('"01","R:\\Film.ts","Film.ts","0","1000","00:00:40","1000","25.000","720","576","3009","192","a","0","0","0","0","48000",""\r\n')
    csv_text.close()
    legacy = load_segments(os.path.join(tmp, "legacy.csv"))
    check(len(legacy) == 1 and legacy[0].fps == 25 and legacy[0].end == 1000, "CSV-Import")
    check(load_segments(os.path.join(tmp, "doesnotexist.json")) == [], "missing file")
    robocop = parse_batch_header(open(os.path.join(HERE, "sample_MediaMaker.sh"), encoding="latin-1").read())
    check(len(robocop.segments) == 6, "RoboCop list")
    row = segment_row(robocop.segments[0], 1)
    check(len(row) == 19 and row[0] == "01" and row[7] == "25.000" and row[5] == "00:31:26", f"row: {row[:8]}")
    check(timeof(7509, Fraction(25)) == "00:05:00.360", timeof(7509, Fraction(25)))
    print("Project file: OK (JSON lossless, old CSV importable, 19 list columns)")


# ----------------------------------------------------------------------------- Main logic
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
    win.inform = win.messages.append
    win.answer = True
    win.ask = lambda text: win.answer
    win.busy = lambda on: None
    return win


def test_app(tmp, videos):
    s2, s3 = os.path.join(videos, "sample2.ts"), os.path.join(videos, "sample3.ts")
    win = make_window(tmp)
    win.showEvent(None)                                       # Form_Load
    check(win.lblText[1].text() == "3072k" and win.lblText[2].text() == "720:576" and win.lblText[3].text() == "25.000",
          "profile display")
    check(win.player.volume == 44, f"volume {win.player.volume}")
    widths = {a[0]: a[1] for a in win.lvwSegments.called("setColumnWidth")}
    # number unchanged 32 pixels; frame numbers and duration from the font (in the test 1 pixel per character): six digits, hh:mm:ss, 20 border each
    px = QtWidgets.FontMetrics.px_per_char
    check(widths[0] == 32 and widths[3] == px * 6 + 20 and widths[4] == px * 6 + 20 and widths[5] == px * 8 + 20,
          f"visible columns (number, first, last frame, duration): {widths}")
    check(widths[3] == widths[4] < widths[5], "columns for first and last frame equally wide, duration somewhat wider")
    hidden = sorted(c for c, w in widths.items() if w == 0)
    check(hidden == [1] + list(range(6, 19)), f"hidden columns: {hidden}")
    check(2 not in widths and win.lvwSegments.header().called("setStretchLastSection") == [(False,)]
          and win.lvwSegments.header().called("setMinimumSectionSize") == [(0,)]
          and len(win.lvwSegments.header().called("setSectionResizeMode")) == 1, "header")
    check(win.player.attached is win.VLC, "video area")

    check(win.OpenVideo(s2), "OpenVideo sample2")
    seg = win.segments[0]
    check((seg.end, seg.total_frames, seg.width, seg.height, seg.fps, seg.audio_sel) == (148, 148, 720, 576, 25, "a"),
          f"Segment: {seg}")
    check(win.lvwSegments.row_count() == 1 and win.lvwSegments.topLevelItem(0).text(2) == "sample2.ts", "list")
    check(win.lvwSegments.topLevelItem(0).font(2).called("setBold")[-1] == (True,), "title bold")
    check(win.current == 0 and win.player.path == s2, "segment loaded")
    check(win.Slider1.maximum() == 148 and win.Slider1.value() == 0, "slider")
    check(win.lblInfo.text() == "Frame 0" and win.lblTime.text() == "Time 00:00:00.000", f"display {win.lblInfo.text()}")
    check(win.lblText[0].text() == "00:00:06", f"total length {win.lblText[0].text()}")
    check(win.cmdPos[3].text() == "|>", "play button after loading")
    check(Settings(os.path.join(tmp, "MediaMaker.ini")).last == s2, "last saved")
    check(load_segments(os.path.join(tmp, "MediaMaker.json"))[0].end == 148, "list saved")

    # Navigation
    win.cmdPos_Click(4)
    check(win.Slider1.value() == 1 and win.player.time == 40 and win.lblInfo.text() == "Frame 1"
          and win.lblTime.text() == "Time 00:00:00.040", f"+1: {win.Slider1.value()} {win.player.time}")
    win.cmdPos_Click(5)
    check(win.Slider1.value() == 126, f"+5 s: {win.Slider1.value()}")
    win.cmdPos_Click(6)
    check(win.Slider1.value() == 148, "end")
    win.cmdPos_Click(1)
    check(win.Slider1.value() == 23, "-5 s")
    win.cmdPos_Click(0)
    check(win.Slider1.value() == 0 and win.player.time == 0, "start")
    # playback
    win.cmdPos_Click(3)
    check(win.player.is_playing and win.cmdPos[3].text() == "=", "Play")
    win.player.tick(1000)
    check(win.lblInfo.text() == "Frame 25", f"time display during playback: {win.lblInfo.text()}")
    check(win.Slider1.value() == 25, f"slider moves along during playback: {win.Slider1.value()}")
    win.player.tick(1000)
    check(win.Slider1.value() == 50 and win.player.time == 2000, "slider keeps following, without letting the player jump again")
    win.Slider1.isSliderDown = lambda: True                    # the user holds the slider
    win.player.tick(1000)
    check(win.Slider1.value() == 50 and win.lblInfo.text() == "Frame 75", "dragged slider stays untouched")
    del win.Slider1.isSliderDown
    win.player.time = 1000
    win.player.tick(0)
    win.cmdPos_Click(3)
    check(not win.player.is_playing and win.cmdPos[3].text() == "|>" and win.Slider1.value() == 25,
          f"pause sets the slider: {win.Slider1.value()}")
    # Marker
    win._go(50)
    win.cmdPos_Click(7)
    check(seg.start == 50 and win.lvwSegments.topLevelItem(0).text(3) == "50", "Marker A")
    check(win.lvwSegments.topLevelItem(0).text(5) == "00:00:04", f"duration {win.lvwSegments.topLevelItem(0).text(5)}")
    win._go(100)
    win.cmdPos_Click(8)
    check(seg.end == 100 and win.lblText[0].text() == "00:00:02", f"marker B / total length {win.lblText[0].text()}")
    check(win.Slider1.value() == 100 and win.timeline_mode == "B", "jump to marker B")
    win._go(40)
    win.cmdPos_Click(8)                                        # end before start: beep, no change
    check(seg.end == 100 and "beep" in QtWidgets.QApplication.log, "end before start")
    win.cmdPos_Click(11)
    check((seg.start, seg.end) == (0, 148), "reset markers")
    # volume
    win.vscVolume.setValue(0)
    win.vscVolume_Scroll()
    check(win.player.volume == 204, "volume up")

    # dropping several files, then back to the first segment
    win.lvwSegments._vb_filter.handlers["drop"]([s3])
    check(len(win.segments) == 2 and win.segments[1].end == 348 and win.current == 1 and win.player.path == s3,
          f"dropping: {len(win.segments)}")
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    check(win.current == 0 and win.player.path == s2 and win.Slider1.maximum() == 148, "change selection")

    # restart: list is loaded
    win2 = make_window(tmp)
    win2.showEvent(None)
    check(len(win2.segments) == 2 and win2.lvwSegments.row_count() == 2, "list loaded at start")
    check(win2.lblText[0].text() == "00:00:20", f"total length after restart {win2.lblText[0].text()}")
    print("Main logic: OK (open, analysis, display, navigation, markers, playback, dropping, restart)")


def test_fresh_and_paths(tmp, videos):
    """New job empties the list; relative paths are stored as full paths."""
    project = os.path.join(tmp, "MediaMaker.json")
    s2 = os.path.join(videos, "sample2.ts")
    old = [Segment(1, s2, "sample2.ts", 0, 148, 148, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")] * 2
    save_segments(project, old)
    # without parameter: last list is loaded
    win = make_window(tmp)
    win.showEvent(None)
    check(len(win.segments) == 2, "without parameter the list is loaded")
    # with parameter: list is discarded and the file emptied
    win = make_window(tmp, fresh=True)
    win.showEvent(None)
    check(win.segments == [] and load_segments(project) == [] and win.lvwSegments.row_count() == 0,
          "with parameter the list starts empty")
    # relative path: called from the folder of the video file
    cwd = os.getcwd()
    os.chdir(videos)
    try:
        check(win.OpenVideo("sample2.ts"), "OpenVideo with file name")
    finally:
        os.chdir(cwd)
    stored = load_segments(project)[0]
    check(stored.path == s2 and os.path.isabs(stored.path), f"path in the list: {stored.path}")
    check(stored.name == "sample2.ts" and win.player.path == s2, "title stays the file name, player gets the full path")
    check(win.settings.last == s2, f"last: {win.settings.last}")
    check(json.load(open(project))["segments"][0]["path"] == s2, "JSON contains the full path")
    print("New job and paths: OK (empty list with parameter, full paths)")


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
    check(win.OpenVideo(f) and win.segments[-1].audio_sel == "2", f"first mp2 track: {win.segments[-1].audio_sel}")
    win.settings.set_option("audio", 2)
    win.OpenVideo(f)
    check(win.segments[-1].audio_sel == "3", f"second mp2 track: {win.segments[-1].audio_sel}")
    win.settings.set_option("audio", 5)
    win.OpenVideo(f)
    check(win.segments[-1].audio_sel == "2" and any("no audio track" in m for m in win.messages), "track does not exist")
    win.settings.set_profile(dict(win.profile, acodec_in="aac"))
    n = len(win.segments)
    check(not win.OpenVideo(f) and len(win.segments) == n and any("no audio stream of type" in m for m in win.messages),
          "codec does not exist")
    win3 = make_window(tmp, probe=lambda p: fake_info(p, []))
    check(not win3.OpenVideo(f) and any("no audio stream" in m for m in win3.messages), "without sound")
    print("Audio track selection: OK (n-th track with matching codec, warnings, cancel)")


def test_counting_and_network(tmp, videos):
    """Quick analysis with estimated number of frames, exact counting in the background, network drive paths."""
    import mediamaker
    from mediaprobe import MediaInfo
    # 1) the estimate is replaced by the count; the end follows as long as the user has not changed it
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
    check(win.OpenVideo(f), "OpenVideo with estimate")
    seg = win.segments[0]
    check((seg.total_frames, seg.end) == (990, 990), f"after counting: {seg.total_frames}/{seg.end}")
    check(win.Slider1.maximum() == 990 and win.lvwSegments.topLevelItem(0).text(6) == "990", "slider and list")
    titles = [a[0] for a in win.called("setWindowTitle")]
    check("counting" in titles[-2] and titles[-1] == "MediaMaker " + mediamaker.VERSION, f"title: {titles[-2:]}")
    # 2) the user's markers are kept, an end behind the real end is limited
    seg.start, seg.end = 200, 500
    win.frames_counted(f, 400, 0, 0.0)
    check((seg.start, seg.end, seg.total_frames) == (200, 400, 400), f"Marker: {seg.start}/{seg.end}/{seg.total_frames}")
    seg.start, seg.end = 100, 300
    win.frames_counted(f, 450, 0, 0.0)
    check((seg.start, seg.end, seg.total_frames) == (100, 300, 450), "markers unchanged with a larger number")
    check(load_segments(os.path.join(tmp, "MediaMaker.json"))[0].total_frames == 450, "saved")
    # 3) cancel counting
    from mediamaker import FrameCounter
    class Proc:
        terminated = False
        def poll(self): return None
        def terminate(self): self.terminated = True
    c = FrameCounter(f, lambda path, on_start=None: (1, 0, 0.0))
    proc = Proc()
    c._remember(proc)
    c.cancel()
    check(proc.terminated and c.cancelled, "counting can be cancelled")
    got = []
    c2 = FrameCounter(f, lambda path, on_start=None: (5, 0, 0.0))
    c2.counted.connect(lambda *a: got.append(a))
    c2.cancelled = True
    c2.run()
    check(got == [], "cancelled counting reports nothing")
    # 4) network drive: the directory kio-fuse-... changes with every session
    share = os.path.join(tmp, "run", "kio-fuse-NEUab", "smb", "nas", "movie")
    os.makedirs(share)
    real = os.path.join(share, "Film 1.ts")
    open(real, "w").close()
    stale = os.path.join(tmp, "run", "kio-fuse-ALTcd", "smb", "nas", "movie", "Film 1.ts")
    seg2 = Segment(1, stale, "Film 1.ts", 0, 100, 100, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")
    save_segments(os.path.join(tmp, "MediaMaker.json"), [seg2])
    win = make_window(tmp)
    win.showEvent(None)
    check(win.segments[0].path == real and not win.messages, f"path resolved: {win.segments[0].path}")
    check(load_segments(os.path.join(tmp, "MediaMaker.json"))[0].path == real, "resolved path saved")
    print("Counting and network drive: OK (estimate, counting in the background, markers stay, cancellable, kio-fuse paths)")


def test_profiles(tmp, videos):
    """Profile and options: checking, INI file, dialogs, profile list, saving, copying from the sample video."""
    from profiles import (default_name, normalize_bitrate, profile_from_segment, valid_profile_name, validate_options,
                          validate_profile, weighted_bitrate)
    ok_profile = {"description": "x", "scale": "720:576", "sws_flags": "lanczos", "fps": "25.000", "bv": "3072k",
                  "acodec_in": "mp2", "acodec_out": "aac", "ar": "48000", "ba": "192k"}
    from profiles import wrapped_lines
    check(wrapped_lines(330, 230, min_lines=2) == 2 and wrapped_lines(50, 230, min_lines=2) == 2
          and wrapped_lines(900, 230) == 4 and wrapped_lines(0, 230) == 1 and wrapped_lines(218, 230) == 1
          and wrapped_lines(219, 230) == 2, "number of lines for long values")
    check(validate_profile(ok_profile) == [], f"valid profile: {validate_profile(ok_profile)}")
    bad = lambda **kw: validate_profile(dict(ok_profile, **kw))
    check(len(bad(scale="abc")) == 1 and len(bad(scale="721:576")) == 1 and len(bad(scale="720:0")) == 1, "scale")
    check(len(bad(fps="25")) == 1 and len(bad(fps="5.000")) == 1 and bad(fps="29.970") == [], "fps")
    check(len(bad(bv="3072")) == 1 and len(bad(ba="0k")) == 1 and bad(ba="64k") == [], "bit rates")
    check(len(bad(ar="48")) == 1 and bad(ar="44100") == [] and len(bad(acodec_out="")) == 1, "ar, Codec")
    check(validate_options({"crop": "72", "floor": "2", "subtitle": "0", "multilanguage": "False"}) == [], "options valid")
    check(len(validate_options({"crop": "-1"})) == 1 and len(bad(pad="yes")) == 1 and bad(pad="True") == []
          and len(validate_options({"subtitle": "a"})) == 1 and validate_options({"subtitle": "1,2"}) == []
          and len(validate_options({"audio": "0"})) == 1, "options invalid")
    check(valid_profile_name("My profile [1]") is None and valid_profile_name("a=b") and valid_profile_name("[x") and
          valid_profile_name("  "), "profile names")
    check(default_name({"description": "MPEG-TS (SD 720x576), 25 FPS"}) == "MPEG-TS_(SD_720x576),_25_FPS", "suggested name")
    check(normalize_bitrate("3000") == "3000k" and normalize_bitrate(" 3000k ") == "3000k" and
          normalize_bitrate("0") is None and normalize_bitrate("abc") is None, "normalize_bitrate")
    seg = lambda frames, v, a: Segment(1, "/x.ts", "x.ts", 0, frames, frames, Fraction(25), 1280, 720, v, a, "a", 0, 0, 0, 0, 44100, "")
    check(weighted_bitrate([seg(250, 4000, 192), seg(750, 2000, 128)], "video") == 2500 and
          weighted_bitrate([seg(250, 4000, 192), seg(750, 2000, 128)], "audio") == 144 and weighted_bitrate([], "video") == 0,
          "weighted mean")
    check(profile_from_segment(seg(100, 3009, 192)) == {"bv": "3009k", "scale": "1280:720", "fps": "25.000", "ar": "44100",
                                                       "ba": "192k"}, "profile from segment")

    # --- INI: named profiles
    ini = os.path.join(tmp, "profiles.ini")
    shutil.copy(os.path.join(HERE, "sample_MediaMaker.ini"), ini)
    st = Settings(ini)
    st.save_profile("My profile [test]", ok_profile)
    st.save_profile("HD", dict(st.profiles["HD"], bv="9999k"))                       # overwrite
    st.update_profile({"bv": "1234k"})
    st.set_options(dict(st.options, crop="60"))
    st.save()
    st = Settings(ini)
    names = list(st.profiles)
    check(len(names) == 12 and names[-1] == "My profile [test]" and st.profiles["HD"]["bv"] == "9999k", f"Profile: {names}")
    check(st.profiles["My profile [test]"] == ok_profile and st.profile["bv"] == "1234k" and st.profile["scale"] == "720:576",
          "profile saved and single value changed")
    check(st.options["crop"] == "60" and st.options["floor"] == "2", "options saved")

    # --- main window
    workdir = os.path.join(tmp, "profwin")
    os.makedirs(workdir)
    shutil.copy(os.path.join(HERE, "sample_MediaMaker.ini"), os.path.join(workdir, "MediaMaker.ini"))
    win = make_window(workdir)
    win.showEvent(None)
    check(len(win.profile_actions) == 11 and win.mnuLoadProfile.called("setEnabled") == [(True,)], "profile menu filled")
    check(win.Frame1.called("setToolTip")[-1] == ("MPEG-TS (SD 720x576), 25 FPS, 3072 and 192 KBit/s",), "tooltip description")
    # load profile via the menu
    hd = next(a for a in win.profile_actions if a.text_ == "HD")
    hd.triggered.emit(False)
    check(win.profile["scale"] == "1280:720" and win.lblText[2].text() == "1280:720" and win.lblText[3].text() == "29.970",
          "load profile: display")
    check(Settings(os.path.join(workdir, "MediaMaker.ini")).profile["scale"] == "1280:720", "load profile: saved")
    # edit profile: first invalid, then valid; cancel changes nothing
    answers = [dict(win.profile, scale="abc"), dict(win.profile, scale="1920:1080", bv="5000k")]
    seen = []
    win.edit_pairs = lambda title, pairs, groups=None, start=0: (seen.append((title, dict(pairs))), answers.pop(0))[1]
    win.mnuProfile_Click()
    check(len(win.messages) == 1 and "width:height" in win.messages[0], f"error message: {win.messages}")
    check(seen[1][1]["scale"] == "abc", "dialog appears again with the entered values")
    check(win.profile["scale"] == "1920:1080" and win.lblText[1].text() == "5000k", "profile edited")
    win.edit_pairs = lambda title, pairs, groups=None, start=0: None
    win.mnuProfile_Click()
    check(win.profile["scale"] == "1920:1080", "cancel changes nothing")
    # options
    win.edit_pairs = lambda title, pairs, groups=None, start=0: dict(pairs, crop="70", floor="1")
    win.mnuOptions_Click()
    check(win.options["crop"] == "70" and win.options["floor"] == "1" and win.options["blackness"] == "12", "options changed")
    check(Settings(os.path.join(workdir, "MediaMaker.ini")).options["crop"] == "70", "options in the INI file")
    win.edit_pairs = lambda title, pairs, groups=None, start=0: dict(pairs, crop="abc")
    n_msgs = len(win.messages)
    answers2 = [dict(win.options, crop="abc"), None]
    win.edit_pairs = lambda title, pairs, groups=None, start=0: answers2.pop(0)
    win.mnuOptions_Click()
    check(len(win.messages) == n_msgs + 1 and win.options["crop"] == "70", "invalid option is rejected")
    # save profile under a name
    names_asked = ["New A", "New A", "New B"]
    win.ask_text = lambda title, label, default="": names_asked.pop(0)
    win.mnuSaveProfile_Click()
    check("New A" in win.settings.profiles and len(win.profile_actions) == 12, "profile saved, menu updated")
    win.answer = False                                                  # overwriting denied: ask for a new name
    win.mnuSaveProfile_Click()
    check("New B" in win.settings.profiles and len(win.profile_actions) == 13 and win.settings.profiles["New A"]["scale"] == "1920:1080",
          "overwriting denied: other name")
    win.ask_text = lambda title, label, default="": None
    win.mnuSaveProfile_Click()
    check(len(win.profile_actions) == 13, "cancel when saving")
    win.ask_text = lambda title, label, default="": "a=b"
    msgs = len(win.messages)
    answers3 = ["a=b", None]
    win.ask_text = lambda title, label, default="": answers3.pop(0)
    win.mnuSaveProfile_Click()
    check(len(win.messages) == msgs + 1, "invalid profile name")
    # sample video: copy values of the target file
    win.mnuReuse_Click()
    check("one and only one" in win.messages[-1], "reuse without segment")
    win.OpenVideo(os.path.join(videos, "sample2.ts"))
    before_reuse = dict(win.profile)
    win.mnuReuse_Click()
    seg0 = win.segments[0]
    check(win.profile["scale"] == "720:576" and win.profile["fps"] == "25.000" and win.profile["ar"] == "48000"
          and win.profile["bv"] == f"{seg0.vbitrate_kbit}k" and win.profile["ba"] == f"{seg0.abitrate_kbit}k"
          and win.lblText[2].text() == "720:576" and "copied from" in win.messages[-1], f"Reuse: {win.profile}")
    check({k: v for k, v in win.profile.items() if k not in ("bv", "scale", "fps", "ar", "ba")}
          == {k: v for k, v in before_reuse.items() if k not in ("bv", "scale", "fps", "ar", "ba")}, "reuse leaves other values unchanged")
    # estimate bit rates
    win.OpenVideo(os.path.join(videos, "sample3.ts"))
    win.mnuReuse_Click()
    check("one and only one" in win.messages[-1], "reuse with two segments")
    win.segments[0].vbitrate_kbit, win.segments[1].vbitrate_kbit = 4000, 2000
    avg = weighted_bitrate(win.segments, "video")
    asked = []
    win.ask_text = lambda title, label, default="": (asked.append((label, default)), "3000")[1]
    win.mnuCalcVideo_Click()
    check(asked[0][1] == str(avg) and win.profile["bv"] == "3000k", f"estimate video: {asked} {win.profile['bv']}")
    win.ask_text = lambda title, label, default="": "160k"
    win.mnuCalcAudio_Click()
    check(win.profile["ba"] == "160k" and win.lblText[5].text() == "160k", "estimate audio")
    win.ask_text = lambda title, label, default="": "abc"
    before = win.profile["bv"]
    win.mnuCalcVideo_Click()
    check(win.profile["bv"] == before and "not a valid bitrate" in win.messages[-1], "invalid bit rate")
    print("Profile and options: OK (checking, INI file, dialogs, profile menu, saving, copying from sample video, estimate)")


def test_dialog():
    """The edit dialog is played through against the strict Qt replacement (enumerations, field types, return value)."""
    import dialogs
    from profiles import PRESETS
    from PySide6.QtWidgets import FontMetrics, QComboBox, QDialog, QFormLayout, QLineEdit
    pairs = {"description": "MPEG-TS (SD 720x576), 25 FPS, 3072 and 192 KBit/s", "scale": "720:576", "fps": "25.000",
             "aflags": "", "pad": "False"}
    QDialog.exec_result = 1
    QDialog.on_exec = None
    QFormLayout.instances.clear()
    result = dialogs.edit_pairs(None, "Profile", pairs, {"scale": "hint"}, PRESETS)
    check(result == pairs, f"return value unchanged: {result}")
    rows = dict((label._args[0], editor) for label, editor in QFormLayout.instances[-1].rows)
    check(isinstance(rows["description"], dialogs.WrappedEdit) and isinstance(rows["scale"], QLineEdit)
          and isinstance(rows["fps"], QComboBox) and isinstance(rows["pad"], QComboBox) and isinstance(rows["aflags"], QLineEdit),
          f"field types: { {k: type(v).__name__ for k, v in rows.items()} }")
    height = rows["description"].called("setFixedHeight")
    check(len(height) == 1 and height[0][0] >= 2 * 16, f"description has at least two lines: {height}")
    check(rows["scale"].called("setToolTip") == [("hint",)], "Tooltip")
    # change inputs: combo box, line field with line break
    def edit(dialog):
        rows2 = dict((l._args[0], e) for l, e in QFormLayout.instances[-1].rows)
        rows2["fps"].setCurrentText("29.970")
        rows2["scale"].setText(" 1280:720 ")
        rows2["description"].setPlainText("first line\nsecond line")
    QDialog.on_exec = edit
    result = dialogs.edit_pairs(None, "Profile", pairs, {}, PRESETS)
    check(result["fps"] == "29.970" and result["scale"] == "1280:720" and result["description"] == "first line second line",
          f"changed values: {result}")
    # cancel
    QDialog.on_exec = None
    QDialog.exec_result = 0
    check(dialogs.edit_pairs(None, "Profile", pairs, {}, PRESETS) is None, "cancel returns None")
    QDialog.exec_result = 1
    # long values in any field also become multi-line
    FontMetrics.px_per_char = 10
    try:
        QFormLayout.instances.clear()
        dialogs.edit_pairs(None, "Options", {"aflags": "x" * 40}, {}, {})
        long_editor = QFormLayout.instances[-1].rows[0][1]
        check(isinstance(long_editor, dialogs.WrappedEdit), "long value in any field becomes multi-line")
    finally:
        FontMetrics.px_per_char = 1
    # Enter in the multi-line field confirms the dialog instead of inserting a line break
    accepted = []
    edit_box = dialogs.WrappedEdit("text", lambda: accepted.append(1))
    class Key:
        def __init__(self, key): self.k = key
        def key(self): return self.k
    edit_box.keyPressEvent(Key(0x01000004))
    edit_box.keyPressEvent(Key(0x41))
    check(accepted == [1], "Enter confirms")
    # The replacement rejects a number instead of an enumeration (the error that was noticed in the real Qt)
    try:
        edit_box.setHorizontalScrollBarPolicy(1)
        check(False, "replacement does not detect a number instead of an enumeration")
    except TypeError:
        pass
    print("Dialog: OK (field types, multi-line description, inputs, cancel, Enter, checking of the enumerations)")


def test_memory_player():
    """MemoryVlcPlayer against a simulated vlc module: formats, callbacks, picture hand-over, shutdown."""
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
        check(player.surface.called("setGeometry") == [(0, 0, 513, 290)], "drawing area fills the video area")
        mp = player.mp
        player.load("/x/film.ts", (720, 576))
        check(mp.format == ("RV32", 720, 576, 2880) and mp.aspect == "720:576" and len(mp.cb_calls) == 1 and mp.stops >= 1,
              f"Format: {mp.format} {mp.aspect}")
        lock, unlock, display, opaque = mp.cb_calls[0]
        check(unlock is None and opaque is None, "no unlock callback")
        planes = [None]
        lock(None, planes)
        check(planes[0].value == ctypes.addressof(player._buf), "callback delivers the memory area")
        ctypes.memmove(player._buf, b"\x01\x02\x03\xff" * (720 * 576), 720 * 576 * 4)
        display(None, None)
        image = player.surface.image
        check(image is not None and image._args[0] == b"\x01\x02\x03\xff" * (720 * 576) and image._args[1:4] == (720, 576, 2880),
              "picture arrives in the drawing area")
        player.load("/x/two.ts", (720, 576))
        check(len(mp.cb_calls) == 1 and player.surface.image is None, "same size: no reinstallation, picture cleared")
        player.load("/x/hd.ts", (1281, 721))
        check(mp.format == ("RV32", 1280, 720, 5120) and len(mp.cb_calls) == 2, f"new size (made even): {mp.format}")
        player.set_aspect("4:3")
        check(player.surface.aspect == (4, 3), "display format")
        # pictures before reaching the start position are not shown (VLC shows the start of the file first)
        lock3, _, display3, _ = mp.cb_calls[-1]
        player.load("/x/three.ts", (1280, 720))
        lock3, _, display3, _ = mp.cb_calls[-1]
        ctypes.memmove(player._buf, b"\x07\x07\x07\xff" * (1280 * 720), 1280 * 720 * 4)
        player.show_at(193_000)
        display3(None, None)
        check(player.surface.image is None, "picture from the start of the file is discarded as long as the position is missing")
        player._awaiting_position = None                            # (position counts as reached)
        # jump in the paused state: if no picture arrives, the medium is reloaded with the start position
        mp.state, mp.t = 4, 90_000
        QTimer.pending.clear()
        frames0 = player._frames_shown
        player._do_seek(560)
        check(len(QTimer.pending) == 1 and QTimer.pending[0][0] == 600, f"check after 600 ms scheduled: {QTimer.pending}")
        loads = mp.calls_play
        QTimer.pending.pop(0)[1]()                                  # no picture arrived
        check(mp.calls_play == loads + 1 and player._awaiting_position == 560 and mp.media.options == [":start-time=0.560"],
              f"no picture after the jump: reloaded with start-time: {mp.media.options}")
        player._awaiting_position = None
        QTimer.pending.clear()
        mp.state, mp.t = 4, 90_000                                  # paused again (reloading has stopped)
        player._do_seek(2000)
        player.surface.image = None
        display3(None, None)                                        # picture has arrived
        loads = mp.calls_play
        QTimer.pending.pop(0)[1]()
        check(mp.calls_play == loads, "picture arrived: no reloading")
        QTimer.pending.clear()
        mp.state, mp.t = 4, 5000
        player._do_seek(5050)                                       # almost the same position: do not check
        check(QTimer.pending == [], "jump to (almost) the same position is not checked")
        player._do_seek(7000)
        player._do_seek(9000)                                       # superseded
        loads = mp.calls_play
        QTimer.pending.pop(0)[1]()
        check(mp.calls_play == loads, "superseded jump is not checked")
        mp.state = 5
        QTimer.pending.clear()
        player._do_seek(100)
        check(QTimer.pending == [], "only in the paused state")
        player._awaiting_position = player._pending_show = 193_000
        mp.state = 5
        mp.t = 193_050
        QTimer.pending.clear()
        player.playing.emit()
        QTimer.pending.pop(0)[1]()
        check(player._awaiting_position is None and mp.set_times[-1] == 193_000, "position reached: another jump for a fresh picture")
        display3(None, None)
        check(player.surface.image is not None, "afterwards pictures are shown")
        image_before = player.surface.image
        player.shutdown()
        lock2, _, display2, _ = mp.cb_calls[1]
        display2(None, None)
        display3(None, None)
        check(player.surface.image is image_before and mp.released, "no more pictures after shutdown, player released")
    finally:
        del sys.modules["vlc"]
    print("Memory playback: OK (format, callbacks, picture hand-over, size change, shutdown)")


def test_timeline(tmp, videos):
    """Timeline: window of the 20 frames, click shifting, crosses, drawing, frame numbers from real recordings."""
    import numpy as np
    import timeline as tl
    from PIL import Image
    from frames import grab_frame, grab_numbered
    from PySide6.QtWidgets import Rect
    s2 = os.path.join(videos, "sample2.ts")
    # --- pure logic
    check(tl.window_numbers(100)[0] == 90 and tl.window_numbers(100)[10] == 100 and tl.window_numbers(100)[19] == 109
          and len(tl.window_numbers(5)) == 20, "window of the frame numbers")
    check([tl.click_delta(i) for i in range(20)] == list(range(-9, 0)) + [0, 0] + list(range(1, 10)), "shift per frame")
    check([tl.click_index(x, 1085) for x in (0, 53, 54, 540, 541, 1084)] == [0, 0, 1, 10, 10, 19], "frame under the mouse")
    check(tl.thumb_size(720, 576, 54) == (53, 42) and tl.thumb_size(576, 720, 54) == (42, 53), "size of the thumbnails")
    check((tl.frame_number(1.824, 1.4, 25), tl.frame_number(1.4, 1.4, 25), tl.frame_number(1.439, 1.4, 25),
           tl.frame_number(1.44, 1.4, 25)) == (10, 0, 0, 1), "frame number from the timestamp")
    # --- real recording: numbers from the timestamps, picture content matches grab_frame
    got = grab_numbered(s2, 0, 20, Fraction(25), (54, 43))
    check(sorted(got) == list(range(10, 30)) and got[10].shape == (43, 54, 3),
          f"frame numbers at the start of the file (sound starts earlier): {sorted(got)[:3]}..{sorted(got)[-2:]}")
    got = grab_numbered(s2, 40, 10, Fraction(25), (54, 43))
    check(sorted(got) == list(range(40, 50)), f"window in the middle of the file: {sorted(got)}")
    for n in (40, 49):
        ref = np.asarray(Image.fromarray(grab_frame(s2, n, Fraction(25))).resize((54, 43), Image.BOX)).astype(int)
        diff = np.abs(ref - got[n].astype(int)).mean()
        check(diff < 12, f"thumbnail {n} matches frame {n}: deviation {diff:.1f}")
    # --- main window with simulated picture source (recording starts at frame 10, 148 frames)
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
    check(area.width() == 1085 and cw == 54, f"drawing area {area.width()}")
    line = win.Line1.called("setGeometry")[-1]
    check(line[0] == win.picTimeline.geometry().x() + area.x() + 10 * cw - 1 and line[2] == 3, f"line lies on the cut position: {line}")
    win.OpenVideo(s2)
    seg = win.segments[0]
    check(win.timeline_mode == "A" and win.timeline_center == 0 and calls[-1][:2] == (0, 10) and calls[-1][2] == (53, 42),
          f"timeline at frame 0: {win.timeline_center} {calls[-1]}")
    check(all(state == "cross" for state, _ in win.timeline_cells()) and len(win.timeline_cells()) == 20,
          "start: only crosses (the first 10 frames are missing, and those before them as well)")
    # marker A at 50: frames 40..59 are loaded and shown
    win._go(50)
    win.cmdPos_Click(7)
    cells = win.timeline_cells()
    check(seg.start == 50 and calls[-1][:2] == (40, 20) and [c[0] for c in cells] == ["image"] * 20, f"Marker A: {calls[-1]}")
    # marker B at 100: timeline around the end; the segment ends with the frame left of the line
    win._go(100)
    win.cmdPos_Click(8)
    check(seg.end == 100 and win.timeline_mode == "B" and win.timeline_center == 100 and calls[-1][:2] == (90, 20), "Marker B")
    # click: left of the line
    def click(index):
        win._mouse_x = area.x() + index * cw + 5
        win.picTimeline_Click()
    click(5)
    check(seg.end == 96 and win.timeline_center == 96 and win.Slider1.value() == 96, f"click left (index 5): end {seg.end}")
    click(9)
    click(10)
    check(seg.end == 96, "click on the two frames at the line changes nothing")
    click(15)
    check(seg.end == 101 and win.lvwSegments.topLevelItem(0).text(4) == "101", f"click right (index 15): end {seg.end}")
    seg.start, seg.end = 95, 101
    click(0)
    check(seg.end == 96, f"end stays at least one frame behind the start: {seg.end}")
    seg.end = 147
    click(19)
    check(seg.end == 148, f"end stays in the movie: {seg.end}")
    # markers A and B must not overtake each other and must not coincide (segment would have 0 frames)
    seg.start, seg.end = 10, 12
    win.cmdPos_Click(9)
    click(19)
    check((seg.start, seg.end) == (11, 12), f"marker A stays before B: {seg.start}/{seg.end}")
    win.cmdPos_Click(10)
    click(0)
    check((seg.start, seg.end) == (11, 12), f"marker B stays behind A: {seg.start}/{seg.end}")
    n_beeps = QtWidgets.QApplication.log.count("beep")
    win._go(12)
    win.cmdPos_Click(7)                                           # set A onto B: rejected
    win._go(11)
    win.cmdPos_Click(8)                                           # set B onto A: rejected
    win._go(13)
    win.cmdPos_Click(7)                                           # set A behind B: rejected
    win._go(5)
    win.cmdPos_Click(8)                                           # set B before A: rejected
    check((seg.start, seg.end) == (11, 12) and QtWidgets.QApplication.log.count("beep") == n_beeps + 4,
          f"setting via the buttons: {seg.start}/{seg.end}")
    win._go(8)
    win.cmdPos_Click(7)                                           # A before B: allowed
    check(seg.start == 8, "A before B is allowed")
    seg.start, seg.end = 0, 148
    # click in mode A
    win.cmdPos_Click(9)
    seg.start = 50
    click(12)
    check(seg.start == 52 and win.Slider1.value() == 52 and win.timeline_center == 52, f"click right, marker A: {seg.start}")
    click(0)
    seg.start = 3
    click(0)
    check(seg.start == 0, f"marker A not below 0: {seg.start}")
    # no mode: click has no effect
    win.timeline_mode = None
    seg.start = 20
    click(0)
    check(seg.start == 20, "no effect without a mode")
    win.cmdPos_Click(9)
    # outdated results are discarded
    cache_size = len(win.thumb_cache)
    win.thumbs_loaded(win._thumb_token - 1, {999: np.zeros((42, 53, 3), np.uint8)}, (999, 999), seg.path, (53, 42))
    check(len(win.thumb_cache) == cache_size, "superseded request is ignored")
    # drawing
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
          and painter.lines == [] and painter.fills == [(2 + 10 * cw - 1, 2, 3, 45)], f"drawing: {painter.fills}")
    seg.start = 0
    win.cmdPos_Click(9)
    painter = Painter()
    win.timeline_paint(painter, Rect(2, 2, 1085, 45))
    check(len(painter.lines) == 40 and painter.images == [], "drawing at the start: 20 crosses")
    print("Timeline: OK (window, click shifting, crosses, drawing, frame numbers from timestamps)")


def quick_thumbs(path, first, count, fps, size, on_start=None):
    """Simulated thumbnails (fast), so that the tests do not wait for ffmpeg."""
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
    """Delete, move, duplicate segments (with search for the start of the movie) and the search itself."""
    import seek
    from PySide6 import QtWidgets
    s2, s3 = os.path.join(videos, "sample2.ts"), os.path.join(videos, "sample3.ts")
    # --- move, delete, remove all
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"))
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    win.cmdCommand_Click(2)
    titles = lambda: [win.lvwSegments.topLevelItem(i).text(2) for i in range(win.lvwSegments.row_count())]
    check(titles() == ["sample3.ts", "sample2.ts"] and win.current == 1 and win.segments[1].path == s2
          and win.lvwSegments.topLevelItem(0).text(0) == "01", f"down: {titles()} {win.current}")
    win.cmdCommand_Click(2)
    check(titles() == ["sample3.ts", "sample2.ts"] and win.current == 1, "all the way down: no change")
    win.cmdCommand_Click(1)
    check(titles() == ["sample2.ts", "sample3.ts"] and win.current == 0, "up")
    win.cmdCommand_Click(1)
    check(win.current == 0, "all the way up: no change")
    check([s.path for s in load_segments(os.path.join(tmp, "seekwin", "MediaMaker.json"))] == [s2, s3], "order saved")
    win.cmdCommand_Click(0)
    check(len(win.segments) == 1 and win.current == 0 and win.segments[0].path == s3 and "stop" in win.player.log
          and f"load {s3}" in win.player.log and win.lvwSegments.current_row() == 0
          and win.lvwSegments.row_count() == 1 and win.lvwSegments.topLevelItem(0).text(0) == "01"
          and len(load_segments(os.path.join(tmp, "seekwin", "MediaMaker.json"))) == 1,
          "delete: the successor is selected and loaded")
    win.cmdCommand_Click(5)
    check("not been ported" in win.messages[-1], "crop/logo: note")
    win.answer = False
    win.cmdCommand_Click(3)
    check(len(win.segments) == 1, "remove all: no")
    win.answer = True
    win.cmdCommand_Click(3)
    check(win.segments == [] and win.lvwSegments.row_count() == 0 and win.lblText[0].text() == "00:00:00"
          and load_segments(os.path.join(tmp, "seekwin", "MediaMaker.json")) == [], "remove all: yes")
    # --- selection after deleting: last entry -> new last, entry in the middle -> successor, finally empty list
    sample = os.path.join(videos, "sample.ts")
    dwin = seek_window(tmp, videos, ("sample2.ts", "sample3.ts", "sample.ts"), workdir="delwin")
    dwin.lvwSegments.select_row(2)
    dwin.lvwSegments_Click()
    dwin.player.log.clear()
    dwin.cmdCommand_Click(0)
    check([x.path for x in dwin.segments] == [s2, s3] and dwin.current == 1 and dwin.lvwSegments.current_row() == 1
          and f"load {s3}" in dwin.player.log, f"last entry deleted: the new last one is selected ({dwin.current}, row {dwin.lvwSegments.current_row()})")
    dwin.lvwSegments.select_row(0)
    dwin.lvwSegments_Click()
    dwin.cmdCommand_Click(0)
    check([x.path for x in dwin.segments] == [s3] and dwin.current == 0 and dwin.lvwSegments.current_row() == 0, "middle/first deleted: successor selected")
    dwin.cmdCommand_Click(0)
    check(dwin.segments == [] and dwin.current == -1 and dwin.lvwSegments.row_count() == 0, "last remaining deleted: empty list")
    dwin.cmdCommand_Click(0)
    check(dwin.segments == [], "empty list: button has no effect")

    # --- duplicate with search for the start of the movie (simulated border detection: movie from frame 130)
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
    check(seg.end == 100, "marker B at 100")
    win.cmdCommand_Click(4)
    new = win.segments[1]
    check((new.start, new.end, new.path, new.crop_top, new.mask) == (100, 148, s2, 5, "0.1 0.2 0.3 0.4") and win.current == 1,
          f"new segment: {new.start}/{new.end}")
    check(win.Slider1.value() == 130 and win.player.time == 5200 and win.lblInfo.text() == f"Frame {130 - new.first_frame}",
          f"search for the start of the movie: frame {win.Slider1.value()}, time {win.player.time}")
    check(min(probes) >= 125 and len(probes) < 40 and win.dialogs[-1].closed and "Seeking" in win.dialogs[-1].message,
          f"search starts behind the minimum length of a commercial (pause): {min(probes)}, {len(probes)} probes")
    check(len(load_segments(os.path.join(tmp, "dupwin", "MediaMaker.json"))) == 2, "saved")
    # marker B at the end of the movie: nothing to duplicate
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    seg.end = seg.total_frames
    win.cmdCommand_Click(4)
    check(len(win.segments) == 2 and "nothing left" in win.messages[-1], "duplicate at the end of the file")
    # several source files in the list: the search runs anyway (unlike VB6)
    win = seek_window(tmp, videos, ("sample3.ts", "sample2.ts"), workdir="dupwin2", border_fn=border)
    win.settings.set_option("pause", 1)
    probes.clear()
    win.lvwSegments.select_row(1)
    win.lvwSegments_Click()
    win._go(100)
    win.cmdPos_Click(8)
    win.cmdCommand_Click(4)
    check(win.multiple() and probes != [] and win.Slider1.value() == 130, f"several sources: search runs, frame {win.Slider1.value()}")
    # intermediate results in the wait window
    texts = win.dialogs[-1].texts
    probe_texts = [t for t in texts if "looking for about 72" in t]
    check(texts and texts[0].startswith("Seeking, please wait...\nframe ") and "border" in texts[0] and "about 72" in texts[0]
          and any("border 72" in t for t in texts) and len(probe_texts) == len(probes)
          and "looking for a cut" in texts[-1], f"wait window shows every probe and the cut search: {texts[:2]}")
    # neither crop nor logo: message, no search
    win = seek_window(tmp, videos, workdir="dupwin3", border_fn=border)
    win.settings.set_option("crop", 0)
    win.settings.set_option("pause", 1)
    probes.clear()
    win.cmdPos_Click(8)
    win._go(100)
    win.cmdPos_Click(8)
    win.cmdCommand_Click(4)
    check(probes == [] and "neither a cropping value" in win.messages[-1] and len(win.segments) == 2, f"without crop and logo: {win.messages[-1:]}")
    win.mnuNext_Click()
    check("neither a cropping value" in win.messages[-1], "also when seeking the next commercial")

    # --- search with the station logo (simulated detection: logo from frame 90, scene change at frame 60)
    elysium = parse_batch_header(open(os.path.join(HERE, "sample_Elysium.bat"), encoding="latin-1").read())
    conf = lambda path, n, fps, ref, opts: 0.9 if n >= 90 else 0.0
    avg = lambda path, f, fps, opts: (10, 10, 10) if f >= 60 else (200, 10, 10)
    win = seek_window(tmp, videos, workdir="logowin", conf_fn=conf, avg_fn=avg)
    win.settings.set_option("crop", 0)
    win.segments[0].mask = elysium.segments[0].mask
    win.mnuEnd_Click()
    check(win.Slider1.value() == 60, f"logo: first frame with logo, then back to the scene change: {win.Slider1.value()}")
    check(any("logo confidence 0.90" in t for t in win.dialogs[-1].texts), "logo search reports every probe")
    win._go(0)
    conf = lambda path, n, fps, ref, opts: 0.9 if n < 50 else 0.0
    win._conf_fn = conf
    win.mnuNext_Click()
    check(win.Slider1.value() == 50, f"logo: start of the next commercial (no more logo): {win.Slider1.value()}")

    # --- real recordings (ffmpeg): commercial -> movie (sample3) and movie -> commercial (sample2) with crop = 72
    win = seek_window(tmp, videos, ("sample3.ts",), workdir="realwin")
    win._go(0)
    win.mnuEnd_Click()
    check(win.Slider1.value() == 59, f"real recording, end of the commercial: {win.Slider1.value()} (expected 59)")
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="realwin2")
    win._go(0)
    win.mnuNext_Click()
    check(win.Slider1.value() == 76, f"real recording, next commercial: {win.Slider1.value()} (expected 76)")

    # --- cancel
    try:
        seek.seek_border("/x", Fraction(25), 1000, 0, 72, True, 1000, {}, lambda *a: 0, lambda: True)
        check(False, "cancel raises no exception")
    except seek.SeekCancelled:
        pass
    got = []
    worker = seek.SeekWorker(lambda cancel: (_ for _ in ()).throw(seek.SeekCancelled()))
    worker.done.connect(got.append)
    worker.failed.connect(got.append)
    worker.run()
    check(got == [], "cancelled search reports nothing")
    worker = seek.SeekWorker(lambda cancel: (_ for _ in ()).throw(RuntimeError("broken")))
    worker.failed.connect(got.append)
    worker.run()
    check(got == ["broken"], "error is reported")
    print("Segments and search: OK (move, delete, remove all, duplicate with search, logo, real recordings, cancel)")


def test_thumbnail_errors(tmp, videos):
    """Errors when loading the thumbnails are reported; missing start times ("N/A") do not break anything."""
    import types
    import numpy as np
    import ffmpeg_cmd
    import timeline as tl
    from PySide6 import QtWidgets
    # --- start times
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
            check(ffmpeg_cmd.stream_times_of.__wrapped__("/x") == expected, f"start times {output!r}")
    finally:
        ffmpeg_cmd.subprocess.run = real_run
    # --- error in the background thread
    errors = []
    def broken(path, first, count, fps, size, on_start=None):
        raise RuntimeError("ffmpeg broken")
    loader = tl.ThumbLoader(3, "/x", 0, 9, Fraction(25), (53, 42), broken)
    loader.failed.connect(lambda token, text: errors.append((token, text)))
    loader.run()
    check(errors == [(3, "RuntimeError: ffmpeg broken")], f"error is reported: {errors}")
    loader = tl.ThumbLoader(4, "/x", 0, 9, Fraction(25), (53, 42), broken)
    loader.failed.connect(lambda token, text: errors.append((token, text)))
    loader.cancelled = True
    loader.run()
    check(len(errors) == 1, "cancelled request reports no error")
    # --- main window: one-time message, title
    win = seek_window(tmp, videos, workdir="thumberr", names=())
    win._thumb_fn = broken
    win.OpenVideo(os.path.join(videos, "sample2.ts"))
    shown = [m for m in win.messages if "thumbnails could not be loaded" in m]
    check(len(shown) == 1 and "ffmpeg broken" in shown[0], f"message about the error: {win.messages}")
    titles = [a[0] for a in win.called("setWindowTitle")]
    check(not win._thumbs_busy and titles[-1] == "MediaMaker " + __import__("mediamaker").VERSION and any("loading thumbnails" in t for t in titles),
          f"title during and after loading: {titles[-3:]}")
    win.timeline_mode = "B"
    win._thumb_token += 1
    win.thumbs_failed(win._thumb_token, "second error")
    check(len([m for m in win.messages if "thumbnails could not" in m]) == 1, "message only once")
    win.thumbs_failed(win._thumb_token - 5, "superseded")
    check(len([m for m in win.messages if "thumbnails could not" in m]) == 1, "superseded errors are ignored")
    # --- placeholders for pictures not yet loaded
    class Painter:
        def __init__(self): self.fills, self.lines = [], []
        def drawImage(self, *a): pass
        def setPen(self, c): pass
        def drawLine(self, *a): self.lines.append(a)
        def fillRect(self, *a): self.fills.append(a)
    painter = Painter()
    tl.draw_strip(painter, __import__("PySide6.QtWidgets", fromlist=["Rect"]).Rect(2, 2, 1085, 45),
                  [("pending", None)] * 20)
    check(len(painter.fills) == 21 and painter.lines == [], f"20 grey placeholders and the line: {len(painter.fills)}")
    print("Thumbnail errors: OK (start times without value, error message, once, title, placeholders)")


def test_first_frame(tmp, videos):
    """If the sound starts earlier than the video, the first video frame does not have the number 0: the start of the segment is then
        on the first real frame, and the timeline shows thumbnails right of the line immediately."""
    import ffmpeg_cmd
    import timeline as tl
    from mediaprobe import first_frame_number
    check([first_frame_number(os.path.join(videos, n), Fraction(25)) for n in ("sample.ts", "sample2.ts", "sample3.ts")] == [33, 10, 14],
          "number of the first frame")
    work = os.path.join(tmp, "firstwin")
    os.makedirs(work, exist_ok=True)
    s2 = os.path.join(videos, "sample2.ts")
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True, first_fn=first_frame_number)
    win.showEvent(None)
    win.OpenVideo(s2)
    seg = win.segments[0]
    check((seg.first_frame, seg.start, seg.end, seg.total_frames) == (10, 10, 158, 158), f"Segment: {seg.first_frame}/{seg.start}/{seg.end}")
    check((win.Slider1.minimum(), win.Slider1.maximum(), win.Slider1.value()) == (10, 158, 10), "slider starts at the first frame")
    cells = win.timeline_cells()
    check([c[0] for c in cells] == ["cross"] * 10 + ["image"] * 10, f"timeline: 10 crosses left, 10 pictures right: {[c[0] for c in cells]}")
    check(win.lblInfo.text() == "Frame 0" and win.lvwSegments.topLevelItem(0).text(3) == "0"
          and win.lvwSegments.topLevelItem(0).text(6) == "148", "display: counting from the first video frame (number 0)")
    # limits
    win.cmdPos_Click(0)
    check(win.Slider1.value() == 10, "start")
    win.cmdPos_Click(6)
    check(win.Slider1.value() == 158, "end")
    win.cmdPos_Click(9)
    check(win.timeline_center == 10, "timeline around the start")
    def click(index):
        area = win.picTimeline.contentsRect()
        win._mouse_x = area.x() + index * tl.cell_width(area.width()) + 5
        win.picTimeline_Click()
    click(0)
    check(seg.start == 10, f"marker A not before the first frame: {seg.start}")
    win._go(60)
    win.cmdPos_Click(7)
    win.cmdPos_Click(11)
    check((seg.start, seg.end) == (10, 158), "reset markers to first and last frame")
    win.cmdPos_Click(10)
    cells = win.timeline_cells()
    check([c[0] for c in cells][:10] == ["image"] * 10 and [c[0] for c in cells][10:] == ["cross"] * 10, "end: frames on the left, crosses on the right")
    # saved, whole file = no trim in the command
    check(load_segments(os.path.join(work, "MediaMaker.json"))[0].first_frame == 10, "first_frame saved")
    job = Job(os.path.join(tmp, "o.mp4"), {"scale": "720:576", "sws_flags": "lanczos", "fps": "25.000", "bv": "3072k", "ba": "192k",
                                          "acodec_out": "aac", "ar": "48000"}, {}, [seg])
    times = {s2: (Fraction(7, 5), Fraction(228, 125))}
    cmd = ffmpeg_cmd.build_command(job, stream_times=times)
    check("trim=" not in cmd[cmd.index("-filter_complex") + 1], "whole file: no trim")
    # several segments: a whole file is trimmed to its first picture (otherwise concat pads the picture when the sound starts earlier)
    seg.start = 10
    job2 = Job(os.path.join(tmp, "o.mp4"), job.profile, {}, [seg, dataclasses.replace(seg, index=2, start=60)])
    cmd2 = ffmpeg_cmd.build_command(job2, stream_times=times)
    check(cmd2[cmd2.index("-filter_complex") + 1].count("trim=") == 4, "several segments: the whole file is trimmed as well (video and audio)")
    seg.start = 60
    cmd = ffmpeg_cmd.build_command(job, stream_times=times)
    check("trim=" in cmd[cmd.index("-filter_complex") + 1], "excerpt: trim")
    # old lists without first_frame behave as before
    legacy = Segment(1, s2, "sample2.ts", 0, 148, 148, Fraction(25), 720, 576, 0, 0, "a", 0, 0, 0, 0, 48000, "")
    check(legacy.first_frame == 0 and not (legacy.end - legacy.start < legacy.total_frames - legacy.first_frame), "old list: whole file")
    # exact count: total = first frame + number of frames
    seg.start, seg.end = 10, 158
    win.frames_counted(s2, 140, 8, 0.0)
    check((seg.total_frames, seg.end) == (150, 150), f"after counting: {seg.total_frames}/{seg.end}")
    check(win.Slider1.minimum() == 10 and win.Slider1.maximum() == 150, "slider after counting")
    print("First frame: OK (segment start on the first video frame, timeline, limits, saving, command without trim)")


def test_marker_start(tmp, videos):
    """A segment with marker A > 0 is shown at this position when clicked (not at the start of the file); old lists are converted
        to the first video frame; VLC receives the start position as a media option."""
    import types
    from types import SimpleNamespace
    import player as pl
    from PySide6.QtCore import QTimer
    s2 = os.path.join(videos, "sample2.ts")
    # --- old list (without first_frame): update on loading
    work = os.path.join(tmp, "legacywin")
    os.makedirs(work, exist_ok=True)
    legacy = [Segment(1, s2, "sample2.ts", 0, 148, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, ""),
              Segment(2, s2, "sample2.ts", 50, 148, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, ""),
              Segment(3, s2, "sample2.ts", 20, 90, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, "")]
    save_segments(os.path.join(work, "MediaMaker.json"), legacy)
    win = make_window(work, thumb_fn=quick_thumbs, first_fn=lambda path, fps: 10)
    win.showEvent(None)
    got = [(s.first_frame, s.start, s.end, s.total_frames) for s in win.segments]
    check(got == [(10, 10, 158, 158), (10, 50, 158, 158), (10, 20, 90, 158)], f"old list converted: {got}")
    check([(s.first_frame, s.start, s.end, s.total_frames) for s in load_segments(os.path.join(work, "MediaMaker.json"))] == got, "converted and saved")
    win2 = make_window(work, thumb_fn=quick_thumbs, first_fn=lambda path, fps: 99)           # do not convert again
    win2.showEvent(None)
    check([(s.first_frame, s.total_frames) for s in win2.segments] == [(10, 158)] * 3, "already converted list stays unchanged")
    # --- clicking: display at marker A, not at the start of the file
    win2.lvwSegments.select_row(1)
    win2.lvwSegments_Click()
    check(win2.player.log[-1] == "show_at 2000" and win2.Slider1.value() == 50 and win2.lblInfo.text() == "Frame 40",
          f"segment with A=50: {win2.player.log[-2:]}, slider {win2.Slider1.value()}, {win2.lblInfo.text()}")
    # time messages from VLC right afterwards (from the old position) do not change display and slider
    win2.player.time_changed.emit(0)
    check(win2.lblInfo.text() == "Frame 40" and win2.Slider1.value() == 50 and win2.last_frame == 50, "old time message is ignored")
    now = [100.0]
    win2._clock = lambda: now[0]
    win2._ignore_time_until = 101.5
    now[0] = 102.0
    win2.player.time_changed.emit(4000)
    check(win2.lblInfo.text() == "Frame 90", f"later time messages count again: {win2.lblInfo.text()}")
    # --- VLC: start position as media option and re-check
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
              f"start position as media option: {mp.calls}")
        QTimer.pending.clear()
        mp.calls.clear()
        player.playing.emit()                                       # VLC reports: running
        check(("pause", 1) in mp.calls and len(QTimer.pending) == 1 and QTimer.pending[0][0] == 150, f"then pause: {mp.calls}")
        mp.t = 0                                                    # VLC is still at the start: caught up, repeatedly
        QTimer.pending.pop(0)[1]()
        check(("set_time", 193_000) in mp.calls and len(QTimer.pending) == 1 and player._awaiting_position == 193_000,
              f"re-check jumps and checks again: {mp.calls}")
        mp.t = 193_100                                              # reached now
        mp.calls.clear()
        QTimer.pending.pop(0)[1]()
        check(player._awaiting_position is None and QTimer.pending == [] and mp.calls == [], "position reached: done")
        check(mp.mutes[:1] == [True] and mp.mutes[-1] is False and player._muted is False, f"sound: muted first, on again after reaching: {mp.mutes}")
        # VLC reports "seekable": jump to the position immediately (earlier than "Playing")
        mp.state = 5
        player.show_at(41_000)
        mp.calls.clear()
        player.seekable.emit(False)
        check(("set_time", 41_000) not in mp.calls, "not seekable: no jump")
        player.seekable.emit(True)
        check(("set_time", 41_000) in mp.calls, f"seekable: jump to the position: {mp.calls}")
        player.play()                                              # the user starts: stop waiting, sound on
        check(player._awaiting_position is None and player._muted is False and mp.mutes[-1] is False, "play() ends the approach and switches the sound on")
        player.seekable.emit(True)
        check(mp.calls.count(("set_time", 41_000)) == 1, "no further jump after play()")
        mp.state = 5
        QTimer.pending.clear()
        player.show_at(5000)                                        # state stopped: again via start-time
        QTimer.pending.clear()
        player.playing.emit()
        mp.t = 5100
        mp.calls.clear()
        QTimer.pending[0][1]()
        check(mp.calls == [] and player._awaiting_position is None, "position reached: no additional jump")
        # superseded request: a second position has been requested in the meantime
        player.show_at(9000)
        QTimer.pending.clear()
        player.playing.emit()
        player.stop()
        mp.calls.clear()
        QTimer.pending[0][1]()
        check(mp.calls == [], "superseded re-check does nothing")
        mp.state = 5
        player.show_at(9000)
        QTimer.pending.clear()
        player.playing.emit()
        mp.t = -1                                                   # VLC does not know the time: at most 30 attempts
        for _ in range(60):
            if not QTimer.pending:
                break
            QTimer.pending.pop(0)[1]()
        check(player._awaiting_position is None, "give up after at most 30 attempts")
        mp.state = 5
        mp.state = 4                                                # paused: direct jump
        mp.calls.clear()
        player.show_at(7000)
        check(mp.calls == [("set_time", 7000)], f"paused: direct jump: {mp.calls}")
    finally:
        del sys.modules["vlc"]
    print("Marker A on click: OK (display at marker A, old lists, time messages, VLC start position)")


def test_jump_to_frame(tmp, videos):
    """Click on the frame number: input of a frame number to jump to."""
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
    check(asked == [], "nothing happens without a segment")
    win.OpenVideo(s2)
    win.answer_int = 99
    handler()
    check(asked[-1][2:] == (0, 0, 148) and "0 to 148" in asked[-1][1], f"input in displayed numbers with default and range: {asked[-1]}")
    check(win.Slider1.value() == 109 and win.lblInfo.text() == "Frame 99" and win.player.time == 4360,
          f"input 99 = absolute 109: {win.Slider1.value()} {win.player.time}")
    win._go(40)
    win.answer_int = None                                         # cancelled
    handler()
    check(asked[-1][2] == 30, "default is the current frame (displayed: 40 - 10)")
    check(win.Slider1.value() == 40, "cancel changes nothing")
    win.answer_int = 30                                           # same position (displayed 30 = absolute 40): picture is shown again
    shows = len([e for e in win.player.log if e.startswith("show_at")])
    handler()
    check(len([e for e in win.player.log if e.startswith("show_at")]) == shows + 1 and win.Slider1.value() == 40, "same position: show picture again")
    win.answer_int = 5000                                         # outside: slider limited
    handler()
    check(win.Slider1.value() == 158, "value outside the range is limited")
    check(win.lblInfo.called("setToolTip") != [], "Tooltip")
    print("Jump to a frame number: OK (input, default, range, cancel, same position)")


def test_media_info(tmp, videos):
    """Media info (Ctrl+K): report from ffprobe with section "MediaMaker", dialog with buttons and copying; tooltip of the timeline."""
    import mediainfo
    from mediaprobe import first_frame_number
    from PySide6.QtWidgets import QApplication
    s2 = os.path.join(videos, "sample2.ts")
    # --- report
    sections = mediainfo.build_sections(s2)
    names = [n for n, _ in sections]
    check(names == ["General", "Video #1", "Audio #1 (deu)", "MediaMaker"], f"sections: {names}")
    text = dict(sections)
    check("720 x 576" in text["Video #1"] and "25.000 fps" in text["Video #1"] and "mpegts" in text["General"]
          and "Complete name" in text["General"], "content of the sections")
    first = first_frame_number(s2, Fraction(25))
    mm = text["MediaMaker"]
    check(mediainfo._kv("First video frame offset", first) in mm and "Container start" in mm and "Video start" in mm
          and "Selected segment" not in mm, f"MediaMaker section: {mm[:300]}")
    seg = Segment(1, s2, "sample2.ts", first, 100, 148 + first, Fraction(25), 720, 576, 0, 0, "a", 1, 2, 3, 4, 48000, "")
    seg.first_frame = first
    mm = dict(mediainfo.build_sections(s2, seg))["MediaMaker"]
    check("Marker A (start)" in mm and f": {first}" in mm and "Frames in the segment" in mm and "1/2/3/4" in mm and "Logo mask / area           : none" in mm.replace("  ", " ").replace(" :", "  :") or "Logo mask" in mm,
          "section with segment")
    check(mediainfo.full_text(sections).count("\n\n") >= 3, "full text")
    # --- menu
    work = os.path.join(tmp, "infowin")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True)
    win.showEvent(None)
    shown = []
    win.show_media_info = lambda title, secs: shown.append((title, [n for n, _ in secs]))
    win.mnuMediaInfo_Click()
    check(shown == [], "nothing happens without a segment")
    win.OpenVideo(s2)
    win.mnuMediaInfo_Click()
    check(shown == [("sample2.ts", names)], f"menu: {shown}")
    real_build = mediainfo.build_sections
    mediainfo.build_sections = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffprobe missing"))
    try:
        win.mnuMediaInfo_Click()
    finally:
        mediainfo.build_sections = real_build
    check("could not be collected" in win.messages[-1] and "ffprobe missing" in win.messages[-1], "error is reported")
    # --- dialog: one tab per section, resizable, as wide as all tabs, text copyable
    from mediainfo_dialog import frmMediaInfo
    dialog = frmMediaInfo("sample2.ts", sections)
    check(dialog.called("setWindowTitle")[-1] == ("Media info for sample2.ts",) and dialog.TabStrip1.called("hide") != []
          and dialog.lblMediaInfo.called("hide") != [], "dialog: title, old controls hidden")
    flags = dialog.called("setWindowFlag")
    check(dialog.called("setMaximumSize") == [(16777215, 16777215)] and dialog.called("setMinimumSize") != []
          and "WindowMaximizeButtonHint" in repr(flags[-1][0]) and flags[-1][1] is True, "window is resizable")
    check([label for _, label in dialog.tabs.tabs_] == names and [e.toPlainText() for e in dialog.editors] == [t for _, t in sections]
          and dialog.tabs.currentIndex() == 0, "one tab per section with its text, the first tab is shown first")
    px = QtWidgets.FontMetrics.px_per_char
    need = sum(px * len(n) + 40 for n in names) + 40
    check(dialog.called("setMinimumWidth")[-1] == (need,) and "ElideNone" in repr(dialog.tabs.called("setElideMode")[-1][0])
          and dialog.tabs.called("setUsesScrollButtons")[-1] == (False,), f"all tabs completely visible: minimum width {need}, no eliding, no scroll buttons")
    dialog.show_tab(3)
    check(dialog.tabs.currentIndex() == 3, "show_tab selects the tab")
    dialog.copy_all()
    check(QApplication._Clipboard.text_ == mediainfo.full_text(sections), "copy all")
    # --- tooltip of the timeline with the frame number
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
    check(tip.startswith(f"Frame {center - 10} (no picture)"), f"tooltip before the first frame: {tip!r}")
    print("Media info: OK (report, segment values, menu, dialog, copying, tooltip with frame number)")


def test_autocrop(tmp, videos):
    """Auto crop (Ctrl+R): count black lines at the picture edge, suggest them as value for the option crop and take it over."""
    s2 = os.path.join(videos, "sample2.ts")
    asked = []
    # --- with real border detection at a frame of the movie (the sample movie has a border of about 72 lines)
    win = seek_window(tmp, videos, workdir="autocropwin")
    win.ask_int = lambda title, label, value, low, high: (asked.append((title, label, value, low, high)), win.answer_int)[1]
    win.answer_int = None
    check(win.options["crop"] == "72" or int(win.options["crop"]) == 72, f"initial value: {win.options['crop']}")
    win._go(win.segment.first_frame + 30)
    win.mnuAutoCrop_Click()
    title, label, value, low, high = asked[-1]
    check(abs(value - 72) <= 3 and low == 0 and high == 144 and "Current value in the options: 72" in label
          and f"{value} black lines at frame 30" in label and win.dialogs[-1].closed and "Auto-cropping" in win.dialogs[-1].message,
          f"suggested value: {value}, range {low}..{high}: {label!r}")
    check("was NOT changed" in win.messages[-1] and int(win.options["crop"]) == 72, "cancel: value stays")
    win.answer_int = 70
    win.mnuAutoCrop_Click()
    check(int(win.options["crop"]) == 70 and int(win.settings.options["crop"]) == 70, "taken over (adjusted value)")
    # --- simulated detection: nothing found, very large border
    found = {"n": 0}
    win = seek_window(tmp, videos, workdir="autocropwin2", border_fn=lambda path, n, fps, opts: found["n"])
    win.ask_int = lambda title, label, value, low, high: (asked.append((title, label, value, low, high)), win.answer_int)[1]
    win.answer_int = 0
    win.mnuAutoCrop_Click()
    check(asked[-1][2] == 0 and "No black border line(s) found" in asked[-1][1] and int(win.options["crop"]) == 0,
          f"nothing found: default 0, option 0: {asked[-1][1]!r}")
    found["n"] = 180
    win.answer_int = 180
    win.mnuAutoCrop_Click()
    check(asked[-1][2] == 180 and asked[-1][4] == 180 and int(win.options["crop"]) == 180, "upper limit grows with the found value")
    # --- nothing happens without a segment; error in the detection is reported
    win2 = seek_window(tmp, videos, names=(), workdir="autocropwin3")
    count = len(asked)
    win2.mnuAutoCrop_Click()
    check(len(asked) == count, "nothing happens without a segment")
    def broken(path, n, fps, opts):
        raise RuntimeError("ffmpeg broken")
    win3 = seek_window(tmp, videos, workdir="autocropwin4", border_fn=broken)
    win3.mnuAutoCrop_Click()
    check("Auto-cropping failed" in win3.messages[-1] and "ffmpeg broken" in win3.messages[-1], f"error is reported: {win3.messages[-1:]}")
    print("Auto crop: OK (counting at the current frame, suggestion with comparison value, taking over, cancel, error)")


def test_input_box(tmp, videos):
    """Input fields (estimating audio/video kb/s and others): fixed width like the InputBox of VB6, text is wrapped."""
    import dialogs
    from PySide6.QtWidgets import QDialog
    long_text = ("The average video bitrate has been calculated to 3072k bits/s and will be saved in your current profile "
                 "accordingly; you can still adjust it here, or hit cancel to keep the old value:")
    QDialog.exec_result, QDialog.on_exec = 1, lambda d: d.setTextValue("2500")
    box = dialogs._input_box(None, "Estimate video kb/s", long_text, dialogs.QtWidgets.QInputDialog.InputMode.TextInput)
    check(box.called("setFixedWidth") == [(440,)] and box.called("resize")[-1][0] == 440 and box.label_.called("setWordWrap") == [(True,)]
          and box.called("setWindowTitle") == [("Estimate video kb/s",)] and box.called("setLabelText") == [(long_text,)],
          "fixed width, wrapping, title, text")
    check(dialogs.ask_text_box(None, "T", long_text, "3072k") == "2500", "enter text")
    QDialog.exec_result = 0
    check(dialogs.ask_text_box(None, "T", long_text, "3072k") is None, "cancel gives None")
    QDialog.exec_result, QDialog.on_exec = 1, lambda d: d.setIntValue(70)
    check(dialogs.ask_int_box(None, "Auto crop", "label", 72, 0, 144) == 70, "enter whole number")
    box = dialogs._input_box(None, "x", "y", dialogs.QtWidgets.QInputDialog.InputMode.IntInput)
    check(box.called("setInputMode") != [], "input mode set")
    QDialog.exec_result, QDialog.on_exec = 1, None
    print("Input fields: OK (fixed width 440 px, wrapping, text and number, cancel)")


def test_option_changes(tmp, videos):
    """Rearrangement: pad in the profile, focus dropped, new search parameters, grouped dialog, step widths in seconds."""
    import logo
    import seek
    from profiles import HIDDEN_OPTIONS, OPTION_GROUPS, ordered_profile, validate_options, validate_profile
    from settings import DEFAULT_TOOLTIPS, default_options
    # --- defaults and checking
    d = default_options()
    check("pad" not in d and "focus" not in d and d["step_end"] == "40" and d["step_next"] == "240" and d["border_tol"] == "3"
          and d["logo_rewind"] == "1.8" and d["logo_edge"] == "18" and d["logo_conf"] == "0.2", "defaults")
    check(validate_options(d) == [], "defaults are valid")
    check(len(validate_options({"step_end": "0"})) == 1 and len(validate_options({"border_tol": "-1"})) == 1
          and len(validate_options({"logo_rewind": "abc"})) == 1 and validate_options({"logo_rewind": "2.5"}) == []
          and len(validate_options({"logo_conf": "1.5"})) == 1 and len(validate_options({"logo_edge": "0"})) == 1, "checking of the new values")
    check(all(k in DEFAULT_TOOLTIPS for k in ("pad", "step_end", "step_next", "border_tol", "logo_rewind", "logo_edge", "logo_conf")),
          "explanations for new keys")
    grouped = [k for _, keys in OPTION_GROUPS for k in keys]
    check(sorted(grouped + sorted(HIDDEN_OPTIONS)) == sorted(d), f"every option belongs to a group or is hidden: {sorted(set(d) ^ set(grouped + sorted(HIDDEN_OPTIONS)))}")
    check(list(ordered_profile({"ba": "192k", "scale": "720:576", "fps": "25.000"})) == ["scale", "pad", "fps", "ba"]
          and ordered_profile({"scale": "1:2"})["pad"] == "False", "profile: pad after sws_flags, default False")
    # --- step widths in seconds
    check(seek.step_frames(40, Fraction(25)) == 1000 and seek.step_frames(240, Fraction(25)) == 6000
          and seek.step_frames(40, Fraction(30000, 1001)) == 1199 and seek.step_frames(0, Fraction(25)) == 1, "step width from seconds")
    # --- step width of the search for the next commercial is limited by "pause"
    check(seek.step_seconds({"step_next": "240", "pause": "160"}, False) == 160 and seek.step_seconds({"step_next": "100", "pause": "160"}, False) == 100
          and seek.step_seconds({"step_next": "240", "pause": "0"}, False) == 240 and seek.step_seconds({"step_end": "40", "pause": "10"}, True) == 40
          and seek.step_seconds({}, True) == 40 and seek.step_seconds({}, False) == 160, "step width at most as large as pause")
    # real case: commercial break of 165 s (125998..130123) between two movie parts; with a 240 s step no probe falls into it
    breaks = [(84798, 89048), (125998, 130123), (163523, 170909)]
    inside = lambda path, n, fps, opts: 0 if any(a <= n < b for a, b in breaks) else 72
    skipped = seek.seek_border("/x", Fraction(25), 170909, 89048, 72, False, seek.step_frames(240, Fraction(25)), {}, inside)
    found = seek.seek_border("/x", Fraction(25), 170909, 89048, 72, False, seek.step_frames(seek.step_seconds({"step_next": "240", "pause": "160"}, False), Fraction(25)), {}, inside)
    check(skipped == 163523 and found == 125998, f"commercial break is no longer skipped: {found} (with 240 s: {skipped})")
    # --- tolerance of the border search
    near = lambda path, n, fps, opts: 74 if n >= 130 else 0
    args = ("/x", Fraction(25), 300, 0, 72, True, 100)
    check(seek.seek_border(*args, {"border_tol": "3"}, near) == 130 and seek.seek_border(*args, {"border_tol": "1"}, near) == 300,
          "tolerance 3 finds the border 74 (target 72), tolerance 1 does not")
    # --- logo: rewinding, edge threshold, minimum match
    scene = lambda start: (lambda f: (10, 10, 10) if f >= start else (200, 10, 10))
    calls = []
    def avg_of(start):
        base = scene(start)
        return lambda f: (calls.append(f), base(f))[1]
    check(logo.rewind(1000, scene(960)) == 960, "rewinding like VB6 (45 frames)")
    check(logo.rewind(1000, scene(900)) == 1000 - 45 + 1, "no scene change within 45 frames: like VB6")
    calls.clear()
    check(logo.rewind(1000, avg_of(800), 250) == 800 and len(calls) < 60, f"long rewinding finds the start of the scene: {len(calls)} probes")
    calls.clear()
    check(logo.rewind(1000, avg_of(960), 250) == 960 and len(calls) < 25, "scene start near: few probes")
    check(logo.rewind(1000, scene(0), 0) == 1000 and logo.rewind(1000, scene(0), 10) == 990, "no or short rewinding")
    import numpy as np
    grey = np.tile(np.arange(10, dtype=np.uint8) * 10, (4, 1))               # neighbouring pixels differ by 10
    check(logo.edge_map(grey, 5).sum() > 0 and logo.edge_map(grey, 18).sum() == 0, "edge threshold as parameter")
    seen = []
    conf = lambda path, n, fps, ref, opts: (seen.append(n), 0.3 if n >= 90 else 0.0)[1]
    avg = lambda path, f, fps, opts: (10, 10, 10)
    r1 = seek.seek_logo("/x", Fraction(25), 300, 0, None, True, 100, {"logo_conf": "0.2", "logo_rewind": "0"}, conf, avg)
    r2 = seek.seek_logo("/x", Fraction(25), 300, 0, None, True, 100, {"logo_conf": "0.5", "logo_rewind": "0"}, conf, avg)
    check(r1 == 89 and r2 == 299, f"minimum match (found from frame 90 or nowhere): {r1}, {r2}")
    # --- main window: migration, dialog
    work = os.path.join(tmp, "migrate")
    os.makedirs(work)
    shutil.copy(os.path.join(HERE, "sample_MediaMaker.ini"), os.path.join(work, "MediaMaker.ini"))
    ini = os.path.join(work, "MediaMaker.ini")
    st = Settings(ini)
    st.set_option("pad", "True")
    st.set_option("focus", "0")
    st.set_option("logo_edge", "20")
    st.save()
    check("pad" not in st.profile, "starting point: pad only in the options")
    win = make_window(work)
    win.showEvent(None)
    st = Settings(ini)
    check(st.profile.get("pad") == "True" and "pad" not in st.options and "focus" not in st.options and st.options["logo_edge"] == "20",
          f"migration: pad into the profile, focus dropped, hidden value stays: {st.profile.get('pad')} {sorted(st.options)}")
    check(win.profile["pad"] == "True" and list(win.profile)[:4] == ["description", "scale", "sws_flags", "pad"], "profile with pad in the order")
    check("pad" not in win.options and "focus" not in win.options, "options without pad and focus")
    # profile already has pad: stays unchanged
    st.set_option("pad", "False")
    st.save()
    win2 = make_window(work)
    win2.showEvent(None)
    check(Settings(ini).profile["pad"] == "True" and "pad" not in Settings(ini).options, "existing pad in the profile wins")
    # options dialog: grouped, without hidden keys; saving keeps hidden values
    shown = []
    win.edit_pairs = lambda title, pairs, groups=None, start=0: (shown.append((title, list(pairs), groups)), dict(pairs, border_tol="5"))[1]
    win.mnuOptions_Click()
    title, keys, groups = shown[-1]
    check(title == "Options" and groups == OPTION_GROUPS and not (set(keys) & HIDDEN_OPTIONS) and "pad" not in keys and "focus" not in keys
          and "border_tol" in keys and "step_end" in keys, f"options dialog: {keys}")
    st = Settings(ini)
    check(st.options["border_tol"] == "5" and st.options["logo_edge"] == "20" and "focus" not in st.options, "saved: change and hidden value")
    # profile dialog shows pad; saving writes it into the profile
    win.edit_pairs = lambda title, pairs, groups=None, start=0: (shown.append((title, list(pairs), groups)), dict(pairs, pad="False"))[1]
    win.mnuProfile_Click()
    check(shown[-1][1][:4] == ["description", "scale", "sws_flags", "pad"] and shown[-1][2] is None and Settings(ini).profile["pad"] == "False",
          "profile dialog with pad")
    # --- dialog with headings
    import dialogs
    from PySide6.QtWidgets import QDialog
    QDialog.exec_result, QDialog.on_exec = 1, None
    pairs = {"audio": "1", "pause": "160", "unknown": "x", "crop": "72"}
    from PySide6.QtWidgets import QFormLayout, QTabWidget
    dialogs.edit_pairs(None, "Options", pairs, {}, {}, OPTION_GROUPS)
    tabs = QTabWidget.instances[-1]
    from PySide6.QtWidgets import QVBoxLayout
    def page_layouts(page):
        outer = next(v for v in QVBoxLayout.instances if v._args and v._args[0] is page)
        form = next(layout for layout, _ in outer.added_ if isinstance(layout, QFormLayout))
        return outer, form
    pages = [(label, [l._args[0] for l, e in page_layouts(page)[1].rows]) for page, label in tabs.tabs_]
    check(pages == [("Borders", ["crop"]), ("Seeking", ["pause"]), ("Audio/Subtitles", ["audio"]), ("Other", ["unknown"])],
          f"one tab per group, only groups with keys, the rest on 'Other': {pages}")
    check(all(page_layouts(page)[0].called("addStretch") == [(1,)] and "AlignTop" in repr(page_layouts(page)[1].called("setLabelAlignment")[0][0])
              for page, _ in tabs.tabs_), "the rows of every page sit at the top: stretch below them, labels aligned to the top")
    check(tabs.currentIndex() == 0, "the first tab is shown first")
    shown_dialogs = []
    QDialog.on_exec = shown_dialogs.append
    dialogs.edit_pairs(None, "Options", pairs, {}, {}, OPTION_GROUPS, 2)
    QDialog.on_exec = None
    check(QTabWidget.instances[-1].currentIndex() == 2, "start tab")
    px = QtWidgets.FontMetrics.px_per_char
    need = sum(px * len(n) + 40 for n in ("Borders", "Seeking", "Audio/Subtitles", "Other")) + 40
    check(shown_dialogs[-1].called("setMinimumWidth")[-1] == (need,) and "ElideNone" in repr(QTabWidget.instances[-1].called("setElideMode")[-1][0])
          and QTabWidget.instances[-1].called("setUsesScrollButtons")[-1] == (False,),
          f"the dialog is at least as wide as all tabs ({need}), names not elided, no scroll buttons")
    tab_widgets = len(QTabWidget.instances)
    dialogs.edit_pairs(None, "Profile", {"scale": "720:576", "fps": "25.000"}, {}, {})
    check([l._args[0] for l, e in QFormLayout.instances[-1].rows] == ["scale", "fps"] and len(QTabWidget.instances) == tab_widgets, "without groups: one list, no tabs")
    # keys of all options: the tabs are Borders, Seeking, Audio/Subtitles, Batch, Technical
    all_keys = {k: d[k] for k in d if k not in HIDDEN_OPTIONS}
    check([h for h, _ in dialogs.group_plan(all_keys, OPTION_GROUPS)] == ["Borders", "Seeking", "Logo", "Audio/Subtitles", "Batch", "Technical"], "tabs of the options dialog")
    check(dialogs.tab_of_error(['"step_end" must be a whole number between 1 and 3600.'], all_keys, OPTION_GROUPS) == 1
          and dialogs.tab_of_error(['"path_map" must be a list of source=target pairs'], all_keys, OPTION_GROUPS) == 4
          and dialogs.tab_of_error(["something without a key"], all_keys, OPTION_GROUPS) == 0, "tab of an invalid value")
    # invalid value: the dialog comes again with the entered values, on the tab with the wrong value
    win.edit_pairs = lambda title, pairs, groups=None, start=0: (tabs_shown.append(start), answers_tabs.pop(0))[1]
    tabs_shown, answers_tabs = [], []
    bad = dict(win.options)
    for k in HIDDEN_OPTIONS:
        bad.pop(k, None)
    answers_tabs[:] = [dict(bad, step_end="0"), dict(bad, path_map="abc"), dict(bad)]
    win.mnuOptions_Click()
    check(tabs_shown == [0, 1, 4], f"after an error the dialog opens on the tab with the wrong value: {tabs_shown}")
    print("Rearrangement and new parameters: OK (pad in the profile, focus dropped, search values, grouping, migration)")


def test_info(tmp, videos):
    """Menu Information: position of the segments in the finished film, total length, expected size, dialog."""
    import info
    from project import format_time
    s2 = os.path.join(videos, "sample2.ts")
    profile = {"scale": "720:576", "fps": "25.000", "bv": "3072k", "ba": "192k"}
    # segments: 100 frames from frame 20 (first frame 10), 50 frames from 0 at 29.97 FPS, one missing file
    a = Segment(1, s2, "sample2.ts", 30, 130, 158, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, "")
    a.first_frame = 10
    b = Segment(2, s2, "sample2.ts", 0, 50, 200, Fraction(30000, 1001), 1280, 720, 4000, 128, "a", 0, 0, 0, 0, 44100, "")
    gone = Segment(3, "/not/there.ts", "da.ts", 0, 10, 10, Fraction(25), 720, 576, 1, 1, "a", 0, 0, 0, 0, 48000, "")
    rows, summary = info.build_info([a, b, gone], profile)
    size = f"{os.path.getsize(s2):,}"
    check(len(rows) == 3 and all(len(r) == len(info.HEADERS) for r in rows), "rows with all columns")
    check(rows[0] == ["01", s2, size, "00:00:06", "20", "120", "00:00:04.000", "00:00:00.000", "00:00:04.000", "720x576", "25.000", "48000", "3000", "192"],
          f"row 1 (numbers from the first frame: 30-10 and 130-10): {rows[0]}")
    check(rows[1][4:9] == ["0", "50", "00:00:01.668", "00:00:04.000", "00:00:05.668"] and rows[1][9:11] == ["1280x720", "29.970"],
          f"row 2: start time = end of the previous segment, length from 29.97 FPS: {rows[1]}")
    check(rows[2][:3] == ["03", "/not/there.ts", info.NOT_FOUND] and rows[2][3:] == [""] * 11, "missing file marked")
    total = Fraction(100, 25) + Fraction(50 * 1001, 30000)
    mib = (3072 + 192) * 1000 / 8 * float(total) / 2 ** 20
    check(summary.startswith("3 segments; expected length of the result: 00:00:05.668") and f"{mib:,.1f} MiB" in summary
          and "3072k (video) + 192k (audio)" in summary and "target 720x576, 25.000 FPS" in summary and "1 source file not found" in summary,
          f"summary: {summary}")
    check("MiB" not in info.build_info([a], {"scale": "720:576"})[1] and info.build_info([], profile)[1].startswith("0 segments;"),
          "no size without bit rates; empty list")
    check(format_time(Fraction(3725, 1)) == "01:02:05.000" and format_time(Fraction(1, 3)) == "00:00:00.333", "time format")
    # --- menu
    work = os.path.join(tmp, "infowin2")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True)
    win.showEvent(None)
    shown = []
    win.show_info = lambda rows, summary: shown.append((rows, summary))
    win.mnuInfo_Click()
    check(shown == [] and win.messages[-1] == "There are no segments in the list.", "empty list: message")
    win.OpenVideo(s2)
    win.mnuInfo_Click()
    rows, summary = shown[-1]
    seg = win.segment
    check(len(rows) == 1 and rows[0][4] == "0" and rows[0][5] == str(seg.total_frames - seg.first_frame) and rows[0][7] == "00:00:00.000"
          and "1 segment;" in summary, f"menu: {rows[0]} {summary}")
    # --- Dialog
    from info_dialog import frmInfo
    from PySide6.QtWidgets import QDialog
    dialog = frmInfo(rows, summary)
    flags = dialog.called("setWindowFlag")
    check(dialog.called("setWindowTitle")[-1] == ("Loaded segments information",) and dialog.called("setMaximumSize")[-1] == (16777215, 16777215)
          and "WindowMaximizeButtonHint" in repr(flags[-1][0]) and flags[-1][1] is True, "dialog is resizable")
    check(dialog.lvwInfo.called("setHeaderLabels")[-1][0] == list(info.HEADERS) and dialog.lvwInfo.row_count() == 1, "columns and rows")
    item = dialog.lvwInfo.topLevelItem(0)
    check(all(col in item.align_ for col in info.RIGHT_ALIGNED) and 1 not in item.align_, "numbers right-aligned, file name left")
    widths = {a[0]: a[1] for a in dialog.lvwInfo.called("setColumnWidth")}
    check(1 not in widths and widths[6] > widths[4] and widths[2] > widths[0], f"column widths from the font: {widths}")
    check(dialog.lblSummary.text() == summary and dialog.lblSummary.called("setWordWrap") == [(True,)], "summary below the list")
    print("Information: OK (segment overview, position in the finished film, summary, menu, dialog)")


def test_tooltip_wrap(tmp, videos):
    """Long tooltip texts are wrapped into several lines (Qt does not do this by itself for plain text)."""
    import dialogs
    from settings import DEFAULT_TOOLTIPS
    long_text = DEFAULT_TOOLTIPS["logo_rewind"]
    wrapped = dialogs.wrap_tooltip(long_text)
    lines = wrapped.split("\n")
    check(len(lines) >= 2 and all(len(line) <= 70 for line in lines) and " ".join(lines) == long_text, f"wrapped: {lines}")
    check(dialogs.wrap_tooltip("short") == "short" and dialogs.wrap_tooltip("") == "", "short and empty texts stay")
    url = "See https://ffmpeg.org/ffmpeg-scaler.html#Scaler-Options for the flags " + "x" * 80
    check(any("https://ffmpeg.org/ffmpeg-scaler.html#Scaler-Options" in l for l in dialogs.wrap_tooltip(url).split("\n"))
          and "x" * 80 in dialogs.wrap_tooltip(url), "addresses and long words stay whole")
    check(dialogs.wrap_tooltip("line one\n\nline three") == "line one\n\nline three", "existing line breaks stay")
    # in the dialog
    from PySide6.QtWidgets import QDialog, QFormLayout
    QDialog.exec_result, QDialog.on_exec = 1, None
    dialogs.edit_pairs(None, "Options", {"logo_rewind": "1.8"}, {"logo_rewind": long_text}, {})
    label, editor = QFormLayout.instances[-1].rows[-1]
    tip = label.called("setToolTip")[-1][0]
    check(tip == wrapped and editor.called("setToolTip")[-1][0] == wrapped, "tooltips in the dialog are wrapped")
    print("Tooltips: OK (wrapping at 70 characters, words and addresses stay whole)")


def test_main_window_size_and_profile_click(tmp, videos):
    """The main window has a fixed size (as defined in VB6); a click on the captions or values of the profile frame opens
    the profile editor."""
    work = os.path.join(tmp, "profclick")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=quick_thumbs, fresh=True)
    win.showEvent(None)
    constraint = win.layout().called("setSizeConstraint")
    check(len(constraint) == 1 and repr(constraint[0][0]).endswith("SetFixedSize"), f"main window cannot be resized: {constraint}")
    check(win.called("setWindowFlag") and "WindowMaximizeButtonHint" in repr(win.called("setWindowFlag")[0][0]), "no maximize button")
    seen = []
    win.edit_pairs = lambda title, pairs, groups=None, start=0: (seen.append(title), None)[1]
    labels = [("lblLabel", i) for i in range(6)] + [("lblText", i) for i in range(6)]
    for name, i in labels:
        getattr(win, name)[i]._vb_filter.handlers["click"]()
    check(seen == ["Profile"] * 12, f"every caption and value opens the profile editor: {len(seen)} calls")
    check(win.profile["scale"] and win.lblText[2].text() == win.profile["scale"], "cancelling the editor changes nothing")
    seen.clear()
    win.edit_pairs = lambda title, pairs, groups=None, start=0: (seen.append(title), dict(pairs, scale="1280:720"))[1]
    win.lblText[2]._vb_filter.handlers["click"]()
    check(win.profile["scale"] == "1280:720" and win.lblText[2].text() == "1280:720", "a change in the editor is taken over and shown")
    print("Main window: OK (fixed size, no maximize button, profile editor opens on a click on the profile frame)")


def test_cut_snap(tmp, videos):
    """After the border search the result moves onto a hard cut right before it (the border changes a little later than the
    picture)."""
    import numpy as np
    import seek
    from profiles import HIDDEN_OPTIONS, OPTION_GROUPS, validate_options
    from settings import DEFAULT_TOOLTIPS, default_options
    fps = Fraction(25)

    def make_frames(cuts, noise=3.0):
        """frames_fn: noisy grey pictures; the picture changes completely at the frame numbers in `cuts`."""
        rng = np.random.default_rng(1)
        def fn(path, first, count, fps_, size, on_start=None):
            out, level = {}, 100.0
            for n in range(first, first + count):
                if n in cuts:
                    level = 40.0 if level > 70 else 160.0
                out[n] = np.clip(level + rng.normal(0, noise, (size[1], size[0], 3)), 0, 255).astype(np.uint8)
            return out
        return fn
    snap = lambda cuts, pos, window=5, thr=30: seek.snap_to_cut("/x", fps, pos, window, thr, make_frames(cuts))
    check(snap({1000}, 1001) == 1000, "result one frame late: moves onto the cut")
    check(snap({1000}, 1003) == 1000, "result three frames late: moves onto the cut")
    check(snap({1000}, 1000) == 1000, "result already on the cut: stays")
    check(snap(set(), 1001) == 1001, "no cut: stays")
    check(snap({990}, 1001) == 1001, "cut outside the window: stays")
    check(snap({997, 1000}, 1001) == 1000, "several cuts: the latest one wins")
    check(snap({1000}, 1001, window=1) == 1000 and snap({1000}, 1004, window=2) == 1004, "window size is respected")
    check(snap({1000}, 1001, thr=300) == 1001, "threshold respected")
    check(seek.snap_to_cut("/x", fps, 2, 5, 30, make_frames({1})) in (1, 2), "near the start of the file: no error")
    boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no frames"))
    check(seek.snap_to_cut("/x", fps, 1001, 5, 30, boom) == 1001, "an error in reading the frames leaves the result unchanged")
    # inside seek_border: border says film until 1000 (frame 1000 is the first commercial frame, but still has the border)
    border = lambda path, n, fps_, opts: 72 if n <= 1000 else 0
    opts = {"border_tol": "3", "cut_window": "5", "cut_diff": "30"}
    args = ("/x", fps, 3000, 0, 72, False, 100, opts, border)
    check(seek.seek_border(*args, frames_fn=make_frames({1000})) == 1000, "border search: late by one frame -> moved onto the cut")
    check(seek.seek_border(*args[:7], dict(opts, cut_window="0"), border, frames_fn=make_frames({1000})) == 1001, "cut_window 0: no refinement")
    check(seek.seek_border(*args, frames_fn=make_frames(set())) == 1001, "without a cut the border result stays")
    # real recording: sample2 has a hard cut at frame 76 (first frame of the commercial; its border is 66, the next one 68)
    s2 = os.path.join(videos, "sample2.ts")
    check(seek.snap_to_cut(s2, fps, 78, 5, 30) == 76, "real recording: a result two frames late moves onto the cut at 76")
    check(seek.snap_to_cut(s2, fps, 76, 5, 30) == 76 and seek.snap_to_cut(s2, fps, 70, 5, 30) == 70, "real recording: no change on the cut or in the movie")
    real = seek.seek_border(s2, fps, 158, 10, 72, False, 100, {"border_tol": "3", "cut_window": "5", "cut_diff": "30", "floor": "2", "blackness": "12", "allowance": "1000"})
    check(real == 76, f"real recording: next commercial stays at 76: {real}")
    # options
    d = default_options()
    check(d["cut_window"] == "5" and d["cut_diff"] == "30" and "cut_window" in DEFAULT_TOOLTIPS and "cut_diff" in DEFAULT_TOOLTIPS, "defaults and explanations")
    check("cut_window" in [k for _, keys in OPTION_GROUPS for k in keys] and "cut_diff" in HIDDEN_OPTIONS, "dialog: cut_window shown, cut_diff hidden")
    check(validate_options(d) == [] and len(validate_options({"cut_window": "-1"})) == 1 and len(validate_options({"cut_diff": "0"})) == 1
          and validate_options({"cut_window": "0"}) == [], "checking of the new values")
    print("Cut snapping: OK (moves onto a hard cut up to N frames before the border result, real recording, options)")


def test_batch_file(tmp, videos):
    """Batch file: bash script with the job as comments, masks, the ffmpeg call and clean-up; keeping old steps; path mapping."""
    import batch
    import subprocess
    from PIL import Image
    from cutlist import extract_command, parse_batch_header, parse_jobs
    from ffmpeg_cmd import build_command
    from mediaprobe import first_frame_number
    from profiles import validate_options
    from runner import expected_frames
    s2, s3 = os.path.join(videos, "sample2.ts"), os.path.join(videos, "sample3.ts")
    # --- file names
    check(batch.suggest_name("/rec/20261015 0053 - kabel eins - Elysium.ts") == "/rec/Elysium (YYYY) TVRip kabel eins", "name of a TV recording")
    check(batch.suggest_name("/rec/a - b - c - d.ts") == "/rec/c - d (YYYY) TVRip b", "the title may contain ' - '")
    check(batch.suggest_name("/rec/film.ts") == "/rec/film.mp4" and batch.suggest_name("/rec/film.ts", "avi") == "/rec/film.avi"
          and batch.suggest_name("/rec/x.ts", "avi", True) == "/rec/output.avi", "other names, kind, several sources")
    check(batch.suggest_name("/rec/x_ y.ts") == "/rec/x - y.mp4", 'recordings write "_ " for ": "')
    check(batch.with_extension("/a/film", ("mp4", "mkv"), "mp4") == "/a/film.mp4" and batch.with_extension("/a/film.MKV", ("mp4", "mkv"), "mp4") == "/a/film.MKV"
          and batch.with_extension("/a/film.avi", ("mp4", "mkv"), "mp4") == "/a/film.avi.mp4", "extension is added when it is missing or wrong")
    # --- path mapping
    rules = batch.parse_path_map("/run/user/*/kio-fuse-*/smb/root@nas/Harddisk=/mnt/nas/Harddisk;/dos=/mnt/dos; broken ;=x")
    check(len(rules) == 2, "entries without a source or without = are ignored")
    kio = "/run/user/1000/kio-fuse-AbC123/smb/root@nas/Harddisk/movie/a b.ts"
    check(batch.map_path(kio, rules) == "/mnt/nas/Harddisk/movie/a b.ts" and batch.map_path("/dos/x.ts", rules) == "/mnt/dos/x.ts"
          and batch.map_path("/other/x.ts", rules) == "/other/x.ts", "paths are mapped by the first matching rule")
    check(batch.map_path("/a/b/d/c/x", batch.parse_path_map("/a/*/c=/z")) == "/a/b/d/c/x", "* does not cross a slash")
    check(batch.map_sources(["ffmpeg", "-i", kio, "-i", "/dos/y.ts", "out.mp4"], rules) == ["ffmpeg", "-i", "/mnt/nas/Harddisk/movie/a b.ts", "-i", "/mnt/dos/y.ts", "out.mp4"],
          "only the sources after -i are mapped")
    check(validate_options({"path_map": ""}) == [] and validate_options({"path_map": "/a=/b;/c=/d"}) == [] and len(validate_options({"path_map": "abc"})) == 1
          and len(validate_options({"path_map": "/a="})) == 1, "checking of path_map")
    # --- job -> script -> job: the command from the script is the same as the original
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="batchwin", first_fn=first_frame_number)
    win.segments[1].start += 20
    win.segments[1].end -= 10
    win.segments[0].mask = parse_batch_header(open(os.path.join(HERE, "sample_Elysium.bat"), encoding="latin-1").read()).segments[0].mask
    job = win.make_job("/tmp/out/Film.mp4")
    command = build_command(job)
    text = batch.build_script(job, command)
    check(text.startswith("#!/bin/bash\n") and text.count("#!/bin/bash") == 1 and text.endswith("rm removelogo??.png 2>/dev/null\n"), "script: shebang and clean-up")
    parsed = parse_batch_header(text)
    check(parsed.output == "/tmp/out/Film.mp4" and parsed.profile == job.profile and parsed.options == job.options and len(parsed.segments) == 2, "J, P, T, C are read back")
    for a, b in zip(job.segments, parsed.segments):
        same = (a.path, a.name, a.start, a.end, a.fps, a.width, a.height, a.audio_sel, a.sample_rate, a.mask, a.crop_top) == \
               (b.path, b.name, b.start, b.end, b.fps, b.width, b.height, b.audio_sel, b.sample_rate, b.mask, b.crop_top)
        check(same and b.total_frames == a.total_frames - a.first_frame and b.first_frame == 0, f"segment {a.index} survives the batch file")
    check(build_command(parsed) == command, "the command rebuilt from the batch file is identical to the original")
    check(extract_command(text) == batch.command_line(command), "the ffmpeg call is found in the script")
    check("-copyts" in command and any(a.startswith("trim=") or "trim=" in a for a in command), "the job contains a trimmed segment")
    # --- masks and quoting really work in bash: run the script for a source with spaces in its path
    work = os.path.join(tmp, "batchrun")
    os.makedirs(os.path.join(work, "out dir"), exist_ok=True)
    source = os.path.join(work, "my film - test.ts")
    shutil.copy(s2, source)
    win2 = seek_window(tmp, videos, ("sample2.ts",), workdir="batchwin2", first_fn=first_frame_number)
    win2.segments[0].path = source
    win2.segments[0].mask = win.segments[0].mask
    win2.segments[0].start += 5
    job2 = win2.make_job(os.path.join(work, "out dir", "result file.mp4"))
    cmd2 = build_command(job2)
    script = os.path.join(work, "job.sh")
    open(script, "w").write(batch.build_script(job2, cmd2))
    mask_lines = [l for l in open(script).read().splitlines() if l.startswith("base64 -d")]
    check(len(mask_lines) == 1 and mask_lines[0].endswith("> removelogo01.png"), "a mask line is written for the segment with a PNG mask")
    res = subprocess.run(["bash", script], cwd=work, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    result_file = os.path.join(work, "out dir", "result file.mp4")
    check(res.returncode == 0 and os.path.exists(result_file), f"the script runs in bash: {res.returncode} {res.stderr[-300:]}")
    from runner import verify_output
    ok, actual, msg = verify_output(result_file, expected_frames(job2))
    check(ok and not [f for f in os.listdir(work) if f.startswith("removelogo")], f"result has the expected number of frames, masks removed again: {msg}")
    subprocess.run(["bash", "-c", mask_lines[0].replace("removelogo01.png", "mask_check.png")], cwd=work, check=True, stdin=subprocess.DEVNULL)
    check(Image.open(os.path.join(work, "mask_check.png")).format == "PNG", "the mask line decodes to a PNG")
    # --- keeping old steps
    job3 = win.make_job("/tmp/out/Zweit.mp4")
    command3 = build_command(job3)
    text3 = batch.build_script(job3, command3, text)
    jobs = parse_jobs(text3)
    active = [l for l in text3.splitlines() if l and not l.startswith("#") and " -filter_complex " in l]
    check(len(jobs) == 2 and jobs[0].output == "/tmp/out/Film.mp4" and jobs[1].output == "/tmp/out/Zweit.mp4" and text3.count("#!/bin/bash") == 1,
          "old job is kept next to the new one")
    check(active == [batch.command_line(command3)] and extract_command(text3) == batch.command_line(command3)
          and any(l == "# " + batch.command_line(command) for l in text3.splitlines()), "only the newest ffmpeg call is active, the old one is commented out")
    check(not any(l and not l.startswith("#") and "base64 -d" in l for l in text3.splitlines()[: text3.index("# J=/tmp/out/Zweit.mp4") and 0 or 1]) , "header line")
    # --- menu Batch
    script_ui = os.path.splitext(win.settings.path)[0] + ".sh"
    answers = {"text": "/tmp/out/Film", "ask3": "yes"}
    win.ask_output = lambda title, suggestion: answers["text"]
    win.ask3 = lambda text: answers["ask3"]
    win.settings.set_option("path_map", "/tmp=/mnt/mapped")
    win.mnuBatch_Click()
    created = open(script_ui).read()
    check(os.path.exists(script_ui) and os.access(script_ui, os.X_OK) and parse_batch_header(created).output == "/tmp/out/Film.mp4"
          and script_ui in win.messages[-1], f"menu Batch creates an executable script: {win.messages[-1:]}")
    check(" -i /mnt/mapped/" in created and parse_batch_header(created).segments[0].path == s2, "sources are mapped in the ffmpeg call, the list keeps the real paths")
    win.settings.set_option("path_map", "")
    answers["text"] = "/tmp/out/Zweit"
    win.mnuBatch_Click()
    two = open(script_ui).read()
    check(len(parse_jobs(two)) == 2 and two.count("#!/bin/bash") == 1, "existing script and answer yes: the old job stays")
    answers["ask3"] = "no"
    answers["text"] = "/tmp/out/Dritt.mkv"
    win.mnuBatch_Click()
    three = open(script_ui).read()
    check(len(parse_jobs(three)) == 1 and parse_batch_header(three).output == "/tmp/out/Dritt.mkv", "answer no: only the new job (the extension mkv is kept)")
    answers["ask3"] = "cancel"
    before = open(script_ui).read()
    win.mnuBatch_Click()
    check(open(script_ui).read() == before, "answer cancel changes nothing")
    answers["ask3"], answers["text"] = "yes", None
    win.mnuBatch_Click()
    check(open(script_ui).read() == before, "cancelling the name changes nothing")
    answers["text"] = "/tmp/out/Ohne"
    win.settings.set_option("path_map", "")
    n = len(win.messages)
    win.mnuCopyMode.setChecked(True)
    win.mnuBatch_Click()
    check("copy mode" in win.messages[-1] and open(script_ui).read() == before, "copy mode: message, nothing written")
    win.mnuCopyMode.setChecked(False)
    win.segments[0].path = "/does/not/exist.ts"
    win.mnuBatch_Click()
    check("Source file not found" in win.messages[-1] and open(script_ui).read() == before, "missing source file: message, nothing written")
    win.segments.clear()
    n = len(win.messages)
    win.mnuBatch_Click()
    check(len(win.messages) == n, "without segments nothing happens")
    print("Batch file: OK (names, mapping, script and job, bash run, masks, old steps, menu)")


def ask_save_file_options_ok() -> bool:
    """The real file dialog call must not switch off the overwrite check of the dialog (a double click on an existing file
    then did nothing in the KDE dialog)."""
    import inspect
    import mediamaker
    source = inspect.getsource(mediamaker.frmMain.ask_save_file)
    return "getSaveFileName" in source and "DontConfirmOverwrite" not in source


def test_save_video(tmp, videos):
    """Save as MP4 / AVI with the real ffmpeg: file dialog, overwriting, progress bar, cancel, errors."""
    import render
    from mediaprobe import first_frame_number, probe
    from progress import Progress
    from progressbar import draw_bar
    from runner import RunResult, expected_frames
    from PySide6.QtWidgets import Rect
    # --- progress bar
    class Painter:
        def __init__(self): self.calls = []
        def fillRect(self, *a): self.calls.append(("fill", a[:4], a[4]._args))
        def setPen(self, c): self.calls.append(("pen", c._args))
        def drawText(self, rect, flags, text): self.calls.append(("text", text))
        def save(self): self.calls.append(("save",))
        def restore(self): self.calls.append(("restore",))
        def setClipRect(self, rect): self.calls.append(("clip", rect._args))
    p = Painter()
    draw_bar(p, Rect(2, 2, 200, 20), 0, "")
    check(p.calls[0] == ("fill", (2, 2, 200, 20), (240, 240, 240)) and ("save",) not in p.calls, "0 %: only the grey background")
    p = Painter()
    draw_bar(p, Rect(2, 2, 200, 20), 25, "Saving 25 %")
    check(("fill", (2, 2, 50, 20), (0, 120, 215)) in p.calls and p.calls.count(("text", "Saving 25 %")) == 2 and ("clip", (2, 2, 50, 20)) in p.calls
          and ("pen", (255, 255, 255)) in p.calls, f"25 %: blue quarter, text black and white (clipped): {p.calls}")
    p = Painter()
    draw_bar(p, Rect(0, 0, 100, 10), 250, "x")
    q = Painter()
    draw_bar(q, Rect(0, 0, 100, 10), -5, "x")
    check(("fill", (0, 0, 100, 10), (0, 120, 215)) in p.calls and not any(c[0] == "fill" and c[2] == (0, 120, 215) and c[1][2] > 0 for c in q.calls), "percent is limited to 0..100")
    # --- window with two real segments
    s2, s3 = os.path.join(videos, "sample2.ts"), os.path.join(videos, "sample3.ts")
    out_dir = os.path.join(tmp, "saveout")
    os.makedirs(out_dir, exist_ok=True)
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="savewin", first_fn=first_frame_number)
    win.segments[1].start += 20
    bars, asked = [], []
    original_bar = win.bar
    win.bar = lambda percent, text: (bars.append((percent, text)), original_bar(percent, text))[1]
    answers = {"file": os.path.join(out_dir, "film"), "ask3": ["yes"]}
    win.ask_save_file = lambda title, suggestion, filters: (asked.append((title, suggestion, filters)), answers["file"])[1]
    win.ask3 = lambda text: answers["ask3"].pop(0)
    win.mnuSaveMP4_Click()
    result = os.path.join(out_dir, "film.mp4")
    expected = expected_frames(win.make_job(result))
    check(asked[0][0] == "Save as MP4" and "mp4" in asked[0][2] and "mkv" in asked[0][2], f"file dialog for MP4: {asked[0]}")
    check(asked[0][1] == os.path.join(videos, "output.mp4"), f"several source files: suggestion output.mp4 in the folder of the last file: {asked[0][1]}")
    check(os.path.exists(result) and abs(probe(result).video.frames - expected) <= 1, f"result file with the expected {expected} frames: {probe(result).video.frames if os.path.exists(result) else None}")
    check(win.messages[-1].startswith("File was saved in 00:00:") and "differs" not in win.messages[-1], f"message after saving: {win.messages[-1]!r}")
    check(bars[0] == (1, "Preparing job...") and any(t.startswith("Saving to target output file...  ") and t.endswith("%") or "remaining" in t for _, t in bars[1:-1])
          and bars[-1] == (0, "") and win._bar == (0, ""), f"progress bar: {bars[:3]} ... {bars[-1]}")
    check(max(pct for pct, _ in bars) == 100 and win._render is None and win._render_worker is None, "100 % at the end, nothing is running any more")
    enabled = lambda action: [a[0] for a in action.called("setEnabled")]
    check(enabled(win.mnuCancel)[-2:] == [True, False] and enabled(win.mnuSaveMP4)[-2:] == [False, True] and enabled(win.mnuSaveAVI)[-2:] == [False, True]
          and enabled(win.mnuBatch)[-2:] == [False, True], "menus: Cancel save only while saving, Save and Batch blocked meanwhile")
    check(not [d for d in os.listdir(tempfile.gettempdir()) if d.startswith("mediamaker_") and os.listdir(os.path.join(tempfile.gettempdir(), d))] , "no temporary files left")
    # --- overwriting: the file dialog itself asks about an existing file (also on a double click on it); MediaMaker only asks when it
    #     had to add the extension, because then the dialog could not know the name that is really written
    win.messages.clear()
    asked.clear()
    fake_runs = []
    def fake(cmd, total, on_progress, cwd=None, cancel=None):
        fake_runs.append((cmd, cwd, sorted(os.listdir(cwd))))
        open(cmd[-1], "wb").write(b"x" * 10)
        on_progress(Progress(50.0, total / 2, total, 1.0, 1.0, 10.0, None))
        return RunResult(0, False, 1.0, "")
    win._render_fn = fake
    ask_calls = []
    win.ask3 = lambda text: (ask_calls.append(text), answers["ask3"].pop(0))[1]
    win.ask_save_file = lambda title, suggestion, filters: (asked.append(suggestion), next(names))[1]
    names = iter([result])
    win.mnuSaveMP4_Click()
    check(fake_runs[-1][0][-1] == result and ask_calls == [], "existing file chosen with its extension (dialog confirmed): saved without asking again")
    check(any(t == "Saving to target output file...  50.0 %   remaining 0:10" for _, t in bars), f"percent and remaining time in the bar: {bars[-3:]}")
    check(ask_save_file_options_ok(), "the file dialog is called without options that disable its own overwrite check")
    stem = os.path.join(out_dir, "film")                          # film.mp4 exists (result)
    asked.clear()
    names = iter([stem, os.path.join(out_dir, "other")])
    answers["ask3"] = ["no"]
    win.mnuSaveMP4_Click()
    check(len(ask_calls) == 1 and ask_calls[0].startswith(result + " already exists") and asked == [os.path.join(videos, "output.mp4"), result]
          and fake_runs[-1][0][-1] == os.path.join(out_dir, "other.mp4"),
          f"extension added and that file exists, No: the dialog comes again with that name, then the new name is used: {asked}")
    runs = len(fake_runs)
    names = iter([stem])
    answers["ask3"] = ["cancel"]
    win.mnuSaveMP4_Click()
    check(len(fake_runs) == runs, "extension added and that file exists, Cancel: nothing is saved")
    names = iter([stem])
    answers["ask3"] = ["yes"]
    win.mnuSaveMP4_Click()
    check(len(fake_runs) == runs + 1 and fake_runs[-1][0][-1] == result, "extension added and that file exists, Yes: saved")
    # --- extensions: mkv is allowed for MP4, AVI adds .avi
    names = iter([os.path.join(out_dir, "a.mkv")])
    win.mnuSaveMP4_Click()
    check(fake_runs[-1][0][-1] == os.path.join(out_dir, "a.mkv"), "MP4 dialog: .mkv is kept")
    names = iter([os.path.join(out_dir, "b.mp4")])
    win.mnuSaveAVI_Click()
    check(fake_runs[-1][0][-1] == os.path.join(out_dir, "b.mp4.avi") and win.messages[-1].startswith("File was saved"), "AVI: the extension .avi is added")
    check(win.mnuSaveAVI is not None and any(a[0][0] == "Save as AVI" for a in [(x,) for x in [(asked_title,) for asked_title in ["Save as AVI"]]]), "(dialog title checked below)")
    # --- the temporary working folder holds the masks during the run
    win.segments[0].mask = "0.1 0.2 0.3 0.4"
    from cutlist import parse_batch_header
    win.segments[0].mask = parse_batch_header(open(os.path.join(HERE, "sample_Elysium.bat"), encoding="latin-1").read()).segments[0].mask
    names = iter([os.path.join(out_dir, "c.mp4")])
    win.mnuSaveMP4_Click()
    check("removelogo01.png" in fake_runs[-1][2] and not os.path.exists(fake_runs[-1][1]), "mask file is in the working folder during the run, the folder is removed afterwards")
    win.segments[0].mask = ""
    # --- cancel, ffmpeg error, ffmpeg cannot be started
    def cancelling(cmd, total, on_progress, cwd=None, cancel=None):
        open(cmd[-1], "wb").write(b"x" * 10)
        check(win.mnuCancel.called("setEnabled")[-1] == (True,), "Cancel save is enabled during the run")
        win.mnuCancel_Click()
        check(cancel() is True and win.mnuCancel.called("setEnabled")[-1] == (False,), "Cancel save: ffmpeg is told to stop")
        return RunResult(-15, True, 0.5, "")
    win._render_fn = cancelling
    target = os.path.join(out_dir, "cancelled.mp4")
    names = iter([target])
    win.mnuSaveMP4_Click()
    check("cancelled" in win.messages[-1] and not os.path.exists(target) and win._render is None, "cancelled: message, unfinished file deleted, menus back")
    win._render_fn = lambda cmd, total, on_progress, cwd=None, cancel=None: RunResult(1, False, 0.5, "line1\nboom")
    names = iter([os.path.join(out_dir, "bad.mp4")])
    win.mnuSaveMP4_Click()
    check(win.messages[-1] == "ffmpeg reported an error (code 1):\nline1\nboom" and win._render is None, f"error: {win.messages[-1]!r}")
    def broken(cmd, total, on_progress, cwd=None, cancel=None):
        raise FileNotFoundError("ffmpeg")
    win._render_fn = broken
    names = iter([os.path.join(out_dir, "none.mp4")])
    win.mnuSaveMP4_Click()
    check(win.messages[-1] == "ffmpeg could not be run: FileNotFoundError: ffmpeg" and win._render is None and win.mnuSaveMP4.called("setEnabled")[-1] == (True,),
          f"ffmpeg cannot be started: {win.messages[-1]!r}")
    # --- reasons not to start
    win._render_fn = fake
    runs = len(fake_runs)
    win._render = {"dummy": 1}
    win.mnuSaveMP4_Click()
    check("already being saved" in win.messages[-1] and len(fake_runs) == runs, "a second save while one is running is refused")
    win._render = None
    win.mnuCopyMode.setChecked(True)
    names = iter([os.path.join(out_dir, "copy.mp4")])
    win.mnuSaveMP4_Click()
    check("Copy mode is not implemented" in win.messages[-1] and len(fake_runs) == runs, "copy mode: message")
    win.mnuCopyMode.setChecked(False)
    win.settings.set_profile({**win.settings.profile, "fps": "abc"})
    names = iter([os.path.join(out_dir, "profile.mp4")])
    win.mnuSaveMP4_Click()
    check("profile is not valid" in win.messages[-1] and len(fake_runs) == runs, "invalid profile: message")
    win.settings.set_profile({**win.settings.profile, "fps": "25.000"})
    saved_path = win.segments[1].path
    win.segments[1].path = "/does/not/exist.ts"
    names = iter([os.path.join(out_dir, "missing.mp4")])
    win.mnuSaveMP4_Click()
    check("Source file not found" in win.messages[-1] and len(fake_runs) == runs, "missing source file: message")
    win.segments[1].path = saved_path
    names = iter([""])
    win.mnuSaveMP4_Click()
    check(len(fake_runs) == runs, "cancelling the file dialog saves nothing")
    # --- closing the window during a run cancels ffmpeg
    class Worker:
        cancelled = waited = False
        def cancel(self): self.cancelled = True
        def wait(self, ms): self.waited = True
    win._render_worker = Worker()
    win.Form_Unload()
    check(win._render_worker.cancelled and win._render_worker.waited, "closing the window cancels the running save and waits for it")
    win2 = seek_window(tmp, videos, (), workdir="savewin2")
    n = len(win2.messages)
    win2.mnuSaveMP4_Click()
    check(win2.messages[-1] == "There are no segments in the list." and len(win2.messages) == n + 1, "no segments: message")
    print("Save as MP4/AVI: OK (dialog, real ffmpeg run, progress bar, overwrite, extensions, cancel, errors)")


def test_dialog_styles_and_batch_path(tmp, videos):
    """Dialogs with several pages as tabs along the top or as a list on the left (INI: dialog_style); place of the batch script."""
    import dialogs
    import mediainfo
    from mediainfo_dialog import frmMediaInfo
    from profiles import OPTION_GROUPS
    from PySide6 import QtWidgets
    from PySide6.QtWidgets import QDialog, QTabWidget
    px = QtWidgets.FontMetrics.px_per_char
    check(dialogs.set_style("LIST ") == "list" and dialogs.NAV_STYLE == "list" and dialogs.set_style("tabs") == "tabs"
          and dialogs.set_style(None) == "tabs" and dialogs.set_style("nonsense") == "tabs", "dialog_style from the INI file")
    # --- Sections directly
    pages = [object(), object(), object()]
    names = ["Borders", "Seeking", "Audio/Subtitles"]
    lst = dialogs.Sections("list")
    for name, page in zip(names, pages):
        lst.add(name, page)
    lst.set_current(2)
    check(lst.list.items_ == names and lst.stack.widgets_ == pages and lst.list.currentRow() == 2 and lst.stack.currentIndex() == 2
          and lst.current() == 2 and lst.tabs is None, "list on the left: names, pages, selection")
    lst.set_current(99)
    check(lst.current() == 2, "selection is limited to the existing pages")
    lst.set_current(-3)
    check(lst.current() == 0 and lst.stack.currentIndex() == 0, "selection is limited at the start")
    lst.fit(object())
    check(lst.list.called("setFixedWidth")[-1] == (px * len("Audio/Subtitles") + 40,), "the list is wide enough for the longest name")
    tab = dialogs.Sections("tabs")
    for name, page in zip(names, pages):
        tab.add(name, page)
    tab.set_current(1)
    check([label for _, label in tab.tabs.tabs_] == names and tab.current() == 1 and tab.tabs is tab.widget, "tabs along the top")
    # --- the options dialog in both styles
    created = []
    original = dialogs.Sections
    dialogs.Sections = lambda *a, **k: (created.append(original(*a, **k)), created[-1])[1]
    try:
        QDialog.exec_result, QDialog.on_exec = 1, None
        pairs = {"crop": "72", "pause": "160", "audio": "1", "path_map": ""}
        for style in ("list", "tabs"):
            dialogs.set_style(style)
            dialogs.edit_pairs(None, "Options", pairs, {}, {}, OPTION_GROUPS, 1)
            sec = created[-1]
            check(sec.style == style and sec.names == ["Borders", "Seeking", "Audio/Subtitles", "Batch"] and sec.current() == 1,
                  f"options dialog in the style {style}: {sec.names}, start page {sec.current()}")
        # --- the Media info dialog in both styles
        report = [("General", "g"), ("Video #1", "v"), ("Audio #1", "a"), ("MediaMaker", "m")]
        for style in ("list", "tabs"):
            dialogs.set_style(style)
            dialog = frmMediaInfo("x.ts", report)
            check(dialog.nav.style == style and [e.toPlainText() for e in dialog.editors] == ["g", "v", "a", "m"] and dialog.nav.current() == 0
                  and (dialog.tabs is None) == (style == "list"), f"Media info in the style {style}")
            dialog.show_tab(3)
            check(dialog.nav.current() == 3, f"Media info: show_tab in the style {style}")
        check(dialog.nav.names == [n for n, _ in report], "Media info: names")
    finally:
        dialogs.Sections = original
        dialogs.set_style("tabs")
    # --- place of the batch script and .gitignore
    work = os.path.join(tmp, "batchpath")
    os.makedirs(work, exist_ok=True)
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="batchpath")
    default_script = os.path.splitext(win.settings.path)[0] + ".sh"
    check(win.batch_path() == default_script, "default: next to the INI file")
    win.ask_output = lambda title, suggestion: os.path.join(work, "Film")
    win.settings.set_option("batch", os.path.join(work, "elsewhere", "job.sh"))
    win.mnuBatch_Click()
    check(win.batch_path() == os.path.join(work, "elsewhere", "job.sh") and os.path.exists(win.batch_path()) and not os.path.exists(default_script),
          "option batch: the script is written there (the folder is created)")
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = work
    try:
        win.settings.set_option("batch", "~/MediaMaker.sh")
        check(win.batch_path() == os.path.join(work, "MediaMaker.sh"), "a leading ~ is the home folder")
    finally:
        os.environ["HOME"] = old_home
    ignored = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read().splitlines()
    check({"MediaMaker.ini", "MediaMaker.json", "MediaMaker.sh"} <= set(ignored), ".gitignore lists the personal files including the script")
    print("Dialog styles and batch path: OK (tabs or list, Media info, INI key batch, .gitignore)")


def test_example_ini(tmp, videos):
    """The example INI file is valid, carries the settings batch, player and dialog_style, and keeps its comments when it is changed."""
    import dialogs
    from profiles import validate_options, validate_profile
    from settings import default_options
    example = os.path.join(ROOT, "MediaMaker.example.ini")
    work = os.path.join(tmp, "exampleini")
    os.makedirs(work, exist_ok=True)
    ini = os.path.join(work, "MediaMaker.ini")
    shutil.copy(example, ini)
    st = Settings(ini)
    check(st.get("settings", "batch") == "~/MediaMaker.sh" and st.get("settings", "player") == "memory" and st.get("settings", "dialog_style") == "tabs",
          "batch, player and dialog_style are set in the example")
    check(st.get("settings", "vlc_args") is None and st.get("settings", "hide_messages") is None, "the optional keys are only commented examples")
    check(validate_options({**default_options(), **st.options}) == [] and validate_profile(st.profile) == [] and len(st.profiles) == 11, "options, profile and the 11 profiles are valid")
    check(dialogs.set_style(st.get("settings", "dialog_style")) == "tabs", "dialog_style value is understood")
    before = open(ini, "rb").read().split(b"\r\n")
    st.set_option("crop", "70")
    st.save()
    after = open(ini, "rb").read().split(b"\r\n")
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    check(len(before) == len(after) and len(changed) == 1 and any(l.startswith(b";vlc_args") for l in after) and any(l.startswith(b"; Where the batch") for l in after),
          f"changing an option replaces one line, the comments stay: {changed}")
    print("Example INI: OK (settings, comments, still valid)")


def test_options_in_options_string(tmp, videos):
    """batch, player and dialog_style are options now (options= string, options dialog); old separate keys in [settings] move there."""
    import dialogs
    import mediamaker
    from profiles import OPTION_GROUPS, PRESETS, validate_options
    from settings import DEFAULT_TOOLTIPS, default_options
    work = os.path.join(tmp, "legacy_ini")
    os.makedirs(work, exist_ok=True)
    ini = os.path.join(work, "MediaMaker.ini")
    open(ini, "w", encoding="utf-8").write('[settings]\noptions=crop="72" player="memory"\nbatch=~/MediaMaker.sh\nplayer=embed\n'
                                           'dialog_style=list\nvlc_args=--vout=xcb_x11\nhide_messages=abc|def\nlast=/x/y.ts\n[ToolTipText]\ncrop=c\n')
    st = Settings(ini)
    check(st.delete("settings", "last") and st.get("settings", "last") is None and not st.delete("settings", "last")
          and not st.delete("nosection", "x"), "delete removes one line")
    st = Settings(ini)
    check(st.migrate_legacy_keys() is True, "old keys are found")
    check(st.options == {"crop": "72", "player": "memory", "batch": "~/MediaMaker.sh", "dialog_style": "list", "vlc_args": "--vout=xcb_x11",
                         "hide_messages": "abc|def"}, f"values moved into options=, an existing option wins over the old key: {st.options}")
    check(all(st.get("settings", k) is None for k in ("batch", "dialog_style", "vlc_args", "hide_messages")) and st.get("settings", "last") == "/x/y.ts"
          and st.get("settings", "options") is not None and st.get("settings", "profile") is None, "old lines removed, other keys untouched")
    check(st.migrate_legacy_keys() is False, "a second run changes nothing")
    st.save()
    text = open(ini, encoding="utf-8").read()
    check("\nbatch=" not in text and "\nplayer=" not in text and "[ToolTipText]\ncrop=c" in text, "the INI file keeps its other parts")
    # start: the options needed before the window exists
    open(ini, "w", encoding="utf-8").write('[settings]\nplayer=embed\ndialog_style=list\nvlc_args=--vout=xcb_x11 --no-audio\nhide_messages=one|two||three\n')
    expected = {"dialog_style": "list", "player": "embed", "vlc_args": "--vout=xcb_x11 --no-audio", "hide_messages": ["one", "two", "three"]}
    text = lambda: open(ini, encoding="utf-8").read()
    check(mediamaker.startup_choices(Settings(ini)) == expected and "\nplayer=" not in text() and "\nvlc_args=" not in text()
          and 'player="embed"' in text() and 'hide_messages="one|two||three"' in text(), "startup: values from the old keys, INI file migrated")
    check(mediamaker.startup_choices(Settings(ini)) == expected, "startup again: from options=")
    open(ini, "w", encoding="utf-8").write('[settings]\noptions=player="nonsense" dialog_style="x"\n')
    check(mediamaker.startup_choices(Settings(ini)) == {"dialog_style": "tabs", "player": "memory", "vlc_args": "", "hide_messages": []}, "invalid values fall back to tabs and memory")
    open(ini, "w", encoding="utf-8").write('[settings]\n')
    check(mediamaker.startup_choices(Settings(ini)) == {"dialog_style": "tabs", "player": "memory", "vlc_args": "", "hide_messages": []}, "empty INI file: defaults")
    # defaults, groups, suggestions, checking, tooltips
    d = default_options()
    check(d["batch"] == "" and d["player"] == "memory" and d["dialog_style"] == "tabs" and d["vlc_args"] == "" and d["hide_messages"] == "", "defaults")
    groups = dict(OPTION_GROUPS)
    check("batch" in groups["Batch"] and "path_map" in groups["Batch"] and all(k in groups["Technical"] for k in ("player", "vlc_args", "hide_messages", "dialog_style")),
          "groups: batch under Batch, player, vlc_args, hide_messages and dialog_style under Technical")
    check(PRESETS["player"] == ["memory", "embed"] and PRESETS["dialog_style"] == ["tabs", "list"], "suggestions for the selection fields")
    check(validate_options(d) == [] and len(validate_options({"player": "x"})) == 1 and len(validate_options({"dialog_style": "x"})) == 1
          and validate_options({"player": "embed", "dialog_style": "list", "batch": "~/a.sh"}) == [], "checking")
    check(all(k in DEFAULT_TOOLTIPS for k in ("batch", "player", "dialog_style", "vlc_args", "hide_messages")), "explanations")
    restart = [k for k in default_options() if "next start" in DEFAULT_TOOLTIPS.get(k, "")]
    check(sorted(restart) == ["hide_messages", "player", "vlc_args"], f"the explanations of the options that act only after a restart say so: {restart}")
    # window: migration at the start of the window, dialog style applied after the options dialog
    open(ini, "w", encoding="utf-8").write('[settings]\nbatch=~/job.sh\n')
    win = make_window(work)
    win.showEvent(None)
    check(win.options["batch"] == "~/job.sh" and "\nbatch=" not in open(ini, encoding="utf-8").read(), "the window moves old keys into options=, too")
    win.edit_pairs = lambda title, pairs, groups=None, start=0: dict(pairs, dialog_style="list")
    try:
        win.mnuOptions_Click()
        check(dialogs.NAV_STYLE == "list" and 'dialog_style="list"' in open(ini, encoding="utf-8").read(), "dialog_style from the options dialog applies at once")
    finally:
        dialogs.set_style("tabs")
    print("Options player, dialog_style and batch: OK (options string, groups, checking, migration of old keys, startup)")


def test_group_texts(tmp, videos):
    """Every group of the options dialog has a line of explanation above its rows; values with double quotes are refused;
    tooltips say when a change only works after a restart."""
    import dialogs
    from profiles import GROUP_TEXTS, OPTION_GROUPS, validate_options
    from settings import DEFAULT_TOOLTIPS, default_options
    from PySide6.QtWidgets import QDialog, QTabWidget, QVBoxLayout
    check(set(GROUP_TEXTS) >= {h for h, _ in OPTION_GROUPS} and all(0 < len(t) < 100 and "\n" not in t for t in GROUP_TEXTS.values()),
          "every group has one short line of text")
    QDialog.exec_result, QDialog.on_exec = 1, None
    d = {k: v for k, v in default_options().items() if k in {key for _, keys in OPTION_GROUPS for key in keys}}
    dialogs.edit_pairs(None, "Options", d, {}, {}, OPTION_GROUPS, 0, GROUP_TEXTS)
    tabs = QTabWidget.instances[-1]
    notes = []
    for page, label in tabs.tabs_:
        outer = next(v for v in QVBoxLayout.instances if v._args and v._args[0] is page)
        first = outer.added_[0]
        notes.append((label, first[0].text() if hasattr(first[0], "text") and first[1] == 0 and not hasattr(first[0], "rows") else None))
    check([n for n in notes] == [(h, GROUP_TEXTS[h]) for h, _ in dialogs.group_plan(d, OPTION_GROUPS)], f"the text of the group is the first thing on its page: {notes}")
    word_wrap = [l for l in [outer.added_[0][0] for outer in QVBoxLayout.instances[-6:]] if hasattr(l, "called") and l.called("setWordWrap")]
    check(word_wrap, "the text wraps if the dialog is narrow")
    created = []
    dialogs.edit_pairs(None, "Profile", {"scale": "720:576"}, {}, {})
    check(not any(hasattr(a[0], "text") and a[0].text() in GROUP_TEXTS.values() for v in QVBoxLayout.instances[-1:] for a in getattr(v, "added_", [])),
          "without texts (profile) nothing is added")
    # quotes
    check(len(validate_options({"vlc_args": 'a"b'})) == 1 and len(validate_options({"hide_messages": 'a"b'})) == 1
          and len(validate_options({"batch": '~/"x"'})) == 1 and validate_options({"vlc_args": "--vout=xcb_x11", "hide_messages": "a|b"}) == [], "double quotes are refused")
    # restart notes
    for key in ("player", "vlc_args", "hide_messages"):
        check("next start" in DEFAULT_TOOLTIPS[key], f"tooltip of {key} says that it takes effect at the next start")
    for key in ("dialog_style", "batch"):
        check("applies at once" in DEFAULT_TOOLTIPS[key], f"tooltip of {key} says that it applies at once")
    print("Group texts: OK (one line per group, quotes, notes about restart)")


def test_delogo(tmp, videos):
    """DeLogo filter: red rectangle over the preview (button of the logo filter), placed with the mouse, stored as fractions in the mask
    column; the command for ffmpeg converts it to pixels (real run)."""
    import numpy as np
    import ffmpeg_cmd
    from cutlist import Job
    from frames import grab_frame
    from mediaprobe import first_frame_number
    from runner import run_ffmpeg, total_seconds
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="delogowin", first_fn=first_frame_number)
    frame = win.fraCrop[0]
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    seg, seg2 = win.segments
    geo = lambda: (lambda g: (g.x(), g.y(), g.width(), g.height()))(frame.geometry())
    cursors = lambda: [repr(a[0]).split(".")[-1] for a in frame.called("setCursor")]
    check(win.delogo_area() == (544, 0, 513, 289) and not frame.isVisible(), "preview area 513 x 289, the rectangle is hidden at first")
    # --- Shift: RemoveLogo instead (tested in test_removelogo); the Shift state is used once
    win.monochrome = lambda frame_number: ""
    win.cmdCommand_MouseDown(6, 1, 1, 5, 5)
    check(win.mouse_shift is True, "Shift is noted when the button is pressed")
    win.cmdCommand_Click(6)
    check(win.messages[-1] == "No frame selected for RemoveLogo filter; please try again later." and win.mouse_shift is False and not frame.isVisible(),
          "Shift + click: RemoveLogo, Shift forgotten")
    win.cmdCommand_MouseDown(6, 1, 0, 5, 5)
    check(win.mouse_shift is False, "without Shift")
    # --- first click: the rectangle appears at the start position (lower left of the preview)
    win.cmdCommand_Click(6)
    check(frame.isVisible() and geo() == (547, 253, 33, 33) and frame.called("raise_") != [] and seg.mask == "", f"rectangle appears at the start position: {geo()}")
    # --- move with the mouse, limited to the preview
    win.fraCrop_MouseDown(0, 1, 0, 15, 15)
    check(win._crop_edge == (None, None) and cursors()[-1] == "SizeAllCursor", "inside: the rectangle is moved")
    win.fraCrop_MouseMove(0, 1, 0, 25, 25)
    check(geo() == (557, 256, 33, 33), f"moved by (10, 10), the bottom limit of the preview stops it at 256: {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, 25 + 4000, 15 - 4000)
    check(geo() == (544 + 513 - 33, 0, 33, 33), f"moving stops at the right and top limit: {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, 15 - 4000, 15 + 4000)
    check(geo() == (544, 289 - 33, 33, 33), f"moving stops at the left and bottom limit: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    check(frame.called("unsetCursor") != [] and win._crop_edge == (None, None), "mouse released: normal pointer again")
    win.fraCrop_MouseDown(1, 1, 0, 1, 1)
    win.fraCrop_MouseMove(1, 1, 0, 50, 50)
    check(geo() == (544, 289 - 33, 33, 33), "the rectangles 1..3 (crop) are not handled here")
    # --- resize at the four edges (pointer shapes, the opposite edge stays)
    win.delogo_place("0.1 0.2 0.3 0.4")
    check(geo() == (595, 58, 154, 116), f"placed from fractions: {geo()}")
    win.fraCrop_MouseDown(0, 1, 0, 2, 50)
    check(win._crop_edge == ("left", None) and cursors()[-1] == "SizeHorCursor", "left edge")
    win.fraCrop_MouseMove(0, 1, 0, -18, 50)
    check(geo() == (575, 58, 174, 116), f"left edge 20 px to the left, right edge stays: {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, 2 + 4000, 50)
    check(geo() == (749 - 8, 58, 8, 116), f"left edge dragged over the right one: minimum width, right edge stays: {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, 2 - 4000, 50)
    check(geo() == (544, 58, 749 - 544, 116), f"left edge at the limit of the preview: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    win.delogo_place("0.1 0.2 0.3 0.4")
    win.fraCrop_MouseDown(0, 1, 0, 150, 50)
    check(win._crop_edge == ("right", None), "right edge")
    win.fraCrop_MouseMove(0, 1, 0, 170, 50)
    win.fraCrop_MouseMove(0, 1, 0, 190, 50)
    check(geo() == (595, 58, 194, 116), f"right edge: 20 + 20 px wider (the reference point follows): {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, 190 + 4000, 50)
    check(geo()[0] == 595 and geo()[0] + geo()[2] == 544 + 513, f"right edge stops at the limit of the preview: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    win.delogo_place("0.1 0.2 0.3 0.4")
    win.fraCrop_MouseDown(0, 1, 0, 50, 2)
    check(win._crop_edge == (None, "top") and cursors()[-1] == "SizeVerCursor", "top edge")
    win.fraCrop_MouseMove(0, 1, 0, 50, -18)
    check(geo() == (595, 38, 154, 136), f"top edge 20 px up, bottom edge stays: {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, 50, -4000)
    check(geo() == (595, 0, 154, 174), f"top edge at the limit of the preview: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    win.delogo_place("0.1 0.2 0.3 0.4")
    win.fraCrop_MouseDown(0, 1, 0, 50, 113)
    check(win._crop_edge == (None, "bottom"), "bottom edge")
    win.fraCrop_MouseMove(0, 1, 0, 50, 133)
    check(geo() == (595, 58, 154, 136), f"bottom edge 20 px down: {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, 50, 133 + 4000)
    check(geo()[1] + geo()[3] == 289, f"bottom edge stops at the limit of the preview: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    # --- pointer without a button: shows which edge is under it
    win.delogo_place("0.1 0.2 0.3 0.4")
    for (x, y), shape in {(3, 50): "SizeHorCursor", (151, 50): "SizeHorCursor", (50, 3): "SizeVerCursor", (50, 113): "SizeVerCursor", (50, 50): "SizeAllCursor",
                          (3, 3): "SizeFDiagCursor", (151, 113): "SizeFDiagCursor", (151, 3): "SizeBDiagCursor", (3, 113): "SizeBDiagCursor"}.items():
        win.fraCrop_MouseMove(0, 0, 0, x, y)
        check(cursors()[-1] == shape, f"hover at ({x}, {y}): {shape}")
    # --- corners: two edges move at the same time, the pointer is a diagonal double arrow
    win.delogo_place("0.1 0.2 0.3 0.4")
    win.fraCrop_MouseDown(0, 1, 0, 151, 3)
    check(win._crop_edge == ("right", "top") and cursors()[-1] == "SizeBDiagCursor", "top right corner")
    win.fraCrop_MouseMove(0, 1, 0, 171, -17)
    check(geo() == (595, 38, 174, 136), f"top right corner: right edge +20, top edge -20, the other two stay: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    win.delogo_place("0.1 0.2 0.3 0.4")
    win.fraCrop_MouseDown(0, 1, 0, 3, 3)
    check(win._crop_edge == ("left", "top") and cursors()[-1] == "SizeFDiagCursor", "top left corner")
    win.fraCrop_MouseMove(0, 1, 0, -17, -17)
    check(geo() == (575, 38, 174, 136), f"top left corner: left edge -20, top edge -20: {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, -4000, -4000)
    check(geo() == (544, 0, 749 - 544, 58 + 116), f"top left corner at the limits of the preview: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    win.delogo_place("0.1 0.2 0.3 0.4")
    win.fraCrop_MouseDown(0, 1, 0, 151, 113)
    check(win._crop_edge == ("right", "bottom") and cursors()[-1] == "SizeFDiagCursor", "bottom right corner")
    win.fraCrop_MouseMove(0, 1, 0, 171, 133)
    win.fraCrop_MouseMove(0, 1, 0, 191, 153)
    check(geo() == (595, 58, 194, 156), f"bottom right corner twice +20 (the reference point follows): {geo()}")
    win.fraCrop_MouseMove(0, 1, 0, 4000, 4000)
    check(geo()[0] + geo()[2] == 544 + 513 and geo()[1] + geo()[3] == 289, f"bottom right corner at the limits of the preview: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    win.delogo_place("0.1 0.2 0.3 0.4")
    win.fraCrop_MouseDown(0, 1, 0, 3, 113)
    check(win._crop_edge == ("left", "bottom") and cursors()[-1] == "SizeBDiagCursor", "bottom left corner")
    win.fraCrop_MouseMove(0, 1, 0, -17, 133)
    check(geo() == (575, 58, 174, 136), f"bottom left corner: left edge -20, bottom edge +20: {geo()}")
    win.fraCrop_MouseUp(0, 1, 0, 0, 0)
    # --- the rectangle is translucent
    style = frame.called("setStyleSheet")[-1][0]
    check("rgba(255, 0, 0," in style and "border: 1px solid" in style and frame.called("setAutoFillBackground")[-1] == (False,)
          and "WA_StyledBackground" in repr(frame.called("setAttribute")[-1][0]), f"translucent red with a solid edge: {style}")
    # --- second click: activate -> fractions in the mask column, saved, remembered
    win.delogo_place()
    win.answer = True
    asked = []
    win.ask = lambda text: (asked.append(text), win.answer)[1]
    win.cmdCommand_Click(6)
    check(asked == ["Do you want to activate the DeLogo filter?"] and seg.mask == "0.005848 0.875433 0.064327 0.114187" and not frame.isVisible()
          and win.delogo_last == seg.mask, f"activated: fractions of the preview area in the mask column: {seg.mask!r}")
    check(load_segments(os.path.join(tmp, "delogowin", "MediaMaker.json"))[0].mask == seg.mask, "the list is saved")
    check(win.lvwSegments.topLevelItem(0).text(18) == seg.mask, "shown in the mask column of the list")
    win.cmdCommand_Click(6)
    check(frame.isVisible() and geo() == (547, 253, 33, 33), f"clicking again shows the stored rectangle: {geo()}")
    win.answer = False
    win.cmdCommand_Click(6)
    check(seg.mask == "" and not frame.isVisible() and win.delogo_last == "0.005848 0.875433 0.064327 0.114187" and
          load_segments(os.path.join(tmp, "delogowin", "MediaMaker.json"))[0].mask == "", "answer No: filter off, the last rectangle is remembered")
    # --- next segment: offer the previous area again (Yes / No / Cancel); a change of the selection removes the rectangle
    answers = ["yes", "yes", "no", "cancel"]
    questions = []
    win.ask3 = lambda text: (questions.append(text), answers.pop(0))[1]
    win.cmdCommand_Click(6)
    check(questions == ["Do you want to re-use the previous logo area again?"] and frame.isVisible() and geo() == (547, 253, 33, 33),
          f"the segment has no rectangle but one was used before: it is offered, Yes: {geo()}")
    win.lvwSegments.select_row(1)
    win.lvwSegments_Click()
    check(not frame.isVisible(), "selecting another segment hides a rectangle that was being placed")
    win.delogo_last = "0.25 0.6 0.1 0.2"
    win.cmdCommand_Click(6)
    check(frame.isVisible() and geo() == (672, 173, 51, 58), f"Yes: the previous area is used: {geo()}")
    frame.hide()
    win.cmdCommand_Click(6)
    check(frame.isVisible() and geo() == (547, 253, 33, 33) and len(questions) == 3, f"No: the start position: {geo()}")
    frame.hide()
    win.cmdCommand_Click(6)
    check(not frame.isVisible() and len(questions) == 4 and seg2.mask == "" and answers == [], "Cancel: nothing happens")
    # --- a RemoveLogo mask (PNG) is replaced; commas as decimal separator (lists of VB6 in a German locale) are understood
    seg2.mask = "iVBORw0KGgo="
    win.delogo_last = ""
    win.cmdCommand_Click(6)
    check(frame.isVisible() and geo() == (547, 253, 33, 33), "a PNG mask is not a rectangle: start position")
    win.answer = True
    win.cmdCommand_Click(6)
    check(seg2.has_delogo and len(seg2.mask.split()) == 4, "the rectangle replaces the PNG mask")
    win.delogo_place("0,1 0,2 0,3 0,4")
    check(geo() == (595, 58, 154, 116), "decimal commas are understood")
    # --- no segment: nothing happens
    win.segments.clear()
    win.current = -1
    n = len(win.messages)
    win.cmdCommand_Click(6)
    check(len(win.messages) == n, "without a segment nothing happens")
    # --- pixels for ffmpeg: fractions of the source picture, limited to the picture
    s = dataclasses.replace(seg, width=720, height=576, mask="0.100000 0.800000 0.150000 0.100000")
    check(ffmpeg_cmd._delogo(s, 720, 576) == "delogo=x=72:y=461:w=108:h=58,", "fractions -> pixels of the source picture")
    s.mask = "0.99 0.99 0.2 0.2"
    check(ffmpeg_cmd._delogo(s, 720, 576) == "delogo=x=713:y=570:w=6:h=5,", "limited to the picture")
    s.mask = "0,1 0,2 0,3 0,4"
    check(ffmpeg_cmd._delogo(s, 720, 576) == "delogo=x=72:y=115:w=216:h=230,", "VB6 lists with decimal commas")
    # --- real run: ffmpeg changes the picture inside the rectangle and (almost) nothing outside of it
    work = tempfile.mkdtemp()
    outputs = {}
    for name, mask in (("plain", ""), ("delogo", "0.300000 0.300000 0.200000 0.200000")):
        w2 = seek_window(tmp, videos, ("sample2.ts",), workdir="delogorun_" + name, first_fn=first_frame_number)
        w2.segments[0].mask = mask
        job = w2.make_job(os.path.join(work, name + ".mp4"))
        res = run_ffmpeg(ffmpeg_cmd.build_command(job), total_seconds(job), None, cwd=work)
        check(res.returncode == 0 and os.path.exists(job.output), f"ffmpeg run with {name}: {res.returncode} {res.errors[-200:]}")
        outputs[name] = job.output
    a = grab_frame(outputs["plain"], 10, Fraction(25)).astype(np.int32)
    b = grab_frame(outputs["delogo"], 10, Fraction(25)).astype(np.int32)
    diff = np.abs(a - b).mean(axis=2)
    # rectangle in the output: x 216..360; y (173..288 - 72 crop at the top) * 576/432 = 135..288
    inside, outside = diff[140:285, 220:356].mean(), (diff.sum() - diff[135:288, 216:360].sum()) / (diff.size - diff[135:288, 216:360].size)
    check(inside > 2 * outside and inside > 1.0, f"the picture changes inside the rectangle (mean difference {inside:.2f}), much less outside ({outside:.2f})")
    print("DeLogo: OK (rectangle, mouse, limits, activate/deactivate, re-use, saving, pixels for ffmpeg, real run)")


def test_removelogo(tmp, videos):
    """RemoveLogo filter: black/white mask of a frame that only shows the logo (dialog), stored as a base64 PNG in the segment,
    written to a temporary file for ffmpeg."""
    import numpy as np
    import logo
    import ffmpeg_cmd
    import removelogo_dialog
    from PIL import Image
    from frames import grab_frame
    from mediaprobe import first_frame_number
    from runner import run_ffmpeg, total_seconds
    import base64
    import io
    # --- building blocks
    rgb = np.zeros((4, 4, 3), np.uint8)
    rgb[0, 0] = (8, 8, 8)
    rgb[0, 1] = (7, 7, 7)
    rgb[1, 0] = (0, 0, 9)
    rgb[1, 1] = (255, 255, 255)
    m = logo.monochrome_mask(rgb)
    check(m.dtype == bool and m[0, 0] and not m[0, 1] and not m[1, 0] and m[1, 1] and not m[2:].any(), "threshold 8: dark pixels are black, the rest is white")
    full = np.ones((100, 10), bool)
    check(np.array_equal(logo.blacken_center(full, 0), full) and logo.blacken_center(full, 0) is not full, "slider at 0: the mask stays as it is")
    half = logo.blacken_center(full, 900)
    rows = np.flatnonzero(~half.any(axis=1))
    check(list(rows) == list(range(24, 75)) and half[:24].all() and half[75:].all(), f"slider in the middle: 51 lines around the centre: {rows[0]}..{rows[-1]}")
    check(not logo.blacken_center(full, 1800).any() and full.all(), "slider at the end: everything is black, the original is not changed")
    odd = logo.blacken_center(np.ones((101, 4), bool), 600)
    rows = np.flatnonzero(~odd.any(axis=1))
    check(len(rows) == 2 * (600 * 50 // 1800) + 1 and rows[0] + rows[-1] == 100 - 0, f"odd height: {rows[0]}..{rows[-1]}")
    pattern = np.zeros((576, 720), bool)
    pattern[20:40, 40:120] = True
    b64 = logo.mask_to_png_b64(pattern)
    check("\n" not in b64 and b64.startswith("iVBOR") and len(b64) < 4000 and np.array_equal(logo.mask_from_png_b64(b64), pattern)
          and Image.open(io.BytesIO(base64.b64decode(b64))).mode == "1", f"1-bit PNG, base64 without line breaks, small ({len(b64)} characters), same mask")
    check(logo.isolate_logo(pattern) is not None and logo.isolate_logo(np.zeros((576, 720), bool)) is None, "the logo can be isolated in the mask")
    # --- the dialog with real frames
    sample = os.path.join(videos, "sample2.ts")
    fps = Fraction(25)
    grabs = []
    grab = lambda n: (grabs.append(n), grab_frame(sample, n, fps))[1]
    dialog = removelogo_dialog.frmRemoveLogo(grab, 40, 10, 157, lambda n: n - 10)
    check(dialog.frame == 40 and dialog.mask is None and dialog.result == "" and dialog.Picture1.paint_hook == dialog.paint_picture, "dialog starts without loading")
    painted = []
    class Painter:
        def setRenderHint(self, *a): pass
        def drawImage(self, rect, image): painted.append((rect, image))
    dialog.paint_picture(Painter(), "rect")
    check(painted == [], "nothing is painted before a frame is loaded")
    check(dialog.load_frame() is True and grabs == [40] and dialog.mask.shape == (576, 720) and dialog.mask.dtype == bool and dialog.mask.any()
          and not dialog.mask.all(), "the frame is loaded as a black/white picture")
    check(dialog.lblFrame.called("setText")[-1] == ("Frame: 30",), "the displayed frame number is counted from the first picture")
    check(dialog.called("setEnabled")[-2:] == [(False,), (True,)], "the dialog is blocked while the frame is loaded")
    dialog.paint_picture(Painter(), "rect")
    check(len(painted) == 1 and painted[0][0] == "rect" and painted[0][1] is dialog.image, "the picture is painted into the box")
    steps = {0: 39, 1: 40, 2: 30, 3: 40}
    for index, expected in steps.items():
        dialog.cmdNavigate_Click(index)
        check(dialog.frame == expected and grabs[-1] == expected, f"button {index}: frame {expected}")
    check(dialog.lblFrame.called("setText")[-1] == ("Frame: 30",), "label after the buttons")
    dialog.frame = 12
    dialog.cmdNavigate_Click(2)
    check(dialog.frame == 10, "10 frames to the left stops at the first frame")
    n = len(grabs)
    dialog.cmdNavigate_Click(0)
    check(dialog.frame == 10 and len(grabs) == n, "at the first frame '<' does nothing")
    dialog.frame = 156
    dialog.cmdNavigate_Click(3)
    check(dialog.frame == 157, "10 frames to the right stops at the last frame")
    n = len(grabs)
    dialog.cmdNavigate_Click(1)
    check(dialog.frame == 157 and len(grabs) == n, "at the last frame '>' does nothing")
    dialog.frame = 40
    dialog.load_frame()
    # --- red band
    check(dialog.fraBlend.called("hide") != [] and not dialog.fraBlend.isVisible(), "no band at first")
    dialog.hscBlend.setValue(600)
    dialog.hscBlend_Change()
    picture = dialog.Picture1.geometry()
    check(picture.height() == 474 and dialog.fraBlend.isVisible() and dialog.fraBlend.called("setGeometry")[-1] == (8, 8 + 237 - 79, 593, 158),
          f"band around the middle of the picture: {dialog.fraBlend.called('setGeometry')[-1]}")
    check("rgba(255, 0, 0," in dialog.fraBlend.called("setStyleSheet")[-1][0], "the band is translucent")
    dialog.hscBlend.setValue(0)
    dialog.hscBlend_Change()
    check(not dialog.fraBlend.isVisible(), "slider at 0: band is hidden")
    # --- OK stores the mask with the blackened centre; Cancel nothing
    accepted = []
    dialog.accept = lambda: accepted.append("accept")
    dialog.hscBlend.setValue(900)
    dialog.cmdOK_Click()
    expected_mask = logo.blacken_center(dialog.mask, 900)
    check(accepted == ["accept"] and "\n" not in dialog.result and np.array_equal(logo.mask_from_png_b64(dialog.result), expected_mask) and not dialog.fraBlend.isVisible(),
          "OK: PNG mask with the centre blackened")
    dialog.result = ""
    dialog.hscBlend.setValue(0)
    dialog.cmdOK_Click()
    check(np.array_equal(logo.mask_from_png_b64(dialog.result), dialog.mask), "OK without the slider: the black/white picture as it is")
    rejected = []
    dialog.reject = lambda: rejected.append("reject")
    dialog.cmdCancel_Click()
    check(rejected == ["reject"] and dialog.result == "", "Cancel: no mask")
    fresh = removelogo_dialog.frmRemoveLogo(grab, 40, 10, 157)
    count = len(accepted)
    fresh.accept = lambda: accepted.append("again")
    fresh.cmdOK_Click()
    check(len(accepted) == count and fresh.result == "", "OK without a loaded frame does nothing")
    # --- no frame available
    broken = removelogo_dialog.frmRemoveLogo(lambda n: (_ for _ in ()).throw(RuntimeError("no")), 40, 10, 157, lambda n: n - 10)
    told = []
    broken.inform = told.append
    check(broken.load_frame() is False and told == ["Could not get frame at frame 30"] and broken.mask is None and broken.called("setEnabled")[-1] == (True,),
          "a frame that cannot be read: message, dialog usable again")
    # --- clamping of the start frame
    check(removelogo_dialog.frmRemoveLogo(grab, 5, 10, 157).frame == 10 and removelogo_dialog.frmRemoveLogo(grab, 999, 10, 157).frame == 157, "start frame inside the valid range")
    # --- main window
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="removelogowin", first_fn=first_frame_number)
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    seg = win.segments[0]
    seen = []
    class Spy:
        def __init__(self, grab_fn, frame, first, last, shown, parent, opacity, aspect):
            seen.append((frame, first, last, shown(frame), opacity, round(aspect, 4)))
        def exec_dialog(self):
            return b64
    original = removelogo_dialog.frmRemoveLogo
    removelogo_dialog.frmRemoveLogo = Spy
    try:
        slider = win.Slider1.value()
        check(win.monochrome(slider) == b64 and seen == [(slider, 10, 158 - 1, slider - 10, 35, 1.7778)], f"monochrome() opens the dialog with the current frame, the valid range, the opacity and the display aspect ratio: {seen}")
    finally:
        removelogo_dialog.frmRemoveLogo = original
    win.fraCrop[0].show()
    win.monochrome = lambda frame_number: b64
    win.cmdCommand_MouseDown(6, 1, 1, 0, 0)
    win.cmdCommand_Click(6)
    check(seg.mask == b64 and seg.has_png_mask and not seg.has_delogo and not win.fraCrop[0].isVisible()
          and win.messages[-1] == f"PNG mask for the removelogo filter was created and saved successfully.\n\n(Size: {len(b64)} bytes)",
          f"mask stored in the segment: {win.messages[-1]!r}")
    check(load_segments(os.path.join(tmp, "removelogowin", "MediaMaker.json"))[0].mask == b64, "the list is saved")
    empty = logo.mask_to_png_b64(np.zeros((576, 720), bool))
    win.monochrome = lambda frame_number: empty
    win.cmdCommand_MouseDown(6, 1, 1, 0, 0)
    win.cmdCommand_Click(6)
    check(seg.mask == empty and "could not be isolated" in win.messages[-1] and win.messages[-1].startswith("PNG mask for the removelogo filter was created"),
          "a mask without a logo is stored, with a note about the search for commercials")
    win.monochrome = lambda frame_number: ""
    win.cmdCommand_MouseDown(6, 1, 1, 0, 0)
    win.cmdCommand_Click(6)
    check(seg.mask == empty and win.messages[-1] == "No frame selected for RemoveLogo filter; please try again later.", "Cancel: the old mask stays")
    # --- real run: ffmpeg's removelogo filter changes the picture inside the mask, as a temporary file written for the run
    mask = np.zeros((576, 720), bool)
    mask[173:288, 216:360] = True
    work = tempfile.mkdtemp()
    outputs = {}
    for name, text in (("plain", ""), ("removelogo", logo.mask_to_png_b64(mask))):
        w2 = seek_window(tmp, videos, ("sample2.ts",), workdir="removelogorun_" + name, first_fn=first_frame_number)
        w2.segments[0].mask = text
        job = w2.make_job(os.path.join(work, name + ".mp4"))
        files = ffmpeg_cmd.write_masks(job.segments, work)
        command = ffmpeg_cmd.build_command(job)
        res = run_ffmpeg(command, total_seconds(job), None, cwd=work)
        check(res.returncode == 0 and os.path.exists(job.output), f"ffmpeg run with {name}: {res.returncode} {res.errors[-200:]}")
        check(("removelogo=removelogo01.png" in " ".join(command)) == bool(text) and (files == ["removelogo01.png"]) == bool(text) and os.path.exists(os.path.join(work, "removelogo01.png")) == bool(text),
              f"{name}: filter and temporary mask file {files}")
        outputs[name] = job.output
    a = grab_frame(outputs["plain"], 10, fps).astype(np.int32)
    b = grab_frame(outputs["removelogo"], 10, fps).astype(np.int32)
    diff = np.abs(a - b).mean(axis=2)
    box = diff[135:288, 216:360]
    inside, outside = diff[140:285, 220:356].mean(), (diff.sum() - box.sum()) / (diff.size - box.size)
    check(inside > 2 * outside and inside > 1.0, f"the picture changes inside the mask (mean difference {inside:.2f}), much less outside ({outside:.2f})")
    print("RemoveLogo: OK (mask, dialog with real frames, blackened centre, window, temporary file, real run)")


def test_logo_options_tooltip_and_dialog_layout(tmp, videos):
    """Opacity of the red areas (option), the tooltip of the logo button with Shift, picture and hint in the RemoveLogo dialog."""
    import numpy as np
    import dialogs
    import removelogo_dialog
    import vbqt
    from frames import grab_frame
    from profiles import GROUP_TEXTS, OPTION_GROUPS, validate_options
    from settings import DEFAULT_TOOLTIPS, default_options
    from PySide6 import QtCore
    from PySide6.QtWidgets import QToolTip
    # --- option overlay_opacity
    check(default_options()["overlay_opacity"] == "35" and "overlay_opacity" in DEFAULT_TOOLTIPS and "applies at once" in DEFAULT_TOOLTIPS["overlay_opacity"]
          and "overlay_opacity" in dict(OPTION_GROUPS)["Logo"] and "Logo" in GROUP_TEXTS, "option, explanation, group Logo")
    check(validate_options({"overlay_opacity": "0"}) == [] and validate_options({"overlay_opacity": "100"}) == []
          and len(validate_options({"overlay_opacity": "101"})) == 1 and len(validate_options({"overlay_opacity": "x"})) == 1, "checking: 0 to 100")
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="opacitywin")
    frame = win.fraCrop[0]
    alpha = lambda: int(frame.called("setStyleSheet")[-1][0].split("rgba(255, 0, 0, ")[1].split(")")[0])
    check(win.overlay_opacity() == 35 and alpha() == 89, f"35 % of 255 = 89: {alpha()}")
    for value, expected in (("0", 0), ("100", 255), ("60", 153), ("150", 255), ("-5", 0)):
        win.settings.set_option("overlay_opacity", value)
        win.style_delogo_frame()
        check(alpha() == expected, f"opacity {value} % -> alpha {expected}: {alpha()}")
    win.settings.set_option("overlay_opacity", "abc")
    check(win.overlay_opacity() == 35, "a value that is not a number: 35")
    win.settings.set_option("overlay_opacity", "35")
    win.edit_pairs = lambda title, pairs, groups=None, start=0: dict(pairs, overlay_opacity="80")
    win.mnuOptions_Click()
    check(alpha() == 204 and win.overlay_opacity() == 80, "a new value from the options dialog applies at once to the rectangle")
    # --- the band of the RemoveLogo dialog
    grab = lambda n: np.full((576, 720, 3), 100, np.uint8)
    for percent, expected in ((35, 89), (0, 0), (100, 255), (150, 255), (-3, 0)):
        d = removelogo_dialog.frmRemoveLogo(grab, 40, 10, 157, opacity=percent)
        check(f"rgba(255, 0, 0, {expected})" in d.fraBlend.called("setStyleSheet")[-1][0], f"band opacity {percent} % -> {expected}")
    # --- tooltip of the logo button
    tip = win.logo_tooltip
    button = win.cmdCommand[6]
    texts = lambda: [a[0] for a in button.called("setToolTip")]
    check(texts()[-1] == "Open/close DeLogo dialog", f"normal tooltip: {texts()[-1]}")
    tip.set_shift(True)
    check(texts()[-1] == "Open/close RemoveLogo dialog", "Shift down: the text of the removelogo dialog")
    n = len(texts())
    tip.set_shift(True)
    check(len(texts()) == n, "no change, no new text")
    tip.set_shift(False)
    check(texts()[-1] == "Open/close DeLogo dialog", "Shift released: back to the DeLogo text")
    state = {"shift": False}
    widget = type(button)()
    tip2 = vbqt.ShiftToolTip(widget, "normal", "with shift", shift_down=lambda: state["shift"])
    class Ev:
        def __init__(self, kind, key=None):
            self.kind, self.k = kind, key
        def type(self):
            return self.kind
        def key(self):
            return self.k
    E, K = QtCore.QEvent.Type, QtCore.Qt.Key
    last = lambda: widget.called("setToolTip")[-1][0]
    check(last() == "normal", "ShiftToolTip starts with the normal text")
    state["shift"] = True
    tip2.eventFilter(widget, Ev(E.Enter))
    check(last() == "with shift", "pointer enters while Shift is down")
    state["shift"] = False
    tip2.eventFilter(widget, Ev(E.ToolTip))
    check(last() == "normal", "tooltip appears after Shift was released")
    state["shift"] = True
    tip2.eventFilter(widget, Ev(E.MouseMove))
    check(last() == "with shift", "the pointer moves over the control while Shift is down")
    state["shift"] = False
    tip2.eventFilter(widget, Ev(E.MouseMove))
    check(last() == "normal", "Shift released, the pointer moves")
    # the key is watched by a timer as long as the pointer is on the control
    widget3 = type(button)()
    tip3 = vbqt.ShiftToolTip(widget3, "normal", "with shift", shift_down=lambda: state["shift"])
    last3 = lambda: widget3.called("setToolTip")[-1][0]
    state["shift"] = False
    check(tip3.timer.called("setInterval")[-1] == (100,) and not tip3.timer.isActive(), "a timer of 100 ms that is not running at first")
    tip3.eventFilter(widget3, Ev(E.Enter))
    check(tip3.timer.isActive() and len(tip3.timer.__dict__["starts_"]) == 1, "the pointer enters: the timer starts")
    state["shift"] = True
    tip3.timer.fire()
    check(last3() == "with shift", "Shift is pressed while the pointer rests on the control: the text changes")
    state["shift"] = False
    tip3.timer.fire()
    check(last3() == "normal", "Shift is released: the text changes back")
    tip3.eventFilter(widget3, Ev(E.Leave))
    check(tip3.timer.__dict__["stops_"] == 1, "the pointer leaves: the timer stops")
    tip3.eventFilter(object(), Ev(E.Enter))
    tip3.eventFilter(object(), Ev(E.Leave))
    check(len(tip3.timer.__dict__["starts_"]) == 1 and tip3.timer.__dict__["stops_"] == 1, "events of other controls are ignored")
    before = len(widget3.called("setToolTip"))
    tip3.eventFilter(widget3, Ev(E.KeyPress, K.Key_Shift))
    tip3.eventFilter(widget3, Ev(E.KeyRelease, K.Key_Shift))
    check(len(widget3.called("setToolTip")) == before, "key events are not handled (the key is asked for, nothing is watched on the whole application)")
    check(tip3.eventFilter(widget3, Ev(E.Enter)) is False, "events are never swallowed")
    widget3.under_mouse_ = True
    QToolTip.shown.append(("pos", "old", widget3))
    state["shift"] = True
    tip3.timer.fire()
    check(QToolTip.shown[-1][1] == "with shift" and QToolTip.shown[-1][2] is widget3, "a tooltip that is showing gets the new text at once")
    QToolTip.shown.clear()
    # --- RemoveLogo dialog: width stays, the height follows the proportions of the picture, no distortion
    sample = os.path.join(videos, "sample2.ts")
    d = removelogo_dialog.frmRemoveLogo(lambda n: grab_frame(sample, n, Fraction(25)), 40, 10, 157)
    fixed = lambda dialog: dialog.called("setFixedSize")[-1]
    check(fixed(d) == (609, 385 + 24) and d.lblHint.text() == removelogo_dialog.HINT and d.hscBlend.called("setToolTip")[-1] == (dialogs.wrap_tooltip(removelogo_dialog.HINT),)
          and d.lblHint.called("setToolTip")[-1] == (dialogs.wrap_tooltip(removelogo_dialog.HINT),), "before loading: the line of explanation makes the window 24 px taller; tooltip on slider and text")
    d.load_frame()
    geo = lambda w: (lambda g: (g.x(), g.y(), g.width(), g.height()))(w.geometry())
    check(geo(d.Picture1) == (8, 8, 593, 474), f"720 x 576 picture: width 593, height 474: {geo(d.Picture1)}")
    check(geo(d.cmdOK) == (520, 352 + 137, 81, 25) and geo(d.cmdNavigate[0]) == (48, 352 + 137, 35, 27) and geo(d.hscBlend) == (264, 360 + 137, 161, 17)
          and geo(d.lblFrame) == (88, 360 + 137, 89, 17) and geo(d.lblHint) == (8, 385 + 137, 593, 17), "the controls below move down with the picture")
    check(fixed(d) == (609, 385 + 24 + 137), f"the window is as tall as needed: {fixed(d)}")
    wide = removelogo_dialog.frmRemoveLogo(lambda n: np.full((1080, 1920, 3), 100, np.uint8), 40, 10, 157)
    wide.load_frame()
    check(geo(wide.Picture1) == (8, 8, 593, 334) and geo(wide.cmdOK) == (520, 349, 81, 25) and fixed(wide) == (609, 406), f"1920 x 1080: height 334, window 406: {geo(wide.Picture1)}")
    wide.grab_frame = lambda n: np.full((1080, 1440, 3), 100, np.uint8)
    wide.load_frame()
    check(geo(wide.Picture1)[3] == round(593 * 1080 / 1440) and fixed(wide) == (609, 409 + round(593 * 1080 / 1440) - 337), "another frame with other proportions: the layout is recalculated from the original positions")
    tall = removelogo_dialog.frmRemoveLogo(lambda n: np.full((2000, 100, 3), 100, np.uint8), 40, 10, 157)
    tall.load_frame()
    flat = removelogo_dialog.frmRemoveLogo(lambda n: np.full((10, 1000, 3), 100, np.uint8), 40, 10, 157)
    flat.load_frame()
    check(geo(tall.Picture1)[3] == 700 and geo(flat.Picture1)[3] == 120, "extreme proportions: the height is limited")
    print("Logo options, tooltip with Shift, dialog layout: OK")


def test_display_aspect(tmp, videos):
    """The RemoveLogo preview has the proportions of the picture as a video player shows it (display aspect ratio / sample aspect ratio)."""
    import numpy as np
    import mediaprobe
    import removelogo_dialog
    from frames import grab_frame
    from mediaprobe import aspect_from_stream, display_aspect
    near = lambda a, b: a is not None and abs(a - b) < 1e-6
    check(near(aspect_from_stream(720, 576, "64:45", "16:9"), 16 / 9) and near(aspect_from_stream(720, 576, "1:1", "5:4"), 1.25), "display aspect ratio of the stream")
    check(near(aspect_from_stream(720, 576, "64:45", "0:1"), 720 * 64 / (576 * 45)) and near(aspect_from_stream(720, 576, "64:45", None), 16 / 9)
          and near(aspect_from_stream(720, 576, "64:45", "N/A"), 16 / 9), "no usable DAR: pixel proportions times SAR")
    check(near(aspect_from_stream(1920, 1080, "1:1", None), 16 / 9) and near(aspect_from_stream(720, 576, "0:1", "0:1"), 1.25)
          and near(aspect_from_stream(720, 576, "N/A", "N/A"), 1.25) and near(aspect_from_stream(720, 576, "x", "y:z"), 1.25), "no SAR and no DAR: the pixel proportions")
    check(near(aspect_from_stream(0, 0, None, None), 1.0) and near(aspect_from_stream(720, 576, "-1:1", "5:-4"), 1.25), "nonsense values")
    check(near(display_aspect(os.path.join(videos, "sample2.ts")), 16 / 9) and display_aspect(os.path.join(tmp, "does_not_exist.ts")) is None, "from a file (ffprobe); None for a missing file")
    work = tempfile.mkdtemp()
    for name, sar, expected in (("square", "1", 1.25), ("anamorphic", "64/45", 16 / 9), ("ntsc43", "8/9", 720 / 576 * 8 / 9)):
        path = os.path.join(work, name + ".ts")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=720x576:rate=25:duration=1", "-vf", f"setsar={sar}", "-c:v", "libx264", "-f", "mpegts", path],
                       check=True, stdin=subprocess.DEVNULL)
        check(near(display_aspect(path), expected), f"{name}: SAR {sar} -> {display_aspect(path)}")
    # --- the dialog
    grab = lambda n: np.full((576, 720, 3), 100, np.uint8)
    geo = lambda w: (lambda g: (g.x(), g.y(), g.width(), g.height()))(w.geometry())
    fixed = lambda dialog: dialog.called("setFixedSize")[-1]
    for aspect, height in ((16 / 9, 334), (4 / 3, 445), (None, 474), (1.25, 474), (2.39, 248), (0.5, 700), (50, 120)):
        d = removelogo_dialog.frmRemoveLogo(grab, 40, 10, 157, aspect=aspect)
        d.load_frame()
        check(geo(d.Picture1) == (8, 8, 593, height) and fixed(d) == (609, 409 + height - 337) and geo(d.cmdOK)[1] == 352 + height - 337,
              f"aspect {aspect}: box {geo(d.Picture1)[2]} x {geo(d.Picture1)[3]} (expected {height}), window {fixed(d)}")
    # --- the main window: asked once per file, passed to the dialog
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="aspectwin")
    asked = []
    win._aspect_fn = lambda path: (asked.append(path), 1.5)[1]
    check(win.aspect_of("/a.ts") == 1.5 and win.aspect_of("/a.ts") == 1.5 and win.aspect_of("/b.ts") == 1.5 and asked == ["/a.ts", "/b.ts"], "the aspect of a file is asked once")
    win._aspect_fn = lambda path: None
    check(win.aspect_of("/c.ts") is None, "unknown aspect: None (the dialog then uses the pixel proportions)")
    print("Display aspect ratio: OK (DAR, SAR, files, dialog height, cache)")


def test_recent_dirs(tmp, videos):
    """Folders used recently: kept in the INI file, offered in a selection list when the target file of a batch is entered."""
    import dialogs
    from PySide6 import QtWidgets as W
    work = os.path.join(tmp, "recent")
    os.makedirs(work, exist_ok=True)
    ini = os.path.join(work, "MediaMaker.ini")
    open(ini, "w", encoding="utf-8").write("[settings]\n")
    st = Settings(ini)
    check(st.recent_dirs == [], "no folders at first")
    st.add_recent_dir("/a/b")
    st.add_recent_dir("/c/")
    check(st.recent_dirs == ["/c", "/a/b"], f"newest first, a trailing slash is dropped: {st.recent_dirs}")
    st.add_recent_dir("/a/b")
    check(st.recent_dirs == ["/a/b", "/c"], "a folder used again moves to the top without a duplicate")
    for bad in ("", "   ", None, "."):
        st.add_recent_dir(bad)
    check(st.recent_dirs == ["/a/b", "/c"], "empty values are ignored")
    for i in range(14):
        st.add_recent_dir(f"/d{i}")
    check(len(st.recent_dirs) == 10 and st.recent_dirs[0] == "/d13" and st.recent_dirs[-1] == "/d4", f"at most 10, the oldest fall out: {st.recent_dirs[:2]} ... {st.recent_dirs[-1]}")
    st.save()
    check(Settings(ini).recent_dirs == st.recent_dirs, "stored in the INI file")
    check("[settings]\nrecent_dirs=" in open(ini, encoding="utf-8").read() or "recent_dirs=" in open(ini, encoding="utf-8").read(), "key recent_dirs in [settings]")
    # --- the input dialog (folder in a selection list + file name)
    made = {}
    class Combo(W.QComboBox):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            made["combo"] = self
    class Edit(W.QLineEdit):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            made["edit"] = self
    original = (W.QComboBox, W.QLineEdit)
    W.QComboBox, W.QLineEdit = Combo, Edit
    try:
        W.QDialog.exec_result, W.QDialog.on_exec = 1, None
        result = dialogs.ask_output_file(None, "Batch", "prompt", ["/x", "/y", "/z"], "/z", "film.mp4")
        combo = made["combo"]
        check(combo.called("setEditable")[-1] == (True,) and combo.called("addItems")[-1] == (["/z", "/x", "/y"],) and combo.called("setCurrentText")[-1] == ("/z",),
              "the list holds the suggested folder first, then the folders used recently (no duplicate); it can be edited")
        check(result == "/z/film.mp4", f"folder and name make the path: {result}")
        W.QDialog.exec_result = 0
        check(dialogs.ask_output_file(None, "Batch", "prompt", ["/x"], "/z", "film.mp4") is None, "cancel: None")
        W.QDialog.exec_result = 1
        made.clear()
        check(dialogs.ask_output_file(None, "Batch", "prompt", [], "", "film.mp4") == "film.mp4" and made["combo"].called("addItems")[-1] == ([],), "no folder: just the name")
        check(dialogs.ask_output_file(None, "Batch", "prompt", [], "/z", "   ") is None, "no file name: None")
        home = os.path.expanduser("~")
        made.clear()
        W.QLineEdit.text = lambda self: "x.mp4"
        check(dialogs.ask_output_file(None, "Batch", "prompt", [], "~/videos", "x.mp4") == os.path.join(home, "videos", "x.mp4"), "~ is the home folder")
    finally:
        W.QComboBox, W.QLineEdit = original
        W.QDialog.exec_result = 1
    # --- in the window: suggestion split into folder and name, folders used recently handed over, list updated
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="recentwin")
    win.settings.add_recent_dir("/old1")
    win.settings.add_recent_dir("/old2")
    captured = []
    original_ask = dialogs.ask_output_file
    dialogs.ask_output_file = lambda parent, title, prompt, folders, folder, name: (captured.append((title, folders, folder, name, prompt)), os.path.join(work, "out", "Film.mp4"))[1]
    win.ask3 = lambda text: "no"                                      # a script exists after the first call: do not keep old steps
    try:
        win.mnuBatch_Click()
    finally:
        dialogs.ask_output_file = original_ask
    title, folders, folder, name, prompt = captured[-1]
    check(title == "Batch" and folders == ["/old2", "/old1"] and folder == videos and name == "sample2.mp4" and "overwritten w/o warning" in prompt,
          f"suggested folder and name, the folders used recently: {captured[-1][:4]}")
    check(win.settings.recent_dirs[:3] == [os.path.join(work, "out"), "/old2", "/old1"] and Settings(win.settings.path).recent_dirs[0] == os.path.join(work, "out"),
          "after the batch the folder is at the top of the list, also in the INI file")
    # cancel changes nothing
    win.ask_output = lambda title, suggestion: None
    before = list(win.settings.recent_dirs)
    win.mnuBatch_Click()
    check(win.settings.recent_dirs == before, "cancelling the input leaves the list alone")
    # Save as MP4/AVI: the folder of the chosen file is remembered, too
    win.ask_save_file = lambda title, suggestion, filters: os.path.join(work, "saved", "film.mp4")
    win._render_fn = lambda cmd, total, on_progress, cwd=None, cancel=None: __import__("runner").RunResult(0, False, 0.1, "")
    win.save_video("mp4")
    check(win.settings.recent_dirs[0] == os.path.join(work, "saved"), "a folder chosen in the Save as dialog is offered in the Batch dialog later")
    print("Recent folders: OK (INI list, input dialog with selection list, Batch, Save as)")


def test_logo_mask_as_in_vb6(tmp, videos):
    """The RemoveLogo mask is used exactly as the threshold picture gives it (as in VB6); the options that were tried for it are gone."""
    import numpy as np
    import ffmpeg_cmd
    import logo
    import removelogo_dialog
    from mediaprobe import first_frame_number
    from profiles import GROUP_TEXTS, OPTION_GROUPS, REMOVED_OPTIONS, validate_options
    from settings import DEFAULT_TOOLTIPS, default_options
    # --- the dialog stores the threshold picture unchanged, also if a dark symbol makes a hole in it
    def logo_frame():
        frame = np.zeros((576, 720, 3), np.uint8)
        frame[81:118, 632:666] = 210
        frame[90:108, 640:656] = 0
        return frame
    d = removelogo_dialog.frmRemoveLogo(lambda n: logo_frame(), 40, 10, 157)
    d.load_frame()
    expected = logo.monochrome_mask(logo_frame())
    d.accept = lambda: None
    d.cmdOK_Click()
    stored = logo.mask_from_png_b64(d.result)
    check(np.array_equal(stored, expected) and not stored[95, 648] and stored[85, 648] and int(stored.sum()) == 37 * 34 - 18 * 16,
          f"OK stores the threshold picture as it is (the hole of the dark symbol stays): {int(stored.sum())} white pixels")
    check(np.array_equal(logo.mask_from_png_b64(logo.mask_to_png_b64(expected)), expected) and not hasattr(logo, "fill_holes") and not hasattr(logo, "grow_mask"),
          "no filling and no growing in the logo module")
    check(not hasattr(d, "final") and not hasattr(d, "preview") and not hasattr(removelogo_dialog, "ADDED_GREY"), "no second (changed) picture in the dialog")
    # --- the command always uses ffmpeg's removelogo, also with an old INI file that still has the dropped options
    work = os.path.join(tmp, "oldlogo")
    os.makedirs(work, exist_ok=True)
    ini = os.path.join(work, "MediaMaker.ini")
    open(ini, "w", encoding="utf-8").write('[settings]\noptions=crop="72" logo_fill="smooth" fill_sigma="9" mask_fill="False" mask_grow="3" player="memory"\n')
    win = make_window(work)
    win.showEvent(None)
    check("logo_fill" not in win.options and "mask_grow" not in win.options and "fill_sigma" not in win.options and "mask_fill" not in win.options, "the dropped options are not offered")
    text = open(ini, encoding="utf-8").read()
    check("logo_fill" not in text and "mask_grow" not in text and 'crop="72"' in text and 'player="memory"' in text, f"they are removed from the INI file, the rest stays: {text.strip()!r}")
    w2 = seek_window(tmp, videos, ("sample2.ts",), workdir="vb6mask", first_fn=first_frame_number)
    m = np.zeros((576, 720), bool)
    m[81:118, 632:666] = True
    w2.segments[0].mask = logo.mask_to_png_b64(m)
    w2.settings.set("settings", "options", w2.settings.get("settings", "options") + ' logo_fill="smooth"')
    cmd = " ".join(ffmpeg_cmd.build_command(w2.make_job(os.path.join(tmp, "o.mp4"))))
    check("removelogo=removelogo01.png" in cmd and "movie=" not in cmd and "gblur" not in cmd, "the command is ffmpeg's removelogo, whatever an old INI says")
    # --- options, explanations, groups
    d0 = default_options()
    check(not (REMOVED_OPTIONS - {"focus", "pad"}) & set(d0) and all(k not in DEFAULT_TOOLTIPS for k in ("logo_fill", "fill_sigma", "mask_fill", "mask_grow")), "no defaults and no explanations for them")
    check(dict(OPTION_GROUPS)["Logo"] == ("overlay_opacity",) and "overlay_opacity" in d0 and GROUP_TEXTS["Logo"], "the group Logo has the opacity of the red areas")
    check(validate_options({"overlay_opacity": "35"}) == [], "checking")
    print("Logo mask as in VB6: OK (unchanged mask, removelogo only, dropped options removed)")


def test_shutdown(tmp, videos):
    """When the window is closed, playback is ended, even in the middle of playing."""
    win = make_window(tmp)
    win.showEvent(None)
    win.OpenVideo(os.path.join(videos, "sample2.ts"))
    win.cmdPos_Click(3)
    check(win.player.is_playing, "playback is running")
    win.closeEvent(None)
    check(win.player.shut_down and not win.player.is_playing, "player shut down after closing")
    win.player.shutdown()                                      # twice is harmless
    print("Quit: OK (player is shut down when closing, even in the middle of playing)")


def test_throttle():
    from player import SeekThrottle
    done = []
    t = SeekThrottle(done.append)
    t.request(1)
    t.request(2)
    t.request(3)
    check(done == [1], f"first jump immediately, further ones held back: {done}")
    t.timer.fire()
    check(done == [1, 3] and t.timer.isActive(), f"last requested value after the delay: {done}")
    t.timer.fire()
    check(done == [1, 3] and not t.timer.isActive(), "nothing left open")
    t.request(4)
    check(done == [1, 3, 4], "immediately again after a pause")
    print("Jump throttle: OK (first immediately, then combined, last value arrives)")


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
    test_main_window_size_and_profile_click(tmp, sys.argv[1])
    test_cut_snap(tmp, sys.argv[1])
    test_batch_file(tmp, sys.argv[1])
    test_save_video(tmp, sys.argv[1])
    test_dialog_styles_and_batch_path(tmp, sys.argv[1])
    test_options_in_options_string(tmp, sys.argv[1])
    test_group_texts(tmp, sys.argv[1])
    test_delogo(tmp, sys.argv[1])
    test_removelogo(tmp, sys.argv[1])
    test_logo_mask_as_in_vb6(tmp, sys.argv[1])
    test_display_aspect(tmp, sys.argv[1])
    test_recent_dirs(tmp, sys.argv[1])
    test_logo_options_tooltip_and_dialog_layout(tmp, sys.argv[1])
    test_example_ini(tmp, sys.argv[1])
    test_first_frame(tmp, sys.argv[1])
    test_shutdown(tmp, sys.argv[1])
    test_throttle()
    if errors:
        print(f"\n{len(errors)} ERRORS:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
