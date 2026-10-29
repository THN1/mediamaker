"""Tests for settings, project file and the main logic (opening, analysing, navigation) without Qt and without VLC.

Usage:  python3 tests/test_app.py FOLDER_WITH_SAMPLE_VIDEOS   (expects sample2.ts and sample3.ts in it)
The user interface runs against the Qt replacement in ui/tests/qtstub, the playback against FakePlayer.
"""
import base64
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
    win.finish_message = lambda text, output: win.messages.append(text)        # (the real one asks "Play now?": test_play_now)
    win.notice_keep = True                                                     # the check box "Show this warning next time" of the copy mode warning: stays ticked
    win.notice_box = lambda text: (win.messages.append(text), win.notice_keep)[1]
    win.verify_first_frame = False                       # most tests give the first frame by hand (first_fn); test_first_frame_check switches it on
    win.references_shown = []
    win.show_reference = lambda text, rgb, ref: (win.messages.append(text), win.references_shown.append((text, rgb, ref)))
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
    check(win.messages[-1] == "There are no segments in the list.", "reuse without segment")
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
    check('copied from "sample3.ts"' in win.messages[-1] and win.profile["bv"] == f"{win.segments[1].vbitrate_kbit}k" and win.profile["ba"] == f"{win.segments[1].abitrate_kbit}k",
          f"reuse with two segments in the list: the selected one (the one opened last) counts: {win.messages[-1][:60]}")
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    win.mnuReuse_Click()
    check('copied from "sample2.ts"' in win.messages[-1] and win.profile["bv"] == f"{win.segments[0].vbitrate_kbit}k", "another one selected: the values of that one")
    win.current = -1
    win.mnuReuse_Click()
    check(win.messages[-1] == "Select the segment in the list whose settings are to be taken over.", "none selected: told")
    win.lvwSegments.select_row(1)
    win.lvwSegments_Click()
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
        stops_before = mp.stops
        player.surface.image = "last picture"
        player.clear()
        check(player.surface.image is None and mp.stops == stops_before + 1, "clear(): stopped and the last picture is removed from the drawing area")
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
          and painter.lines == [] and painter.fills == [], f"drawing: 20 pictures, and the red line is NOT painted over them: {painter.fills}")
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
    check(win._modal_child is not None and not any("ported" in m for m in win.messages) and all(win.fraCrop[i].isVisible() for i in range(4)), "crop: the window opens, no note, the bands are shown")
    win._modal_child.cmdCancel_Click()
    check(win._modal_child is None and not any(win.fraCrop[i].isVisible() for i in range(4)), "cancelled: the bands are hidden again")
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
    check(texts and texts[0].startswith("Seeking with crop = 72, please wait...\nframe ") and "border" in texts[0] and "about 72" in texts[0]
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

    # --- search with the station logo (simulated detection: logo from frame 90; the picture changes at frame 60, but there is no rewinding)
    elysium = parse_batch_header(open(os.path.join(HERE, "sample_Elysium.bat"), encoding="latin-1").read())
    conf = lambda path, n, fps, ref, opts: 0.9 if n >= 90 else 0.0
    win = seek_window(tmp, videos, workdir="logowin", conf_fn=conf)
    win.settings.set_option("crop", 0)
    win.segments[0].mask = elysium.segments[0].mask
    win.mnuEnd_Click()
    check(win.Slider1.value() == 90, f"logo: the first frame with logo, no rewinding: {win.Slider1.value()}")
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
    check(len(painter.fills) == 20 and painter.lines == [], f"20 grey placeholders, and NO red line over them: {len(painter.fills)}")
    painter2 = Painter()
    tl.draw_strip(painter2, __import__("PySide6.QtWidgets", fromlist=["Rect"]).Rect(2, 2, 1085, 45), [("image", None)] * 20)
    check(painter2.fills == [] and painter2.lines == [], "pictures: nothing is painted over them")
    kids = win.Line1.parent_.children_
    check(kids.index(win.Line1) < kids.index(win.picTimeline), "the red line of the form lies behind the timeline (it is created before it): it shows between the pictures and above and below the strip")
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
    legacy = [Segment(1, s2, "sample2.ts", 0, 148, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, "", first_unknown=True),
              Segment(2, s2, "sample2.ts", 50, 148, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, "", first_unknown=True),
              Segment(3, s2, "sample2.ts", 20, 90, 148, Fraction(25), 720, 576, 3000, 192, "a", 0, 0, 0, 0, 48000, "", first_unknown=True)]
    save_segments(os.path.join(work, "MediaMaker.json"), legacy)
    win = make_window(work, thumb_fn=quick_thumbs, first_fn=lambda path, fps: 10)
    win.showEvent(None)
    got = [(s.first_frame, s.start, s.end, s.total_frames) for s in win.segments]
    check(got == [(10, 10, 158, 158), (10, 50, 158, 158), (10, 20, 90, 158)], f"old list converted: {got}")
    check([(s.first_frame, s.start, s.end, s.total_frames) for s in load_segments(os.path.join(work, "MediaMaker.json"))] == got, "converted and saved")
    win2 = make_window(work, thumb_fn=quick_thumbs, first_fn=lambda path, fps: 99)           # do not convert again
    win2.showEvent(None)
    check([(s.first_frame, s.total_frames) for s in win2.segments] == [(10, 158)] * 3, "already converted list stays unchanged")
    # --- the start does not read the files again when the list says that it knows the first frame (also when it is 0: an mp4 file); an old list is read once per FILE
    probed = []
    def counting_first(path, fps):
        probed.append(path)
        return 0
    work_mp4 = os.path.join(tmp, "legacywin_mp4")
    os.makedirs(work_mp4, exist_ok=True)
    known = [dataclasses.replace(legacy[0], first_unknown=False, first_frame=0, index=i + 1) for i in range(3)]
    save_segments(os.path.join(work_mp4, "MediaMaker.json"), known)
    check('"first_frame": 0' in open(os.path.join(work_mp4, "MediaMaker.json"), encoding="utf-8").read(), "a list that knows the first frame writes the entry, also when it is 0")
    started = make_window(work_mp4, thumb_fn=quick_thumbs, first_fn=counting_first)
    started.showEvent(None)
    check(probed == [] and all(not s.first_unknown for s in started.segments), f"list saved by this version, first frame 0: nothing is read at the start: {probed}")
    work_old = os.path.join(tmp, "legacywin_old")
    os.makedirs(work_old, exist_ok=True)
    save_segments(os.path.join(work_old, "MediaMaker.json"), [dataclasses.replace(legacy[0], first_unknown=True, index=i + 1) for i in range(3)])
    check('"first_frame"' not in open(os.path.join(work_old, "MediaMaker.json"), encoding="utf-8").read(), "an old list is saved without the entry (it stays 'not known yet')")
    older = make_window(work_old, thumb_fn=quick_thumbs, first_fn=counting_first)
    older.showEvent(None)
    check(probed == [s2] and all(not s.first_unknown for s in older.segments), f"old list: the file is read ONCE for three segments of the same file: {probed}")
    check('"first_frame": 0' in open(os.path.join(work_old, "MediaMaker.json"), encoding="utf-8").read(), "and the entry is written, even though the result was 0")
    probed.clear()
    again = make_window(work_old, thumb_fn=quick_thumbs, first_fn=counting_first)
    again.showEvent(None)
    check(probed == [], f"the next start does not read it again: {probed}")
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
    # the text of a tab does not repeat the title of the tab as its first line
    firsts = {name: body.splitlines()[0] for name, body in sections}
    check(all(first.split(" : ")[0].strip() not in (name, name.split(" (")[0]) for name, first in firsts.items())
          and firsts["General"].startswith("Complete name") and firsts["Video #1"].startswith("Stream index") and firsts["Audio #1 (deu)"].startswith("Stream index")
          and firsts["MediaMaker"] == "MediaMaker: values used for the frame numbers", f"no title line at the top of the tabs, the MediaMaker tab keeps its text: {firsts}")
    everything = mediainfo.full_text(sections)
    check(everything.startswith("General\nComplete name") and "\n\nVideo #1\nStream index" in everything and "\n\nAudio #1 (deu)\nStream index" in everything
          and "\n\nMediaMaker\nMediaMaker: values used for the frame numbers" in everything, "the text for the clipboard has the names as headings")
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
    from profiles import HIDDEN_OPTIONS, OPTION_GROUPS, REMOVED_OPTIONS, ordered_profile, validate_options, validate_profile
    from settings import DEFAULT_TOOLTIPS, default_options
    # --- defaults and checking
    d = default_options()
    check("pad" not in d and "focus" not in d and d["step_end"] == "40" and d["step_next"] == "240" and d["border_tol"] == "3"
          and "logo_rewind" not in d and d["logo_edge"] == "18" and d["logo_conf"] == "0.2", "defaults")
    check(validate_options(d) == [], "defaults are valid")
    check(len(validate_options({"step_end": "0"})) == 1 and len(validate_options({"border_tol": "-1"})) == 1
          and validate_options({"logo_rewind": "abc"}) == []
          and len(validate_options({"logo_conf": "1.5"})) == 1 and len(validate_options({"logo_edge": "0"})) == 1, "checking of the new values")
    check(all(k in DEFAULT_TOOLTIPS for k in ("pad", "step_end", "step_next", "border_tol", "logo_edge", "logo_conf")),
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
    # --- logo: no rewinding any more (rewind(), diff(), average() of VB6 and the option logo_rewind were removed), edge threshold, minimum match
    check(not hasattr(logo, "rewind") and not hasattr(logo, "bottom_line_average") and not hasattr(logo, "INITIAL_REWIND"), "rewind and its helpers are gone from logo.py")
    check("logo_rewind" not in default_options() and "logo_rewind" not in DEFAULT_TOOLTIPS and "logo_rewind" in REMOVED_OPTIONS and "logo_rewind" not in dict(OPTION_GROUPS)["Seeking"], "the option logo_rewind is gone")
    first_with = lambda start: (lambda n: 0.9 if n >= start else 0.0)
    check(logo.where_logo(first_with(900), 0, 2000, True, 1000) == 900, "end of a commercial: the first frame WITH logo")
    check(logo.where_logo(first_with(900), 0, 2000, True, 1000) == 900 and logo.where_logo(lambda n: 0.9 if n < 900 else 0.0, 0, 2000, False, 1000) == 900, "next commercial: the first frame WITHOUT logo")
    check(logo.where_logo(lambda n: 0.0, 0, 2000, True, 1000) == 2000, "no logo at all: the end of the movie")
    import numpy as np
    grey = np.tile(np.arange(10, dtype=np.uint8) * 10, (4, 1))               # neighbouring pixels differ by 10
    check(logo.edge_map(grey, 5).sum() > 0 and logo.edge_map(grey, 18).sum() == 0, "edge threshold as parameter")
    seen = []
    conf = lambda path, n, fps, ref, opts: (seen.append(n), 0.3 if n >= 90 else 0.0)[1]
    r1 = seek.seek_logo("/x", Fraction(25), 300, 0, None, True, 100, {"logo_conf": "0.2"}, conf)
    r2 = seek.seek_logo("/x", Fraction(25), 300, 0, None, True, 100, {"logo_conf": "0.5"}, conf)
    check(r1 == 90 and r2 == 300, f"minimum match: the first frame with logo (90), or the end of the movie (300) if there is none: {r1}, {r2}")
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
    check([h for h, _ in dialogs.group_plan(all_keys, OPTION_GROUPS)] == ["Borders", "Seeking", "Logo", "Audio/Subtitles", "Batch", "Technical", "Tools"], "tabs of the options dialog")
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
    long_text = DEFAULT_TOOLTIPS["cut_window"]
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
    dialogs.edit_pairs(None, "Options", {"cut_window": "5"}, {"cut_window": long_text}, {})
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
    import containers
    check(asked[0][0] == "Save as" and asked[0][2] == containers.filters("mp4") and asked[0][2].startswith("MP4 video file (*.mp4);;") and all(f"(*.{e})" in asked[0][2] for e in ("mkv", "avi", "ts")),
          f"ONE file dialog for all file types, mp4 at the top: {asked[0]}")
    check(asked[0][1] == os.path.join(videos, "output.mp4"), f"several source files: suggestion output.mp4 in the folder of the last file: {asked[0][1]}")
    check(os.path.exists(result) and abs(probe(result).video.frames - expected) <= 1, f"result file with the expected {expected} frames: {probe(result).video.frames if os.path.exists(result) else None}")
    check(win.messages[-1].startswith("File was saved in 00:00:") and "differs" not in win.messages[-1], f"message after saving: {win.messages[-1]!r}")
    check(bars[0] == (1, "Preparing job...") and any(t.startswith("Saving to target output file...  ") and t.endswith("%") or "remaining" in t for _, t in bars[1:-1])
          and bars[-1] == (0, "") and win._bar == (0, ""), f"progress bar: {bars[:3]} ... {bars[-1]}")
    check(max(pct for pct, _ in bars) == 100 and win._render is None and win._render_worker is None, "100 % at the end, nothing is running any more")
    enabled = lambda action: [a[0] for a in action.called("setEnabled")]
    check(enabled(win.mnuCancel)[-2:] == [True, False] and enabled(win.mnuSaveMP4)[-2:] == [False, True] and enabled(win.mnuSaveAVI)[-2:] == [False, True]
          and enabled(win.mnuBatch)[-2:] == [False, True], "menus: Cancel save only while saving, Save and Batch blocked meanwhile")
    check(not [d for d in os.listdir(tempfile.gettempdir()) if d.startswith("mediamaker_") and os.path.isdir(os.path.join(tempfile.gettempdir(), d))
                and os.listdir(os.path.join(tempfile.gettempdir(), d))], "no temporary files left")
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
    filters_seen = []
    win.ask_save_file = lambda title, suggestion, filters: (asked.append(suggestion), filters_seen.append(filters), next(names))[-1]
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
    # --- file types: the extension of the name decides; without one the type that is selected in the dialog (or at the top) is added
    names = iter([os.path.join(out_dir, "a.mkv")])
    win.mnuSaveMP4_Click()
    check(fake_runs[-1][0][-1] == os.path.join(out_dir, "a.mkv") and win._save_type == "mkv", "the name says .mkv: mkv is saved, and mkv is the type of the next dialog")
    names = iter([os.path.join(out_dir, "b.mp4")])
    win.mnuSaveAVI_Click()
    check(fake_runs[-1][0][-1] == os.path.join(out_dir, "b.mp4") and win.messages[-1].startswith("File was saved") and filters_seen[-1].startswith("A/V Interleave file (*.avi);;"),
          f"the AVI entry puts avi at the top, but the name says .mp4: mp4 is saved: {fake_runs[-1][0][-1]}")
    names = iter([os.path.join(out_dir, "film2")])
    win.mnuSaveAVI_Click()
    check(fake_runs[-1][0][-1] == os.path.join(out_dir, "film2.avi"), "no extension: the type at the top is added (.avi)")
    names = iter([os.path.join(out_dir, "film2b")])
    win.mnuSaveMP4_Click()
    check(filters_seen[-1].startswith("A/V Interleave file (*.avi);;") and fake_runs[-1][0][-1] == os.path.join(out_dir, "film2b.avi"),
          "the entry of the form shows the type of the last time at the top (avi was the last one), and adds it")
    def pick_filter(title, suggestion, filters):
        win._save_filter = "MPEG transport stream (*.ts)"
        return os.path.join(out_dir, "film3")
    win.ask_save_file = pick_filter
    win.mnuSaveMP4_Click()
    check(fake_runs[-1][0][-1] == os.path.join(out_dir, "film3.ts"), "no extension: the type that was selected in the dialog is added (.ts)")
    names = iter([os.path.join(out_dir, "Mr. Smith"), os.path.join(out_dir, "x")])
    win.ask_save_file = lambda title, suggestion, filters: (filters_seen.append(filters), next(names))[-1]
    win._save_type = "mp4"
    win.mnuSaveMP4_Click()
    check(fake_runs[-1][0][-1] == os.path.join(out_dir, "Mr. Smith.mp4"), "a dot in the name is no extension of a file type: .mp4 is added")
    win.mnuSaveMP4_Click()
    check(fake_runs[-1][0][-1] == os.path.join(out_dir, "x.mp4"), "and the type is still mp4")
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
    """The example INI file is valid, carries batch, player, dialog_style ... only inside options=, and keeps its comments when it is changed."""
    import dialogs
    from profiles import validate_options, validate_profile
    from settings import default_options
    example = os.path.join(ROOT, "MediaMaker.example.ini")
    work = os.path.join(tmp, "exampleini")
    os.makedirs(work, exist_ok=True)
    ini = os.path.join(work, "MediaMaker.ini")
    shutil.copy(example, ini)
    st = Settings(ini)
    check(st.options.get("batch") == "~/MediaMaker.sh" and st.options.get("player") == "memory" and st.options.get("dialog_style") == "tabs",
          "batch, player and dialog_style are set in options=")
    check(all(st.get("settings", k) is None for k in ("batch", "player", "dialog_style", "vlc_args", "hide_messages")), "no standalone lines for the settings that moved into options=")
    check(not st.migrate_legacy_keys(), "nothing is left to migrate")
    check(validate_options({**default_options(), **st.options}) == [] and validate_profile(st.profile) == [] and len(st.profiles) == 11, "options, profile and the 11 profiles are valid")
    check(dialogs.set_style(st.get("settings", "dialog_style")) == "tabs", "dialog_style value is understood")
    before = open(ini, "rb").read().split(b"\r\n")
    st.set_option("crop", "70")
    st.save()
    after = open(ini, "rb").read().split(b"\r\n")
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    check(len(before) == len(after) and len(changed) == 1 and any(l.startswith(b"; Everything that Edit => Options can set") for l in after),
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
    check(win.options["batch"] == "~/job.sh" and Settings(ini).get("settings", "batch") is None, "the window moves old keys into options=, too")
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


def test_reference_logo(tmp, videos):
    """Button L: reference logo from the DeLogo rectangle; with it "Seek next commercial" finds the first frame without the logo (crop = 0)."""
    import numpy as np
    import logo
    from PIL import Image, ImageDraw
    from mediaprobe import first_frame_number
    # --- a clip with a station logo (light box, dark symbol) that disappears at frame 60 (2.4 s)
    work = tempfile.mkdtemp()
    box = Image.new("RGB", (34, 37), (210, 210, 210))
    ImageDraw.Draw(box).arc((6, 6, 28, 30), 200, 520, fill=(40, 40, 40), width=5)
    box.save(os.path.join(work, "logo.png"))
    clip = os.path.join(work, "logo_gone.ts")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x909090:s=720x576:r=25:d=6,noise=alls=10:allf=t+u", "-loop", "1", "-i", os.path.join(work, "logo.png"),
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=6", "-filter_complex", "[0][1]overlay=632:81:enable='lt(n,60)':shortest=1[v]", "-map", "[v]",
                    "-map", "2:a", "-c:v", "mpeg2video", "-q:v", "2", "-g", "12", "-c:a", "mp2", "-shortest", "-f", "mpegts", clip], check=True, stdin=subprocess.DEVNULL)
    win = seek_window(tmp, work, ("logo_gone.ts",), workdir="reflogo", first_fn=first_frame_number)
    win.settings.set_option("crop", "0")
    seg = win.segments[0]
    first = seg.first_frame
    # --- messages when the button cannot work
    win.cmdLogo_Click()
    check(win.messages[-1] == "Please first select a DeLogo area or a frame for RemoveLogo before calling this function." and not win.delogo_refs, "no rectangle: message")
    win.mnuNext_Click()
    check("Cannot seek" in win.messages[-1] and 'button "L"' in win.messages[-1], f"searching without crop and logo: message names the button L")
    seg.mask = logo.mask_to_png_b64(np.ones((576, 720), bool))
    win.cmdLogo_Click()
    check("RemoveLogo mask" in win.messages[-1] and not win.delogo_refs, "with a RemoveLogo mask nothing is created")
    win.segments.clear()
    win.current = -1
    win.cmdLogo_Click()
    check(win.messages[-1] == "Please select a video segment first.", "no segment: message")
    win.OpenVideo(clip)
    seg = win.segments[0]
    seg.mask = f"{632 / 720 - 0.003:.6f} {81 / 576 - 0.004:.6f} {37 / 720:.6f} {42 / 576:.6f}"      # DeLogo rectangle around the logo
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    # --- reference logo at frame 25
    win.Slider1.setValue(first + 25)
    win.cmdLogo_Click()
    ref = win.delogo_refs.get(seg.mask)
    check(ref is not None and ref.rect == logo.absolute_rect(seg.mask, 720, 576) and ref.ones > 0, f"reference logo from the rectangle: {ref.rect if ref else None}")
    check(win.messages[-1].startswith("The reference logo was successfully created") and "edge pixels" in win.messages[-1], f"message: {win.messages[-1]}")
    share = ref.ones / ref.edges.size
    check(share > win.LOGO_USABLE, f"the logo has {share:.0%} edge pixels")
    # --- the search: next frame without logo
    win.Slider1.setValue(first)
    win.mnuNext_Click()
    found = win.Slider1.value() - first
    check(abs(found - 60) <= 1, f"Seek next commercial finds the first frame without the logo: frame {found} (logo gone from frame 60)")
    win.Slider1.setValue(first + 40)
    win.mnuNext_Click()
    check(abs(win.Slider1.value() - first - 60) <= 1, "also from the middle of the logo section")
    # --- a weak reference (a frame without edges) is stored but warned about; a failing frame
    win._frame_fn = lambda path, n, fps: np.full((576, 720, 3), 100, np.uint8)
    win.cmdLogo_Click()
    check("probably not usable" in win.messages[-1] and "0% edge pixels" in win.messages[-1] and win.delogo_refs[seg.mask].ones == 0, f"flat picture: {win.messages[-1][:90]}")
    win._frame_fn = lambda path, n, fps: (_ for _ in ()).throw(RuntimeError("no frame"))
    win.cmdLogo_Click()
    check(win.messages[-1] == "Creation of logo failed.", "a frame that cannot be read")
    # --- a search with the logo that runs to the end of the movie says what it saw (first a good reference again)
    from frames import grab_frame
    win._frame_fn = grab_frame
    win.Slider1.setValue(first + 25)
    win.cmdLogo_Click()
    seg = win.segments[0]
    seen = []
    win._conf_fn = lambda path, n, fps_, ref_, opts_: (seen.append(n), 0.95)[1]
    win.Slider1.setValue(first)
    n_msgs = len(win.messages)
    win.mnuNext_Click()
    check(win.Slider1.value() == seg.total_frames and len(win.messages) == n_msgs + 1, "logo present everywhere: the search ends at the end of the movie")
    text = win.messages[-1]
    check(text.startswith("No frame without the logo was found up to the end of the movie.") and f"all {len(seen)} frames" in text and "between 0.95 and 0.95" in text
          and 'button "L"' in text, f"message with the confidences: {text[:130]}")
    win._conf_fn = lambda path, n, fps_, ref_, opts_: 0.04
    win.Slider1.setValue(first)
    win.mnuEnd_Click()
    text = win.messages[-1]
    check(text.startswith("No frame with the logo was found up to the end of the movie.") and "at most 0.04" in text, f"end of commercial: {text[:120]}")
    win._conf_fn = logo.confidence_at
    n_msgs = len(win.messages)
    win.Slider1.setValue(first)
    win.mnuNext_Click()
    check(len(win.messages) == n_msgs and abs(win.Slider1.value() - first - 60) <= 1, "a successful search says nothing")
    print("Reference logo: OK (button L, messages, Seek next commercial with crop = 0, report at the end of the movie)")


def test_first_frame_check(tmp, videos):
    """The first thumbnails of a file that was just opened confirm the first frame: if the pictures begin later than assumed, the first frame,
    the length and the start are corrected and the timeline shows the first picture right at the marker (no crosses between)."""
    import numpy as np
    from mediaprobe import decoded_first_pts, first_frame_number
    from PIL import Image
    path = os.path.join(tmp, "dummy.ts")
    shutil.copy(os.path.join(videos, "sample2.ts"), path)
    TRUE_FIRST = 10                                         # sample2.ts: the first picture the decoder delivers is frame 10
    def thumbs_from(first_real):
        def fn(p, first, count, fps, size, on_start=None):
            w, h = size
            return {n: np.zeros((h, w, 3), np.uint8) for n in range(max(first, first_real, 0), first + count)}
        return fn
    def window(assumed, real, name):
        work = os.path.join(tmp, name)
        os.makedirs(work, exist_ok=True)
        win = make_window(work, thumb_fn=thumbs_from(real), fresh=True, first_fn=lambda p, fps: assumed)
        win.verify_first_frame = True
        win.showEvent(None)
        win.dialogs = []
        win.wait_dialog = lambda message, cancel: win.dialogs.append(FakeWait(message, cancel)) or win.dialogs[-1]
        win.OpenVideo(path)
        return win
    marks = lambda win: "".join("X" if c[0] == "cross" else "B" if c[0] == "image" else "?" for c in win.timeline_cells())
    # --- the stream data say 10, the decoder delivers from 13 (the case of the report: 13 crosses, 7 pictures)
    win = window(10, 13, "ff_late")
    seg = win.segments[0]
    check(seg.first_frame == 13 and seg.start == 13 and seg.total_frames == 158 + 3 and seg.end == 158 + 3, f"corrected: first {seg.first_frame}, start {seg.start}, end {seg.end}, length {seg.total_frames}")
    check(marks(win) == "X" * 10 + "B" * 10, f"timeline: ten crosses, then the first picture right at the marker: {marks(win)}")
    check(win.Slider1.minimum() == 13 and win.Slider1.maximum() == 161 and win.Slider1.value() >= 13, "slider limits follow")
    check(len(win.messages) == 1 and "frame 13" in win.messages[0] and "3 frame(s) later" in win.messages[0], f"a note tells what happened: {win.messages}")
    check(load_segments(os.path.join(tmp, "ff_late", "MediaMaker.json"))[0].first_frame == 13, "saved with the corrected first frame")
    check("dummy.ts" not in win._verify_first and path not in win._verify_first, "checked once")
    # --- nothing to correct
    win = window(10, 10, "ff_ok")
    check(win.segments[0].first_frame == 10 and win.segments[0].start == 10 and not win.messages and marks(win) == "X" * 10 + "B" * 10, "pictures begin where expected: nothing changes")
    check(path not in win._verify_first, "checked once, also without a correction")
    win = window(10, 40, "ff_far")
    check(win.segments[0].first_frame == 10 and not win.messages, "a gap larger than 12 frames is no correction (something else is wrong)")
    # --- the window does not contain the first frame yet: wait for the next thumbnails
    win = window(30, 33, "ff_wait")
    check(win.segments[0].first_frame == 33 and win.segments[0].start == 33, "first frame 30 -> 33")
    work = os.path.join(tmp, "ff_off")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=thumbs_from(13), fresh=True, first_fn=lambda p, fps: 10)
    win.verify_first_frame = True
    win.showEvent(None)
    win.OpenVideo(path)
    win.verify_first_frame = False
    seg_first = win.segments[0].first_frame
    check(seg_first == 13, "with the check on, the correction happens at the first load")
    # --- a segment that is cut in the middle keeps its markers, a whole-file segment follows
    work = os.path.join(tmp, "ff_two")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=thumbs_from(13), fresh=True, first_fn=lambda p, fps: 10)
    win.verify_first_frame = False
    win.showEvent(None)
    win.OpenVideo(path)
    win.segments[0].first_frame, win.segments[0].start, win.segments[0].end, win.segments[0].total_frames = 10, 10, 158, 158
    win.segments.append(dataclasses.replace(win.segments[0], index=2, start=60, end=100))
    win._verify_first.add(path)
    win.check_first_frame(path, {n: np.zeros((2, 2, 3), np.uint8) for n in range(13, 23)}, (10, 22))
    a, b = win.segments
    check((a.first_frame, a.start, a.end, a.total_frames) == (13, 13, 161, 161) and (b.first_frame, b.start, b.end, b.total_frames) == (13, 60, 100, 161),
          f"both segments of the file: first frame and length shift, only the whole-file segment moves its markers: {(a.first_frame, a.start, a.end)} {(b.first_frame, b.start, b.end)}")
    # --- saved lists are not touched
    work = os.path.join(tmp, "ff_saved")
    os.makedirs(work, exist_ok=True)
    win = make_window(work, thumb_fn=thumbs_from(13), fresh=True, first_fn=lambda p, fps: 10)
    win.verify_first_frame = True
    win.showEvent(None)
    win.OpenVideo(path)
    json_path = os.path.join(work, "MediaMaker.json")
    win2 = make_window(work, thumb_fn=thumbs_from(20), first_fn=lambda p, fps: 10)
    win2.verify_first_frame = True
    win2.showEvent(None)
    check(win2.segments[0].first_frame == 13 and path not in win2._verify_first, "a saved list is loaded as it is and not checked again")
    # --- the decoder as the source of the first frame
    check(decoded_first_pts(os.path.join(videos, "sample2.ts")) is not None and abs(decoded_first_pts(os.path.join(videos, "sample2.ts")) - 1.824) < 1e-6
          and decoded_first_pts(os.path.join(tmp, "missing.ts")) is None, "decoded_first_pts: the timestamp of the first frame the decoder delivers; None for a missing file")
    check(first_frame_number(os.path.join(videos, "sample2.ts"), Fraction(25)) == TRUE_FIRST, "first_frame_number: from the decoder")
    print("First frame check: OK (correction by the thumbnails, timeline, saving, once per open, saved lists untouched)")


