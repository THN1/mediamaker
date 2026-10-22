"""Station logo: mask for removelogo, isolation of the logo, detection and search in the movie.

Port of the VB6 functions monochrome() / frmRemoveLogo, logo(), binary(), bin(), ones(),
where_logo() and rewind(). The numerical values (8, 5, 400, 18, 0.2, 25, 20, 100) come from VB6.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Optional

import numpy as np
from PIL import Image

from frames import grab_frame

THRESHOLD = 8        # frmRemoveLogo: brightness from 8 counts as "white" (logo)
EXTRA = 5            # border around the isolated logo in pixels
LINE_SUM = 400       # sum of the bytes of a 1-bit line from which it counts as a "logo line"
BIN_MIN = 18         # bin(): brightness difference of neighbouring pixels from which an edge is counted
MIN_CONF = 0.2       # where_logo(): minimum match


@dataclass
class LogoRef:
    rect: tuple[int, int, int, int]      # left, top, right, bottom (pixels, right/bottom exclusive)
    edges: np.ndarray                    # edge map of the reference logo (bool)
    ones: int                            # number of edges in the reference


# ----------------------------------------------------------------------------- Building blocks
def to_grey(img: np.ndarray) -> np.ndarray:
    """RGB -> 8-bit grey (Rec.709 like FreeImage_ConvertToGreyscale)."""
    r, g, b = (img[..., i].astype(np.float64) for i in range(3))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.5).astype(np.uint8)


def edge_map(grey: np.ndarray, bin_min: int = BIN_MIN) -> np.ndarray:
    """bin(): pixel x is an edge if |grey(x) - grey(x+1)| > bin_min (VB6: 18). The last column stays empty."""
    m = np.zeros(grey.shape, dtype=bool)
    m[:, :-1] = np.abs(grey[:, 1:].astype(int) - grey[:, :-1].astype(int)) > bin_min
    return m


def ones(m1: np.ndarray, m2: np.ndarray) -> int:
    """Number of common edges. As in VB6 the last line is left out."""
    return int((m1[:-1] & m2[:-1]).sum())


# ----------------------------------------------------------------------------- Mask (removelogo)
def make_mask(frame_rgb: np.ndarray, threshold: int = THRESHOLD, blend: float = 0.0) -> np.ndarray:
    """1-bit mask of a (preferably black) picture with a logo: True = logo.

        blend (0..1): blackens a band around the middle of the picture (height = blend * half the picture height upwards
        and downwards) to remove disturbing remains in the middle of the picture (hscBlend in frmRemoveLogo).
    """
    mask = to_grey(frame_rgb) >= threshold
    if blend > 0:
        h = mask.shape[0] // 2
        k = int(blend * h)
        mask[max(0, h - k): h + k + 1, :] = False
    return mask


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fills the black areas that are completely enclosed by white ones. A logo whose symbol is darker than the brightness limit (a
    dark glyph in a bright box) otherwise leaves the symbol out of the mask: ffmpeg's removelogo only replaces white pixels, so the
    symbol would stay visible as a shadow in its own shape. Black areas that reach the edge of the picture stay black."""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return mask.copy()
    top, bottom = max(0, ys.min() - 1), min(mask.shape[0], ys.max() + 2)         # work on the part of the picture around the white
    left, right = max(0, xs.min() - 1), min(mask.shape[1], xs.max() + 2)
    part = mask[top:bottom, left:right]
    outside = np.zeros_like(part)
    outside[0, :], outside[-1, :], outside[:, 0], outside[:, -1] = True, True, True, True
    outside &= ~part                                                              # black pixels at the edge of the part: outside
    while True:                                                                   # the outside spreads over the black pixels
        spread = outside.copy()
        spread[1:] |= outside[:-1]
        spread[:-1] |= outside[1:]
        spread[:, 1:] |= outside[:, :-1]
        spread[:, :-1] |= outside[:, 1:]
        spread &= ~part
        if np.array_equal(spread, outside):
            break
        outside = spread
    result = mask.copy()
    result[top:bottom, left:right] = ~outside                                     # what the outside does not reach is inside
    return result


def grow_mask(mask: np.ndarray, pixels: int) -> np.ndarray:
    """Makes the white areas `pixels` pixels bigger in every direction (square), so that the blurred edge of a logo (anti-aliasing,
    compression) is replaced as well."""
    result = mask.copy()
    for _ in range(max(0, pixels)):
        grown = result.copy()
        grown[1:] |= result[:-1]
        grown[:-1] |= result[1:]
        result = grown
        grown = result.copy()
        grown[:, 1:] |= result[:, :-1]
        grown[:, :-1] |= result[:, 1:]
        result = grown
    return result


