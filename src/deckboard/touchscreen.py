"""Touchscreen and Widget classes for the Stream Deck+ LCD strip."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PIL import Image

from .image import WIDGET_COUNT, render_widget_image
from .types import AsyncHandler

if TYPE_CHECKING:
    from .widgets.slider import Slider

logger = logging.getLogger(__name__)


class Widget:
    """Represents a single touchscreen zone (200x100px) under a dial.

    The Stream Deck+ touchscreen (800x100) is divided into 4 zones,
    each aligned with one of the 4 dials.

    Usage::

        widget.set_icon("mdi:volume-high")
        widget.set_label("Volume")
        widget.set_value("75%")

        @widget.on_tap
        async def handle():
            print("Widget tapped!")
    """

    def __init__(self, index: int) -> None:
        self._index = index
        self._icon_name: str | None = None
        self._icon_color: str = "white"
        self._label: str | None = None
        self._value: str | None = None
        self._tap_handler: AsyncHandler | None = None
        self._long_press_handler: AsyncHandler | None = None
        self._drag_handler: AsyncHandler | None = None
        self._rendered: Image.Image | None = None
        self._dirty = True

        # Slider sub-elements
        self._sliders: list[Slider] = []
        self._active_slider_index: int = 0
        self._default_slider_index: int = 0
        self._selection_timeout: float = 5.0
        self._last_selection_time: float | None = None

    @property
    def index(self) -> int:
        return self._index

    # -- Configuration methods (return self for chaining) ------------------

    def set_icon(self, name: str, color: str = "white") -> Widget:
        """Set the icon by Iconify name.

        Args:
            name: Icon name in ``prefix:name`` format.
            color: Icon color. Defaults to white.
        """
        self._icon_name = name
        self._icon_color = color
        self._dirty = True
        return self

    def set_label(self, label: str | None) -> Widget:
        """Set the primary text label."""
        self._label = label
        self._dirty = True
        return self

    def set_value(self, value: str | None) -> Widget:
        """Set the secondary value text."""
        self._value = value
        self._dirty = True
        return self

    def clear(self) -> Widget:
        """Clear all content from this widget zone."""
        self._icon_name = None
        self._label = None
        self._value = None
        self._rendered = None
        self._dirty = True
        return self

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

    # -- Internal ----------------------------------------------------------

    @property
    def icon_name(self) -> str | None:
        return self._icon_name

    @property
    def icon_color(self) -> str:
        return self._icon_color

    @property
    def label(self) -> str | None:
        return self._label

    @property
    def value(self) -> str | None:
        return self._value

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    @property
    def rendered(self) -> Image.Image | None:
        return self._rendered

    def set_rendered(self, img: Image.Image) -> None:
        self._rendered = img
        self._dirty = False

    # -- Slider sub-element management -------------------------------------

    def add_slider(self, slider: Slider, default: bool = False) -> Widget:
        """Add a slider sub-element to this widget zone.

        Args:
            slider: A :class:`Slider` instance to display in this zone.
            default: If ``True``, this slider becomes the default
                (the one selected after timeout).

        Returns:
            This widget (for chaining).
        """
        from .widgets.slider import Slider as _Slider

        if not isinstance(slider, _Slider):
            msg = f"Expected a Slider instance, got {type(slider).__name__}"
            raise TypeError(msg)
        self._sliders.append(slider)
        idx = len(self._sliders) - 1
        if default or idx == 0:
            self._default_slider_index = idx
            self._active_slider_index = idx
        self._dirty = True
        return self

    @property
    def sliders(self) -> list[Slider]:
        """All slider sub-elements in this widget zone."""
        return list(self._sliders)

    @property
    def active_slider(self) -> Slider | None:
        """The slider currently controlled by the dial, or ``None``."""
        if not self._sliders:
            return None
        return self._sliders[self._active_slider_index]

    @property
    def active_slider_index(self) -> int:
        """Index of the currently active slider."""
        return self._active_slider_index

    @property
    def selection_timeout(self) -> float:
        """Seconds before active slider resets to the default."""
        return self._selection_timeout

    def set_selection_timeout(self, seconds: float) -> Widget:
        """Set how long before active slider resets to the default.

        Args:
            seconds: Timeout in seconds.  Use ``0`` to disable.
        """
        self._selection_timeout = max(0.0, seconds)
        return self

    def cycle_active_slider(self) -> None:
        """Advance to the next slider (wrapping around).

        Called on dial push.  Marks the widget dirty so the highlight
        redraws on the next render.
        """
        if len(self._sliders) <= 1:
            return
        self._active_slider_index = (self._active_slider_index + 1) % len(self._sliders)
        self._last_selection_time = time.monotonic()
        self._dirty = True

    def check_selection_timeout(self) -> bool:
        """Reset to the default slider if the timeout has elapsed.

        Returns:
            ``True`` if the active slider changed (widget is now dirty).
        """
        if (
            self._selection_timeout <= 0
            or self._last_selection_time is None
            or self._active_slider_index == self._default_slider_index
        ):
            return False
        elapsed = time.monotonic() - self._last_selection_time
        if elapsed >= self._selection_timeout:
            self._active_slider_index = self._default_slider_index
            self._last_selection_time = None
            self._dirty = True
            return True
        return False

    def handle_dial_turn(self, direction: int) -> None:
        """Adjust the active slider's value by *direction* steps.

        Marks the widget dirty so the next render reflects the change.
        """
        if self._sliders:
            self._sliders[self._active_slider_index].adjust(direction)
            self._dirty = True

    def handle_dial_press(self) -> None:
        """Cycle to the next slider.  Called on dial push."""
        self.cycle_active_slider()

    # -- Rendering ---------------------------------------------------------

    def render(self, icon: Image.Image | None = None) -> Image.Image:
        """Render this widget zone as a 200x100 PIL Image.

        If sliders have been added via :meth:`add_slider`, they are
        rendered instead of the default icon/label/value layout.

        Args:
            icon: Pre-fetched icon image (used by the classic layout).

        Returns:
            A 200x100 RGB :class:`~PIL.Image.Image`.
        """
        if self._sliders:
            return self._render_with_sliders()
        return render_widget_image(
            icon=icon,
            label=self._label,
            value=self._value,
        )

    def _render_with_sliders(self) -> Image.Image:
        """Compose all slider sub-elements into a single widget image."""
        from .image import TOUCHSCREEN_HEIGHT, WIDGET_WIDTH

        img = Image.new("RGB", (WIDGET_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        if not self._sliders:
            return img

        self.check_selection_timeout()

        count = len(self._sliders)
        slot_height = TOUCHSCREEN_HEIGHT // count
        for i, slider in enumerate(self._sliders):
            y = i * slot_height
            active = i == self._active_slider_index and count > 1
            slider.render_onto(
                img, x=0, y=y, width=WIDGET_WIDTH, height=slot_height, active=active
            )
        return img


class TouchScreen:
    """Manages the 4 widget zones on the Stream Deck+ touchscreen."""

    def __init__(self) -> None:
        self._widgets: list[Widget] = [Widget(i) for i in range(WIDGET_COUNT)]

    def widget(self, index: int) -> Widget:
        """Get a widget zone by index (0-3)."""
        if not 0 <= index < WIDGET_COUNT:
            raise IndexError(f"Widget index must be 0-{WIDGET_COUNT - 1}, got {index}")
        return self._widgets[index]

    @property
    def widgets(self) -> list[Widget]:
        return self._widgets

    @property
    def any_dirty(self) -> bool:
        return any(w.is_dirty for w in self._widgets)
