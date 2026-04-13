"""DsuiCard: a touchscreen card backed by a .dsui package."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from PIL import Image

from ..runtime.events import AsyncHandler, EventType, TouchEvent
from ..ui.cards.base import Card
from .event_map import EventMap
from .svg_renderer import SvgRenderer

if TYPE_CHECKING:
    from .schema import PackageSpec

logger = logging.getLogger(__name__)


class DsuiCard(Card):
    """A touchscreen card whose layout and events are defined by a .dsui package.

    Instead of writing a Python class with imperative Pillow rendering,
    you describe the UI in an SVG layout and a YAML manifest.  The card
    loads the package, lets you set binding values, and renders the SVG
    into a PIL Image for the Stream Deck+ touchscreen.

    Usage::

        from deckboard.dsui import load_package, DsuiCard

        spec = load_package("./AudioCard.dsui")
        card = DsuiCard(0, spec)
        card.set("artist", "Ash Walker")

        @card.on("toggle_play_pause")
        async def handle():
            ...

    Args:
        index: Touch-strip zone index (0-3).
        spec: A validated :class:`~deckboard.dsui.schema.PackageSpec`.
    """

    def __init__(self, index: int, spec: PackageSpec) -> None:
        super().__init__(index)
        self._spec = spec
        self._renderer = SvgRenderer(spec)
        self._events = EventMap(spec.events, spec.regions)

    @property
    def spec(self) -> PackageSpec:
        """The package specification backing this card."""
        return self._spec

    # -- Data binding API --------------------------------------------------

    def set(self, name: str, value: Any) -> DsuiCard:
        """Set a binding value.  Marks the card dirty if changed.

        Args:
            name: Binding name as defined in the manifest.
            value: New value (type depends on binding kind).

        Returns:
            self, for method chaining.

        Raises:
            KeyError: If *name* is not a known binding.
        """
        if self._renderer.set(name, value):
            self.mark_dirty()
        return self

    def set_many(self, **kwargs: Any) -> DsuiCard:
        """Set multiple binding values at once.

        Returns:
            self, for method chaining.
        """
        if self._renderer.set_many(**kwargs):
            self.mark_dirty()
        return self

    def get(self, name: str) -> Any:
        """Get the current value of a binding.

        Raises:
            KeyError: If *name* is not a known binding.
        """
        return self._renderer.get(name)

    # -- Semantic event API ------------------------------------------------

    def on(self, event_name: str) -> Callable[[AsyncHandler], AsyncHandler]:
        """Decorator to register a handler for a named semantic event.

        Usage::

            @card.on("toggle_play_pause")
            async def handle():
                ...

        Args:
            event_name: Semantic event name from the manifest.

        Returns:
            A decorator that registers the handler and returns it unchanged.
        """

        def decorator(fn: AsyncHandler) -> AsyncHandler:
            self._events.on(event_name, fn)
            return fn

        return decorator

    def bind_event(self, event_name: str, handler: AsyncHandler) -> None:
        """Imperatively register a handler for a named semantic event.

        Args:
            event_name: Semantic event name from the manifest.
            handler: The async callable to invoke.
        """
        self._events.on(event_name, handler)

    # -- Card protocol: rendering ------------------------------------------

    def render(self) -> Image.Image:
        """Render the SVG layout with current bindings to a PIL Image.

        Returns:
            A PANEL_WIDTH x PANEL_HEIGHT RGB :class:`~PIL.Image.Image`.
        """
        return self._renderer.render()

    async def prepare_assets(self) -> None:
        """No-op — .dsui cards manage their own assets via the SVG."""

    # -- Card protocol: encoder event hooks --------------------------------

    def handle_encoder_turn(self, direction: int) -> None:
        """Route encoder turn through the event map."""
        handler = self._events.handle_encoder_turn(direction)
        if handler is not None:
            self.queue_pending_callback(handler, ())

    def handle_encoder_press(self) -> None:
        """Route encoder press through the event map."""
        for handler in self._events.handle_encoder_press():
            self.queue_pending_callback(handler, ())

    def handle_encoder_release(self) -> None:
        """Route encoder release through the event map."""
        for handler in self._events.handle_encoder_release():
            self.queue_pending_callback(handler, ())

    # -- Card protocol: touch event dispatch override ----------------------

    async def dispatch_touch(self, event: TouchEvent) -> None:
        """Dispatch touch events through regions and the event map.

        Falls back to the base Card touch handlers (on_tap, etc.)
        if the event map doesn't handle the event.
        """
        handler = self._events.handle_touch(event.event_type, event.x, event.y)
        if handler is not None:
            await handler()
        else:
            # Fall back to base Card touch handling
            await super().dispatch_touch(event)
