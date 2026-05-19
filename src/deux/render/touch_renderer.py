"""Touch-strip rendering for Stream Deck cards.

Uses pyvips for all compositing and encoding operations. PIL is only
used as a fallback for BMP encoding (pyvips lacks native BMP support).
"""

from __future__ import annotations

import io
from typing import Any

from ..render.svg_rasterize import _ensure_macos_lib_path


def _to_vips(value: object) -> Any:
    """Convert an image value (bytes or PIL Image) to a pyvips.Image.

    Parameters
    ----------
    value
        Either raw image bytes (PNG/JPEG) or a ``PIL.Image.Image``.

    Returns
    -------
    object
        A ``pyvips.Image`` instance.
    """
    import pyvips

    if isinstance(value, bytes):
        return pyvips.Image.new_from_buffer(value, "")
    # PIL Image — convert to PNG bytes.
    buf = io.BytesIO()
    value.save(buf, format="PNG")  # type: ignore[attr-defined]
    return pyvips.Image.new_from_buffer(buf.getvalue(), "")


def _encode_vips_image(vimg: Any, image_format: str, quality: int = 90) -> bytes:
    """Encode a pyvips image to the requested format.

    Parameters
    ----------
    vimg
        A ``pyvips.Image`` instance.
    image_format : str
        Target format: ``"JPEG"`` or ``"BMP"``.
    quality : int, default=90
        JPEG quality (ignored for BMP).

    Returns
    -------
    bytes
        Encoded image bytes.
    """
    import pyvips  # noqa: F401

    fmt = image_format.upper()
    if fmt == "BMP":
        # pyvips doesn't support BMP natively; use PIL for this one format.
        from PIL import Image as _PILImage

        png_bytes = vimg.write_to_buffer(".png")
        pil_img = _PILImage.open(io.BytesIO(png_bytes)).convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, format="BMP")
        return buf.getvalue()
    return vimg.write_to_buffer(".jpg", Q=quality)  # type: ignore[no-any-return]


def composite_frame_on_tile(
    frame_bytes: bytes,
    *,
    bg_tile_bytes: bytes,
    panel_width: int,
    panel_height: int,
    image_format: str = "JPEG",
) -> bytes:
    """Composite a rendered frame onto a background tile using pyvips.

    Used for spinner animations where each frame must be composited
    onto the touchstrip background.

    Parameters
    ----------
    frame_bytes : bytes
        Encoded frame image (PNG or JPEG).
    bg_tile_bytes : bytes
        PNG-encoded background tile.
    panel_width : int
        Width of the panel in pixels.
    panel_height : int
        Height of the panel in pixels.
    image_format : str, default="JPEG"
        Output encoding format.

    Returns
    -------
    bytes
        Encoded composited image bytes.
    """
    _ensure_macos_lib_path()
    import pyvips

    bg = pyvips.Image.new_from_buffer(bg_tile_bytes, "")
    frame = pyvips.Image.new_from_buffer(frame_bytes, "")

    # Ensure both images are the right size.
    if bg.width != panel_width or bg.height != panel_height:
        bg = bg.thumbnail_image(panel_width, height=panel_height, crop="centre")
    if frame.width != panel_width or frame.height != panel_height:
        frame = frame.thumbnail_image(panel_width, height=panel_height, crop="centre")

    # Composite frame over background using alpha if present.
    if frame.hasalpha():
        # Ensure bg has alpha for compositing.
        if not bg.hasalpha():
            bg = bg.addalpha()
        bg = bg.copy(interpretation="srgb")
        frame = frame.copy(interpretation="srgb")
        result = bg.composite2(frame, "over")
        result = result.flatten(background=[0, 0, 0])
    else:
        result = frame

    return _encode_vips_image(result, image_format)


def compose_card_with_background(
    card_bytes: bytes | object | None,
    *,
    bg_tile: bytes | None = None,
    bg_tile_bytes: bytes | None = None,
    background: str = "black",
    panel_width: int,
    panel_height: int,
    image_format: str = "JPEG",
) -> bytes:
    """Composite a single card onto its background tile and encode.

    Used for partial touchscreen updates where only one card panel
    needs to be pushed to the device.

    Parameters
    ----------
    card_bytes
        Encoded card image (PNG/JPEG bytes), or ``None`` for a blank panel.
    bg_tile_bytes
        PNG-encoded background tile, or ``None`` to use the solid
        *background* colour.
    background
        Fallback fill colour when *bg_tile_bytes* is ``None``.
    panel_width
        Width of the card panel in pixels.
    panel_height
        Height of the card panel in pixels.
    image_format
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded image bytes for a single panel.
    """
    _ensure_macos_lib_path()
    import pyvips

    # Support both parameter names for backward compatibility.
    _tile = bg_tile_bytes or bg_tile
    if _tile is not None:
        base = _to_vips(_tile)
        if base.hasalpha():
            base = base.flatten(background=[0, 0, 0])
    else:
        # Parse CSS colour name to RGB.
        r, g, b = _parse_color(background)
        base = pyvips.Image.black(panel_width, panel_height, bands=3) + [r, g, b]
        base = base.cast("uchar").copy(interpretation="srgb")

    if card_bytes is not None:
        card = _to_vips(card_bytes)
        if card.hasalpha():
            if not base.hasalpha():
                base = base.addalpha()
            # Ensure compatible colourspace for compositing.
            base = base.copy(interpretation="srgb")
            card = card.copy(interpretation="srgb")
            base = base.composite2(card, "over")
            base = base.flatten(background=[0, 0, 0])
        else:
            base = card

    return _encode_vips_image(base, image_format)


