"""KeySlot class: wraps a physical key on the Stream Deck."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...runtime.events import AsyncHandler

logger = logging.getLogger(__name__)


class KeySlot:
    """Represents a single physical key on the Stream Deck.

    Examples
    --------
    Use decorators to register event handlers::

        @key.on_press
        async def handle():
            print("pressed!")
    """

    def __init__(self, index: int) -> None:
        self._index = index
        self._press_handler: AsyncHandler | None = None
        self._release_handler: AsyncHandler | None = None
        self._image_bytes: bytes | None = None
        self._dirty = True

    @property
    def index(self) -> int:
        return self._index

    def on_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for key press events.

        Examples
        --------
        ::

            @key.on_press
            async def handle():
                ...
        """
        self._press_handler = handler
        return handler

    def on_release(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for key release events.

        Examples
        --------
        ::

            @key.on_release
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
