"""TouchPanel — a widget zone composed of stacked sub-elements (sliders, text, etc.)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Union

from PIL import Image

from ..image import WIDGET_HEIGHT, WIDGET_WIDTH
from ..touchscreen import Widget

if TYPE_CHECKING:
    from .dual_value import LargeDualValue, SmallDualValue
    from .slider import Slider
    from .text import LargeText, SmallText

# Union of all element types that can be placed inside a TouchPanel.
PanelElement = Union[
    "Slider", "LargeText", "SmallText", "LargeDualValue", "SmallDualValue"
]


class TouchPanel(Widget):
    """A widget that displays stacked sub-elements (sliders, text, etc.).

    Elements are laid out vertically within the widget zone.  Only
    *selectable* elements (e.g. sliders) participate in dial-press
    cycling; non-selectable elements (e.g. text) are rendered but
    skipped when the user pushes the dial.

    Usage::

        from deckboard.widgets import (
            VolumeSlider, BrightnessSlider, LargeText, TouchPanel,
        )

        panel = TouchPanel(0)
        panel.add_element(LargeText("Now Playing"))
        panel.add_element(VolumeSlider("Volume", value=75))
        panel.add_element(BrightnessSlider("Bright", value=50))
    """

    def __init__(self, index: int) -> None:
        super().__init__(index)
        self._elements: list[PanelElement] = []
        self._active_slider_index: int = 0
        self._default_slider_index: int = 0
        self._selection_timeout: float = 5.0
        self._last_selection_time: float | None = None

    # -- Helpers -----------------------------------------------------------

    def _selectable_indices(self) -> list[int]:
        """Return indices into ``_elements`` for selectable entries only."""
        return [
            i for i, e in enumerate(self._elements) if getattr(e, "selectable", True)
        ]

    # -- Element management ------------------------------------------------

    def add_element(
        self, element: PanelElement, *, default: bool = False
    ) -> TouchPanel:
        """Add a sub-element (slider, text, or dual-value) to this panel.

        Args:
            element: A :class:`Slider`, :class:`LargeText`,
                :class:`SmallText`, :class:`LargeDualValue`, or
                :class:`SmallDualValue` instance.
            default: If ``True`` **and** the element is selectable, it
                becomes the default active element after timeout.

        Returns:
            This panel (for chaining).
        """
        from .dual_value import LargeDualValue as _LargeDualValue
        from .dual_value import SmallDualValue as _SmallDualValue
        from .slider import Slider as _Slider
        from .text import LargeText as _LargeText
        from .text import SmallText as _SmallText

        if not isinstance(
            element,
            (_Slider, _LargeText, _SmallText, _LargeDualValue, _SmallDualValue),
        ):
            msg = (
                f"Expected a Slider, LargeText, SmallText, LargeDualValue, "
                f"or SmallDualValue instance, got {type(element).__name__}"
            )
            raise TypeError(msg)

        element._widget = self  # type: ignore[union-attr]
        self._elements.append(element)

        # Update selectable tracking
        selectable = self._selectable_indices()
        if selectable and getattr(element, "selectable", True):
            idx = selectable[-1]  # the one we just added
            if default or len(selectable) == 1:
                self._default_slider_index = idx
                self._active_slider_index = idx

        self._dirty = True
        return self

    def add_slider(self, slider: Slider, default: bool = False) -> TouchPanel:
        """Add a slider sub-element to this panel.

        This is a convenience wrapper around :meth:`add_element`
        that validates the type is a :class:`Slider`.

        Args:
            slider: A :class:`Slider` instance.
            default: If ``True``, this slider becomes the default.

        Returns:
            This panel (for chaining).
        """
        from .slider import Slider as _Slider

        if not isinstance(slider, _Slider):
            msg = f"Expected a Slider instance, got {type(slider).__name__}"
            raise TypeError(msg)
        return self.add_element(slider, default=default)

    @property
    def elements(self) -> list[PanelElement]:
        """All sub-elements in this panel."""
        return list(self._elements)

    @property
    def sliders(self) -> list[Slider]:
        """All slider sub-elements in this panel (excluding text)."""
        from .slider import Slider as _Slider

        return [e for e in self._elements if isinstance(e, _Slider)]

    @property
    def active_slider(self) -> Slider | None:
        """The slider currently controlled by the dial, or ``None``."""
        from .slider import Slider as _Slider

        selectable = self._selectable_indices()
        if not selectable:
            return None
        idx = self._active_slider_index
        if idx < len(self._elements) and isinstance(self._elements[idx], _Slider):
            return self._elements[idx]
        return None

    @property
    def active_slider_index(self) -> int:
        """Index (into :attr:`elements`) of the currently active slider."""
        return self._active_slider_index

    @property
    def selection_timeout(self) -> float:
        """Seconds before active slider resets to the default."""
        return self._selection_timeout

    def set_selection_timeout(self, seconds: float) -> TouchPanel:
        """Set how long before active slider resets to the default.

        Args:
            seconds: Timeout in seconds.  Use ``0`` to disable.
        """
        self._selection_timeout = max(0.0, seconds)
        return self

    def cycle_active_slider(self) -> None:
        """Advance to the next selectable element (wrapping around).

        Called on dial push.  Non-selectable elements (text) are
        skipped.  Marks the widget dirty so the highlight redraws.
        """
        selectable = self._selectable_indices()
        if len(selectable) <= 1:
            return

        # Find current position in the selectable list
        try:
            pos = selectable.index(self._active_slider_index)
        except ValueError:
            pos = 0
        next_pos = (pos + 1) % len(selectable)
        self._active_slider_index = selectable[next_pos]
        self._last_selection_time = time.monotonic()
        self._dirty = True

    # -- Widget hooks (override base class no-ops) -------------------------

    def handle_dial_turn(self, direction: int) -> None:
        """Adjust the active slider's value by *direction* steps.

        Marks the widget dirty so the next render reflects the change.
        Also resets the selection timeout so the active slider doesn't
        revert to the default while the user is still interacting.
        """
        from .slider import Slider as _Slider

        selectable = self._selectable_indices()
        if not selectable:
            return
        idx = self._active_slider_index
        if idx < len(self._elements) and isinstance(self._elements[idx], _Slider):
            self._elements[idx].adjust(direction)
            if self._active_slider_index != self._default_slider_index:
                self._last_selection_time = time.monotonic()
            self._dirty = True

    def handle_dial_press(self) -> None:
        """Cycle to the next selectable element.  Called on dial push."""
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
        """Compose all sub-elements into a single widget image.

        Returns:
            A WIDGET_WIDTH x WIDGET_HEIGHT RGB :class:`~PIL.Image.Image`.
        """
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        if not self._elements:
            return img

        self.check_selection_timeout()

        selectable = self._selectable_indices()
        count = len(self._elements)
        slot_height = WIDGET_HEIGHT // count
        for i, element in enumerate(self._elements):
            y = i * slot_height
            active = (
                i == self._active_slider_index
                and len(selectable) > 1
                and i in selectable
            )
            element.render_onto(
                img, x=0, y=y, width=WIDGET_WIDTH, height=slot_height, active=active
            )
        return img
