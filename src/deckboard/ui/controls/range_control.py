"""Base range-control classes for touchscreen card sub-elements.

The hierarchy is::

    RangeControl      (abstract base — value, clamping, drawing primitives)
    ├── LargeSlider   (full-width bar with label + value text above)
    └── SmallSlider   (compact bar with label to the left, no value text)

``Slider`` is a backward-compatible alias for ``RangeControl``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from .base import Control
from ...render.fonts import get_font

if TYPE_CHECKING:
    from ..cards.base import Card
    from ...runtime.events import AsyncHandler

# ── Layout constants (derived from the reference SVG) ────────────────────

# Large slider — fits 2 per widget zone
_LARGE_MARGIN_X = 2
_LARGE_LABEL_FONT_SIZE = 14
_LARGE_LABEL_GAP = 3  # gap between label line and frame top
_LARGE_FRAME_HEIGHT = 17
_LARGE_FRAME_RX = 2
_LARGE_FRAME_STROKE = 1
_LARGE_INNER_PAD = 2  # padding between frame and inner track
_LARGE_INDICATOR_W = 3
_LARGE_INNER_RX = 1

# Small slider — fits 4 per widget zone
_SMALL_LABEL_WIDTH = 54
_SMALL_LABEL_GAP = 2
_SMALL_FRAME_HEIGHT = 12
_SMALL_FRAME_RX = 2
_SMALL_FRAME_STROKE = 1
_SMALL_INNER_PAD = 2
_SMALL_INDICATOR_W = 3
_SMALL_INNER_RX = 1

# Highlight colour for the active slider when multiple share a zone
_HIGHLIGHT_COLOR = "#5599ff"
_NORMAL_STROKE_COLOR = "white"


class RangeControl(Control, ABC):
    """Abstract base for all slider / progressbar sub-elements.

    A range control holds a numeric value within a ``[min_value, max_value]``
    range and knows how to render itself onto a PIL image.
    """

    selectable: bool = True

    def __init__(
        self,
        label: str,
        *,
        min_value: float = 0,
        max_value: float = 100,
        value: float | None = None,
        unit: str = "%",
        step: float = 1,
    ) -> None:
        super().__init__()
        self._label = label
        self._min = float(min_value)
        self._max = float(max_value)
        self._value = float(value) if value is not None else self._min
        self._unit = unit
        self._step = float(step)
        self._change_handler: AsyncHandler | None = None

    # -- Properties --------------------------------------------------------

    @property
    def label(self) -> str:
        return self._label

    @property
    def value(self) -> float:
        return self._value

    @property
    def min_value(self) -> float:
        return self._min

    @property
    def max_value(self) -> float:
        return self._max

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def step(self) -> float:
        return self._step

    @property
    def normalized(self) -> float:
        """Value mapped to 0.0 – 1.0 within the min/max range."""
        span = self._max - self._min
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (self._value - self._min) / span))

    # -- Mutators ----------------------------------------------------------

    def on_change(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for value change events.

        The handler receives the new ``value`` after clamping.  It is
        invoked asynchronously by the event loop after the value changes
        (via dial turn or programmatic :meth:`set_value`).

        Usage::

            @slider.on_change
            async def handle(value: float):
                print(f"New value: {value}")
        """
        self._change_handler = handler
        return handler

    def set_value(self, v: float) -> None:
        """Set the value, clamping to ``[min_value, max_value]``.

        If the value actually changes and an :meth:`on_change` handler
        is registered, a callback is queued on the parent widget for
        deferred async invocation.
        """
        old = self._value
        self._value = max(self._min, min(self._max, float(v)))
        if self._card is not None:
            self._card.mark_dirty()
            if self._change_handler is not None and self._value != old:
                self._card.queue_pending_callback(self._change_handler, (self._value,))

    def adjust(self, direction: int) -> None:
        """Adjust the value by ``direction * step``."""
        self.set_value(self._value + direction * self._step)

    def format_value(self) -> str:
        """Human-readable string, e.g. ``'50%'`` or ``'3000K'``."""
        if self._value == int(self._value):
            v = str(int(self._value))
        else:
            v = f"{self._value:.1f}"
        return f"{v}{self._unit}"

    # -- Rendering ---------------------------------------------------------

    @abstractmethod
    def render_onto(
        self,
        img: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        active: bool = False,
    ) -> None:
        """Draw this slider onto *img* within the given rectangle.

        Args:
            img: Target image (modified in-place).
            x: Left edge.
            y: Top edge.
            width: Available width.
            height: Available height.
            active: If ``True``, highlight the frame to show the dial
                is currently controlling this slider.
        """

    # -- Drawing primitives used by subclasses -----------------------------

    @staticmethod
    def _draw_rounded_rect(
        draw: ImageDraw.ImageDraw,
        xy: tuple[float, float, float, float],
        *,
        radius: int = 2,
        fill: str | None = None,
        outline: str | None = None,
        width: int = 1,
    ) -> None:
        """Draw a rectangle with rounded corners."""
        draw.rounded_rectangle(
            xy, radius=radius, fill=fill, outline=outline, width=width
        )

    @staticmethod
    def _draw_gradient(
        img: Image.Image,
        x: int,
        y: int,
        w: int,
        h: int,
        color_left: str,
        color_right: str,
        radius: int = 1,
    ) -> None:
        """Draw a horizontal linear gradient rectangle onto *img*."""
        if w <= 0 or h <= 0:
            return

        from PIL import ImageColor

        r1, g1, b1 = ImageColor.getrgb(color_left)
        r2, g2, b2 = ImageColor.getrgb(color_right)

        grad = Image.new("RGB", (w, h))
        for px in range(w):
            t = px / max(w - 1, 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            for py in range(h):
                grad.putpixel((px, py), (r, g, b))

        # Apply rounded-corner mask
        mask = Image.new("L", (w, h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
        img.paste(grad, (x, y), mask)


# Backward-compatible alias
Slider = RangeControl


class LargeSlider(RangeControl, ABC):
    """A full-width slider with label and value text above the bar.

    Two ``LargeSlider`` instances stack vertically inside one widget zone.
    """

    # Subclasses override this to draw the bar contents.
    @abstractmethod
    def _draw_bar_contents(
        self,
        draw: ImageDraw.ImageDraw,
        img: Image.Image,
        ix: int,
        iy: int,
        iw: int,
        ih: int,
    ) -> None:
        """Draw the inner track contents (fill, indicator, gradient, etc.).

        Args:
            draw: ImageDraw handle for *img*.
            img: The target image (for gradient pasting).
            ix: Inner track left x.
            iy: Inner track top y.
            iw: Inner track width.
            ih: Inner track height.
        """

    def render_onto(
        self,
        img: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        active: bool = False,
    ) -> None:
        draw = ImageDraw.Draw(img)
        font = get_font()

        mx = _LARGE_MARGIN_X
        bar_w = width - 2 * mx
        frame_h = _LARGE_FRAME_HEIGHT

        # Position: bar at the bottom of the slot, label above
        bar_y = y + height - frame_h - 1
        label_y = bar_y - _LARGE_LABEL_GAP - _LARGE_LABEL_FONT_SIZE

        # Label (left-aligned)
        draw.text((x + mx, label_y), self._label, fill="white", font=font)
        # Value (right-aligned)
        val_text = self.format_value()
        bbox = draw.textbbox((0, 0), val_text, font=font)
        val_w = bbox[2] - bbox[0]
        draw.text((x + mx + bar_w - val_w, label_y), val_text, fill="white", font=font)

        # Frame (use inclusive integer coords for symmetric stroke)
        stroke_color = _HIGHLIGHT_COLOR if active else _NORMAL_STROKE_COLOR
        fx = x + mx
        fy = bar_y
        self._draw_rounded_rect(
            draw,
            (fx, fy, fx + bar_w - 1, fy + frame_h - 1),
            radius=_LARGE_FRAME_RX,
            outline=stroke_color,
            width=_LARGE_FRAME_STROKE,
        )

        # Inner track coordinates
        pad = _LARGE_INNER_PAD
        ix = fx + pad
        iy = fy + pad
        iw = bar_w - 2 * pad
        ih = frame_h - 2 * pad

        self._draw_bar_contents(draw, img, ix, iy, iw, ih)


class SmallSlider(RangeControl, ABC):
    """A compact slider with the label to the left and no value text.

    Four ``SmallSlider`` instances stack vertically inside one widget zone.
    """

    @abstractmethod
    def _draw_bar_contents(
        self,
        draw: ImageDraw.ImageDraw,
        img: Image.Image,
        ix: int,
        iy: int,
        iw: int,
        ih: int,
    ) -> None:
        """Draw the inner track contents."""

    def render_onto(
        self,
        img: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        active: bool = False,
    ) -> None:
        draw = ImageDraw.Draw(img)
        font = get_font()

        # Label on the left (right-aligned within label column)
        label_x_end = x + _SMALL_LABEL_WIDTH
        bbox = draw.textbbox((0, 0), self._label, font=font)
        label_w = bbox[2] - bbox[0]
        label_h = bbox[3] - bbox[1]

        # Bar area to the right of the label
        bar_x = label_x_end + _SMALL_LABEL_GAP
        bar_w = width - bar_x + x
        frame_h = _SMALL_FRAME_HEIGHT

        # Position: bar at the bottom of the slot, label vertically centred on bar
        bar_y = y + height - frame_h - 1
        label_y = bar_y + (frame_h - label_h) // 2

        draw.text(
            (label_x_end - label_w, label_y), self._label, fill="white", font=font
        )

        # Frame (use inclusive integer coords for symmetric stroke)
        stroke_color = _HIGHLIGHT_COLOR if active else _NORMAL_STROKE_COLOR
        self._draw_rounded_rect(
            draw,
            (bar_x, bar_y, bar_x + bar_w - 1, bar_y + frame_h - 1),
            radius=_SMALL_FRAME_RX,
            outline=stroke_color,
            width=_SMALL_FRAME_STROKE,
        )

        # Inner track
        pad = _SMALL_INNER_PAD
        ix = bar_x + pad
        iy = bar_y + pad
        iw = bar_w - 2 * pad
        ih = frame_h - 2 * pad

        self._draw_bar_contents(draw, img, ix, iy, iw, ih)
