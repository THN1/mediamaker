# Changes

## 0.3 (in progress)

- Version number set to 0.3-dev.
- The opacity of the red areas that mark the logo (DeLogo rectangle, band in the RemoveLogo dialog) is the new option `overlay_opacity`
  (percent, default 35; new tab "Logo" of the options dialog); a change applies to the rectangle at once.
- While Shift is held down, the tooltip of the logo button reads "Open/close RemoveLogo dialog" instead of "Open/close DeLogo dialog".
- RemoveLogo dialog: the picture is no longer distorted: the width of the window stays, the height of the picture box (and of the window)
  follows the proportions of the frame. A line of explanation below the buttons (and a tooltip) describes the slider.
- **RemoveLogo filter** (Shift + click on the logo button): a dialog shows the current frame as a black/white picture (brightness at
  least 8 = white); with `<` `>` (1 frame) and `<<` `>>` (10 frames) one looks for a frame that only shows the logo, and a slider blackens
  a band around the centre (title, names ...), shown as a translucent red band. OK stores the mask as a 1-bit PNG, base64 encoded, in the
  segment. When saving, the mask is written to a temporary file for ffmpeg's `removelogo` filter; in a batch script every mask is created
  before the ffmpeg call and removed afterwards. If the logo cannot be isolated in the mask (for the search with the logo), a note says so.
- The DeLogo rectangle is translucent red with a solid edge, and its corners resize two edges at once (diagonal double arrow).
- **DeLogo filter** (button in the middle of the main window, without Shift): a red rectangle appears over the preview, which is moved
  with the mouse (inside), resized (at the four edges) and placed on the station logo; it stays inside the preview. A second click asks
  "Do you want to activate the DeLogo filter?": Yes stores the rectangle as fractions of the preview (`x y width height`) in the mask
  column of the segment, No switches the filter off. The last rectangle is offered again for the next segment. When rendering, the
  fractions become pixels of the source picture and go to ffmpeg's `delogo` filter.
  Selecting another segment hides a rectangle that was being placed.

## 0.2

Second frozen state: English throughout, save as MP4/AVI with progress and cancel, batch scripts, dialogs with tabs, options in one place.

- All comments, docstrings, messages, tests and documentation are now in English (the generated user interface files were
  regenerated; their code is unchanged).
- The settings `batch`, `player`, `dialog_style`, `vlc_args` and `hide_messages` are options now: they are part of the `options=` string,
  appear in the options dialog (Batch / Technical tabs, with explanations) and are in `MediaMaker.example.ini`. Old keys of their own
  in `[settings]` move into `options=` when the program starts. A changed `dialog_style` applies at once; `player`, `vlc_args` and
  `hide_messages` act at the next start, which their explanations say.
- Fix: on a page of the options dialog with a single multi-line field (Batch: `path_map`) the row was shown in the middle; the rows of
  every page now sit at the top.
- The option `dialog_style=list` shows the pages of the options and Media info dialogs as a list on the left instead of tabs
  (`tabs` is the default).
- The batch script `MediaMaker.sh` is in `.gitignore` (it is a personal file next to the INI file), and the option `batch` sets another
  place, e.g. `batch=~/MediaMaker.sh`.
- The Media info dialog also uses tabs (one per section). Both tab dialogs are at least as wide as all their tabs side by side; the tab
  names are not elided and there are no scroll arrows.
- Every group of the options dialog has one line of explanation above its rows (`GROUP_TEXTS` in `profiles.py`). Options with values that
  would break the `key="value"` format (double quotes in `batch`, `path_map`, `vlc_args`, `hide_messages`, `aflags`) are refused.
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
