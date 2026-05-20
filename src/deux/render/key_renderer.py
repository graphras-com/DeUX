"""Key image rendering for Stream Deck button slots.

Uses Pillow for all image compositing and encoding operations.
"""

from __future__ import annotations

import io

from PIL import Image


def render_key_image(
    key_size: tuple[int, int],
    icon: bytes | Image.Image | None = None,
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
        Optional icon: encoded image bytes (PNG/JPEG) or a
        ``PIL.Image.Image``. Resized to ``key_size`` if it does not
        already match.
    background
        Background colour name (used when *icon* is ``None`` or has alpha).
    image_format
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded image bytes ready to send to the device.
    """
    from .touch_renderer import _parse_color

    key_w, key_h = key_size
    r, g, b = _parse_color(background)
    img = Image.new("RGB", (key_w, key_h), (r, g, b))

    if icon is not None:
        icon_img: Image.Image
        if isinstance(icon, bytes):
            icon_img = Image.open(io.BytesIO(icon))
        elif isinstance(icon, Image.Image):
            icon_img = icon
        else:
            raise TypeError(f"Unsupported icon type: {type(icon)}")

        if icon_img.size != (key_w, key_h):
            icon_img = icon_img.resize((key_w, key_h), Image.Resampling.LANCZOS)

        if icon_img.mode == "RGBA":
            img.paste(icon_img, (0, 0), icon_img)
        else:
            img = icon_img.convert("RGB")

    return _encode_image_bytes(img, image_format)


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


def _encode_image_bytes(img: Image.Image, image_format: str = "JPEG", quality: int = 90) -> bytes:
    """Encode a PIL image in the specified format.

    Parameters
    ----------
    img
        A ``PIL.Image.Image`` instance.
    image_format : str, default="JPEG"
        Target format (``"JPEG"`` or ``"BMP"``).
    quality : int, default=90
        JPEG quality (ignored for BMP).

    Returns
    -------
    bytes
        Raw encoded image bytes.
    """
    fmt = image_format.upper()
    buf = io.BytesIO()
    if fmt == "BMP":
        img.convert("RGB").save(buf, format="BMP")
    else:
        img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
