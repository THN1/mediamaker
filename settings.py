"""Settings: reads and writes the INI file of MediaMaker (same format as under VB6).

The file stays readable and editable by hand. When writing, only the changed line is replaced; comments,
order and all other sections remain unchanged. The paths of helper programs (avidemux, vlc) are options (group Tools).

Important keys:
  [settings] options=  options as a key="value" list (crop, floor, blackness, allowance, ...)
  [settings] profile=  current target profile (scale, fps, bv, ar, ba, ...)
  [settings] last=     last opened file
  [profiles]           named profiles, one entry per line
  [ToolTipText]        explanations of ALL keys (options and profile); missing ones are added at the start (sync_tooltips)
"""
from __future__ import annotations

import os
import re
import shutil
from typing import Optional

from cutlist import parse_kv


def format_kv(values: dict) -> str:
    """{'crop': '72', 'floor': '2'} -> 'crop="72" floor="2"'"""
    return " ".join(f'{k}="{v}"' for k, v in values.items())


class Settings:
    def __init__(self, path: str):
        self.path = path
        self._newline = "\n"
        self._lines: list[str] = []
        self.load()

    # ------------------------------------------------------------------ File
    def load(self) -> None:
        if not os.path.exists(self.path):
            self._lines = []
            return
        raw = open(self.path, "rb").read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")           # file comes from VB6 (ANSI)
        self._newline = "\r\n" if "\r\n" in text else "\n"
        self._lines = text.replace("\r\n", "\n").split("\n")
        if self._lines and self._lines[-1] == "":
            self._lines.pop()

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(self._newline.join(self._lines) + self._newline)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------ Access to sections
    def _section_range(self, section: str) -> Optional[tuple[int, int]]:
        start = None
        for i, line in enumerate(self._lines):
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                if start is not None:
                    return start, i
                if s[1:-1].lower() == section.lower():
                    start = i + 1
        return (start, len(self._lines)) if start is not None else None

    def items(self, section: str) -> list[tuple[str, str]]:
        rng = self._section_range(section)
        out = []
        if rng:
            for line in self._lines[rng[0]:rng[1]]:
                s = line.strip()
                if s and not s.startswith(";") and "=" in s:
                    k, _, v = s.partition("=")
                    out.append((k.strip(), v.strip()))
        return out

    def get(self, section: str, key: str, default: Optional[str] = None) -> Optional[str]:
        for k, v in self.items(section):
            if k.lower() == key.lower():
                return v
        return default

    def set(self, section: str, key: str, value: str) -> None:
        """Replaces the value (only this line) or appends the key to the section."""
        rng = self._section_range(section)
        if rng is None:
            if self._lines and self._lines[-1].strip():
                self._lines.append("")
            self._lines += [f"[{section}]", f"{key}={value}"]
            return
        for i in range(*rng):
            s = self._lines[i].strip()
            if s and not s.startswith(";") and s.partition("=")[0].strip().lower() == key.lower():
                self._lines[i] = f"{key}={value}"
                return
        last = rng[1]
        while last > rng[0] and not self._lines[last - 1].strip():
            last -= 1                                              # insert after the last non-empty line
        self._lines.insert(last, f"{key}={value}")

    def delete(self, section: str, key: str) -> bool:
        """Removes the line of a key; False if it does not exist."""
        rng = self._section_range(section)
        if rng is None:
            return False
        for i in range(*rng):
            line = self._lines[i].strip()
            if line and not line.startswith(";") and line.partition("=")[0].strip().lower() == key.lower():
                del self._lines[i]
                return True
        return False

    # ------------------------------------------------------------------ Settings of MediaMaker
    def migrate_legacy_keys(self, keys=("batch", "player", "dialog_style", "vlc_args", "hide_messages")) -> bool:
        """Settings that used to be keys of their own in [settings] now belong to the string options= (and the options dialog):
        their values move there, unless options= has the key already, and the old lines are removed. True if something changed
        (the caller saves)."""
        options = self.options
        changed = False
        for key in keys:
            value = self.get("settings", key)
            if value is None:
                continue
            if key not in options:
                options[key] = value.strip()
            self.delete("settings", key)
            changed = True
        if changed:
            self.set_options(options)
        return changed

    @property
    def options(self) -> dict:
        return parse_kv(self.get("settings", "options", ""))

    def set_option(self, key: str, value) -> None:
        opts = self.options
        opts[key] = str(value)
        self.set("settings", "options", format_kv(opts))

    def set_options(self, options: dict) -> None:
        self.set("settings", "options", format_kv(options))

    @property
    def profile(self) -> dict:
        return parse_kv(self.get("settings", "profile", ""))

    def set_profile(self, profile: dict) -> None:
        self.set("settings", "profile", format_kv(profile))

    def update_profile(self, updates: dict) -> None:
        """Changes individual values of the current profile (VB6: uky "profile", key, value)."""
        profile = self.profile
        profile.update(updates)
        self.set_profile(profile)

    def save_profile(self, name: str, profile: dict) -> None:
        """Stores the profile under a name in the section [profiles] (overwrites one with the same name)."""
        self.set("profiles", name, format_kv(profile))

    @property
    def profiles(self) -> dict:
        return {name: parse_kv(value) for name, value in self.items("profiles")}

    @property
    def last(self) -> str:
        return self.get("settings", "last", "") or ""

    @last.setter
    def last(self, path: str) -> None:
        self.set("settings", "last", path)
        self.save()

    RECENT_LIMIT = 10                    # number of folders that are remembered

    @property
    def copy_mode(self) -> bool:
        """Copy mode as it was when the program ended ([settings] copy_mode=on|off). It is not an option (not in the options dialog): it is the state of the
        menu entry Edit => Copy mode, which is put back at the next start."""
        return (self.get("settings", "copy_mode", "off") or "off").strip().lower() == "on"

    def set_copy_mode(self, on: bool) -> bool:
        """Remembers the state. The file is only written if that changes something (no entry and off are the same), so that the INI file of someone who never
        uses copy mode stays as it is. True if the file was written."""
        if bool(on) == self.copy_mode:
            return False
        self.set("settings", "copy_mode", "on" if on else "off")
        self.save()
        return True

    @property
    def recent_dirs(self) -> list:
        """Folders of target files used recently, newest first ([settings] recent_dirs=, separated by |)."""
        return [d for d in (self.get("settings", "recent_dirs", "") or "").split("|") if d.strip()]

    def add_recent_dir(self, directory: str) -> None:
        """Puts a folder at the top of the list of recently used folders (without duplicates, at most RECENT_LIMIT)."""
        directory = os.path.normpath(directory.strip()) if directory and directory.strip() else ""
        if not directory or directory == ".":
            return
        folders = [directory] + [d for d in self.recent_dirs if d != directory]
        self.set("settings", "recent_dirs", "|".join(folders[:self.RECENT_LIMIT]))

    def tooltip(self, key: str) -> str:
        return self.get("ToolTipText", key, "") or DEFAULT_TOOLTIPS.get(key, "")

    def tool(self, name: str) -> Optional[str]:
        """Path of a helper program (avidemux, vlc): the option of that name (group Tools), otherwise the PATH."""
        value = (self.options.get(name) or "").strip()
        if value:
            return os.path.expanduser(value)
        return shutil.which(name)

    TOOL_KEYS = ("avidemux", "vlc")
    TOOL_SECTIONS = ("tools.linux", "tools.windows", "tools")

    def remove_section(self, section: str) -> bool:
        """Removes a section with its header and everything in it."""
        rng = self._section_range(section)
        if rng is None:
            return False
        end = rng[1]
        while end > rng[0] and not self._lines[end - 1].strip():
            end -= 1                                              # the empty lines before the next section stay
        del self._lines[rng[0] - 1:end]
        return True

    def migrate_tools(self) -> bool:
        """The paths of helper programs used to be keys of a section [tools.linux]; they are options now (group Tools). The values move there
        (unless the option is set), the lines are removed, and a section that has no keys left is removed, too. True if something changed."""
        options = self.options
        changed = False
        for section in self.TOOL_SECTIONS:
            for key in self.TOOL_KEYS:
                value = self.get(section, key)
                if value is None:
                    continue
                if not options.get(key) and value.strip():
                    options[key] = value.split("|")[0].strip()
                self.delete(section, key)
                changed = True
            if self._section_range(section) is not None and not self.items(section):
                self.remove_section(section)
                changed = True
        if changed:
            self.set_options(options)
        return changed

    def sync_tooltips(self, wanted: dict, obsolete: tuple = ()) -> bool:
        """Makes the section [ToolTipText] complete: every key of `wanted` (key -> text) that is missing is appended (texts that are there, also
        edited ones, stay), keys in `obsolete` are removed. The section is created if there is none. True if something changed."""
        changed = False
        present = {k.lower() for k, _ in self.items("ToolTipText")}
        for key in obsolete:
            if key.lower() in present and key not in wanted:
                self.delete("ToolTipText", key)
                present.discard(key.lower())
                changed = True
        for key, text in wanted.items():
            if key.lower() not in present:
                self.set("ToolTipText", key, text)
                changed = True
        return changed