def mask_to_png_b64(mask: np.ndarray) -> str:
    """As in VB6 (SubItems(18)): 1-bit PNG as Base64 text without line breaks."""
    buf = io.BytesIO()
    Image.fromarray(mask).save(buf, format="PNG")          # bool array -> mode "1"
    return base64.b64encode(buf.getvalue()).decode("ascii")


def mask_from_png_b64(text: str) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(text))).convert("1"))


# ----------------------------------------------------------------------------- RemoveLogo mask (frmRemoveLogo)
MASK_THRESHOLD = 8                  # brightness from which a pixel belongs to the mask (FreeImage_Threshold(p, 8))
BLEND_MAX = 1800                    # maximum of the slider that blackens the centre of the picture


def monochrome_mask(frame_rgb: np.ndarray, threshold: int = MASK_THRESHOLD) -> np.ndarray:
    """Black/white picture of a frame: True (white) where the brightness is at least `threshold`, False (black) elsewhere."""
    return to_grey(frame_rgb) >= threshold


def blacken_center(mask: np.ndarray, value: int, maximum: int = BLEND_MAX) -> np.ndarray:
    """Blackens a band around the middle line of the picture (to get rid of the title, the director's name, the list of actors ... in a
    frame that should only contain the logo): the band is 2 * value * (height // 2) // maximum + 1 lines high; value 0 leaves the mask as it is."""
    result = mask.copy()
    if value <= 0:
        return result
    height = mask.shape[0]
    middle = height // 2
    k = value * middle // maximum
    # VB6 counts the lines from the bottom edge (FreeImage), the array from the top edge
    first, last = max(0, height - 1 - (middle + k)), min(height - 1, height - 1 - (middle - k))
    result[first:last + 1] = False
    return result


