"""Key image rendering for Stream Deck+ button slots."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from .debug_grid import draw_key_grid
from .fonts import get_font
from .metrics import (
    ICON_PADDING,
    ICON_SIZE,
    KEY_MARGIN_BOTTOM,
    KEY_MARGIN_LEFT,
    KEY_MARGIN_RIGHT,
    KEY_MARGIN_TOP,
    KEY_SIZE,
    KEY_USABLE_HEIGHT,
    KEY_USABLE_WIDTH,
)


def render_key_image(
    icon: Image.Image | None = None,
    label: str | None = None,
    background: str = "black",
    debug_grid: bool = False,
) -> bytes:
    """Render a JPEG image for a Stream Deck+ key.

    Content is placed within the usable area defined by the key
    margins (``KEY_MARGIN_TOP/RIGHT/BOTTOM/LEFT``).  The full
    image is still ``KEY_SIZE`` (120x120).

    Args:
        icon: Optional icon image to render on the key.
        label: Optional text label below the icon.
        background: Background colour name.
        debug_grid: When ``True``, overlay a 4x4 alignment grid.
    """
    img = Image.new("RGB", KEY_SIZE, background)

    if icon is not None:
        if icon.size != (ICON_SIZE, ICON_SIZE):
            icon = icon.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)

        x_offset = KEY_MARGIN_LEFT + ICON_PADDING
        if label:
            y_offset = KEY_MARGIN_TOP + 1
        else:
            y_offset = KEY_MARGIN_TOP + ICON_PADDING

        if icon.mode == "RGBA":
            img.paste(icon, (x_offset, y_offset), icon)
        else:
            img.paste(icon, (x_offset, y_offset))

    if label:
        draw = ImageDraw.Draw(img)
        font = get_font()
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = KEY_MARGIN_LEFT + (KEY_USABLE_WIDTH - text_width) // 2
        text_y = KEY_SIZE[1] - KEY_MARGIN_BOTTOM - 17
        draw.text((text_x, text_y), label, fill="white", font=font)

    if debug_grid:
        img = draw_key_grid(img)

    return _encode_jpeg(img)


def render_blank_key(debug_grid: bool = False) -> bytes:
    """Render a blank key image."""
    return render_key_image(debug_grid=debug_grid)


def _encode_jpeg(img: Image.Image, quality: int = 90) -> bytes:
    """Encode a PIL image as JPEG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
