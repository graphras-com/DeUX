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

    def __init__(self) -> None:
        self._press_handler: AsyncHandler | None = None
        self._release_handler: AsyncHandler | None = None
        self._image_bytes: bytes | None = None
        self._dirty = True
        self._request_refresh: AsyncHandler | None = None

    def set_refresh_callback(self, callback: AsyncHandler) -> None:
        """Register an async callback the key can invoke to request a refresh.

        This is set automatically by :class:`~deux.runtime.deck.Deck`
        when a screen is activated, so any code path (key handler,
        background task, external state change) can call
        :meth:`request_refresh` to trigger a re-render.

        Parameters
        ----------
        callback
            Async callable that triggers a deck refresh.
        """
        self._request_refresh = callback

    async def request_refresh(self) -> None:
        """Ask the deck to re-render the active screen.

        No-op if no refresh callback has been registered.
        """
        if self._request_refresh is not None:
            await self._request_refresh()

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
        """Whether the key image needs re-rendering."""
        return self._dirty

    def mark_dirty(self) -> None:
        """Flag this key for re-rendering on the next refresh."""
        self._dirty = True

    def mark_clean(self) -> None:
        """Clear the dirty flag after the key image has been flushed."""
        self._dirty = False

    def set_rendered_image(self, image_bytes: bytes) -> None:
        """Store pre-rendered JPEG bytes (set by Deck during render)."""
        self._image_bytes = image_bytes
        self._dirty = False

    @property
    def image_bytes(self) -> bytes | None:
        """The pre-rendered image bytes, or ``None`` if not yet rendered."""
        return self._image_bytes
