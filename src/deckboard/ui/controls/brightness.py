"""Brightness slider — dark-to-bright gradient with a thin indicator."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .range_control import LargeSlider, _LARGE_INDICATOR_W, _LARGE_INNER_RX


class BrightnessSlider(LargeSlider):
    """A large slider showing brightness as a thin indicator over a gradient.

    The background is a horizontal gradient from black to white.
    A thin vertical rectangle indicates the current position.

    Args:
        label: Display label (e.g. ``"Brightness"``).
        value: Initial value.  Defaults to 0.
        min_value: Minimum value.  Defaults to 0.
        max_value: Maximum value.  Defaults to 100.
        step: Encoder-turn increment.  Defaults to 1.
    """

    def __init__(
        self,
        label: str = "Brightness",
        *,
        value: float | None = None,
        min_value: float = 0,
        max_value: float = 100,
        step: float = 1,
    ) -> None:
        super().__init__(
            label,
            min_value=min_value,
            max_value=max_value,
            value=value,
            unit="%",
            step=step,
        )

    def _draw_bar_contents(
        self,
        draw: ImageDraw.ImageDraw,
        img: Image.Image,
        ix: int,
        iy: int,
        iw: int,
        ih: int,
    ) -> None:
        # Gradient background: dark → bright
        self._draw_gradient(
            img, ix, iy, iw, ih, "#000000", "#FFFFFF", radius=_LARGE_INNER_RX
        )

        # Thin indicator
        ind_x = ix + int((iw - _LARGE_INDICATOR_W) * self.normalized)
        self._draw_rounded_rect(
            draw,
            (ind_x, iy, ind_x + _LARGE_INDICATOR_W - 1, iy + ih - 1),
            radius=_LARGE_INNER_RX,
            fill="white",
            outline="black",
            width=1,
        )