def default_options() -> dict:
    """Defaults in case the INI file contains no options yet (as in VB6). The step widths of the search are given in seconds
        (40 s = 1000 frames and 240 s = 6000 frames at 25 FPS, the values from VB6)."""
    return {"crop": "0", "floor": "2", "blackness": "12", "allowance": "1000", "dedup": "400", "audio": "1",
            "pause": "160", "detect": "0", "aflags": "", "subtitle": "0", "multilanguage": "False",
            "step_end": "40", "step_next": "240", "border_tol": "3", "cut_window": "5",
            "logo_edge": "18", "logo_conf": "0.2", "cut_diff": "30", "path_map": "",
            "batch": "", "player": "memory", "dialog_style": "tabs", "vlc_args": "", "hide_messages": "", "overlay_opacity": "35", "file_dialog": "qt", "sessions_dir": "", "avidemux": "", "vlc": "", "cutpoint_filters": "on", "restore_backup": "on"}


# explanations for keys that are still missing in the INI file (section [ToolTipText])
DEFAULT_TOOLTIPS = {
    # profile parameters
    'description': 'Description of settings in this profile',
    'scale': 'Target video screen size in format width:height',
    'sws_flags': 'Use this ffmpeg scaling algorithm; see https://ffmpeg.org/ffmpeg-scaler.html#Scaler-Options',
    'fps': 'Target frame rate (frames per second); format must be exactly ##.###',
    'bv': 'Target video bitrate (quality); don\'t forget the "k" suffix!',
    'acodec_in': 'Name of audio codec to be used when extracting the audio track from the source file(s)',
    'acodec_out': 'Name of audio codec to be used in the target output file',
    'ar': 'Target audio resampling rate (usually 44100 or 48000)',
    'ba': 'Target audio bitrate (quality); don\'t forget the "k" suffix!',
    # options from VB6
    'crop': 'Remove this many pixels at top and bottom of source video frame; usually in the range of 60 to 74',
    'floor': 'Seek next earlier keyframe in this many seconds; should be 1 (or maybe 2)',
    'blackness': 'RGB-related value below which non-black pixels will be considered black (RGB=0) during auto-cropping',
    'allowance': 'During auto-cropping, max. number of non-black pixels allowed in one scanline to be still considered black',
    'dedup': 'Max. number of frames examined during duplicate scene removal search (menu Edit => Dedup scene)',
    'audio': 'Use nth detected audio stream (language); should be 1 unless (optionally) for multilanguage DVD',
    'pause': 'Min. length (in seconds) of pause caused by commercials in between movie segments (for TV recordings)',
    'detect': 'Detect audio streams after moving n milliseconds into the source file; useful for streamed recordings (.ts)',
    'aflags': 'Flags for ffmpeg when extracting audio (like +igndts+genpts); useful when audio is broken',
    'subtitle': 'Add subtitles from the given track(s) number(s), separated by ",", or zero (0) to disable subtitling (use Ctrl-K or menu Edit => Media info)',
    'multilanguage': 'False (default) or True; allows to add secondary language stream(s), if present in source video (EXPERIMENTAL)',
    # options added in the Python version
    "restore_backup": "Restore session: on = the check box \"Save the current state as a session first\" is ticked when the window opens; the program remembers "
                      "your last choice here (the other two check boxes are ticked every time); applies at once",
    "cutpoint_filters": "Analyze cut point: on = the clip is made with all the filters that Save As applies (cropping, scaling, DeLogo, RemoveLogo); "
                        "off = without cropping and logo filters (only scaled to the profile), with a note in the picture; applies at once",
    "avidemux": "Tools: path of Avidemux (e.g. an AppImage; it must be executable) for Edit => Analyze cut point; empty: searched in the PATH; applies at once",
    "vlc": "Tools: path of the VLC program that plays the clip of Edit => Analyze cut point; empty: searched in the PATH, then the standard player of the desktop; applies at once",
    "pad": "If True, source videos will be padded with (minimal) black border(s), else they will be stretched to the target scale",
    "step_end": "Seeking the end of a commercial: initial step width in seconds (refined by factor 10 down to single frames)",
    "step_next": "Seeking the next commercial: initial step width in seconds (refined by factor 10 down to single frames); "
                 "limited to the value of 'pause' so that no commercial break can be skipped",
    "border_tol": "Seeking with the black border: tolerance in scanlines when comparing the detected border with the crop value",
    "cut_window": "Seeking with the black border: after the border has been found, look this many frames back for a hard cut and move "
                  "the result onto it (0 = off). The border changes a little later than the picture.",
    "path_map": "Batch file: replaces the beginning of the source paths in the ffmpeg call, \"source=target;source=target\". "
                "A * in a source stands for any characters except /, e.g. /run/user/*/kio-fuse-*/smb/root@nas/Harddisk=/mnt/nas/Harddisk",
    "overlay_opacity": "Station logo: how strongly the red areas show, in percent: the rectangle of the DeLogo filter over the preview "
                       "and the band in the RemoveLogo dialog (0 = only the edge, 100 = solid red); applies at once",
    "file_dialog": "File dialog of Save as MP4/AVI: qt = Qt's own dialog (a double click on an existing file saves it; the folders used "
                   "recently are among its places), native = the dialog of your desktop (in some KDE setups a double click on an existing "
                   "file did nothing there); applies at once",
    "sessions_dir": "Sessions (File => Backup session): folder with the saved sessions; a leading ~ is your home folder (empty: the folder "
                    "'sessions' next to the INI file); applies at once",
    "batch": "Batch: file the batch script is written to; a leading ~ is your home folder (empty: next to the INI file, "
             "with the extension .sh); applies at once",
    "player": "Preview: memory = VLC decodes into memory and Qt draws the pictures (runs natively under Wayland), "
              "embed = VLC draws into its own X11 window (XWayland); takes effect at the next start",
    "vlc_args": "Preview: additional arguments for libvlc, separated by spaces, e.g. --vout=xcb_x11; takes effect at the next start",
    "hide_messages": "Console: messages containing one of these texts are not shown, separated by | (the harmless messages of VDPAU, Wayland "
                     "and the KDE file dialog are always hidden); takes effect at the next start",
    "dialog_style": "Dialogs with several pages (options, Media info): tabs = tabs along the top, list = list of the pages on the left; "
                    "applies at once",
    "cut_diff": "Seeking with the black border (advanced): min. mean difference (0 to 255) between two frames to count as a hard cut",
    "logo_edge": "Logo detection (advanced): min. grey level difference of neighbouring pixels that counts as an edge",
    "logo_conf": "Logo detection (advanced): min. share (0 to 1) of the reference edges that must be found for the logo to count as present",
}