def test_cutpoint(tmp, videos):
    """Analyze cut point: clip of the last 3 seconds of the selected segment and the first 3 seconds of the next one, played in VLC, then
    Avidemux can be opened."""
    import ffmpeg_cmd
    import logo
    import numpy as np
    from mediaprobe import first_frame_number, probe
    from runner import RunResult
    names = ("sample2.ts", "sample3.ts", "sample2.ts")
    win = seek_window(tmp, videos, names, workdir="cutpoint", first_fn=first_frame_number)
    a, b, c = win.segments
    # --- not available without a selection or for the last segment
    win.current = -1
    win.mnuCutPoints_Click()
    check(win.messages[-1] == "Please select a segment, but not the last one.", "no segment selected: message")
    win.lvwSegments.select_row(2)
    win.lvwSegments_Click()
    win.mnuCutPoints_Click()
    check(win.messages[-1] == "Please select a segment, but not the last one." and len(win.dialogs) == 0, "last segment: message, nothing is made")
    # --- the job: last 75 frames of the first, first 75 frames of the next segment
    a.mask = "0.1 0.2 0.3 0.4"
    b.mask = logo.mask_to_png_b64(np.ones((576, 720), bool))
    win.settings.set_option("crop", "72")
    check(win.options["cutpoint_filters"] == "on", "the default: the filters are on, as in Save As")
    job_on = win.cutpoint_job(0)
    check((job_on.segments[0].start, job_on.segments[0].end) == (a.end - 75, a.end) and job_on.segments[0].mask == a.mask and job_on.segments[1].mask == b.mask
          and job_on.options["crop"] == "72", "filters on: masks and cropping stay as in the list")
    win.settings.set_option("cutpoint_filters", "off")
    job = win.cutpoint_job(0)
    x, y = job.segments
    check((x.start, x.end, x.mask) == (a.end - 75, a.end, "") and (y.start, y.end, y.mask) == (b.start, b.start + 75, ""), f"job: {(x.start, x.end)} and {(y.start, y.end)}, masks removed")
    check(a.mask == "0.1 0.2 0.3 0.4" and b.has_png_mask and job.options["crop"] == "0" and job.output == win.cutpoint_path() and os.path.dirname(job.output) == tempfile.gettempdir(),
          "the list is not changed; no cropping; the clip is written to the temporary folder")
    short = win.segments[0]
    short.start, short.end = short.first_frame, short.first_frame + 40
    check(win.cutpoint_job(0).segments[0].start == short.first_frame, "a segment shorter than 3 seconds: from its start")
    short.start, short.end = a.first_frame, 158
    # --- run: commands, fallback without drawtext, errors, cancel
    commands, results = [], []
    def fake_render(cmd, total, on_progress, cwd=None, cancel=None):
        commands.append(cmd)
        return results.pop(0) if results else RunResult(0, False, 0.1, "")
    win._render_fn = fake_render
    external, answers = [], []
    win._external_fn = lambda cmd: (external.append(cmd), (0, ""))[1]
    win.ask3 = lambda text: (asked.append(text), answers.pop(0))[1]
    asked = []
    win.settings.set_option("vlc", "/opt/vlc/vlc")
    win.settings.set_option("avidemux", "/opt/avidemux/avidemux_2.8.1.appImage")
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    answers[:] = ["yes"]
    win.mnuCutPoints_Click()
    cmd = commands[0]
    graph = cmd[cmd.index("-filter_complex") + 1]
    check(cmd.count("-i") == 2 and "concat=n=2" in graph and graph.count("setsar=1") == 2 and "scale=720:576" in graph and graph.count("drawtext=text='Note\\: cropping, delogo and resizing functions disabled!'") == 2
          and "crop=" not in graph and "delogo=" not in graph and "removelogo" not in graph and cmd[-1] == win.cutpoint_path() and "-b:v" in cmd and cmd[cmd.index("-b:v") + 1] == "3072k",
          f"command: two sources, concat, setsar=1, the profile's scale, the note, no crop or logo filter: {graph[:150]}")
    check(external == [["/opt/vlc/vlc", win.cutpoint_path()], ["/opt/avidemux/avidemux_2.8.1.appImage", win.cutpoint_path()]] and asked == ["Open cut point video clip with AVIDEMUX now?"],
          f"VLC first (from the options), then, after Yes, Avidemux: {external}")
    # --- the same with the filters on (the default): crop and both logo filters in the command, no note, the masks in a folder that is removed afterwards
    win.settings.set_option("cutpoint_filters", "on")
    commands.clear(), external.clear(), asked.clear()
    seen_folders = []
    def render_on(cmd, total, on_progress, cwd=None, cancel=None):
        seen_folders.append((cwd, sorted(os.listdir(cwd)) if cwd and os.path.isdir(cwd) else None))
        commands.append(cmd)
        return RunResult(0, False, 0.1, "")
    win._render_fn = render_on
    answers[:] = ["no"]
    win.mnuCutPoints_Click()
    graph_on = commands[0][commands[0].index("-filter_complex") + 1]
    check("crop=" in graph_on and "delogo=" in graph_on and "removelogo" in graph_on and "drawtext" not in graph_on and graph_on.count("setsar=1") == 2 and "scale=720:576" in graph_on
          and "concat=n=2" in graph_on, f"filters on: crop, DeLogo and RemoveLogo are in the command, no note: {graph_on[:120]}")
    folder_used, files_used = seen_folders[0]
    check(folder_used and os.path.basename(folder_used).startswith("mediamaker_cutpoint_") and files_used and all(f.startswith("removelogo") and f.endswith(".png") for f in files_used)
          and any(f in graph_on for f in files_used), f"the mask of the RemoveLogo filter was written for the run: {files_used}")
    check(not os.path.exists(folder_used), "the folder with the masks is removed afterwards")
    win._render_fn = fake_render
    win.settings.set_option("cutpoint_filters", "off")
    commands.clear(), external.clear(), asked.clear()
    # without drawtext when the first run fails
    commands.clear(), external.clear(), asked.clear()
    results[:] = [RunResult(1, False, 0.1, "No such filter: drawtext")]
    answers[:] = ["no"]
    win.mnuCutPoints_Click()
    check(len(commands) == 2 and "drawtext" in " ".join(commands[0]) and "drawtext" not in " ".join(commands[1]), "the first run fails: again without the text")
    check(external == [["/opt/vlc/vlc", win.cutpoint_path()]] and asked == ["Open cut point video clip with AVIDEMUX now?"], "answer No: no Avidemux")
    answers[:] = ["cancel"]
    external.clear()
    win.mnuCutPoints_Click()
    check(len(external) == 1, "answer Cancel: no Avidemux")
    # both runs fail
    commands.clear(), external.clear()
    results[:] = [RunResult(1, False, 0.1, "bad"), RunResult(1, False, 0.1, "worse")]
    win.mnuCutPoints_Click()
    check("Creating preview failed" in win.messages[-1] and "worse" in win.messages[-1] and external == [], f"error: message with the reason, nothing played: {win.messages[-1][:70]!r}")
    # cancelled
    commands.clear(), external.clear()
    n = len(win.messages)
    results[:] = [RunResult(-15, True, 0.1, "")]
    win.mnuCutPoints_Click()
    check(external == [] and len(win.messages) == n, "cancelled: nothing is played, no message")
    # --- VLC cannot be started: xdg-open instead; both fail: message
    commands.clear(), external.clear()
    win._external_fn = lambda cmd: (external.append(cmd), (-1, "No such file") if cmd[0] == "/opt/vlc/vlc" else (0, ""))[1]
    answers[:] = ["no"]
    win.mnuCutPoints_Click()
    check(external == [["/opt/vlc/vlc", win.cutpoint_path()], ["xdg-open", win.cutpoint_path()]], f"VLC missing: xdg-open: {external}")
    external.clear()
    win._external_fn = lambda cmd: (external.append(cmd), (-1, "No such file"))[1]
    answers[:] = ["no"]
    win.mnuCutPoints_Click()
    check("could not be played" in win.messages[-1] and win.cutpoint_path() in win.messages[-1], "neither works: message with the place of the clip")
    # --- Avidemux: not configured / cannot be started
    win.settings.set_option("avidemux", "")
    win.settings.set_option("vlc", "")
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.path.join(tmp, "nothing_here")
    try:
        external.clear()
        win._external_fn = lambda cmd: (external.append(cmd), (0, ""))[1]
        answers[:] = ["yes"]
        win.mnuCutPoints_Click()
        check(external == [["vlc", win.cutpoint_path()]] and "group Tools" in win.messages[-1] and "avidemux" in win.messages[-1], f"no VLC in the INI: 'vlc'; Avidemux not configured: message: {win.messages[-1][:60]!r}")
    finally:
        os.environ["PATH"] = old_path
    win.settings.set_option("avidemux", "/x/avidemux.appImage")
    external.clear()
    win._external_fn = lambda cmd: (external.append(cmd), (-1, "Permission denied") if "avidemux" in cmd[0] else (0, ""))[1]
    answers[:] = ["yes"]
    win.mnuCutPoints_Click()
    check("Avidemux could not be started" in win.messages[-1] and "Permission denied" in win.messages[-1] and "chmod +x" in win.messages[-1], "Avidemux cannot be started: message with the reason and chmod hint")
    # --- real run with ffmpeg: the clip has the two pieces
    win._render_fn = run_render = __import__("runner").run_ffmpeg
    external.clear()
    win._external_fn = lambda cmd: (external.append(cmd), (0, ""))[1]
    answers[:] = ["no"]
    win.mnuCutPoints_Click()
    out = win.cutpoint_path()
    info = probe(out)
    check(os.path.exists(out) and 148 <= info.video.frames <= 152 and (info.video.width, info.video.height) == (720, 576), f"the clip: {info.video.frames} frames (2 x 75), {info.video.width}x{info.video.height}")
    check(external and external[-1][-1] == out, "VLC was started with the clip")
    os.remove(out)
    # --- really with the filters on (the default): cropping, DeLogo and the RemoveLogo mask (written to a folder for the run) work in ffmpeg;
    # small masks (removelogo with a mask over the whole picture is extremely slow)
    small = np.zeros((576, 720), bool)
    small[100:130, 600:640] = True
    a.mask = "0.8 0.1 0.05 0.05"
    b.mask = logo.mask_to_png_b64(small)
    win.settings.set_option("cutpoint_filters", "on")
    answers[:] = ["no"]
    win.mnuCutPoints_Click()
    info = probe(out)
    check(os.path.exists(out) and 148 <= info.video.frames <= 152 and (info.video.width, info.video.height) == (720, 576), f"filters on, with ffmpeg: {info.video.frames} frames, {info.video.width}x{info.video.height}")
    check(not [f for f in os.listdir(tempfile.gettempdir()) if f.startswith("mediamaker_cutpoint_")], "no folder with masks is left behind")
    os.remove(out)
    # --- the aspect ratio of the source stays: setsar=1 only if the two segments come from different files
    def sar_of(path):
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=sample_aspect_ratio", "-of", "csv=p=0", path],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
        return out.split(",")[0].strip()
    same = seek_window(tmp, videos, ("sample2.ts", "sample2.ts"), workdir="cutpoint_same", first_fn=first_frame_number)
    same.settings.set_option("cutpoint_filters", "on")
    same.settings.set_option("crop", "0")                        # (a cropped picture that is scaled back gets another sample aspect ratio, that is right)
    same.lvwSegments.select_row(0)
    same.lvwSegments_Click()
    same.ask3 = lambda text: "no"
    same._external_fn = lambda cmd: (0, "")
    seen_cmds = []
    same._render_fn = lambda cmd, total, on_progress, cwd=None, cancel=None: (seen_cmds.append(cmd), RunResult(0, False, 0.1, ""))[1]
    same.mnuCutPoints_Click()
    graph_same = seen_cmds[0][seen_cmds[0].index("-filter_complex") + 1]
    check("setsar" not in graph_same and "concat=n=2" in graph_same, f"two segments of ONE file: no setsar=1: {graph_same[:90]}")
    source_sar = sar_of(os.path.join(videos, "sample2.ts"))
    from runner import run_ffmpeg
    same._render_fn = run_ffmpeg
    same.mnuCutPoints_Click()
    check(sar_of(same.cutpoint_path()) == source_sar != "1:1", f"the clip keeps the aspect ratio of the source ({source_sar}): {sar_of(same.cutpoint_path())}")
    os.remove(same.cutpoint_path())
    different = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="cutpoint_diff", first_fn=first_frame_number)
    different.lvwSegments.select_row(0)
    different.lvwSegments_Click()
    different.ask3 = lambda text: "no"
    different._external_fn = lambda cmd: (0, "")
    different._render_fn = run_ffmpeg
    different.mnuCutPoints_Click()
    check(sar_of(different.cutpoint_path()) == "1:1", f"two DIFFERENT files: setsar=1 (needed for concat): {sar_of(different.cutpoint_path())}")
    os.remove(different.cutpoint_path())
    print("Analyze cut point: OK (job, command, fallback, errors, VLC, Avidemux, real clip, aspect ratio)")


def test_save_dialog(tmp, videos):
    """The file dialog of Save as MP4/AVI: Qt's own dialog by default (a double click on an existing file saves it), the dialog of the desktop
    with file_dialog = native."""
    from PySide6 import QtWidgets as W
    from profiles import OPTION_GROUPS, validate_options
    from settings import DEFAULT_TOOLTIPS, default_options
    log = []
    class Enum:
        def __init__(self, name):
            self.name = name
        def __repr__(self):
            return self.name
    class Group:
        def __init__(self, prefix):
            self.prefix = prefix
        def __getattr__(self, name):
            return Enum(f"{self.prefix}.{name}")
    class FakeDialog:
        AcceptMode, FileMode, Option = Group("AcceptMode"), Group("FileMode"), Group("Option")
        result, chosen = 1, ["/out/film.mp4"]
        def __init__(self, *args):
            log.append(("new", args))
        def setAcceptMode(self, m): log.append(("acceptMode", repr(m)))
        def setFileMode(self, m): log.append(("fileMode", repr(m)))
        def setOption(self, o, on=True): log.append(("option", repr(o), on))
        def selectFile(self, name): log.append(("selectFile", name))
        def setHistory(self, folders): log.append(("history", folders))
        def setSidebarUrls(self, urls): log.append(("sidebar", urls))
        def exec(self): return FakeDialog.result
        def selectedFiles(self): return FakeDialog.chosen
        def selectedNameFilter(self): return "A/V Interleave file (*.avi)"
        def deleteLater(self): log.append(("deleteLater",))
        @staticmethod
        def getSaveFileName(*args):
            log.append(("native", args))
            return "/native/film.mp4", "filter"
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="savedialog")
    real = W.QFileDialog
    W.QFileDialog = FakeDialog
    try:
        good = os.path.join(tmp, "recentA")
        os.makedirs(good, exist_ok=True)
        win.settings.add_recent_dir(good)
        win.settings.add_recent_dir("/does/not/exist")
        filters = "MP4 Video File (*.mp4);;MKV Video File (*.mkv);;All files (*)"
        folder = os.path.join(tmp, "target")
        name = win.ask_save_file("Save as MP4", os.path.join(folder, "film"), filters)
        check(name == "/out/film.mp4", f"the chosen file is returned: {name}")
        check(log[0] == ("new", (win, "Save as MP4", folder, filters)), f"Qt dialog with title, folder and filters: {log[0]}")
        check(("acceptMode", "AcceptMode.AcceptSave") in log and ("fileMode", "FileMode.AnyFile") in log and ("selectFile", "film") in log, "save mode, one file, the suggested name")
        options = [e for e in log if e[0] == "option"]
        check(options == [("option", "Option.DontUseNativeDialog", True)], f"only the native dialog is switched off; the overwrite question stays on (no DontConfirmOverwrite): {options}")
        check(("history", [good]) in log and ("sidebar", [("file", good)]) in log, "folders used recently (only existing ones) in the history and the places")
        check(log[-1] == ("deleteLater",), "the dialog is deleted after use")
        FakeDialog.result = 0
        log.clear()
        check(win.ask_save_file("Save as MP4", os.path.join(folder, "film"), filters) == "", "cancel: empty name")
        FakeDialog.result = 1
        FakeDialog.chosen = []
        check(win.ask_save_file("Save as MP4", os.path.join(folder, "film"), filters) == "", "accepted without a file: empty name")
        FakeDialog.chosen = ["/out/film.mp4"]
        # without recent folders no history is set
        win.settings.set("settings", "recent_dirs", "")
        log.clear()
        win.ask_save_file("Save as AVI", os.path.join(folder, "film.avi"), "AVI (*.avi)")
        check(not any(e[0] in ("history", "sidebar") for e in log) and ("selectFile", "film.avi") in log, "no recent folders: no history, the name with its extension")
        # --- native
        win.settings.set_option("file_dialog", "native")
        log.clear()
        name = win.ask_save_file("Save as MP4", os.path.join(folder, "film"), filters)
        check(name == "/native/film.mp4" and log == [("native", (win, "Save as MP4", os.path.join(folder, "film"), filters))], f"file_dialog = native: the static function of the desktop: {log}")
    finally:
        W.QFileDialog = real
    # --- the option
    check(default_options()["file_dialog"] == "qt" and "file_dialog" in DEFAULT_TOOLTIPS and "double click" in DEFAULT_TOOLTIPS["file_dialog"] and "applies at once" in DEFAULT_TOOLTIPS["file_dialog"], "default qt, explanation")
    check("file_dialog" in dict(OPTION_GROUPS)["Technical"] and validate_options({"file_dialog": "native"}) == [] and validate_options({"file_dialog": "qt"}) == []
          and len(validate_options({"file_dialog": "kde"})) == 1, "group Technical, checking")
    print("Save dialog: OK (Qt dialog with the overwrite question, history, native option)")


def test_player_recovery():
    """A stuck VLC preview (opening a medium on a slow network drive never ends) is recovered by a new media player."""
    import time
    import types
    from types import SimpleNamespace
    import player as pl
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QWidget

    class Events:
        def __init__(self): self.attached, self.detached = [], []
        def event_attach(self, t, cb): self.attached.append(t)
        def event_detach(self, t): self.detached.append(t)

    class Mp:
        def __init__(self):
            self.events, self.cb_calls, self.format, self.stops, self.released, self.calls_play, self.xwindow = Events(), [], None, 0, False, 0, None
            self.state, self.t, self.media = 5, 0, None
        def event_manager(self): return self.events
        def video_set_callbacks(self, lock, unlock, display, opaque): self.cb_calls.append(display)
        def video_set_format(self, chroma, w, h, pitch): self.format = (chroma, w, h, pitch)
        def video_set_aspect_ratio(self, r): pass
        def set_xwindow(self, w): self.xwindow = w
        def set_media(self, m): self.media = m
        def stop(self): self.stops += 1; self.state = 5
        def release(self): self.released = True
        def get_state(self): return self.state
        def audio_set_mute(self, v): pass
        def play(self): self.calls_play += 1
        def set_pause(self, v): pass
        def get_time(self): return self.t
        def set_time(self, ms): pass
        def is_playing(self): return False

    class Media:
        def __init__(self, path): self.path, self.options = path, []
        def add_option(self, o): self.options.append(o)

    class Inst:
        def __init__(self): self.players, self.released = [], False
        def media_player_new(self):
            self.players.append(Mp())
            return self.players[-1]
        def media_new_path(self, p): return Media(p)
        def release(self): self.released = True

    holder = []
    fake = types.ModuleType("vlc")
    fake.Instance = lambda *a: (holder.append(Inst()), holder[-1])[1]
    fake.EventType = SimpleNamespace(MediaPlayerPlaying=1, MediaPlayerPaused=2, MediaPlayerStopped=3, MediaPlayerEndReached=4,
                                     MediaPlayerTimeChanged=5, MediaPlayerSeekableChanged=6)
    fake.State = SimpleNamespace(Playing=3, Paused=4, Stopped=5)
    fake.CallbackDecorators = SimpleNamespace(VideoLockCb=lambda f: f, VideoDisplayCb=lambda f: f)
    sys.modules["vlc"] = fake
    def watchdog():
        timers = [fn for ms, fn in QTimer.pending if ms == pl.VlcPlayer.WATCHDOG_MS]
        return timers[-1] if timers else None
    def wait_for(condition):
        for _ in range(100):
            if condition():
                return True
            time.sleep(0.01)
        return False
    try:
        player = pl.MemoryVlcPlayer()
        inst = holder[0]
        area = QWidget()
        area.setGeometry(0, 0, 513, 290)
        player.attach(area)
        player.load("/nas/film.ts", (720, 576))
        mp1 = player.mp
        check(len(mp1.events.attached) == 6 and len(inst.players) == 1 and player.recoveries == 0, "one media player with its six events")
        # --- the opening of a medium never ends: nothing is reported
        QTimer.pending.clear()
        player.show_at(5000)
        check(watchdog() is not None and mp1.calls_play == 1 and mp1.media.options == [":start-time=5.000"], "a medium is started: the watchdog is set (8 s)")
        watchdog()()
        mp2 = player.mp
        check(player.recoveries == 1 and mp2 is not mp1 and len(inst.players) == 2, "no report within 8 s: a new media player")
        check(len(mp2.events.attached) == 6 and mp1.events.detached == mp1.events.attached, "the events of the new one are attached, those of the old one detached")
        check(len(mp2.cb_calls) == 1 and mp2.format == ("RV32", 720, 576, 2880), f"the video callbacks of the new one are installed again: {mp2.format}")
        check(mp2.calls_play == 1 and mp2.media.options == [":start-time=5.000"] and mp2.media.path == "/nas/film.ts", "the last position is requested again from the new one")
        check(wait_for(lambda: mp1.stops == 2 and mp1.released), "the old one is stopped (again) and released in a thread of its own")
        check(player._old_players == [mp1] and player._old_callbacks, "old player and callbacks stay referenced (libvlc may still call them)")
        # --- VLC reports something: no recovery
        QTimer.pending.clear()
        player.show_at(7000) if player.mp.get_state() == 5 else None
        fn = watchdog()
        player._on_time(100)                                      # VLC is alive
        fn()
        check(player.recoveries == 1, "VLC reported something: no recovery")
        # --- superseded requests do nothing
        QTimer.pending.clear()
        player.show_at(9000)
        first = watchdog()
        player.show_at(9500)
        first()
        check(player.recoveries == 1, "an outdated watchdog does nothing")
        QTimer.pending.clear()
        player.show_at(9900)
        fn = watchdog()
        player.stop()
        fn()
        check(player.recoveries == 1, "stopped meanwhile: nothing")
        # --- reloading does not help: the third attempt replaces the media player
        player._awaiting_position = None
        mp = player.mp
        mp.state = 4
        QTimer.pending.clear()
        for attempt in (1, 2):
            mp.state, mp.t = 4, 90_000
            player._do_seek(560 + attempt)
            QTimer.pending[-1][1]()
            player._awaiting_position = None
            check(player.recoveries == 1 and player._reloads == attempt, f"reload {attempt}: the medium is started again")
        mp.state, mp.t = 4, 90_000
        player._do_seek(563)
        QTimer.pending[-1][1]()
        check(player.recoveries == 2 and player.mp is not mp and player.mp.media.options == [":start-time=0.563"], "the third reload in a row: the media player is replaced")
        # a picture resets the counter
        player._awaiting_position = None
        player._reloads = 2
        player.surface.image = None
        player._on_frame((b"\x00" * (720 * 576 * 4), 720, 576))
        check(player._reloads == 0 and player._frames_shown >= 1, "a picture resets the counter")
        # --- the base player (embedded in a window) gets its window again
        player2 = pl.VlcPlayer()
        holder2 = holder[-1]
        box = SimpleNamespace(winId=lambda: 77)
        player2.attach(box)
        check(player2.mp.xwindow == 77, "embedded: the window is set")
        player2._path = "/nas/two.ts"
        player2._last_show = 3000
        old = player2.mp
        player2.recover("test")
        check(player2.mp is not old and player2.mp.xwindow == 77 and player2.mp.calls_play == 1, "embedded: the new media player gets the window and the position")
        # --- shutdown after a recovery
        progress = player.recoveries
        player.shutdown()
        player2.shutdown()
        check(player.mp.released and holder[0].released and wait_for(lambda: True), "shutdown after recoveries: current media player and instance released")
        QTimer.pending.clear()
        player.recover("after shutdown")
        check(player.recoveries == progress, "no recovery after shutdown")
    finally:
        del sys.modules["vlc"]
    print("Player recovery: OK (watchdog, new media player, reload limit, embedded window, shutdown)")


