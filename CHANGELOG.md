# Changes

## 0.2 (in progress)

- Version number set to 0.2-dev.
- All comments, docstrings, messages, tests and documentation are now in English (the generated user interface files were
  regenerated; their code is unchanged).
- The Media info dialog also uses tabs (one per section). Both tab dialogs are at least as wide as all their tabs side by side; the tab
  names are not elided and there are no scroll arrows.
- The options dialog shows the groups as tabs along the top (Borders, Seeking, Audio/Subtitles, Batch, Technical) instead of one long list;
  after an invalid value it comes back on the tab with that value. The grouping is defined in the program (`OPTION_GROUPS` in `profiles.py`),
  the INI file still holds the plain `key="value"` list.
- Fix: a double click on an existing file in the Save dialog did nothing in the KDE dialog. The dialog now asks itself before overwriting
  (the option `DontConfirmOverwrite` is no longer used); MediaMaker only asks when it had to add the extension.
- The harmless warning `kf.kio.widgets.kdirmodel: No node found for item ...` of the KDE file dialog is no longer printed on the console.
- **Save as MP4 / Save as AVI** (Ctrl+S / Ctrl+V): the container follows from the extension of the target file (ffmpeg chooses it; mkv is
  also allowed in the MP4 dialog). The run goes on in the background with a progress bar (percent and remaining time) in the main
  window; **Cancel save** (Ctrl+C) stops ffmpeg and deletes the unfinished file; the masks for the logo filter are created in a
  temporary folder. Asks before overwriting; the suggested name is made from the recording's name as in VB6.
- **Batch** (Ctrl+B): writes the job as a bash script (`MediaMaker.sh` next to the INI file) whose comments carry the profile, options and
  segment list for a later import, with the masks, the ffmpeg call and the clean-up. Old steps can be kept (switched off with `#`).
  The new option `path_map` (`source=target;...`, `*` allowed) replaces the beginning of the source paths in the script, e.g. the
  changing `kio-fuse-XXXX` directory by a fixed mount point.
- A segment that is a whole file is now trimmed when several segments are joined: with sound starting before the first picture, concat
  had padded the picture of that segment with frozen frames (9 extra frames in the test).
- "Seek next commercial" / "Seek end of commercial" with the black border: the result could be one frame late, because the first frame of a
  commercial may still have (almost) the border of the movie. After the border search the result now moves onto a hard cut in the
  last frames before it (new option `cut_window`, default 5 frames, 0 = off; advanced `cut_diff` in the INI file).
- The main window has a fixed size again, as defined in VB6 (BorderStyle 1): the generator now fixes the whole window including the
  menu bar, not only its contents. The window could be enlarged before.
- A click on a caption or value of the "Target output profile" frame opens the profile editor (as in VB6).
- Fix: after quitting MediaMaker the console no longer shows typed characters. Several ffmpeg processes running at the same time
  left the terminal without echo; all external programs now get no terminal as standard input. New test `tests/test_terminal.py`.
- Fix: after deleting a segment the entry that takes its place is selected and loaded (after deleting the last entry: the new last
  one) instead of the cursor jumping to the top of the list.
- Fix: "Seek next commercial" could skip a short commercial break. The initial step is now limited to the option `pause` (minimum
  length of a break), a 240 s step could jump over a 165 s break.

## 0.1

First frozen state of the reimplementation in Python/PySide6 (not all functions of the VB6 program yet).

Included:

- **Main window** with segment list (JSON file `MediaMaker.json`, old CSV lists importable), opening and analysing videos
  (ffprobe), drag & drop, audio track selection, clean shutdown of VLC on exit.
- **Preview** with VLC: playback into memory, drawn by Qt (runs under Wayland and X11); slider, frame number and
  time; jump to a frame number; approaching the start position is secured.
- **Markers A/B** and **timeline** with 20 thumbnails, red crosses for missing frames, click to move the markers.
- **Frame numbers** count from the first decodable video frame (internally from the container start).
- **Segments**: delete, move, duplicate; when duplicating, the start of the movie is searched.
- **Search** for the end of a commercial or the next commercial break using border detection or the station logo (background,
  cancellable, with progress); **Auto crop**.
- **Profile and options** (dialogs with checking, named profiles, bit rate estimation); `pad` belongs to the profile.
- **Media info** (Ctrl+K) and **Information** (segment overview with position in the finished film, total length and estimated size).
- **ffmpeg call** checked against the VB6 program (example Elysium: command identical, pictures match), command line
  `run_job.py`, progress and remaining time.
- **User interface** from the VB6 forms (`ui/frm2qt.py`), Qt replacement for tests without a user interface.

Not included yet:

- Dialogs for crop and logo (frmCrop, frmRemoveLogo) and the buttons for them
- Saving as MP4/AVI from the user interface with a progress display (the building blocks `ffmpeg_cmd.py`, `runner.py`, `run_job.py` exist)
- Batch menu, import/restore of a session, subtitles, multilanguage, DVD mode, copy mode
- Overlap of segments, chapters (chapter()), preview at the cut point
