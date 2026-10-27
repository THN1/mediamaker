"""Calculations for the cropping of a segment (VB6: frmCrop, the check box 16:9)."""
from __future__ import annotations

from fractions import Fraction
from typing import Optional

RATIO_16_9 = Fraction(16, 9)


def sample_aspect(width: int, height: int, display_ratio: Optional[float]) -> Fraction:
    """Sample aspect ratio of the pixels (width : height of one pixel) from the display ratio of the whole picture (as a player shows it);
    1 if it is not known. 720x576 shown as 16:9 gives 64/45."""
    if not display_ratio or width <= 0 or height <= 0:
        return Fraction(1)
    return (Fraction(display_ratio).limit_denominator(1000) * height / width).limit_denominator(1000)


def ratio_side(width: int, height: int, sar: Fraction, top: int, bottom: int, ratio: Fraction = RATIO_16_9) -> int:
    """How many pixels to crop at the left AND at the right, so that the picture that is left after cutting `top` and `bottom` is shown in the
    proportions `ratio` (VB6: (top + bottom) * 8 \\ 9, which is this for square pixels and a 16:9 picture). Never below 0: a picture that is
    already too high for the ratio cannot be made wider by cropping at the sides."""
    side = (Fraction(width) - Fraction(height - top - bottom) * ratio / Fraction(sar)) / 2
    return max(0, round(side))


def valid(width: int, height: int, top: int, bottom: int, left: int, right: int) -> bool:
    """Is something left of the picture after cropping?"""
    return min(top, bottom, left, right) >= 0 and top + bottom < height and left + right < width
