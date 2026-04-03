"""Touchscreen and Widget classes for the Stream Deck+ LCD strip."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from PIL import Image

from .image import WIDGET_COUNT, WIDGET_HEIGHT, WIDGET_WIDTH
from .types import AsyncHandler

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Widget(ABC):
    """Abstract base for a single touchscreen zone (195x78px) under a dial.

    The Stream Deck+ touchscreen (800x100) is divided into 4 zones,
    each aligned with one of the 4 dials.  A margin is applied around
    the usable area (top=4, bottom=18, left=4, right=4) and widgets
    are separated by a 4px gap, giving each zone 195x78 usable pixels.

    Subclass this to build custom widgets.  At minimum, implement
    :meth:`render`.  Override the ``handle_dial_*`` and
    ``check_selection_timeout`` hooks to react to dial events.

    Usage::

        class MyWidget(Widget):
            def render(self) -> Image.Image:
                img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
                # ... draw custom content ...
                return img

    Event handlers are registered with decorators::

        @widget.on_tap
        async def handle():
            print("Widget tapped!")
    """

    def __init__(self, index: int) -> None:
        self._index = index
        self._tap_handler: AsyncHandler | None = None
        self._long_press_handler: AsyncHandler | None = None
        self._drag_handler: AsyncHandler | None = None
        self._dial_turn_handler: AsyncHandler | None = None
        self._dial_press_handler: AsyncHandler | None = None
        self._pending_callbacks: list[tuple[AsyncHandler, tuple[float]]] = []
        self._rendered: Image.Image | None = None
        self._dirty = True

    @property
    def index(self) -> int:
        return self._index

    # -- Decorator-based event registration --------------------------------

    def on_tap(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for short tap events in this zone.

        Usage::

            @widget.on_tap
            async def handle():
                ...
        """
        self._tap_handler = handler
        return handler

    def on_long_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for long press events in this zone.

        Usage::

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

        Usage::

            @widget.on_drag
            async def handle(x: int, y: int, x_out: int, y_out: int):
                ...
        """
        self._drag_handler = handler
        return handler

    def on_dial_turn(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for dial turn events on this widget.

        The handler receives a single ``direction`` argument:
        positive = clockwise, negative = counter-clockwise.

        Usage::

            @widget.on_dial_turn
            async def handle(direction: int):
                ...
        """
        self._dial_turn_handler = handler
        return handler

    def on_dial_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for dial press events on this widget.

        Usage::

            @widget.on_dial_press
            async def handle():
                ...
        """
        self._dial_press_handler = handler
        return handler

    # -- Pending callbacks (deferred async invocation) ---------------------

    def queue_pending_callback(self, handler: AsyncHandler, args: tuple[float]) -> None:
        """Enqueue a callback for deferred async invocation.

        Called by child elements (e.g. sliders) when their value changes
        synchronously.  The queued callbacks are drained and awaited by
        :class:`~deckboard.deck.Deck` during event dispatch or refresh.

        Args:
            handler: The async callback to invoke.
            args: Positional arguments to pass to the callback.
        """
        self._pending_callbacks.append((handler, args))

    def drain_pending_callbacks(self) -> list[tuple[AsyncHandler, tuple[float]]]:
        """Remove and return all pending callbacks.

        Returns:
            A list of ``(handler, args)`` tuples.  The list is empty if
            no callbacks are pending.
        """
        callbacks = self._pending_callbacks
        self._pending_callbacks = []
        return callbacks

    # -- Dirty tracking ----------------------------------------------------

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    def mark_dirty(self) -> None:
        """Flag this widget for re-rendering on the next refresh."""
        self._dirty = True

    @property
    def rendered(self) -> Image.Image | None:
        return self._rendered

    def set_rendered(self, img: Image.Image) -> None:
        self._rendered = img
        self._dirty = False

    # -- Rendering (abstract) ----------------------------------------------

    @abstractmethod
    def render(self) -> Image.Image:
        """Render this widget zone as a WIDGET_WIDTH x WIDGET_HEIGHT PIL Image.

        Returns:
            A WIDGET_WIDTH x WIDGET_HEIGHT RGB :class:`~PIL.Image.Image`.
        """

    # -- Dial interaction hooks (default no-ops) ---------------------------

    def handle_dial_turn(self, direction: int) -> None:
        """Called when the dial above this widget is turned.

        Override to handle dial rotation.  The default is a no-op.
        """

    def handle_dial_press(self) -> None:
        """Called when the dial above this widget is pressed.

        Override to handle dial presses.  The default is a no-op.
        """

    def check_selection_timeout(self) -> bool:
        """Check whether an internal selection timeout has elapsed.

        Override to implement timeout logic (e.g. for slider cycling).
        The default always returns ``False``.

        Returns:
            ``True`` if the widget state changed and needs re-rendering.
        """
        return False


class TouchScreen:
    """Manages the 4 widget zones on the Stream Deck+ touchscreen."""

    def __init__(self) -> None:
        # Import here to avoid circular imports at module level
        from .widgets.icon_widget import IconWidget

        self._widgets: list[Widget] = [IconWidget(i) for i in range(WIDGET_COUNT)]

    def widget(self, index: int) -> Widget:
        """Get a widget zone by index (0-3)."""
        if not 0 <= index < WIDGET_COUNT:
            raise IndexError(f"Widget index must be 0-{WIDGET_COUNT - 1}, got {index}")
        return self._widgets[index]

    def set_widget(self, index: int, widget: Widget) -> None:
        """Replace the widget at *index* with a custom widget.

        Args:
            index: Widget zone index (0-3).
            widget: A :class:`Widget` subclass instance.

        Raises:
            IndexError: If *index* is out of range.
            TypeError: If *widget* is not a :class:`Widget` instance.
        """
        if not 0 <= index < WIDGET_COUNT:
            raise IndexError(f"Widget index must be 0-{WIDGET_COUNT - 1}, got {index}")
        if not isinstance(widget, Widget):
            msg = f"Expected a Widget instance, got {type(widget).__name__}"
            raise TypeError(msg)
        self._widgets[index] = widget

    @property
    def widgets(self) -> list[Widget]:
        return self._widgets

    @property
    def any_dirty(self) -> bool:
        return any(w.is_dirty for w in self._widgets)
