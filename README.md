# MediaMaker

Cuts TV recordings (`.ts`): removes commercials, black borders and the station logo, and writes the result as `.mp4`.
A reimplementation of the VB6 program in Python with PySide6; rendering is done with `ffmpeg`, the preview with VLC.
The user interface is still designed in the VB6 IDE and translated to PySide6 with `ui/frm2qt.py`.

The state of the work is described in [CHANGELOG.md](CHANGELOG.md).

## Requirements

- Python 3.10 or newer
- Packages: see `requirements.txt` (PySide6, python-vlc, numpy, Pillow)
- Programs: `ffmpeg` and `ffprobe` (in the PATH), VLC with libvlc

## Setup and start

```
cp MediaMaker.example.ini MediaMaker.ini      # then adapt it to your computer (MediaMaker.ini is not versioned)
python3 mediamaker.py movie.ts                # new job with this file
python3 mediamaker.py                         # load the most recently edited segment list
python3 run_job.py JOB.sh --output movie.mp4  # run a job without the user interface
```

Useful environment variables: `MEDIAMAKER_DEBUG=1` (log in `mediamaker_debug.log`), `MEDIAMAKER_NO_FILTER=1` (unfiltered error
output). In the INI file, section `[settings]`: `player=memory|embed`, `vlc_args=...`, `hide_messages=Text1|Text2`.

## Tests

The tests need no user interface (Qt is replaced by `ui/tests/qtstub`) and small sample videos (`sample.ts`, `sample2.ts`,
`sample3.ts`) that are not part of the repository:

```
python3 tests/test_app.py /path/to/sample/videos
python3 tests/test_border.py /path/to/sample/videos
python3 tests/test_logo.py /path/to/sample.ts
python3 tests/test_build.py /path/to/sample/videos
python3 ui/tests/test_frm2qt.py "/path/to/VB6/folder"
```

## Generating the user interface from VB6 forms

```
python3 ui/frm2qt.py /path/to/VB6/folder/*.frm --out ui/generated --stub
python3 ui/show_form.py frmMain --dir ui/generated        # preview of a form
```

## Versions

Changed states are marked with tags (`v0.1`, `v0.2`, ...). The next version is developed on `main`; the version number is in
`mediamaker.py` (`VERSION`).
