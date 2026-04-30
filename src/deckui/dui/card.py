"""DuiCard: a touchscreen card backed by a .dui package."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..ui.cards.base import Card
from .animator import PushFn, SpinnerAnimator
from .event_map import EventMap
from .spinner import SpinnerFrames
from .svg_renderer import SvgRenderer

if TYPE_CHECKING:
    from collections.abc import Callable

    from PIL import Image

    from ..runtime.events import AsyncHandler, TouchEvent
    from .schema import PackageSpec

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

        from deckui.dui import load_package, DuiCard

        spec = load_package("./AudioCard.dui")
        card = DuiCard(spec)
        card.set("artist", "Ash Walker")

        @card.on("toggle_play_pause")
        async def handle():
            ...

    The card index is assigned automatically when you install the card
    on a screen with :meth:`~deckui.ui.screen.Screen.set_card`.

    Parameters
    ----------
    spec
        A validated :class:`~deckui.dui.schema.PackageSpec`.
    """

    def __init__(self, spec: PackageSpec) -> None:
        super().__init__(-1)
        self._spec = spec
        self._renderer = SvgRenderer(spec)
        self._events = EventMap(spec.events, spec.regions)
        self._busy = False
        self._animator: SpinnerAnimator | None = None
        self._spinner_frames: SpinnerFrames | None = None
        self._push_fn: PushFn | None = None

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

    def set_push_fn(self, push_fn: PushFn) -> None:
        """Set the async function used to push animation frames to the device.

        This must be called before spinner animations can play.
        Typically set by :class:`~deckui.runtime.deck.Deck`.

        Parameters
        ----------
        push_fn
            Async callable ``(frame_bytes) -> None``.
        """
        self._push_fn = push_fn

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
            A PANEL_WIDTH x PANEL_HEIGHT RGB :class:`~PIL.Image.Image`.
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
        if self._spec.spinner is None or self._push_fn is None:
            return

        from ..render.metrics import PANEL_HEIGHT, PANEL_WIDTH

        rendered_svg = self._renderer.render_svg()
        self._spinner_frames = SpinnerFrames(
            self._spec,
            width=PANEL_WIDTH,
            height=PANEL_HEIGHT,
            rendered_svg=rendered_svg,
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
