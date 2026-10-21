"""Bilder aus .frx-Dateien (Ressourcen zu VB6-Formularen) lesen.

Aufbau eines Bildeintrags: DWORD Länge | "lt" 00 00 | DWORD Datenlänge | Daten (Symbol, Bitmap, GIF, JPEG ...).
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
    """Zeichenkette (Text-Eigenschaft eines Textfeldes u. a.): 0xFF, WORD Länge, Zeichen; kurze Texte: 1 Byte Länge."""
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
    """Listeneinträge einer ComboBox/ListBox (List) bzw. deren ItemData: WORD Anzahl, WORD größte Länge,
    dann je Eintrag WORD Länge + Zeichen."""
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
