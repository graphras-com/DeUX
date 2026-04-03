"""Key image rendering for Stream Deck+ button slots."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from .fonts import get_font
from .metrics import ICON_PADDING, ICON_SIZE, KEY_SIZE


def render_key_image(
    icon: Image.Image | None = None,
    label: str | None = None,
    background: str = "black",
) -> bytes:
    """Render a JPEG image for a Stream Deck+ key."""
    img = Image.new("RGB", KEY_SIZE, background)

    if icon is not None:
        if icon.size != (ICON_SIZE, ICON_SIZE):
            icon = icon.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)

        y_offset = 8 if label else ICON_PADDING
        x_offset = ICON_PADDING

        if icon.mode == "RGBA":
            img.paste(icon, (x_offset, y_offset), icon)
        else:
            img.paste(icon, (x_offset, y_offset))

    if label:
        draw = ImageDraw.Draw(img)
        font = get_font()
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (KEY_SIZE[0] - text_width) // 2
        text_y = KEY_SIZE[1] - 24
        draw.text((text_x, text_y), label, fill="white", font=font)

    return _encode_jpeg(img)


def render_blank_key() -> bytes:
    """Render a blank key image."""
    return render_key_image()


def _encode_jpeg(img: Image.Image, quality: int = 90) -> bytes:
    """Encode a PIL image as JPEG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
