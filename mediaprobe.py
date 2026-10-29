"""Robust media analysis for TV recordings (.ts) based on ffprobe.

Replaces the VB6 function minfo() (MediaInfo). Idea: the number of frames is no longer
guessed from duration * FPS but counted from the packets of the video stream
(fast, without decoding). All values carry an indication of their origin so that the
program can recognise and show uncertain values.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

# common TV frame rates; only used to check FPS values for plausibility
KNOWN_FPS = [Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001),
             Fraction(30), Fraction(50), Fraction(60000, 1001), Fraction(60)]


class ProbeError(Exception):
    pass


@dataclass
class VideoInfo:
    index: int
    codec: str
    width: int
    height: int
    fps: Fraction
    fps_source: str                 # 'avg_frame_rate' | 'r_frame_rate' | 'fallback'
    frames: int
    frames_source: str              # 'nb_frames' | 'packets' | 'estimated'  (packets = from the first keyframe)
    duration: float                 # seconds
    bitrate: int                    # bit/s, 0 = unknown
    start_time: float = 0.0
    interlaced: bool = False
    leading_packets: int = 0         # undecodable packets at the beginning (not counted)
    first_frame_offset: float = 0.0  # time of the first decodable frame from the video start (= ffmpeg time 0 when cutting)


@dataclass
class AudioInfo:
    index: int                      # absolute stream index
    codec: str
    channels: int
    sample_rate: int
    bitrate: int                    # bit/s, 0 = unknown
    language: str = ""


@dataclass
class MediaInfo:
    path: str
    format_name: str
    duration: float
    size: int
    bitrate: int
    video: VideoInfo
    audio: list[AudioInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _run_ffprobe(args: list[str], ffprobe: str) -> dict:
    cmd = [ffprobe, "-v", "error", "-print_format", "json", *args]
    try:
        res = subprocess.run(cmd, capture_output=True, check=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise ProbeError(f"ffprobe not found: {ffprobe}") from e
    except subprocess.CalledProcessError as e:
        raise ProbeError(e.stderr.decode(errors="replace").strip() or "ffprobe failed") from e
    return json.loads(res.stdout or b"{}")


def _int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _fraction(v: Optional[str]) -> Optional[Fraction]:
    """'25/1' -> Fraction(25); '0/0' or nonsense -> None."""
    if not v or "/" not in str(v):
        try:
            f = Fraction(str(v)) if v else None
        except (ValueError, ZeroDivisionError):
            return None
    else:
        try:
            f = Fraction(*[int(x) for x in str(v).split("/")])
        except (ValueError, ZeroDivisionError):
            return None
    return f if f and f > 0 else None


def _plausible(f: Optional[Fraction]) -> bool:
    return f is not None and any(abs(f - k) / k < Fraction(1, 200) for k in KNOWN_FPS)


def _pick_fps(stream: dict, interlaced: bool) -> tuple[Fraction, str]:
    avg = _fraction(stream.get("avg_frame_rate"))
    r = _fraction(stream.get("r_frame_rate"))
    # r_frame_rate often reports the field rate (50 instead of 25) for interlaced TS
    if _plausible(avg):
        return avg, "avg_frame_rate"
    if _plausible(r):
        return (r / 2 if interlaced and r >= 50 else r), "r_frame_rate"
    if avg or r:
        return (avg or r), "r_frame_rate"
    return Fraction(25), "fallback"


def _ratio(text) -> Optional[float]:
    """"16:9" -> 1.777...; None for "0:1", "N/A" and anything else that is not a usable ratio."""
    try:
        a, b = str(text).split(":")
        a, b = float(a), float(b)
    except ValueError:
        return None
    return a / b if a > 0 and b > 0 else None


def aspect_from_stream(width: int, height: int, sar=None, dar=None) -> float:
    """Proportions (width / height) of the picture as a video player shows it: the display aspect ratio of the stream if it has one,
    otherwise the pixel proportions times the sample aspect ratio, otherwise the pixel proportions."""
    shape = width / height if width > 0 and height > 0 else 1.0
    display = _ratio(dar)
    if display:
        return display
    pixel = _ratio(sar)
    return shape * pixel if pixel else shape


def format_duration(path: str, ffprobe: str = "ffprobe") -> float:
    """The duration of the file as the container gives it (seconds; fast, nothing is counted). This is the length by which the concat demuxer moves the next file."""
    data = _run_ffprobe(["-show_entries", "format=duration", path], ffprobe)
    return _float(data.get("format", {}).get("duration"))


def subtitle_codecs(path: str, ffprobe: str = "ffprobe") -> list:
    """The codec names of the subtitle tracks of the file, in their order (track 1 of the option subtitle is the first one). Fast: only the stream list is read."""
    data = _run_ffprobe(["-select_streams", "s", "-show_entries", "stream=codec_name", path], ffprobe)
    return [str(s.get("codec_name", "")) for s in data.get("streams", [])]


def display_aspect(path: str, ffprobe: str = "ffprobe") -> Optional[float]:
    """Proportions (width / height) of the first video stream as a player shows it (see aspect_from_stream); None if unknown."""
    try:
        data = _run_ffprobe(["-select_streams", "v:0", "-show_entries", "stream=width,height,sample_aspect_ratio,display_aspect_ratio",
                             "-of", "json", path], ffprobe)
        stream = data["streams"][0]
        return aspect_from_stream(int(stream["width"]), int(stream["height"]), stream.get("sample_aspect_ratio"), stream.get("display_aspect_ratio"))
    except (ProbeError, KeyError, IndexError, ValueError, TypeError, OSError):
        return None


def count_video_packets(path: str, ffprobe: str = "ffprobe", on_start=None) -> tuple[int, int, float]:
    """Counts the decodable video frames via the packets (reads the whole file, but does not decode).

        Returns: (usable packets, discarded packets, PTS of the first keyframe).
        Not usable are (1) packets before the first keyframe, when the recording begins in the middle of a group
        of pictures, and (2) leading B-frames directly after the first keyframe whose time lies BEFORE the keyframe
        and which refer to a missing preceding frame. Players and cutting programs do not show
        these packets. If there is no keyframe at all, all packets are counted.

        on_start(process) receives the started ffprobe process so that the caller can terminate it if needed
        (counting takes minutes for long recordings on a network drive).
    """
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time,flags",
           "-of", "csv=p=0", path]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as e:
        raise ProbeError(f"ffprobe not found: {ffprobe}") from e
    if on_start:
        on_start(proc)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise ProbeError(err.strip() or "ffprobe failed or was cancelled")
    rows = [line.split(",") for line in out.splitlines() if line.strip()]
    first_key = next((i for i, r in enumerate(rows) if len(r) > 1 and "K" in r[1]), None)
    if first_key is None:
        return len(rows), 0, 0.0
    key_pts = _float(rows[first_key][0])
    usable = sum(1 for r in rows[first_key:] if _float(r[0], key_pts) >= key_pts - 1e-6)
    return usable, len(rows) - usable, key_pts


def decoded_first_pts(path: str, ffprobe: str = "ffprobe", packets: int = 300) -> Optional[float]:
    """Timestamp (seconds) of the first video frame that the DECODER delivers, or None. The decoder drops frames it cannot decode (B-frames
    in front of the first keyframe that refer to the previous GOP, frames before a recovery point ...); what it delivers is also what the
    thumbnails and the cut result contain. Only the first packets are read and decoded (fast, also on a network drive)."""
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+#{packets}", "-show_entries", "frame=pts_time",
           "-of", "csv=p=0", path]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, text=True, stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    times = [_float(line.split(",")[0], -1.0) for line in out.splitlines() if line.strip()]
    times = [t for t in times if t >= 0]
    return min(times) if times else None


def first_frame_number(path: str, fps, ffprobe: str = "ffprobe", packets: int = 300) -> int:
    """Number of the first decodable video frame, counted from the container start (like the frame numbers in the program).

        If in a TV recording the sound starts earlier than the video, the first frame does not have the number 0. Only the first packets
        are read (fast, also on a network drive). The first frame is the first one the decoder delivers (decoded_first_pts); that is what
        the thumbnails and the cut result contain. If the decoder yields nothing, the first keyframe packet applies (B-frames before it are
        not decodable), and without a keyframe among the first packets the start of the video stream.
    """
    from math import floor
    from ffmpeg_cmd import stream_times_of
    container, video = stream_times_of(path)
    pts = decoded_first_pts(path, ffprobe, packets)
    if pts is None:
        cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+#{packets}", "-show_entries",
               "packet=pts_time,flags", "-of", "csv=p=0", path]
        try:
            out = subprocess.run(cmd, capture_output=True, check=True, text=True, stdin=subprocess.DEVNULL).stdout
        except (OSError, subprocess.CalledProcessError):
            out = ""
        pts = video
        for line in out.splitlines():
            parts = line.split(",")
            if len(parts) > 1 and "K" in parts[1] and _float(parts[0], -1.0) >= 0:
                pts = _float(parts[0])
                break
    return max(0, floor((float(pts) - float(container)) * float(fps) + 1e-3))


def probe(path: str, ffprobe: str = "ffprobe", exact_frames: bool = True) -> MediaInfo:
    data = _run_ffprobe(["-show_format", "-show_streams", path], ffprobe)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    warnings: list[str] = []

    vstreams = [s for s in streams if s.get("codec_type") == "video"
                and not s.get("disposition", {}).get("attached_pic")]
    if not vstreams:
        raise ProbeError("No video stream found.")
    v = vstreams[0]

    interlaced = v.get("field_order", "progressive") not in ("progressive", "unknown", "")
    fps, fps_src = _pick_fps(v, interlaced)
    if fps_src == "fallback":
        warnings.append("Frame rate not recognisable, 25 fps assumed.")

    fmt_dur = _float(fmt.get("duration"))
    v_dur = _float(v.get("duration")) or fmt_dur
    if fmt_dur and v_dur and abs(fmt_dur - v_dur) > 2:
        warnings.append(f"Duration differs (container {fmt_dur:.1f}s, video {v_dur:.1f}s).")
    duration = v_dur or fmt_dur
    estimated = round(duration * float(fps)) if duration else 0

    # --- number of frames: metadata > packet count from the first keyframe > estimate ---------
    frames, frames_src = _int(v.get("nb_frames")), "nb_frames"
    leading, key_pts = 0, 0.0
    if exact_frames and frames <= 0:
        frames, leading, key_pts = count_video_packets(path, ffprobe)
        frames_src = "packets"
    if frames <= 0:
        frames, frames_src = estimated, "estimated"
        warnings.append("Number of frames only estimated from duration*FPS.")
    elif estimated and abs(frames + leading - estimated) > max(5, 0.02 * estimated):
        warnings.append(f"Number of frames ({frames + leading}) differs significantly from duration*FPS ({estimated}).")
    first_offset = max(0.0, key_pts - _float(v.get("start_time"))) if key_pts else 0.0
    if leading:
        warnings.append(f"{leading} video packets at the beginning (before the first keyframe or leading B-frames) are "
                        f"not decodable and not counted; the first frame appears at "
                        f"{first_offset:.2f} s (ffmpeg time).")

    # --- Audio -----------------------------------------------------------------
    audio = [AudioInfo(index=s["index"], codec=s.get("codec_name", ""),
                       channels=_int(s.get("channels")), sample_rate=_int(s.get("sample_rate")),
                       bitrate=_int(s.get("bit_rate")),
                       language=s.get("tags", {}).get("language", ""))
             for s in streams if s.get("codec_type") == "audio"]

    # --- video bit rate: stream > container minus audio, minus overhead ------------
    v_br = _int(v.get("bit_rate"))
    fmt_br = _int(fmt.get("bit_rate"))
    if not v_br and fmt_br:
        v_br = max(0, int(0.95 * (fmt_br - sum(a.bitrate for a in audio))))
        warnings.append("Video bit rate derived from the container bit rate.")

    video = VideoInfo(index=v["index"], codec=v.get("codec_name", ""),
                      width=_int(v.get("width")), height=_int(v.get("height")),
                      fps=fps, fps_source=fps_src, frames=frames, frames_source=frames_src,
                      duration=duration, bitrate=v_br,
                      start_time=_float(v.get("start_time")), interlaced=interlaced,
                      leading_packets=leading, first_frame_offset=first_offset)
    return MediaInfo(path=path, format_name=fmt.get("format_name", ""), duration=fmt_dur or duration,
                     size=_int(fmt.get("size")), bitrate=fmt_br, video=video,
                     audio=audio, warnings=warnings)


if __name__ == "__main__":
    import sys
    info = probe(sys.argv[1])
    print(json.dumps(info, default=lambda o: float(o) if isinstance(o, Fraction) else o.__dict__,
                     indent=2, ensure_ascii=False))
