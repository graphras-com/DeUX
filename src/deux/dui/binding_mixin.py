"""Shared mixin for event-binding helpers used by DuiCard and DuiKey."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..runtime.async_event import AsyncEvent
    from ..runtime.events import AsyncHandler
    from .event_map import EventMap


class BindingMixin:
    """Mixin providing ``bind``, ``bind_range``, ``bind_many``, ``forward``, and helpers.

    Subclasses must provide the following attributes/methods:

    * ``_events: EventMap``
    * ``_subscriptions: list[tuple[AsyncEvent, AsyncHandler]]``
    * ``is_dirty: bool`` (property)
    * ``request_refresh() -> Coroutine``
    * ``set(name, value)``
    * ``set_range(name, value, *, min_val, max_val)``
    * ``set_many(**kwargs)``
    """

    # Attributes/methods expected on the concrete class (provided by Card/KeySlot).
    # Declared here for type-checking only; no runtime implementations.
    if TYPE_CHECKING:
        _events: EventMap
        _subscriptions: list[tuple[AsyncEvent, AsyncHandler]]

        @property
        def is_dirty(self) -> bool: ...

        async def request_refresh(self) -> None: ...

        def set(self, name: str, value: Any) -> Any: ...

        def set_range(
            self, name: str, value: float, *, min_val: float, max_val: float
        ) -> Any: ...

        def set_many(self, **kwargs: Any) -> Any: ...

    def on(self, event_name: str) -> Callable[[AsyncHandler], AsyncHandler]:
        """Decorator to register a handler for a named semantic event.

        Examples
        --------
        ::

            @element.on("toggle")
            async def handle():
                ...

        Parameters
        ----------
        event_name
            Semantic event name from the manifest.

        Returns
        -------
        Callable
            A decorator that registers the handler and returns it unchanged.
        """

        def decorator(fn: AsyncHandler) -> AsyncHandler:
            self._events.on(event_name, self._wrap_handler(fn))
            return fn

        return decorator

    def bind_event(self, event_name: str, handler: AsyncHandler) -> None:
        """Imperatively register a handler for a named semantic event.

        Parameters
        ----------
        event_name
            Semantic event name from the manifest.
        handler
            The async callable to invoke.
        """
        self._events.on(event_name, self._wrap_handler(handler))

    def bind(
        self,
        name: str,
        event: AsyncEvent,
        *,
        transform: Callable[..., Any] | None = None,
    ) -> Self:
        """Subscribe to *event*; on emit, write binding *name* and refresh.

        This fuses three operations that otherwise repeat across every
        controller: subscribe to a service ``AsyncEvent``, translate
        the emitted value into the binding's domain, and request a
        refresh.

        Without *transform*, the binding receives the first positional
        argument from the event (``args[0]``).  With *transform*, the
        callable is invoked with all event ``args``/``kwargs`` and its
        return value becomes the binding value.

        The subscriber lives for the lifetime of the element unless
        :meth:`detach` is called.  Bind once during construction or
        lifecycle hooks.

        Parameters
        ----------
        name
            Binding name as defined in the manifest.
        event
            The :class:`~deux.runtime.async_event.AsyncEvent` to
            subscribe to (e.g. a service's ``on_volume_changed``).
        transform
            Optional sync callable that maps event args to the binding
            value.  If ``None``, ``args[0]`` is used.

        Returns
        -------
        Self
            self, for method chaining.
        """

        async def _on_event(*args: Any, **kwargs: Any) -> None:
            value = (
                (args[0] if args else None)
                if transform is None
                else transform(*args, **kwargs)
            )
            self.set(name, value)
            if self.is_dirty:
                await self.request_refresh()

        event.subscribe(_on_event)
        self._subscriptions.append((event, _on_event))

        # Seed the binding with the event's last emitted value so the
        # first render already shows the real state instead of defaults.
        if event.has_value:
            args, kwargs = event.last_args, event.last_kwargs
            value = (
                (args[0] if args else None)
                if transform is None
                else transform(*args, **kwargs)
            )
            self.set(name, value)

        return self

    def bind_range(
        self,
        name: str,
        event: AsyncEvent,
        *,
        min_val: float = 0,
        max_val: float = 1,
        transform: Callable[..., float] | None = None,
    ) -> Self:
        """Subscribe to *event*; on emit, write binding *name* via :meth:`set_range`.

        Same shape as :meth:`bind`, but routes through :meth:`set_range`
        so the emitted value can be in domain units (e.g. a 0--100
        percentage).

        Parameters
        ----------
        name
            Binding name (must be a ``range`` or ``slider`` binding).
        event
            The :class:`~deux.runtime.async_event.AsyncEvent` to
            subscribe to.
        min_val
            Lower bound of the domain range.
        max_val
            Upper bound of the domain range.
        transform
            Optional sync callable that maps event args to a numeric
            value in domain units.  If ``None``, ``args[0]`` is used.

        Returns
        -------
        Self
            self, for method chaining.

        Raises
        ------
        ValueError
            If *min_val* equals *max_val*.
        """
        if min_val == max_val:
            raise ValueError("min_val and max_val must not be equal")

        async def _on_event(*args: Any, **kwargs: Any) -> None:
            value = (
                float(args[0])
                if transform is None
                else float(transform(*args, **kwargs))
            )
            self.set_range(name, value, min_val=min_val, max_val=max_val)
            if self.is_dirty:
                await self.request_refresh()

        event.subscribe(_on_event)
        self._subscriptions.append((event, _on_event))

        # Seed with the last emitted value.
        if event.has_value:
            args, kwargs = event.last_args, event.last_kwargs
            value = (
                float(args[0])
                if transform is None
                else float(transform(*args, **kwargs))
            )
            self.set_range(name, value, min_val=min_val, max_val=max_val)

        return self

    def bind_many(
        self,
        event: AsyncEvent,
        transform: Callable[..., dict[str, Any]],
    ) -> Self:
        """Subscribe to *event*; transform args into a dict and :meth:`set_many` it.

        Use this when one event drives several bindings at once -- e.g.
        a ``track_changed`` event populating ``artist``, ``title``,
        ``album``, and ``state`` from a single track dict.

        Parameters
        ----------
        event
            The :class:`~deux.runtime.async_event.AsyncEvent` to
            subscribe to.
        transform
            Required sync callable that maps event args to a dict of
            binding names to values.

        Returns
        -------
        Self
            self, for method chaining.
        """

        async def _on_event(*args: Any, **kwargs: Any) -> None:
            values = transform(*args, **kwargs)
            self.set_many(**values)
            if self.is_dirty:
                await self.request_refresh()

        event.subscribe(_on_event)
        self._subscriptions.append((event, _on_event))

        # Seed with the last emitted value.
        if event.has_value:
            args, kwargs = event.last_args, event.last_kwargs
            values = transform(*args, **kwargs)
            self.set_many(**values)

        return self

    def detach(self) -> None:
        """Unsubscribe all handlers registered via :meth:`bind` and friends.

        Call this during teardown to prevent leaked handlers
        accumulating across reconnect cycles.
        """
        for event, handler in self._subscriptions:
            with suppress(ValueError):
                event.unsubscribe(handler)
        self._subscriptions.clear()

    def detach_events(self, *events: Any) -> None:
        """Unsubscribe only handlers bound to specific :class:`AsyncEvent` instances.

        Use this for partial teardown — e.g. removing bindings to a
        dying ``Deck``'s events while preserving service-owned bindings
        that were established in the controller's ``__init__``.

        Parameters
        ----------
        *events
            One or more :class:`AsyncEvent` objects whose subscriptions
            should be removed.
        """
        targets = set(events)
        remaining: list[tuple[Any, Any]] = []
        for event, handler in self._subscriptions:
            if event in targets:
                with suppress(ValueError):
                    event.unsubscribe(handler)
            else:
                remaining.append((event, handler))
        self._subscriptions = remaining

    def forward(
        self,
        event_name: str,
        target: Callable[..., Any],
    ) -> Self:
        """Register *target* as the handler for manifest event *event_name*.

        Sugar for the very common shape::

            @element.on("toggle")
            async def _h() -> None:
                await svc.toggle()

        which becomes::

            element.forward("toggle", svc.toggle)

        *target* may be an async function or any sync callable that
        returns an awaitable.  All positional and keyword arguments
        emitted by the event are forwarded to *target*.

        Parameters
        ----------
        event_name
            Semantic event name from the manifest.
        target
            Async-callable forwarding target.

        Returns
        -------
        Self
            self, for method chaining.
        """

        async def _handler(*args: Any, **kwargs: Any) -> None:
            await target(*args, **kwargs)

        self._events.on(event_name, self._wrap_handler(_handler))
        return self

    def _wrap_handler(self, fn: AsyncHandler) -> AsyncHandler:
        """Wrap *fn* so any state changes trigger a refresh after it runs.

        For events dispatched synchronously from the deck's event loop
        (key press, encoder press, non-accumulated turns) the deck
        already calls ``refresh()`` when the card is dirty after the
        handler runs.  But several event paths fire from detached
        asyncio tasks where the dispatcher is no longer in scope:

        * Accumulator flushes (``accumulate: true`` encoder turns).
        * Hold timers (``encoder_hold`` / ``key_hold``).

        Without this wrapper, those handlers can mutate bindings
        without ever triggering a render.  Wrapping at the registration
        boundary makes every handler self-refreshing, regardless of how
        it's dispatched.

        The wrapper:

        * Is a no-op when no refresh callback is wired (i.e. before the
          element is installed on a screen).
        * Is idempotent when the handler already calls
          :meth:`request_refresh` itself -- the second call finds the
          element clean and skips re-rendering.
        """

        async def _wrapped(*args: Any, **kwargs: Any) -> None:
            await fn(*args, **kwargs)
            if self.is_dirty:
                await self.request_refresh()

        # Preserve the original for testing / introspection.
        _wrapped.__wrapped__ = fn  # type: ignore[attr-defined]
        return _wrapped
