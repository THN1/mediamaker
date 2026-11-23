# MediaMaker 1.1-rc1 (release candidate)

Cuts, unifies and joins videos: films, parts of films, clips and TV recordings, in many formats and sizes. The pieces (segments) can
come from one or several files; they are brought to one size, frame rate and sound (the *profile*) and written as one file, as MP4, MKV, AVI
or TS, with chapters, several audio tracks and subtitles if wanted. For TV recordings there are special tools: finding the end of the
commercial breaks, removing black borders and the station logo.

A reimplementation of a VB6 program in Python with PySide6; the work is done by `ffmpeg`, the preview is shown with VLC. It runs on
Linux (developed on KDE). The user interface is still designed in the VB6 IDE and translated to PySide6 with `ui/frm2qt.py`.

The history and the details of every change are in [CHANGELOG.md](CHANGELOG.md).

## What it does

**Cutting**
- A list of segments (start and end markers) from one or more files; the timeline shows the pictures around the cut point, with
  frame-exact positioning. The segments are joined in the order of the list.
- Material of different formats, sizes, frame rates and sound can be joined: every segment is scaled to the size of the profile (with black
  bars if the profile parameter `pad` is on, stretched if it is off), set to its frame rate and its sound is resampled, so that one uniform file results.
  (Without re-encoding, in *Copy mode*, the pieces must have the same characteristics.)
- **DVD mode:** if all segments are VOB files of one title set (`VTS_02_1.VOB`, `VTS_02_2.VOB` ... of a `VIDEO_TS` folder; the menu files `VTS_nn_0.VOB` and `VIDEO_TS.VOB` do not count),
  the program works as the VB6 program did for a DVD. It starts by itself, no option is needed:
  - *Tracks.* Saving (also to a batch file) opens the dialog for the sound tracks and subtitles, unless the option `multitrack` is `off` (default `dvd`: only in DVD mode; `on`: always). It has three buttons:
    **OK** (go on with this choice), **Defaults** (the first sound track, no subtitles: what is saved when the option is `off`) and **Cancel** (stop saving, no file is written). The tracks are
    named by their stream id (`0x80` ... for sound, `0x20` ... for subtitles, shown in the dialog) and not by their position: every part of a DVD is analysed on its own and the order of
    its streams differs. To find tracks that turn up late (subtitles), the first 100 MB of every part that is used are looked at; this can take some seconds on a network drive.
  - *Languages.* The VOB files carry no language, the file `VTS_nn_0.IFO` in the same folder does: its codes are read and put into the dialog (a code of a track that has none is
    typed or picked from the drop-down list, which offers the codes of the IFO file first and then the usual ones with their names, e.g. `deu (German)`; the code is checked against
    ISO 639-2). The dialog says where the languages come from (*Languages retrieved from VTS_02_0.IFO*) or that there is none (*No valid IFO file found*): then the codes have to be chosen by hand.
  - *Parts that follow each other are one stream.* A DVD splits its stream at 1 GB in the middle of a group of pictures and of a block of sound, so the end of part 1 and the beginning of
    part 2 cannot be decoded without each other (about one second of picture and a block of sound are lost when they are read as two files). Segments that continue each other (part k
    to its end, part k+1 from its first picture, same size, mask and sound) are therefore read as ONE input (`concat:part1|part2`, the bytes joined) and cut by counted time. A cut
    between them, or parts that are not neighbours, are separate inputs joined with the concat filter, as before. The number of pictures of the new file can then be larger than the sum
    of the segments by those pictures; the check of the frame count knows that.
  - *Jumps in the time.* A DVD has jumps in the time of its stream (the time starts again at a new cell). DVD mode cuts by relative times, without `-copyts`, and makes the time of the
    pictures and of the sound from their count (newer versions of ffmpeg do not make the time continuous in a filter graph any more); `-reinit_filter 0` keeps the filter graph when the
    colour space changes inside a file. Copy mode is not used.
  - *No seeking.* Because of those jumps ffmpeg's `-ss` (seeking by time) is not used in DVD mode: a cut deep inside a title is reached by counting from the start of the stream, which reads the file from its beginning (a cut at 23:25 takes about as long as decoding 23 minutes).
  - *Subtitles.* Bitmap subtitles cannot be cut by a filter: they are cut by a list for the concat demuxer, which reads a file in pieces between two jumps of its time (found by one
    reading of all its packets with ffprobe, 10 to 30 s per GB, before the first saving of a file) and starts at the time of the picture. They go into mkv (and mp4); ffmpeg loses the
    LAST event of a DVD subtitle track in an mp4 file (also without MediaMaker), so mkv is the file type for them.
  - *Progress and checks.* The progress bar follows the frames written (the largest time of all streams jumps when a subtitle stream runs ahead). After a save the frames written are
    compared with the frames expected.
