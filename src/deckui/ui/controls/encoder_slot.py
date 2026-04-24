"""EncoderSlot class: wraps a physical rotary encoder on the Stream Deck+."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...runtime.events import AsyncHandler

logger = logging.getLogger(__name__)


class EncoderSlot:
    """Represents a single physical rotary encoder on the Stream Deck+.

    Examples
    --------
    Use decorators to register event handlers::

        @encoder.on_turn
        async def handle(direction: int):
            print(f"Turned by {direction}")
    """

    def __init__(self, index: int) -> None:
        self._index = index
        self._turn_handler: AsyncHandler | None = None
        self._press_handler: AsyncHandler | None = None
        self._release_handler: AsyncHandler | None = None

    @property
    def index(self) -> int:
        return self._index

    def on_turn(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for encoder turn events.

        The handler receives a single ``direction`` argument:
        positive = clockwise, negative = counter-clockwise.

        Examples
        --------
        ::

            @encoder.on_turn
            async def handle(direction: int):
                ...
        """
        self._turn_handler = handler
        return handler

    def on_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for encoder press events.

        Examples
        --------
        ::

            @encoder.on_press
            async def handle():
                ...
        """
        self._press_handler = handler
        return handler

    def on_release(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for encoder release events.

        Examples
        --------
        ::

            @encoder.on_release
            async def handle():
                ...
        """
        self._release_handler = handler
        return handler

    async def dispatch_turn(self, direction: int) -> None:
        """Dispatch an encoder turn event through the registered handler."""
        if self._turn_handler is not None:
            await self._turn_handler(direction)

    async def dispatch_press(self, pressed: bool) -> None:
        """Dispatch an encoder press or release event."""
        handler = self._press_handler if pressed else self._release_handler
        if handler is not None:
            await handler()
