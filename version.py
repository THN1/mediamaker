"""The version of the program and what depends on it.

A version that ends in "-dev" is a development version: it keeps its files (MediaMaker.ini, the debug log) next to the program and has the menu Deploy. A
version without "-dev" is a public one: its files are in the configuration folder of the user (~/.config/MediaMaker, or $XDG_CONFIG_HOME/MediaMaker),
because the folder of an installed program (a package, an AppImage) cannot be written to. The environment variable MEDIAMAKER_INI overrides the
place of the INI file in both.
"""
from __future__ import annotations

import os

VERSION = "1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
INI_NAME = "MediaMaker.ini"


def is_dev(version: str = None) -> bool:
    return (version or VERSION).endswith("-dev")


def config_dir() -> str:
    """The folder of the files of the user in a public version (made if it does not exist)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, "MediaMaker")
    os.makedirs(path, exist_ok=True)
    return path


def ini_path() -> str:
    """MEDIAMAKER_INI, otherwise MediaMaker.ini next to the program (development version) or in the configuration folder (public version)."""
    return os.environ.get("MEDIAMAKER_INI") or os.path.join(HERE if is_dev() else config_dir(), INI_NAME)


def debug_log_path() -> str:
    """mediamaker_debug.log (with MEDIAMAKER_DEBUG=1): next to the program or in the configuration folder, like the INI file."""
    return os.path.join(HERE if is_dev() else config_dir(), "mediamaker_debug.log")
