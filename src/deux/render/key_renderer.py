"""Key image rendering for Stream Deck button slots.

Uses pyvips for image encoding. PIL is only needed as a fallback for
BMP format (which pyvips does not support natively).
"""

from __future__ import annotations

import io

from ..render.svg_rasterize import _ensure_macos_lib_path


def render_key_image(
    key_size: tuple[int, int],
    icon: bytes | object | None = None,
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
        ``PIL.Image.Image`` (for backward compatibility). Resized to
        ``key_size`` if it does not already match.
    background
        Background colour name (used when *icon* is ``None`` or has alpha).
    image_format
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded image bytes ready to send to the device.
    """
    _ensure_macos_lib_path()
    import pyvips

    from .touch_renderer import _parse_color

    key_w, key_h = key_size
    r, g, b = _parse_color(background)
    img = pyvips.Image.black(key_w, key_h, bands=3) + [r, g, b]
    img = img.cast("uchar")

    if icon is not None:
        # Accept bytes or PIL Image.
        if isinstance(icon, bytes):
            icon_img = pyvips.Image.new_from_buffer(icon, "")
        else:
            # PIL Image — convert to PNG bytes first.
            buf = io.BytesIO()
            icon.save(buf, format="PNG")  # type: ignore[union-attr]
            icon_img = pyvips.Image.new_from_buffer(buf.getvalue(), "")

        if icon_img.width != key_w or icon_img.height != key_h:
            icon_img = icon_img.thumbnail_image(key_w, height=key_h, crop="centre")

        if icon_img.hasalpha():
            # Ensure both images are in sRGB colourspace for compositing.
            if img.bands == 3:
                img = img.copy(interpretation="srgb")
            img = img.addalpha()
            if icon_img.interpretation != img.interpretation:
                icon_img = icon_img.copy(interpretation="srgb")
            img = img.composite2(icon_img, "over")
            img = img.flatten(background=[r, g, b])
        else:
            img = icon_img

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


def _encode_image_bytes(vimg: object, image_format: str = "JPEG", quality: int = 90) -> bytes:
    """Encode a pyvips image in the specified format.

    Parameters
    ----------
    vimg
        A ``pyvips.Image`` instance.
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
    if fmt == "BMP":
        from PIL import Image as _PILImage

        png_bytes = vimg.write_to_buffer(".png")  # type: ignore[union-attr]
        pil_img = _PILImage.open(io.BytesIO(png_bytes)).convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, format="BMP")
        return buf.getvalue()
    return vimg.write_to_buffer(".jpg", Q=quality)  # type: ignore[union-attr]


# Legacy alias for backward compatibility with internal imports.
def _encode_image(img: object, image_format: str = "JPEG", quality: int = 90) -> bytes:
    """Encode an image (pyvips or PIL) to device bytes.

    Accepts both pyvips.Image and PIL.Image.Image for backward
    compatibility during the migration period.

    Parameters
    ----------
    img
        A pyvips.Image or PIL.Image.Image instance.
    image_format : str, default="JPEG"
        Target format (``"JPEG"`` or ``"BMP"``).
    quality : int, default=90
        JPEG quality (ignored for BMP).

    Returns
    -------
    bytes
        Raw encoded image bytes.
    """
    try:
        import pyvips

        if isinstance(img, pyvips.Image):
            return _encode_image_bytes(img, image_format, quality)
    except ImportError:
        pass

    # PIL fallback for legacy callers.
    from PIL import Image as _PILImage

    if isinstance(img, _PILImage.Image):
        buf = io.BytesIO()
        fmt = image_format.upper()
        if fmt == "BMP":
            img.save(buf, format="BMP")
        else:
            img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

    raise TypeError(f"Unsupported image type: {type(img)}")
