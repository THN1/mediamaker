# Changes

## 0.4 (in progress)

- Version number set to 0.4-dev.
- **Preview player taken back to the state before "slow medium" mode** (0.3 had it): there every jump reopened the medium with a new media player, which
  made the preview jump to the start of the film first and play it briefly, with sound, before it went to the wanted frame. Kept from 0.3 are the
  watchdog (nothing reported by VLC for 8 s after a medium was started: new media player) and the report of an unsuccessful logo search. Known and
  open: on a slow network drive a jump in the open VLC medium can take seconds, and `stop()` can block the window for that time.
- **VLC against ffmpeg: automatic shift per file** (option `vlc_sync`, `auto` or `off`). With a debug package of the RTL recording on the NAS the preview
  showed, for the same frame number, the picture 17 frames (0.68 s) later than ffmpeg does (`vlc_preview.png` against `frame_at_slider.png`: the preview
  picture is found in the recording at 50.40 s, ffmpeg's frame at 49.72 s): VLC and ffmpeg count the start of such a recording differently. All frame
  numbers of the program are ffmpeg's (thumbnails, searches, the cut itself), so what was picked in the preview was cut 0.68 s too early. Now the
  program compares the picture of the preview with the frames of ffmpeg around the same number (once the picture has stayed for half a second),
  takes the shift per file, applies it to every jump of the preview and to the slider during playback, and confirms it with a second
  measurement. Still pictures cannot be measured (8 tries, then the shift stays 0). `segment.json` of the debug package tells the shift.
- **Debug package: the piece of the recording is centred on the SLIDER** (= `frame_at_slider.png`, where the search stopped): 50 s before to 10 s after
  it, not around marker B. `clip_info.txt` tells where the slider, marker A and B and the place where the reference logo was created are inside the
  piece ("outside" if not).
- **Button L shows what it did**: after creating the reference logo a window shows the picture L took the logo from (the rectangle marked), the area of the
  logo enlarged and the edges that are searched for, so that a logo that is not in the picture is seen at once. The picture, the frame number and
  the preview picture of that moment are kept for the debug package: `reference_logo_frame.png`, `reference_logo_area.png`,
  `reference_logo_vlc_preview.png` and in `reference_logo.json` the frame and time of creation. (The files `frame_at_slider.png` and
  `logo_area_at_slider.png` show the slider position at the time the package is made, which can be another picture.)
- **Debug package: preview against ffmpeg**: `vlc_preview.png` is what the preview shows (taken from the program, no photo needed); `preview_check.json`
  (and `reference_logo_preview_check.json` for the moment of L) tell which frame number that picture really belongs to in ffmpeg's numbering
  (`best_offset_frames`; 0 = they agree), because VLC and ffmpeg can count the start of a recording differently.
- Option `logo_rewind = 0` now returns the first frame WITH logo (before: the last one without it); a search that finds no logo returns the end of
  the movie.
- **"Seek next commercial" / "Seek end of commercial" say which method they use**: the wait window begins with "Seeking with crop = 72" (crop > 0: black
  border) or "Seeking with reference logo" (crop = 0), so that a crop left over from an earlier session does not go unnoticed.
- **Deploy => Create debug package**: collects in the folder `debug/<time>` next to the INI file (and as a zip file of the same name, to be uploaded) what is
  needed to understand a wrong search or cut: the cut values of the selected segment (numbers as counted and as shown, times, neighbours), the DeLogo
  rectangle or the RemoveLogo mask, the reference logo (values and edge picture), what the last search did (method, crop, every frame it examined
  with its confidence or border value, result), options, versions, the list, the picture at the slider and the logo area in it, the end of the debug
  log, and an unchanged piece of the recording (`ffmpeg -c copy`) from 50 s before to 10 s after the slider with `clip_info.txt` telling where the
  markers are inside it. Things that fail (e.g. the piece) are noted and do not stop the rest. `debug/` is in `.gitignore`.
- Clearing the segment list (button, File => Close all), deleting the last segment and restoring a session also clear the VLC preview: it no longer
  keeps showing the film that was loaded last.
- `MediaMaker.example.ini`: the lines `batch=`, `player=` and `dialog_style=` (and the comments about `vlc_args`/`hide_messages`) are gone, these
  settings are part of `options=` since 0.3.
- **Sessions** (File => Backup session / Restore session / Delete session): a session is one zip file in the folder `sessions` next to the INI file
  (option `sessions_dir` for another place), named with the time as in VB6 (`2026.10.25_14-03-12.zip`), with the INI file, the segment list and a small
  manifest (time, optional note, number and titles of the segments, program version). No 7-Zip any more; nothing is rewritten when a session is
  added, deleting is deleting a file, a session can be copied or sent, any archive program opens it, a damaged file harms no other session.
  Backup asks for an optional note. Restore shows the sessions (newest first, with note and titles), lets you choose what to restore (segment list,
  settings, or both), saves the current state as a session first ("automatic backup before restoring ..."), checks the session (zip intact, the
  list is a MediaMaker list) before anything is written, and takes the files up in the running program: no restart as in VB6 (options for the
  player and VLC arguments apply at the next start). Delete accepts several sessions. Old 7-Zip archives of VB6 are not read.

## 0.3

Third frozen state: DeLogo and RemoveLogo filters, reference logo, Analyze cut point, first frame from the decoder, frozen-preview recovery on slow
network drives, dialogs and options in one place.

- **Frozen preview on a network drive** (log of a 2.5 GB recording on the NAS: opening a medium at a position took under a second, but every jump in
  the open medium 3 to 7 seconds, and `stop()` waited 4 seconds for such a jump, which blocked the whole window). Now a jump that brings no picture
  within 600 ms marks the medium as slow; from then on every jump opens the medium anew at the position, with a NEW media player instead of
  stopping the old one (which is stopped and released in a thread of its own). While such a reload runs, further jumps only keep the latest
  position, which is loaded as soon as the picture of the running one has arrived. `stop()` does not block for such media either. If VLC reports
  nothing for 8 s after a medium was started, the media player is replaced as well (watchdog). The log (`MEDIAMAKER_DEBUG=1`) now tells how many
  milliseconds a picture needed after a jump or reload, and `RECOVERY ...` / `slow medium: reloading at ...`.
- A search with the logo that finds nothing (no frame without the logo for "Seek next commercial", none with it for "Seek end of commercial")
  now says what it saw: the number of examined frames and their confidences, and what to check (rectangle, reference logo).
- The program sets its desktop file name; the harmless KDE messages "kf.jobwidgets: Cannot register a job with KUiServerV2JobTracker ..." and
  "... instance contains N stalled jobs" are filtered.
- New tool `tools/make_test_clips.py`: cuts short pieces (stream copy) out of a long recording from times, frame numbers or the saved list, so that
  they can be sent for testing.
- **Analyze cut point** (Ctrl+Y, as in VB6; not for the last segment): makes a clip of the last 3 seconds of the selected segment and the first 3
  seconds of the next one (without cropping and logo filters, scaled to the profile, with a note in the picture), plays it in VLC outside of the
  program and, after VLC is closed, offers to open it in Avidemux to look at the cut picture by picture. The programs are taken from the INI file
  (section `[tools.linux]`, keys `vlc` and `avidemux`, otherwise from the PATH; without VLC `xdg-open` is tried). If the text in the picture
  (drawtext) fails, the clip is made without it. The clip is saved as `mediamaker_cutpoint.mp4` in the temporary folder.
- **Save as MP4/AVI**: new option `file_dialog` (qt|native, default qt): Qt's own dialog, in which a double click on an existing file saves it (after
  the question whether to replace it) and the folders used recently are among its places. With `native` the dialog of the desktop is used (in some
  KDE setups a double click on an existing file did nothing there).
