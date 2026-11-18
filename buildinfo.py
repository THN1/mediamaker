"""Which version of the program is this? The version number says "0.8-dev" for months; what a test really ran with is the COMMIT.

The commit comes from git when the program runs from a clone (the update script makes one). A delivered program has no .git folder: the build step then puts a file COMMIT next to
the program (line 1: the commit, line 2: the date, line 3: the title of the commit), and that is read instead.
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
COMMIT_FILE = "COMMIT"


def _git(folder: str, *args: str) -> Optional[str]:
    """The output of a git command in this folder, None if git is missing, the folder is no repository, or it takes too long. Nothing is written (no index lock)."""
    try:
        done = subprocess.run(["git", "-C", folder, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=5,
                              env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.rstrip("\n") if done.returncode == 0 else None            # (not strip(): the first status line starts with a space)


def commit_info(folder: Optional[str] = None) -> dict:
    """What is known about the commit of the program in `folder`: hash, short, date, subject, describe (e.g. v0.7-12-g0db2bc3), branch, dirty (the tracked files with local changes),
    source ('git', 'file' or '' if nothing is known)."""
    folder = folder or HERE
    info = {"hash": "", "short": "", "date": "", "subject": "", "describe": "", "branch": "", "dirty": [], "source": ""}
    top = (_git(folder, "rev-parse", "--show-toplevel") or "").strip()
    if top and os.path.realpath(top) == os.path.realpath(folder):            # (a program inside ANOTHER repository, e.g. a home folder under git, is not this one)
        line = _git(folder, "log", "-1", "--format=%H%n%cI%n%s") or ""
        parts = line.split("\n", 2)
        if len(parts) == 3 and len(parts[0]) >= 7:
            info.update(hash=parts[0], short=parts[0][:7], date=parts[1], subject=parts[2], source="git")
            info["describe"] = (_git(folder, "describe", "--tags", "--always") or info["short"]).strip()
            info["branch"] = (_git(folder, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()
            status = _git(folder, "status", "--porcelain", "--untracked-files=no") or ""
            info["dirty"] = [x[3:] for x in status.splitlines() if len(x) > 3]
            return info
    try:
        with open(os.path.join(folder, COMMIT_FILE), encoding="utf-8") as f:
            lines = [x.strip() for x in f.read().splitlines()]
        if lines and len(lines[0]) >= 7:
            info.update(hash=lines[0], short=lines[0][:7], date=lines[1] if len(lines) > 1 else "", subject=lines[2] if len(lines) > 2 else "", describe=lines[0][:7], source="file")
    except OSError:
        pass
    return info


def one_line(info: dict) -> str:
    """'0db2bc3 (v0.7-12-g0db2bc3), 2026-11-13 16:40: DVD mode ...; local changes in 2 files' for versions.txt of the debug package and for the copy of the About window."""
    if not info.get("hash"):
        return "(unknown: not a git clone, and no file COMMIT next to the program)"
    text = f"{info['short']}"
    if info.get("describe") and info["describe"] != info["short"]:
        text += f" ({info['describe']})"
    if info.get("date"):
        text += f", {info['date'][:16].replace('T', ' ')}"
    if info.get("subject"):
        text += f": {info['subject']}"
    if info.get("dirty"):
        text += f"; LOCAL CHANGES in {len(info['dirty'])} file(s): {', '.join(info['dirty'][:6])}"
    return text
