"""Abstract base card for a single touch-strip zone under an encoder."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ...runtime.events import AsyncHandler, EventType, TouchEvent

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


class Card(ABC):
    """Abstract base for a single touch-strip zone under an encoder.

    The touchscreen is divided into zones aligned with the device's
    encoders.  A margin is applied around the usable area and cards
    are separated by a gap.  The exact dimensions depend on the
    connected device (e.g. 197x98 per zone on Stream Deck+).

    Subclass this to build custom widgets.  At minimum, implement
    :meth:`render`.  Override the ``handle_encoder_*`` and
    ``check_selection_timeout`` hooks to react to encoder events.

    Examples
    --------
    ::

        class MyCard(Card):
            def render(self) -> Image.Image:
                img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
                # ... draw custom content ...
                return img

    Event handlers are registered with decorators::

        @card.on_tap
        async def handle():
            print("Card tapped!")
    """

    def __init__(self, index: int) -> None:
        self._index = index
        self._tap_handler: AsyncHandler | None = None
        self._long_press_handler: AsyncHandler | None = None
        self._drag_handler: AsyncHandler | None = None
        self._encoder_turn_handler: AsyncHandler | None = None
        self._encoder_press_handler: AsyncHandler | None = None
        self._encoder_release_handler: AsyncHandler | None = None
        self._pending_callbacks: list[tuple[AsyncHandler, tuple[object, ...]]] = []
        self._rendered: Image.Image | None = None
        self._dirty = True
        self._request_refresh: AsyncHandler | None = None

    @property
    def index(self) -> int:
        return self._index

    def on_tap(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for short tap events in this zone.

        Examples
        --------
        ::

            @widget.on_tap
            async def handle():
                ...
        """
        self._tap_handler = handler
        return handler

    def on_long_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for long press events in this zone.

        Examples
        --------
        ::

            @widget.on_long_press
            async def handle():
                ...
        """
        self._long_press_handler = handler
        return handler

    def on_drag(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for drag/swipe events in this zone.

        The handler receives ``x``, ``y``, ``x_out``, ``y_out`` arguments
        describing the start and end coordinates of the drag gesture.

        Examples
        --------
        ::

            @widget.on_drag
            async def handle(x: int, y: int, x_out: int, y_out: int):
                ...
        """
        self._drag_handler = handler
        return handler

    def on_encoder_turn(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for encoder turn events on this widget.

        The handler receives a single ``direction`` argument:
        positive = clockwise, negative = counter-clockwise.

        Examples
        --------
        ::

            @widget.on_encoder_turn
            async def handle(direction: int):
                ...
        """
        self._encoder_turn_handler = handler
        return handler

    def on_encoder_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for encoder press events on this widget.

        Examples
        --------
        ::

            @widget.on_encoder_press
            async def handle():
                ...
        """
        self._encoder_press_handler = handler
        return handler

    def on_encoder_release(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for encoder release events on this widget.

        Examples
        --------
        ::

            @widget.on_encoder_release
            async def handle():
                ...
        """
        self._encoder_release_handler = handler
        return handler

    def set_refresh_callback(self, callback: AsyncHandler) -> None:
        """Register an async callback the card can invoke to request a refresh.

        This is set automatically by :class:`~deckui.runtime.deck.Deck`
        when dispatching events so that cards with internal timers (e.g.
        long-press detection) can trigger a re-render without a direct
        reference to the deck.
        """
        self._request_refresh = callback

    async def request_refresh(self) -> None:
        """Ask the deck to re-render this card.

        No-op if no refresh callback has been registered.
        """
        if self._request_refresh is not None:
            await self._request_refresh()

    def queue_pending_callback(
        self, handler: AsyncHandler, args: tuple[object, ...]
    ) -> None:
        """Enqueue a callback for deferred async invocation.

        Called by child elements (e.g. sliders) when their value changes
        synchronously.  The queued callbacks are drained and awaited by
        :class:`~deckui.runtime.deck.Deck` during event dispatch or refresh.

        Parameters
        ----------
        handler
            The async callback to invoke.
        args
            Positional arguments to pass to the callback.
        """
        self._pending_callbacks.append((handler, args))

    def drain_pending_callbacks(self) -> list[tuple[AsyncHandler, tuple[object, ...]]]:
        """Remove and return all pending callbacks.

        Returns
        -------
        list[tuple[AsyncHandler, tuple[object, ...]]]
            A list of ``(handler, args)`` tuples.  The list is empty if
            no callbacks are pending.
        """
        callbacks = self._pending_callbacks
        self._pending_callbacks = []
        return callbacks

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    def mark_dirty(self) -> None:
        """Flag this card for re-rendering on the next refresh."""
        self._dirty = True

    @property
    def rendered(self) -> Image.Image | None:
        return self._rendered

    def set_rendered(self, img: Image.Image | None) -> None:
        self._rendered = img
        self._dirty = False

    async def prepare_assets(self) -> None:
        """Prepare external assets needed for rendering this card."""
        return None

    async def dispatch_encoder_turn(self, direction: int) -> None:
        """Dispatch an encoder-turn event to the card."""
        if self._encoder_turn_handler is not None:
            await self._encoder_turn_handler(direction)
        self.handle_encoder_turn(direction)

    async def dispatch_encoder_press(self) -> None:
        """Dispatch an encoder-press event to the card."""
        if self._encoder_press_handler is not None:
            await self._encoder_press_handler()
        self.handle_encoder_press()

    async def dispatch_encoder_release(self) -> None:
        """Dispatch an encoder-release event to the card."""
        if self._encoder_release_handler is not None:
            await self._encoder_release_handler()
        self.handle_encoder_release()

    async def dispatch_touch(self, event: TouchEvent) -> None:
        """Dispatch a touch gesture to the card."""
        if event.event_type == EventType.TOUCH_SHORT:
            if self._tap_handler is not None:
                await self._tap_handler()
        elif event.event_type == EventType.TOUCH_LONG:
            if self._long_press_handler is not None:
                await self._long_press_handler()
        elif (
            event.event_type == EventType.TOUCH_DRAG and self._drag_handler is not None
        ):
            await self._drag_handler(event.x, event.y, event.x_out, event.y_out)

    @abstractmethod
    def render(self) -> Image.Image | None:
        """Render this card as a PANEL_WIDTH x PANEL_HEIGHT PIL Image.

        Return ``None`` to let the touchstrip background colour show
        through (used by :class:`~deckui.ui.cards.blank.BlankCard`).

        Returns
        -------
        Image.Image or None
            A PANEL_WIDTH x PANEL_HEIGHT RGB :class:`~PIL.Image.Image`,
            or ``None`` for a transparent/empty slot.
        """

    def handle_encoder_turn(self, direction: int) -> None:
        """Called when the encoder above this widget is turned.

        Override to handle encoder rotation.  The default is a no-op.
        """
        _ = direction
        return None

    def handle_encoder_press(self) -> None:
        """Called when the encoder above this widget is pressed.

        Override to handle encoder presses.  The default is a no-op.
        """
        return None

    def handle_encoder_release(self) -> None:
        """Called when the encoder above this widget is released.

        Override to handle encoder releases.  The default is a no-op.
        """
        return None

    def check_selection_timeout(self) -> bool:
        """Check whether an internal selection timeout has elapsed.

        Override to implement timeout logic (e.g. for slider cycling).
        The default always returns ``False``.

        Returns
        -------
        bool
            ``True`` if the widget state changed and needs re-rendering.
        """
        return False