- *Frame counting.* The exact number of frames of a file is counted in the background after it has been opened (title: "counting frames 37 %"); for a big file on a network drive that can take minutes. The result is remembered in the INI section `[known_files]` (name without folder and size of the file = frames, ...), so that the same file is not counted again; option `known_files` = how many files are remembered (default 200, 0 = none).
- For TV recordings (container formats `.ts` or `.m2t`): *Seek next commercial / end of commercial* look for the pauses that commercials make in a recording (option `pause`);
  the preview shows every picture that the search reads (option `search_pictures`). The search uses the black border (option `crop` above 0)
  or, with `crop = 0`, the station logo (a reference logo made with the button L); improved logo detection: certain disturbances are tolerated
  and overlooked. *Dedup scene* removes a scene that is repeated at a cut; *Analyze cut point* makes a short test clip around a cut (option `cutpoint_length`: 6 seconds = the last 3 of the segment and the first 3 of the next one), with the
  filters of *Save as* and opens it in the viewer of MediaMaker (in every mode): every picture is shown one by one (buttons
  *Previous picture* / *Next picture*, the arrow keys left and right, or the slider; number and time of the picture are shown), and *Play with sound* (Space) plays the clip with its sound from
  the shown picture on; stepping or Space pauses. The pictures are written by ffmpeg into a temporary folder that is removed when the viewer is closed. The picture area has the display format
  of the source, so that the pictures are not distorted: for a DVD (DVD mode) the one the IFO file gives (4:3 or 16:9), otherwise the display aspect ratio of the file (DAR and SAR), changed by
  the crop that the clip has got (the global crop or the margins of the selected segment; only with the option `cutpoint_filters` = on, see the options dialog).
- *Copy mode* (Config menu): saves without re-encoding. One video is cut at the next keyframe, several files are joined in full
  length (chapters work). Cropping, logo filters, scaling and the profile are ignored in this mode.

**Picture**
- *Auto crop* finds black borders; every segment can have its own crop (crop dialog, 16:9 aware); the *DeLogo* function removes a
  station logo with a mask that is made from the picture. *Profile* sets size, frame rate, bit rates and audio codecs of the result;
  *Estimate bitrate(s)* (one dialog for both rates) and *Reuse source A/V* take values from the source.

**Tracks and chapters**
- *Multitrack* (option `multitrack` = `on`, `off` or `dvd`; `dvd` = the dialog opens only in DVD mode, see there): a dialog with two tabs chooses which audio tracks and subtitles go into the new file, in which
  order, with language codes (checked against ISO 639-2). Subtitles are cut like the picture; DVB subtitles (small pictures) are
  converted to `dvd_subtitle` for MP4; Teletext is ignored. The dialog has three buttons: OK (this choice), Defaults (only the main audio track, no subtitles) and Cancel (stop saving).
- *Chapters* (File menu): names for the parts of the joined film, written into MP4 and MKV files.

**Saving and automation**
- *Save as*: one dialog for all file types; before anything starts it is checked what the chosen type can hold (see below).
  The progress of the save, and of every longer job (the searches, auto crop, dedup scene, the clip around a cut), is shown in the bar at the bottom of
  the main window; the small red button at its right end (Ctrl+C) cancels it. While such a job runs the window cannot be used; while a file is saved the segments cannot be changed (the middle buttons, the markers, the timeline and most menu entries are off), but the pictures can still be looked at.
- *Batch* writes the job as a bash script (by default `~/MediaMaker.sh`) with the whole job in its comments; *Run now?* runs it in a
  terminal window of its own. *Import* reads a job from such a script again, `run_job.py` runs a script without the user interface.
- *Backup session / Restore session* keep the segment list, the options and the chapters; *Media info*
  and *Information* show the details of a file and of the joined film.

## The buttons beside the list

