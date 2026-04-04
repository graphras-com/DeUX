"""EncoderSlot class: wraps a physical rotary encoder on the Stream Deck+."""

from __future__ import annotations

import logging

from ...runtime.events import AsyncHandler

logger = logging.getLogger(__name__)


class EncoderSlot:
    """Represents a single physical dial (rotary encoder) on the Stream Deck+.

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

    # -- Decorator-based event registration --------------------------------

    def on_turn(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for dial turn events.

        The handler receives a single ``direction`` argument:
        positive = clockwise, negative = counter-clockwise.

        Usage::

            @dial.on_turn
            async def handle(direction: int):
                ...
        """
        self._turn_handler = handler
        return handler

    def on_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for dial press events.

        Usage::

            @dial.on_press
            async def handle():
                ...
        """
        self._press_handler = handler
        return handler

    def on_release(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for dial release events.

        Usage::

            @dial.on_release
            async def handle():
                ...
        """
        self._release_handler = handler
        return handler

    async def dispatch_turn(self, direction: int) -> None:
        """Dispatch a dial turn event through the registered handler."""
        if self._turn_handler is not None:
            await self._turn_handler(direction)

    async def dispatch_press(self, pressed: bool) -> None:
        """Dispatch a dial press or release event."""
        handler = self._press_handler if pressed else self._release_handler
        if handler is not None:
            await handler()


# Backward-compatible alias
Dial = EncoderSlot
