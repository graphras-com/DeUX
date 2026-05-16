"""Key image rendering for Stream Deck button slots."""

from __future__ import annotations

import io

from PIL import Image


def render_key_image(
    key_size: tuple[int, int],
    icon: Image.Image | None = None,
    background: str = "black",
    image_format: str = "JPEG",
) -> bytes:
    """Render an image for a Stream Deck key.

    The icon (if any) is resized to fill the entire key, edge-to-edge —
    the library does not impose margins or padding. Callers that want
    spacing should bake it into the source icon.

    Parameters
    ----------
    key_size
        Key dimensions ``(width, height)`` in pixels.
    icon
        Optional icon image to render on the key. Resized to ``key_size``
        if it does not already match.
    background
        Background colour name (used when *icon* is ``None`` or has alpha).
    image_format
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded image bytes ready to send to the device.
    """
    img = Image.new("RGB", key_size, background)

    if icon is not None:
        if icon.size != key_size:
            icon = icon.resize(key_size, Image.Resampling.LANCZOS)

        if icon.mode == "RGBA":
            img.paste(icon, (0, 0), icon)
        else:
            img.paste(icon, (0, 0))

    return _encode_image(img, image_format)


def render_blank_key(
    key_size: tuple[int, int],
    image_format: str = "JPEG",
) -> bytes:
    """Render a blank key image at the given size.

    Parameters
    ----------
    key_size
        Key dimensions ``(width, height)`` in pixels.
    image_format
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
