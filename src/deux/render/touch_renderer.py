"""Touch-strip rendering for Stream Deck cards."""

from __future__ import annotations

from PIL import Image

from .key_renderer import _encode_image


def _composite_card_on_tile(
    card: Image.Image,
    tile: Image.Image,
) -> Image.Image:
    """Composite an RGBA card image onto an RGB background tile.

    If the card has an alpha channel it is used as a mask so that
    transparent regions of the card reveal the background tile
    underneath.  If the card is RGB (no alpha), it replaces the tile
    entirely.

    Parameters
    ----------
    card
        The card image (RGB or RGBA).
    tile
        The background tile (RGB).

    Returns
    -------
    Image.Image
        An RGB image with the card composited onto the tile.
    """
    base = tile.copy()
    if card.mode == "RGBA":
        base.paste(card, mask=card)
    else:
        base.paste(card)
    return base


def compose_card_with_background(
    card: Image.Image | None,
    *,
    bg_tile: Image.Image | None = None,
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
    card
        The card image (RGB or RGBA), or ``None`` for a blank panel.
    bg_tile
        Pre-sliced background tile for this panel, or ``None`` to use
        the solid *background* colour.
    background
        Fallback fill colour when *bg_tile* is ``None``.
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
    if bg_tile is not None:
        img = _composite_card_on_tile(card, bg_tile) if card is not None else bg_tile.copy()
    else:
        img = Image.new("RGB", (panel_width, panel_height), background)
        if card is not None:
            if card.mode == "RGBA":
                img.paste(card, mask=card)
            else:
                img.paste(card)

    return _encode_image(img, image_format)


def compose_touchstrip(
    cards: list[Image.Image | None],
    *,
    touchscreen_width: int,
    touchscreen_height: int,
    panel_count: int,
    panel_width: int,
    background: str = "black",
    bg_tiles: list[Image.Image] | None = None,
    image_format: str = "JPEG",
) -> bytes:
    """Compose card images into a single touchscreen image.

    Cards are tiled edge-to-edge across the touchscreen — the library
    imposes no margins or gaps. Card *i* starts at
    ``(i * panel_width, 0)`` and is expected to be ``panel_width`` wide
    and ``touchscreen_height`` tall. The *background* colour shows
    through wherever a slot is ``None`` or a card image leaves pixels
    uncovered.

    When *bg_tiles* is provided, each panel is composited onto its
    corresponding background tile instead of the solid-colour canvas.
    Cards with RGBA transparency will reveal the background tile
    underneath.

    Parameters
    ----------
    cards
        Card images (or ``None`` for blank slots).
    touchscreen_width
        Total touchscreen width in pixels.
    touchscreen_height
        Total touchscreen height in pixels.
    panel_count
        Number of card zones (slots beyond this are silently dropped).
    panel_width
        Width of each card panel in pixels.
    background
        Fill colour for the canvas where no card is drawn.
    bg_tiles
        Optional list of pre-sliced background tiles (one per panel).
        When provided, cards are composited onto these tiles instead of
        the solid *background* colour.
    image_format
        Image encoding format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded touchscreen image bytes.
    """
    img = Image.new("RGB", (touchscreen_width, touchscreen_height), background)

    for index, card_image in enumerate(cards):
        if index >= panel_count:
            break
        x_offset = index * panel_width
        tile = bg_tiles[index] if bg_tiles is not None and index < len(bg_tiles) else None

        if tile is not None:
            panel = (
                _composite_card_on_tile(card_image, tile) if card_image is not None else tile
            )
            img.paste(panel, (x_offset, 0))
        elif card_image is not None:
            if card_image.mode == "RGBA":
                # Composite RGBA card onto the solid-colour canvas region
                region = img.crop((x_offset, 0, x_offset + panel_width, touchscreen_height))
                region.paste(card_image, mask=card_image)
                img.paste(region, (x_offset, 0))
            else:
                img.paste(card_image, (x_offset, 0))

    return _encode_image(img, image_format)


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
