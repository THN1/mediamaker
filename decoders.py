"""Is there a decoder for the video codec of a file? (Qt-free.) Some distributions ship an ffmpeg without the H.264 / H.265 decoders of its own (openSUSE: only `libopenh264`, which cannot
decode many streams, VLC has the same limit): the file then shows no picture and no thumbnails, and nothing says why. The program checks it when a file is opened."""
from __future__ import annotations

import subprocess
from typing import Optional

from mediaprobe import distro_ids

CHECKED = {"h264": "H.264", "hevc": "H.265 (HEVC)"}              # codec name of ffprobe: name for the message
_cache: dict = {}


def decoder_names(ffmpeg: str = "ffmpeg", run=subprocess.run) -> Optional[set]:
    """The names of all decoders of ffmpeg (from `ffmpeg -decoders`), None if that cannot be asked. Asked once per program."""
    if ffmpeg not in _cache:
        try:
            res = run([ffmpeg, "-hide_banner", "-decoders"], capture_output=True, stdin=subprocess.DEVNULL, timeout=20)
            names = set()
            for line in res.stdout.decode(errors="replace").splitlines():
                parts = line.split()
                if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS" and parts[1] != "=":      # " V....D h264  H.264 / AVC ..."
                    names.add(parts[1])
            _cache[ffmpeg] = names or None
        except (OSError, subprocess.SubprocessError):
            _cache[ffmpeg] = None
    return _cache[ffmpeg]


def how_to_install(os_release: str = "/etc/os-release") -> str:
    ids = distro_ids(os_release)
    if ids & {"opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse", "sles"}:
        return "openSUSE: sudo zypper install opi, then: opi codecs (sets up the Packman repository and installs the full FFmpeg and VLC codecs)"
    if ids & {"fedora", "rhel", "centos"}:
        return "Fedora: set up RPM Fusion, then: sudo dnf swap ffmpeg-free ffmpeg --allowerasing (and install the VLC codecs of RPM Fusion)"
    return "Please install an FFmpeg and a VLC with full codec support (H.264 / H.265) with the package manager of your distribution"


def decoder_problem(codec: str, names: Optional[set] = None, os_release: str = "/etc/os-release") -> Optional[str]:
    """A text if the video codec `codec` (ffprobe's name) has no decoder of its own in ffmpeg, otherwise None (also when that is not known)."""
    label = CHECKED.get((codec or "").lower())
    if label is None:
        return None
    names = decoder_names() if names is None else names
    if not names or codec.lower() in names:
        return None
    only = " (only libopenh264, which cannot decode many streams)" if codec.lower() == "h264" and "libopenh264" in names else ""
    return (f"The ffmpeg of this computer has no {label} decoder of its own{only}. This file will show no picture in the preview and no thumbnails, and the saved "
            f"file will not be right.\n{how_to_install(os_release)}")
