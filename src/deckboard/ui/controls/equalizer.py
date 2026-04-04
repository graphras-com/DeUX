"""Equalizer slider — thin indicator on a transparent background."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .range_control import SmallSlider, _SMALL_INDICATOR_W, _SMALL_INNER_RX


class EqualizerSlider(SmallSlider):
    """A small slider for equalizer bands (Sub, Bass, Treble, etc.).

    No background fill.  A thin vertical indicator shows the position.

    Args:
        label: Display label (e.g. ``"Bass"``).
        value: Initial value.  Defaults to 0.
        min_value: Minimum value.  Defaults to 0.
        max_value: Maximum value.  Defaults to 100.
        step: Dial-turn increment.  Defaults to 1.
    """

    def __init__(
        self,
        label: str = "EQ",
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
        # Thin indicator
        ind_x = ix + int((iw - _SMALL_INDICATOR_W) * self.normalized)
        self._draw_rounded_rect(
            draw,
            (ind_x, iy, ind_x + _SMALL_INDICATOR_W - 1, iy + ih - 1),
            radius=_SMALL_INNER_RX,
            fill="white",
        )