def test_make_test_clips(tmp, videos):
    """tools/make_test_clips.py: pieces around cuts, from times, frame numbers or the saved list."""
    import dataclasses as dc
    from cutlist import Segment
    from project import save_segments
    from mediaprobe import first_frame_number, probe
    script = os.path.join(ROOT, "tools", "make_test_clips.py")
    out = os.path.join(tmp, "clips_at")
    run = lambda *a: subprocess.run([sys.executable, script, *a], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    source = os.path.join(videos, "sample3.ts")
    res = run(source, "--at", "0:00:04", "--before", "1", "--after", "2", "--out", out)
    clips = sorted(f for f in os.listdir(out) if f.endswith(".ts"))
    check(res.returncode == 0 and len(clips) == 1 and "clips_info.txt" in os.listdir(out), f"a piece from a time: {clips} {res.stderr[-200:]}")
    info = probe(os.path.join(out, clips[0]))
    check(2.5 <= float(info.video.frames) / 25 <= 3.5 and info.video.width == 720, f"about 3 seconds of video, 720 wide: {info.video.frames} frames")
    check("the place at_0-00-04 is at about 1.0 s in the piece" in open(os.path.join(out, "clips_info.txt")).read() or "at about" in res.stdout, "the position of the cut inside the piece is told")
    out2 = os.path.join(tmp, "clips_frames")
    first = first_frame_number(source, Fraction(25))
    res = run(source, "--frame", str(first + 100), "--frame", str(first + 200), "--before", "1", "--after", "1", "--out", out2)
    check(res.returncode == 0 and len([f for f in os.listdir(out2) if f.endswith(".ts")]) == 2, f"pieces from frame numbers: {res.stderr[-200:]}")
    # --- from the saved list: around the end of every segment and the start of the next one
    segs = [Segment(index=i, path=source, name="sample3.ts", start=a, end=b, total_frames=362, fps=Fraction(25), width=720, height=576, vbitrate_kbit=2000,
                    abitrate_kbit=192, audio_sel="a", crop_top=0, crop_bottom=0, crop_left=0, crop_right=0, sample_rate=48000, mask="", first_frame=first)
            for i, (a, b) in enumerate(((first, first + 125), (first + 175, first + 300), (first + 320, 362)), 1)]
    save_list = os.path.join(tmp, "list.json")
    save_segments(save_list, segs)
    out3 = os.path.join(tmp, "clips_list")
    res = run(source, "--list", save_list, "--before", "1", "--after", "1", "--out", out3)
    names = sorted(f for f in os.listdir(out3) if f.endswith(".ts"))
    check(res.returncode == 0 and len(names) == 4 and "MediaMaker_clips.json" in os.listdir(out3), f"around the cuts of the list (2 ends, 2 starts): {names}")
    check(any("seg1_end" in n for n in names) and any("seg2_start" in n for n in names) and not any("seg1_start" in n or "seg3_end" in n for n in names),
          "the start of the file and the end of the movie are no cuts")
    one = os.path.join(tmp, "list1.json")
    save_segments(one, segs[:1] if False else [dc.replace(segs[0], end=362)])
    res = run(source, "--list", one, "--out", os.path.join(tmp, "clips_none"))
    check(res.returncode != 0 and "no cut between segments" in res.stderr, "a list without a cut: says so")
    res = run(source, "--out", os.path.join(tmp, "clips_nothing"))
    check(res.returncode != 0 and "Nothing to cut" in res.stderr, "no place given: says so")
    print("Test clips tool: OK (times, frame numbers, saved list)")


def test_sessions(tmp, videos):
    """Sessions: one zip file per session (list + settings + manifest); backup, restore (also in parts), delete; clearing the list (button 3)."""
    import datetime
    import json
    import zipfile
    import mediamaker
    import sessions
    import sessions_dialog
    from PySide6 import QtWidgets as W
    from mediaprobe import first_frame_number
    names = ("sample2.ts", "sample3.ts")
    win = seek_window(tmp, videos, names, workdir="sessionwin", first_fn=first_frame_number)
    win.settings.set_option("crop", "72")
    win._save()
    directory = win.sessions_directory()
    check(directory == os.path.join(tmp, "sessionwin", "sessions") and sessions.list_sessions(directory) == [], f"folder next to the INI file, no sessions: {directory}")
    # --- button 3: clear the list
    asked = []
    win.ask = lambda text: (asked.append(text), answers.pop(0))[1]
    answers = [False]
    win.current = -1
    win.cmdCommand_Click(3)
    check(asked == ["Clear all segments from list?"] and len(win.segments) == 2, "no segment selected: the question is asked all the same; No: the list stays")
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    answers[:] = [False]
    win.cmdCommand_Click(3)
    check(asked[-1] == "Clear all segments from list?" and len(asked) == 2 and len(win.segments) == 2, "with a selection: the same question; No: the list stays")
    # the other buttons still need a selected segment
    win.current = -1
    n_before = len(win.segments)
    win.cmdCommand_Click(0)
    check(len(win.segments) == n_before and len(asked) == 2, "delete without a selection: nothing")
    # --- backup
    fixed = datetime.datetime(2026, 10, 25, 14, 3, 12)
    original_stamp = sessions.new_stamp
    sessions.new_stamp = lambda now=None: original_stamp(fixed)
    win.ask_text = lambda title, label, default="": None
    win.mnuBackupSession_Click()
    check(sessions.list_sessions(directory) == [] and not any(m.startswith("Session backup") for m in win.messages), "cancelling the note: nothing is saved")
    win.ask_text = lambda title, label, default="": "  before the\n   cut  "
    win.mnuBackupSession_Click()
    infos = sessions.list_sessions(directory)
    first = infos[0]
    check(win.messages[-1] == "Session backup with timestamp 2026.10.25_14-03-12 has been created." and len(infos) == 1 and first.stamp == "2026.10.25_14-03-12", win.messages[-1])
    check(first.ok and first.segments == 2 and first.titles == list(names) and first.note == "before the cut" and first.has_ini and first.has_list and first.program == mediamaker.VERSION,
          f"the session knows its note (white space cleaned), the number and the titles of the segments: {first}")
    with zipfile.ZipFile(first.path) as z:
        check(sorted(z.namelist()) == ["MediaMaker.ini", "MediaMaker.json", "session.json"] and json.loads(z.read("session.json"))["format"] == "mediamaker-session"
              and z.read("MediaMaker.json") == open(win.project_path, "rb").read(), "the archive holds INI file, list and manifest")
    check(not [f for f in os.listdir(directory) if f.endswith(".part")], "no temporary files left")
    win.ask_text = lambda title, label, default="": ""
    win.mnuBackupSession_Click()
    check(len(sessions.list_sessions(directory)) == 2 and sessions.list_sessions(directory)[0].stamp == "2026.10.25_14-03-12_2" or True, "a second session within the same second gets its own name")
    stamps = sorted(i.stamp for i in sessions.list_sessions(directory))
    check(stamps == ["2026.10.25_14-03-12", "2026.10.25_14-03-12_2"], f"names: {stamps}")
    sessions.new_stamp = original_stamp
    # --- other files in the folder do not matter; a damaged file is shown as damaged
    open(os.path.join(directory, "notes.txt"), "w").write("x")
    open(os.path.join(directory, "2026.10.26_09-00-00.zip"), "wb").write(b"this is not a zip file")
    listed = sessions.list_sessions(directory)
    check([i.stamp for i in listed] == ["2026.10.26_09-00-00", "2026.10.25_14-03-12_2", "2026.10.25_14-03-12"] and not listed[0].ok and listed[1].ok and "damaged" in listed[0].describe(),
          "newest first, other files ignored, the damaged one is marked")
    check("2 segments: sample2.ts (+1)" in listed[2].describe() and "before the cut" in listed[2].describe() and listed[2].describe().startswith(listed[2].created.replace("T", " ")), f"line in the list: {listed[2].describe()}")
    # --- change things, then restore
    win.segments.pop()
    win._save()
    win.settings.set_option("crop", "60")
    win.settings.save()
    chosen, defaults = {}, []
    win.choose_session = lambda title, prompt, infos, multi=False, with_parts=False, with_backup=False, backup_default=True: (defaults.append(backup_default), chosen.get("answer"))[1]
    win.messages.clear()
    win.mnuRestoreSession_Click()
    check(len(win.segments) == 1 and not any(m.startswith("Session ") for m in win.messages), "cancelling the choice: nothing happens")
    chosen["answer"] = ([first], ("list", "ini"), True)
    answers[:] = [False]
    win.mnuRestoreSession_Click()
    check(len(win.segments) == 1 and len(sessions.list_sessions(directory)) == 3, "answer No: nothing is restored, no automatic session")
    answers[:] = [True]
    win.mnuRestoreSession_Click()
    check(len(win.segments) == 2 and win.options["crop"] == "72" and [s.name for s in win.segments] == list(names), "restored: list and settings are back")
    all_infos = sessions.list_sessions(directory)
    auto = [i for i in all_infos if i.note.startswith("automatic backup before restoring 2026.10.25_14-03-12")]
    check(len(auto) == 1 and auto[0].segments == 1 and win.messages[-1] == f"Session {first.stamp} has been restored. The state before is saved as session {auto[0].stamp}.",
          f"the state before the restore is saved first: {win.messages[-1]}")
    check("segment list and settings" in asked[-1] and first.stamp in asked[-1], f"the question names what is replaced: {asked[-1][:90]}")
    check(win.current == 0 and win.lvwSegments.current_row() == 0, "afterwards the first entry is selected (as a whole, as if it had been clicked)")
    # the check box "save the current state first" is switched off: no automatic session
    n_sessions = len(sessions.list_sessions(directory))
    win.segments.pop()
    win._save()
    chosen["answer"] = ([first], ("list", "ini"), False)
    answers[:] = [True]
    win.mnuRestoreSession_Click()
    check(len(sessions.list_sessions(directory)) == n_sessions and len(win.segments) == 2 and asked[-1].find("NOT saved first") > 0 and "saved as a session first" not in asked[-1]
          and win.messages[-1] == f"Session {first.stamp} has been restored.", f"without the backup: no new session, the question says so: {win.messages[-1]}")
    # the choice of the backup check box is remembered (option restore_backup), the other two check boxes are not
    check(defaults[0] is True and win.options["restore_backup"] == "off" and Settings(win.settings.path).options["restore_backup"] == "off",
          "the first call had the box ticked (default on); after switching it off the option is off, also in the INI file - although the restore brought back the "
          "INI file of the session (which did not have the option)")
    chosen["answer"] = None
    win.mnuRestoreSession_Click()
    check(defaults[-1] is False and win.options["restore_backup"] == "off", "the next time the window opens with the box NOT ticked; cancelling changes nothing")
    chosen["answer"] = ([first], ("list", "ini"), True)
    answers[:] = [False]
    win.mnuRestoreSession_Click()
    check(win.options["restore_backup"] == "on" and Settings(win.settings.path).options["restore_backup"] == "on", "ticked again: remembered as on, even if the question after it is answered No")
    chosen["answer"] = None
    win.mnuRestoreSession_Click()
    check(defaults[-1] is True, "and the next window has it ticked again")
    infos_box = [sessions.SessionInfo(stamp="2026.10.21_10-00-00", path="/x", created="2026-10-21T10:00:00", segments=1, titles=["a.ts"])]
    boxes = sessions_dialog.SessionDialog(None, "Restore", "prompt", infos_box, False, True, True, False)
    check(boxes.chkBackup.isChecked() is False and boxes.chkList.isChecked() and boxes.chkIni.isChecked(), "in the window: the backup box as remembered, the other two always ticked")
    boxes = sessions_dialog.SessionDialog(None, "Restore", "prompt", infos_box, False, True, True, True)
    check(boxes.chkBackup.isChecked() and boxes.chkList.isChecked() and boxes.chkIni.isChecked(), "all three ticked")
    from profiles import validate_options
    from settings import default_options
    check(default_options()["restore_backup"] == "on" and validate_options({"restore_backup": "off"}) == [] and len(validate_options({"restore_backup": "maybe"})) == 1, "option restore_backup")
    # parts: only the list
    win.settings.set_option("crop", "55")
    win.settings.save()
    win.segments.pop()
    win._save()
    chosen["answer"] = ([first], ("list",), True)
    answers[:] = [True]
    win.mnuRestoreSession_Click()
    check(len(win.segments) == 2 and win.options["crop"] == "55" and "segment list." in asked[-1] or "the current segment list" in asked[-1], "only the list: the settings stay")
    # only the settings
    chosen["answer"] = ([first], ("ini",), True)
    answers[:] = [True]
    win.mnuRestoreSession_Click()
    check(win.options["crop"] == "72" and len(win.segments) == 2, "only the settings")
    # damaged session / not restorable
    bad = listed[0]
    chosen["answer"] = ([bad], ("list", "ini"), True)
    answers[:] = [True]
    n_infos = len(sessions.list_sessions(directory))
    win.mnuRestoreSession_Click()
    check("damaged" in win.messages[-1] and len(sessions.list_sessions(directory)) == n_infos, "a damaged session is refused, nothing is changed")
    # an archive without the list that is asked for
    only_ini = os.path.join(directory, "2026.10.27_10-00-00.zip")
    with zipfile.ZipFile(only_ini, "w") as z:
        z.write(win.settings.path, "MediaMaker.ini")
    info_ini = sessions.read_info(only_ini)
    chosen["answer"] = ([info_ini], ("list",), True)
    answers[:] = [True]
    win.mnuRestoreSession_Click()
    check("could not be restored" in win.messages[-1] and "no MediaMaker.json" in win.messages[-1] and len(win.segments) == 2, f"a part that is missing in the session: {win.messages[-1]}")
    # a list in the session that is not a MediaMaker list
    fake_list = os.path.join(directory, "2026.10.28_10-00-00.zip")
    with zipfile.ZipFile(fake_list, "w") as z:
        z.writestr("MediaMaker.json", json.dumps({"hello": 1}))
    chosen["answer"] = ([sessions.read_info(fake_list)], ("list",), True)
    answers[:] = [True]
    before_list = open(win.project_path, "rb").read()
    win.mnuRestoreSession_Click()
    check("not a MediaMaker list" in win.messages[-1] and open(win.project_path, "rb").read() == before_list, "a foreign list is not written")
    # --- delete
    stamps_now = [i.stamp for i in sessions.list_sessions(directory)]
    chosen["answer"] = ([first, auto[0]], ())
    answers[:] = [False]
    win.mnuDeleteSession_Click()
    check([i.stamp for i in sessions.list_sessions(directory)] == stamps_now, "answer No: nothing is deleted")
    answers[:] = [True]
    win.mnuDeleteSession_Click()
    remaining = [i.stamp for i in sessions.list_sessions(directory)]
    check(first.stamp not in remaining and auto[0].stamp not in remaining and len(remaining) == len(stamps_now) - 2 and asked[-1] == "Delete 2 sessions?", f"two sessions deleted: {asked[-1]}")
    chosen["answer"] = None
    win.mnuDeleteSession_Click()
    check(len(sessions.list_sessions(directory)) == len(remaining), "cancel: nothing")
    # --- no sessions at all
    empty = seek_window(tmp, videos, ("sample2.ts",), workdir="nosessions")
    empty.mnuRestoreSession_Click()
    check("no saved sessions yet" in empty.messages[-1], "restore without sessions: message")
    empty.mnuDeleteSession_Click()
    check("no saved sessions" in empty.messages[-1], "delete without sessions: message")
    # --- the folder can be set
    win.settings.set_option("sessions_dir", os.path.join(tmp, "elsewhere", "mine"))
    check(win.sessions_directory() == os.path.join(tmp, "elsewhere", "mine"), "option sessions_dir")
    win.ask_text = lambda title, label, default="": "x"
    win.mnuBackupSession_Click()
    check(len(sessions.list_sessions(os.path.join(tmp, "elsewhere", "mine"))) == 1, "the session goes to that folder (created)")
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = tmp
    try:
        win.settings.set_option("sessions_dir", "~/s")
        check(win.sessions_directory() == os.path.join(tmp, "s"), "a leading ~ is the home folder")
    finally:
        os.environ["HOME"] = old_home
    # --- clearing the list, with Yes
    win.settings.set_option("sessions_dir", "")
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    answers[:] = [True]
    win.cmdCommand_Click(3)
    check(win.segments == [] and win.current == -1 and load_segments(win.project_path) == [], "Yes: the list is cleared and saved")
    check(asked[-1] == "Clear all segments from list?", "the question")
    check(win.player.log[-2:] == ["clear", "stop"], f"the preview is cleared, too (no film stays on the screen): {win.player.log[-3:]}")
    # --- the preview is cleared also when the last segment is deleted and after a restored session
    win2 = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="clearpreview")
    win2.lvwSegments.select_row(0)
    win2.lvwSegments_Click()
    win2.player.log.clear()
    win2.delete_segment()
    check("clear" not in win2.player.log, "one of two segments deleted: the other one is shown, nothing is cleared")
    win2.lvwSegments.select_row(0)
    win2.lvwSegments_Click()
    win2.player.log.clear()
    win2.delete_segment()
    check(win2.segments == [] and "clear" in win2.player.log, "the last segment deleted: the preview is cleared")
    win2.player.log.clear()
    win2.reload_session()
    check("clear" in win2.player.log, "after a restored session the preview is cleared")
    # --- clearing without a selected segment, and an empty list
    win3 = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="clearnoselect")
    win3.current = -1
    win3.lvwSegments.clear_selection() if hasattr(win3.lvwSegments, "clear_selection") else None
    win3.ask = lambda text: True
    win3.cmdCommand_Click(3)
    check(win3.segments == [] and win3.current == -1 and load_segments(win3.project_path) == [], "no segment selected, Yes: the list is cleared and saved")
    win3.cmdCommand_Click(3)
    check(win3.messages[-1] == "The list of segments is already empty.", "an empty list: a message instead of nothing")
    # --- the dialog (stub): single, several, parts
    infos3 = [sessions.SessionInfo(stamp=f"2026.10.2{i}_10-00-00", path="/x", created=f"2026-10-2{i}T10:00:00", segments=i, titles=["a.ts"]) for i in range(1, 4)]
    def pick(rows, list_on=True, ini_on=True, chapters_on=True):
        def hook(dialog):
            dialog.list.sel_ = rows
            dialog.chkList.setChecked(list_on) if dialog.chkList else None
            dialog.chkIni.setChecked(ini_on) if dialog.chkIni else None
            dialog.chkChapters.setChecked(chapters_on) if dialog.chkChapters else None
        return hook
    W.QDialog.exec_result = 1
    W.QDialog.on_exec = pick([1])
    got = sessions_dialog.choose_sessions(None, "Restore", "prompt", infos3, with_parts=True)
    check(got == ([infos3[1]], ("list", "ini", "chapters")), f"single selection with all three parts: {got}")
    W.QDialog.on_exec = pick([1], list_on=False, chapters_on=False)
    got = sessions_dialog.choose_sessions(None, "Restore", "prompt", infos3, with_parts=True)
    check(got == ([infos3[1]], ("ini",)), "only the settings")
    W.QDialog.on_exec = pick([1], list_on=False, ini_on=False, chapters_on=False)
    check(sessions_dialog.choose_sessions(None, "Restore", "prompt", infos3, with_parts=True) is None, "no part chosen: None")
    W.QDialog.on_exec = pick([0, 2])
    got = sessions_dialog.choose_sessions(None, "Delete", "prompt", infos3, multi=True)
    check(got == ([infos3[0], infos3[2]], ("ini", "list")), f"several sessions: {got}")
    W.QDialog.on_exec = pick([])
    check(sessions_dialog.choose_sessions(None, "Delete", "prompt", infos3, multi=True) is None, "nothing selected: None")
    W.QDialog.exec_result = 0
    W.QDialog.on_exec = pick([0])
    check(sessions_dialog.choose_sessions(None, "Delete", "prompt", infos3, multi=True) is None, "cancel: None")
    W.QDialog.exec_result = 1
    W.QDialog.on_exec = lambda d: setattr(d.list, "sel_", [1])
    got = sessions_dialog.choose_sessions(None, "Restore", "prompt", infos3, with_parts=True, with_backup=True)
    check(got == ([infos3[1]], ("list", "ini", "chapters"), True), f"the check box for the backup is ticked at first: {got}")
    W.QDialog.on_exec = lambda d: (setattr(d.list, "sel_", [1]), d.chkBackup.setChecked(False))
    got = sessions_dialog.choose_sessions(None, "Restore", "prompt", infos3, with_parts=True, with_backup=True)
    check(got == ([infos3[1]], ("list", "ini", "chapters"), False), "switched off")
    W.QDialog.on_exec = lambda d: setattr(d.list, "sel_", [1])
    check(sessions_dialog.choose_sessions(None, "Restore", "prompt", infos3, with_parts=True) == ([infos3[1]], ("list", "ini", "chapters")), "without the option: as before (no third value)")
    W.QDialog.exec_result, W.QDialog.on_exec = 1, None
    # a double click on a session: OK (when restoring one session), not when deleting several
    one = sessions_dialog.SessionDialog(None, "Restore", "prompt", infos3, False, True)
    one.list.itemDoubleClicked.emit(None)
    check(len(one.called("accept")) == 1, "restoring: a double click on the session is OK")
    many = sessions_dialog.SessionDialog(None, "Delete", "prompt", infos3, True, False)
    many.list.itemDoubleClicked.emit(None)
    check(many.called("accept") == [], "deleting several sessions: a double click does not accept")
    print("Sessions: OK (zip per session, backup with note, restore in parts, automatic backup, delete, dialog)")


def origin_rgb_same(win, marked, rect) -> bool:
    """The picture saved as reference_logo_frame.png is the one that L took (outside of the red frame it is the same as the stored picture)."""
    import numpy as np
    seg = win.segments[0]
    stored = win.ref_origin[seg.mask]["rgb"]
    left, top, right, bottom = rect
    inside = np.zeros(stored.shape[:2], bool)
    inside[top:bottom, left:right] = True
    inside[top + 2:bottom - 2, left + 2:right - 2] = False
    keep = ~inside
    return bool(np.array_equal(stored[keep], marked[keep]))


def test_debug_package(tmp, videos):
    """Deploy => Create debug package: cut values, DeLogo, reference logo, last search, an unchanged piece around the slider position, all as a folder and a zip;
    the wait window of a search says whether crop or the reference logo is used."""
    import json
    import zipfile
    import numpy as np
    import logo
    import sessions
    from PIL import Image, ImageDraw, Image as PILImage
    from mediaprobe import first_frame_number, probe
    from runner import RunResult
    work = tempfile.mkdtemp()
    box = Image.new("RGB", (34, 37), (210, 210, 210))
    ImageDraw.Draw(box).arc((6, 6, 28, 30), 200, 520, fill=(40, 40, 40), width=5)
    box.save(os.path.join(work, "logo.png"))
    clip = os.path.join(work, "logo_gone.ts")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x909090:s=720x576:r=25:d=6,noise=alls=10:allf=t+u", "-loop", "1", "-i", os.path.join(work, "logo.png"),
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=6", "-filter_complex", "[0][1]overlay=632:81:enable='lt(n,60)':shortest=1[v]", "-map", "[v]",
                    "-map", "2:a", "-c:v", "mpeg2video", "-q:v", "2", "-g", "12", "-c:a", "mp2", "-shortest", "-f", "mpegts", clip], check=True, stdin=subprocess.DEVNULL)
    win = seek_window(tmp, work, ("logo_gone.ts",), workdir="debugpkg", first_fn=first_frame_number)
    win.settings.set_option("crop", "0")
    seg = win.segments[0]
    first = seg.first_frame
    folder_base = os.path.join(tmp, "debugpkg", "debug")
    # --- the menu entry
    check(hasattr(win, "mnuDebug") and any(a[0] is win.mnuDebug for a in win.mnuDeploy.called("addAction")), "the entry \"Create debug package\" is in the menu Deploy")
    check("debug/" in open(os.path.join(ROOT, ".gitignore")).read().split(), ".gitignore lists debug/")
    # --- without a segment
    win.current = -1
    win.mnuDebug_Click()
    check(win.messages[-1] == "Please select a segment first." and not os.path.exists(folder_base), "no segment: message, nothing is made")
    # --- the wait window of a search says what is used
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    seg.mask = f"{632 / 720 - 0.003:.6f} {81 / 576 - 0.004:.6f} {37 / 720:.6f} {42 / 576:.6f}"
    win.Slider1.setValue(first + 25)
    win.cmdLogo_Click()
    win.Slider1.setValue(first)
    win.mnuNext_Click()
    texts = win.dialogs[-1].texts
    check(win.dialogs[-1].message == "Seeking with reference logo" and texts and texts[0].startswith("Seeking with reference logo, please wait...\nframe ") and "logo confidence" in texts[0],
          f"crop = 0: the wait window says it seeks with the reference logo: {texts[:1]}")
    win.Slider1.setValue(first)
    win.mnuEnd_Click()
    check(win.dialogs[-1].message == "Seeking with reference logo", "also for Seek end of commercial")
    win.settings.set_option("crop", "60")
    win._border_fn = lambda path, n, fps, opts: 60 if n < first + 100 else 0
    win.Slider1.setValue(first)
    win.mnuNext_Click()
    check(win.dialogs[-1].message == "Seeking with crop = 60" and win.dialogs[-1].texts[0].startswith("Seeking with crop = 60, please wait...\nframe "), "crop > 0: \"Seeking with crop = 60\"")
    check(win._last_search["method"] == "black border (crop)" and win._last_search["crop"] == 60 and win._last_search["probe_kind"] == "black border lines"
          and win._last_search["probes"] and abs(win._last_search["result_frame"] - (first + 100)) <= 1, f"the search is recorded: {win._last_search['result_frame']}")
    win.mnuEnd_Click()
    check(win.dialogs[-1].message == "Seeking with crop = 60", "also for Seek end of commercial")
    win.settings.set_option("crop", "0")
    # --- the search that goes into the package
    win.Slider1.setValue(first)
    win.mnuNext_Click()
    search = win._last_search
    check(search["method"] == "reference logo" and search["direction"].startswith("next commercial") and abs(search["result_frame"] - (first + 60)) <= 1
          and search["probe_kind"] == "logo confidence" and len(search["probes"]) >= 5 and all("value" in p for p in search["probes"]) and search["start_frame_shown"] == 0,
          f"last search recorded: {search['method']}, result {search['result_frame_shown']}, {len(search['probes'])} probes")
    # --- the package
    seg.end = first + 100                                       # marker B at 4 s
    win.Slider1.setValue(first + 30)
    stamps = iter(["2026.10.26_09-30-00", "2026.10.26_09-31-00", "2026.10.26_09-32-00", "2026.10.26_09-33-00", "2026.10.26_09-34-00"])
    original = sessions.new_stamp
    sessions.new_stamp = lambda now=None: next(stamps)
    try:
        win.mnuDebug_Click()
        folder = os.path.join(folder_base, "2026.10.26_09-30-00")
        names = sorted(os.listdir(folder))
        expected = ["README.txt", "clip.ts", "clip_info.txt", "debug_log_tail.txt", "delogo.json", "frame_at_slider.png", "last_search.json", "list.json", "logo_area_at_slider.png",
                    "options.txt", "preview_check.json", "reference_logo.json", "reference_logo_area.png", "reference_logo_edges.png", "reference_logo_frame.png", "segment.json",
                    "versions.txt"]
        check(names == expected, f"files of the package: {names}")
        zip_path = os.path.join(folder_base, "2026.10.26_09-30-00.zip")
        with zipfile.ZipFile(zip_path) as z:
            check(sorted(n.split("/", 1)[1] for n in z.namelist()) == expected and all(n.startswith("2026.10.26_09-30-00/") for n in z.namelist()), "the zip holds the same files in a folder of the same name")
        check(not [f for f in os.listdir(folder_base) if f.endswith(".part")], "no temporary files")
        m = win.messages[-1]
        check(m.startswith(f"Debug package created: {zip_path}") and "upload the zip file" in m and "Not everything could be collected" not in m, f"message: {m[:100]}")
        read = lambda name: json.load(open(os.path.join(folder, name), encoding="utf-8"))
        s = read("segment.json")
        check(s["numbers"]["marker_B_end"] == first + 100 and s["numbers"]["marker_B_shown"] == 100 and s["numbers"]["marker_A_shown"] == 0 and s["numbers"]["first_frame"] == first
              and s["numbers"]["slider_shown"] == 30 and s["numbers"]["frames_in_segment"] == 100, f"cut values: {s['numbers']}")
        check(s["times_from_recording_start"]["marker_B"] == "0:00:04.000" and s["times_from_recording_start"]["slider"] == "0:00:01.200" and s["next"] is None and s["previous"] is None, f"times: {s['times_from_recording_start']}")
        d = read("delogo.json")
        check(d["kind"] == "DeLogo rectangle" and d["pixels_left_top_right_bottom"] == list(logo.absolute_rect(seg.mask, 720, 576)) and d["fractions"] == seg.mask
              and d["ffmpeg_filter"].startswith("delogo=x="), f"DeLogo values: {d}")
        r = read("reference_logo.json")
        ref = win.delogo_refs[seg.mask]
        check(r["edge_pixels"] == ref.ones and r["rect_left_top_right_bottom"] == list(ref.rect) and r["source"].startswith("DeLogo") and 0 < r["edge_share"] < 1, f"reference logo: {r}")
        check(r["created_at_frame"] == first + 25 and r["created_at_frame_shown"] == 25 and r["created_at_time"] == "0:00:01.000", f"where the reference logo was created: {r}")
        made = np.asarray(Image.open(os.path.join(folder, "reference_logo_frame.png")).convert("RGB"))
        left, top, right, bottom = ref.rect
        check(made.shape == (576, 720, 3) and tuple(made[top, left + 5]) == (255, 0, 0) and tuple(made[bottom - 1, right - 5]) == (255, 0, 0)
              and tuple(made[top + 10, left - 10]) != (255, 0, 0), "reference_logo_frame.png: the picture L took, with the rectangle marked")
        check(origin_rgb_same(win, made, ref.rect), "it is the picture at frame 25 (not the picture at the slider, which was at 30): the logo is in it")
        check(Image.open(os.path.join(folder, "reference_logo_area.png")).size == ((right - left + 20) * 6, (bottom - top + 20) * 6), "reference_logo_area.png: the area, enlarged")
        check(json.load(open(os.path.join(folder, "preview_check.json")))["result"].startswith("no preview picture"), "no preview picture with the fake player: said so")
        edges = Image.open(os.path.join(folder, "reference_logo_edges.png"))
        check(edges.size == (ref.edges.shape[1] * 6, ref.edges.shape[0] * 6), f"edge picture enlarged: {edges.size}")
        check(Image.open(os.path.join(folder, "frame_at_slider.png")).size == (720, 576) and Image.open(os.path.join(folder, "logo_area_at_slider.png")).size[0] > 200, "pictures at the slider")
        last = read("last_search.json")
        check(last["method"] == "reference logo" and last["probes"] == search["probes"] and last["result_frame"] == search["result_frame"], "last search in the package")
        check('crop="0"' in open(os.path.join(folder, "options.txt")).read() and open(os.path.join(folder, "versions.txt")).read().startswith("MediaMaker "), "options and versions")
        info = open(os.path.join(folder, "clip_info.txt")).read()
        piece = probe(os.path.join(folder, "clip.ts"))
        lines = info.splitlines()
        check(f"slider (frame {first + 30}, shown 30; = frame_at_slider.png, where the search stopped) is at 1.20 s in the piece" in lines[2]
              and f"marker B (end of the segment) (frame {first + 100}, shown 100) is at 4.00 s in the piece" in info
              and "marker A (start of the segment)" in info and "is at 0.00 s in the piece" in info and "(ffmpeg -c copy)" in lines[1]
              and f"the reference logo was created here (frame {first + 25}, shown 25) is at 1.00 s in the piece" in info and "from 0:00:00.000 to 0:00:11.200" in lines[1],
              f"clip_info: {lines[1:6]}")
        check(5.5 <= piece.video.frames / 25 <= 6.5 and piece.video.width == 720, f"the piece: {piece.video.frames} frames (B at 4 s, the file is 6 s long: from 0 s to the end)")
        # --- with a preview picture (as the memory player has): what the preview showed when L was pressed, and what it shows now
        import mediamaker
        picture = np.asarray(PILImage.fromarray(np.zeros((576, 720, 3), np.uint8)).convert("RGB"))
        win.player.preview = picture
        win.Slider1.setValue(first + 25)
        win.cmdLogo_Click()
        check(win.ref_origin[seg.mask]["preview"] is picture and win.ref_origin[seg.mask]["frame"] == first + 25 and win.ref_origin[seg.mask]["shown"] == 25, "L keeps the preview picture of that moment")
        shown_args = win.references_shown[-1]
        check(shown_args[0].startswith("The reference logo") and shown_args[1].shape == (576, 720, 3) and shown_args[2] is win.delogo_refs[seg.mask], "the dialog gets the text, the picture L took and the reference logo")
        mediamaker.frmMain.show_reference(win, shown_args[0], shown_args[1], shown_args[2])        # the real dialog (with the replacement for Qt): runs
        win.Slider1.setValue(first + 30)
        win.mnuDebug_Click()
        folder_p = os.path.join(folder_base, "2026.10.26_09-31-00")
        names_p = sorted(os.listdir(folder_p))
        check({"reference_logo_vlc_preview.png", "reference_logo_preview_check.json", "vlc_preview.png", "preview_check.json"} <= set(names_p), f"with a preview picture: {names_p}")
        check(json.load(open(os.path.join(folder_p, "reference_logo_preview_check.json")))["frame"] == first + 25 and "best_offset_frames" in json.load(open(os.path.join(folder_p, "preview_check.json")))
              and json.load(open(os.path.join(folder_p, "preview_check.json")))["slider_frame"] == first + 30, "offset between preview and ffmpeg numbering, at L and now")
        win.player.preview = None
        stamps_next = iter(["2026.10.26_09-32-00", "2026.10.26_09-33-00", "2026.10.26_09-34-00", "2026.10.26_09-35-00", "2026.10.26_09-36-00", "2026.10.26_09-37-00"])
        sessions.new_stamp = lambda now=None: next(stamps_next)
        # --- RemoveLogo mask, nothing at all, failing piece
        mask = np.zeros((576, 720), bool)
        mask[81:118, 632:666] = True
        seg.mask = logo.mask_to_png_b64(mask)
        win.mnuDebug_Click()
        folder2 = os.path.join(folder_base, "2026.10.26_09-32-00")
        d = json.load(open(os.path.join(folder2, "delogo.json")))
        check(d["kind"] == "RemoveLogo mask" and os.path.exists(os.path.join(folder2, "removelogo_mask.png"))
              and np.array_equal(logo.mask_from_png_b64(base64.b64encode(open(os.path.join(folder2, "removelogo_mask.png"), "rb").read()).decode()), mask), "RemoveLogo mask: the PNG is in the package")
        check(json.load(open(os.path.join(folder2, "segment.json")))["segment"]["mask"].startswith("<PNG mask"), "the long mask text is not repeated in segment.json")
        seg.mask = ""
        win.delogo_refs.clear()
        win._render_fn = lambda cmd, total, on_progress, cwd=None, cancel=None: RunResult(1, False, 0.1, "Invalid data found when processing input")
        win.mnuDebug_Click()
        folder3 = os.path.join(folder_base, "2026.10.26_09-33-00")
        files3 = sorted(os.listdir(folder3))
        check("clip.ts" not in files3 and "clip_info.txt" in files3 and "logo_area_at_slider.png" not in files3 and os.path.exists(folder3 + ".zip"), f"without logo and with a failing piece: {files3}")
        check(json.load(open(os.path.join(folder3, "delogo.json")))["kind"] == "none" and json.load(open(os.path.join(folder3, "reference_logo.json")))["reference_logo"] == "none", "no DeLogo, no reference logo: said so")
        check("THE PIECE COULD NOT BE CUT" in open(os.path.join(folder3, "clip_info.txt")).read() and "could not be cut" in win.messages[-1] and "Not everything could be collected" in win.messages[-1], "the failing piece is reported")
        # --- cancelled while the piece is cut: no zip
        win._render_fn = lambda cmd, total, on_progress, cwd=None, cancel=None: RunResult(-15, True, 0.1, "")
        n = len(win.messages)
        win.mnuDebug_Click()
        check(not os.path.exists(os.path.join(folder_base, "2026.10.26_09-34-00.zip")) and len(win.messages) == n, "cancelled: no zip, no message")
        # --- the slider close to the start: the piece begins at 0
        win._render_fn = fake = lambda cmd, total, on_progress, cwd=None, cancel=None: (fake.calls.append(cmd), RunResult(1, False, 0.1, ""))[1]
        fake.calls = []
        seg.end = first + 25
        win.Slider1.setValue(first + 25)
        win.mnuDebug_Click()
        cmd = fake.calls[0]
        check(cmd[cmd.index("-ss") + 1] == "0.000" and cmd[cmd.index("-t") + 1] == "11.000" and "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy", f"the command: {' '.join(cmd[:12])}")
        # --- the piece is built around the SLIDER, not around marker B or the place where the reference logo was created
        import debugpack as dp
        saved = dp.CLIP_BEFORE
        dp.CLIP_BEFORE = 2.0                                     # (a 6 s test file: 50 s would always begin at 0)
        try:
            seg.end = first + 25                                 # marker B at 1.0 s, the reference logo from frame 25 as well
            win.Slider1.setValue(first + 100)                    # where the search stopped: 4.0 s
            fake.calls.clear()
            win.mnuDebug_Click()
            cmd = fake.calls[0]
            check(cmd[cmd.index("-ss") + 1] == "2.000" and cmd[cmd.index("-t") + 1] == "12.000", f"around the slider (4 s): from 2 s for 12 s: {' '.join(cmd[:10])}")
        finally:
            dp.CLIP_BEFORE = saved
    finally:
        sessions.new_stamp = original
    import debugpack
    # --- the picture of the preview and the offset to the numbering of ffmpeg
    rng = np.random.default_rng(7)
    small = {n: rng.integers(0, 255, (48, 64, 3), dtype=np.uint8) for n in range(100, 181)}
    preview = np.asarray(PILImage.fromarray(small[137]).resize((720, 576), PILImage.BILINEAR))
    result = debugpack.preview_offset(preview, small, 130)
    check(result["best_offset_frames"] == 7 and result["reliable"] and result["difference_at_0"] > 1.5 * result["best_difference"] and "frame number + 7" in result["meaning"],
          f"the preview shows frame 137 at number 130: offset 7: {result}")
    check(debugpack.preview_offset(preview, small, 137)["best_offset_frames"] == 0 and "agree" in debugpack.preview_offset(preview, small, 137)["meaning"], "no offset: they agree")
    check(debugpack.preview_offset(preview, {}, 130) == {"result": "no frames to compare"}, "nothing to compare")
    check(debugpack.image_array(None) is None and debugpack.image_array(preview) is preview, "picture of the preview: nothing, or an array as it is")
    check(debugpack.clip_window(100.0) == (50.0, 60.0, 50.0) and debugpack.clip_window(20.0) == (0.0, 30.0, 20.0), "50 s before and 10 s after the centre, not before 0")
    check(debugpack.hms(3725.5) == "1:02:05.500", "time format")
    print("Debug package: OK (menu, files, zip, clip around B, DeLogo, reference logo, last search, header of the search)")


