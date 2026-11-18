# Changes

## 1.0 (2026-11-18)

- Menu entries with a check mark (Copy mode, the profile in use in Load profile) show a small green tick without a check box, the same on every system (before: the check box of Qt's style, which looks different in different Qt versions). The tick is drawn by the program (menustyle.py, a thin layer over the style); MEDIAMAKER_PLAIN_MENU=1 switches it off.
- The dialogs of the profile and of the options match the main window when it is enlarged (UI_SCALE): they use the font of the main window, and the input fields and the room around the tabs are as much larger as the main window is (125 %: 1.25 times).
- Main window cut off at the right and at the bottom (seen with a new AppImage): at the start the window is now made at least as large as the scaled form (and cannot get smaller), also when the window manager brings back a smaller size.
- ffprobe/ffmpeg are not part of the AppImage (they come from the system). When ffprobe is missing, the message (one sentence per line) says how to install FFmpeg with the package manager of the distribution (openSUSE: zypper, with a note about the Packman repository for H.264/AAC; Debian/Ubuntu, Fedora, Arch), and the program offers to run the installation itself: after "Yes" the command runs with pkexec (the system asks for the administrator password), then the file is opened.
- AppImage on other distributions (openSUSE Leap 16.1: "ffprobe: libstdc++.so.6: version `GLIBCXX_3.4.32' not found"): the programs started by MediaMaker (ffprobe, ffmpeg, VLC) no longer get the library path of the bundle, and the AppImage no longer contains libstdc++ and libgcc_s of the build computer (the system's are used). The other libraries stay in the bundle (removing them all made the start fail: libgthread-2.0.so.0 missing).
- Crashes with VLC and Qt ("free(): invalid pointer" while saving or closing, "deallocating None" at the end of the program, Abort in the picture callback): the pictures of the preview are no longer passed from the VLC thread to Qt with a signal (Python object from a foreign thread); the VLC thread only stores the picture, the Qt thread fetches it with a timer (8 ms). The program also always ends at once (after saving and the atexit functions), not only in the AppImage.
- Thumbnails: with ffmpeg 4.4 (Ubuntu 22.04) the timeline had gaps (crosses) on long recordings: ffmpeg writes the time of a frame with 6 digits only, so from 10000 s on (about 2 h 47 min into the container time, e.g. recordings of a TV box) the frames got wrong numbers. The numbers now come from the exact counter.
- Debug log (MEDIAMAKER_DEBUG=1): when ffmpeg delivers fewer thumbnails than asked for, the log shows the ffmpeg command, the time stamps, the numbers and the messages of ffmpeg (to find why thumbnails are missing).
- AppImage: the program ends at once after saving and releasing everything (no clean-up of the libraries at the end); before, the console showed "free(): invalid pointer" and "Aborted (core dumped)" when it was closed.
- The dialogs in which one entry of a list is chosen (the target profile at the first start, the profile that fits the audio of a file) are 60 % as wide as before; the text wraps.
- ffmpeg older than 5.1 (e.g. 4.4 of Ubuntu 22.04): the options `-fps_mode passthrough` (thumbnails of the timeline, pictures of the cut point preview, frame reading) are replaced by `-vsync 0` (the same, the older name); the version of ffmpeg is asked once. Before, these functions failed with "Unrecognized option 'fps_mode'".
- Opening a video: if the profile in use expects an audio stream type (`acodec_in`) that the file does not have, the program explains it ("You are loading the file ... with the profile ..., which expects an audio stream of type ...") and offers the saved profiles that fit the types of the file in the same dialog: OK opens the file with the profile chosen, Cancel does not open it.
- Menu *Load profile*: the saved profile that is in use is ticked; if the profile in use was changed (or never saved) there is no tick.
- AppImage: libvlc and libvlccore are no longer put into the bundle (the copies found no VLC plug-ins: "unknown option --avcodec-hw"); the VLC of the system is used.
- Dialog *Information* (Ctrl+N): font and window size follow the scaling of the main window (125 %: font 1.25 times as big, window 1375 x 525 instead of 1100 x 420).
- Profile parameter `pad` is `on` / `off` now (was `True` / `False`), like the other on/off parameters. Old INI files are converted when the program starts (`profile=` and every entry of `[profiles]`); old jobs with `True` / `False` are still understood. The help text of `pad` was rewritten (an INI file that still has the old text gets the new one).
- No target profile yet (a new INI file, or one with empty or missing `profile=`): the program asks the user to choose one from the list (name and description; SD is preselected), at the start and, if none is chosen yet, when a video is opened. An INI file without any named profile gets the 11 example profiles (the same as in `MediaMaker.example.ini`) first; a new INI file has them from the start. Before, a new INI file had no profile at all and opening a video gave an error.
- **Public version 1.0** (the version number without "-dev"): the settings, the segment list, the sessions, the debug packages and the debug log are in `~/.config/MediaMaker` (`$XDG_CONFIG_HOME/MediaMaker`) instead of the program folder (a development version, "-dev", keeps them next to the program); the menu *Deploy* is hidden. `MEDIAMAKER_INI` still names the INI file in both. The version number is in the new file `version.py`.
- Debug package: Ctrl+Shift+F1 (no menu entry in the public version; the development version has *Deploy => Create debug package* as well). A warning comes first: the package holds private data (settings, paths, the segment list, pictures and a piece of the video).
- New: `LICENSE` (GPL-3), `install.sh` (installs for one user or with `--prefix`, `--uninstall` removes it), `packaging/` (icon, desktop entry, `appimage/build.sh` builds an AppImage), README sections "Installation", "Where your files are", "Bug reports and the debug package" and "License".
- Settings: `save()` makes the folder of the INI file if it does not exist.
- Test data: names of stations, films and the network drive replaced by neutral ones.
- README: new section "Keyboard shortcuts" lists all hotkeys of the menus (and F1, and the keys of the cut point dialog) in a table.
- README: new section "The buttons beside the list" explains the column of buttons (remove, up, down, duplicate, crop, DeLogo / RemoveLogo, L, clear the list).
- Estimate bitrate(s): when the dialog opens, the number in the first field (video) is selected and the field has the focus.
- New option `cutpoint_length` (group Technical, default 6, 2 to 120): length of the clip of *Analyze cut point* in seconds; it is made of the last half of the selected segment and the first half of the next one (6 = 3 + 3 seconds as before).
- The volume bar has the tooltip "Adjust audio volume".
- Analyze cut point: the picture area of the viewer (and with it the height of the dialog) has the display format of the SOURCE (DVD mode: the format from the IFO file; otherwise DAR/SAR of the file) changed by the crop that the clip has got (option cutpoint_filters = on: the global crop or the margins of the selected segment), so that the pictures are not distorted. With cutpoint_filters = off the crop does not count; with pad in the profile or without a known format the clip's own display aspect ratio is used. Before, the pixel proportions of the clip were taken, which distorted wide pictures stored as 720 x 576.
- Main window scaling: the form from the VB6 IDE is shown 125 % larger (fixed, no option): positions and sizes of all controls, the text (also the white value fields of the target profile), the symbols of the buttons and the preview area (VLC); the window is 1366 px wide instead of 1361: the 5 surplus pixels go into the gaps left and right of the column of buttons. The other dialogs are not scaled yet.
- Option `border_tol` is called `tolerance` now (INI files and job lines of older versions are converted).
- Menu: "Estimate audio kb/s" (Ctrl+I) is hidden, "Estimate bitrate(s)" (Ctrl+E) sets both rates. In the form the entry can be deleted.
- Estimate bitrate(s): "Estimate video kb/s" and "Estimate audio kb/s" are one dialog now (menu Ctrl+E): both rates, each in its own field; an empty field keeps the old value, an invalid value saves nothing. The second menu entry (mnuCalcAudio) still works and opens the same dialog until it is removed in the VB6 form.
- Seek next / end of commercial: after the search the preview keeps the LAST picture of the search. Before, VLC (still waiting at the old marker position, e.g. after Set marker A on a slow network drive) could draw a late picture of that position over it, so that the first picture of the segment appeared again. Now VLC stays blocked until it is brought to the slider position (slider moves, marker is set, Play).
- Frame counting: the result is remembered in the INI section `[known_files]` (key: file name without folder and file size in bytes, value: frames, frames that cannot be shown, time of the first keyframe). A file that was counted before is not counted again when it is opened (a file of 2 h on a network drive took about 100 s); a changed size means a new counting. New option `known_files` (group Technical): number of remembered files, default 200, the oldest are dropped, 0 = nothing is remembered.
- Seeking: the number (and time) of the picture that the preview shows during the search is now in the label lblInfo ("Frame 1234") and lblTime, as it was in VB6. The progress bar no longer repeats it and only says what was measured ("border 72 (looking for about 72)" or "logo confidence 0.31").
- Duplicate segment: a segment that is not cut at the end (marker B already at the end of the video) can be duplicated too. There is no search for the end of a commercial then; the segment is added again in full length directly behind the current one (before: message "There is nothing left behind the end of this segment").
- Counting frames in the background: the title now shows how far it is ("counting frames 37 %"), so that one sees whether it works or is stuck (counted from the first packet, because the times of a TV recording do not begin at 0; reported every 2000 packets); ffprobe runs with a low priority (`nice`), so that the preview, the timeline and the thumbnails are slowed down less when they start at the same time (a file of 2 h 21 min on a network drive can take minutes); start and end of every counting are in the debug log. The result is the same.
- Seek next / end of commercial: the preview no longer flickers between the first picture of the segment and the pictures of the search. While the search shows its pictures (option `search_pictures`) the player draws nothing of its own and the stills of ffmpeg are not shown; afterwards everything is as before (`Player.images_only`).
- DVD mode: the language codes of the sound tracks and subtitles are read from `VTS_nn_0.IFO` and put into the track dialog (stream ids 0x80+n / 0x20+n).
- DVD mode: the track dialog says where the languages come from ("Languages retrieved from VTS_02_0.IFO" or "No valid IFO file found ...").
- DVD mode: the drop-down list of the languages offers the codes of the IFO file first and then the usual ones (`deu (German)`, ...).
- *Analyze cut point* opens the clip in an internal viewer (in every mode): every picture one by one (buttons, arrow keys, slider) and playing with sound (new module `clipview.py`). The picture area has a fixed size (the dialog no longer grows when the video plays) and the display format of the video; in DVD mode (also the preview in the main window) the format comes from the IFO file, so a 4:3 DVD is shown as 4:3.
- DVD mode: no `-ss` any more (a cut far inside a title, e.g. *Analyze cut point* at 23:25, gave a clip without any stream with ffmpeg 9, because the times of the stream jump); the start is reached by counted time. Cutting deep into a title therefore reads the file from its start (it takes longer).
- README: DVD section rewritten, version in the heading.

## 0.8

Eighth frozen state: the **DVD mode**. A list whose segments all come from the VOB files of one title set (`VTS_nn_k.VOB`) is saved with the dialog for the tracks (by stream id), subtitles
cut like the picture, counted times that survive the jumps of a DVD stream, the parts of the title read as one stream where they follow each other (no loss at the seam), a progress bar that
follows the frames written. Also new: the menu Help (Readme, About with the commit), the commit in every job of a batch
file, and the track dialog with OK / Defaults / Cancel. Everything that is not a DVD is built exactly as in 0.7 (tested against 864e58d). Checked by the user on a real DVD (27:22: sound, picture
and subtitles in step, also behind the jumps at 11:50 and at the seam of the two VOB files at 23:25).

- Version number set to 0.8-dev.
- **DVD: subtitles behind a jump of the time stamps (found by the user, 14 Nov 2026).** In `VTS_02_1.VOB` the time of the stream jumps at picture 17777 (11:50 in the new
  file; the time starts again: a new cell). The sound and the picture are counted (since b076dfc) and stayed in step, but the subtitles come from a second input, the concat demuxer with a list
  (`subtitles.ffconcat`, since 2c3a089 of 30 Oct: trim filters cannot cut bitmap subtitles, so the list cuts them with `inpoint` / `outpoint`), and that demuxer does not correct jumps: the
  events behind it came with times BEFORE the earlier ones, ffmpeg wrote hundreds of "Non-monotonic DTS" lines and put every event at one time, so no subtitle
  appeared until the next file (23:45). `dvd.scan_of` / `dvd.pieces_of` read all packets of a file once with ffprobe (10 to 30 s per GB, kept per file, size and date), find the jumps
  (a step back of more than 1 s or forward of more than 10 s in video, audio or data) and cut the file at the sector before the first packet behind it; `build_command` puts every piece into the
  list as a file of its own (`subfile,,start,<byte>,end,<byte>,,:<path>`, with `-protocol_whitelist file,subfile,crypto,data`) with the length of its pictures. Only for DVD mode with subtitles, and
  only for a segment that reaches behind a jump: a segment without a jump gives the same list as before. Test `test_dvd_subtitle_jump` (with the user's piece `VTS_02_1_naht.vob`: bytes 9037824,
  picture 375, list with 15.000 s + 13.000 s, the subtitles of the file written come at 4.8 s, about 20 s and 26 s; ffmpeg 6.1 before: 4.8 s, then 94752 s).
- **DVD: the seam between two parts (the jump and the click at 23:45).** The user's seam pieces (the last 6 MB of `VTS_02_1.VOB`, the first 6 MB of `VTS_02_2.VOB`) show it: the second piece
  on its own gives 184 pictures, behind the first one 210; the first 26 pictures of a part (about one second) and its first AC3 block cannot be decoded without the part before (a DVD
  splits its stream at 1 GB in the middle of a group of pictures) and were thrown away with the numbering of "first_frame" (the user's own experiment with `concat:a|b` was right).
  `dvd.effective_segments` makes neighbouring segments that continue each other (part k to its end, part k+1 from its first picture, same size, mask, sound and a crop within 2 pixels)
  ONE segment whose path is `concat:part1|part2` (the bytes joined by ffmpeg); it is one input, cut by counted time like any segment. The numbers: a part contributes U + D pictures (U
  = `dvd.undecodable_head`, the packets before the first key frame and the leading B-frames, read from the first 400 packets only; D = total_frames - first_frame), so the run has
  more pictures than the sum of its segments, `runner.expected_frames` / `total_seconds` use the run. A cut (the second segment starts later, the first ends earlier), different parts of
  the title set or a path with `|` stay separate segments, as before. The list of subtitles takes the numbers of the PACKETS (`first = start - first_frame + U`) and the pieces of all parts of
  a run one after the other. Test `test_dvd_seam` (with the user's real seam pieces: 195 + 184 pictures on their own, 405 behind each other, the file has 405). Changed on purpose:
  the filter graph test (three parts in a row are ONE input now; parts 1 and 3 give two inputs and the concat filter) and the tolerance of the subtitle times of the queen test (0.1 s).
- **Fix: the subtitles began at once instead of after 17 s** (the user, 14 Nov): the question for the start time of the list of subtitles (`ffprobe -f concat`, also in the script as
  `SUBSTART=$(...)`) did not have `subfile` on its protocol whitelist, failed silently, answered 0 and `-itsoffset` was 0 instead of 16.8. Now it has the whitelist; test in
  `test_dvd_subtitle_jump`.

## 0.7

Seventh frozen state: **multitrack** (several audio tracks and subtitles in the new file, with language codes), the batch script in the home folder with "Run now?", the preview during a search
(the pictures that the search reads, no playing of the place in VLC at the end), the new segment is not played while the search after duplicating runs, searches that survive an unreadable end of a
recording and say when they found nothing, an improved logo detection (certain disturbances are tolerated and overlooked), larger symbols in the column of buttons, a README with the functions and the supported formats,
and a debug log with milliseconds. Still to do: DVD mode, and more tests with several audio and subtitle tracks. The logo that appears again INSIDE a commercial break is found as the end of the
break; this cannot be told apart by the logo alone.

- Version number was 0.7-dev.
- **The button Cancel and Ctrl+C work in every state of the window** (checked, not changed in the program): neither blocking level touches the button (`edit_controls` does not contain it; the cover of the
  jobs ends above the bar, `picProgress.y`), the shortcut is the button's own (a QPushButton shortcut, not a menu entry, so `block_ui` does not disable it), and no menu entry has Ctrl+C any more
  (the hidden `mnuCancel` has no shortcut: two entries with the same shortcut make Qt ignore both). New test `test_cancel_stays_usable`: both levels, a click while the cover is up, a click in the middle
  of a real search; its three counter-checks (button blocked, cover over the bar, a second Ctrl+C) fail. The Qt stand-in now emits `clicked` on `click()` of an enabled button, and the other tests press
  the button instead of calling the function behind it.
- **Decisions of the user (14 Nov 2026):** the track dialog stays as it is built, with OK / Defaults / Cancel in BOTH modes (answer A: the old "Cancel" of multitrack is the button Defaults now, so
  the two old checks "Cancel: the main audio track only, no subtitles" and "without subtitles an avi file is made" are replaced by the new meaning, which `test_multitrack*` and `test_containers`
  test); and the commit is shown in About and in EVERY job of a batch file whether or not DVD mode is used (tested for an ordinary job and for copy mode in `test_help_menu`).
- **Everything since 864e58d (apart from the Help menu, d7a3ff1) happens in DVD mode only; proof.** The user's rule: the tests made before the DVD work must stay valid for everything that is not a DVD.
  (1) The OLD tests (`tests/` of 864e58d: 77 parts and the small programs) were run against the new code: all green except three checks: "Cancel: the main audio track only, no subtitles" and
  "without subtitles an avi file is made" (the track dialog: Cancel now stops saving and the new button Defaults has the old meaning of Cancel; asked for by the user for both modes, see
  below) and "all menu entries are off except Exit, Information and Media info" (the two entries of the menu Help stay usable). (2) This showed what else was not DVD only and is now: the
  `-loglevel warning` (DVD saves only), the progress from the frames written
  (`run_ffmpeg(frame_progress=)` and `RenderWorker(frame_progress=)`: only for DVD saves; the old callers and the fake functions of the tests are not given the new argument), the recording of
  a save with its `ffprobe` call of the file written. The extra field `id` in the track list of `ffprobe` stays (the DVD parts are probed
  in more than one place, and without it the choice by id fails: tried); it changes no result. (3) `tests/test_nondvd_unchanged.py <videos> [commit]`: the ffmpeg commands (one file, several
  files and cuts, PNG and delogo masks, crop, mkv, avi, ts, chapters, path_map, VB6 times, multitrack with audio and subtitles into mkv and mp4, copy mode cut and join) and the batch scripts (also with
  subtitles) of 20 jobs are made with 864e58d and with the program as it is now: all 20 texts are identical; a control that changes `-sws_flags` on purpose is found in 18 of the 20 cases.
  The two changes that are not DVD only, both asked for by the user: the track dialog (OK / Defaults / Cancel, Cancel stops saving) and the comment `# Made by MediaMaker ...` of every job of a
  batch file (a comment: the import and the shell ignore it).
- **DVD: the subtitles came about 20 s too early; every job of a batch file says which commit made it.** Test of 87d8fe4 by the user: progress right, no "Frame count differs", `-reinit_filter 0` in
  the script, sound and picture together; but the subtitles 20 s early. The log of the earlier batch run said `Input #2, concat, from '...subtitles.tmp': start: 16.800000`: the input made of the
  list of subtitles starts at its first subtitle, and ffmpeg subtracts the START TIME OF EVERY INPUT from its times when there is no `-copyts` (DVD mode has none): 16.8 s too early. ffmpeg 6.1 says
  -0.08 s for the same list (it does not look at the first packet), which is why no test of mine saw it (and why the subtitles were 80 ms late there). `ffmpeg_cmd.subtitle_start` asks ffprobe
  (the same build as ffmpeg) for `format=start_time` of the list and the command gives it back with `-itsoffset <time>` in front of the input of the list (placeholder `SUBTITLE_START` in the command,
  filled in by `fill_subtitle_start` when the list has been written; in a batch script the script asks when it runs: `SUBSTART=$(ffprobe ...)`, `case ... N/A ... SUBSTART=0`, `-itsoffset "$SUBSTART"`).
  Only without `-copyts` (DVD mode); a TV recording has `-copyts` and nothing is subtracted. The subtitle times of queen.vob are now exact (2.12 s for 2.764 - 0.644, 80 ms better than before; the
  test accepts 60 ms). NOT checked with ffmpeg 9 (I have 6.1). Subtitles BEHIND a jump in the time of the file are still not looked at. **Batch file**: every job has the line
  `# Made by MediaMaker <version>, commit <hash> (<describe>), <date>: <title>[; LOCAL CHANGES ...]` after `# J=` (`batch.job_lines(made_by=)`, `Form.made_by()`); a script may hold jobs of several
  versions, and an old job keeps its old command (the user looked at one without `-reinit_filter 0`). The import ignores the line. The message "Changing video frame properties on the fly is not
  supported by all filters" (csp: smpte170m, incoming bt470bg) is what `-reinit_filter 0` is for: the colour tag changes, the size does not. Test: `test_dvd_subtitle_start` (it runs the script).
- **Fix confirmed by the user; the progress bar follows the frames.** The user ran the comparison: without `-reinit_filter 0` 17777 frames, `time=11:51`, `drop=17357`; with it all 35133 frames,
  `time=23:25`, nothing dropped (ffmpeg 8). The next save of 1113185 + the option showed no "Frame count differs" and took 2:09 instead of 1:23 (all 41030 frames). A batch command that the user
  inspected had the counted times but no `-reinit_filter 0`: an OLD script (the batch file is only rewritten by Batch); a new one has it before every input (checked). What stayed: the bar jumped from
  41 to 84 % and stayed there for a while. `-progress` reports `out_time` = the largest time of ALL streams, and the subtitles of a DVD (their times come from the file, wrong behind its jump) run
  ahead. `runner.progress_seconds`: the progress is frames written / frame rate of the output (`runner.output_fps`: `-r`), out_time only without it (stream copy); a block without a usable frame
  count gives nothing (before, "frame=N/A" or 0 fell back to out_time). Test: `test_progress_from_frames` with a real ffmpeg run whose subtitle input is shifted by 1000 s (with the rate: 0, 1, 1, 2 ...
  %; without it: 100 % at once). The subtitles themselves are still wrong behind the jump.
- **DVD: `-reinit_filter 0`; the track dialog has the button Defaults.** The user's batch log of 1113185 shows the next cause: "[fc#0] Reconfiguring filter graph because video parameters changed to
  yuv420p(tv, bt470bg), 720x576" at the very start of the run (VTS_02_1.VOB: colour space smpte170m, progressive; VTS_02_2.VOB: bt470bg, bottom first), followed by "Queue input is backward in time" and
  many "Non-monotonic DTS; previous: 7168, current: 512" of the sound (it starts from the beginning again after 7 blocks, 0.15 s). Newer ffmpeg builds the WHOLE filter graph anew when the colour space or
  the field order of the frames changes (ffmpeg 6.1 does not look at them, which is why no fixture of mine showed it), and every counter starts again: `setpts=N`, `trim`, the state of `concat`.
  So the counted times could not help. In DVD mode every segment input gets `-reinit_filter 0` (the graph is never rebuilt; the size stays 720x576 in a title set). NOT checked with ffmpeg 8; the
  user can compare in one minute: `ffmpeg -reinit_filter 0 -i VTS_02_1.VOB -filter_complex "[0:v]setpts=N*1/25/TB,trim=0:1405.36,setpts=PTS-STARTPTS[v]" -map "[v]" -r 25 -f null -` against the same
  without `-reinit_filter 0` (the line "Reconfiguring filter graph" and the frame count). The progress that jumped from 38 to 84 % is the time of the output running wild, probably the same fault. Seen
  in the log, not a cause: "Decode error rate 0.694444 exceeds maximum 0.666667" at the end of the run that the user stopped (ffmpeg had only decoded the broken start of the second file so far).
  The track dialog (suggestion of the user): OK, **Defaults** and Cancel for both modes. Cancel stops saving (before: with `multitrack` it meant "only the main audio track", now that is Defaults);
  Defaults = only the main audio track, no subtitles; in DVD mode the main sound track by its id (`run_dialog` returns the choice, `tracks_dialog.DEFAULTS` or None).
- **DVD: the times of the pictures and of the samples are COUNTED (`setpts=N*d/n/TB`, `asetpts=N/rate/TB`), because ffmpeg 8 no longer makes the time continuous in a filter graph.** The user's
  measurements on VTS_02_1.VOB (a jump in the time of the stream at packet 17778, byte 536473614, nearly the middle of the 1 GB file; the second half starts again at 0.085 s): (A) decoding alone
  35133 frames, `time=23:25`; (B) the chain of the program (trim, setpts, `-r 25`) 17777 frames, `drop=17357`; (C) the same without `-r` all 35133 frames but `time=11:34` (the time after the jump
  starts again). So the frames arrive, their times do not continue, and the frame rate conversion throws away every frame whose time is behind the last one: the whole second half. ffmpeg 6.1 corrects
  the jump in the filter graph too (all three right), which is why the fixtures made so far lost nothing. The count of the frames (35134) is right: the earlier idea that the file is only 15 minutes
  long was a wrong conclusion from the shortened output. `ffmpeg_cmd.build_command` puts `setpts=N*1/25/TB` in front of the picture chain and `asetpts=N/48000/TB` in front of every sound chain of a DVD
  structure (`regen`), so that the time is continuous whatever the stream says; the PICTURE span of a trimmed segment starts at (start - first_frame) frames, the sound span and the subtitle list keep
  the old values (the sound of a DVD part often starts before the picture, 0.48 s in a part of queen.vob; the subtitles were 0.2 to 0.5 s late until this was separated). Tested without relying
  on the version of ffmpeg: the command run with `-copyts` (a jump that ffmpeg does not correct) gives all frames with the counted times and 692 of 1016 (the second piece lost) without
  them. The real data of the user (`VTS_02_1_anfang.vob`: the beginning, `VTS_02_1_naht.vob`: the piece around the jump; joined to a file with the same jump to 0.085 s) are used by
  `test_dvd_mode` if both files are in the test folder. Also seen in them: the first three pictures of the file have a doubled time stamp (0.06 s), so the thumbnails of pictures 38 and 39 are missing
  (not solved); the subtitle tracks turn up only at 16.86 s. NOT solved: the subtitles AFTER the jump (their list uses the time of the file); the 1.6 s lead of the sound that the user measured is
  probably the same fault (to be seen with the next save).
- **DVD: Cancel says that it stops saving.** After the DVD test of the user (expected 41030, got 23244, the same as 23252 before, so the
  change to relative times did not help there): the segments are 35134 + 5896 frames; 23252 = 17356 + 5896, 17356 = 35134 - 17778 = the part of VTS_02_1.VOB AFTER the jump in its time (packet 17778:
  710.98 s -> 0.085 s), so it looks as if the part BEFORE the jump is missing, not the second segment; NOT reproduced here (a jump with B pictures from the real queen.vob loses nothing; with
  two pieces the first one survived in the absolute way). The sound of a 10 s piece of the user's output is 1.6 s ahead of the picture (cross correlation of the claps with the movement:
  0.41 at -1600 ms, 0.03 at 0). So the facts are kept now: `record_save` (the ffmpeg command, its messages, expected / written frames, the segments, the streams of the file written, and the last block of
  the progress with `drop_frames` and `dup_frames`) is kept; real saves run with `-loglevel warning` instead of `error` (the runner puts error first, the command's own flag is the
  last and counts), so that warnings such as "Non-monotonous DTS" are there. `RunResult.progress`. Also: the note in the track dialog says
  "DVD: Cancel stops saving, no file is written." in DVD mode (it said "only the main audio track, no subtitles", which is true only with the option multitrack): `run_dialog(dvd=)` /
  `ask_tracks(dvd=)` (was `show_ids`).
- **Menu Help (the last one): Readme and About, with the COMMIT.** The version number ("0.8-dev") does not say what a test ran with, the commit does. `buildinfo.commit_info()` reads it from git
  (`git log -1`, `describe --tags`, the branch, the tracked files with local changes; nothing is written: `GIT_OPTIONAL_LOCKS=0`; only if the program folder IS the top of the repository, a
  program inside another repository, e.g. a home folder under git, takes nothing from it); a delivered program without `.git` reads the file `COMMIT` next to it (line 1: the commit, 2: the date,
  3: the title; the build step writes it); otherwise "unknown" is said. `helpdialogs.py`: **Readme** (F1) shows `README.md` formatted (QTextBrowser, Markdown with headings, lists, tables, links
  opening in the browser); **About MediaMaker** shows the name, the version, framed and large the commit (short hash, `describe`, date, title, branch, "No local changes" or a warning with the
  changed files) and the versions of Python, PySide6, ffmpeg, ffprobe and libvlc, with the button "Copy information" (for a bug report) and the link to the repository. The commit is also in every job of a batch. Both entries are allowed while a file is saved (`ALLOWED_WHILE_SAVING`). Test: `test_help_menu` (a clone, local changes, untracked files, the
  file COMMIT, unknown, a folder inside another repository, Help is the last menu, the Readme text, no README.md, About and its copy button); the Qt stand-in has QTextBrowser now.
- **DVD mode cuts by relative times, no `-copyts`** (fix: "Frame count differs: expected 41030, got 23252" with the two files VTS_02_1.VOB and VTS_02_2.VOB of a DVD, picture and sound not quite
  together). The normal way cuts by ABSOLUTE times and needs `-copyts`; ffmpeg does NOT correct a jump in the time of the stream with `-copyts`, and a DVD has such jumps (a new cell, a new program
  chain: the time starts again somewhere in the file). Reproduced with a file of two pieces of 8 s each, the second starting its time again: cut by absolute times 202 of 400 frames (the
  frames after the jump are outside the window), without `-copyts` all 400; the same size of error as on the DVD: 23252 frames are about one 1 GB part at 9.2 Mbit/s, so the whole second segment was
  lost. `ffmpeg_cmd.build_command` takes the relative way for a DVD structure (`relative`; `-ss` and trim as in VB6, `split_seek`), the list for the subtitles then holds the times in the file (start
  of the file + the jump of -ss, `shift`). Measured at the place where the two pieces meet: the picture turns red at 8.00 s, the tone changes at 7.99 s (13 ms). The hidden 6.5 s before the start in
  the user's test2.mp4 (negative time stamps, hidden by an edit list in the mp4: 915 frames in 30 s) look like the same jump; not checked with the user's files. Tests: `test_dvd_mode` (the jump file
  `make_jump_vob`, all 400 frames, no -copyts, picture and sound meet; the subtitle times of `queen.vob`); both fail without the change. NOT solved: the subtitles AFTER a jump in the same file
  (the list uses the time as the file gives it, the demuxer cannot know the corrected one); and every other source with jumps (a TV recording) still loses frames, "Frame count differs" tells.
- **DVD mode** (`dvd.py`; VB6: `DVDMode()` and the form `frmStreams`, which the multitrack dialog replaces). All segments are VOB files `VTS_nn_k.VOB` (k >= 1) of one title set of one folder:
  (1) saving (`save_video` and the batch file) opens the dialog for the tracks whenever there is anything to choose, whether `multitrack` is on or not; Cancel stops saving (as in VB6: streams =
  "Cancel"); (2) the streams of ALL parts that are used are read with ffprobe (`dvd.PROBE_ARGS`: the first 100 MB) and joined (`tracks.merge`), because a subtitle track may turn up only in a later
  part; the dialog shows the stream id of every track; (3) the choice is kept by STREAM ID (`audio_tracks = "0x81:eng,0x80:deu"`, `tracks.to_ids` / `to_indexes`), because every part of a DVD is analysed
  on its own and its streams are numbered in the order of their first packets: measured, the same sound track was `a:0` in two parts and `a:1` in the third (a choice by position took the wrong one; by
  id the result was identical to a hand-made reference); (4) the filter graph takes the sound tracks as `[n:i:0x81]` and joins them with the concat filter, the list for the subtitles declares the
  streams (`stream` / `exact_stream_id`, `ffmpeg_cmd.subtitle_list_text(entries, stream_ids)`), so that the concat demuxer takes the stream with THIS id from every file; (5) DVD mode has precedence over
  copy mode (`copy_mode_used`), with a note. New: `Track.stream_id`, `mediaprobe.track_list(probe_args=)`, `tracks.key_of / find / audio_spec / merge / to_ids / to_indexes`, `fits(lenient_subtitles)`
  (a subtitle track by id may be missing in a part). Tests: `test_dvd_mode` (units; a DVD made for the test with two tones, in part 3 the sound tracks in the other order; Cancel; copy mode; batch;
  tests the real DVD piece `queen.vob` from the test folder if it is there: three of its five subtitle tracks arrive in mkv with the six pictures of THEIR source ids, compared by size; fails when the
  choice is made by position). Not done: the language codes (the IFO files have them). Known: ffmpeg loses the last event of a DVD subtitle track in an mp4 file (also when it is run alone), mkv keeps all.
- **While a file is saved the segments cannot be changed.** The save did not block anything (only Save, Save as AVI and Batch were off), so the middle buttons could move or remove segments or clear
  the whole list during the run. `begin_action(..., block="edit")` (the save) now switches off what changes the segments or markers (`edit_controls`: all middle buttons, set marker A and B, reset
  the markers, the timeline) and every menu entry except Exit, Information and Media info (`ALLOWED_WHILE_SAVING`); looking at the pictures (slider, the buttons that move through the film and go to
  the markers, play) stays possible, there is no cover. Files dropped on the list are refused (`edit_blocked`) while saving and during a job. `render_finished` ends the action first and enables Save,
  Save as AVI and Batch afterwards (otherwise the states from before the save would have been restored over them). `block=True` / `"all"` is the cover of the jobs as before. Test: the real save
  (`test_save_video`) checks it at every progress message and fails without it; `test_actions_in_bar` checks the levels, the refusal of a job and of dropped files.
- **"Don't ask again" in the question "Open cut point video clip with AVIDEMUX now?"** (`dialogs.ask3_with_checkbox`, `ask3_remember`): the check box is not ticked at first; ticked, a Yes or No is
  saved in the option `cutpoint_avidemux` (yes / no) and the question does not come again; Cancel is not an answer and saves nothing; not ticked, the option stays ask. The check box has a tooltip
  that says where the answer is kept (Options, page Tools); the help text of the option mentions it too (the two earlier help texts in an INI file are replaced).
- **New option `cutpoint_avidemux` (yes, no, ask; default ask), group Tools.** First tooltip: "Run avidemux to analyze cutpoint" (the one asked for), then a longer one that says what yes, no and ask do; an INI file that has the short text gets the new one (`OUTDATED_TOOLTIPS`). After the clip of Edit => Analyze cut point has been seen in VLC,
  yes starts Avidemux at once, no never, ask asks "Open cut point video clip with AVIDEMUX now?" as before (`cutpoint_played`). It is a setting of this computer, like `avidemux` and `vlc`
  (`LOCAL_OPTIONS`); the test of the cut point runs all three values (and fails when the option is ignored).
- **The blue wait window is gone: every job shows its progress in the bar and is cancelled with the red button.** Searches (border and logo), auto crop, dedup scene, the clip around a cut
  (Analyze cut point) ran in the modal wait window (`dialogs.WaitDialog`, removed together with `wait_dialog` and its test). Now `_run_job` uses the same functions as
  the save: `begin_action(message, cancel, block)` (one action at a time: a second one is refused with "Another action is still running ...", also a job while a save runs), `action_note`
  (the text: "<name>...  <what it does>", one line in the bar), `action_fraction` (the percentage; the bar only moves forward), `end_action`. The button Cancel calls the `cancel` of the action
  (`cmdCancelButton_Click`), so it reaches all of them; Ctrl+C too. The jobs block the window, as the modal window did: `block_ui` puts a transparent cover over everything above the bar (mouse
  and keys) and disables the menu entries (and so their shortcuts), the old states are restored when the job ends, before its result is shown; the save does not block (as before).
  The percentages (`SeekWorker.fraction`, `control.fraction(x)`): the searches the furthest frame looked at between the start and the end of the movie (at most 97 %); auto crop 50 % while
  it reads the picture; dedup reading the two ranges of pictures (0 to 20 %), then the comparison with its step (20 to 100 %); the clip around a cut the masks (5 %), then ffmpeg's own
  percentage (5 to 100 %). Tests: `test_actions_in_bar` (progress, cover, entries off and restored,
  cancel by the button after the 3rd probe, a failing job, a second action refused, save and job exclude each other; fails without the blocking or without the refusal) and the checks in
  the tests of the cut point and dedup; the old tests watch the bar through `watch_actions` instead of the window.
- **The button "Cancel current action" replaces the menu entry "Cancel save".** `picProgress` is narrower by its own height (17 px = 255 twips: 1072 instead of 1089) and the button
  `cmdCancelButton` (17 x 17 px, the red cross of "Remove selected segment" made smaller: `icons/cancel.png`, 16 x 16; for the VB6 form also `icons/cancel.ico` and `cancel.bmp`, VB6 cannot read
  PNG) sits at its right end, tooltip "Cancel current action". It cancels what shows its progress in the bar (at first only the save; now every job, see the entry above). The shortcut Ctrl+C belongs to the button now (`CANCEL_SHORTCUT`); the button can be pressed only while a save runs (`set_cancel_enabled`); the
  menu entry `mnuCancel` is hidden, disabled and without a shortcut, its handler name `mnuCancel_Click` still works. The window makes the button itself when the form has none
  (`setup_cancel_button`, as it did with Save as and Dedup scene); a form with `cmdCancelButton` (and a narrower `picProgress`) is used as it is, and a form without `mnuCancel` works too.
  For the VB6 form: `picProgress` Width - 255 twips; a CommandButton `cmdCancelButton` with Left = old Left + new Width, Top = Top of `picProgress`, Width = Height = 255, Style = 1 (Graphical),
  Picture = `icons/cancel.ico`, ToolTipText = "Cancel current action"; delete the menu entry `mnuCancel`.
- **Fix: the button "Cancel current action" was invisible.** The window sets itself up when it is shown (`Form_Load` from `showEvent`), so the button was made AFTER the window was visible, and
  a child widget that is added to a visible window stays hidden until `show()` is called: the bar was narrower, the button not there. `setup_cancel_button` calls `show()` and `raise_()` now; the
  test checks it and fails without. While nothing is running the button is disabled, so its cross is shown greyed (as every disabled button does).
- **README: the beginning no longer speaks of TV recordings only.** MediaMaker cuts, unifies and joins videos of many formats and sizes (films, parts of films, clips, TV recordings); the tools
  for commercials, borders and the station logo are named as the special tools for TV recordings. A new line says that material of different size, frame rate and sound is made uniform by the profile.
  Also repaired: the words "Dedup scene" had got lost from the description of the search.
- **Options dialog: "Show advanced options".** The page Logo has the check box "Show advanced options" under `overlay_opacity` (`profiles.ADVANCED_OPTIONS`, `dialogs.edit_pairs(advanced=...)`). It is
  OFF every time the dialog opens; ticked, the rows `logo_conf` and `logo_extra` appear below it and can be changed (hidden, they cannot be edited and their values come back unchanged). If one of
  them is wrong when OK is pressed, the dialog opens again with the check box on (`dialogs.error_in_advanced`). The two values were hidden before (only in the INI file), so that a user did not
  find the new `logo_extra`; `logo_edge` and `cut_diff` stay hidden.
- **Logo detection: a busy picture no longer counts as the logo** (`logo.logo_confidence`, new option `logo_extra`, default 1.0; it and `logo_conf` are on the page Logo of the options dialog
  under "Show advanced options"). A user's recording (60 s of
  a commercial break of an RTL recording, reference logo made with the button L) showed why the search for the end of the commercial stopped too early: it got confused by patterns similar to the searched-for logo. The confidence was only the
  share of the reference edges that is found in the logo rectangle (73 x 36 pixels); a picture with many vertical edges (fine stripes, textures) has so many that about half of the reference edges are hit by chance (0.47 to 0.72; the
  minimum `logo_conf` is 0.2). My recalculation of the package gave exactly the 28 values that the search had logged. In the 1504 frames of the clip 92 frames, in four runs, counted as
  'logo present'. Now the confidence is that share MINUS `logo_extra` times the density of the edges that are not in the reference (`found - extra * others`, at least 0): with the weight 1.0
  no frame of the clip reaches more than 0.118 (before 0.721, 0 frames above 0.2 instead of 92). With the logo inserted into the same frames (reference picture, three kinds of insertion): at least
  0.53 with the whole logo box opaque, 0.40 with only the tiles opaque, 0.28 with the tiles at 80 % opacity; only at 65 % opacity and a very busy background single frames fall below 0.2 (the search
  only has to meet the logo in some frame of the movie). Weights below 0.75 leave such pictures above the minimum, 1.25 and more cost recognition of a transparent logo; `logo_extra = 0` is the old
  behaviour. Test data: `tests/data/logo_false_positives.npz` (the edge maps of 327 frames, no pictures) and the test `test_logo_busy_pictures`, which fails with the weight 0.
  NOT solved by this: the logo that appears again INSIDE the commercial break (the user's frame 86875); a logo alone cannot tell it from the end of the break.
- **A search no longer fails when the end of the recording cannot be read, and says when it found nothing.** A search for the end of a commercial with `crop = 73` ran through the whole rest of a
  recording (no border of 73 in it), and the very last frame (162022 = `total_frames`) could not be read (the recording is damaged at its end: "Invalid frame dimensions 0x0", "ac-tex damaged"):
  "Seeking with crop = 73 failed: Frame 162022 could not be read". `grab_frame` raises `frames.FrameUnreadable` (a RuntimeError) now; `seek_border` and `seek_logo` take an unreadable frame in
  the last 10 seconds of the recording (`_tail_frames`) as the end of the data (`SeekEndReached`): the search stops, the result is the last frame that could be read (`stats["found"] = False`,
  `end_reason = "unreadable"`); an unreadable frame elsewhere is still an error. A search that found nothing (also when everything could be read: the border/logo never matched) says so after
  the slider has been set: `border_seek_report` ("No end of the commercial was found ..."; the logo search had its own `logo_seek_report`, which now also says that the end could not be read).
  Before, the border search ended at the last frame as if it had found something there. The condition of a hit is one function now (`border.border_hit`, `logo.logo_hit`). Also: the record of a
  search (`last_search.json`) has `found`, `end_reason` and, for the logo search, `reference_logo` (the rectangle, whether it was made with the button L, at which frame,
  how many edge pixels): which reference a search used. NOTE: with the option `crop` above 0 the search always uses the black border; the reference logo is used only with `crop = 0`.
- **The search ends without playing the place in VLC.** The last picture of the search STAYS on screen (it is the picture of the result: `border_at` / `confidence_at` read the frame that is
  found last); the slider, the frame info and `last_frame` are set, but VLC is not sent there (`seek_done`: `_vlc_stale`, `_slider_sync_off`). VLC is brought to the slider position (`show_at`)
  only when the slider is moved again (`Slider1_Change`), when a marker is set (`cmdPos_Click` 7/8 -> `display_frame`) or when Play is pressed: then `Player.play_at(ms)` starts at the slider
  position, also for a medium that was only loaded and never started (the new segment after duplicating; media option start-time, no pause afterwards), or jumps and plays if it is started.
  If the result is not the frame of the last picture (a cut was snapped to, `cut_window`), its own picture is read by ffmpeg. Without pictures (option `search_pictures` off, the embed
  player, a search function without `on_image`) it is as before: VLC jumps to the result.
- **The preview shows pictures while a search runs** (option `search_pictures`, on|off, default on, group Seeking; memory player only). The preview shows the picture of EVERY probe, down to the
  step width 1 (`seek.PICTURE_MIN_STEP = 1`; the step width goes 1000 -> 100 -> 10 -> 1; first built for step widths from 10 on, then opened up because the pictures cost nothing), like a film that
  runs by; at the end VLC jumps to the result as before. The
  pictures are the ones that the search reads anyway: `border_at` and `confidence_at` read the whole frame with `grab_frame` and hand it over (`on_image`), `where_border` / `where_logo`
  report the step width of each probe (`probe`), `SeekWorker.picture` passes it to the main window (`search_picture`). **Measured** with `test_3.ts` (1280x720 h264, local disk, 11 steps, 8 of
  them with step width >= 10, two runs each): without pictures 8.96 s; handing over the picture that was read **9.05 s (+1 %)**; an additional ffmpeg call per picture, in parallel
  15.68 s (+75 %), one after the other 15.90 s (+77 %). So the second read would nearly have doubled the search; reusing the picture costs nothing measurable (on a network drive a second read
  would also read the file twice). Not tried on the NAS. The single picture of marker A that was shown for a short time while the preview was held (duplicate_segment) is out again: the
  search pictures take its place; until the first probe the preview stays black.
- **Duplicate segment: VLC does not show the new segment during the search, but at the end of it.** Debug logs of the user showed that VLC was sent to the new segment twice before the search
  (`show_at` for marker A of the new segment, then at once for the place after the pause) and played it for a moment (picture and sound), while the search for the end of the commercial ran.
  `duplicate_segment` now HOLDS the preview (`_preview_held`): the slider and `display_frame` do not touch VLC until the search is over; the list, the slider and the timeline (marker A) are
  set up as before. The search shows its result as before (`seek_done`); if it fails, is cancelled (only `finished` is emitted then) or is not started at all, the picture at the slider position
  is shown (`release_preview`, `worker_finished`). Before this, three other attempts were made and taken out again because they changed nothing for the user: a wait until the preview was quiet
  (`after_preview_settled`, `Player.settled`, `picture_idle_ms`; commits 6bfabd0, f8d2b61, 0ce2ae6, a7e8cc5) and the muting of the sound while a job runs (`hold_mute`; commit 160fb37). The
  logging of ce92d0c stays. Note: the search itself only reports text to the wait window; it does not move the slider or the preview.
- **More in the debug log** (`MEDIAMAKER_DEBUG=1`, file `mediamaker_debug.log` in the program folder): the time has milliseconds now (`log_line`), and the steps of the preview are logged:
  `display frame` (picture from ffmpeg or `show_at`), `show_at` (also the way without flags: "the medium is started already"), "VLC plays: pausing", "position ... reached", "duplicate: ...
  starting the search" and "search started", each with `Player.describe()` (state, playing, time, flags of VLC). The description is only made
  when the log is on (`debug_log` takes a function for the text).
- **README.md rewritten** (it is the text that GitHub shows under the files): what the program does (cutting, picture, tracks and chapters, saving and automation), the supported input and
  output formats (with what each output type can hold), requirements, start, options, tests.
- **Help text of `batch`**: the old default text ("... empty: next to the INI file, with the extension .sh ...") in an INI file is replaced by the current one (`settings.OUTDATED_TOOLTIPS`;
  a text that was edited stays).
- **Batch: the script goes to the home folder, and Run now?** Without the option `batch` the script is `~/MediaMaker.sh` (the name of the INI file; before: next to the INI file); an option that
  is set keeps its place. The dialog at the end ("Batch file was updated ...") ends with **Run now?**: Yes runs the script in a window of its own, a terminal program (`external.terminal_command`:
  konsole, gnome-terminal, xfce4-terminal, mate-terminal, lxterminal, kitty, alacritty or xterm, the first one that is installed) that stays open until Enter is pressed so that the result can be read.
  New option `terminal` (group Tools): a command of your own (e.g. `konsole --separate -e`; the script is appended). No terminal program or one that cannot be started: it is told, with the command
  to run the script by hand. The test environment sets HOME to the folder of the window, so no test writes to the real home folder.
- **Help text of `multitrack`** begins with "When set to on, ...". An INI file that still has the first default text gets the new one (`settings.OUTDATED_TOOLTIPS`); a text that was edited stays.
- **Multitrack: several audio tracks and subtitles in the new file** (option `multitrack`, on|off, default off, group Audio/Subtitles; replaces the options `multilanguage` and
  `subtitle`, which are removed: an old INI file or job with `multilanguage=True` or a `subtitle` other than 0 gets `multitrack=on`). With the option on, a dialog with two tabs
  (Audio, Subtitles; `tracks_dialog.py`) opens after the name of the file has been chosen (Save as and Batch), but only if the source has more than one audio track or any
  subtitle track. For every position it offers the tracks of the source file ("-" = unused) and a language code (a drop-down list with the codes of the source file; a typed code
  is checked against ISO 639-2, `languages.py`; T and B codes are accepted, `ger` becomes `deu`; OK is impossible while a code is wrong, a track is chosen twice or the file type cannot
  hold a subtitle). Teletext tracks are ignored and not counted in the numbers of the dialog (but in the index of ffmpeg). Cancel: only the main audio track, no subtitles.
  * The choice (`tracks.Choice`) is part of the OPTIONS OF THE JOB (`audio_tracks=1:fra,0:deu`, `subtitle_tracks=2:fra`, index of ffmpeg and code), not of the settings: the batch file
    carries it, a session keeps it, the import restores it; the INI file never holds it. The dialog starts with the last choice if it fits the file.
  * **Normal mode**: every chosen audio track is cut and joined like the first one (`concat` with `a=K`), with `-metadata:s:a:N language=xxx` (an AVI file has no field for it:
    `title=`). **Subtitles** cannot go through the concat filter, so they come from a second input, the concat DEMUXER with a list (`inpoint`, `outpoint`, `duration` from the same times
    as the trim of the picture; with `-copyts` the events then meet the picture exactly; measured with a TV recording). The list is a file in the working folder (the batch file writes
    and removes `<target>.subtitles.tmp`). One command, no second run.
  * **Copy mode**: `-map` of the chosen tracks, the languages, the conversion of the subtitles.
  * **What becomes of a subtitle** (`containers.subtitle_plan`): MKV copies; MP4 converts text with `mov_text` and bitmaps (DVB) with `-c:s dvdsub` into dvd_subtitle (MP4 holds it; the
    first version of the table said "text only"); TS keeps DVB; AVI cannot hold subtitles (error before saving).
  * **`-canvas_size`**: a bitmap subtitle that is converted gets the size of the picture of the SOURCE film (an input option, before the input). Measured: without it the new track has no size;
    with the size of the source (1280x720) it has, also when the film is rescaled (the players scale it); with the NEW smaller size ffmpeg fails ("canvas_size ... is too small for render").
    Not handled: cropping moves the picture, the positions of bitmap subtitles refer to the whole source picture.
  * All files of a list must have the tracks of the choice (the choice is made for the first file); otherwise it is told before anything starts.
- **Larger symbols in the column of buttons** (remove, move, ..., crop, DeLogo, clear): 22 x 22 px (`frmMain.COMMAND_ICON_SIZE`). Qt took its default of about 16 px, VB6 drew the symbols
  nearly as large as the 25 x 25 px buttons. The pictures of the form (32 and 24 px) are scaled; the size is set when the window is built, the generated user interface is unchanged.

## 0.6

Sixth frozen state: one dialog "Save as" for mp4, mkv, avi and ts with the check of what each type can hold, copy mode in the batch file, in the import, in sessions and remembered for the
next start (with a warning that can be switched off), pictures of the stopped film from ffmpeg (option `paused_preview`), the red line of the timeline behind the pictures, Reuse source A/V
for the selected segment, Dedup scene on Ctrl+V, English shortcuts in the menus, a faster start with mp4 lists, and the smaller things below.
Still to do: DVD mode, multilanguage, and more tests with several audio and subtitle tracks.

- **Timeline: the red line is behind the pictures**. `timeline.draw_strip` painted it once more over the thumbnails (and over the grey placeholders); the form has the red control
  `Line1`, which lies behind the timeline like a line of VB6, so it now shows in the gap between the two pictures of the cut and above and below the strip, as it does when the
  timeline is empty.
- **Reuse source A/V (Edit)** works with any number of segments in the list (VB6 and the first versions wanted exactly one): the values of the target profile (size, frame rate, bit
  rates, sample rate) are taken from the segment that is SELECTED in the list. Messages: "There are no segments in the list." and, if none is selected, "Select the segment in the list
  whose settings are to be taken over."
- **Shortcuts**: Dedup scene is **Ctrl+V** now (was Ctrl+F8); Ctrl+V became free when "Save as AVI" went (the hidden entry has no shortcut any more, so it is not used twice). The menus
  are English, but Qt writes the names of the keys in the language of the system ("Strg+S" on a German one): the text of the shortcut is written into the entry by hand ("Save as...<tab>Ctrl+S";
  Qt adds its own only if the text has no tab; `vbqt.english_shortcuts`), so the menus show "Ctrl". Done when the window is built, the generated user interface is unchanged: for the
  VB6 form set the shortcut of `mnuDeDup` to Ctrl+V and take it away from `mnuSaveAVI` if you want it there too. A test checks that no shortcut is used twice.
- **Fix: the program did not start** after the previous change ("RuntimeError: libshiboken: '__init__' method of object's base class (frmMain) not called."). The object for the
  pictures of ffmpeg was made in the constructor of the main window BEFORE the base class was initialised, with the window as its parent, which Qt does not allow. It is made
  right after the base class now. The replacement for Qt in the tests did not check this; it raises the same error now when an object whose base class is not initialised is given as a
  parent or argument (the old code fails with it, the new one runs).
- **Preview while the film is stopped: pictures from ffmpeg (option `paused_preview`, vlc|ffmpeg, default vlc, group Technical, applies at once; `player = memory` only)**. With VLC the
  preview followed the slider only about ten times in the stopped state and then got stuck (while the film runs it does not). With `ffmpeg` every picture of the stopped film is read
  by ffmpeg (`stills.py`, one process at a time; newer requests replace each other while one is read, so the picture follows the slider with a short delay and the last one counts) and
  put into the preview (`Player.show_image`); VLC is not asked at all. Pressing Play tells VLC the position of the picture first (`leave_still`), then it plays; while the film runs
  the slider makes VLC jump as before. The first picture of a film (it is not started yet) still comes from VLC. The pictures have the frame numbers of the thumbnails and the cut (VLC
  was seen to show a picture 17 frames later). Not tried with a real libvlc here (there is none): the logic is tested with the replacement player and a real ffmpeg picture.
- **Save as: ONE dialog for all file types** (`containers.py`). "Save as MP4" and "Save as AVI" are one entry "Save as..." (the form still has the two; at the start the first one is
  renamed and the second hidden, so the VB6 form can be changed later: an entry `mnuSaveAs` in the form is used as it is, `mnuSaveAs_Click` exists). The dialog offers mp4, mkv, avi and ts
  (and All files), the type chosen last in this run at the top. The extension of the name decides the file type; without one, or with something that is no file type of the program (the dot
  in "Dr. No"), the type selected in the dialog (or at the top) is added. Before, ".avi" typed in the MP4 dialog became "x.avi.mp4".
  * **What each type can hold is checked before anything is made** (`containers.check`), measured with ffmpeg 6.1.1: all the usual codecs (h264, mpeg2video, mpeg4, hevc with aac, mp2,
    mp3, ac3, pcm) are accepted by all four containers, so codecs are NOT checked. What differs: chapters (mp4 and mkv; avi and ts leave them out without a word), subtitles (mkv copies
    every kind; mp4 only text subtitles, with `-c:s mov_text` - a plain copy is an ffmpeg error, bitmap subtitles cannot be converted; avi: error "Not yet implemented in FFmpeg"; ts holds the
    DVB ones of a recording, a text subtitle becomes "private data" that no player knows), `-movflags` (mp4 only, not used by the program).
  * **Chapters in a file type that cannot hold them**: the question "A .avi file cannot hold chapters: they are left out ... Save anyway?" comes BEFORE saving (the note afterwards is gone).
  * **Subtitles in copy mode** (option `subtitle`): the codecs of the tracks are read (`mediaprobe.subtitle_codecs`); a type that cannot hold them, a bitmap subtitle for mp4 or a track
    that is not there is an error told before anything starts. `-c:s` comes from the container (`containers.subtitle_codec`).
  * File => Batch makes the same check (the extension ts is allowed there too, a name without a type gets the type of the last Save as).
- **No beep of our own after saving**: two melodies were heard at "Play now?" (the explicit beep and the sound that the window of the question makes by itself).
- **Faster start with lists whose first frame is 0** (an mp4 file): the start read every segment of such a list again, for every start (ffprobe, about 1.3 s per segment on a local disk, much more
  on a network drive; measured the same in all versions back to 0.3, so it was no new slowdown but only showed with mp4 lists). A list now says whether it knows the first frame
  (the entry `first_frame` is in the segment; `Segment.first_unknown`): only lists from VB6, older versions or imported jobs are looked up, once per FILE (not per segment), and then
  the entry is written. The same file three times in the list is read once.
- **Copy mode question**: the line about joining several videos ends with "However, the definition of chapters is still possible."; the old sentence "The 'Copy mode' flag is not saved in the
  options nor in the batch script(s)" is replaced (it was wrong since the state is remembered).
- **The copy mode warning has a check box "Show this warning next time"** (ticked at first, under the text), the same one for all three cases where copy mode comes back on: at the
  start of the program, when a session is restored and when a job is imported from the batch file. Unticked, the new option `copy_mode_notice` (on|off, group Technical, also in the
  options dialog) goes to off and the warning is not shown any more in any of the three cases; switch it on again in the options. When a session is restored the warning is in the
  same window as the message about the restore (with the warning off only that message is shown). The warning itself is a window with an OK button (`dialogs.notice_with_checkbox`).
- **Copy mode is remembered for the next start**: the state is written to the INI file as its own entry `copy_mode=on|off` in [settings] (not among the options, so not in the options
  dialog) at every change and once more when the program ends, and put back at the next start, with the same note as for an import or a session ("... (the last run was made in copy mode) ...").
  The file is only written when that changes something (no entry and "off" are the same), so the INI file of someone who never uses copy mode stays as it is. A new job
  (fresh start) begins without copy mode and writes "off". After restoring a session the state of the program counts, not the entry in the INI file that was put back. The note
  now reads: "Attention: copy mode is switched ON now (... was made in copy mode), hence activating output file creation without re-encoding. A single video can be cut at a keyframe or several are joined in full
  length, with or without chapters; cropping, logo filters, rescaling and the output profile are ignored. To enable re-encoding, switch copy mode off in the Edit menu." (after a blank line; the wording of
  the user's own change in his clone, taken over so that the update does not clash with it).
- **Copy mode in the batch file, in the import and in sessions**:
  * **File => Batch works in copy mode** now (it was refused, as in VB6): the script has the comment `# M=copy` (like J, P, T, C, K), writes the list of files for the concat demuxer
    (`<target>.files.tmp`, the paths mapped by `path_map`) and the chapters file for ffmpeg by itself when it runs, calls ffmpeg with `-c copy` (no filter, no encoding) and removes the
    temporary files. A single segment is a cut at a keyframe with absolute times, as when saving. The comment K= keeps the chapters as the program has them, the heredoc has what ffmpeg
    needs (in copy mode with files joined: the times of the whole files). The message says what copy mode does with the job. The reason why a list cannot be saved is told at once.
  * **Import** (File => Import): a job with `M=copy` switches copy mode ON again, with a note; a job without it switches copy mode off (no note). Scripts of older versions have no
    flag and count as made without copy mode.
  * **Sessions** keep whether copy mode was on (`copy_mode` in `session.json`; the list shows `[copy mode]`). Restoring the segment list (part "list") puts copy mode back as it was, with a
    note in the message when it is switched ON; restoring only the settings leaves it alone; sessions of older versions count as made without copy mode.
- **Copy mode: the reason why a list cannot be saved is told at once**, when Save as MP4/AVI is called, and no longer only after the name of the target file was asked for
  (just before ffmpeg would start). Same check as before (`copymode.make_plan`: segments of one file with cut markers, files that differ, no segments). File => Batch does the same
  check first (it works in copy mode now, see above).
- **Fix: "counting frames ..." stayed in the title** of the main window. Only a counting that ended WITH a result took the note away; if the counting ended without one (file not
  readable, cancelled, any other error) the file stayed in the list of the running countings for good. Now every counting reports when it ends (`FrameCounter.ended`), and the
  note shows the files whose counting is really still running (two countings of the same file at the same time are told apart); counters that have ended are let go when the
  next one starts.
- **Fix: copy mode refused the same whole file several times** ("The list has 3 segments of the same video ... cutting AND joining") although nothing is cut. A list of one
  file only is refused now only if one of its segments has cut markers (the message names them and says that removing the markers joins the whole video n times); with no
  cut markers the file is joined n times, with one chapter per item.

## 0.5

Fifth frozen state: Copy mode (cut at a keyframe, or join in full length, without re-encoding), Chapters (editor, validity, batch file, import, sessions),
cropping of a single segment, import of a job from the batch file, Dedup scene, "Play now?" after saving, and the many smaller things below.
Still to do: DVD mode, multilanguage, and more tests with several audio and subtitle tracks.

- **Chapters** (Edit => Chapters, Ctrl+H; VB6 `frmChapters` with `savetxt()`; modules `chapters.py`, `chapters_dialog.py`): the chapter editor shows one chapter per
  segment. The check box "Add chapter(s) to target file" switches them on (the first style is made at once) and off (the file is deleted); the style
  (Enumerated, Named = "Scene from <file>", Named (short), Previous = the names of the existing file, From Batch = the names in the last job of the batch file that has
  chapters) gives the names; a double click or F2 edits a name; every change writes the chapters file at once (`MediaMaker.chapters` next to the INI file, ffmpeg's
  metadata format). When there are more or fewer names than segments, the surplus ones are dropped and the missing ones are called "Scene n". The old warning
  "input files must not have chapters" is hidden: the command now takes the chapters explicitly from this file (`-map_chapters`), so a source with chapters of its own
  does no harm. VB6 wrote the times in microseconds under `TIMEBASE=1/1000` (a factor of 1000 too long); they are milliseconds now, rounded from the running sum so that
  nothing drifts. `&` is no longer replaced by `+` (that was for the batch file of Windows).
  * **Validity**: the times come from the segments, so the file is only valid while the segments are the same. It carries a signature of them in a comment line (file,
    cut points counted from the first video frame, frame rate, order): deleting, moving, loading again or other cut points make it useless, cropping, rescaling, the
    logo filter and the target output profile do not, nor does a correction of the first frame. Whenever the list is saved or loaded the file is checked; if it does not
    fit any more it is deleted, after a warning. (VB6 deleted the file when the program ended; it is kept now, as long as it is valid.)
  * **Saving** takes valid chapters into the target file (`-i <chapters> -map_chapters`). In copy mode with several files joined (concat demuxer) the chapters take their
    NAMES from the chapters file and their TIMES from the durations of the whole files as the container gives them (`mediaprobe.format_duration`): the concat demuxer moves
    each file by the duration of the one before it, and that is longer than the picture alone when the sound starts before the picture (measured with a recording: the picture
    of part 2 began at 29.92 s, the file 1 is 29.676 s long, but only 28.46 s of picture; chapters made from the number of pictures would have begun 1.2 s too early).
    A cut has one chapter, a little off because the start is a keyframe. avi and ts cannot hold chapters at all (ffmpeg leaves them out without a word): the message after
    saving says so (mp4 and mkv work, also with the concat demuxer).
  * **Batch file**: the chapters are written as the comment `K=` (like J, P, T, C) AND as a heredoc that the script runs to make the file when it runs, also long after the
    program was closed, next to the target file (`<target>.chapters.tmp`, removed after the call). Old steps keep them.
  * **Import** asks whether to restore the chapters of the job. **Sessions** contain the file; the window for restoring has a third box "Chapters" (ticked every time); chapters
    that do not fit the restored list are deleted with the warning.
- **Play now?**: the message after a successful save (interactive mode; not in the batch script) ends with the question "Play now?"; Yes opens the result with the
  program that the system has for it (`xdg-open`), No does nothing; if the player cannot be started the error is told. An error or a cancel does not ask.
- **Chapter editor: editing a name**: a single click on a row opens the editor IN the row (VB6: label edit; Enter or a click elsewhere confirms, Escape cancels; an empty
  name is put back; the file is written when a name was confirmed), a double click or F2 opens the separate window as before. The editor in the row starts after the time of
  a double click (`QApplication.doubleClickInterval()`), so that a double click can cancel it and open the window instead. Qt's own triggers are switched off for this.
  So that it can be seen that the editor is there, the blue bar of the marked row is taken away while it is open, the cursor stands at the end of the text (no text
  marked) and flashes there, and when the editor is closed the row is marked again.
- **Chapter editor layout**: the check box no longer sits on the edge of the frame (the frame showed through it). The frame, with everything in it, and the Close button
  move down, the frame has the caption "Chapter names" (it was "Frame1" in the VB6 form), the check box stands alone above it. Done when the window is built, the
  generated user interface is unchanged.
- **Play now?**: the message after a successful save (interactive mode) ends with the question "Play now?"; Yes opens the result with the player that the system has for the file
  type (`xdg-open`), No does nothing. An error of the player is told. After an error or a cancel there is no question.
- **Open dialog**: the file type that was chosen there (for example mp4 or avi instead of ts) is the first suggestion the next time, as long as the program runs;
  it is not saved, a new run starts with ts again. Cancelling does not forget it.
- **Copy mode**: switching it OFF is confirmed with a message ("Copy mode is switched off."); switching it on asks first, as before.
- **Copy mode** (Edit => Copy mode, Ctrl+D; module `copymode.py`): saving WITHOUT re-encoding (`-c copy`, no `filter_complex`). It is a switch in the menu, not an option; since 0.6-dev its state is also remembered (see below), in the batch file and in sessions (VB6 could only join files, and its menu entry could not even be checked before). Switching it on
  warns first (Continue anyway?). The decisive number is that of different SOURCE FILES in the list:
  * **one video, one segment**: cut at a keyframe, without trim and without `setsar=1`, so the aspect ratio of the source stays. ffmpeg starts a copied
    cut at the first keyframe that is NOT BEFORE the marker, never before it; the end is marker B. A segment that is the whole file is copied as it is.
    (Measured with a TV recording: `-ss`/`-t` counted from the cut end up to 0.4 s early because of the lead of the sound; the command therefore uses
    absolute times, `-copyts -seek_timestamp 1 -ss <start> -i <file> -to <end> ... -avoid_negative_ts make_zero`, container start + frame number / frame rate.)
  * **several videos** (at least two different files): EVERY item of the list is joined in full length with the concat demuxer (`-f concat -safe 0`), in the order of the
    list, as VB6 did; the same file may be in the list several times (A, B, A gives three parts and three chapters; a first version joined every file only once and dropped
    the chapters then). Cut markers, cropping, logo filters, rescaling and the output profile are ignored (the message after saving says what was not taken into account). Files
    with different size, frame rate or sample rate are refused with the list of differences.
  * a list of ONE file only with several segments is refused (that would be cutting AND joining).
  * the sound track (`audio`, all of them with `multilanguage`) and the subtitles (`subtitle`, numbers 1, 2 ...; for mp4 as `mov_text`) are chosen with `-map`;
    what is not mapped is deleted; `build_copy_command` accepts a chapters file for the chapters function that is still to come. File => Batch
    works in copy mode too (since 0.6-dev).
- After an **import** from the batch file or a **restore** of a session the first entry of the list is selected as a whole (all fields, as if it had been
  clicked; before only the number field showed the focus); the crop window is centred in the preview. It is now a PART of the main window, not a window of its own: under Wayland the compositor decides where a
  window goes, so the position could not be set (it came up in the middle of the main window). As in VB6 the rest of the main window cannot be used while it is
  open; closing the main window cancels it;
  the window for **Restore session** has a check box "Save the current state as a session first", so that the number of automatic
  sessions stays manageable; the question and the message after the restore say which it was. The choice of this box is remembered between the runs of the
  program in the new option `restore_backup` (on|off, group Technical, default on; a restored INI file does not take it back); the other two boxes
  (segment list, settings) are ticked every time.
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
the additional files of a recording, the reference logo, tools and help texts in the INI file, and many smaller things below.
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
- **Edit => Dedup scene (Ctrl+V; was Ctrl+F8 until 0.6)** (first "Overlap segments"), VB6 `mnuDeDup_Click` with `match()` and `far()` (new module `dedup.py`). The names and texts follow the
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
  frame number, the picture 17 frames (0.68 s) later than ffmpeg does. With the option
  `logo_rewind = 0` the search "Seek end of commercial" was precise to within a few frames; the preview offset is therefore only noted, not corrected.
- **Button L shows what it did**: after creating the reference logo a window shows the picture L took the logo from (the rectangle marked), the area of the
  logo enlarged and the edges that are searched for, so that a logo that is not in the picture is seen at once. The picture, the frame number and
  the preview picture of that moment are kept.
- Option `logo_rewind = 0` now returns the first frame WITH logo (before: the last one without it); a search that finds no logo returns the end of
  the movie.
- **"Seek next commercial" / "Seek end of commercial" say which method they use**: the wait window begins with "Seeking with crop = 72" (crop > 0: black
  border) or "Seeking with reference logo" (crop = 0), so that a crop left over from an earlier session does not go unnoticed.
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
