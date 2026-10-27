# Changes

## 0.5 (in progress)

- Version number set to 0.5-dev.
- **Cropping of one segment** (the crop button, VB6 `cmdCommand(5)` with `frmCrop`; modules `crop_dialog.py` and `cropping.py`): a small window with the four margins
  (top, bottom 0..400, left, right 0..250) as scroll bars and text boxes (a number typed into a box moves its scroll bar), R sets everything to zero,
  OK takes the values over, X cancels. While it is open the margins are shown as red bands over the preview, in proportion to the picture. The check box
  **16:9** sets left and right from top and bottom so that the picture that is left has the proportions 16:9 and keeps them when top or bottom change;
  unlike VB6 (`(top + bottom) * 8 \ 9`, right for square pixels) it takes the sample aspect ratio into account, so it is right for 720x576 shown as 16:9 as well
  (`(top + bottom) * 5/8`), and it never gives a negative margin. OK is refused when nothing would be left of the picture. A global cropping value (option
  `crop`) prevails over the individual one, so after OK the question from VB6 is asked whether to set the global value to zero.
- **Import** (File => Import, Ctrl+M; VB6 `mnuImport_Click`, `batch.parse_jobs`): reads the batch file (the script that File => Batch writes), lists all jobs in it
  ("Job1:<output file>", also the ones that are switched off), and a double click or OK brings the chosen one back: profile, options and the segment list with
  crop and the masks of the logo filters (the first frames are found again). Options of this computer (paths of programs, the batch file, player,
  dialogs, path map ...) stay as they are; names of options from older versions are converted. If the list is not empty, the program asks first and saves the
  state before as a session ("automatic backup before importing a job from the batch file"). Damaged jobs are marked and refused; messages when there is no
  batch file or no job in it.

## 0.4

Fourth frozen state: Dedup scene (removes a duplicate scene at a cut), Analyze cut point with the filters of Save As, sessions as zip files, Delete with
the additional files of a recording, the reference logo with its debug package, tools and help texts in the INI file, and many smaller things below.
Still to do: copy mode, DVD mode, chapters, and more tests with several audio and subtitle tracks.

- **Preview player taken back to the state before "slow medium" mode** (0.3 had it): there every jump reopened the medium with a new media player, which
  made the preview jump to the start of the film first and play it briefly, with sound, before it went to the wanted frame. Kept from 0.3 are the
  watchdog (nothing reported by VLC for 8 s after a medium was started: new media player) and the report of an unsuccessful logo search. Known and
  open: on a slow network drive a jump in the open VLC medium can take seconds, and `stop()` can block the window for that time.
- **Dedup scene**: the warning "Attention: this may take some time" is gone from the question; since only the middle line of the frames needed is read, in
  one call per segment, the search takes less than a second.
- **Restore session**: a double click on the wanted session is the same as OK (not in the dialog for deleting, where several sessions can be selected).
- **Overlap segments**: when it is done, the program now asks whether to check the cut with "Analyze cut point" at once (Yes starts it for the same two
  segments) instead of only naming the menu item in the text.
- **Media info**: the text of a tab no longer begins with the title of the tab again ("General", "Video #1", "Audio #1 (deu)"); the tab already says it.
  The MediaMaker tab keeps its first line "MediaMaker: values used for the frame numbers" (it is a description, not just the title). "Copy all"
  still has the names as headings, so that the copied text can be read.
- **Analyze cut point keeps the aspect ratio of the source**: `setsar=1` is only set when the two segments come from DIFFERENT files (it is needed for the
  concatenation then), like in Save As. Before, it was always set, which replaced the sample aspect ratio of the source by 1:1. The parameter
  `setsar_always` of `build_command` is gone.
- **Analyze cut point: new option `cutpoint_filters` (on|off, group Technical)**. With `on`, the new default, the clip is made with all the filters that
  Save As applies (cropping, scaling, DeLogo, RemoveLogo; the masks of RemoveLogo are written to a temporary folder for the run, as in Save As), without
  the note in the picture. With `off` as before (VB6): without cropping and logo filters, only scaled to the profile, with the note "cropping, delogo and
  resizing functions disabled".
