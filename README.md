# MediaMaker

Cuts TV recordings: removes commercials, black borders and the station logo, joins pieces of several files and writes the result
as MP4, MKV, AVI or TS, with chapters, several audio tracks and subtitles if wanted. A reimplementation of a VB6 program in
Python with PySide6; the work is done by `ffmpeg`, the preview is shown with VLC. It runs on Linux (developed on KDE).
The user interface is still designed in the VB6 IDE and translated to PySide6 with `ui/frm2qt.py`.

The history and the details of every change are in [CHANGELOG.md](CHANGELOG.md).

## What it does

**Cutting**
- A list of segments (start and end markers) from one or more files; the timeline shows the pictures around the cut point, with
  frame-exact positioning. The segments are joined in the order of the list.
- *Seek next commercial / end of commercial* look for the pauses that commercials make in a recording (option `pause`); *Dedup scene*
  removes a scene that is repeated at a cut; *Analyze cut point* makes a short test clip around a cut, with the filters of *Save as*,
  and opens it in Avidemux or VLC.
- *Copy mode* (Edit menu): saves without re-encoding. One video is cut at the next keyframe, several files are joined in full
  length (chapters work). Cropping, logo filters, scaling and the profile are ignored in this mode.

**Picture**
- *Auto crop* finds black borders; every segment can have its own crop (crop dialog, 16:9 aware); the *DeLogo* function removes a
  station logo with a mask that is made from the picture. *Profile* sets size, frame rate, bit rates and audio codecs of the result;
  *Estimate video/audio kb/s* and *Reuse source A/V* take values from the source.

**Tracks and chapters**
- *Multitrack* (option `multitrack`): a dialog with two tabs chooses which audio tracks and subtitles go into the new file, in which
  order, with language codes (checked against ISO 639-2). Subtitles are cut like the picture; DVB subtitles (small pictures) are
  converted to `dvd_subtitle` for MP4; Teletext is ignored. Cancel keeps only the main audio track.
- *Chapters* (Edit menu): names for the parts of the joined film, written into MP4 and MKV files.

**Saving and automation**
- *Save as*: one dialog for all file types; before anything starts it is checked what the chosen type can hold (see below).
  The progress is shown in the main window, *Cancel save* stops it.
- *Batch* writes the job as a bash script (by default `~/MediaMaker.sh`) with the whole job in its comments; *Run now?* runs it in a
  terminal window of its own. *Import* reads a job from such a script again, `run_job.py` runs a script without the user interface.
- *Backup session / Restore session* keep the segment list, the options and the chapters; *Media info*
  and *Information* show the details of a file and of the joined film; *Create debug package* collects what is needed for a bug report.

## Supported formats

**Input** (File -> Open): MPEG transport stream `.ts`, `.m2t`, MP4 `.mp4`, AVI `.avi`, DVD VOB (`*_1.vob`; a DVD mode with the
menu structure is not implemented yet) and, with *All files*, anything else that ffmpeg reads, e.g. `.mkv`. The audio codec of the
source has to match `acodec_in` of the profile (`mp2` by default; `ac3`, `aac`, `mp3`, `eac3` and `dts` are offered). Tested with DVB
recordings (`.ts`), MP4 and MKV files; teletext tracks are ignored.

**Output** (the file type follows from the extension of the name):

| Type | Chapters | Several audio tracks | Subtitles |
|------|----------|----------------------|-----------|
| `.mp4` | yes | yes (language code kept) | text (`mov_text`), DVB converted to `dvd_subtitle` |
| `.mkv` | yes | yes (language code kept) | every kind, copied as it is |
| `.avi` | no | yes (the code becomes the name of the track) | no |
| `.ts` | no | yes (language code kept) | DVB subtitles only, copied |

What a type cannot hold is reported before the job starts (chapters in AVI/TS: you are asked whether to save anyway; subtitles that
the type cannot hold: an error).

## Requirements

- Python 3.10 or newer
- Packages: see `requirements.txt` (PySide6, python-vlc, numpy, Pillow)
- Programs: `ffmpeg` and `ffprobe` (in the PATH), VLC with libvlc (preview). Optional: Avidemux (Analyze cut point), a terminal
  program (`konsole`, `gnome-terminal`, `xfce4-terminal`, `xterm`, ... or the option `terminal`) for *Run now?*, `xdg-open` for *Play now?*.

## Setup and start

```
cp MediaMaker.example.ini MediaMaker.ini      # then adapt it to your computer (MediaMaker.ini is not versioned)
python3 mediamaker.py movie.ts                # new job with this file
python3 mediamaker.py                         # load the most recently edited segment list
python3 run_job.py JOB.sh --output movie.mp4  # run a job without the user interface
```

Settings are made in the options dialog (Edit -> Options) and stored in the INI file; every option has a help text there (and in the
section `[ToolTipText]` of the INI file). Some options of interest: `player=memory|embed` and `paused_preview=vlc|ffmpeg` (the
preview; with `ffmpeg` the pictures of a stopped film come from ffmpeg and are frame exact), `multitrack=on|off`, `batch=` (the
file of the batch script; empty: `~/MediaMaker.sh`), `path_map=` (replaces the beginning of source paths in scripts, e.g. for a network
drive), `copy_mode_notice=on|off`. `MEDIAMAKER_DEBUG=1` writes a log (`mediamaker_debug.log`), `MEDIAMAKER_NO_FILTER=1` shows the
unfiltered error output of ffmpeg.

## Tests

The tests need no user interface (Qt is replaced by `ui/tests/qtstub`) and small sample videos (`sample.ts`, `sample2.ts`, `sample3.ts`;
`test_3.ts` with several audio and DVB subtitle tracks enables more tests) that are not part of the repository:

```
python3 tests/test_app.py /path/to/sample/videos
python3 tests/test_border.py /path/to/sample/videos
python3 tests/test_logo.py /path/to/sample.ts
python3 tests/test_build.py /path/to/sample/videos
python3 tests/test_terminal.py
python3 ui/tests/test_frm2qt.py "/path/to/VB6/folder"
```

## Generating the user interface from VB6 forms

```
python3 ui/frm2qt.py /path/to/VB6/folder/*.frm --out ui/generated --stub
python3 ui/show_form.py frmMain --dir ui/generated        # preview of a form
```

## Versions

Frozen states are marked with tags (`v0.1` to `v0.6`). The next version is developed on `main`; the version number is in
`mediamaker.py` (`VERSION`).
