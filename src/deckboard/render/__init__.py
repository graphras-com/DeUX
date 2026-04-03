"""Rendering helpers for deckboard keys, cards, and icons."""

from __future__ import annotations

from .debug_grid import draw_key_grid, draw_touchscreen_grid
from .fonts import get_font, get_large_font, get_small_font
from .icons import IconError, IconManager
from .key_renderer import render_blank_key, render_key_image
from .metrics import (
    ICON_PADDING,
    ICON_SIZE,
    KEY_SIZE,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    PANEL_COUNT,
    PANEL_GAP,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
    USABLE_HEIGHT,
    USABLE_WIDTH,
)
from .touch_renderer import (
    compose_touchstrip,
    render_blank_touchscreen,
    render_status_card_image,
)

__all__ = [
    "ICON_PADDING",
    "ICON_SIZE",
    "IconError",
    "IconManager",
    "KEY_SIZE",
    "MARGIN_BOTTOM",
    "MARGIN_LEFT",
    "MARGIN_RIGHT",
    "MARGIN_TOP",
    "PANEL_COUNT",
    "PANEL_GAP",
    "PANEL_HEIGHT",
    "PANEL_WIDTH",
    "TOUCHSCREEN_HEIGHT",
    "TOUCHSCREEN_WIDTH",
    "USABLE_HEIGHT",
    "USABLE_WIDTH",
    "compose_touchstrip",
    "draw_key_grid",
    "draw_touchscreen_grid",
    "get_font",
    "get_large_font",
    "get_small_font",
    "render_blank_key",
    "render_blank_touchscreen",
    "render_key_image",
    "render_status_card_image",
]