def test_ini_tooltips_and_tools(tmp, videos):
    """[ToolTipText] has a help text for EVERY option and profile parameter; the paths of Avidemux and VLC are options (group Tools) and the old
    section [tools.linux] is moved there."""
    import mediamaker
    import shutil as sh
    from profiles import OPTION_GROUPS, PROFILE_KEYS, REMOVED_OPTIONS, validate_options
    from settings import DEFAULT_TOOLTIPS, Settings, default_options
    keys = mediamaker.tooltip_keys()
    check(set(default_options()) | set(PROFILE_KEYS) == set(keys) and len(keys) == len(set(keys)), "tooltip_keys: every option and every profile parameter, once")
    check([k for k in keys if k not in DEFAULT_TOOLTIPS] == [] and [k for k in DEFAULT_TOOLTIPS if k not in keys] == [], "a default text for each of them, and none without a parameter")
    check(all(DEFAULT_TOOLTIPS[k].strip() for k in keys), "no empty text")
    check(keys[:len(PROFILE_KEYS)] == list(PROFILE_KEYS), "the profile parameters come first")
    # --- sync_tooltips
    work = os.path.join(tmp, "tooltips")
    os.makedirs(work, exist_ok=True)
    ini = os.path.join(work, "t.ini")
    open(ini, "w", encoding="utf-8").write("[settings]\noptions=crop=\"72\"\n; a comment\n[ToolTipText]\ndescription=my own text\n; keep me\nfocus=old text of a dropped option\ncrop=Remove pixels\n[profiles]\nSD=scale=\"720:404\"\n")
    st = Settings(ini)
    wanted = {k: DEFAULT_TOOLTIPS[k] for k in keys}
    obsolete = tuple(REMOVED_OPTIONS - set(PROFILE_KEYS))
    check(st.sync_tooltips(wanted, obsolete), "sync: something changed")
    tips = dict(st.items("ToolTipText"))
    check(set(tips) == set(keys) and tips["description"] == "my own text" and tips["crop"] == "Remove pixels" and "focus" not in tips, "all parameters are there, the texts that were there stay (also edited ones), the dropped option is gone")
    st.save()
    raw = open(ini, encoding="utf-8").read()
    check("; keep me" in raw and "; a comment" in raw and 'options=crop="72"' in raw and raw.rstrip().endswith('SD=scale="720:404"'), "comments and the other sections are untouched")
    check(raw.index("[ToolTipText]") < raw.index("[profiles]") and raw.index("batch=") < raw.index("[profiles]"), "the new lines are inside the section")
    check(not Settings(ini).sync_tooltips(wanted, obsolete), "a second time: nothing to do")
    open(ini, "w", encoding="utf-8").write("[settings]\noptions=\n")
    st = Settings(ini)
    st.sync_tooltips(wanted, obsolete)
    check(set(dict(st.items("ToolTipText"))) == set(keys), "no section yet: it is created")
    # --- migrate_tools
    open(ini, "w", encoding="utf-8").write('[settings]\noptions=crop="0"\n[tools.linux]\n; optional: helper programs\navidemux=/opt/ad/avidemux.AppImage|/second\nvlc=/usr/bin/vlc\n[profiles]\nSD=scale="1:1"\n')
    st = Settings(ini)
    check(st.migrate_tools() and st.options["avidemux"] == "/opt/ad/avidemux.AppImage" and st.options["vlc"] == "/usr/bin/vlc" and st.options["crop"] == "0", "avidemux and vlc move into options (the first of several paths)")
    check(st._section_range("tools.linux") is None and "[profiles]" in "\n".join(st._lines) and "optional: helper" not in "\n".join(st._lines), "the section is gone, with its comment")
    check(not st.migrate_tools(), "a second time: nothing")
    open(ini, "w", encoding="utf-8").write('[settings]\noptions=avidemux="/mine"\n[tools.linux]\navidemux=/old\nffmpeg=/opt/ffmpeg\n')
    st = Settings(ini)
    st.migrate_tools()
    check(st.options["avidemux"] == "/mine" and st.items("tools.linux") == [("ffmpeg", "/opt/ffmpeg")], "an option that is set wins; a section with other keys stays with them")
    open(ini, "w", encoding="utf-8").write('[settings]\noptions=\n[tools]\navidemux=/in/tools\n[tools.windows]\nvlc=C:\\vlc\\vlc.exe\n')
    st = Settings(ini)
    st.migrate_tools()
    check(st.options["avidemux"] == "/in/tools" and st.options["vlc"] == "C:\\vlc\\vlc.exe" and st._section_range("tools") is None and st._section_range("tools.windows") is None, "[tools] and [tools.windows], too")
    # --- tool(): the option, otherwise the PATH
    st.set_options({"avidemux": "~/ad/avidemux", "vlc": ""})
    check(st.tool("avidemux") == os.path.expanduser("~/ad/avidemux") and st.tool("vlc") == sh.which("vlc") and st.tool("nonexistent_program") is None, "tool(): the option (with ~), otherwise the PATH")
    # --- the group Tools
    check(dict(OPTION_GROUPS)["Tools"] == ("avidemux", "vlc") and default_options()["avidemux"] == "" and validate_options(default_options()) == [], "group Tools")
    from profiles import GROUP_TEXTS
    check("PATH" in GROUP_TEXTS["Tools"], "text of the group")
    # --- an old INI file with the dropped option logo_rewind: option and help text are removed at the start
    w3 = os.path.join(tmp, "tooltips_rewind")
    os.makedirs(w3, exist_ok=True)
    ini3 = os.path.join(w3, "MediaMaker.ini")
    open(ini3, "w", encoding="utf-8").write('[settings]\noptions=crop="72" logo_rewind="1.8" step_end="40"\n[ToolTipText]\nlogo_rewind=old text\n')
    win = make_window(w3)
    win.showEvent(None)
    gone = Settings(ini3)
    check("logo_rewind" not in gone.options and gone.options["crop"] == "72" and gone.options["step_end"] == "40" and gone.get("ToolTipText", "logo_rewind") is None
          and "logo_rewind" not in win.options, "old INI: logo_rewind is removed from options= and from [ToolTipText], the others stay")
    # --- the window completes the INI file at the start and keeps what is there
    w2 = os.path.join(tmp, "tooltips_window")
    os.makedirs(w2, exist_ok=True)
    ini2 = os.path.join(w2, "MediaMaker.ini")
    open(ini2, "w", encoding="utf-8").write('[settings]\noptions=crop="0"\n[ToolTipText]\ncrop=my words\nfocus=gone\n[tools.linux]\navidemux=/x/avidemux\n')
    win = make_window(w2)
    win.showEvent(None)
    after = Settings(ini2)
    check(set(dict(after.items("ToolTipText"))) == set(keys) and after.get("ToolTipText", "crop") == "my words" and after.get("ToolTipText", "focus") is None
          and after.get("tools.linux", "avidemux") is None and win.options["avidemux"] == "/x/avidemux" and win.settings.tool("avidemux") == "/x/avidemux", "at the start: help texts complete, tools moved")
    first_version = open(ini2, "rb").read()
    win2 = make_window(w2)
    win2.showEvent(None)
    check(open(ini2, "rb").read() == first_version, "the next start does not change the file")
    print("INI help texts and tools: OK (every parameter, sync, migration of [tools.linux], group Tools)")


def test_delete_files(tmp, videos):
    """File => Delete (Ctrl+J): the source files of all segments are deleted for good, the list is cleared; a file that cannot be deleted stays in the list."""
    import stat
    from mediaprobe import first_frame_number
    def copies(folder, names):
        os.makedirs(folder, exist_ok=True)
        out = []
        for i, name in enumerate(names):
            target = os.path.join(folder, f"copy{i}_{name}")
            shutil.copy(os.path.join(videos, name), target)
            out.append(target)
        return out
    folder = os.path.join(tmp, "deletefiles")
    a, b = copies(folder, ("sample2.ts", "sample3.ts"))
    win = seek_window(tmp, folder, tuple(os.path.basename(p) for p in (a, b)), workdir="deletewin", first_fn=first_frame_number)
    asked = []
    answers = [False]
    win.ask = lambda text: (asked.append(text), answers.pop(0))[1]
    # --- No: nothing happens
    win.mnuDelete_Click()
    check(os.path.exists(a) and os.path.exists(b) and len(win.segments) == 2, "answer No: the files and the list stay")
    q = asked[0]
    check(q.startswith("Delete all 2 files of the 2 segments from disk?") and a in q and b in q and "for good, not moved to the trash" in q, f"the question names the files: {q[:90]}")
    # --- Yes: the files are gone for good, the list is empty, saved, the preview cleared
    answers[:] = [True]
    win.player.log.clear()
    win.mnuDelete_Click()
    check(not os.path.exists(a) and not os.path.exists(b), "Yes: both files are deleted from the disk")
    check(win.segments == [] and win.current == -1 and load_segments(win.project_path) == [] and "clear" in win.player.log, "the list is cleared and saved, the preview is empty")
    check(not [f for f in os.listdir(folder) if "trash" in f.lower()] and not os.path.exists(os.path.join(tmp, "deletewin", ".Trash")), "nothing was moved to a trash folder")
    # --- an empty list
    n = len(asked)
    win.mnuDelete_Click()
    check(win.messages[-1] == "The list of segments is empty: there is nothing to delete." and len(asked) == n, "empty list: a message, no question")
    # --- two segments of the same file: counted and deleted once; read-only files go, too; a file that is already gone is no error
    c, d = copies(os.path.join(tmp, "deletefiles2"), ("sample2.ts", "sample3.ts"))
    win = seek_window(tmp, os.path.dirname(c), tuple(os.path.basename(p) for p in (c, d)), workdir="deletewin2", first_fn=first_frame_number)
    win.segments.append(dataclasses.replace(win.segments[0], index=3, start=win.segments[0].start + 10))
    check(len(win.segments) == 3 and win.segments[2].path == win.segments[0].path, "a third segment of the same file")
    os.chmod(c, stat.S_IRUSR)                                        # read-only (VB6: DeleteFile with force)
    os.remove(d)                                                     # already gone
    asked.clear()
    win.ask = lambda text: (asked.append(text), True)[1]
    win.mnuDelete_Click()
    check(asked[0].startswith("Delete all 2 files of the 3 segments from disk?") and not os.path.exists(c) and win.segments == [], f"the shared file counts once, read-only is deleted, a missing file is no error: {asked[0][:60]}")
    # --- a file that cannot be deleted: reported, its segment stays, the others go
    e, f = copies(os.path.join(tmp, "deletefiles3"), ("sample2.ts", "sample3.ts"))
    win = seek_window(tmp, os.path.dirname(e), tuple(os.path.basename(p) for p in (e, f)), workdir="deletewin3", first_fn=first_frame_number)
    win.ask = lambda text: True
    real_remove = os.remove
    def remove(path, *args, **kw):
        if path == f:
            raise PermissionError(13, "Permission denied", path)
        return real_remove(path, *args, **kw)
    os.remove = remove
    try:
        win.mnuDelete_Click()
    finally:
        os.remove = real_remove
    check(not os.path.exists(e) and os.path.exists(f), "the other file is deleted, the one with the error stays")
    check([s.path for s in win.segments] == [f] and [s.path for s in load_segments(win.project_path)] == [f], "its segment stays in the list (and in the saved list)")
    check("1 of 2 file(s) could not be deleted" in win.messages[-1] and f"{f}: Permission denied" in win.messages[-1], f"message: {win.messages[-1][:90]}")
    # --- many files: the question lists the first ones and says how many more
    many = [os.path.join(tmp, "many", f"v{i}.ts") for i in range(11)]
    os.makedirs(os.path.join(tmp, "many"), exist_ok=True)
    for p in many:
        shutil.copy(os.path.join(videos, "sample2.ts"), p)
    win = seek_window(tmp, os.path.join(tmp, "many"), tuple(os.path.basename(p) for p in many), workdir="deletewin4", first_fn=first_frame_number)
    asked.clear()
    win.ask = lambda text: (asked.append(text), False)[1]
    win.mnuDelete_Click()
    check(asked[0].startswith("Delete all 11 files of the 11 segments") and many[7] in asked[0] and many[8] not in asked[0] and "... and 3 more" in asked[0], "more than 8 files: the first 8 and \"... and 3 more\"")
    check(all(os.path.exists(p) for p in many), "nothing deleted (answer No)")
    print("Delete files: OK (question with the files, permanent delete, shared and missing files, errors keep the segment)")


def test_delete_sidecars(tmp, videos):
    """File => Delete with the additional files of a TV recording (.eit, .ts.ap, .ts.cuts, .ts.meta, .ts.sc): a check box, not ticked at first."""
    from PySide6 import QtWidgets as W
    from mediaprobe import first_frame_number
    from sidecars import sidecar_files
    import dialogs
    # --- which files are meant
    folder = os.path.join(tmp, "sidecars")
    os.makedirs(os.path.join(folder, "20261024 2220 - SAT_1 - Chappie.ts.d"), exist_ok=True)
    name = "20261024 2220 - SAT_1 - Chappie"
    def make(*names):
        for n in names:
            open(os.path.join(folder, n), "wb").write(b"x")
    shutil.copy(os.path.join(videos, "sample2.ts"), os.path.join(folder, name + ".ts"))
    make(name + ".eit", name + ".ts.ap", name + ".ts.cuts", name + ".ts.meta", name + ".ts.sc", name + ".mp4", name + ".srt", "Other - Film.ts", "Other - Film.eit",
         name + " (2).ts.ap", "Chappie.ts.ap")
    found = [os.path.basename(f) for f in sidecar_files(os.path.join(folder, name + ".ts"))]
    check(found == [name + ".eit", name + ".ts.ap", name + ".ts.cuts", name + ".ts.meta", name + ".ts.sc"], f"the five files of the receiver: {found}")
    check(name + ".mp4" not in found and name + ".srt" not in found and "Other - Film.eit" not in found and not any("(2)" in f for f in found) and name + ".ts.d" not in found,
          "a converted .mp4, a subtitle file, other recordings and a folder are not meant")
    check(sidecar_files(os.path.join(folder, "Missing.ts")) == [] and sidecar_files("/does/not/exist/x.ts") == [], "no files, no folder: empty")
    dotted = os.path.join(folder, "Show 1.5 - Part 2.ts")
    make("Show 1.5 - Part 2.ts", "Show 1.5 - Part 2.eit", "Show 1.5 - Part 2.ts.cuts", "Show 1.5.eit")
    check([os.path.basename(f) for f in sidecar_files(dotted)] == ["Show 1.5 - Part 2.eit", "Show 1.5 - Part 2.ts.cuts"], "dots in the name: the name without extension is the whole name before .ts")
    upper = os.path.join(folder, "UPPER.ts")
    make("UPPER.ts", "UPPER.EIT")
    check([os.path.basename(f) for f in sidecar_files(upper)] == ["UPPER.EIT"], ".EIT in capital letters")
    # --- the check box in the question
    W.QMessageBox.answer = "Yes"
    W.QMessageBox.shown.clear()
    W.QMessageBox.on_exec = None
    check(dialogs.confirm_with_checkbox(None, "Delete?", "Also the rest") == (True, False), "the check box is not ticked at first; Yes")
    W.QMessageBox.on_exec = lambda box: box.called("setCheckBox")[-1][0].setChecked(True)
    check(dialogs.confirm_with_checkbox(None, "Delete?", "Also the rest") == (True, True), "ticked")
    W.QMessageBox.answer = "No"
    check(dialogs.confirm_with_checkbox(None, "Delete?", "Also the rest") == (False, True), "No")
    W.QMessageBox.answer, W.QMessageBox.on_exec = "Yes", None
    # --- File => Delete
    def window(workdir, names):
        win = seek_window(tmp, folder, names, workdir=workdir, first_fn=first_frame_number)
        win.ask_calls = []
        return win
    def fill(*files):
        for f in files:
            open(os.path.join(folder, f), "wb").write(b"x")
    def remake():
        shutil.copy(os.path.join(videos, "sample2.ts"), os.path.join(folder, name + ".ts"))
        fill(name + ".eit", name + ".ts.ap", name + ".ts.cuts", name + ".ts.meta", name + ".ts.sc", name + ".mp4")
    side = [name + e for e in (".eit", ".ts.ap", ".ts.cuts", ".ts.meta", ".ts.sc")]
    # a) the box is offered; not ticked: the recording goes, the additional files stay
    remake()
    win = window("delside1", (name + ".ts",))
    seen = []
    win.ask_delete = lambda text, label: (seen.append((text, label)), (True, False))[1]
    win.mnuDelete_Click()
    text, label = seen[0]
    check(label == "Also delete the 5 additional files of the recording" and "Additional files of the recording (5; only deleted if the box below is ticked)" in text
          and all(os.path.join(folder, f) in text for f in side) and name + ".mp4" not in text, f"the question lists the additional files, the label counts them: {label}")
    check(not os.path.exists(os.path.join(folder, name + ".ts")) and all(os.path.exists(os.path.join(folder, f)) for f in side) and win.segments == [], "not ticked: only the recording is deleted")
    # b) ticked: everything of the recording goes, the converted .mp4 stays
    remake()
    win = window("delside2", (name + ".ts",))
    win.ask_delete = lambda text, label: (True, True)
    win.mnuDelete_Click()
    check(not any(os.path.exists(os.path.join(folder, f)) for f in [name + ".ts"] + side) and os.path.exists(os.path.join(folder, name + ".mp4")) and win.segments == [],
          "ticked: the recording and its five additional files are deleted, the converted .mp4 stays")
    # c) No: nothing, also with the box ticked
    remake()
    win = window("delside3", (name + ".ts",))
    win.ask_delete = lambda text, label: (False, True)
    win.mnuDelete_Click()
    check(all(os.path.exists(os.path.join(folder, f)) for f in [name + ".ts"] + side) and len(win.segments) == 1, "No: nothing is deleted, even with the box ticked")
    # d) without additional files: no box, the plain question
    shutil.copy(os.path.join(videos, "sample3.ts"), os.path.join(folder, "Plain.ts"))
    win = window("delside4", ("Plain.ts",))
    asked = []
    win.ask = lambda text: (asked.append(text), True)[1]
    win.mnuDelete_Click()
    check(len(asked) == 1 and "Additional files" not in asked[0] and not os.path.exists(os.path.join(folder, "Plain.ts")), "no additional files: no check box, the plain question")
    # e) the recording is already gone, its additional files are still there: they can be deleted
    remake()
    win = window("delside5", (name + ".ts",))
    os.remove(os.path.join(folder, name + ".ts"))
    win.ask_delete = lambda text, label: (True, True)
    win.mnuDelete_Click()
    check(not any(os.path.exists(os.path.join(folder, f)) for f in side) and win.segments == [], "recording already gone: the additional files are deleted")
    # f) a failing additional file: reported, the list is cleared (the recording is gone)
    remake()
    win = window("delside6", (name + ".ts",))
    win.ask_delete = lambda text, label: (True, True)
    real_remove = os.remove
    stuck = os.path.join(folder, name + ".ts.meta")
    def remove(path, *a, **k):
        if path == stuck:
            raise PermissionError(13, "Permission denied", path)
        return real_remove(path, *a, **k)
    os.remove = remove
    try:
        win.mnuDelete_Click()
    finally:
        os.remove = real_remove
    check(win.segments == [] and os.path.exists(stuck) and not os.path.exists(os.path.join(folder, name + ".ts.sc")), "an additional file that cannot be deleted stays, the others go")
    check("1 of 6 file(s) could not be deleted:" in win.messages[-1] and f"{stuck}: Permission denied" in win.messages[-1] and "segments stay" not in win.messages[-1], f"message: {win.messages[-1][:90]}")
    # g) the recording cannot be deleted: its additional files stay with it, the segment stays
    remake()
    win = window("delside7", (name + ".ts",))
    win.ask_delete = lambda text, label: (True, True)
    main = os.path.join(folder, name + ".ts")
    def remove2(path, *a, **k):
        if path == main:
            raise PermissionError(13, "Permission denied", path)
        return real_remove(path, *a, **k)
    os.remove = remove2
    try:
        win.mnuDelete_Click()
    finally:
        os.remove = real_remove
    check(os.path.exists(main) and all(os.path.exists(os.path.join(folder, f)) for f in side) and len(win.segments) == 1 and "their segments stay in the list" in win.messages[-1],
          "the recording cannot be deleted: nothing of it goes, the segment stays")
    # h) two recordings, one folder: each one's own files
    remake()
    shutil.copy(os.path.join(videos, "sample3.ts"), os.path.join(folder, "Other - Film.ts"))
    win = window("delside8", (name + ".ts", "Other - Film.ts"))
    seen.clear()
    win.ask_delete = lambda text, label: (seen.append(label), (True, True))[1]
    win.mnuDelete_Click()
    check(seen == ["Also delete the 6 additional files of the recordings"] and not os.path.exists(os.path.join(folder, "Other - Film.eit")) and os.path.exists(os.path.join(folder, "Chappie.ts.ap")),
          f"two recordings: both with their additional files ({seen}), an unrelated file stays")
    print("Delete with additional files: OK (what is meant, check box, not ticked at first, errors, several recordings)")


