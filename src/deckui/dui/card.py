"""DuiCard: a touchscreen card backed by a .dui package."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..ui.cards.base import Card
from .animator import PushFn, SpinnerAnimator
from .event_map import EventMap
from .schema import PackageSpec
from .spinner import SpinnerFrames
from .svg_renderer import SvgRenderer

if TYPE_CHECKING:
    from collections.abc import Callable

    from PIL import Image

    from ..runtime.async_event import AsyncEvent
    from ..runtime.events import AsyncHandler, TouchEvent

logger = logging.getLogger(__name__)


class DuiCard(Card):
    """A touchscreen card whose layout and events are defined by a .dui package.

    Instead of writing a Python class with imperative Pillow rendering,
    you describe the UI in an SVG layout and a YAML manifest.  The card
    loads the package, lets you set binding values, and renders the SVG
    into a PIL Image for the Stream Deck touchscreen.

    Examples
    --------
    ::

        from deckui import DuiCard

        # Resolve by name from the DUI repository
        card = DuiCard("AudioCard")
        card.set("artist", "Ash Walker")

        @card.on("toggle_play_pause")
        async def handle():
            ...

    You can also pass a pre-loaded :class:`~deckui.dui.schema.PackageSpec`
    directly::

        from deckui.dui import load_package, DuiCard

        spec = load_package("./AudioCard.dui")
        card = DuiCard(spec)

    The card index is assigned automatically when you install the card
    on a screen with :meth:`~deckui.ui.screen.Screen.set_card`.

    Parameters
    ----------
    spec : PackageSpec or str
        A validated :class:`~deckui.dui.schema.PackageSpec`, or a
        package name (e.g. ``"DashboardCard"``) to resolve from the
        DUI repository.
    """

    def __init__(self, spec: PackageSpec | str) -> None:
        if isinstance(spec, str):
            from .repository import resolve_dui

            spec = resolve_dui(spec)
        super().__init__()
        self._spec = spec
        self._renderer = SvgRenderer(spec)
        self._events = EventMap(spec.events, spec.regions)
        self._busy = False
        self._animator: SpinnerAnimator | None = None
        self._spinner_frames: SpinnerFrames | None = None
        self._push_fn: PushFn | None = None
        self._panel_size: tuple[int, int] | None = None
        self._bg_tile: Image.Image | None = None

    @property
    def spec(self) -> PackageSpec:
        """The package specification backing this card."""
        return self._spec

    @property
    def is_busy(self) -> bool:
        """Whether a busy-guarded handler is currently executing."""
        return self._busy

    @property
    def is_animating(self) -> bool:
        """Whether a spinner animation is currently running."""
        return self._animator is not None and self._animator.is_running

    def set_push_fn(self, push_fn: PushFn, panel_size: tuple[int, int]) -> None:
        """Set the async function used to push animation frames to the device.

        This must be called before spinner animations can play.
        Typically set by :class:`~deckui.runtime.deck.Deck`.

        Parameters
        ----------
        push_fn
            Async callable ``(frame_bytes) -> None``.
        panel_size
            ``(width, height)`` of the touchscreen panel this card occupies,
            used to size spinner frames.
        """
        self._push_fn = push_fn
        self._panel_size = panel_size

    def set_bg_tile(self, tile: Image.Image | None) -> None:
        """Set the background tile for compositing spinner frames.

        When a touchstrip background SVG is active, the corresponding
        pre-sliced tile is passed here so that spinner animations can
        composite each frame onto the background.

        Parameters
        ----------
        tile
            The RGB background tile, or ``None`` to clear.
        """
        self._bg_tile = tile

    def set(self, name: str, value: Any) -> DuiCard:
        """Set a binding value.  Marks the card dirty if changed.

        Parameters
        ----------
        name
            Binding name as defined in the manifest.
        value
            New value (type depends on binding kind).

        Returns
        -------
        DuiCard
            self, for method chaining.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        """
        if self._renderer.set(name, value):
            self.mark_dirty()
        return self

    def set_many(self, **kwargs: Any) -> DuiCard:
        """Set multiple binding values at once.

        Returns
        -------
        DuiCard
            self, for method chaining.
        """
        if self._renderer.set_many(**kwargs):
            self.mark_dirty()
        return self

    def get(self, name: str) -> Any:
        """Get the current value of a binding.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        """
        return self._renderer.get(name)

    def set_range(
        self, name: str, value: float, *, min_val: float = 0, max_val: float = 1
    ) -> DuiCard:
        """Set a range/slider binding using a domain-scale value.

        Normalises *value* from ``[min_val, max_val]`` to ``[0.0, 1.0]``
        and delegates to :meth:`set`.

        Parameters
        ----------
        name
            Binding name (must be a ``range`` or ``slider`` binding).
        value
            Value in domain units (e.g. 0–100 for a percentage).
        min_val
            Lower bound of the domain range.
        max_val
            Upper bound of the domain range.

        Returns
        -------
        DuiCard
            self, for method chaining.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        ValueError
            If *min_val* equals *max_val*.
        """
        if min_val == max_val:
            raise ValueError("min_val and max_val must not be equal")
        clamped = max(min_val, min(max_val, value))
        normalised = (clamped - min_val) / (max_val - min_val)
        return self.set(name, normalised)

    def adjust_range(
        self, name: str, delta: float, *, min_val: float = 0, max_val: float = 1
    ) -> float:
        """Adjust a range/slider binding by *delta* domain-scale units.

        Reads the current normalised value, denormalises it, adds *delta*,
        clamps, re-normalises, and calls :meth:`set`.

        Parameters
        ----------
        name
            Binding name (must be a ``range`` or ``slider`` binding).
        delta
            Amount to add in domain units (negative to decrease).
        min_val
            Lower bound of the domain range.
        max_val
            Upper bound of the domain range.

        Returns
        -------
        float
            The new value in domain units (clamped to
            ``[min_val, max_val]``), so callers can use it for display
            without back-computing.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        ValueError
            If *min_val* equals *max_val*.
        """
        if min_val == max_val:
            raise ValueError("min_val and max_val must not be equal")
        current_norm = float(self.get(name) or 0.0)
        current_domain = min_val + current_norm * (max_val - min_val)
        new_domain = max(min_val, min(max_val, current_domain + delta))
        normalised = (new_domain - min_val) / (max_val - min_val)
        self.set(name, normalised)
        return new_domain

    def get_range(
        self, name: str, *, min_val: float = 0, max_val: float = 1
    ) -> float:
        """Get a range/slider binding denormalised to domain units.

        Parameters
        ----------
        name
            Binding name.
        min_val
            Lower bound of the domain range.
        max_val
            Upper bound of the domain range.

        Returns
        -------
        float
            The current value in domain units.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        ValueError
            If *min_val* equals *max_val*.
        """
        if min_val == max_val:
            raise ValueError("min_val and max_val must not be equal")
        current_norm = float(self.get(name) or 0.0)
        return min_val + current_norm * (max_val - min_val)

    def on(self, event_name: str) -> Callable[[AsyncHandler], AsyncHandler]:
        """Decorator to register a handler for a named semantic event.

        Examples
        --------
        ::

            @card.on("toggle_play_pause")
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
    ) -> DuiCard:
        """Subscribe to *event*; on emit, write binding *name* and refresh.

        This fuses three operations that otherwise repeat across every
        controller: subscribe to a service ``AsyncEvent``, translate
        the emitted value into the binding's domain, and request a
        refresh.

        Without *transform*, the binding receives the first positional
        argument from the event (``args[0]``).  With *transform*, the
        callable is invoked with all event ``args``/``kwargs`` and its
        return value becomes the binding value.

        The subscriber lives for the lifetime of the card -- there is
        no automatic teardown.  Bind once during construction or
        :meth:`on_attach`-style lifecycle hooks.

        Parameters
        ----------
        name
            Binding name as defined in the manifest.
        event
            The :class:`~deckui.runtime.async_event.AsyncEvent` to
            subscribe to (e.g. a service's ``on_volume_changed``).
        transform
            Optional sync callable that maps event args to the binding
            value.  If ``None``, ``args[0]`` is used.

        Returns
        -------
        DuiCard
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
        return self

    def bind_range(
        self,
        name: str,
        event: AsyncEvent,
        *,
        min_val: float = 0,
        max_val: float = 1,
        transform: Callable[..., float] | None = None,
    ) -> DuiCard:
        """Subscribe to *event*; on emit, write binding *name* via :meth:`set_range`.

        Same shape as :meth:`bind`, but routes through :meth:`set_range`
        so the emitted value can be in domain units (e.g. a 0--100
        percentage).

        Parameters
        ----------
        name
            Binding name (must be a ``range`` or ``slider`` binding).
        event
            The :class:`~deckui.runtime.async_event.AsyncEvent` to
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
        DuiCard
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
        return self

    def bind_many(
        self,
        event: AsyncEvent,
        transform: Callable[..., dict[str, Any]],
    ) -> DuiCard:
        """Subscribe to *event*; transform args into a dict and :meth:`set_many` it.

        Use this when one event drives several bindings at once -- e.g.
        a ``track_changed`` event populating ``artist``, ``title``,
        ``album``, and ``state`` from a single track dict.

        Parameters
        ----------
        event
            The :class:`~deckui.runtime.async_event.AsyncEvent` to
            subscribe to.
        transform
            Required sync callable that maps event args to a dict of
            binding names to values.

        Returns
        -------
        DuiCard
            self, for method chaining.
        """

        async def _on_event(*args: Any, **kwargs: Any) -> None:
            values = transform(*args, **kwargs)
            self.set_many(**values)
            if self.is_dirty:
                await self.request_refresh()

        event.subscribe(_on_event)
        return self

    def forward(
        self,
        event_name: str,
        target: Callable[..., Any],
    ) -> DuiCard:
        """Register *target* as the handler for manifest event *event_name*.

        Sugar for the very common shape::

            @card.on("toggle")
            async def _h() -> None:
                await svc.toggle()

        which becomes::

            card.forward("toggle", svc.toggle)

        *target* may be an async function or any sync callable that
        returns an awaitable (e.g. a lambda whose body invokes an
        async method).  All positional and keyword arguments emitted
        by the event are forwarded to *target*.

        Parameters
        ----------
        event_name
            Semantic event name from the manifest.
        target
            Async-callable forwarding target.

        Returns
        -------
        DuiCard
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
        without ever triggering a render -- the user's display goes
        silently stale (e.g. brightness slider lagging behind rapid
        encoder spins).  Wrapping at the registration boundary makes
        every handler self-refreshing, regardless of how it's
        dispatched.

        The wrapper:

        * Is a no-op when no refresh callback is wired (i.e. before the
          card is installed on a screen).
        * Is idempotent when the handler already calls
          :meth:`request_refresh` itself -- the second call finds the
          card clean and skips re-rendering.
        """

        async def _wrapped(*args: Any, **kwargs: Any) -> None:
            await fn(*args, **kwargs)
            if self.is_dirty:
                await self.request_refresh()

        # Preserve the original for testing / introspection.
        _wrapped.__wrapped__ = fn  # type: ignore[attr-defined]
        return _wrapped

    def render(self) -> Image.Image:
        """Render the SVG layout with current bindings to a PIL Image.

        Returns
        -------
        Image.Image
            A panel-sized RGB :class:`~PIL.Image.Image` (sized from the
            ``.dui`` SVG's intrinsic dimensions).
        """
        return self._renderer.render()

    async def prepare_assets(self) -> None:
        """No-op — .dui cards manage their own assets via the SVG."""

    def handle_encoder_turn(self, direction: int) -> None:
        """Route encoder turn through the event map."""
        handler = self._events.handle_encoder_turn(direction)
        if handler is not None:
            self.queue_pending_callback(handler, (direction,))

    def handle_encoder_press(self) -> None:
        """Route encoder press through the event map."""
        for handler in self._events.handle_encoder_press():
            self.queue_pending_callback(handler, ())

    def handle_encoder_release(self) -> None:
        """Route encoder release through the event map."""
        for handler in self._events.handle_encoder_release():
            self.queue_pending_callback(handler, ())

    async def dispatch_touch(self, event: TouchEvent) -> None:
        """Dispatch touch events through regions and the event map.

        Falls back to the base Card touch handlers (on_tap, etc.)
        if the event map doesn't handle the event.
        """
        handler = self._events.handle_touch(event.event_type, event.x, event.y)
        if handler is not None:
            await handler()
        else:
            await super().dispatch_touch(event)

    async def start_busy(self) -> None:
        """Enter the busy state and start the spinner animation.

        While busy, the card suppresses further ``start_busy()`` calls.
        The spinner keeps running until :meth:`finish_busy` is called.

        If no spinner is configured in the manifest the busy flag is
        still set (suppressing duplicate calls) but no animation plays.
        """
        if self._busy:
            return
        self._busy = True
        await self._start_spinner()

    async def finish_busy(self) -> None:
        """Stop the spinner and exit the busy state.

        Call this from your application code when the asynchronous
        work is truly complete (e.g. after receiving a state update
        from an external system).

        If the card is not currently busy this is a no-op.
        """
        if not self._busy:
            return
        await self._stop_spinner()
        self._busy = False
        self.mark_dirty()

    async def _start_spinner(self) -> None:
        """Start the spinner animation if configured."""
        if (
            self._spec.spinner is None
            or self._push_fn is None
            or self._panel_size is None
        ):
            return

        width, height = self._panel_size
        rendered_svg = self._renderer.render_svg()
        self._spinner_frames = SpinnerFrames(
            self._spec,
            width=width,
            height=height,
            rendered_svg=rendered_svg,
            bg_tile=self._bg_tile,
        )

        self._animator = SpinnerAnimator(
            frames=self._spinner_frames.frames,
            interval_ms=self._spinner_frames.interval_ms,
            push_fn=self._push_fn,
        )
        await self._animator.start()

    async def _stop_spinner(self) -> None:
        """Stop the spinner animation."""
        if self._animator is not None:
            await self._animator.stop()
            self._animator = None

    def cleanup(self) -> None:
        """Cancel pending accumulators and release resources."""
        self._events.cancel_accumulators()
