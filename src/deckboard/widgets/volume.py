"""Volume slider — solid fill growing from left to right."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .slider import LargeSlider, _LARGE_INNER_RX


class VolumeSlider(LargeSlider):
    """A large slider that displays volume as a solid fill bar.

    The filled portion grows from left to right proportionally to
    the current value.

    Args:
        label: Display label (e.g. ``"Volume"``).
        value: Initial value.  Defaults to 0.
        min_value: Minimum value.  Defaults to 0.
        max_value: Maximum value.  Defaults to 100.
        step: Dial-turn increment.  Defaults to 1.
    """

    def __init__(
        self,
        label: str = "Volume",
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
        fill_w = int(iw * self.normalized)
        if fill_w > 0:
            self._draw_rounded_rect(
                draw,
                (ix, iy, ix + fill_w, iy + ih),
                radius=_LARGE_INNER_RX,
                fill="white",
            )
