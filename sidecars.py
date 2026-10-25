"""The additional files of a TV recording.

A satellite receiver writes next to the recording `20261024 2220 - SAT_1 - Chappie.ts` some more files:
    20261024 2220 - SAT_1 - Chappie.eit        the programme information of the broadcaster
    20261024 2220 - SAT_1 - Chappie.ts.ap      access points (positions of keyframes)
    20261024 2220 - SAT_1 - Chappie.ts.cuts    the cut marks
    20261024 2220 - SAT_1 - Chappie.ts.meta    name, description, time
    20261024 2220 - SAT_1 - Chappie.ts.sc      start codes (for fast winding)
They belong to the recording and are useless without it. Only these are meant: the files that begin with the whole name of the recording and a
dot, and `<name without extension>.eit`. Other files with the same beginning (e.g. a converted `... Chappie.mp4`) are NOT.
"""
from __future__ import annotations

import os


def sidecar_files(path: str) -> list:
    """The additional files of the recording `path` that exist (full paths, sorted). The recording itself is not among them."""
    folder, name = os.path.split(path)
    stem = os.path.splitext(name)[0]
    try:
        entries = os.listdir(folder or ".")
    except OSError:
        return []
    found = []
    for entry in sorted(entries):
        full = os.path.join(folder, entry)
        if entry == name or not os.path.isfile(full):
            continue
        if entry.startswith(name + ".") or entry.lower() == (stem + ".eit").lower():
            found.append(full)
    return found
