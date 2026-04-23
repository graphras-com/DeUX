"""Info screen rendering for devices with a non-touch display (e.g. Neo)."""

from __future__ import annotations

import io

from PIL import Image


def render_info_screen(
    image: Image.Image | None,
    width: int,
    height: int,
    background: str = "black",
    image_format: str = "JPEG",
) -> bytes:
    """Render an info screen image.

    Args:
        image: Optional PIL Image to display. If ``None``, a blank
            black screen is rendered.
        width: Screen width in pixels.
        height: Screen height in pixels.
        background: Background colour.
        image_format: Encoding format (``"JPEG"`` or ``"BMP"``).

    Returns:
        Encoded image bytes.
    """
    canvas = Image.new("RGB", (width, height), background)

    if image is not None:
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        if image.mode == "RGBA":
            canvas.paste(image, (0, 0), image)
        else:
            canvas.paste(image, (0, 0))

    buf = io.BytesIO()
    fmt = image_format.upper()
    if fmt == "BMP":
        canvas.save(buf, format="BMP")
    else:
        canvas.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
