# Changes

## 1.1 release candidate 1 (2026-11-22)

What is new since 1.0:

**Menus**
- The menus are arranged anew. *File*: files, the list, saving, sessions (and *Chapters...*, which belongs to the whole list). *Edit*: only what works on the selected
  segment: *Reuse source A/V*, *Auto crop*, *Media info*, *Analyze cut point*, *Dedup scene*, the two seek entries. New menu *Config*: *Profile...*, *Load profile*,
  *Save profile*, *Copy mode*, *Estimate bitrate(s)*, *Options...*. All shortcuts are unchanged.
- The menu *Deploy* is gone from the public version.

**Size of the windows**
- All dialogs and message boxes now have the font and the size of the main window (the option for an enlarged window, 125 %), not only the profile, options and
  information dialogs: questions and messages, input boxes, target file, bit rates, sessions, tracks, Readme, About, the viewer of the cut point (font only), and the
  crop, chapters, media info and logo mask windows.

**Audio and subtitle tracks (option `multitrack`)**
- The option has a third value. `on`: the dialog for the tracks opens whenever you save. `off`: never (a DVD is then saved with its first sound track and no
  subtitles). `dvd` (the new default): only when the files are the video files of a DVD. The dialog always has the buttons OK, Defaults and Cancel.
  Attention: an INI file with `multitrack=off` now switches the dialog off for DVDs as well; write `dvd` there to get the old behaviour back.
- Saving with subtitles from a very large recording on a slow network drive: ffmpeg has to read the whole recording once before the picture starts. The program now
  measures the reading speed, tells you beforehand how long this will take (when it is a minute or more) and asks whether to go on; the bar then says
  "Reading subtitles (about 7 minutes)..." instead of "Preparing job...".

**Fixes**
- *Cancel* during saving always works: ffmpeg is stopped even when it hangs reading a file on a network drive (before, only `kill -9` helped).
- Crashes on some Linux systems (openSUSE: "deallocating None", "free(): invalid pointer", abort while scrubbing the slider): the pictures and the events of VLC no
  longer reach Qt from a foreign thread, and the AppImage uses PySide6 below 6.9 (6.12 has a leak that brought the program down after a few minutes).
- *Close all* left the last picture in the preview; the preview is empty now.
- Cropping a 4:3 DVD (black bands left and right in the 16:9 preview): the red crop bands and the logo rectangle are now measured against the picture and stay inside it (before, 14 pixels of the file looked like 90 on the screen). Logo rectangles stored with 4:3 DVDs before may have to be placed again.
- Saving: after the dialog for the tracks the window showed nothing for a long time (a DVD with subtitles on a network drive: 40 s); the bar now says "Preparing job...  reading the files" at once, the window does not freeze, and Cancel works in this phase too.
- Saving: the file name is asked first; the tracks are then read in the background (with a message and Cancel), and the warning about the long reading time for subtitles is now shown inside the track dialog instead of in a separate question.
- The preview that stopped following the slider after hectic scrubbing on a network drive is reloaded by the program.
- ffmpeg without its own H.264 / H.265 decoder (openSUSE): the program says so when you open a file, with the way out (Packman, RPM Fusion).
- The Readme dialog showed this file broken after some entry; fixed.

**For bug reports**
- Ctrl+Shift+F1 makes a debug package. With the environment variable `MEDIAMAKER_DEBUG=1` the program writes a log (`mediamaker_debug.log`, in the configuration
  folder) that includes what ffmpeg says and does while saving.

## 1.0 (2026-11-18)

The first public version. Cuts, unifies and joins videos and TV recordings (segment list, frame-exact timeline, profiles, MP4 / MKV / AVI / TS, chapters, several audio
tracks and subtitles), finds the end of commercial breaks, removes black borders and the station logo, saves in batch jobs and sessions, DVD mode for the video files of a
DVD, preview with VLC, work done by ffmpeg. The history of the versions 0.1 to 1.0 (development) is in the git history of the project.