The column of buttons between the list of segments and the preview works on the selected segment (they do nothing without one; the list gets the focus again afterwards). From top to bottom:

| Button | Tooltip | What it does |
|---|---|---|
| red X | Remove selected segment | takes the segment out of the list |
| green arrow up | Shift selected segment up | moves the segment one place up |
| green arrow down | Shift selected segment down | moves the segment one place down |
| two pages | Duplicate segment | adds the segment again behind the selected one. A segment that was cut at its end (marker B before the end of the video): the copy starts where the original ends and runs to the end of the video; the preview jumps there and searches the end of the next commercial (*Seek end of commercial*), so that you only confirm the start of the new segment with *Set marker A*. A segment that is not cut: the copy has the full length, without a search |
| crop frame | Open cropping dialog | sets the margins (top, bottom, left, right) of this segment; they are shown as red bands over the preview. Without own margins the global option `crop` counts |
| picture | Open/close DeLogo dialog | **DeLogo:** a red rectangle appears over the preview; place it on the station logo (move it, pull the edges). The next click asks "Do you want to activate the DeLogo filter?" and stores the rectangle for the segment; for the next segment it is offered again. **Shift + click: RemoveLogo** (the tooltip changes while Shift is held): choose a frame that shows only the logo; its black and white picture becomes the mask of the removelogo filter |
| L | Create reference logo from current frame | takes the logo of the current picture as the reference for the search for commercials by the station logo (used when the option `crop` is 0). It needs a DeLogo rectangle or a RemoveLogo mask of the segment, and the logo must be visible in the current picture |
| trash can | Clear the list | removes all segments after a question |

## Keyboard shortcuts

The shortcuts of the menu entries (they are shown in the menus too). The other functions have no key; they are reached with the buttons and the menus.

| Key | Menu | Function |
|---|---|---|
| Ctrl+O | File | Open |
| Ctrl+L | File | Close all |
| Ctrl+J | File | Delete... (the source files of the list, for good) |
| Ctrl+N | File | Information... |
| Ctrl+H | File | Chapters... |
| Ctrl+S | File | Save as... |
| Ctrl+C | File | Cancel the running save or job (the red button beside the progress bar) |
| Ctrl+B | File | Batch... |
| Ctrl+M | File | Import... |
| Ctrl+Q | File | Backup session |
| Ctrl+Z | File | Restore session... |
| Ctrl+P | File | Delete session(s)... |
| Ctrl+X | File | Exit |
| Ctrl+G | Edit | Reuse source A/V |
| Ctrl+R | Edit | Auto crop |
| Ctrl+K | Edit | Media info |
| Ctrl+Y | Edit | Analyze cut point |
| Ctrl+V | Edit | Dedup scene |
| Ctrl+W | Edit | Seek next commercial |
| Ctrl+U | Edit | Seek end of commercial |
| Ctrl+F | Config | Profile... |
| Ctrl+A | Config | Save profile |
| Ctrl+D | Config | Copy mode (switch) |
| Ctrl+E | Config | Estimate bitrate(s) |
| Ctrl+T | Config | Options... |
| F1 | Help | Readme |

In the dialog *Analyze cut point*: left / right arrow = one picture back / forward, space = play / pause.

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

## Batch file

*File => Batch* (or the Batch button) writes the job into `MediaMaker.sh` and keeps the earlier jobs, switched off. Every job has a comment line after `# J=` that says which version and which
**commit** made it (`# Made by MediaMaker 0.8-dev, commit 87d8fe4 ...`), so that a script that is sent in for a bug can be matched with the program.

## Help menu

*Help => Readme* (F1) shows this file formatted. *Help => About MediaMaker* shows the version and, above all, the **commit** that the program was started from (read from git; a delivered
program without `.git` reads a file `COMMIT` next to it) and the versions of Python, PySide6, ffmpeg, ffprobe and VLC; "Copy information" puts them into the clipboard for a bug report.

## Installation

MediaMaker needs `ffmpeg` and `ffprobe` and VLC (libvlc) on the computer; they are not part of the program (install them with your package manager).