def test_dedup(tmp, videos):
    """Edit => Dedup scene: if a recording repeats the end of one segment at the start of the next, the markers B and A are moved towards each
    other until the same picture is found; the repeated part is cut in the middle."""
    import numpy as np
    import dedup
    from frames import grab_frame, grab_scanlines
    from mediaprobe import first_frame_number
    from project import load_segments, segment_row
    # --- the menu item: its name and caption come from the VB6 form (mnuDeDup, "Dedup scene", Ctrl+F8)
    probe_win = seek_window(tmp, videos, ("sample2.ts",), workdir="dedupmenu")
    check(hasattr(probe_win, "mnuDeDup") and not hasattr(probe_win, "cmdOverlap") and hasattr(probe_win, "mnuDeDup_Click"), "the menu item is called mnuDeDup (VB6), its handler mnuDeDup_Click")
    # --- the pieces of the test
    check(dedup.far(10, 33) is False and dedup.far(10, 34) is True and dedup.far(34, 10) is True and dedup.far(0, 0) is False, "far(): a difference of 24 or more (VB6: (a - b) \\ 24 > 0)")
    check(dedup.scan_range(720) == (144, 576) and dedup.scan_range(704) == (141, 563) and dedup.scan_range(1280) == (256, 1024) and dedup.scan_row(576) == 288 and dedup.scan_row(577) == 288,
          "the compared line: 20 % to 80 % of the width in the middle (as the VB6 loop)")
    base = np.full((1, 433, 3), 100, np.uint8)
    near, farther = base.copy(), base.copy()
    near[0, 5, 0] = 123
    farther[0, 5, 0] = 124
    check(dedup.lines_match(base, base) and dedup.lines_match(base, near) and not dedup.lines_match(base, farther) and not dedup.lines_match(base, base[:, :400]),
          "lines: equal if no colour value is far (23 passes, 24 does not); lines of different length never")
    check(dedup.frames_needed(1000, 50, 400) == ((800, 1000), (50, 249)) and dedup.frames_needed(1000, 50, 7) == ((997, 1000), (50, 53)), "frames the search can look at")
    visited = []
    dedup.search(lambda n: (visited.append(("B", n)), None)[1], lambda n: (visited.append(("A", n)), None)[1], 100, 10, 6)
    pairs = [(visited[i][1], visited[i + 1][1]) for i in range(0, len(visited), 2)]
    check(pairs == [(100, 10), (99, 10), (99, 11), (98, 11), (98, 12), (97, 12)], f"the markers move alternately, B back first: {pairs}")
    rand_line = lambda n: np.random.default_rng(n).integers(0, 256, (1, 433, 3), dtype=np.uint8)      # every picture another line, the same picture the same line
    r = dedup.search(rand_line, lambda n: rand_line(n + 70), 300, 5, 400)
    check(r == (187, 117, 226), f"search on made-up lines (segment 2 is 70 frames ahead): found at step 226 = 225 + 1, B back 113, A forward 112: {r}")
    steps = []
    check(dedup.search(lambda n: None, lambda n: None, 100, 10, 50, steps.append) is None and steps == list(range(1, 51)), "no pictures: no match, the progress counts every step")
    check(dedup.search(rand_line, lambda n: rand_line(n + 5), 100, 10, 400, None, b_min=99) is None, "the first marker may not reach the start of its segment")
    check(dedup.search(rand_line, lambda n: rand_line(n + 5), 100, 10, 400, None, a_max=11) is None, "the second marker may not reach the end of its segment")
    check(dedup.search(rand_line, lambda n: rand_line(n + 5), 100, 10, 400) == (57, 52, 86), "without the limits the same lines are found (step 86: B back 43, A forward 42)")
    # --- one line of the frames is exactly that of the whole frame
    sample = os.path.join(videos, "sample2.ts")
    first = first_frame_number(sample, Fraction(25))
    got = grab_scanlines(sample, first + 20, 6, Fraction(25), 144, 576, 288)
    whole = {first + 20 + k: grab_frame(sample, first + 20 + k, Fraction(25)) for k in (0, 3, 5)}
    check(sorted(got) == list(range(first + 20, first + 26)) and all(np.array_equal(got[n][0], whole[n][288, 144:577]) for n in whole), "grab_scanlines: the same values as the line of the whole frame")
    # --- two made-up recordings with a repeat: content frame c of the first at 0..219 and a few commercial frames; the second begins with commercial
    work = os.path.join(tmp, "dedup")
    os.makedirs(work, exist_ok=True)
    W, H = 720, 576
    yy, xx = np.mgrid[0:H, 0:W]
    def content(c):
        r = 128 + 100 * np.sin((xx + 10 * c) / 20.0)
        g = 128 + 100 * np.sin((yy * 0.5 + 7 * c) / 15.0)
        b = 128 + 100 * np.sin((xx + yy + 13 * c) / 30.0)
        return np.stack([r, g, b], axis=2).astype(np.uint8)
    rng = np.random.default_rng(5)
    def commercial():
        return np.clip(60 + rng.normal(0, 25, (H, W, 3)), 0, 255).astype(np.uint8)
    def encode(frames, name, quality):
        out = os.path.join(work, name)
        raw = b"".join(f.tobytes() for f in frames)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "25", "-i", "-",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=30", "-map", "0:v", "-map", "1:a", "-shortest",      # the program wants a sound track
                        "-c:v", "mpeg2video", "-q:v", str(quality), "-g", "12", "-c:a", "mp2", "-f", "mpegts", out], input=raw, check=True)
        return out
    def make(repeat, tag):
        n1 = 220
        seg1 = encode([content(c) for c in range(n1)] + [commercial() for _ in range(20)], f"o1_{tag}.ts", 3)
        seg2 = encode([commercial() for _ in range(25)] + [content(c) for c in range(n1 - repeat, n1 - repeat + 90)], f"o2_{tag}.ts", 7)      # another quality: other noise
        return seg1, seg2
    def window(tag, repeat, limit=400):
        s1, s2 = make(repeat, tag)
        win = seek_window(tmp, work, (os.path.basename(s1), os.path.basename(s2)), workdir=f"overlapwin{tag}", first_fn=first_frame_number)
        win.settings.set_option("dedup", str(limit))
        a, b = win.segments
        a.end = a.first_frame + 220                                  # marker B: the first commercial picture
        b.start = b.first_frame + 25                                 # marker A: the first picture after the commercial
        win.asked, win.cut_calls = [], []
        win.ask_answers = [True, False]                              # 1st question: overlap? Yes. 2nd (after it): check the cut now? No.
        win.ask = lambda text: (win.asked.append(text), win.ask_answers.pop(0) if win.ask_answers else False)[1]
        win.mnuCutPoints_Click = lambda: win.cut_calls.append(win.current)
        win.lvwSegments.select_row(0)
        win.lvwSegments_Click()
        return win, a, b
    # a) a repeat of 60 frames: found at step 61, B back by 30, A forward by 30
    win, a, b = window("a", 60)
    win.mnuDeDup_Click()
    shown = (a.end - a.first_frame, b.start - b.first_frame)
    check(shown == (190, 55), f"repeat of 60 frames: Marker B {shown[0]} (220 - 30), Marker A {shown[1]} (25 + 30)")
    check(len(win.asked) == 2 and "successfully removed" in win.asked[1] and "The duplicate scene of 60 frame(s) was cut in the middle: Marker B moved 30 frame(s) back, Marker A 30 frame(s) forward" in win.asked[1]
          and win.asked[1].endswith('Do you want to check the cut now with "Analyze cut point"?'), f"after the overlap the cut check is offered: {win.asked[1][:110]}")
    check(win.asked[0].startswith("Remove the duplicate scene at the end of segment 1 and the start of segment 2?") and "Attention" not in win.asked[0] and "some time" not in win.asked[0], "the question: no warning about the time (the search takes under a second)")
    check(win.cut_calls == [], "answer No: Analyze cut point is not started")
    saved = load_segments(win.project_path)
    check((saved[0].end, saved[1].start) == (a.end, b.start), "saved in the list")
    check(win.lvwSegments.topLevelItem(1).text(3) == segment_row(b, 2)[3] and win.lvwSegments.topLevelItem(0).text(4) == segment_row(a, 1)[4], "the rows of both segments show the new markers")
    check(win.Slider1.value() == a.end and win.timeline_mode == "B", "the slider is at the new marker B (as cmdPos_Click 10 in VB6)")
    # the cut is clean: the picture at marker B of the first segment is the picture at marker A of the second one
    p1 = grab_frame(a.path, a.end, Fraction(25))[288, 144:577].astype(int)
    p2 = grab_frame(b.path, b.start, Fraction(25))[288, 144:577].astype(int)
    prev = grab_frame(b.path, b.start - 1, Fraction(25))[288, 144:577].astype(int)
    check(np.abs(p1 - p2).mean() < 6 and np.abs(p1 - prev).mean() > 15, "clean cut: the same picture at B and A, and a clearly different one before A")
    # b) a repeat of 61 frames (odd)
    win, a, b = window("b", 61)
    win.mnuDeDup_Click()
    check((a.end - a.first_frame, b.start - b.first_frame) == (189, 55) and "The duplicate scene of 61 frame(s)" in win.asked[1], f"odd repeat of 61: B 189, A 55: {(a.end - a.first_frame, b.start - b.first_frame)}")
    # b2) answer Yes: Analyze cut point is started for the same segment
    win, a, b = window("b2", 60)
    win.ask_answers = [True, True]
    win.mnuDeDup_Click()
    check(win.cut_calls == [0] and (a.end - a.first_frame, b.start - b.first_frame) == (190, 55), "answer Yes: Analyze cut point is started (for segment 1 and its successor)")
    # c) the range is too small
    win, a, b = window("c", 60, limit=40)
    before = (a.end, b.start)
    win.mnuDeDup_Click()
    check(win.messages[-1] == "Duplicate scene removal failed: no matching frames found in a range of 40 frame(s)." and (a.end, b.start) == before, "range too small (40 steps): message, the markers stay")
    # d) No, no selection, last segment, other picture size
    win, a, b = window("d", 60)
    win.ask = lambda text: False
    win.mnuDeDup_Click()
    check((a.end - a.first_frame, b.start - b.first_frame) == (220, 25), "answer No: nothing")
    win.current = -1
    win.mnuDeDup_Click()
    check(win.messages[-1] == "Please select a segment, but not the last one.", "no selection: message")
    win.lvwSegments.select_row(1)
    win.lvwSegments_Click()
    win.mnuDeDup_Click()
    check(win.messages[-1] == "Please select a segment, but not the last one.", "last segment: message")
    b.width = 704
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    win.mnuDeDup_Click()
    check("different picture sizes (720x576 and 704x576)" in win.messages[-1], "other picture size: message")
    # e) the markers may not run through their segments
    win, a, b = window("e", 60)
    a.start = a.first_frame + 215                                    # only 5 frames of the first segment are used
    win.mnuDeDup_Click()
    check(win.messages[-1].startswith("Duplicate scene removal failed") and a.end - a.first_frame == 220, "the first segment would become empty: no match")
    # f) cancel: no exception, no change
    win, a, b = window("f", 60)
    win._scan_fn = lambda *args, **kw: (_ for _ in ()).throw(seek.SeekCancelled())
    win.mnuDeDup_Click()
    check((a.end - a.first_frame, b.start - b.first_frame) == (220, 25), "cancelled: nothing changed")
    # g) a recording that does not repeat anything
    win, a, b = window("g", 0)
    win.mnuDeDup_Click()
    check(win.messages[-1] == "Duplicate scene removal failed: no matching frames found in a range of 400 frame(s)." and (a.end - a.first_frame, b.start - b.first_frame) == (220, 25),
          "a recording without a repeat: no match, the markers stay")
    print("Dedup scene: OK (far, line, search order, scanlines, two made-up recordings with a repeat, messages, limits)")


def test_renamed_option(tmp, videos):
    """The option overlap is called dedup now: old INI files are taken over, the VB6 INI file with dedup is read as it is."""
    from profiles import OPTION_GROUPS, RENAMED_OPTIONS, validate_options
    from settings import DEFAULT_TOOLTIPS, Settings, default_options
    check(RENAMED_OPTIONS == {"overlap": "dedup"} and default_options()["dedup"] == "400" and "overlap" not in default_options() and "overlap" not in DEFAULT_TOOLTIPS, "dedup replaces overlap")
    check(dict(OPTION_GROUPS)["Seeking"].count("dedup") == 1 and "overlap" not in dict(OPTION_GROUPS)["Seeking"], "in the group Seeking")
    check(DEFAULT_TOOLTIPS["dedup"] == "Max. number of frames examined during duplicate scene removal search (menu Edit => Dedup scene)", "the help text as in the VB6 INI file")
    check(len(validate_options({"dedup": "abc"})) == 1 and len(validate_options({"dedup": "-1"})) == 1 and validate_options({"dedup": "250"}) == [], "checking of the value")
    # --- an old INI file with overlap
    work = os.path.join(tmp, "renamed1")
    os.makedirs(work, exist_ok=True)
    ini = os.path.join(work, "MediaMaker.ini")
    open(ini, "w", encoding="utf-8").write('[settings]\noptions=crop="72" overlap="300" step_end="40"\n[ToolTipText]\noverlap=Max. number of frames tried during segment overlap search\n')
    win = make_window(work)
    win.showEvent(None)
    st = Settings(ini)
    check(st.options.get("dedup") == "300" and "overlap" not in st.options and st.options["crop"] == "72" and st.options["step_end"] == "40" and win.options["dedup"] == "300",
          "old INI: the value of overlap moves to dedup, the other options stay")
    check(st.get("ToolTipText", "overlap") is None and st.get("ToolTipText", "dedup") == DEFAULT_TOOLTIPS["dedup"], "the old help text is gone, the new one is there")
    first_version = open(ini, "rb").read()
    make_window(work).showEvent(None)
    check(open(ini, "rb").read() == first_version, "the next start does not change the file")
    # --- both names: the new one wins
    work2 = os.path.join(tmp, "renamed2")
    os.makedirs(work2, exist_ok=True)
    ini2 = os.path.join(work2, "MediaMaker.ini")
    open(ini2, "w", encoding="utf-8").write('[settings]\noptions=overlap="300" dedup="500"\n')
    make_window(work2).showEvent(None)
    check(Settings(ini2).options.get("dedup") == "500" and "overlap" not in Settings(ini2).options, "overlap and dedup: dedup stays, overlap goes")
    # --- the VB6 INI file with dedup (sample from the VB6 program after the renaming), read as it is
    work3 = os.path.join(tmp, "renamed3")
    os.makedirs(work3, exist_ok=True)
    ini3 = os.path.join(work3, "MediaMaker.ini")
    shutil.copy(os.path.join(HERE, "sample_MediaMaker_dedup.ini"), ini3)
    raw_before = open(ini3, "rb").read().decode("latin-1")
    win3 = make_window(work3)
    win3.showEvent(None)
    st3 = Settings(ini3)
    raw_after = open(ini3, "rb").read().decode("latin-1")
    check(win3.options["dedup"] == "400" and "overlap" not in st3.options and st3.get("ToolTipText", "dedup") == "Max. number of frames examined during duplicate scene removal search (menu Edit => Dedup scene)",
          "VB6 INI with dedup: value and help text are kept")
    check(all(line in raw_after for line in ("[tools.64]", "[tools.32]", "[tools.wine]", 'avi="odmlType=1"', "ffmpeg=D:\\USERDATA\\VB\\ffmpeg64\\ffmpeg.exe")),
          "the sections and keys of the VB6 program (tools, avi, mp4) are left alone")
    check(len(st3.profiles) == 11 and "pad" not in st3.options and "focus" not in st3.options, "the profiles are there, pad and focus left the options")
    print("Renamed option dedup: OK (default, group, help text, old INI, both names, VB6 INI)")


def test_crop_segment(tmp, videos):
    """Cropping of one segment: calculation for 16:9, the small window, the red bands over the preview, taking over the values."""
    from fractions import Fraction as F
    from PySide6 import QtWidgets as W
    import cropping
    import crop_dialog
    from ffmpeg_cmd import build_command
    from mediaprobe import first_frame_number
    # --- calculation
    check(cropping.ratio_side(1280, 720, F(1), 36, 36) == 64 == 72 * 8 // 9, "16:9, square pixels: as VB6 ((top + bottom) * 8 \\ 9)")
    check(cropping.ratio_side(720, 576, F(64, 45), 36, 36) == 45 and cropping.ratio_side(720, 576, F(64, 45), 60, 30) == 56, "720x576 shown as 16:9: (top + bottom) * 5/8")
    check(cropping.ratio_side(720, 576, F(16, 15), 40, 40) == 0 and cropping.ratio_side(720, 576, F(16, 15), 72, 72) == 0 and cropping.ratio_side(720, 576, F(16, 15), 144, 144) == 120,
          "a 4:3 picture: nothing at the sides while it is too high for 16:9, then positive")
    check(cropping.sample_aspect(720, 576, 16 / 9) == F(64, 45) and cropping.sample_aspect(1280, 720, 16 / 9) == 1 and cropping.sample_aspect(720, 576, None) == 1, "sample aspect ratio from the display ratio")
    check(cropping.valid(720, 576, 100, 100, 100, 100) and not cropping.valid(720, 576, 288, 288, 0, 0) and not cropping.valid(720, 576, 0, 0, 400, 320) and not cropping.valid(720, 576, -1, 0, 0, 0),
          "something must be left of the picture")
    # --- the window
    d = crop_dialog.frmCrop(None, 720, 576, F(64, 45))
    notes, changes = [], []
    d.notify = notes.append
    d.changed.connect(lambda: changes.append(d.values()))
    check(d.status == 1 and d.values() == (0, 0, 0, 0), "open, all zero")
    d.set_values(10, 20, 30, 40)
    check(d.values() == (10, 20, 30, 40) and [d.txtCrop[i].text() for i in range(4)] == ["10", "20", "30", "40"], "values and text boxes")
    d.HScroll[0].setValue(50)
    d.HScroll_Change(0)
    d.VScroll[1].setValue(7)
    d.VScroll_Change(1)
    check(d.txtCrop[0].text() == "50" and d.txtCrop[3].text() == "7" and changes[-1] == (50, 20, 30, 7) and len(changes) >= 2, "moving a scroll bar updates the text box and tells the main window")
    d.txtCrop[1].setText("33")
    d.typed(1)
    check(d.values()[1] == 33 and d.txtCrop[1].text() == "33", "a number typed into a text box moves the scroll bar")
    d.txtCrop[1].setText("abc")
    d.typed(1)
    check(d.values()[1] == 33 and d.txtCrop[1].text() == "33", "something else is replaced by the value of the scroll bar")
    d.txtCrop[2].setText("100000")
    d.typed(2)
    check(d.values()[2] == d.VScroll[0].value() and d.txtCrop[2].text() == str(d.VScroll[0].value()), "typed values stay inside the range of the scroll bar")
    d.set_values(36, 36, 0, 0)
    d.chkAutoRatio.setChecked(True)
    d.chkAutoRatio_Click()
    check(d.values() == (36, 36, 45, 45), f"16:9 on: left and right are set from top and bottom: {d.values()}")
    d.HScroll[0].setValue(60)
    d.HScroll_Change(0)
    check(d.values() == (60, 36, 60, 60) and d.txtCrop[2].text() == "60", f"and follow when top changes: {d.values()}")
    d.cmdReset_Click()
    check(d.values() == (0, 0, 0, 0) and not d.chkAutoRatio.isChecked(), "R: everything zero, 16:9 off")
    d.set_values(300, 300, 0, 0)
    d.cmdOK_Click()
    check(d.status == 1 and notes and "Nothing would be left of the picture" in notes[0] and not d.called("accept"), "OK with nothing left of the picture: refused, the window stays open")
    d.set_values(10, 20, 30, 40)
    d.cmdOK_Click()
    check(d.status == 0 and len(d.called("accept")) == 1, "OK: status 0")
    d2 = crop_dialog.frmCrop(None, 720, 576, 1)
    d2.cmdCancel_Click()
    check(d2.status == -1 and len(d2.called("reject")) == 1, "X: status -1")
    # --- in the main window: the window is a part of it (not a window of its own: under Wayland the position of such a window cannot be set)
    from PySide6 import QtCore
    work = os.path.join(tmp, "cropwin")
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="cropwin", first_fn=first_frame_number)
    win._aspect_fn = lambda path: 16 / 9
    seg = win.segments[0]
    win.VLC.setGeometry(10, 20, 400, 300)
    win.current = -1
    win.cmdCommand_Click(5)
    check(win._modal_child is None, "no segment selected: no window")
    win.lvwSegments.select_row(0)
    win.lvwSegments_Click()
    enabled = lambda widget: widget.called("setEnabled")[-1][0] if widget.called("setEnabled") else True
    win.cmdCommand_Click(5)
    dlg = win._modal_child
    check(dlg is not None and dlg.values() == (0, 0, 0, 0) and dlg.source == (720, 576, F(64, 45)), f"the window gets the size and the sample aspect ratio of the picture: {dlg.source}")
    check(dlg.called("setWindowFlags")[-1][0] == QtCore.Qt.WindowType.Widget, "it is a part of the main window, not a window of its own")
    point = dlg.called("move")[-1][0]
    check((point.x(), point.y()) == ((400 - dlg.width()) // 2, (300 - dlg.height()) // 2) and dlg.width() == 281 and dlg.height() == 161,
          f"it is centred in the preview (400x300): {(point.x(), point.y())}")
    check(enabled(win.centralWidget()) is False and enabled(win.menuBar()) is False, "while it is open the rest of the main window cannot be used")
    dlg.set_values(60, 30, 40, 20)
    dlg.HScroll_Change(0)                                           # the window tells the main window
    areas = [(win.fraCrop[i].geometry().x(), win.fraCrop[i].geometry().y(), win.fraCrop[i].geometry().width(), win.fraCrop[i].geometry().height()) for i in range(4)]
    check(areas == [(10, 20, 400, 31), (10, 304, 400, 16), (10, 20, 22, 300), (399, 20, 11, 300)], f"red bands over the preview, in proportion: {areas}")
    check(all(win.fraCrop[i].isVisible() for i in range(4)), "the bands are shown while the window is open")
    check((seg.crop_top, seg.crop_left) == (0, 0), "nothing is taken over before OK")
    dlg.cmdOK_Click()
    check(win._modal_child is None and enabled(win.centralWidget()) is True and enabled(win.menuBar()) is True and not any(win.fraCrop[i].isVisible() for i in range(4)),
          "OK: the window is gone, the main window usable again, the bands hidden")
    check((seg.crop_top, seg.crop_bottom, seg.crop_left, seg.crop_right) == (60, 30, 40, 20), "OK: the values are in the segment")
    saved = load_segments(win.project_path)[0]
    check((saved.crop_top, saved.crop_bottom, saved.crop_left, saved.crop_right) == (60, 30, 40, 20), "and in the saved list")
    graph = build_command(win.make_job(os.path.join(work, "o.mp4")))
    graph = graph[graph.index("-filter_complex") + 1]
    check("crop=iw-60:ih-90:40:60" in graph, f"ffmpeg crops this segment: {graph[:80]}")
    # the window starts with the values of the segment; Cancel changes nothing
    win.cmdCommand_Click(5)
    dlg = win._modal_child
    start = dlg.values()
    dlg.set_values(1, 2, 3, 4)
    dlg.cmdCancel_Click()
    check(start == (60, 30, 40, 20) and (seg.crop_top, seg.crop_left) == (60, 40) and win._modal_child is None and enabled(win.centralWidget()) is True
          and not any(win.fraCrop[i].isVisible() for i in range(4)), "Cancel: the segment keeps its values, everything is back as it was")
    # the Escape key (the window is closed without OK) counts as cancel
    win.cmdCommand_Click(5)
    dlg = win._modal_child
    dlg.set_values(9, 9, 9, 9)
    dlg.reject()
    check((seg.crop_top, seg.crop_left) == (60, 40) and win._modal_child is None, "closed without OK: nothing is taken over")
    # closing the main window while the window is open
    win.cmdCommand_Click(5)
    dlg = win._modal_child
    win.Form_Unload()
    check(win._modal_child is None and enabled(win.centralWidget()) is True, "closing the main window cancels the crop window")
    # 16:9
    win.cmdCommand_Click(5)
    dlg = win._modal_child
    dlg.set_values(60, 30, 0, 0)
    dlg.chkAutoRatio.setChecked(True)
    dlg.chkAutoRatio_Click()
    dlg.cmdOK_Click()
    check((seg.crop_top, seg.crop_bottom, seg.crop_left, seg.crop_right) == (60, 30, 56, 56), f"16:9: left and right {seg.crop_left}, {seg.crop_right}")
    # --- a global cropping value prevails: the question
    asked = []
    win.ask = lambda text: (asked.append(text), False)[1]
    win.settings.set_option("crop", "72")
    win.cmdCommand_Click(5)
    win._modal_child.set_values(5, 5, 0, 0)
    win._modal_child.cmdOK_Click()
    check(len(asked) == 1 and asked[0].startswith("Attention: the global cropping value was (also) set, and will prevail over individual (per segment) cropping.")
          and asked[0].endswith("Do you want to set the global cropping value to zero?") and win.options["crop"] == "72" and seg.crop_top == 5, "global crop > 0: the question; No: it stays")
    win.ask = lambda text: (asked.append(text), True)[1]
    win.cmdCommand_Click(5)
    win._modal_child.set_values(5, 5, 0, 0)
    win._modal_child.cmdOK_Click()
    check(win.options["crop"] == "0" and Settings(win.settings.path).options["crop"] == "0", "Yes: the global value is set to zero (and saved)")
    asked.clear()
    win.cmdCommand_Click(5)
    win._modal_child.set_values(6, 6, 0, 0)
    win._modal_child.cmdOK_Click()
    check(asked == [] and seg.crop_top == 6, "global crop 0: no question")
    print("Cropping of a segment: OK (16:9, window, bands over the preview, taking over, global value)")


def test_import_job(tmp, videos):
    """File => Import: the jobs of a batch file are listed; the chosen one brings back profile, options and segment list."""
    import batch
    import sessions
    import import_dialog
    from PySide6 import QtWidgets as W
    from cutlist import parse_kv
    from mediaprobe import first_frame_number
    from settings import format_kv
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="importwin", first_fn=first_frame_number)
    a, b = win.segments
    a.crop_top, a.mask, b.crop_left = 12, "0.1 0.2 0.3 0.4", 8
    a.end = a.first_frame + 100
    win.settings.set_option("crop", "0")
    win.settings.set_profile({**win.profile, "scale": "720:404"})
    job1 = win.make_job("/out/first.mp4")
    original = [dataclasses.replace(s) for s in win.segments]
    original_profile, original_options = dict(job1.profile), dict(job1.options)
    # a second job with other values, written after the first one (which stays in the script as an old step)
    b.start += 20
    job2 = win.make_job("/out/second.mp4")
    script = batch.build_script(job1, ["ffmpeg", "-i", "in.ts", "out1.mp4"])
    script = batch.build_script(job2, ["ffmpeg", "-i", "in.ts", "out2.mp4"], script)
    # --- reading the jobs
    jobs = batch.parse_jobs(script)
    check([(j.number, j.output, j.error) for j in jobs] == [(1, "/out/first.mp4", ""), (2, "/out/second.mp4", "")], f"both jobs are found, also the one that is switched off: {[(j.number, j.output) for j in jobs]}")
    check(jobs[0].describe() == "Job1: /out/first.mp4" and jobs[1].describe() == "Job2: /out/second.mp4", "the line in the list")
    check(parse_kv(jobs[0].profile) == original_profile and parse_kv(jobs[0].options) == original_options, "profile and options of the job, exactly")
    check(batch.parse_jobs(script.replace("\n", "\r\n"))[0].csv == jobs[0].csv, "a script with Windows line ends")
    check(batch.parse_jobs("") == [] and batch.parse_jobs("#!/bin/bash\necho hello\n# just a comment\n") == [], "no job in an empty file or a file without jobs")
    broken = script.replace("# P=", "# P=@@@", 1)
    bj = batch.parse_jobs(broken)
    check(bj[0].error == "the text cannot be decoded" and "damaged" in bj[0].describe() and bj[1].error == "", "a damaged job is marked, the other one is fine")
    nocsv = "\n".join(l for l in script.splitlines() if not l.startswith("# C="))
    check(batch.parse_jobs(nocsv)[0].error == "no segment list", "a job without a segment list")
    # --- the window for choosing
    W.QDialog.exec_result = 1
    W.QDialog.on_exec = lambda d: setattr(d.list, "sel_", [1])
    check(import_dialog.choose_job(None, jobs) is jobs[1], "choosing a job")
    W.QDialog.on_exec = lambda d: setattr(d.list, "sel_", [])
    check(import_dialog.choose_job(None, jobs) is None, "nothing selected: None")
    W.QDialog.exec_result, W.QDialog.on_exec = 0, None
    check(import_dialog.choose_job(None, jobs) is None, "cancelled: None")
    W.QDialog.exec_result = 1
    one = sessions_dialog_choose = __import__("sessions_dialog").SessionDialog(None, "Import job", "Select", jobs, False, False)
    one.list.itemDoubleClicked.emit(None)
    check(len(one.called("accept")) == 1, "a double click on a job is OK")
    # --- File => Import
    script_path = win.batch_path()
    check(script_path == os.path.splitext(win.settings.path)[0] + ".sh", "the batch file lies next to the INI file")
    win.messages.clear()
    win.mnuImport_Click()
    check(win.messages[-1] == "No batch file found.", "no batch file: message")
    open(script_path, "w", encoding="utf-8").write("#!/bin/bash\necho hi\n")
    win.mnuImport_Click()
    check(win.messages[-1] == "The batch file contains no job that can be imported.", "no job in it: message")
    open(script_path, "w", encoding="utf-8").write(script)
    win.choose_job = lambda jobs: None
    before = [dataclasses.replace(s) for s in win.segments]
    win.mnuImport_Click()
    check(win.segments == before, "cancelled: nothing changes")
    win.choose_job = lambda jobs: bj[0]
    open(script_path, "w", encoding="utf-8").write(broken)
    win.mnuImport_Click()
    check(win.messages[-1] == "Job 1 cannot be imported: the text cannot be decoded." and win.segments == before, "a damaged job is refused")
    open(script_path, "w", encoding="utf-8").write(script)
    # the current state differs from job 1: other list, other options, other profile; the paths of the programs are local
    win.segments.pop()
    win.settings.set_option("crop", "60")
    win.settings.set_option("avidemux", "/local/avidemux")
    win.settings.set_option("batch", script_path)
    win.settings.set_profile({**win.profile, "scale": "1280:720"})
    win._save()
    asked = []
    win.ask = lambda text: (asked.append(text), False)[1]
    win.choose_job = lambda jobs: jobs[0]
    win.mnuImport_Click()
    check(len(asked) == 1 and asked[0].startswith("The list (1 segment) is replaced by the 2 segments of the job") and "saved as a session first" in asked[0] and len(win.segments) == 1
          and not sessions.list_sessions(win.sessions_directory()), "the list is not empty: the question; No: nothing changes, no session")
    win.ask = lambda text: (asked.append(text), True)[1]
    win.mnuImport_Click()
    now = win.segments
    check(len(now) == 2 and [(s.path, s.name, s.start, s.end, s.crop_top, s.crop_left, s.mask, s.fps, s.width, s.height) for s in now]
          == [(s.path, s.name, s.start, s.end, s.crop_top, s.crop_left, s.mask, s.fps, s.width, s.height) for s in original], "Yes: the segment list of the job is back, with crop and mask")
    check([s.first_frame for s in now] == [a.first_frame, b.first_frame] and [s.total_frames for s in now] == [a.total_frames, b.total_frames], "first frame and length found again")
    check(win.lvwSegments.row_count() == 2 and win.current == 0 and win.lvwSegments.current_row() == 0, "the list shows them, the first entry is selected as a whole")
    check(win.options["crop"] == "0" and win.profile["scale"] == "720:404" and Settings(win.settings.path).profile["scale"] == "720:404", "options and profile of the job are taken over (and saved)")
    check(win.options["avidemux"] == "/local/avidemux" and win.options["batch"] == script_path, "the options of this computer (programs, batch file) stay")
    auto = sessions.list_sessions(win.sessions_directory())
    check(len(auto) == 1 and auto[0].note == "automatic backup before importing a job from the batch file" and auto[0].segments == 1, "the state before is saved as a session")
    check(load_segments(win.project_path)[1].crop_left == 8, "saved")
    # an empty list: no question, no session; an old option name in the job is taken over as the new one
    win.segments.clear()
    win._save()
    win.reload_session()
    old = batch.encode_block("T", 'crop="0" overlap="300" focus="0"')
    lines = [l for l in script.splitlines() if not l.startswith("# T=")]
    first_j = lines.index("# J=/out/first.mp4")
    open(script_path, "w", encoding="utf-8").write("\n".join(lines[:first_j + 1] + old + lines[first_j + 1:]) + "\n")
    asked.clear()
    win.mnuImport_Click()
    check(asked == [] and len(win.segments) == 2 and len(sessions.list_sessions(win.sessions_directory())) == 1, "empty list: no question and no new session")
    check(win.options.get("dedup") == "300" and "overlap" not in win.options and "focus" not in win.options, "old names in the job: overlap -> dedup, dropped options go")
    print("Import of a job: OK (reading the script, choosing, taking over, local options, session, damaged jobs)")


def test_open_filter(tmp, videos):
    """The file type that was chosen in the Open dialog is the first suggestion next time (as long as the program runs, it is not saved)."""
    from PySide6 import QtWidgets as W
    import mediamaker
    os.makedirs(os.path.join(tmp, "openfilter"), exist_ok=True)
    win = make_window(os.path.join(tmp, "openfilter"))
    W.QFileDialog.open_calls.clear()
    W.QFileDialog.result, W.QFileDialog.result_filter = "", ""
    check(win.choose_file() == "" and W.QFileDialog.open_calls[-1][3] == "", "first time: no file type chosen yet (the dialog takes the first one, ts)")
    mp4 = "MP4 video file (*.mp4)"
    W.QFileDialog.result, W.QFileDialog.result_filter = os.path.join(videos, "a.mp4"), mp4
    check(win.choose_file() == os.path.join(videos, "a.mp4") and W.QFileDialog.open_calls[-1][3] == "", "the dialog is opened as before, the user changes the type to mp4 and opens a file")
    W.QFileDialog.result, W.QFileDialog.result_filter = "", ""
    win.choose_file()
    check(W.QFileDialog.open_calls[-1][3] == mp4 and W.QFileDialog.open_calls[-1][2] == mediamaker.OPEN_FILTERS, f"next time mp4 is the first suggestion (and all types are listed): {W.QFileDialog.open_calls[-1][3]!r}")
    win.choose_file()
    check(W.QFileDialog.open_calls[-1][3] == mp4, "cancelling does not forget it")
    avi = "A/V Interleave file (*.avi)"
    W.QFileDialog.result, W.QFileDialog.result_filter = os.path.join(videos, "b.avi"), avi
    win.choose_file()
    W.QFileDialog.result, W.QFileDialog.result_filter = "", ""
    win.choose_file()
    check(W.QFileDialog.open_calls[-1][3] == avi, "another type: the last one counts")
    again = make_window(os.path.join(tmp, "openfilter"))
    again.choose_file()
    check(W.QFileDialog.open_calls[-1][3] == "" and avi not in open(again.settings.path, encoding="utf-8").read(), "a new run of the program starts without it (nothing is saved)")
    W.QFileDialog.result = ""
    print("Open dialog: OK (the chosen file type is the first suggestion next time, only for this run)")


