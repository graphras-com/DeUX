"""Temperature slider — cold-to-warm gradient with a thin indicator."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .slider import LargeSlider, _LARGE_INDICATOR_W, _LARGE_INNER_RX


class TemperatureSlider(LargeSlider):
    """A large slider for room temperature (Celsius).

    The background is a horizontal gradient from cold (#4555E5) to
    warm (#DB3232).  A thin vertical indicator marks the current value.

    Args:
        label: Display label (e.g. ``"Temperature"``).
        value: Initial value.  Defaults to 15.
        min_value: Minimum temperature.  Defaults to 15.
        max_value: Maximum temperature.  Defaults to 25.
        step: Dial-turn increment.  Defaults to 0.5.
    """

    def __init__(
        self,
        label: str = "Temperature",
        *,
        value: float | None = None,
        min_value: float = 15,
        max_value: float = 25,
        step: float = 0.5,
    ) -> None:
        super().__init__(
            label,
            min_value=min_value,
            max_value=max_value,
            value=value,
            unit="\u00b0C",
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
        # Gradient background: cold → warm
        self._draw_gradient(
            img, ix, iy, iw, ih, "#4555E5", "#DB3232", radius=_LARGE_INNER_RX
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
