"""Async event primitive for property-change notifications.

:class:`AsyncEvent` is a tiny multicast hook used throughout DeckUI
wherever a state change should be observable by zero or more async
subscribers — for example :attr:`deckui.Deck.on_brightness_changed`.

The shape mirrors what a real-world backend SDK (Spotify, Home Assistant,
etc.) usually exposes for property-change notifications: a callable that
acts both as a decorator for registering subscribers and an awaitable
emitter for the producer.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

AsyncHandler = Callable[..., Coroutine[Any, Any, None]]
"""Async callable accepted by :class:`AsyncEvent` subscribers."""

_H = TypeVar("_H", bound=AsyncHandler)


class AsyncEvent:
    """A multicast async event that can have multiple subscribers.

    Subscribers are async callables registered via :meth:`subscribe`
    or by using the event itself as a decorator.  :meth:`emit` invokes
    every registered subscriber sequentially, awaiting each one in
    registration order.

    The handler list is snapshotted at the start of every :meth:`emit`,
    so subscribers may safely register or unregister during dispatch
    without affecting the in-flight emission.

    The signature of an event is part of its documented contract, not
    its static type — events here are intentionally non-generic so
    they can carry arbitrary positional/keyword payloads.

    Examples
    --------
    ::

        on_volume_changed = AsyncEvent()

        @on_volume_changed
        async def _log(value: int) -> None:
            print(f"volume = {value}")

        await on_volume_changed.emit(75)
    """

    __slots__ = ("_handlers",)

    def __init__(self) -> None:
        self._handlers: list[AsyncHandler] = []

    def subscribe(self, handler: _H) -> _H:
        """Register *handler* as a subscriber.

        Parameters
        ----------
        handler
            Async callable to invoke on every :meth:`emit`.

        Returns
        -------
        handler
            The original *handler*, unchanged, so this can be used as
            a decorator.
        """
        self._handlers.append(handler)
        return handler

    def unsubscribe(self, handler: AsyncHandler) -> None:
        """Remove *handler* from the subscriber list.

        Parameters
        ----------
        handler
            A previously-registered subscriber.

        Raises
        ------
        ValueError
            If *handler* is not currently subscribed.
        """
        self._handlers.remove(handler)

    def __call__(self, handler: _H) -> _H:
        """Decorator alias for :meth:`subscribe`.

        Parameters
        ----------
        handler
            Async callable to register.

        Returns
        -------
        handler
            The original handler.
        """
        return self.subscribe(handler)

    async def emit(self, *args: Any, **kwargs: Any) -> None:
        """Invoke every subscriber sequentially, awaiting each in turn.

        A snapshot of the handler list is taken first, so handlers may
        subscribe or unsubscribe during dispatch without affecting the
        current emission.

        Parameters
        ----------
        *args
            Positional arguments forwarded to every handler.
        **kwargs
            Keyword arguments forwarded to every handler.
        """
        for handler in list(self._handlers):
            await handler(*args, **kwargs)

    @property
    def subscriber_count(self) -> int:
        """Number of currently-registered subscribers."""
        return len(self._handlers)
