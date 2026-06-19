"""
Unicode-capable text drawing for OpenCV frames.

cv2.putText only ships Hershey vector fonts (ASCII-only), so glyphs like
θ ω α γ ² ° render as '?'. This module renders text with a TrueType font
(Pillow) instead, while keeping cv2.putText's semantics:

  - `org` is the bottom-left baseline point (same as cv2)
  - `color` is BGR (same as cv2)
  - `font_scale` maps to Hershey-equivalent pixel height (≈ scale * 24)

Only the glyph's bounding box is converted to/from PIL per call, so it stays
cheap enough for real-time dashboards (no full-canvas round trip).
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# DejaVu Sans is bundled with matplotlib and covers Greek + super/subscripts
# + degree sign on every platform, so we don't depend on Windows font paths.
try:
    import matplotlib
    _FONT_PATH = os.path.join(
        os.path.dirname(matplotlib.__file__),
        "mpl-data", "fonts", "ttf", "DejaVuSans.ttf",
    )
    if not os.path.exists(_FONT_PATH):
        _FONT_PATH = None
except Exception:
    _FONT_PATH = None

# Empirically, PIL pixel size ≈ cv2 fontScale * 24 matches Hershey glyph height,
# so existing layouts tuned for cv2.putText stay aligned.
_SCALE_TO_PX = 24.0

_font_cache: dict[int, "ImageFont.FreeTypeFont"] = {}


def _get_font(font_scale: float) -> "ImageFont.FreeTypeFont":
    px = max(8, int(round(font_scale * _SCALE_TO_PX)))
    font = _font_cache.get(px)
    if font is None:
        if _FONT_PATH:
            font = ImageFont.truetype(_FONT_PATH, px)
        else:
            font = ImageFont.load_default()
        _font_cache[px] = font
    return font


def put_text(
    img: np.ndarray,
    text: str,
    org: tuple,
    font_scale: float = 0.5,
    color: tuple = (220, 220, 220),
    thickness: int = 1,
) -> np.ndarray:
    """
    Drop-in Unicode replacement for cv2.putText (LINE_AA, Hershey-like sizing).

    Args mirror cv2.putText: `org` = bottom-left baseline, `color` = BGR.
    Renders in place into `img` and also returns it.
    """
    if not text:
        return img

    font = _get_font(font_scale)
    x, y = int(org[0]), int(org[1])
    stroke = max(0, thickness - 1)

    # Ink box relative to the (x, y) left-baseline anchor.
    l, t, r, b = font.getbbox(text, anchor="ls", stroke_width=stroke)
    pad = 2 + stroke
    x0 = max(0, x + l - pad)
    y0 = max(0, y + t - pad)
    x1 = min(img.shape[1], x + r + pad)
    y1 = min(img.shape[0], y + b + pad)
    if x1 <= x0 or y1 <= y0:
        return img

    # Convert only the glyph's region (BGR -> RGB), draw, write back.
    patch = img[y0:y1, x0:x1]
    pil = Image.fromarray(patch[:, :, ::-1])
    draw = ImageDraw.Draw(pil)
    rgb = (int(color[2]), int(color[1]), int(color[0]))
    draw.text(
        (x - x0, y - y0), text, font=font, fill=rgb,
        anchor="ls", stroke_width=stroke, stroke_fill=rgb,
    )
    patch[:, :, :] = np.asarray(pil)[:, :, ::-1]
    return img
