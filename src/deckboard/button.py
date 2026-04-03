"""Button class: wraps a physical key on the Stream Deck."""

from __future__ import annotations

import logging

from .types import AsyncHandler

logger = logging.getLogger(__name__)


class Button:
    """Represents a single physical key on the Stream Deck.

    Use decorators to register event handlers::

        @button.on_press
        async def handle():
            print("pressed!")
    """

    def __init__(self, index: int) -> None:
        self._index = index
        self._icon_name: str | None = None
        self._icon_color: str = "white"
        self._label: str | None = None
        self._press_handler: AsyncHandler | None = None
        self._release_handler: AsyncHandler | None = None
        self._image_bytes: bytes | None = None
        self._dirty = True  # needs re-render

    @property
    def index(self) -> int:
        return self._index

    @property
    def icon_name(self) -> str | None:
        return self._icon_name

    @property
    def label(self) -> str | None:
        return self._label

    @property
    def icon_color(self) -> str:
        return self._icon_color

    # -- Configuration methods (return self for chaining) ------------------

    def set_icon(self, name: str, color: str = "white") -> Button:
        """Set the icon by Iconify name (e.g. ``mdi:home``).

        Args:
            name: Icon name in ``prefix:name`` format.
            color: Icon color (CSS color string). Defaults to white.

        Returns:
            self, for method chaining.
        """
        self._icon_name = name
        self._icon_color = color
        self._dirty = True
        return self

    def set_label(self, label: str | None) -> Button:
        """Set a text label displayed below the icon.

        Args:
            label: Text label, or None to remove.

        Returns:
            self, for method chaining.
        """
        self._label = label
        self._dirty = True
        return self

    def clear(self) -> Button:
        """Clear the icon and label, resetting to a blank key."""
        self._icon_name = None
        self._label = None
        self._image_bytes = None
        self._dirty = True
        return self

    # -- Decorator-based event registration --------------------------------

    def on_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for key press events.

        Usage::

            @button.on_press
            async def handle():
                ...
        """
        self._press_handler = handler
        return handler

    def on_release(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for key release events.

        Usage::

            @button.on_release
            async def handle():
                ...
        """
        self._release_handler = handler
        return handler

    async def dispatch(self, pressed: bool) -> None:
        """Dispatch a press or release event through the registered handlers."""
        handler = self._press_handler if pressed else self._release_handler
        if handler is not None:
            await handler()

    # -- Internal methods --------------------------------------------------

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    def set_rendered_image(self, image_bytes: bytes) -> None:
        """Store pre-rendered JPEG bytes (set by Deck during render)."""
        self._image_bytes = image_bytes
        self._dirty = False

    @property
    def image_bytes(self) -> bytes | None:
        return self._image_bytes
