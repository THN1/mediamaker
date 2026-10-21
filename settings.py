"""Settings: reads and writes the INI file of MediaMaker (same format as under VB6).

The file stays readable and editable by hand. When writing, only the changed line is replaced; comments,
order and all other sections (e.g. the Windows tool paths) remain unchanged.

Important keys:
  [settings] options=  options as a key="value" list (crop, floor, blackness, allowance, ...)
  [settings] profile=  current target profile (scale, fps, bv, ar, ba, ...)
  [settings] last=     last opened file
  [profiles]           named profiles, one entry per line
  [ToolTipText]        explanations of the keys
  [tools.linux]        optional: paths to ffmpeg/ffprobe (otherwise they are searched in the PATH)
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

    # ------------------------------------------------------------------ Settings of MediaMaker
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

    def tooltip(self, key: str) -> str:
        return self.get("ToolTipText", key, "") or DEFAULT_TOOLTIPS.get(key, "")

    def tool(self, name: str) -> Optional[str]:
        """Path of a helper program: [tools.linux], otherwise in the PATH."""
        value = self.get("tools.linux", name)
        if value:
            return value.split("|")[0]
        return shutil.which(name)


def default_options() -> dict:
    """Defaults in case the INI file contains no options yet (as in VB6). The step widths of the search are given in seconds
        (40 s = 1000 frames and 240 s = 6000 frames at 25 FPS, the values from VB6); logo_rewind corresponds to 45 frames."""
    return {"crop": "0", "floor": "2", "blackness": "12", "allowance": "1000", "overlap": "400", "audio": "1",
            "pause": "160", "detect": "0", "aflags": "", "subtitle": "0", "multilanguage": "False",
            "step_end": "40", "step_next": "240", "border_tol": "3", "cut_window": "5", "logo_rewind": "1.8",
            "logo_edge": "18", "logo_conf": "0.2", "cut_diff": "30"}


# explanations for keys that are still missing in the INI file (section [ToolTipText])
DEFAULT_TOOLTIPS = {
    "pad": "If True, source videos will be padded with (minimal) black border(s), else they will be stretched to the target scale",
    "step_end": "Seeking the end of a commercial: initial step width in seconds (refined by factor 10 down to single frames)",
    "step_next": "Seeking the next commercial: initial step width in seconds (refined by factor 10 down to single frames); "
                 "limited to the value of 'pause' so that no commercial break can be skipped",
    "border_tol": "Seeking with the black border: tolerance in scanlines when comparing the detected border with the crop value",
    "cut_window": "Seeking with the black border: after the border has been found, look this many frames back for a hard cut and move "
                  "the result onto it (0 = off). The border changes a little later than the picture.",
    "cut_diff": "Seeking with the black border (advanced): min. mean difference (0 to 255) between two frames to count as a hard cut",
    "logo_rewind": "Seeking with the station logo: max. number of seconds to go back from the first frame showing the logo, "
                   "looking for the start of the scene (the logo may appear some seconds late)",
    "logo_edge": "Logo detection (advanced): min. grey level difference of neighbouring pixels that counts as an edge",
    "logo_conf": "Logo detection (advanced): min. share (0 to 1) of the reference edges that must be found for the logo to count as present",
}
