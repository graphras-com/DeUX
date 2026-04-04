"""Kelvin slider — warm-to-cold gradient with a thin indicator."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .range_control import LargeSlider, _LARGE_INDICATOR_W, _LARGE_INNER_RX


class KelvinSlider(LargeSlider):
    """A large slider for light colour temperature (Kelvin).

    The background is a horizontal gradient from warm (#FFB87B) to
    cool (#FFFFFF).  A thin vertical indicator marks the current value.

    Args:
        label: Display label (e.g. ``"Kelvin"``).
        value: Initial value.  Defaults to 2000.
        min_value: Minimum Kelvin.  Defaults to 2000.
        max_value: Maximum Kelvin.  Defaults to 6500.
        step: Encoder-turn increment.  Defaults to 100.
    """

    def __init__(
        self,
        label: str = "Kelvin",
        *,
        value: float | None = None,
        min_value: float = 2000,
        max_value: float = 6500,
        step: float = 100,
    ) -> None:
        super().__init__(
            label,
            min_value=min_value,
            max_value=max_value,
            value=value,
            unit="K",
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
        # Gradient background: warm → cold
        self._draw_gradient(
            img, ix, iy, iw, ih, "#FFB87B", "#FFFFFF", radius=_LARGE_INNER_RX
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
