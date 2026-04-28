"""Key image rendering for Stream Deck button slots."""

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
    key_size: tuple[int, int] | None = None,
    image_format: str = "JPEG",
) -> bytes:
    """Render an image for a Stream Deck key.

    Parameters
    ----------
    icon
        Optional icon image to render on the key.
    background
        Background colour name.
    key_size
        Key dimensions ``(width, height)``.  Defaults to
        the Stream Deck+ size ``(120, 120)``.
    image_format
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded image bytes ready to send to the device.
    """
    size = key_size or KEY_SIZE
    icon_px = min(size[0], size[1]) * ICON_SIZE // KEY_SIZE[0]

    img = Image.new("RGB", size, background)

    if icon is not None:
        if icon.size != (icon_px, icon_px):
            icon = icon.resize((icon_px, icon_px), Image.Resampling.LANCZOS)

        x_offset = (size[0] - icon_px) // 2
        y_offset = (size[1] - icon_px) // 2

        if icon.mode == "RGBA":
            img.paste(icon, (x_offset, y_offset), icon)
        else:
            img.paste(icon, (x_offset, y_offset))

    return _encode_image(img, image_format)


def render_blank_key(
    key_size: tuple[int, int] | None = None,
    image_format: str = "JPEG",
) -> bytes:
    """Render a blank key image.

    Parameters
    ----------
    key_size : tuple of int, optional
        Key dimensions ``(width, height)``.  Defaults to the
        Stream Deck+ size ``(120, 120)``.
    image_format : str, default="JPEG"
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded blank-key image bytes.
    """
    return render_key_image(key_size=key_size, image_format=image_format)


def _encode_image(
    img: Image.Image, image_format: str = "JPEG", quality: int = 90
) -> bytes:
    """Encode a PIL image in the specified format.

    Parameters
    ----------
    img : PIL.Image.Image
        Image to encode.
    image_format : str, default="JPEG"
        Target format (``"JPEG"`` or ``"BMP"``).
    quality : int, default=90
        JPEG quality (ignored for BMP).

    Returns
    -------
    bytes
        Raw encoded image bytes.
    """
    buf = io.BytesIO()
    fmt = image_format.upper()
    if fmt == "BMP":
        img.save(buf, format="BMP")
    else:
        img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