- **Wait window** ("..., please wait..."): it has room for three lines from the start and wraps long lines. Before, the second line ("reading the
  pictures...", "frame 135: border 72 ...") was cut off because the window kept the height of the first text.
- **Edit => Dedup scene (Ctrl+F8)** (first "Overlap segments"), VB6 `mnuDeDup_Click` with `match()` and `far()` (new module `dedup.py`). The names and texts follow the
  changed VB6 form (`mnuDeDup`, "Dedup scene", "Duplicate scene removal failed: ..."); the generated user interface was made again from it (only the menu
  item changed). The option `overlap` is now `dedup` (like in the VB6 program): old INI files are taken over at the start (the value moves, the old help
  text goes; if both exist, `dedup` wins), the VB6 INI file with `dedup` is read as it is (`tests/sample_MediaMaker_dedup.ini`). If a recording repeats the end of one
  segment at the start of the next, marker B of the selected segment and marker A of the next one are moved towards each other, alternately (B back, A
  forward) up to `dedup` steps (option, default 400) until the picture at B equals the picture at A: the repeated part is cut in the middle and the cut
  is clean (verify with Analyze cut point). The pictures are compared by one line in the middle, from 20 % to 80 % of the width; equal if no R, G or B
  value differs by 24 or more (`far`, unchanged from VB6). Measured with a real example (two segments, 8.8 s repeated, MPEG-2 SD): 219 of the 222
  matching pairs pass the test, pairs one frame apart pass in only 2.5 %, and for 6156 starting positions of the markers the right pair was found
  every time (B 9.2 s -> 4.76 s, A 3.4 s -> 7.8 s); the seam of the cut is as smooth as the pictures around it (difference 2.98 against 2.91). The
  markers cannot run through their segments. Instead of one ffmpeg call per picture (VB6: `oneframe`), one call per segment fetches only the middle
  line of all frames needed (`frames.grab_scanlines`, the same values as the line of the whole frame): about 1 s for the example. The cut-in-the-middle
  is reported with the number of repeated frames and how far each marker moved. Not available for the last segment; different picture sizes are refused.
  The threshold of `far` (24) was tested against 13 other values on the same example: below 24 true pairs fail (at 20: no result for 7.6 % of the
  starting positions, at 16: for 24 %), from 36 on the search stops one frame too early (101 of 6156 starting positions at 36 and 40, 541 at 48, most at
  64); 24 to 33 are all right, so 24 stays.
- **Removed: the rewinding after a logo search** (VB6 `rewind()` with `diff()` and `average()`, option `logo_rewind`). It did not give satisfying results
  in the tests (with a wipe between commercial and movie it went back the whole 1.8 s). "Seek end of commercial" with the logo now returns the first frame
  WITH the logo, "Seek next commercial" the first frame WITHOUT it, and a search that finds nothing returns the end of the movie. In VB6 `rewind` was
  called at one place only (the end of `where_logo`), and `diff` and `average` only by `rewind`; in Python `logo.rewind`, `logo.bottom_line_average`
  and the constants are gone, `seek_logo` and the main window no longer have `avg_fn`. Old INI files lose `logo_rewind` from `options=` and its help text
  at the start. A new approach for finding the start of the movie can be built later (a good example is needed).
- **File => Delete (Ctrl+J)**: deletes the source files of all segments of the list from the disk, for good (no trash), and clears the list. The
  question names the files (the first 8, then "... and n more"); a file that several segments share counts and is deleted once; a missing file is no
  error. A file that cannot be deleted is reported with the reason, and its segments stay in the list (also in the saved one) for another try.
  With an empty list a message says so.
  **Additional files of a TV recording**: if there are any next to a recording (`X.eit`, `X.ts.ap`, `X.ts.cuts`, `X.ts.meta`, `X.ts.sc`: the files that begin with
  the whole name of the recording and a dot, and the name without extension plus `.eit`; a converted `X.mp4` is not meant), the question lists them and
  has a check box "Also delete the n additional files ...", NOT ticked at first (the default button is No). They go only with a recording that has been
  deleted (or was already gone); a recording that cannot be deleted keeps its files. See `sidecars.py`.
- **Clearing the list** (button, File => Close all) no longer needs a selected segment: it asks "Clear all segments from list?" and clears; with an
  empty list it says so instead of doing nothing. (The other buttons still need a selected segment.)
- **`[ToolTipText]` in the INI file has a help text for EVERY parameter**, options and profile parameters, also those added after the VB6 version. At the
  start the program adds the missing ones (texts that are there, also edited ones, stay) and removes those of dropped options (`focus` ...). A test
  makes sure that a new option cannot be forgotten.
- **Tools are options** (new group "Tools" in the options dialog): `avidemux` (path of Avidemux, e.g. the AppImage) and `vlc` (for Analyze cut point);
  empty: searched in the PATH. The section `[tools.linux]` (also `[tools]` and `[tools.windows]`) is not needed any more: at the start its `avidemux=` and
  `vlc=` move into `options=`, and a section without keys left is removed. `MediaMaker.example.ini` has no tool section and complete help texts.
- **Tried and dropped: automatic VLC shift** (commit 45a86a1, reverted). Finding: on the RTL recording on the NAS the VLC preview showed, for the same
  frame number, the picture 17 frames (0.68 s) later than ffmpeg does (see `preview_check.json` of the debug package, which stays). With the option
  `logo_rewind = 0` the search "Seek end of commercial" was precise to within a few frames; the preview offset is therefore only noted, not corrected.
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