def mask_to_png_b64(mask: np.ndarray) -> str:
    """The mask as a 1-bit PNG, base64 encoded without line breaks (the form stored in the parameters of a segment)."""
    buffer = io.BytesIO()
    Image.fromarray((mask * 255).astype(np.uint8)).convert("1").save(buffer, "PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# ----------------------------------------------------------------------------- Isolating the logo
def isolate_logo(mask: np.ndarray, extra: int = EXTRA, bin_min: int = BIN_MIN) -> Optional[LogoRef]:
    """Looks for the logo in the upper quarter of the mask and forms the reference logo (monochrome()).

        Lines count as a "logo line" if the sum of their bytes (1 byte = 8 pixels, left pixel = highest
        bit) is greater than 400. The first contiguous block of such lines from the top is found.
    """
    h, w = mask.shape
    packed = np.packbits(mask, axis=1)
    sums = packed.sum(axis=1, dtype=np.int64)

    # 1st loop: upper left corner (h0 = top line in FreeImage counting from the bottom, w0 = left byte * 8)
    h0 = w0 = 0
    for y in range(h - 1, h * 3 // 4 - 1, -1):
        r = h - 1 - y
        if sums[r] > LINE_SUM:
            for x in np.flatnonzero(packed[r] > 7):
                if h0 == 0:
                    h0 = y
                if w0 == 0 or w0 > x * 8:
                    w0 = int(x) * 8
        elif w0 * h0 > 0:
            break
    if w0 * h0 == 0:
        return None

    # 2nd loop: lower right corner, at most 50 lines below h0
    w1 = 0
    for y in range(h0, h0 - 51, -1):
        r = h - 1 - y
        if r < 0 or r >= h:
            break
        if sums[r] > LINE_SUM:
            for x in range(packed.shape[1] - 1, w0 // 8 - 1, -1):
                if packed[r, x] > 7 and (w1 == 0 or w1 < x * 8):
                    w1 = x * 8
        else:
            h1 = y
            left, top = max(0, w0 - extra), max(0, h - h0 - extra)
            right, bottom = min(w, w1 + extra), min(h, h - h1 + extra)
            crop = (mask[top:bottom, left:right] * 255).astype(np.uint8)
            edges = edge_map(crop, bin_min)
            return LogoRef((left, top, right, bottom), edges, ones(edges, edges))
    return None


# ----------------------------------------------------------------------------- reference from rectangle (delogo)
def absolute_rect(rel: str, width: int, height: int) -> tuple[int, int, int, int]:
    """SubItems(18) in delogo mode: 'x y width height' as fractions of the picture -> pixels (absolute())."""
    x, y, bw, bh = (float(t.replace(",", ".")) for t in rel.split(" ")[:4])
    return round(width * x), round(height * y), round(width * (x + bw)), round(height * (y + bh))


def ref_from_rect(frame_rgb: np.ndarray, rect: tuple[int, int, int, int], bin_min: int = BIN_MIN) -> LogoRef:
    """cmdLogo_Click without PNG mask: reference from the rectangle of the current frame."""
    left, top, right, bottom = rect
    edges = edge_map(to_grey(frame_rgb[top:bottom, left:right]), bin_min)
    return LogoRef(rect, edges, ones(edges, edges))


# ----------------------------------------------------------------------------- Detection
def logo_confidence(frame_rgb: np.ndarray, ref: LogoRef, bin_min: int = BIN_MIN) -> float:
    """Share of the reference edges that also occur in the logo rectangle of this frame (0..1)."""
    left, top, right, bottom = ref.rect
    edges = edge_map(to_grey(frame_rgb[top:bottom, left:right]), bin_min)
    return ones(edges, ref.edges) / ref.ones if ref.ones else 0.0


def confidence_at(path: str, frame: int, fps: Fraction, ref: LogoRef, opts: dict, ffmpeg: str = "ffmpeg") -> float:
    return logo_confidence(grab_frame(path, frame, fps, int(opts.get("floor", 2)), ffmpeg), ref,
                           int(opts.get("logo_edge", BIN_MIN)))


INITIAL_REWIND = 25        # frames that are gone back first (VB6); the reference colour lies there
DEFAULT_MAX_REWIND = 45    # frames in total (VB6: 25 + up to 20); 1.8 seconds at 25 FPS
COARSE_STEP = 5            # when rewinding far, the search first uses steps of 5 frames


def rewind(pos: int, bottom_line_avg: Callable[[int], tuple[int, int, int]], max_back: int = DEFAULT_MAX_REWIND) -> int:
    """Goes back from the found start of the logo and looks for the scene change (rewind()).

        The reference is the mean of the bottom picture line 25 frames before `pos` (in VB6 FreeImage scanline 0); then it goes back up to
        `max_back` frames in total, until the colour changes by more than 100 (VB6: at most 20 further frames,
        frame by frame). For longer distances the search first uses steps of 5 frames and then refines frame by frame,
        so that rewinding stays fast even over several seconds.
    """
    if max_back <= 0:
        return pos
    pos -= min(INITIAL_REWIND, max_back)
    steps = max_back - INITIAL_REWIND
    if steps <= 0:
        return pos
    ref = bottom_line_avg(pos)

    def changed(p: int) -> bool:
        return sum(abs(a - b) for a, b in zip(bottom_line_avg(p), ref)) > 100

    if steps <= 20:                                  # as in VB6: frame by frame
        for _ in range(steps):
            pos -= 1
            if changed(pos):
                break
        return pos + 1
    moved = 0
    while moved < steps:
        n = min(COARSE_STEP, steps - moved)
        if changed(pos - n):                         # the change lies in these n frames: look frame by frame
            for _ in range(n):
                pos -= 1
                if changed(pos):
                    break
            return pos + 1
        pos -= n
        moved += n
    return pos + 1


def bottom_line_average(path: str, frame: int, fps: Fraction, opts: dict, ffmpeg: str = "ffmpeg") -> tuple[int, int, int]:
    img = grab_frame(path, max(0, frame), fps, int(opts.get("floor", 2)), ffmpeg)
    return tuple(int(v) for v in img[-1].astype(np.int64).sum(axis=0) // img.shape[1])


def where_logo(conf_of: Callable[[int], float], pos: int, last: int, equal: bool, stepping: int,
               rewind_fn: Optional[Callable[[int], int]] = None, min_conf: float = MIN_CONF) -> int:
    """Starting at frame `pos`, searches for the next frame WITH logo (equal=True, then rewind) or WITHOUT logo (equal=False).

        VB6 calls: 'end of commercial' = (True, 1000), 'next commercial' = (False, 6000).
    """
    while stepping > 0:
        if pos + stepping >= last:
            stepping = (stepping + 8) // 10          # end of file: only reduce the step width
            continue
        pos += stepping
        c = conf_of(pos)
        if (equal and c > min_conf) or (not equal and c < min_conf):
            pos -= stepping
            stepping = (stepping + 8) // 10
    if equal:
        return rewind_fn(pos) if rewind_fn else pos
    return pos + 1
