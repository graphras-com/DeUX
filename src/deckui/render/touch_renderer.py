"""Touch-strip rendering for Stream Deck cards."""

from __future__ import annotations

from PIL import Image

from .key_renderer import _encode_image, _encode_jpeg
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
    touchscreen_width: int | None = None,
    touchscreen_height: int | None = None,
    panel_count: int | None = None,
    panel_width: int | None = None,
    margin_left: int | None = None,
    margin_top: int | None = None,
    panel_gap: int | None = None,
    image_format: str = "JPEG",
) -> bytes:
    """Compose card images into a single touchscreen image.

    All dimension parameters default to Stream Deck+ values when
    not specified.

    Args:
        cards: Card images (or ``None`` for blank slots).
        background: Fill colour for the canvas (margins and gaps).
        touchscreen_width: Total touchscreen width in pixels.
        touchscreen_height: Total touchscreen height in pixels.
        panel_count: Number of card zones.
        panel_width: Width of each card panel in pixels.
        margin_left: Left margin in pixels.
        margin_top: Top margin in pixels.
        panel_gap: Gap between panels in pixels.
        image_format: Image encoding format (``"JPEG"`` or ``"BMP"``).
    """
    ts_w = touchscreen_width if touchscreen_width is not None else TOUCHSCREEN_WIDTH
    ts_h = touchscreen_height if touchscreen_height is not None else TOUCHSCREEN_HEIGHT
    p_count = panel_count if panel_count is not None else PANEL_COUNT
    p_width = panel_width if panel_width is not None else PANEL_WIDTH
    m_left = margin_left if margin_left is not None else MARGIN_LEFT
    m_top = margin_top if margin_top is not None else MARGIN_TOP
    p_gap = panel_gap if panel_gap is not None else PANEL_GAP

    img = Image.new("RGB", (ts_w, ts_h), background)

    for index, card_image in enumerate(cards):
        if index >= p_count:
            break
        if card_image is not None:
            x = m_left + index * (p_width + p_gap)
            img.paste(card_image, (x, m_top))

    return _encode_image(img, image_format)


def render_blank_touchscreen(
    background: str = "black",
    touchscreen_width: int | None = None,
    touchscreen_height: int | None = None,
    panel_count: int | None = None,
    image_format: str = "JPEG",
) -> bytes:
    """Render a blank touch-strip image."""
    p_count = panel_count if panel_count is not None else PANEL_COUNT
    return compose_touchstrip(
        [None] * p_count,
        background=background,
        touchscreen_width=touchscreen_width,
        touchscreen_height=touchscreen_height,
        panel_count=p_count,
        image_format=image_format,
    )
