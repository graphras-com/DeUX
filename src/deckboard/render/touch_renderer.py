"""Touch-strip rendering for Stream Deck+ cards."""

from __future__ import annotations

from PIL import Image

from .key_renderer import _encode_jpeg
from .metrics import (
    MARGIN_LEFT,
    MARGIN_TOP,
    PANEL_COUNT,
    PANEL_GAP,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
)


def compose_touchstrip(
    cards: list[Image.Image | None],
    background: str = "black",
) -> bytes:
    """Compose 4 card images into a single touchscreen JPEG.

    Args:
        cards: Up to 4 card images (or ``None`` for blank slots).
        background: Fill colour for the 800x100 canvas (margins and gaps).
    """
    img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), background)

    for index, card_image in enumerate(cards):
        if index >= PANEL_COUNT:
            break
        if card_image is not None:
            x = MARGIN_LEFT + index * (PANEL_WIDTH + PANEL_GAP)
            img.paste(card_image, (x, MARGIN_TOP))

    return _encode_jpeg(img)


def render_blank_touchscreen(
    background: str = "black",
) -> bytes:
    """Render a blank touch-strip image."""
    return compose_touchstrip([None] * PANEL_COUNT, background=background)
