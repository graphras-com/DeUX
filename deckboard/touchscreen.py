"""Touchscreen and Widget classes for the Stream Deck+ LCD strip."""

from __future__ import annotations

import logging

from PIL import Image

from .image import WIDGET_COUNT
from .types import AsyncHandler

logger = logging.getLogger(__name__)


class Widget:
    """Represents a single touchscreen zone (200x100px) under a dial.

    The Stream Deck+ touchscreen (800x100) is divided into 4 zones,
    each aligned with one of the 4 dials.

    Usage::

        widget.set_icon("mdi:volume-high")
        widget.set_label("Volume")
        widget.set_value("75%")

        @widget.on_tap
        async def handle():
            print("Widget tapped!")
    """

    def __init__(self, index: int) -> None:
        self._index = index
        self._icon_name: str | None = None
        self._icon_color: str = "white"
        self._label: str | None = None
        self._value: str | None = None
        self._tap_handler: AsyncHandler | None = None
        self._long_press_handler: AsyncHandler | None = None
        self._drag_handler: AsyncHandler | None = None
        self._rendered: Image.Image | None = None
        self._dirty = True

    @property
    def index(self) -> int:
        return self._index

    # -- Configuration methods (return self for chaining) ------------------

    def set_icon(self, name: str, color: str = "white") -> Widget:
        """Set the icon by Iconify name.

        Args:
            name: Icon name in ``prefix:name`` format.
            color: Icon color. Defaults to white.
        """
        self._icon_name = name
        self._icon_color = color
        self._dirty = True
        return self

    def set_label(self, label: str | None) -> Widget:
        """Set the primary text label."""
        self._label = label
        self._dirty = True
        return self

    def set_value(self, value: str | None) -> Widget:
        """Set the secondary value text."""
        self._value = value
        self._dirty = True
        return self

    def clear(self) -> Widget:
        """Clear all content from this widget zone."""
        self._icon_name = None
        self._label = None
        self._value = None
        self._rendered = None
        self._dirty = True
        return self

    # -- Decorator-based event registration --------------------------------

    def on_tap(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for short tap events in this zone.

        Usage::

            @widget.on_tap
            async def handle():
                ...
        """
        self._tap_handler = handler
        return handler

    def on_long_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for long press events in this zone.

        Usage::

            @widget.on_long_press
            async def handle():
                ...
        """
        self._long_press_handler = handler
        return handler

    def on_drag(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for drag/swipe events in this zone.

        The handler receives ``x``, ``y``, ``x_out``, ``y_out`` arguments
        describing the start and end coordinates of the drag gesture.

        Usage::

            @widget.on_drag
            async def handle(x: int, y: int, x_out: int, y_out: int):
                ...
        """
        self._drag_handler = handler
        return handler

    # -- Internal ----------------------------------------------------------

    @property
    def icon_name(self) -> str | None:
        return self._icon_name

    @property
    def icon_color(self) -> str:
        return self._icon_color

    @property
    def label(self) -> str | None:
        return self._label

    @property
    def value(self) -> str | None:
        return self._value

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    @property
    def rendered(self) -> Image.Image | None:
        return self._rendered

    def set_rendered(self, img: Image.Image) -> None:
        self._rendered = img
        self._dirty = False


class TouchScreen:
    """Manages the 4 widget zones on the Stream Deck+ touchscreen."""

    def __init__(self) -> None:
        self._widgets: list[Widget] = [Widget(i) for i in range(WIDGET_COUNT)]

    def widget(self, index: int) -> Widget:
        """Get a widget zone by index (0-3)."""
        if not 0 <= index < WIDGET_COUNT:
            raise IndexError(f"Widget index must be 0-{WIDGET_COUNT - 1}, got {index}")
        return self._widgets[index]

    @property
    def widgets(self) -> list[Widget]:
        return self._widgets

    @property
    def any_dirty(self) -> bool:
        return any(w.is_dirty for w in self._widgets)
