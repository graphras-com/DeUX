"""Balance slider — centre-fill bar for left/right speaker balance."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .slider import SmallSlider, _SMALL_INNER_RX


class BalanceSlider(SmallSlider):
    """A small slider for left/right speaker balance.

    Value range 0–100 where 50 = perfectly balanced (both speakers
    full volume).  The visualisation uses two filled rectangles growing
    from the centre: the left rect represents left-speaker volume and
    the right rect represents right-speaker volume.  When balanced
    (value = 50) both rectangles fill the full half.

    A thin vertical centre line marks the midpoint.

    Args:
        label: Display label (e.g. ``"Balance"``).
        value: Initial value.  Defaults to 50 (centre).
        min_value: Minimum value.  Defaults to 0 (full left).
        max_value: Maximum value.  Defaults to 100 (full right).
        step: Dial-turn increment.  Defaults to 1.
    """

    def __init__(
        self,
        label: str = "Balance",
        *,
        value: float | None = None,
        min_value: float = 0,
        max_value: float = 100,
        step: float = 1,
    ) -> None:
        if value is None:
            value = 50.0
        super().__init__(
            label,
            min_value=min_value,
            max_value=max_value,
            value=value,
            unit="",
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
        centre_x = ix + iw // 2
        half_w = iw // 2

        # Compute left and right speaker volumes.
        # 50 → both full.  0 → only left.  100 → only right.
        n = self.normalized  # 0.0 (full-left) to 1.0 (full-right)

        # Right speaker: full when n >= 0.5, shrinks to 0 at n = 0
        right_frac = min(1.0, n * 2)
        # Left speaker: full when n <= 0.5, shrinks to 0 at n = 1
        left_frac = min(1.0, (1.0 - n) * 2)

        # Left fill: grows from centre toward the left
        left_fill_w = int(half_w * left_frac)
        if left_fill_w > 0:
            self._draw_rounded_rect(
                draw,
                (centre_x - left_fill_w, iy, centre_x, iy + ih - 1),
                radius=_SMALL_INNER_RX,
                fill="white",
            )

        # Right fill: grows from centre toward the right
        right_fill_w = int(half_w * right_frac)
        if right_fill_w > 0:
            self._draw_rounded_rect(
                draw,
                (centre_x, iy, centre_x + right_fill_w, iy + ih - 1),
                radius=_SMALL_INNER_RX,
                fill="white",
            )

        # Centre line
        draw.line(
            [(centre_x, iy), (centre_x, iy + ih - 1)],
            fill="black",
            width=1,
        )
