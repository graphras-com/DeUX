"""EncoderSlot class: wraps a physical rotary encoder on the Stream Deck+."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from .dial_accumulator import DialAccumulator

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
        self._accumulator: DialAccumulator | None = None

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

    def on_turn_accumulated(
        self,
        callback: Callable[[int], Awaitable[None]] | None = None,
        *,
        delay: float = 0.25,
        max_steps: int = 10,
    ) -> DialAccumulator | Callable[[Callable[[int], Awaitable[None]]], DialAccumulator]:
        """Register an accumulated turn handler backed by a :class:`DialAccumulator`.

        Can be used as a plain decorator or called with keyword arguments::

            # Plain decorator — default delay/max_steps
            @encoder.on_turn_accumulated
            async def handle(steps: int):
                ...

            # With options
            @encoder.on_turn_accumulated(delay=0.1, max_steps=5)
            async def handle(steps: int):
                ...

        Returns the :class:`DialAccumulator` instance (which replaces the
        decorated function reference).
        """

        def _wrap(cb: Callable[[int], Awaitable[None]]) -> DialAccumulator:
            acc = DialAccumulator(cb, delay=delay, max_steps=max_steps)
            self._accumulator = acc
            async def _tick(direction: int) -> None:
                acc.tick(direction)

            self._turn_handler = _tick
            return acc

        # Called as @on_turn_accumulated (no parens) — callback is the function
        if callback is not None:
            return _wrap(callback)
        # Called as @on_turn_accumulated(...) — return the wrapper
        return _wrap

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
