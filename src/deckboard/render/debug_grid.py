"""Debug grid overlay for alignment inspection during UI development."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .metrics import (
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
)

# Grid density: 10 columns x 10 rows for the full 800x100 touchscreen.
_GRID_COLS = 10
_GRID_ROWS = 10

# Colours — margin lines are brighter so they stand out.
_MARGIN_COLOR = (120, 120, 120)  # lighter grey for margin boundaries
_GRID_COLOR = (50, 50, 50)  # subtle dark grey for inner grid lines


def draw_touchscreen_grid(img: Image.Image) -> Image.Image:
    """Draw a 10x10 debug grid on a touchscreen-sized image.

    Margin boundaries (top/bottom/left/right) are drawn with a
    brighter line so they are easy to distinguish from the evenly
    spaced inner grid lines.

    Args:
        img: An 800x100 RGB :class:`~PIL.Image.Image`.
             A copy is made — the original is not modified.

    Returns:
        A new image with the grid drawn on top.
    """
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)
    w, h = overlay.size

    col_step = w / _GRID_COLS
    row_step = h / _GRID_ROWS

    # Inner vertical grid lines
    for i in range(1, _GRID_COLS):
        x = round(i * col_step)
        draw.line([(x, 0), (x, h - 1)], fill=_GRID_COLOR)

    # Inner horizontal grid lines
    for i in range(1, _GRID_ROWS):
        y = round(i * row_step)
        draw.line([(0, y), (w - 1, y)], fill=_GRID_COLOR)

    # Margin boundary lines (brighter)
    # Left margin
    draw.line(
        [(MARGIN_LEFT, 0), (MARGIN_LEFT, h - 1)],
        fill=_MARGIN_COLOR,
    )
    # Right margin
    right_x = w - MARGIN_RIGHT - 1
    draw.line(
        [(right_x, 0), (right_x, h - 1)],
        fill=_MARGIN_COLOR,
    )
    # Top margin
    draw.line(
        [(0, MARGIN_TOP), (w - 1, MARGIN_TOP)],
        fill=_MARGIN_COLOR,
    )
    # Bottom margin
    bottom_y = h - MARGIN_BOTTOM - 1
    draw.line(
        [(0, bottom_y), (w - 1, bottom_y)],
        fill=_MARGIN_COLOR,
    )

    return overlay


def draw_key_grid(img: Image.Image, divisions: int = 4) -> Image.Image:
    """Draw a debug grid on a key-sized image.

    Args:
        img: A 120x120 RGB :class:`~PIL.Image.Image`.
             A copy is made — the original is not modified.
        divisions: Number of grid divisions per axis (default 4).

    Returns:
        A new image with the grid drawn on top.
    """
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)
    w, h = overlay.size

    col_step = w / divisions
    row_step = h / divisions

    for i in range(1, divisions):
        x = round(i * col_step)
        draw.line([(x, 0), (x, h - 1)], fill=_GRID_COLOR)

    for i in range(1, divisions):
        y = round(i * row_step)
        draw.line([(0, y), (w - 1, y)], fill=_GRID_COLOR)

    return overlay