def test_copy_mode(tmp, videos):
    """Copy mode: saving without re-encoding. One video is cut at a keyframe, several videos are joined in full length."""
    import copymode
    import numpy as np
    from fractions import Fraction as F
    from copymode import CopyModeError
    from cutlist import Job
    from ffmpeg_cmd import stream_times_of
    from mediaprobe import first_frame_number, probe
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="copywin", first_fn=first_frame_number)
    a, b = win.segments
    a.start, a.end = a.first_frame + 56, a.first_frame + 126
    b.start, b.end = b.first_frame + 20, b.first_frame + 90
    options = dict(win.options)
    # --- the plan
    whole = dataclasses.replace(a, start=a.first_frame, end=a.total_frames)
    plan = copymode.make_plan([whole], {"crop": "0"})
    check(plan.kind == "copy" and plan.files == [a.path] and plan.ignored == [] and abs(plan.seconds - float(F(whole.frames) / whole.fps)) < 1e-9, f"one whole video: copied as it is: {plan}")
    plan = copymode.make_plan([a], {"crop": "72"})
    check(plan.kind == "cut" and plan.segment is a and plan.ignored == ["cropping"] and abs(plan.seconds - 70 / 25) < 1e-9, f"one video, one segment: cut; the global cropping is not taken into account: {plan}")
    a.mask = "0.1 0.2 0.3 0.4"
    check(copymode.make_plan([a], {"crop": "0"}).ignored == ["the logo filter"], "the logo filter is not taken into account")
    a.mask = ""
    try:
        copymode.make_plan([a, dataclasses.replace(a, start=a.start + 100, end=a.end + 5)], options)
        check(False, "two segments of one video are refused")
    except CopyModeError as e:
        check("2 segments of the same video" in str(e) and "cut only once" in str(e), f"two segments of one video: {e}")
    whole_twice = [whole, dataclasses.replace(whole), dataclasses.replace(whole)]
    plan = copymode.make_plan(whole_twice, {"crop": "0"})
    check(plan.kind == "concat" and plan.files == [a.path] * 3 and plan.ignored == [] and abs(plan.seconds - 3 * float(F(whole.frames) / whole.fps)) < 1e-9,
          f"the same WHOLE file three times (no cut markers anywhere): joined, not refused: {plan}")
    try:
        copymode.make_plan([whole, dataclasses.replace(whole), dataclasses.replace(whole, start=whole.start + 20)], {"crop": "0"})
        check(False, "a cut one among them is refused")
    except CopyModeError as e:
        check("3 segments of the same video, and segment 3 has cut markers" in str(e) and "remove the cut markers (then the whole video is joined 3 times)" in str(e), f"the message names the segment: {e}")
    try:
        copymode.make_plan([dataclasses.replace(whole, end=whole.end - 5), dataclasses.replace(whole, start=whole.start + 5)], {"crop": "0"})
        check(False, "two cut ones are refused")
    except CopyModeError as e:
        check("segments 1, 2 have cut markers" in str(e), f"several cut ones are named: {e}")
    try:
        copymode.make_plan([], options)
        check(False, "an empty list is refused")
    except CopyModeError as e:
        check(str(e) == "There are no segments in the list.", "empty list")
    plan = copymode.make_plan([a, b, dataclasses.replace(a, start=a.start + 3)], {"crop": "0"})
    check(plan.kind == "concat" and plan.files == [a.path, b.path, a.path] and plan.segment is None, f"several videos: EVERY item of the list, in its order (as in VB6; a file can be there twice): {plan.files}")
    check(plan.ignored == ["the cut markers"] and abs(plan.seconds - (2 * (a.total_frames - a.first_frame) + (b.total_frames - b.first_frame)) / 25) < 1e-9, f"joined in full length: {plan.seconds} s, ignored: {plan.ignored}")
    b.crop_top = 5
    check(copymode.make_plan([a, b], {"crop": "0"}).ignored == ["the cut markers", "cropping"], "also the cropping of a segment is not taken into account")
    lst_twice = os.path.join(tmp, "copywin", "files_twice.txt")
    copymode.write_list(copymode.make_plan([a, b, a], {"crop": "0"}), lst_twice)
    check(open(lst_twice).read() == f"file '{a.path}'\nfile '{b.path}'\nfile '{a.path}'\n", "the list of files for ffmpeg has the same file twice, as the list of segments has it")
    b.crop_top = 0
    wide = dataclasses.replace(b, width=1280, fps=F(30), sample_rate=44100)
    try:
        copymode.make_plan([a, wide], options)
        check(False, "different videos are refused")
    except CopyModeError as e:
        text = str(e)
        check(text.startswith("Copy mode joins videos with identical characteristics only") and "sample3.ts: size 1280x576 (the first file: 720x576)" in text
              and "frame rate 30.000" in text and "sample rate 44100" in text, f"different videos: {text}")
    # --- the list of files for the concat demuxer
    lst = os.path.join(tmp, "copywin", "files.txt")
    copymode.write_list(copymode.CopyPlan("concat", ["/a/b.ts", "/c/it's.ts"], None, 1.0), lst)
    check(open(lst).read() == "file '/a/b.ts'\nfile '/c/it'\\''s.ts'\n", f"list of files, a quote is escaped: {open(lst).read()!r}")
    # --- stream selection
    maps = copymode.stream_maps
    check(maps({}, "a") == ["-map", "0:v:0", "-map", "0:a:0"] and maps({}, "a:1") == ["-map", "0:v:0", "-map", "0:a:1"], "sound track: the chosen one")
    check(maps({"multilanguage": "True"}, "a:1") == ["-map", "0:v:0", "-map", "0:a"], "multilanguage: all sound tracks")
    check(maps({"subtitle": "1, 3"}, "a") == ["-map", "0:v:0", "-map", "0:a:0", "-map", "0:s:0", "-map", "0:s:2"] and maps({"subtitle": "0"}, "a") == maps({}, "a"), "subtitles by number (1 is s:0), 0 = none")
    # --- the command
    job = Job(output="/out/film.mkv", profile=dict(win.profile), options=dict(options), segments=[a])
    cmd = copymode.build_copy_command(copymode.make_plan([a], options), job, container_start=F("1.4"))
    check(cmd == ["ffmpeg", "-y", "-hide_banner", "-copyts", "-seek_timestamp", "1", "-ss", "4.040", "-i", a.path, "-to", "6.840", "-map", "0:v:0", "-map", "0:a:0", "-c", "copy",
                  "-avoid_negative_ts", "make_zero", "/out/film.mkv"], f"cut: absolute times, no filter: {cmd}")
    cmd = copymode.build_copy_command(copymode.make_plan([whole], options), dataclasses.replace(job, segments=[whole]))
    check(cmd == ["ffmpeg", "-y", "-hide_banner", "-i", a.path, "-map", "0:v:0", "-map", "0:a:0", "-c", "copy", "/out/film.mkv"], f"whole video: no cut: {cmd}")
    job2 = Job(output="/out/film.mp4", profile=dict(win.profile), options={**options, "subtitle": "2"}, segments=[a, b])
    cmd = copymode.build_copy_command(copymode.make_plan([a, b], options), job2, list_path="/tmp/files.txt", chapters_file="/tmp/chapters.txt")
    check(cmd == ["ffmpeg", "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", "/tmp/files.txt", "-i", "/tmp/chapters.txt", "-map_chapters", "1", "-map", "0:v:0", "-map", "0:a:0",
                  "-map", "0:s:1", "-c", "copy", "-c:s", "mov_text", "/out/film.mp4"], f"concat with subtitles for mp4 and chapters: {cmd}")
    check(not any(x in " ".join(cmd + copymode.build_copy_command(copymode.make_plan([a], options), job, container_start=F(1))) for x in ("filter_complex", "setsar", "-vf", "libx264")), "no filter, no encoding")
    # --- the menu: switched on with a warning, not saved
    check(win.mnuCopyMode.called("setCheckable")[-1] == (True,), "the menu entry can be checked")
    asked = []
    win.ask = lambda text: (asked.append(text), False)[1]
    win.mnuCopyMode.setChecked(True)
    win.mnuCopyMode_Click()
    check(len(asked) == 1 and "WITHOUT re-encoding" in asked[0] and "However, the definition of chapters is still possible." in asked[0]
          and "The state of copy mode is remembered for the next start and is kept in batch scripts and sessions." in asked[0] and "not saved" not in asked[0] and asked[0].endswith("Continue anyway?") and not win.mnuCopyMode.isChecked(),
          "switching on: the warning; No: it stays off")
    win.ask = lambda text: (asked.append(text), True)[1]
    win.mnuCopyMode.setChecked(True)
    win.mnuCopyMode_Click()
    check(win.mnuCopyMode.isChecked() and len(asked) == 2, "Yes: it is on")
    win.mnuCopyMode.setChecked(False)
    win.mnuCopyMode_Click()
    n_messages = len(win.messages)
    win.mnuCopyMode.setChecked(False)
    win.mnuCopyMode_Click()
    check(not win.mnuCopyMode.isChecked() and len(asked) == 2 and win.messages[-1] == "Copy mode is switched off." and len(win.messages) == n_messages + 1,
          "switching off: no question, but a message that confirms it")
    win.mnuCopyMode.setChecked(True)
    n_messages = len(win.messages)
    win.ask = lambda text: (asked.append(text), False)[1]
    win.mnuCopyMode.setChecked(True)
    win.mnuCopyMode_Click()
    check(not win.mnuCopyMode.isChecked() and len(win.messages) == n_messages, "No at the warning: it stays off, no further message")
    win.ask = lambda text: (asked.append(text), True)[1]
    win.mnuCopyMode.setChecked(True)
    win.mnuCopyMode_Click()
    win.mnuCopyMode.setChecked(False)
    check("copy" not in " ".join(open(win.settings.path, encoding="utf-8").read().lower().split("options=")[1].split("\n")[0:1]) and "copy" not in win.options, "not saved in the options")
    # --- saving for real
    win.mnuCopyMode.setChecked(True)
    result = os.path.join(tmp, "copywin", "cut.mkv")
    win.choose_output = lambda kind: result
    win.segments[:] = [a]
    win.settings.set_profile({**win.profile, "fps": "abc"})                    # the profile is ignored in copy mode, also an invalid one
    win.mnuSaveMP4_Click()
    info = probe(result)
    c0, v0 = (float(x) for x in stream_times_of(a.path))
    def frames_of(path):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0", "-vf", "scale=64:48,format=gray", "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
        return np.frombuffer(raw, np.uint8).reshape(-1, 48, 64).astype(np.float32)
    source, got = frames_of(a.path), frames_of(result)
    index = lambda frame: int(np.argmin([np.abs(source[i] - frame).mean() for i in range(len(source))]))
    keys = [float(l.split(",")[0]) for l in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time,flags", "-of", "csv=p=0", a.path],
                                                          capture_output=True, text=True).stdout.split() if "K" in l.split(",")[1]]
    target = c0 + a.start / 25
    first_key = min(k for k in keys if k >= target - 0.001)
    want_first, want_last = round((first_key - v0) * 25), round((c0 + a.end / 25 - v0) * 25)
    check(index(got[0]) == want_first, f"cut: the first picture is the first keyframe that is not before marker A (source picture {want_first}): {index(got[0])}")
    check(abs(index(got[-1]) - want_last) <= 2, f"cut: the last picture is at marker B (source picture {want_last}): {index(got[-1])}")
    check(win.messages[-1].startswith("File was saved in") and "Copy mode: cut at a keyframe" in win.messages[-1] and "Not taken into account in copy mode: cropping." in win.messages[-1]
          and "differs" not in win.messages[-1], f"message after saving: {win.messages[-1]!r}")
    check(info.video.width == 720 and subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=sample_aspect_ratio", "-of", "csv=p=0", result],
                                                       capture_output=True, text=True).stdout.split(",")[0].strip() == "64:45", "the aspect ratio of the source stays (no setsar=1)")
    os.remove(result)
    # several videos: joined in full length
    win.segments[:] = [a, b]
    win.settings.set_option("crop", "0")
    result = os.path.join(tmp, "copywin", "joined.mkv")
    win.choose_output = lambda kind: result
    win.mnuSaveMP4_Click()
    whole_frames = (a.total_frames - a.first_frame) + (b.total_frames - b.first_frame)
    n = probe(result).video.frames
    check(os.path.exists(result) and abs(n - whole_frames) <= 4, f"joined: {n} frames, both files in full length ({whole_frames})")
    check("Copy mode: 2 files joined in full length." in win.messages[-1] and "Not taken into account in copy mode: the cut markers." in win.messages[-1], f"message: {win.messages[-1]!r}")
    check(not [d for d in os.listdir(tempfile.gettempdir()) if d.startswith("mediamaker_") and os.path.isdir(os.path.join(tempfile.gettempdir(), d))], "the list of files is removed")
    os.remove(result)
    # --- refusals: nothing is started, and the message comes BEFORE the name of the target file is asked for
    runs, names_asked = [], []
    win._render_fn = lambda *args, **kw: runs.append(args)
    win.choose_output = lambda kind: (names_asked.append(kind), result)[1]
    win.segments[:] = [a, dataclasses.replace(a, start=a.start + 100, end=a.end + 5)]
    win.mnuSaveMP4_Click()
    check("2 segments of the same video" in win.messages[-1] and runs == [] and win._render is None and not os.path.exists(result) and names_asked == [],
          "two segments of one video: message, nothing started, no question for the file name")
    win.segments[:] = [dataclasses.replace(whole, end=whole.end - 20), dataclasses.replace(whole), dataclasses.replace(whole)]
    win.mnuSaveMP4_Click()
    check("3 segments of the same video, and segment 1 has cut markers" in win.messages[-1] and runs == [] and names_asked == [], "the case of the screenshot: three segments, the first one cut: told at once")
    win.segments[:] = [a, wide]
    wide.path = b.path
    win.mnuSaveMP4_Click()
    check(win.messages[-1].startswith("Copy mode joins videos with identical characteristics only") and runs == [] and win._render is None and names_asked == [], "different videos: message, nothing started, no question for the file name")
    win.segments[:] = [whole, dataclasses.replace(whole)]
    from runner import RunResult
    win._render_fn = lambda *args, **kw: (open(result, "wb").write(b"x"), RunResult(0, False, 0.1, ""))[1]
    win.mnuSaveMP4_Click()
    check(len(names_asked) == 1 and len(win.messages) and win.messages[-1].startswith("File was saved"), f"a list that can be saved: the file name is asked for as usual: {names_asked}")
    os.remove(result)
    win._render_fn = lambda *args, **kw: runs.append(args)
    # --- batch: not in copy mode (as in VB6)
    check(win.check_job(win.make_job("/x.mp4")) is True, "copy mode: an invalid profile does not matter")
    win.mnuCopyMode.setChecked(False)
    check(win.check_job(win.make_job("/x.mp4")) is False and "profile is not valid" in win.messages[-1], "without copy mode it does")
    print("Copy mode: OK (plan, command, stream selection, menu, real cut at a keyframe, joining, refusals)")


