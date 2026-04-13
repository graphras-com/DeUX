"""Key image rendering for Stream Deck+ button slots."""

from __future__ import annotations

import io

from PIL import Image

from .metrics import (
    ICON_SIZE,
    KEY_SIZE,
)


def render_key_image(
    icon: Image.Image | None = None,
    background: str = "black",
) -> bytes:
    """Render a JPEG image for a Stream Deck+ key.

    Args:
        icon: Optional icon image to render on the key.
        background: Background colour name.
    """
    img = Image.new("RGB", KEY_SIZE, background)

    if icon is not None:
        if icon.size != (ICON_SIZE, ICON_SIZE):
            icon = icon.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)

        # Centre icon on the key
        x_offset = (KEY_SIZE[0] - ICON_SIZE) // 2
        y_offset = (KEY_SIZE[1] - ICON_SIZE) // 2

        if icon.mode == "RGBA":
            img.paste(icon, (x_offset, y_offset), icon)
        else:
            img.paste(icon, (x_offset, y_offset))

    return _encode_jpeg(img)


def render_blank_key() -> bytes:
    """Render a blank key image."""
    return render_key_image()


def _encode_jpeg(img: Image.Image, quality: int = 90) -> bytes:
    """Encode a PIL image as JPEG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
