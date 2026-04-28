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
        self._press_turn_handler: AsyncHandler | None = None
        self._accumulator: DialAccumulator | None = None
        self._press_turn_accumulator: DialAccumulator | None = None
        self._pressed: bool = False

    @property
    def index(self) -> int:
        """The encoder index on the device."""
        return self._index

    # -- Turn handlers -------------------------------------------------------

    def on_turn(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for encoder turn events.

        The handler receives a single ``direction`` argument:
        positive = clockwise, negative = counter-clockwise.

        When a ``press_turn`` handler is also registered, ``on_turn`` only
        fires for turns while the encoder is **not** pressed.

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

        if callback is not None:
            return _wrap(callback)
        return _wrap

    # -- Press-turn handlers -------------------------------------------------

    def on_press_turn(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for turning while pressed.

        The handler receives a single ``direction`` argument, just like
        :meth:`on_turn`.  When registered, ``on_turn`` will **not** fire
        for turns that happen while the encoder is held down.

        Examples
        --------
        ::

            @encoder.on_press_turn
            async def handle(direction: int):
                ...
        """
        self._press_turn_handler = handler
        return handler

    def on_press_turn_accumulated(
        self,
        callback: Callable[[int], Awaitable[None]] | None = None,
        *,
        delay: float = 0.25,
        max_steps: int = 10,
    ) -> DialAccumulator | Callable[[Callable[[int], Awaitable[None]]], DialAccumulator]:
        """Register an accumulated press-turn handler backed by a :class:`DialAccumulator`.

        Same API as :meth:`on_turn_accumulated` but only fires while the
        encoder is held down.

        Examples
        --------
        ::

            @encoder.on_press_turn_accumulated(delay=0.1, max_steps=5)
            async def handle(steps: int):
                ...
        """

        def _wrap(cb: Callable[[int], Awaitable[None]]) -> DialAccumulator:
            acc = DialAccumulator(cb, delay=delay, max_steps=max_steps)
            self._press_turn_accumulator = acc

            async def _tick(direction: int) -> None:
                acc.tick(direction)

            self._press_turn_handler = _tick
            return acc

        if callback is not None:
            return _wrap(callback)
        return _wrap

    # -- Press / release handlers --------------------------------------------

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

    # -- Dispatch ------------------------------------------------------------

    async def dispatch_turn(self, direction: int) -> None:
        """Dispatch an encoder turn event through the registered handler.

        When a ``press_turn`` handler is registered, turns while pressed
        are routed to it instead of the regular ``turn`` handler (matching
        the priority logic of :class:`~deckui.dui.event_map.EventMap`).
        """
        if self._pressed and self._press_turn_handler is not None:
            await self._press_turn_handler(direction)
            return
        if self._turn_handler is not None:
            await self._turn_handler(direction)

    async def dispatch_press(self, pressed: bool) -> None:
        """Dispatch an encoder press or release event."""
        self._pressed = pressed
        handler = self._press_handler if pressed else self._release_handler
        if handler is not None:
            await handler()
