"""Read pictures from .frx files (resources belonging to VB6 forms).

Structure of a picture entry: DWORD length | "lt" 00 00 | DWORD data length | data (icon, bitmap, GIF, JPEG ...).
"""
import io
import struct
from typing import Optional

from PIL import Image


def read_picture(frx_path: str, offset: int) -> Optional[bytes]:
    data = open(frx_path, "rb").read()
    if offset + 12 > len(data) or data[offset + 4: offset + 8] != b"lt\x00\x00":
        return None
    (length,) = struct.unpack_from("<I", data, offset + 8)
    return data[offset + 12: offset + 12 + length]


def picture_to_png(raw: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw))
    img.load()
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG")
    return buf.getvalue()


def read_text(frx_path: str, offset: int) -> Optional[str]:
    """String (Text property of a text box among others): 0xFF, WORD length, characters; short texts: 1 byte length."""
    data = open(frx_path, "rb").read()
    if offset >= len(data):
        return None
    if data[offset] == 0xFF:
        (n,) = struct.unpack_from("<H", data, offset + 1)
        raw = data[offset + 3: offset + 3 + n]
    else:
        n = data[offset]
        raw = data[offset + 1: offset + 1 + n]
    return raw.decode("cp1252", errors="replace")


def read_list(frx_path: str, offset: int) -> Optional[list]:
    """List entries of a ComboBox/ListBox (List) or their ItemData: WORD count, WORD greatest length,
        then per entry WORD length + characters."""
    data = open(frx_path, "rb").read()
    if offset + 4 > len(data):
        return None
    (count,) = struct.unpack_from("<H", data, offset)
    pos, out = offset + 4, []
    for _ in range(count):
        (n,) = struct.unpack_from("<H", data, pos)
        out.append(data[pos + 2: pos + 2 + n].decode("cp1252", errors="replace"))
        pos += 2 + n
    return out
