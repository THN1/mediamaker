"""Sessions: a snapshot of the work (the segment list and the settings) that can be restored later.

VB6 copied the files into a folder named with the time and pushed it into a 7-Zip archive. Here every session is a small zip file of its own
(standard library, no extra program) in the folder `sessions` next to the INI file:

    2026.10.25_14-03-12.zip
        MediaMaker.ini      the settings (profiles, options, tool paths ...)
        MediaMaker.json     the segment list (the masks of the logo filters are part of it)
        session.json        what the session is: time, note, number of segments, their titles, program version

One file per session means: nothing is rewritten when a session is added, deleting a session is deleting a file, a session can be copied or sent
by mail, any archive program opens it, and a damaged session does not harm the others. The name is the time (as in VB6), so the list is sorted by time.
"""
from __future__ import annotations

import datetime
import json
import os
import zipfile
from dataclasses import dataclass, field
from typing import Optional

FORMAT = "mediamaker-session"
EXTENSION = ".zip"
MANIFEST = "session.json"
INI_NAME = "MediaMaker.ini"
LIST_NAME = "MediaMaker.json"
PARTS = {"ini": INI_NAME, "list": LIST_NAME}


class SessionError(Exception):
    """A session cannot be read or restored."""


@dataclass
class SessionInfo:
    stamp: str                       # the name without extension: yyyy.mm.dd_hh-mm-ss
    path: str
    created: str = ""                # ISO time from the manifest (else from the stamp)
    note: str = ""
    segments: int = 0
    titles: list = field(default_factory=list)
    program: str = ""
    size: int = 0
    has_ini: bool = False
    has_list: bool = False
    ok: bool = True                  # False: the file is not a readable session

    def describe(self) -> str:
        """One line for the list of sessions."""
        when = self.created.replace("T", " ")[:19] if self.created else self.stamp
        if not self.ok:
            return f"{when}  (damaged: {os.path.basename(self.path)})"
        what = f"{self.segments} segment{'s' if self.segments != 1 else ''}"
        if self.titles:
            what += f": {self.titles[0]}" + (f" (+{len(self.titles) - 1})" if len(self.titles) > 1 else "")
        return f"{when}  {what}" + (f"  - {self.note}" if self.note else "")


def default_directory(ini_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(ini_path)), "sessions")


def new_stamp(now: Optional[datetime.datetime] = None) -> str:
    return (now or datetime.datetime.now()).strftime("%Y.%m.%d_%H-%M-%S")


def _stamp_to_iso(stamp: str) -> str:
    try:
        return datetime.datetime.strptime(stamp[:19], "%Y.%m.%d_%H-%M-%S").isoformat(timespec="seconds")
    except ValueError:
        return ""


def read_info(path: str) -> SessionInfo:
    """Information about a session file; `ok` is False if it is no readable session."""
    stamp = os.path.splitext(os.path.basename(path))[0]
    info = SessionInfo(stamp=stamp, path=path, created=_stamp_to_iso(stamp), size=os.path.getsize(path) if os.path.exists(path) else 0)
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            info.has_ini, info.has_list = INI_NAME in names, LIST_NAME in names
            if MANIFEST in names:
                data = json.loads(z.read(MANIFEST).decode("utf-8"))
                if data.get("format") != FORMAT:
                    raise SessionError("not a MediaMaker session")
                info.created = data.get("created", info.created)
                info.note = data.get("note", "")
                info.segments = int(data.get("segments", 0))
                info.titles = list(data.get("titles", []))
                info.program = data.get("program", "")
            elif not (info.has_ini or info.has_list):
                raise SessionError("no files of a session")
    except (zipfile.BadZipFile, OSError, ValueError, SessionError):
        info.ok = False
    return info


def list_sessions(directory: str) -> list[SessionInfo]:
    """All sessions in the folder, the newest first. Other files are ignored."""
    if not os.path.isdir(directory):
        return []
    files = [f for f in os.listdir(directory) if f.lower().endswith(EXTENSION)]
    return [read_info(os.path.join(directory, f)) for f in sorted(files, reverse=True)]


def create_session(directory: str, ini_path: str, list_path: str, segments: list, note: str = "", program: str = "",
                   now: Optional[datetime.datetime] = None) -> SessionInfo:
    """Writes a new session file (first under a temporary name, so that a failure leaves no half file) and returns its information."""
    os.makedirs(directory, exist_ok=True)
    stamp = new_stamp(now)
    name, n = stamp, 1
    while os.path.exists(os.path.join(directory, name + EXTENSION)):
        n += 1                                       # a second session within the same second
        name = f"{stamp}_{n}"
    path = os.path.join(directory, name + EXTENSION)
    manifest = {"format": FORMAT, "version": 1, "created": (now or datetime.datetime.now()).isoformat(timespec="seconds"),
                "note": " ".join(note.split()), "program": program, "segments": len(segments),
                "titles": [s.name for s in segments], "files": [n for n, p in ((INI_NAME, ini_path), (LIST_NAME, list_path)) if os.path.exists(p)]}
    part = path + ".part"
    try:
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            for arcname, source in ((INI_NAME, ini_path), (LIST_NAME, list_path)):
                if os.path.exists(source):
                    z.write(source, arcname)
            z.writestr(MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False))
        os.replace(part, path)
    finally:
        if os.path.exists(part):
            os.remove(part)
    return read_info(path)


def restore_session(info: SessionInfo, ini_path: str, list_path: str, parts: tuple = ("ini", "list")) -> list[str]:
    """Puts the files of the session back (each one replaced in one step). Returns the names of the restored files.

    Everything is read and checked first (zip intact, the list is a MediaMaker list), only then something is written."""
    wanted = [PARTS[p] for p in parts]
    targets = {INI_NAME: ini_path, LIST_NAME: list_path}
    try:
        with zipfile.ZipFile(info.path) as z:
            bad = z.testzip()
            if bad:
                raise SessionError(f"The session is damaged ({bad}).")
            data = {}
            for name in wanted:
                if name not in z.namelist():
                    raise SessionError(f"The session has no {name}.")
                data[name] = z.read(name)
    except (zipfile.BadZipFile, OSError) as e:
        raise SessionError(f"The session cannot be read: {e}") from e
    if LIST_NAME in data:
        try:
            if json.loads(data[LIST_NAME].decode("utf-8")).get("format") != "mediamaker-segments":
                raise ValueError
        except ValueError as e:
            raise SessionError("The segment list in the session is not a MediaMaker list.") from e
    for name, content in data.items():
        target = targets[name]
        part = target + ".part"
        with open(part, "wb") as f:
            f.write(content)
        os.replace(part, target)
    return list(data)


def delete_session(info: SessionInfo) -> None:
    os.remove(info.path)