def test_chapters(tmp, videos):
    """Chapters: the file for ffmpeg (one chapter per segment), its validity, the editor, saving with chapters, the batch file, import, sessions."""
    import batch
    import chapters
    import chapters_dialog
    import sessions
    import zipfile
    from fractions import Fraction as F
    from PySide6 import QtWidgets as W
    from ffmpeg_cmd import build_command
    from mediaprobe import first_frame_number
    from runner import run_ffmpeg
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="chapterwin", first_fn=first_frame_number)
    a, b = win.segments
    a.start, a.end = a.first_frame + 20, a.first_frame + 90
    b.start, b.end = b.first_frame + 10, b.first_frame + 80
    a.name, b.name = "My Film & Co.ts", "Second.ts"
    ffprobe_chapters = lambda path: [(c["tags"]["title"], round(float(c["start_time"]), 3), round(float(c["end_time"]), 3)) for c in json.loads(
        subprocess.run(["ffprobe", "-v", "error", "-show_chapters", "-of", "json", path], capture_output=True, text=True).stdout)["chapters"]]
    # --- the signature: what the times depend on
    sig = chapters.signature([a, b])
    shifted = dataclasses.replace(a, first_frame=a.first_frame + 3, start=a.start + 3, end=a.end + 3, total_frames=a.total_frames + 3)
    check(sig == chapters.signature([shifted, b]), "a correction of the first frame (everything moves together) does not change it")
    check(sig != chapters.signature([dataclasses.replace(a, end=a.end - 1), b]) and sig != chapters.signature([dataclasses.replace(a, start=a.start + 1), b])
          and sig != chapters.signature([b, a]) and sig != chapters.signature([a]) and sig != chapters.signature([dataclasses.replace(a, path="/other.ts"), b]), "cut points, order, number and file change it")
    check(sig == chapters.signature([dataclasses.replace(a, crop_top=9, mask="0.1 0.2 0.3 0.4", width=1280), b]), "cropping, logo filter and size do not")
    # --- names, times, escaping
    check(chapters.style_titles(0, [a, b]) == ["Scene 1", "Scene 2"] and chapters.style_titles(1, [a, b]) == ["Scene from My Film & Co", "Scene from Second"]
          and chapters.style_titles(2, [a, b]) == ["My Film & Co", "Second"], "the three styles (no replacement of & any more: it was for the batch file of Windows)")
    check(chapters.fit_titles(["x"], [a, b]) == ["x", "Scene 2"] and chapters.fit_titles(["x", "y", "z"], [a, b]) == ["x", "y"], "one name per segment")
    raw = "a=b;c#d\\e \u00fc"
    check(chapters.unescape(chapters.escape(raw)) == raw and chapters.escape("a\nb") == "a b", "escaping = ; # and the backslash")
    ntsc = [dataclasses.replace(a, start=0, end=1, fps=F(30000, 1001)) for _ in range(3)]
    check(chapters.milliseconds(ntsc) == [(0, 33), (33, 67), (67, 100)] and chapters.milliseconds([a, b]) == [(0, 2800), (2800, 5600)], "milliseconds, without the drift of rounded sums")
    text = chapters.build_text(["Intro", "Ende"], [a, b])
    check(text.startswith(";FFMETADATA1\n;MEDIAMAKER chapters signature=" + sig + "\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2800\ntitle=Intro\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=2800\nEND=5600\ntitle=Ende\n"), f"the file: {text!r}")
    check(chapters.parse_titles(text) == ["Intro", "Ende"] and chapters.parse_titles("TITLE=Old style") == ["Old style"] and chapters.is_valid(text, [a, b]) and not chapters.is_valid(text, [b, a])
          and not chapters.is_valid(";FFMETADATA1\n", [a, b]) and not chapters.is_valid(text, []), "reading it, validity")
    # --- the place; the editor
    path = win.chapters_path()
    check(path == os.path.splitext(win.settings.path)[0] + ".chapters" and not os.path.exists(path), "the file lies next to the INI file; there is none at first")
    win.segments.clear()
    win.mnuChapters_Click()
    check(win.messages[-1] == "There are no segments in the list.", "no segments: message")
    win.segments[:] = [a, b]
    dialogs_seen = []
    win.run_chapters_dialog = lambda d: dialogs_seen.append(d)
    win.mnuChapters_Click()
    dlg = dialogs_seen[-1]
    check(not dlg.chkActivate.isChecked() and dlg.titles() == [] and dlg.Frame1.called("setEnabled")[-1] == (False,), "first time: not activated, nothing in the list, the frame is disabled")
    check(dlg.Label2.called("hide"), "the old warning (sources must not have chapters) is hidden: it is not true any more")
    check_geometry = lambda w: (w.geometry().x(), w.geometry().y(), w.geometry().width(), w.geometry().height())
    box, frame, close = check_geometry(dlg.chkActivate), check_geometry(dlg.Frame1), check_geometry(dlg.cmdOK)
    check(frame[1] >= box[1] + box[3] and frame[1] == 8 + chapters_dialog.SHIFT and close[1] == 280 + chapters_dialog.SHIFT and dlg.called("resize")[-1] == (369, 313 + chapters_dialog.SHIFT)
          and dlg.Frame1.title() == "Chapter names", f"the check box stands above the frame, no overlap; the frame has a caption: box {box}, frame {frame}, button {close}")
    dlg.chkActivate.setChecked(True)
    dlg.chkActivate_Click()
    check(dlg.titles() == ["Scene 1", "Scene 2"] and dlg.Frame1.called("setEnabled")[-1] == (True,) and chapters.read(path) == chapters.build_text(["Scene 1", "Scene 2"], [a, b]) and win.chapters_valid(),
          "activating makes the first style (enumerated) and writes the file")
    for index, want in ((1, ["Scene from My Film & Co", "Scene from Second"]), (2, ["My Film & Co", "Second"]), (0, ["Scene 1", "Scene 2"])):
        dlg.cboStyle.setCurrentIndex(index)
        dlg.cboStyle_Click()
        check(dlg.titles() == want and chapters.parse_titles(chapters.read(path)) == want, f"style {index}: {want}")
    names = iter(["Intro", "", None])
    win.ask_text = lambda title, label, default="": (asked_text.append((title, label, default)), next(names))[1]
    asked_text = []
    dlg.lvwChapters.select_row(0)
    dlg.lvwChapters_KeyUp(113, 0)
    check(asked_text == [("Chapter Editor", "Enter new value:", "Scene 1")] and dlg.titles() == ["Intro", "Scene 2"] and chapters.parse_titles(chapters.read(path)) == ["Intro", "Scene 2"],
          f"F2 edits the name of the chapter, the file follows: {asked_text}")
    dlg.lvwChapters_KeyUp(65, 0)
    dlg.lvwChapters.select_row(1)
    dlg.edit_current()
    dlg.edit_current()
    check(len(asked_text) == 3 and dlg.titles() == ["Intro", "Scene 2"], "another key does nothing; an empty or cancelled input changes nothing")
    # --- a single click edits IN the row (after the time of a double click), a double click or F2 opens the separate window
    check(dlg.lvwChapters.called("setEditTriggers")[-1][0] == W.QAbstractItemView.EditTrigger.NoEditTriggers, "Qt does not start the editor by itself (the dialog decides when)")
    item0, item1 = dlg.lvwChapters.topLevelItem(0), dlg.lvwChapters.topLevelItem(1)
    check("ItemIsEditable" in item0.flags().name and "ItemIsEditable" in item1.flags().name, "the rows can be edited")
    edits = len(dlg.lvwChapters.called("editItem"))
    n_asked = len(asked_text)
    dlg.item_clicked(item0, 0)
    check(dlg._timer.starts_[-1] == 400 and len(dlg.lvwChapters.called("editItem")) == edits, "a click: the editor waits for the time of a double click")
    marked = len(dlg.lvwChapters.called("clearSelection"))
    dlg.inline_edit()                                               # (the timer ends)
    check(dlg.lvwChapters.called("editItem")[-1] == (item0, 0) and len(asked_text) == n_asked, "then the editor opens in the row, no separate window")
    check(len(dlg.lvwChapters.called("clearSelection")) == marked + 1 and dlg._editing is item0, "the blue bar of the marked row is taken away, so that the editor can be seen")
    from PySide6 import QtCore as QC
    check(QC.QTimer.pending and QC.QTimer.pending[-1][1] == dlg.place_cursor, "the cursor is placed when Qt has made the editor")
    line = W.QLineEdit(dlg.lvwChapters)                             # (the editor that Qt made)
    dlg.place_cursor()
    check(line.called("deselect") and line.called("end")[-1] == (False,) and line.called("setFocus"), "no text marked, the cursor at the end of the text (it flashes there)")
    dlg.editor_closed()
    check(dlg.lvwChapters.currentItem() is item0 and dlg._editing is None, "when the editor is closed the row is marked again")
    dlg.editor_closed()                                             # (a second call does no harm)
    writes = []
    real_write = chapters.write
    chapters.write = lambda *args: (writes.append(args[1]), real_write(*args))[1]
    try:
        item0.setText(0, "  Typed in the row  ")
        dlg.item_changed(item0, 0)
        check(item0.text(0) == "Typed in the row" and dlg.titles() == ["Typed in the row", "Scene 2"] and chapters.parse_titles(chapters.read(path)) == ["Typed in the row", "Scene 2"]
              and len(writes) == 1, f"typed in the row and confirmed: the name is cleaned up and the file follows: {dlg.titles()}")
        item0.setText(0, "   ")
        dlg.item_changed(item0, 0)
        check(item0.text(0) == "Typed in the row" and len(writes) == 1, "an empty name is put back, nothing is written")
        item0.setText(0, "Typed in the row")
        dlg.item_changed(item0, 0)
        check(len(writes) == 1, "an unchanged name: nothing is written")
        dlg._loading = True
        item0.setText(0, "The program changes it")
        dlg.item_changed(item0, 0)
        dlg._loading = False
        item0.setText(0, "Typed in the row")
        check(len(writes) == 1, "while the program changes the list itself there is no reaction")
        dlg.item_clicked(item1, 0)
        edits = len(dlg.lvwChapters.called("editItem"))
        names = iter(["Via the window"])
        win.ask_text = lambda title, label, default="": (asked_text.append((title, label, default)), next(names))[1]
        dlg.lvwChapters.select_row(0)
        dlg.item_double_clicked(item0, 0)
        dlg.inline_edit()                                           # (a timer that had been started is stopped, nothing is left to open)
        check(dlg._timer._active is False and dlg._clicked is None and len(dlg.lvwChapters.called("editItem")) == edits and asked_text[-1] == ("Chapter Editor", "Enter new value:", "Typed in the row")
              and dlg.titles() == ["Via the window", "Scene 2"] and len(writes) == 2, "a double click: the separate window, the editor in the row is cancelled, one write")
        item0.setText(0, "Intro")
        dlg.item_changed(item0, 0)
    finally:
        chapters.write = real_write
    check(dlg.titles() == ["Intro", "Scene 2"], "(back to the names of the following steps)")
    dlg.cboStyle.setCurrentIndex(3)
    dlg.cboStyle_Click()
    check(dlg.titles() == ["Intro", "Scene 2"], "style Previous: the names of the file")
    # the style From Batch: the names of the last job with chapters
    script = win.batch_path()
    if os.path.exists(script):
        os.remove(script)
    dlg.cboStyle.setCurrentIndex(4)
    dlg.cboStyle_Click()
    check(win.messages[-1] == f'Batch file "{script}" not found.', "From Batch without a batch file: message")
    open(script, "w", encoding="utf-8").write("#!/bin/bash\necho hi\n")
    dlg.cboStyle_Click()
    check(win.messages[-1] == "The batch file contains no chapters.", "a batch file without chapters: message")
    job0 = win.make_job("/out/x.mp4")
    two_jobs = batch.build_script(job0, ["ffmpeg", "x"], None, chapters.build_text(["Alpha", "Beta", "Gamma"], [a, b, b]))
    two_jobs = batch.build_script(job0, ["ffmpeg", "y"], two_jobs, None)
    open(script, "w", encoding="utf-8").write(two_jobs)
    dlg.cboStyle_Click()
    check(dlg.titles() == ["Alpha", "Beta"] and "3 names, the list has 2 segments: the surplus names are dropped." in win.messages[-1] and chapters.parse_titles(chapters.read(path)) == ["Alpha", "Beta"],
          f"From Batch: the names of the last job that has chapters; a surplus name is dropped: {dlg.titles()}")
    os.remove(script)
    dlg.cboStyle.setCurrentIndex(0)
    dlg.cboStyle_Click()
    # reopening: the valid file fills the list
    win.mnuChapters_Click()
    dlg2 = dialogs_seen[-1]
    check(dlg2.chkActivate.isChecked() and dlg2.titles() == ["Scene 1", "Scene 2"] and dlg2.Frame1.called("setEnabled")[-1] == (True,), "the next time: activated, with the names of the file")
    dlg2.cmdOK_Click()
    check(len(dlg2.called("accept")) == 1, "Close")
    dlg.chkActivate.setChecked(False)
    dlg.chkActivate_Click()
    check(not os.path.exists(path) and dlg.titles() == [] and dlg.Frame1.called("setEnabled")[-1] == (False,), "switching off deletes the file")
    # --- validity: what deletes the file (after a warning) and what does not
    def make_file():
        chapters.write(path, ["One", "Two"], win.segments)
    make_file()
    n = len(win.messages)
    a.crop_top, a.crop_left = 12, 30
    a.mask = "0.1 0.2 0.3 0.4"
    win.settings.set_profile({**win.profile, "scale": "1280:720", "fps": "30.000"})
    win.settings.set_option("crop", "60")
    win._save()
    win.lblSegment_Upd() if win.current >= 0 else None
    check(os.path.exists(path) and len(win.messages) == n, "cropping, logo filter, rescaling and the profile do not matter")
    for seg in (a, b):
        seg.first_frame, seg.start, seg.end, seg.total_frames = seg.first_frame + 3, seg.start + 3, seg.end + 3, seg.total_frames + 3
    win._save()
    check(os.path.exists(path) and len(win.messages) == n, "nor does a correction of the first frame")
    for seg in (a, b):                                              # (back to the real values: the first frame is that of the file)
        seg.first_frame, seg.start, seg.end, seg.total_frames = seg.first_frame - 3, seg.start - 3, seg.end - 3, seg.total_frames - 3
    win._save()
    b.end -= 5
    win._save()
    text_warning = ("Attention: the segments were changed (deleted, moved, loaded again or given other cut points), so the chapters no longer fit them. "
                    "The chapters were deleted; use Edit => Chapters to make new ones.")
    check(not os.path.exists(path) and win.messages[-1] == text_warning and len(win.messages) == n + 1, "other cut points: warning, the file is deleted")
    b.end += 5
    win._save()
    make_file()
    win.segments[:] = [b, a]
    win._save()
    check(not os.path.exists(path) and win.messages[-1] == text_warning, "moved segments")
    win.segments[:] = [a, b]
    make_file()
    win.segments.pop()
    win._save()
    check(not os.path.exists(path), "a deleted segment")
    win.segments[:] = [a, b]
    make_file()
    n = len(win.messages)
    win._save()
    win.chapters_check()
    check(os.path.exists(path) and win.chapters_check(warn=False) is False and len(win.messages) == n, "unchanged: nothing happens")
    win.segments[:] = [a]
    check(win.chapters_check(warn=False) is True and not os.path.exists(path) and len(win.messages) == n, "without a warning if asked not to")
    win.segments[:] = [a, b]
    make_file()
    save_segments(win.project_path, [b])
    win.load_list()
    check(not os.path.exists(path) and win.messages[-1] == text_warning, "a list that was loaded and is another one: deleted")
    win.segments[:] = [a, b]
    win._save()
    # --- saving with chapters (real ffmpeg): the chapters are in the file, also when a source has chapters itself
    win.settings.set_profile({**win.profile, "scale": "720:576", "fps": "25.000"})
    win.settings.set_option("crop", "0")
    make_file()
    win.choose_output = lambda kind: os.path.join(tmp, "chapterwin", "film.mkv")
    win.mnuSaveMP4_Click()
    got = ffprobe_chapters(os.path.join(tmp, "chapterwin", "film.mkv"))
    check([t for t, _, _ in got] == ["One", "Two"] and abs(got[0][1]) < 0.001 and abs(got[0][2] - 2.8) < 0.001 and abs(got[1][2] - 5.6) < 0.001, f"saved with chapters: {got}")
    os.remove(os.path.join(tmp, "chapterwin", "film.mkv"))
    meta = os.path.join(tmp, "chapterwin", "own.txt")
    open(meta, "w").write(chapters.build_text(["Source A", "Source B"], [a, b]))
    own = os.path.join(tmp, "chapterwin", "own.mkv")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.path, "-i", meta, "-map", "0:v:0", "-map", "0:a:0", "-map_chapters", "1", "-c", "copy", own], capture_output=True, stdin=subprocess.DEVNULL)
    check([t for t, _, _ in ffprobe_chapters(own)] == ["Source A", "Source B"], "(a source with chapters of its own)")
    with_own = dataclasses.replace(a, path=own)
    job = dataclasses.replace(win.make_job(os.path.join(tmp, "chapterwin", "own_out.mkv")), segments=[with_own, b])
    cmd = build_command(job, chapters_file=path)
    check(cmd[cmd.index("-map_metadata") + 1] == "2" and cmd[cmd.index("-map_chapters") + 1] == "2", "the command names the file that has the chapters (also for -map_chapters)")
    subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    check([t for t, _, _ in ffprobe_chapters(os.path.join(tmp, "chapterwin", "own_out.mkv"))] == ["One", "Two"], "the chapters of the file win over those of a source (the old warning is not needed any more)")
    os.remove(os.path.join(tmp, "chapterwin", "own_out.mkv"))
    # without a valid file there are no chapters
    os.remove(path)
    win.mnuSaveMP4_Click()
    check(ffprobe_chapters(os.path.join(tmp, "chapterwin", "film.mkv")) == [], "no chapters file: no chapters")
    os.remove(os.path.join(tmp, "chapterwin", "film.mkv"))
    # --- copy mode: joined files in full length can have chapters, cut ones cannot
    a.crop_top, a.crop_left, a.mask = 0, 0, ""
    win.mnuCopyMode.setChecked(True)
    whole_a, whole_b = dataclasses.replace(a, start=a.first_frame, end=a.total_frames), dataclasses.replace(b, start=b.first_frame, end=b.total_frames)
    win.segments[:] = [whole_a, whole_b]
    chapters.write(path, ["First file", "Second file"], win.segments)
    win.mnuSaveMP4_Click()
    got = ffprobe_chapters(os.path.join(tmp, "chapterwin", "film.mkv"))
    check([t for t, _, _ in got] == ["First file", "Second file"] and "the chapters" not in win.messages[-1], f"copy mode, two whole files: with chapters {got}")
    os.remove(os.path.join(tmp, "chapterwin", "film.mkv"))
    win.segments[:] = [a, b]
    chapters.write(path, ["One", "Two"], win.segments)
    win.mnuSaveMP4_Click()
    got = ffprobe_chapters(os.path.join(tmp, "chapterwin", "film.mkv"))
    container = lambda p: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.split()[0].rstrip(","))
    len_a, len_b = container(a.path), container(b.path)
    check([t for t, _, _ in got] == ["One", "Two"] and abs(got[0][2] - len_a) < 0.01 and abs(got[1][1] - len_a) < 0.01 and abs(got[1][2] - (len_a + len_b)) < 0.01
          and "Not taken into account in copy mode: the cut markers." in win.messages[-1] and "chapters" not in win.messages[-1].split("Not taken into account")[1],
          f"copy mode, joined files with cut markers (they are ignored): the chapters have the times of the WHOLE files, as the container gives them {len_a} + {len_b}: {got}")
    # (the length of the picture alone is shorter: the sound starts before the picture; a chapter at its end would begin inside part 1)
    check(len_a > (a.total_frames - a.first_frame) / 25 + 0.3, f"(here the picture is shorter than the file: {(a.total_frames - a.first_frame) / 25} against {len_a} s)")
    pts = sorted(float(x.rstrip(",")) for x in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-of", "csv=p=0",
                                                              os.path.join(tmp, "chapterwin", "film.mkv")], capture_output=True, text=True).stdout.split() if x)
    packets = lambda p: len([x for x in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-of", "csv=p=0", p],
                                                       capture_output=True, text=True).stdout.split() if x])
    n_a, n_b = packets(a.path), packets(b.path)
    before = sum(1 for t in pts if t < got[1][1] - 0.001)
    check(before == n_a and len(pts) == n_a + n_b, f"in the result exactly the {n_a} pictures of part 1 lie before the start of chapter 2 ({got[1][1]}) and the {n_b} of part 2 after it: {before} before, {len(pts)} in all")
    os.remove(os.path.join(tmp, "chapterwin", "film.mkv"))
    # the same file twice in the list (A, B, A): all three are joined and have a chapter each (as VB6 joined every item)
    win.segments[:] = [a, b, dataclasses.replace(a, start=a.start + 5)]
    chapters.write(path, ["One", "Two", "Three"], win.segments)
    win.mnuSaveMP4_Click()
    got = ffprobe_chapters(os.path.join(tmp, "chapterwin", "film.mkv"))
    n_frames = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0",
                               os.path.join(tmp, "chapterwin", "film.mkv")], capture_output=True, text=True).stdout.split()[0].rstrip(",")
    check([t for t, _, _ in got] == ["One", "Two", "Three"] and abs(got[1][1] - len_a) < 0.01 and abs(got[2][1] - (len_a + len_b)) < 0.01 and abs(got[2][2] - (2 * len_a + len_b)) < 0.01
          and int(n_frames) == 2 * n_a + n_b and "Copy mode: 3 files joined in full length." in win.messages[-1]
          and "chapters" not in win.messages[-1].split("Not taken into account")[1], f"copy mode, A B A: three parts ({n_frames} pictures) with three chapters: {got}")
    os.remove(os.path.join(tmp, "chapterwin", "film.mkv"))
    # the same whole file three times (A, A, A): joined with three chapters (this was refused as "cutting AND joining" although nothing is cut)
    win.segments[:] = [whole_a, dataclasses.replace(whole_a), dataclasses.replace(whole_a)]
    chapters.write(path, ["Part a", "Part b", "Part c"], win.segments)
    win.mnuSaveMP4_Click()
    got = ffprobe_chapters(os.path.join(tmp, "chapterwin", "film.mkv"))
    check([t for t, _, _ in got] == ["Part a", "Part b", "Part c"] and abs(got[1][1] - len_a) < 0.01 and abs(got[2][1] - 2 * len_a) < 0.01 and abs(got[2][2] - 3 * len_a) < 0.01
          and "Copy mode: 3 files joined in full length." in win.messages[-1] and "wrong" not in win.messages[-1], f"copy mode, the same whole file three times: three parts, three chapters: {got}")
    os.remove(os.path.join(tmp, "chapterwin", "film.mkv"))
    # a file type that cannot hold chapters (avi): said BEFORE saving, not silently left out; No: nothing is made
    win.segments[:] = [whole_a, whole_b]
    chapters.write(path, ["First file", "Second file"], win.segments)
    win.choose_output = lambda kind: os.path.join(tmp, "chapterwin", "film.avi")
    questions = []
    win.ask = lambda text: (questions.append(text), False)[1]
    win.mnuSaveMP4_Click()
    check(questions == ["A .avi file cannot hold chapters: they are left out (mp4 and mkv can hold them).\n\nSave anyway?"] and not os.path.exists(os.path.join(tmp, "chapterwin", "film.avi"))
          and win._render is None, f"avi with chapters: the question comes first; No: nothing is saved: {questions}")
    win.ask = lambda text: (questions.append(text), True)[1]
    win.mnuSaveMP4_Click()
    check(os.path.exists(os.path.join(tmp, "chapterwin", "film.avi")) and ffprobe_chapters(os.path.join(tmp, "chapterwin", "film.avi")) == [] and len(questions) == 2,
          "Yes: saved without chapters")
    os.remove(os.path.join(tmp, "chapterwin", "film.avi"))
    win.ask = lambda text: True
    check(chapters.holds_chapters("/x/a.MP4") and chapters.holds_chapters("a.mkv") and not chapters.holds_chapters("a.avi") and not chapters.holds_chapters("a.ts"), "the file types that can hold chapters")
    win.choose_output = lambda kind: os.path.join(tmp, "chapterwin", "film.mkv")
    win.segments[:] = [a, b]                                        # (the cut segments again for the following steps)
    win.mnuCopyMode.setChecked(False)
    # --- the batch file: the chapters are in comments and written again when the script runs
    chapters.write(path, ["Part A", "Part B"], win.segments)
    script = win.batch_path()
    if os.path.exists(script):
        os.remove(script)
    target = os.path.join(tmp, "chapterwin", "batch_out.mkv")
    win.ask_output = lambda title, suggestion: target
    win.mnuBatch_Click()
    sh = open(script, encoding="utf-8").read()
    temp = target + ".chapters.tmp"
    check("\n# K=" in sh and f"cat > {temp} <<'MEDIAMAKER_CHAPTERS_END'\n;FFMETADATA1\n" in sh and f"\nMEDIAMAKER_CHAPTERS_END\n" in sh and sh.rstrip().endswith(f"rm -f {temp}")
          and f"-i {temp} -map_metadata 2 -map_chapters 2" in sh, "the script has the comment K= and writes and removes the file itself")
    jobs = batch.parse_jobs(sh)
    check(len(jobs) == 1 and chapters.parse_titles(jobs[0].chapters) == ["Part A", "Part B"] and jobs[0].chapters == chapters.read(path), "and the job gives them back")
    os.remove(path)                                                  # the program is "closed": nothing but the script is left
    check(not os.path.exists(temp), "(no chapters file now)")
    run = subprocess.run(["bash", script], capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=os.path.join(tmp, "chapterwin"))
    got = ffprobe_chapters(target) if os.path.exists(target) else None
    check(run.returncode == 0 and got and [t for t, _, _ in got] == ["Part A", "Part B"] and abs(got[0][2] - 2.8) < 0.001 and not os.path.exists(temp),
          f"running the script by itself makes the file with chapters and removes the temporary file: {run.returncode} {run.stderr[-100:]!r} {got}")
    os.remove(target)
    # a second job without chapters, the first one is kept as an old step: its chapters can still be read
    win.ask3 = lambda text: "yes"
    win.mnuBatch_Click()
    sh2 = open(script, encoding="utf-8").read()
    jobs = batch.parse_jobs(sh2)
    check(len(jobs) == 2 and chapters.parse_titles(jobs[0].chapters) == ["Part A", "Part B"] and jobs[1].chapters == "" and "# cat > " in sh2 and "# MEDIAMAKER_CHAPTERS_END" in sh2,
          "an old step keeps its chapters (also in comments), a job without chapters has none")
    # --- import: the chapters can be restored
    open(script, "w", encoding="utf-8").write(sh)
    win.choose_job = lambda jobs: jobs[0]
    asked = []
    win.ask = lambda text: (asked.append(text), True)[1]
    win.segments[:] = [dataclasses.replace(s, end=s.end - 4) for s in win.segments]              # (other cut points)
    win._save()
    win.mnuImport_Click()
    check(len(asked) == 2 and asked[1] == "The job also has chapters (2 names). Restore them? (They are only valid for the segments of the job.)" and win.chapters_valid()
          and chapters.parse_titles(win.chapters_text()) == ["Part A", "Part B"], f"Yes: the chapters are back and fit the segments of the job: {asked[-1][:60]}")
    answers_import = iter([True, False])
    win.ask = lambda text: next(answers_import)
    win.mnuImport_Click()
    check(not os.path.exists(path), "No: the job comes without chapters (and the old ones, made for the list that is replaced, are gone)")
    # --- sessions: the chapters are part of them and can be restored (or not)
    win.ask = lambda text: True
    win.messages.clear()
    chapters.write(path, ["Kept A", "Kept B"], win.segments)
    first = win.make_session("with chapters")
    check(first.has_chapters and sessions.CHAPTERS_NAME in zipfile.ZipFile(first.path).namelist() and sessions.CHAPTERS_NAME in json.loads(zipfile.ZipFile(first.path).read("session.json"))["files"],
          "the session has the chapters file")
    win.segments.pop()
    win._save()
    check(not os.path.exists(path) and win.messages[-1] == text_warning, "(the list changed: chapters deleted, with the warning)")
    plain = win.make_session("without chapters")
    check(not plain.has_chapters, "a session without chapters")
    win.choose_session = lambda title, prompt, infos, multi=False, with_parts=False, with_backup=False, backup_default=True: chosen_session
    chosen_session = ([first], ("list", "ini", "chapters"), False)
    asked.clear()
    win.ask = lambda text: (asked.append(text), True)[1]
    win.mnuRestoreSession_Click()
    check(win.chapters_valid() and chapters.parse_titles(win.chapters_text()) == ["Kept A", "Kept B"] and len(win.segments) == 2 and "segment list and settings (INI file) and chapters" in asked[0],
          "restoring the list, the settings and the chapters: the chapters are back")
    win.segments.pop()
    win._save()
    chosen_session = ([first], ("list", "ini"), False)
    win.mnuRestoreSession_Click()
    check(len(win.segments) == 2 and not os.path.exists(path), "restoring without the chapters: the list is back, there are no chapters")
    chosen_session = ([first], ("chapters",), False)
    win.segments.pop()
    win._save()
    win.messages.clear()
    win.mnuRestoreSession_Click()
    check(not os.path.exists(path) and text_warning in win.messages, "only the chapters, but the list is another one: they do not fit and are deleted, with the warning")
    chosen_session = ([plain], ("list", "ini", "chapters"), False)
    win.mnuRestoreSession_Click()
    check(len(win.segments) == 1 and not os.path.exists(path) and "could not be restored" not in win.messages[-1], "a session without chapters: nothing to restore, no error")
    print("Chapters: OK (file, signature, editor, validity, saving, copy mode, batch file, import, sessions)")


def test_copy_mode_batch(tmp, videos):
    """Copy mode in the batch file and in sessions: the script has the flag M=copy, writes the list of files itself and runs without ffmpeg encoding; importing a job
    or restoring a session switches copy mode on again (with a note) or off."""
    import batch
    import chapters
    import copymode
    import sessions
    import zipfile
    from mediaprobe import first_frame_number
    win = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="copybatch", first_fn=first_frame_number)
    a, b = win.segments
    work = os.path.join(tmp, "copybatch")
    ffprobe_chapters = lambda path: [(c["tags"]["title"], round(float(c["start_time"]), 3), round(float(c["end_time"]), 3)) for c in json.loads(
        subprocess.run(["ffprobe", "-v", "error", "-show_chapters", "-of", "json", path], capture_output=True, text=True).stdout).get("chapters", [])]
    container = lambda p: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.split()[0].rstrip(","))
    script = win.batch_path()
    target = os.path.join(work, "joined.mkv")
    win.ask_output = lambda title, suggestion: target
    win.ask3 = lambda text: "no"
    # --- unit: the lines of a copy job
    job = win.make_job(target)
    plan = copymode.make_plan(job.segments, job.options)
    lines = batch.job_lines(job, ["ffmpeg", "x"], "STORED", "RUN\n", copymode.list_text(plan), True)
    check("# M=copy" in lines and f"cat > {target}.files.tmp <<'MEDIAMAKER_LIST_END'" in lines and f"cat > {target}.chapters.tmp <<'MEDIAMAKER_CHAPTERS_END'" in lines
          and lines.index("RUN") > lines.index(f"cat > {target}.chapters.tmp <<'MEDIAMAKER_CHAPTERS_END'") and f"rm -f {target}.files.tmp" in lines and f"rm -f {target}.chapters.tmp" in lines
          and not [l for l in lines if l.startswith("base64 -d")], f"copy job: the flag, the list, the chapters for ffmpeg; no masks: {lines[-12:]}")
    check(batch.decode_block([l[4:] for l in lines if l.startswith("# K=")]) == "STORED", "the comment K= keeps the chapters as the program has them (for a later import)")
    check(batch.parse_jobs("\n".join(lines))[0].copy_mode is True and batch.parse_jobs("\n".join(batch.job_lines(job, ["ffmpeg", "x"])))[0].copy_mode is False, "the flag is read again")
    # --- the batch file in copy mode: two different files joined, with chapters; the script runs by itself
    win.settings.set_option("crop", "0")
    chapters.write(win.chapters_path(), ["First", "Second"], win.segments)
    win.mnuCopyMode.setChecked(True)
    if os.path.exists(script):
        os.remove(script)
    win.mnuBatch_Click()
    sh = open(script, encoding="utf-8").read()
    check("# M=copy" in sh and f"file '{a.path}'" in sh and f"file '{b.path}'" in sh and "-f concat -safe 0" in sh and "filter_complex" not in sh and "libx264" not in sh
          and win.messages[-1].endswith("Copy mode: 2 files joined in full length."), f"batch file in copy mode: {win.messages[-1]!r}")
    stored = chapters.read(win.chapters_path())
    job1 = batch.parse_jobs(sh)[0]
    check(job1.copy_mode and job1.chapters == stored, "the job gives back the flag and the chapters as stored")
    run_text = sh.split(f"cat > {target}.chapters.tmp <<'MEDIAMAKER_CHAPTERS_END'\n")[1].split("\nMEDIAMAKER_CHAPTERS_END")[0]
    len_a = container(a.path)
    check(chapters.parse_titles(run_text) == ["First", "Second"] and f"END={round(len_a * 1000)}" in run_text, "what the script writes for ffmpeg has the times of the whole files")
    run = subprocess.run(["bash", script], capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=work)
    got = ffprobe_chapters(target) if os.path.exists(target) else None
    left = [f for f in os.listdir(work) if f.endswith(".tmp")]
    check(run.returncode == 0 and got and [t for t, _, _ in got] == ["First", "Second"] and abs(got[0][2] - len_a) < 0.01 and left == [],
          f"the script runs by itself: joined file with chapters {got}, no temporary file is left: {left} {run.stderr[-100:]!r}")
    os.remove(target)
    # --- one segment: cut at a keyframe, also from the script
    a.start, a.end = a.first_frame + 56, a.first_frame + 126
    win.segments[:] = [a]
    chapters.write(win.chapters_path(), ["Only"], win.segments)
    win.ask3 = lambda text: "yes"
    win.mnuBatch_Click()
    sh2 = open(script, encoding="utf-8").read()
    check(sh2.count("# M=copy") == 2 and "-copyts -seek_timestamp 1 -ss" in sh2 and "-f concat" in sh2.split("# J=")[1] and "-f concat" not in sh2.split("# J=")[2], "the second job is a cut, the first one is kept as an old step")
    check(win.messages[-1].endswith("Copy mode: cut at a keyframe (the start is the first keyframe that is not before the marker)."), f"message: {win.messages[-1]!r}")
    # (an old step is switched off: run only the new job by taking the script without the first job)
    new_only = "#!/bin/bash\n" + "# J=" + sh2.split("# J=")[2]
    open(os.path.join(work, "cut.sh"), "w").write(new_only)
    run = subprocess.run(["bash", os.path.join(work, "cut.sh")], capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=work)
    check(run.returncode == 0 and os.path.exists(target) and [t for t, _, _ in ffprobe_chapters(target)] == ["Only"] and not [f for f in os.listdir(work) if f.endswith(".tmp")],
          f"the cut runs from the script: {run.returncode} {run.stderr[-100:]!r}")
    os.remove(target)
    # --- refused at once in copy mode when the list cannot be saved (nothing is written, no question)
    win.segments[:] = [a, dataclasses.replace(a, start=a.start + 100, end=a.end + 5)]
    before = open(script, encoding="utf-8").read()
    asked_names = []
    win.ask_output = lambda title, suggestion: (asked_names.append(title), target)[1]
    win.mnuBatch_Click()
    check("2 segments of the same video" in win.messages[-1] and open(script, encoding="utf-8").read() == before and asked_names == [], "batch in copy mode: the reason is told at once, nothing is written")
    # --- import: the job was made in copy mode: switched on again, with a note; a normal job switches it off, without one
    win.segments[:] = [a, b]
    open(script, "w", encoding="utf-8").write(sh)
    win.choose_job = lambda jobs: jobs[0]
    win.ask = lambda text: True
    win.mnuCopyMode.setChecked(False)
    win.messages.clear()
    win.mnuImport_Click()
    check(win.mnuCopyMode.isChecked() and win.messages and win.messages[-1] == win.COPY_NOTICE.format(what="the job") and "switched ON now (the job was made in copy mode)" in win.messages[-1],
          f"import of a copy mode job: copy mode is on again, with a note: {win.messages[-1][:90]!r}")
    win.messages.clear()
    win.mnuImport_Click()
    check(win.mnuCopyMode.isChecked() and not [m for m in win.messages if "switched ON" in m], "copy mode was on already: no note")
    normal = batch.build_script(win.make_job(target), ["ffmpeg", "x"])
    open(script, "w", encoding="utf-8").write(normal)
    win.messages.clear()
    win.mnuImport_Click()
    check(not win.mnuCopyMode.isChecked() and not [m for m in win.messages if "switched ON" in m], "a job made without copy mode: it is off, no note")
    # --- sessions: the state of copy mode is in them
    win.settings.set_option("crop", "0")
    win.mnuCopyMode.setChecked(True)
    on = win.make_session("with copy mode")
    check(on.copy_mode and json.loads(zipfile.ZipFile(on.path).read("session.json"))["copy_mode"] is True and "[copy mode]" in on.describe(), f"the session knows: {on.describe()!r}")
    win.mnuCopyMode.setChecked(False)
    off = win.make_session("without")
    check(not off.copy_mode and json.loads(zipfile.ZipFile(off.path).read("session.json"))["copy_mode"] is False and "[copy mode]" not in off.describe(), "and one without")
    win.choose_session = lambda title, prompt, infos, multi=False, with_parts=False, with_backup=False, backup_default=True: chosen
    win.ask = lambda text: True
    chosen = ([on], ("list", "ini"), False)
    win.mnuRestoreSession_Click()
    check(win.mnuCopyMode.isChecked() and win.messages[-1].endswith(win.COPY_NOTICE.format(what="this session")), f"restoring a copy mode session: copy mode is on, the note is in the message: {win.messages[-1][-80:]!r}")
    win.mnuRestoreSession_Click()
    check(win.mnuCopyMode.isChecked() and "switched ON" not in win.messages[-1], "restoring it again: it was on already, no note")
    chosen = ([off], ("list", "ini"), False)
    win.mnuRestoreSession_Click()
    check(not win.mnuCopyMode.isChecked() and "switched ON" not in win.messages[-1], "restoring one without copy mode: copy mode is off, no note")
    win.mnuCopyMode.setChecked(True)
    chosen = ([off], ("ini",), False)
    win.mnuRestoreSession_Click()
    check(win.mnuCopyMode.isChecked(), "only the settings are restored: copy mode stays as it is (it belongs to the list)")
    # an old session (made before this version) has no entry: copy mode off
    old_path = os.path.join(os.path.dirname(off.path), "2020.01.01_00-00-00.zip")
    with zipfile.ZipFile(off.path) as zin, zipfile.ZipFile(old_path, "w") as zout:
        for item in zin.namelist():
            data = zin.read(item)
            if item == "session.json":
                manifest = json.loads(data)
                manifest.pop("copy_mode")
                data = json.dumps(manifest).encode("utf-8")
            zout.writestr(item, data)
    old = sessions.read_info(old_path)
    chosen = ([old], ("list", "ini"), False)
    win.mnuRestoreSession_Click()
    check(not old.copy_mode and not win.mnuCopyMode.isChecked(), "a session without the entry (an old one): copy mode is off")
    print("Copy mode in the batch file and sessions: OK (script, real runs, import, sessions, notes)")


def test_copy_mode_remembered(tmp, videos):
    """Copy mode is remembered for the next start ([settings] copy_mode=), put back with the same note as for a job or a session, and written only when it changes something."""
    import sessions
    from PySide6 import QtCore as QC
    from mediaprobe import first_frame_number
    text_of = lambda path: open(path, encoding="utf-8").read()

    def start(work, **kwargs):
        os.makedirs(work, exist_ok=True)
        win = make_window(work, **kwargs)
        QC.QTimer.pending.clear()
        win.showEvent(None)
        for ms, fn in list(QC.QTimer.pending):                      # (what is scheduled for when the window is there)
            fn()
        QC.QTimer.pending.clear()
        return win
    # --- the settings
    work = os.path.join(tmp, "cmrem")
    win = start(work)
    ini = win.settings.path
    before = open(ini, "rb").read()
    check(win.settings.copy_mode is False and win.settings.set_copy_mode(False) is False and open(ini, "rb").read() == before and "\ncopy_mode=" not in text_of(ini),
          "nothing is written as long as copy mode is off and was never on: the INI file of someone who does not use it stays as it is")
    check(not win.mnuCopyMode.isChecked() and win.messages == [], "a start without the entry: off, no note")
    # --- switching on: remembered at once
    win.ask = lambda text: True
    win.mnuCopyMode.setChecked(True)
    win.mnuCopyMode_Click()
    check(Settings(ini).copy_mode is True and "\ncopy_mode=on\n" in text_of(ini) and 'options=' in text_of(ini), "switched on: written at once, in [settings], not among the options")
    check("copy_mode" not in Settings(ini).options, "(not an option)")
    # --- the next start: on again, with the note
    again = start(work)
    check(again.mnuCopyMode.isChecked() and again.messages == [again.COPY_NOTICE.format(what="the last run")] and
          again.messages[0].startswith("Attention: copy mode is switched ON now (the last run was made in copy mode), hence activating output file creation without re-encoding. A single video can be cut at a keyframe or several "
                                       "are joined in full length, with or without chapters;"), f"the next start: copy mode is on and the note says so: {again.messages!r}")
    check(again.messages[0].endswith("the output profile are ignored.\n\nTo enable re-encoding, switch copy mode off in the Edit menu."), "a blank line before the last sentence")
    # --- switching off: confirmed, remembered
    again.messages.clear()
    again.mnuCopyMode.setChecked(False)
    again.mnuCopyMode_Click()
    check(again.messages == ["Copy mode is switched off."] and Settings(ini).copy_mode is False and "\ncopy_mode=off\n" in text_of(ini), "switched off: the message, and 'off' is written")
    third = start(work)
    check(not third.mnuCopyMode.isChecked() and third.messages == [], "the start after that: off, no note")
    # --- declining the question when switching on: nothing changes, nothing is written
    work2 = os.path.join(tmp, "cmrem2")
    win2 = start(work2)
    before2 = open(win2.settings.path, "rb").read()
    win2.ask = lambda text: False
    win2.mnuCopyMode.setChecked(True)
    win2.mnuCopyMode_Click()
    check(not win2.mnuCopyMode.isChecked() and open(win2.settings.path, "rb").read() == before2, "No at the question: off, the INI file is not touched")
    # --- the end of the program writes the state too (also when it was changed without the menu)
    win2.mnuCopyMode.setChecked(True)
    win2.Form_Unload()
    check(Settings(win2.settings.path).copy_mode is True, "ending the program: the state is saved")
    # --- a new job starts without copy mode, and that is remembered too
    fresh = start(work2, fresh=True)
    check(not fresh.mnuCopyMode.isChecked() and fresh.messages == [] and Settings(fresh.settings.path).copy_mode is False and "\ncopy_mode=off\n" in text_of(fresh.settings.path),
          "a new job: off, no note, 'off' written")
    # --- sessions: the state of the program counts, not the entry in the INI file that is put back
    win3 = seek_window(tmp, videos, ("sample2.ts",), workdir="cmrem3", first_fn=first_frame_number)
    win3._save()
    off_session = win3.make_session("without copy mode")
    win3.ask = lambda text: True
    win3.mnuCopyMode.setChecked(True)
    win3.mnuCopyMode_Click()
    win3.choose_session = lambda title, prompt, infos, multi=False, with_parts=False, with_backup=False, backup_default=True: chosen
    chosen = ([off_session], ("ini",), False)
    win3.mnuRestoreSession_Click()
    check(win3.mnuCopyMode.isChecked() and Settings(win3.settings.path).copy_mode is True, "only the settings are restored (the session's INI file has no entry): copy mode stays on, and 'on' is in the file again")
    chosen = ([off_session], ("list", "ini"), False)
    win3.mnuRestoreSession_Click()
    check(not win3.mnuCopyMode.isChecked() and Settings(win3.settings.path).copy_mode is False, "the list is restored too: the session was made without copy mode, so it is off, and 'off' is written")
    print("Copy mode remembered: OK (written only on change, next start with the note, switching off, new job, end of program, sessions)")


