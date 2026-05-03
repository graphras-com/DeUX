"""Touch-strip rendering for Stream Deck cards."""

from __future__ import annotations

from PIL import Image

from .key_renderer import _encode_image


def compose_touchstrip(
    cards: list[Image.Image | None],
    *,
    touchscreen_width: int,
    touchscreen_height: int,
    panel_count: int,
    panel_width: int,
    background: str = "black",
    image_format: str = "JPEG",
) -> bytes:
    """Compose card images into a single touchscreen image.

    Cards are tiled edge-to-edge across the touchscreen — the library
    imposes no margins or gaps. Card *i* starts at
    ``(i * panel_width, 0)`` and is expected to be ``panel_width`` wide
    and ``touchscreen_height`` tall. The *background* colour shows
    through wherever a slot is ``None`` or a card image leaves pixels
    uncovered.

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
        if card_image is not None:
            img.paste(card_image, (index * panel_width, 0))

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