def compose_touchstrip(
    card_tiles: list[bytes | object | None],
    *,
    touchscreen_width: int,
    touchscreen_height: int,
    panel_count: int,
    panel_width: int,
    background: str = "black",
    bg_tiles: list[bytes | object] | None = None,
    image_format: str = "JPEG",
) -> bytes:
    """Compose card images into a single touchscreen image.

    Cards are tiled edge-to-edge across the touchscreen. Card *i*
    starts at ``(i * panel_width, 0)``.

    Parameters
    ----------
    card_tiles
        Encoded card images (or ``None`` for blank slots).
    touchscreen_width
        Total touchscreen width in pixels.
    touchscreen_height
        Total touchscreen height in pixels.
    panel_count
        Number of card zones.
    panel_width
        Width of each card panel in pixels.
    background
        Fill colour for the canvas where no card is drawn.
    bg_tiles
        Optional list of PNG-encoded background tiles (one per panel).
    image_format
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded touchscreen image bytes.
    """
    _ensure_macos_lib_path()
    import pyvips

    r, g, b = _parse_color(background)
    canvas = pyvips.Image.black(touchscreen_width, touchscreen_height, bands=3) + [r, g, b]
    canvas = canvas.cast("uchar").copy(interpretation="srgb")

    for index, card_data in enumerate(card_tiles):
        if index >= panel_count:
            break
        x_offset = index * panel_width
        tile_bytes = (
            bg_tiles[index] if bg_tiles is not None and index < len(bg_tiles) else None
        )

        if tile_bytes is not None:
            tile_img = _to_vips(tile_bytes)
            if tile_img.hasalpha():
                tile_img = tile_img.flatten(background=[r, g, b])
            panel = tile_img
        else:
            panel = None

        if card_data is not None:
            card_img = _to_vips(card_data)
            if panel is not None:
                if card_img.hasalpha():
                    if not panel.hasalpha():
                        panel = panel.addalpha()
                    panel = panel.copy(interpretation="srgb")
                    card_img = card_img.copy(interpretation="srgb")
                    panel = panel.composite2(card_img, "over")
                    panel = panel.flatten(background=[r, g, b])
                else:
                    panel = card_img
            else:
                if card_img.hasalpha():
                    card_img = card_img.flatten(background=[r, g, b])
                panel = card_img

        if panel is not None:
            canvas = canvas.insert(panel, x_offset, 0)

    return _encode_vips_image(canvas, image_format)


def render_blank_touchscreen(
    *,
    touchscreen_width: int,
    touchscreen_height: int,
    panel_count: int,
    panel_width: int,
    background: str = "black",
    image_format: str = "JPEG",
) -> bytes:
    """Render a blank touch-strip image.

    Parameters
    ----------
    touchscreen_width
        Total touchscreen width in pixels.
    touchscreen_height
        Total touchscreen height in pixels.
    panel_count
        Number of card zones.
    panel_width
        Width of each card panel in pixels.
    background
        Fill colour for the canvas.
    image_format
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded blank touchscreen image bytes.
    """
    return compose_touchstrip(
        [None] * panel_count,
        touchscreen_width=touchscreen_width,
        touchscreen_height=touchscreen_height,
        panel_count=panel_count,
        panel_width=panel_width,
        background=background,
        image_format=image_format,
    )


def _parse_color(color: str) -> tuple[int, int, int]:
    """Parse a CSS colour name or hex value to an RGB tuple.

    Parameters
    ----------
    color : str
        CSS colour name (e.g. ``"black"``) or hex (e.g. ``"#ff0000"``).

    Returns
    -------
    tuple[int, int, int]
        RGB values in [0, 255].
    """
    _COLORS = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "green": (0, 128, 0),
        "blue": (0, 0, 255),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "transparent": (0, 0, 0),
    }
    c = color.strip().lower()
    if c in _COLORS:
        return _COLORS[c]
    if c.startswith("#"):
        c = c[1:]
        if len(c) == 3:
            c = c[0] * 2 + c[1] * 2 + c[2] * 2
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    return (0, 0, 0)