If `ffprobe` is missing when a file is opened, MediaMaker says so and, on openSUSE, Debian/Ubuntu, Fedora and Arch, offers to install FFmpeg for you: after "Yes" the package manager runs through `pkexec` (the system asks for the administrator password) and the file is opened. On other systems the message names the package to install. On openSUSE the FFmpeg of the standard repositories lacks H.264 and AAC; for those the [Packman](https://en.opensuse.org/Additional_package_repositories#Packman) repository is needed. VLC is not installed by this offer.

**AppImage** (any Linux distribution, x86_64): download `MediaMaker-1.0-x86_64.AppImage` from the releases page of the project, make it executable (`chmod +x MediaMaker-1.0-x86_64.AppImage`) and start it. Python, PySide6 and the other Python packages are inside; FFmpeg and VLC come from the system (see above).

**From the source** (needs Python 3.10 or newer and the Python packages in `requirements.txt`: PySide6, python-vlc, numpy, Pillow; Arch: `python-pyside6 python-vlc python-numpy python-pillow`; or `python3 -m pip install --user -r requirements.txt`):

```
bash install.sh                  # for you alone: ~/.local/bin/mediamaker, the menu of the desktop, the icon (--prefix /usr/local for everybody; --uninstall removes it)
mediamaker movie.ts              # new job with this file
mediamaker                       # load the most recently edited segment list
```

Without installing: `python3 mediamaker.py [movie.ts ...]` in the folder of the program. `python3 run_job.py JOB.sh --output movie.mp4` runs a job (a batch file) without the user interface.

**Optional:** a terminal program (`konsole`, `gnome-terminal`, `xfce4-terminal`, `xterm`, ... or the option `terminal`) for *Run now?*, `xdg-open` for *Play now?*.

### Where your files are

The settings (`MediaMaker.ini`), the segment list (`MediaMaker.json`), the sessions and the debug packages are in the folder `~/.config/MediaMaker` (or `$XDG_CONFIG_HOME/MediaMaker`). The environment variable `MEDIAMAKER_INI` names another INI file; the other files are then next to it. At the first start the program makes the INI file with the example profiles in it and asks you to choose the target profile (size, frame rate and bit rates of the new video; you can change it later with Config -> Load profile). `MediaMaker.example.ini` in the program folder shows every setting with its help text. The batch script is `~/MediaMaker.sh` (the option `batch`).

Development versions (the version number ends in `-dev`, for example when you run the program from a clone) keep these files next to the program instead and have the extra menu *Deploy* (with *Create debug package*).

### Settings

Settings are made in the options dialog (Config -> Options) and stored in the INI file; every option has a help text there (and in the
section `[ToolTipText]` of the INI file). Some options of interest: `player=memory|embed` and `paused_preview=vlc|ffmpeg` (the
preview; with `ffmpeg` the pictures of a stopped film come from ffmpeg and are frame exact), `multitrack=on|off|dvd`, `batch=` (the
file of the batch script; empty: `~/MediaMaker.sh`), `path_map=` (replaces the beginning of source paths in scripts, e.g. for a network
drive), `copy_mode_notice=on|off`. `MEDIAMAKER_DEBUG=1` writes a log with times in milliseconds (`mediamaker_debug.log` next to the INI file), `MEDIAMAKER_NO_FILTER=1` shows the unfiltered error output of ffmpeg.

## Bug reports and the debug package

If a search for a commercial or a cut goes wrong, select the segment, put the slider where the search stopped and press **Ctrl+Shift+F1** (there is no menu entry). After a warning it makes the folder `debug/<time>` next to the INI file and a zip file of the same name. It holds what is needed to understand the problem: the values of the segment, what the last search did, the options and versions, the segment list, pictures from the video, and an unchanged piece of the recording of about a minute (with picture and sound). `README.txt` in the package lists the files.

**The package contains private data**: your settings with the paths of your files, the whole segment list, and a piece of your video. Look at it before you send it to anybody, and delete what should not leave your computer. Attach the zip file to the report (Help -> About MediaMaker -> "Copy information" gives the versions) and say what went wrong, for example that the end of the commercial was found too early or too late, and at about which time.

## License

MediaMaker is free software under the **GNU General Public License, version 3** (see the file `LICENSE`). It uses PySide6 (LGPL), python-vlc, numpy and Pillow, and runs `ffmpeg` and VLC as separate programs.

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

Public versions (without `-dev`) are marked with a tag (`v1.0`, ...) and are on the branch `main` of the project page; the version number is in `version.py` (`VERSION`).
What changed is in [CHANGELOG.md](CHANGELOG.md).
