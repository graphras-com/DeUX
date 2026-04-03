"""Compatibility exports for key and touch-strip rendering helpers."""

from __future__ import annotations

from .render.fonts import _get_font, get_font, get_large_font, get_small_font
from .render.key_renderer import _encode_jpeg, render_blank_key, render_key_image
from .render.metrics import (
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
from .render.touch_renderer import (
    compose_touchstrip,
    render_blank_touchscreen,
    render_status_card_image,
)

# Legacy touchscreen names kept for compatibility.
WIDGET_COUNT = PANEL_COUNT
WIDGET_GAP = PANEL_GAP
WIDGET_HEIGHT = PANEL_HEIGHT
WIDGET_WIDTH = PANEL_WIDTH


def compose_touchscreen(widgets):
    """Compatibility wrapper around the new touch-strip compositor."""
    return compose_touchstrip(widgets)


def render_widget_image(
    icon=None,
    label=None,
    value=None,
    background: str = "black",
):
    """Compatibility wrapper around the new status-card renderer."""
    return render_status_card_image(
        icon=icon,
        label=label,
        value=value,
        background=background,
    )


__all__ = [
    "ICON_PADDING",
    "ICON_SIZE",
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
    "WIDGET_COUNT",
    "WIDGET_GAP",
    "WIDGET_HEIGHT",
    "WIDGET_WIDTH",
    "_encode_jpeg",
    "_get_font",
    "compose_touchscreen",
    "get_font",
    "get_large_font",
    "get_small_font",
    "render_blank_key",
    "render_blank_touchscreen",
    "render_key_image",
    "render_widget_image",
]
