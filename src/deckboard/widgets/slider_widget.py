"""SliderWidget — a widget zone composed of one or more Slider sub-elements."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PIL import Image

from ..image import WIDGET_HEIGHT, WIDGET_WIDTH
from ..touchscreen import Widget

if TYPE_CHECKING:
    from .slider import Slider


class SliderWidget(Widget):
    """A widget that displays one or more :class:`Slider` sub-elements.

    Sliders stack vertically within the widget zone.  When multiple
    sliders are present, the dial push cycles through them (highlighted
    with a blue frame), and an inactivity timeout reverts to the default.

    Usage::

        from deckboard.widgets import VolumeSlider, BrightnessSlider, SliderWidget

        sw = SliderWidget(0)
        sw.add_slider(VolumeSlider("Volume", value=75), default=True)
        sw.add_slider(BrightnessSlider("Bright", value=50))
    """

    def __init__(self, index: int) -> None:
        super().__init__(index)
        self._sliders: list[Slider] = []
        self._active_slider_index: int = 0
        self._default_slider_index: int = 0
        self._selection_timeout: float = 5.0
        self._last_selection_time: float | None = None

    # -- Slider management -------------------------------------------------

    def add_slider(self, slider: Slider, default: bool = False) -> SliderWidget:
        """Add a slider sub-element to this widget zone.

        Args:
            slider: A :class:`Slider` instance to display in this zone.
            default: If ``True``, this slider becomes the default
                (the one selected after timeout).

        Returns:
            This widget (for chaining).
        """
        from .slider import Slider as _Slider

        if not isinstance(slider, _Slider):
            msg = f"Expected a Slider instance, got {type(slider).__name__}"
            raise TypeError(msg)
        slider._widget = self
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

    def set_selection_timeout(self, seconds: float) -> SliderWidget:
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

    # -- Widget hooks (override base class no-ops) -------------------------

    def handle_dial_turn(self, direction: int) -> None:
        """Adjust the active slider's value by *direction* steps.

        Marks the widget dirty so the next render reflects the change.
        Also resets the selection timeout so the active slider doesn't
        revert to the default while the user is still interacting.
        """
        if self._sliders:
            self._sliders[self._active_slider_index].adjust(direction)
            if self._active_slider_index != self._default_slider_index:
                self._last_selection_time = time.monotonic()
            self._dirty = True

    def handle_dial_press(self) -> None:
        """Cycle to the next slider.  Called on dial push."""
        self.cycle_active_slider()

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

    # -- Rendering ---------------------------------------------------------

    def render(self) -> Image.Image:
        """Compose all slider sub-elements into a single widget image.

        Returns:
            A WIDGET_WIDTH x WIDGET_HEIGHT RGB :class:`~PIL.Image.Image`.
        """
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        if not self._sliders:
            return img

        self.check_selection_timeout()

        count = len(self._sliders)
        slot_height = WIDGET_HEIGHT // count
        for i, slider in enumerate(self._sliders):
            y = i * slot_height
            active = i == self._active_slider_index and count > 1
            slider.render_onto(
                img, x=0, y=y, width=WIDGET_WIDTH, height=slot_height, active=active
            )
        return img