- **First frame**: it is now taken from the first picture that the decoder delivers (`decoded_first_pts`), not from the first keyframe packet; the
  decoder drops frames it cannot decode, and the thumbnails and the cut result contain exactly what it delivers. In addition, the first thumbnails of a
  file that was just opened confirm it: if the pictures begin later than assumed (up to 12 frames), the first frame, the length and the start of the
  segment are corrected and a note says so, so that the first picture lies right at the cut marker (before: ten crosses, then the picture
  was missing for a few frames at the marker, e.g. 13 crosses and 7 pictures). Saved lists are not touched. New tool
  `tools/first_frame_check.py FILE` shows the start times, packets, decoded frames and the pictures of the timeline loader.
- **Button L (reference logo)**: creates the reference logo for the search with the station logo from the DeLogo rectangle of the segment at the
  current frame (the logo must be visible there); with a RemoveLogo mask the reference comes from the mask. With it "Seek next commercial" /
  "Seek end of commercial" work when the recording has no black border (`crop = 0`). A reference counts as usable with more than 5 % edge pixels
  in the logo area (VB6: 10 %; the test logo had 9 % and was found reliably: confidence 0.93 to 1.0 with the logo and 0.00 without, whichever
  frame served as reference); the message shows the percentage. The reference is kept in memory only (as in VB6): after a restart press L again.
- Tried and dropped again: a smooth fill instead of `removelogo` (`logo_fill`, `fill_sigma`) and changes to the RemoveLogo mask (`mask_fill`,
  `mask_grow`, a grey preview). In a test on a real recording the smooth fill still left a grey area with cross-shaped traces, and it made
  ffmpeg slower (7.5 x instead of 12 to 14 x real time). The mask chosen in the dialog is used unchanged, as in VB6; the grey haze of
  `removelogo` can be avoided with the DeLogo filter (solid rectangle). The four options are removed from old INI files at the start.
- The tooltips of the RemoveLogo dialog are wrapped at 70 characters. The tooltip of the logo button follows the Shift key again ("...DeLogo..." / "...RemoveLogo..."): the key is asked for
  when the pointer enters or moves over the button and by a timer (every 100 ms) as long as the pointer stays on it, so pressing or releasing
  Shift also changes a tooltip that is already showing. No event filter on the whole application any more.
- The Batch dialog asks for the target file with a selection list of the (up to 10) folders used recently (INI key `recent_dirs`, also
  filled by Save as MP4/AVI), the file name and a "Browse..." button. The dialog is a class of its own and is deleted after use (a crash
  when closing the program after writing a batch script was reported: "QObject: shared QObject was deleted directly"; cause not yet known).
- The opacity of the red areas that mark the logo (DeLogo rectangle, band in the RemoveLogo dialog) is the new option `overlay_opacity`
  (percent, default 35; new tab "Logo" of the options dialog); a change applies to the rectangle at once.
- While Shift is held down, the tooltip of the logo button reads "Open/close RemoveLogo dialog" instead of "Open/close DeLogo dialog".
- RemoveLogo dialog: the width of the window stays, the height of the picture box (and of the window) follows the proportions of the
  picture **as a video player shows it**: the display aspect ratio of the stream (e.g. 16:9 for 720 x 576 pixels), otherwise the pixel
  proportions times the sample aspect ratio, otherwise the pixel proportions. The stored mask keeps the resolution of the video, as
  ffmpeg requires. A line of explanation below the buttons (and a tooltip) describes the slider.
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
