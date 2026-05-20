"""Touch-strip rendering for Stream Deck cards.

Uses Pillow for all compositing and encoding operations.
"""

from __future__ import annotations

import io

from PIL import Image


def _to_pil(value: object) -> Image.Image:
    """Convert an image value (bytes or PIL Image) to a PIL Image.

    Parameters
    ----------
    value
        Either raw image bytes (PNG/JPEG) or a ``PIL.Image.Image``.

    Returns
    -------
    Image.Image
        A PIL Image instance.
    """
    if isinstance(value, bytes):
        return Image.open(io.BytesIO(value))
    if isinstance(value, Image.Image):
        return value
    # Assume PIL-like object with save method.
    buf = io.BytesIO()
    value.save(buf, format="PNG")  # type: ignore[attr-defined]
    return Image.open(io.BytesIO(buf.getvalue()))


def _encode_pil_image(img: Image.Image, image_format: str, quality: int = 90) -> bytes:
    """Encode a PIL image to the requested format.

    Parameters
    ----------
    img
        A ``PIL.Image.Image`` instance.
    image_format : str
        Target format: ``"JPEG"`` or ``"BMP"``.
    quality : int, default=90
        JPEG quality (ignored for BMP).

    Returns
    -------
    bytes
        Encoded image bytes.
    """
    fmt = image_format.upper()
    buf = io.BytesIO()
    rgb = img.convert("RGB")
    if fmt == "BMP":
        rgb.save(buf, format="BMP")
    else:
        rgb.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def composite_frame_on_tile(
    frame_bytes: bytes,
    *,
    bg_tile_bytes: bytes,
    panel_width: int,
    panel_height: int,
    image_format: str = "JPEG",
) -> bytes:
    """Composite a rendered frame onto a background tile.

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
    bg = Image.open(io.BytesIO(bg_tile_bytes)).convert("RGBA")
    frame = Image.open(io.BytesIO(frame_bytes)).convert("RGBA")

    if bg.size != (panel_width, panel_height):
        bg = bg.resize((panel_width, panel_height), Image.Resampling.LANCZOS)
    if frame.size != (panel_width, panel_height):
        frame = frame.resize((panel_width, panel_height), Image.Resampling.LANCZOS)

    bg = Image.alpha_composite(bg, frame)
    return _encode_pil_image(bg, image_format)


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
    # Support both parameter names for backward compatibility.
    _tile = bg_tile_bytes or bg_tile
    if _tile is not None:
        base = _to_pil(_tile).convert("RGBA")
    else:
        r, g, b = _parse_color(background)
        base = Image.new("RGBA", (panel_width, panel_height), (r, g, b, 255))

    if card_bytes is not None:
        card = _to_pil(card_bytes).convert("RGBA")
        base = Image.alpha_composite(base, card)

    return _encode_pil_image(base, image_format)


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
    r, g, b = _parse_color(background)
    canvas = Image.new("RGBA", (touchscreen_width, touchscreen_height), (r, g, b, 255))

    for index, card_data in enumerate(card_tiles):
        if index >= panel_count:
            break
        x_offset = index * panel_width
        tile_bytes = (
            bg_tiles[index] if bg_tiles is not None and index < len(bg_tiles) else None
        )

        panel: Image.Image | None = None
        if tile_bytes is not None:
            panel = _to_pil(tile_bytes).convert("RGBA")

        if card_data is not None:
            card_img = _to_pil(card_data).convert("RGBA")
            panel = Image.alpha_composite(panel, card_img) if panel is not None else card_img

        if panel is not None:
            canvas.paste(panel, (x_offset, 0))

    return _encode_pil_image(canvas, image_format)


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
