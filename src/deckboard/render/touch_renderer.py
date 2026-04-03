"""Touch-strip rendering for Stream Deck+ cards."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .fonts import get_font, get_small_font
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


def render_status_card_image(
    icon: Image.Image | None = None,
    label: str | None = None,
    value: str | None = None,
    background: str = "black",
) -> Image.Image:
    """Render a single status card image."""
    img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), background)
    draw = ImageDraw.Draw(img)
    font = get_font()
    small_font = get_small_font()

    card_icon_size = 50
    icon_x = 8
    icon_y = (PANEL_HEIGHT - card_icon_size) // 2

    if icon is not None:
        sized = icon.resize((card_icon_size, card_icon_size), Image.LANCZOS)
        if sized.mode == "RGBA":
            img.paste(sized, (icon_x, icon_y), sized)
        else:
            img.paste(sized, (icon_x, icon_y))

    text_x = icon_x + card_icon_size + 10
    if label and value:
        draw.text((text_x, 18), label, fill="white", font=font)
        draw.text((text_x, 40), value, fill="#aaaaaa", font=small_font)
    elif label:
        draw.text((text_x, 30), label, fill="white", font=font)
    elif value:
        draw.text((text_x, 30), value, fill="#aaaaaa", font=small_font)

    return img


def compose_touchstrip(cards: list[Image.Image | None]) -> bytes:
    """Compose 4 card images into a single touchscreen JPEG."""
    img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")

    for index, card_image in enumerate(cards):
        if index >= PANEL_COUNT:
            break
        if card_image is not None:
            x = MARGIN_LEFT + index * (PANEL_WIDTH + PANEL_GAP)
            img.paste(card_image, (x, MARGIN_TOP))

    return _encode_jpeg(img)


def render_blank_touchscreen() -> bytes:
    """Render a blank touch-strip image."""
    return compose_touchstrip([None] * PANEL_COUNT)