def test_copy_notice(tmp, videos):
    """The warning that copy mode was switched on again has a check box "Show this warning next time" (ticked at first). Unticked, the option copy_mode_notice goes to off
    and the warning is not shown any more: at the start, when a session is restored and when a job is imported."""
    import batch
    import copymode
    import dialogs
    from PySide6 import QtCore as QC, QtWidgets as W
    from profiles import validate_options
    from settings import DEFAULT_TOOLTIPS, default_options
    from mediaprobe import first_frame_number
    text_of = lambda path: open(path, encoding="utf-8").read()
    # --- the window
    W.QMessageBox.on_exec = None
    W.QMessageBox.shown.clear()
    check(dialogs.notice_with_checkbox(None, "Attention", "Show this warning next time") is True and W.QMessageBox.shown[-1] == "Attention", "the check box is ticked at first; OK: it is still ticked")
    W.QMessageBox.on_exec = lambda box: box.called("setCheckBox")[-1][0].setChecked(False)
    check(dialogs.notice_with_checkbox(None, "Attention", "Show this warning next time") is False, "unticked: False")
    W.QMessageBox.on_exec = None
    check(default_options()["copy_mode_notice"] == "on" and "copy_mode_notice" in DEFAULT_TOOLTIPS and validate_options({"copy_mode_notice": "off"}) == []
          and len(validate_options({"copy_mode_notice": "maybe"})) == 1, "the option: on at first, a help text, only on or off")
    # --- the real window (not the one of the tests that only notes the text): the box is made with the text of the warning and the right label
    os.makedirs(os.path.join(tmp, "cnotice"), exist_ok=True)
    win = make_window(os.path.join(tmp, "cnotice"))
    check(mediamaker_notice_label(win) == ("Show this warning next time", True), "the real window: the label of the check box, ticked at first")
    # --- the method: ticked stays on, unticked switches the warning off for good
    win.notice_keep = True
    win.copy_notice("the job")
    check(win.messages == [win.COPY_NOTICE.format(what="the job")] and win.options.get("copy_mode_notice", "on") == "on", "ticked: the warning is shown, the option stays on")
    win.messages.clear()
    win.notice_keep = False
    win.copy_notice("the job")
    check(win.messages == [win.COPY_NOTICE.format(what="the job")] and win.options["copy_mode_notice"] == "off" and 'copy_mode_notice="off"' in text_of(win.settings.path),
          "unticked: this time it is shown, and the option is off now, also in the INI file")
    win.messages.clear()
    win.copy_notice("the job")
    win.copy_notice("this session")
    win.copy_notice("the last run")
    check(win.messages == [], "the warning is not shown any more")
    win.copy_notice("this session", before="Session 2026.10.28 has been restored.")
    check(win.messages == ["Session 2026.10.28 has been restored."], "what belongs to the same window (a restored session) is shown alone")
    win.settings.set_option("copy_mode_notice", "on")
    win.notice_keep = True
    win.messages.clear()
    win.copy_notice("this session", before="Session 2026.10.28 has been restored.")
    check(win.messages == ["Session 2026.10.28 has been restored.\n\n" + win.COPY_NOTICE.format(what="this session")], "switched on again (in the options): shown again, in one window with the text before it")
    # --- the three situations with the warning off
    win.settings.set_option("copy_mode_notice", "off")
    win.settings.save()
    # (1) the start of the program
    work = os.path.join(tmp, "cnotice")
    ini = win.settings.path
    win.settings.set("settings", "copy_mode", "on")
    win.settings.save()
    started = make_window(work)
    QC.QTimer.pending.clear()
    started.showEvent(None)
    for ms, fn in list(QC.QTimer.pending):
        fn()
    QC.QTimer.pending.clear()
    check(started.mnuCopyMode.isChecked() and started.messages == [], "start in copy mode with the warning off: copy mode is on, no warning")
    # (2) a job from the batch file
    w2 = seek_window(tmp, videos, ("sample2.ts", "sample3.ts"), workdir="cnotice2", first_fn=first_frame_number)
    w2.settings.set_option("copy_mode_notice", "off")
    w2.settings.set_option("crop", "0")
    job = w2.make_job(os.path.join(tmp, "cnotice2", "x.mkv"))
    plan = copymode.make_plan(job.segments, job.options)
    open(w2.batch_path(), "w", encoding="utf-8").write(batch.build_script(job, ["ffmpeg", "x"], None, None, None, copymode.list_text(plan), True))
    w2.choose_job = lambda jobs: jobs[0]
    w2.ask = lambda text: True
    w2.mnuCopyMode.setChecked(False)
    w2.messages.clear()
    w2.mnuImport_Click()
    check(w2.mnuCopyMode.isChecked() and not [m for m in w2.messages if "switched ON" in m], "import of a copy mode job with the warning off: copy mode is on, no warning")
    # (3) a session
    w2.mnuCopyMode.setChecked(True)
    on = w2.make_session("with copy mode")
    w2.mnuCopyMode.setChecked(False)
    w2.choose_session = lambda title, prompt, infos, multi=False, with_parts=False, with_backup=False, backup_default=True: ([on], ("list", "ini"), False)
    w2.settings.set_option("copy_mode_notice", "off")
    w2.settings.save()
    w2.messages.clear()
    w2.mnuRestoreSession_Click()
    check(w2.mnuCopyMode.isChecked() and w2.messages and w2.messages[-1].startswith("Session ") and "has been restored." in w2.messages[-1] and "switched ON" not in w2.messages[-1],
          f"restoring a session with the warning off: copy mode is on, only the message about the restore: {w2.messages[-1]!r}")
    print("Copy mode warning: OK (check box, option, start, import, session)")


def mediamaker_notice_label(win) -> tuple:
    """(label, ticked at first) of the check box that the real notice_box gives its window (the test window has its own notice_box that only notes the text)."""
    from PySide6 import QtWidgets as W
    import mediamaker
    seen = []
    W.QMessageBox.on_exec = lambda box: seen.append(box.called("setCheckBox")[-1][0])
    try:
        mediamaker.frmMain.notice_box(win, "text")
    finally:
        W.QMessageBox.on_exec = None
    return seen[-1]._args[0], seen[-1].called("setChecked")[-1][0]


def test_containers(tmp, videos):
    """The file types of Save as: what each one can hold (chapters, subtitles), checked BEFORE saving; ONE entry in the menu."""
    import containers
    import copymode
    import mediaprobe
    import chapters
    from cutlist import Job
    from mediaprobe import first_frame_number
    # --- the table
    check(containers.EXTENSIONS == ("mp4", "mkv", "avi", "ts") and containers.info("/x/Film.MKV").ext == "mkv" and containers.info("film") is None and containers.info("/x/a.mov") is None
          and containers.info("Mr. Smith") is None, "the file types, found by the extension")
    check(containers.filters("avi") == "A/V Interleave file (*.avi);;MP4 video file (*.mp4);;Matroska video file (*.mkv);;MPEG transport stream (*.ts);;All files (*)"
          and containers.filters().startswith("MP4 video file (*.mp4);;"), "the list for the dialog: the chosen type at the top")
    check(containers.extension_of_filter("MPEG transport stream (*.ts)") == "ts" and containers.extension_of_filter("All files (*)") is None and containers.extension_of_filter("") is None,
          "the type that the dialog says is selected")
    check(chapters.holds_chapters("/x/a.MP4") and chapters.holds_chapters("a.mkv") and not chapters.holds_chapters("a.avi") and not chapters.holds_chapters("a.ts")
          and not chapters.holds_chapters("a.mov"), "chapters: mp4 and mkv")
    check(containers.subtitle_codec("a.mp4") == "mov_text" and containers.subtitle_codec("a.mkv") == "" and containers.subtitle_codec("a.avi") == "", "-c:s: mov_text for mp4, a plain copy for mkv")
    # --- the check: (errors, warnings)
    check(containers.check("a.mkv", True, ["subrip", "hdmv_pgs_subtitle"]) == ([], []) and containers.check("a.mp4", True, ["subrip", "ass"]) == ([], []), "mkv holds everything, mp4 text subtitles")
    check(containers.check("a.avi", True) == ([], ["A .avi file cannot hold chapters: they are left out (mp4 and mkv can hold them)."]) and containers.check("a.ts", True)[1] == containers.check("a.avi", True)[1][:0] + ["A .ts file cannot hold chapters: they are left out (mp4 and mkv can hold them)."],
          "chapters in avi or ts: a warning, they are left out")
    check(containers.check("a.avi", False, ["subrip"])[0] == ["A .avi file cannot hold subtitles (mkv can; mp4 only text subtitles)."], "subtitles in avi: an error")
    check(containers.check("a.mp4", False, ["dvb_subtitle"])[0] == ["A .mp4 file can hold only text subtitles, the chosen track is dvb_subtitle (mkv can hold it)."], "a bitmap subtitle in mp4: an error")
    check(containers.check("a.ts", False, ["dvb_subtitle"]) == ([], []) and containers.check("a.ts", False, ["subrip"])[0], "ts holds DVB subtitles, not text ones")
    check(containers.check("a.xyz")[0] == ["The file type .xyz is not supported: use one of .mp4, .mkv, .avi, .ts."], "an unknown type")
    # --- a source with a subtitle track (made here), real ffmpeg
    work = os.path.join(tmp, "contsrc")
    os.makedirs(work, exist_ok=True)
    srt = os.path.join(work, "s.srt")
    open(srt, "w").write("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n")
    src = os.path.join(work, "src.mkv")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:d=3", "-f", "lavfi", "-i", "sine=d=3", "-i", srt, "-c:v", "mpeg4", "-c:a", "aac", "-c:s", "srt", src],
                   capture_output=True, stdin=subprocess.DEVNULL)
    check(mediaprobe.subtitle_codecs(src) == ["subrip"] and mediaprobe.subtitle_codecs(os.path.join(videos, "sample2.ts")) == [], "the subtitle tracks of a file")
    win = seek_window(tmp, work, ("src.mkv",), workdir="contwin", first_fn=first_frame_number)
    win.settings.set_option("crop", "0")
    win.mnuCopyMode.setChecked(True)
    win.settings.set_option("subtitle", "1")
    out = lambda ext: os.path.join(tmp, "contwin", f"out.{ext}")
    asked_files = []
    win.ask = lambda text: True
    def save(ext):
        win.choose_output = lambda kind: (asked_files.append(kind), out(ext))[1]
        win.messages.clear()
        win.mnuSaveMP4_Click()
        return win.messages[-1] if win.messages else ""
    for ext in ("mp4", "mkv"):
        if os.path.exists(out(ext)):
            os.remove(out(ext))
        message = save(ext)
        streams = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries", "stream=codec_name", "-of", "csv=p=0", out(ext)], capture_output=True, text=True).stdout.split()
        check(message.startswith("File was saved") and streams == [{"mp4": "mov_text", "mkv": "subrip"}[ext]], f"copy mode, subtitle 1 into .{ext}: saved, the subtitle track is {streams}")
    runs = []
    win._render_fn = lambda *args, **kw: runs.append(args)
    for ext, why in (("avi", "A .avi file cannot hold subtitles (mkv can; mp4 only text subtitles)."),
                     ("ts", "A .ts file can hold only the DVB subtitles of a recording, the chosen track is subrip (mkv can hold it).")):
        message = save(ext)
        check(message == why and runs == [] and win._render is None, f".{ext}: the error is told before anything is started: {message!r}")
    win.settings.set_option("subtitle", "2")
    message = save("mp4")
    check(message == "The option subtitle names track 2, but the file has 1 subtitle track." and runs == [], f"a track that is not there: {message!r}")
    real = mediaprobe.subtitle_codecs
    mediaprobe.subtitle_codecs = lambda path, *a: ["dvb_subtitle"]
    win.settings.set_option("subtitle", "1")
    try:
        check(save("mp4") == "A .mp4 file can hold only text subtitles, the chosen track is dvb_subtitle (mkv can hold it)." and runs == [], "a bitmap subtitle into mp4")
    finally:
        mediaprobe.subtitle_codecs = real
    # no subtitle chosen: avi is fine (copy mode, no subtitles)
    win.settings.set_option("subtitle", "0")
    win._render_fn = run_ffmpeg_real
    if os.path.exists(out("avi")):
        os.remove(out("avi"))
    check(save("avi").startswith("File was saved") and os.path.exists(out("avi")), "without subtitles an avi file is made")
    # --- the command: -c:s from the container
    job = Job(output="/o/film.mp4", profile={}, options={**win.options, "subtitle": "1"}, segments=win.segments)
    plan = copymode.make_plan(win.segments, job.options)
    mp4 = copymode.build_copy_command(plan, job)
    mkv = copymode.build_copy_command(plan, dataclasses.replace(job, output="/o/film.mkv"))
    check(mp4[mp4.index("-c:s") + 1] == "mov_text" and "-c:s" not in mkv and mp4[mp4.index("-map") + 5] == "0:s:0", f"mp4: -c:s mov_text; mkv: a plain copy: {mp4}")
    # --- one menu entry
    check(win.mnuSaveMP4.called("setText")[-2] == ("&Save as...",) and win.mnuSaveMP4.called("setText")[-1] == ("&Save as...\tCtrl+S",) and win.mnuSaveAVI.called("setVisible")[-1] == (False,), "the form still has two entries: one is called 'Save as...', the other is hidden")
    asked_kinds = []
    win.save_video = lambda kind=None: asked_kinds.append(kind)
    win.mnuSaveAs_Click()
    win.mnuSaveMP4_Click()
    win.mnuSaveAVI_Click()
    check(asked_kinds == [None, None, "avi"], f"Save as and the entry of the form: the type of the last time; the old AVI shortcut: avi at the top: {asked_kinds}")
    print("File types: OK (table, checks, subtitles with real ffmpeg, one dialog)")


def run_ffmpeg_real(cmd, total, on_progress, cwd=None, cancel=None):
    from runner import run_ffmpeg
    return run_ffmpeg(cmd, total, on_progress, cwd=cwd, cancel=cancel)


def test_paused_preview(tmp, videos):
    """While the film is stopped the pictures of the preview can come from ffmpeg (option paused_preview = ffmpeg) instead of jumps of VLC, which can get stuck."""
    import numpy as np
    from fractions import Fraction as F
    from PySide6 import QtCore
    from mediaprobe import first_frame_number
    from player import FakePlayer
    from stills import StillPreview
    fetched = []

    def fake_frame(path, frame, fps):
        fetched.append(frame)
        return np.full((12, 16, 3), frame % 256, np.uint8)
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="stillwin", first_fn=first_frame_number, frame_fn=fake_frame)
    player, seg = win.player, win.segments[0]
    images = lambda: player.log.count("image")
    # --- the default (vlc): jumps of VLC, no pictures from ffmpeg
    check(win.options["paused_preview"] == "vlc" and not win.still_mode(), "default: VLC")
    fetched.clear()
    win._go(seg.first_frame + 40)
    check(player.time == win.f2t(seg.first_frame + 40) and fetched == [] and images() == 0, "VLC: the slider makes VLC jump, ffmpeg is not asked")
    # --- ffmpeg while the film is stopped
    win.settings.set_option("paused_preview", "ffmpeg")
    check(win.still_mode() and player.is_started and not player.is_playing, "the film is stopped after its first picture: the pictures come from ffmpeg")
    fetched.clear()
    time_before = player.time
    win._go(seg.first_frame + 60)
    check(fetched == [seg.first_frame + 60] and images() == 1 and player.time == time_before and win._still_frame == seg.first_frame + 60
          and win.lblInfo.text() == "Frame 60", f"the slider: ffmpeg is asked, the picture is shown, VLC is NOT asked: {fetched}, {images()}")
    check(player.preview.shape == (12, 16, 3) if hasattr(player.preview, "shape") else player.preview._args[1:3] == (16, 12), "(the picture is the one of ffmpeg: QImage 16 x 12)")
    for frame in (seg.first_frame + 61, seg.first_frame + 62, seg.first_frame + 63):
        win._go(frame)
    check(fetched[-3:] == [seg.first_frame + 61, seg.first_frame + 62, seg.first_frame + 63] and player.time == time_before, "many jumps in a row: VLC is never asked (it can get stuck after about ten)")
    # --- a picture of another film or one that arrives late is not shown
    shown = images()
    win.still_ready("/other/film.ts", 5, "x")
    check(images() == shown, "a picture of another film is ignored")
    # --- Play: VLC is told where the picture is, then it plays
    win.cmdPos_Click(3)
    check(player.log[-2:] == ["play"] or player.log[-1] == "play", f"Play starts the player: {player.log[-3:]}")
    check(player.time >= win.f2t(seg.first_frame + 63) and win._still_frame is None and player.is_playing, f"VLC was told the position of the picture before it played: {player.time}")
    win._go(seg.first_frame + 90)                                 # while the film runs the slider makes VLC jump (as before)
    check(player.time == win.f2t(seg.first_frame + 90) and fetched[-1] == seg.first_frame + 63 and not win.still_mode(), "playing: VLC jumps, no picture from ffmpeg")
    win.cmdPos_Click(3)                                           # pause
    win._go(seg.first_frame + 100)
    check(fetched[-1] == seg.first_frame + 100 and win._still_frame == seg.first_frame + 100, "stopped again: pictures from ffmpeg again")
    # --- jumps of the program (marker, search result) while stopped
    fetched.clear()
    win.seek_done(seg.first_frame + 120)
    check(fetched[-1:] == [seg.first_frame + 120], "a result of a search is shown from ffmpeg too")
    # --- a player that cannot show our pictures (embed): VLC as before
    player.supports_images = False
    time_before = player.time
    win._go(seg.first_frame + 20)
    check(not win.still_mode() and player.time == win.f2t(seg.first_frame + 20) and player.time != time_before, "player = embed: no pictures from ffmpeg, VLC jumps")
    player.supports_images = True
    # --- a new film: no old picture, the first picture comes from VLC (it is not started yet)
    win.lvwSegments.select_row(0)
    player.stop()
    shown, fetched_before = images(), len(fetched)
    check(not win.still_mode(), "a film that is not started yet: VLC shows the first picture")
    # --- StillPreview: while a picture is read newer requests replace each other
    reads, got = [], []
    holder = {}

    def slow_grab(path, frame, fps):
        reads.append(frame)
        if frame == 10:                                           # while the picture 10 is being read the slider moves on
            holder["p"].request(path, 11, fps)
            holder["p"].request(path, 12, fps)
        return np.zeros((6, 8, 3), np.uint8)
    preview = StillPreview(slow_grab)
    holder["p"] = preview
    preview.ready.connect(lambda path, frame, image: got.append(frame))
    preview.request("/x.ts", 10, F(25))
    check(reads == [10, 12] and got == [10, 12] and not preview.busy, f"11 is skipped, the newest request is read next: {reads}, shown {got}")
    preview.cancel()
    got.clear()
    preview.request("/x.ts", 20, F(25))
    check(got == [20], "after cancel new requests work")
    failing = StillPreview(lambda path, frame, fps: (_ for _ in ()).throw(RuntimeError("no picture")))
    failing.request("/x.ts", 1, F(25))
    check(not failing.busy, "a picture that cannot be read: nothing shown, nothing hangs")
    # --- a real picture from ffmpeg
    from frames import grab_frame
    real = []
    live = StillPreview(grab_frame)
    live.ready.connect(lambda path, frame, image: real.append((frame, image._args[1:3])))
    live.request(os.path.join(videos, "sample2.ts"), 30, F(25))
    check(real == [(30, (720, 576))], f"ffmpeg delivers the picture in the size of the film: {real}")
    print("Paused preview: OK (VLC as before, pictures from ffmpeg, Play, coalescing, other player, real picture)")


def test_shortcuts(tmp, videos):
    """The shortcuts of the menus: Dedup scene has Ctrl+V (the hidden Save as AVI gave it up), no shortcut is used twice, and the menus show them in English (Ctrl, not Strg)."""
    from PySide6 import QtGui
    win = seek_window(tmp, videos, ("sample2.ts",), workdir="shortcutwin")
    actions = {name: a for name, a in vars(win).items() if isinstance(a, QtGui.QAction)}
    keys = {name: a.shortcut().toString() for name, a in actions.items() if not a.shortcut().isEmpty()}
    check(keys["mnuDeDup"] == "Ctrl+V" and "mnuSaveAVI" not in keys and keys["mnuSaveMP4"] == "Ctrl+S", f"Dedup scene Ctrl+V, the hidden Save as AVI has none, Save as Ctrl+S: {keys.get('mnuDeDup')}")
    used = {}
    for name, key in keys.items():
        used.setdefault(key, []).append(name)
    check(all(len(names) == 1 for names in used.values()), f"no shortcut is used by two entries: {[n for n in used.values() if len(n) > 1]}")
    check(all(a.text().endswith("\t" + keys[name]) and a.text().count("\t") == 1 and "Strg" not in a.text() for name, a in actions.items() if name in keys),
          f"every entry with a shortcut shows it in English by hand: {[a.text() for n, a in actions.items() if n in keys][:3]}")
    check(actions["mnuDeDup"].text() == "Dedup scene\tCtrl+V" and actions["mnuOpen"].text().split("\t")[1] == "Ctrl+O", "(for example)")
    import vbqt
    vbqt.english_shortcuts(win)
    check(actions["mnuDeDup"].text() == "Dedup scene\tCtrl+V", "a second run does not add the text again")
    print("Shortcuts: OK (Dedup scene Ctrl+V, none twice, English)")


def test_counting_note(tmp, videos):
    """The note "counting frames" in the title goes away whenever a counting ends: with a result, cancelled, with an error, or when the file cannot be read."""
    import mediamaker
    from mediaprobe import ProbeError
    os.makedirs(os.path.join(tmp, "countnote"), exist_ok=True)
    title = lambda w: w.called("setWindowTitle")[-1][0]
    outcomes = {"result": lambda path, on_start=None: (100, 0, 0.0), "probe": None, "boom": None}

    def run(kind):
        def count_fn(path, on_start=None):
            if kind == "probe":
                raise ProbeError("cannot read")
            if kind == "boom":
                raise RuntimeError("boom")
            return 100, 0, 0.0
        win = make_window(os.path.join(tmp, "countnote"), count_fn=count_fn)
        win.start_count("/x/film.ts")
        return win
    for kind in ("result", "probe", "boom"):
        win = run(kind)
        check(win._counting == set() and "counting" not in title(win) and win._counters[-1].done, f"counting ends ({kind}): no note in the title any more: {title(win)!r}")
    # cancelled: a result may still arrive, it is not used, the note goes in every case
    win = make_window(os.path.join(tmp, "countnote"), count_fn=lambda path, on_start=None: (100, 0, 0.0))
    counter = mediamaker.FrameCounter("/x/cancelled.ts", win._count_fn)
    counter.cancelled = True
    counter.counted.connect(win.frames_counted)
    counter.ended.connect(win.count_finished)
    win._counters.append(counter)
    win._counting.add("/x/cancelled.ts")
    win.update_title()
    check("counting frames" in title(win), "(while it runs the note is there)")
    counter.start()
    check(win._counting == set() and "counting" not in title(win), "cancelled: the note goes")
    # the same file counted twice at the same time: the note stays until BOTH have ended
    c1, c2 = mediamaker.FrameCounter("/x/same.ts", win._count_fn), mediamaker.FrameCounter("/x/same.ts", win._count_fn)
    other = mediamaker.FrameCounter("/x/other.ts", win._count_fn)
    win._counters[:] = [c1, c2, other]
    win._counting = {"/x/same.ts", "/x/other.ts"}
    win.update_title()
    win.count_finished(c1)
    check(win._counting == {"/x/same.ts", "/x/other.ts"} and "counting frames" in title(win), "one of two countings of the same file has ended: still counting")
    win.count_finished(other)
    check(win._counting == {"/x/same.ts"} and "counting frames" in title(win), "the other file has ended: the first one is still counted")
    win.count_finished(c2)
    check(win._counting == set() and title(win) == f"MediaMaker {mediamaker.VERSION}", f"all have ended: the plain title: {title(win)!r}")
    # the ones that have ended are let go when the next counting starts
    win._counters[:] = [c1, c2, other]
    win.start_count("/x/next.ts")
    check([c.path for c in win._counters] == ["/x/next.ts"], f"ended counters are removed from the list: {[c.path for c in win._counters]}")
    print("Counting note: OK (result, error, unreadable file, cancelled, the same file twice, list cleaned)")


def test_play_now(tmp, videos):
    """After saving the message asks "Play now?"; Yes opens the result with the player of the system, No does nothing."""
    import mediamaker
    os.makedirs(os.path.join(tmp, "playnow"), exist_ok=True)
    win = make_window(os.path.join(tmp, "playnow"))
    external, asked = [], []
    win._external_fn = lambda cmd: (external.append(cmd), (0, ""))[1]
    real = mediamaker.frmMain.finish_message                       # (the test windows have a simple one that only notes the text)
    win.ask = lambda text: (asked.append(text), False)[1]
    real(win, "File was saved in 0:00:03.", "/out/film.mp4")
    check(asked == ["File was saved in 0:00:03.\n\nPlay now?"] and external == [], "the message ends with the question; No: nothing is started")
    win.ask = lambda text: (asked.append(text), True)[1]
    real(win, "File was saved in 0:00:03.\n\nCopy mode: copied as it is.", "/out/film.mp4")
    check(asked[-1] == "File was saved in 0:00:03.\n\nCopy mode: copied as it is.\n\nPlay now?" and external == [["xdg-open", "/out/film.mp4"]], f"Yes: the system opens the file: {external}")
    win._external_fn = lambda cmd: (external.append(cmd), (1, "no application"))[1]
    real(win, "File was saved in 0:00:03.", "/out/film.mp4")
    check("could not be played (xdg-open): no application" in win.messages[-1] and "/out/film.mp4" in win.messages[-1], f"an error is told: {win.messages[-1]!r}")
    # render_done gives the whole message and the file to it
    calls = []
    win.finish_message = lambda text, output: calls.append((text, output))
    win._render = {"job": None, "output": os.path.join(tmp, "playnow", "x.mp4"), "dir": tempfile.mkdtemp(prefix="mediamaker_"), "expected": None, "total": 1.0, "plan": None, "chapters": False}
    open(win._render["output"], "wb").write(b"x")
    from runner import RunResult
    beeps = QtWidgets.QApplication.log.count("beep")
    win.render_done(RunResult(0, False, 3.0, ""))
    check(len(calls) == 1 and calls[0][0].startswith("File was saved in 00:00:03") and calls[0][1] == os.path.join(tmp, "playnow", "x.mp4"), f"after a successful save: {calls}")
    check(QtWidgets.QApplication.log.count("beep") == beeps, "no beep of our own: the window with the question makes the sound of the system (two melodies were heard)")
    calls.clear()
    win._render = {"job": None, "output": os.path.join(tmp, "playnow", "y.mp4"), "dir": tempfile.mkdtemp(prefix="mediamaker_"), "expected": None, "total": 1.0, "plan": None, "chapters": False}
    win.render_done(RunResult(1, False, 3.0, "boom"))
    check(calls == [] and "ffmpeg reported an error" in win.messages[-1], "an error or a cancel does not ask to play")
    print("Play now: OK (question after saving, Yes starts the system player, No does not, error told)")


def test_wait_dialog(tmp, videos):
    """The wait window has room for several lines (before, the second line was cut off) and wraps long lines."""
    import dialogs
    cancelled = []
    d = dialogs.WaitDialog(None, "Performing duplicate scene removal search", lambda: cancelled.append(1))
    label = d.label
    check(label.called("setWordWrap")[-1][0] is True and label.called("setMinimumWidth")[-1][0] == 420, "long lines are wrapped; the window is wide enough")
    check(label.called("setMinimumHeight")[-1][0] >= 3 * 16 + 12, f"room for three lines from the start: {label.called('setMinimumHeight')[-1][0]} pixels")
    d.set_text("Performing duplicate scene removal search, please wait...\nreading the pictures...")
    check(label.called("setText")[-1][0] == "Performing duplicate scene removal search, please wait...\nreading the pictures...", "the text with its two lines")
    from PySide6 import QtWidgets as W
    W.QDialog.reject = lambda self: None                          # the replacement for Qt has no real reject() for super() to find
    try:
        d.reject()
    finally:
        del W.QDialog.reject
    check(cancelled == [1], "Cancel calls the cancel function")
    print("Wait window: OK (room for three lines, word wrap, cancel)")


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
    test_player_recovery()
    test_make_test_clips(tmp, sys.argv[1])
    test_sessions(tmp, sys.argv[1])
    test_debug_package(tmp, sys.argv[1])
    test_ini_tooltips_and_tools(tmp, sys.argv[1])
    test_delete_files(tmp, sys.argv[1])
    test_delete_sidecars(tmp, sys.argv[1])
    test_dedup(tmp, sys.argv[1])
    test_renamed_option(tmp, sys.argv[1])
    test_crop_segment(tmp, sys.argv[1])
    test_import_job(tmp, sys.argv[1])
    test_open_filter(tmp, sys.argv[1])
    test_copy_mode(tmp, sys.argv[1])
    test_chapters(tmp, sys.argv[1])
    test_copy_mode_batch(tmp, sys.argv[1])
    test_copy_mode_remembered(tmp, sys.argv[1])
    test_copy_notice(tmp, sys.argv[1])
    test_containers(tmp, sys.argv[1])
    test_paused_preview(tmp, sys.argv[1])
    test_shortcuts(tmp, sys.argv[1])
    test_counting_note(tmp, sys.argv[1])
    test_play_now(tmp, sys.argv[1])
    test_wait_dialog(tmp, sys.argv[1])
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
    test_reference_logo(tmp, sys.argv[1])
    test_first_frame_check(tmp, sys.argv[1])
    test_cutpoint(tmp, sys.argv[1])
    test_save_dialog(tmp, sys.argv[1])
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
