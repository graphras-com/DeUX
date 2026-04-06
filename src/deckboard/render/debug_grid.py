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

# Grid density: 32 columns x 4 rows within the usable (margin-bounded) area.
_GRID_COLS = 32
_GRID_ROWS = 4

# Colours — margin lines are brighter so they stand out.
_MARGIN_COLOR = (120, 120, 120)  # lighter grey for margin boundaries
_GRID_COLOR = (50, 50, 50)  # subtle dark grey for inner grid lines


def draw_touchscreen_grid(img: Image.Image) -> Image.Image:
    """Draw a 32x4 debug grid within the margin boundaries of a touchscreen image.

    Margin boundaries (top/bottom/left/right) are drawn with a
    brighter line so they are easy to distinguish from the evenly
    spaced inner grid lines.  All grid lines run only between the
    margin boundaries, not edge-to-edge.

    Args:
        img: An 800x100 RGB :class:`~PIL.Image.Image`.
             A copy is made — the original is not modified.

    Returns:
        A new image with the grid drawn on top.
    """
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)
    w, h = overlay.size

    # Margin boundary positions
    left = MARGIN_LEFT
    right = w - MARGIN_RIGHT - 1
    top = MARGIN_TOP
    bottom = h - MARGIN_BOTTOM - 1

    usable_w = right - left
    usable_h = bottom - top

    col_step = usable_w / _GRID_COLS
    row_step = usable_h / _GRID_ROWS

    # Inner vertical grid lines (margin-to-margin)
    for i in range(1, _GRID_COLS):
        x = round(left + i * col_step)
        draw.line([(x, top), (x, bottom)], fill=_GRID_COLOR)

    # Inner horizontal grid lines (margin-to-margin)
    for i in range(1, _GRID_ROWS):
        y = round(top + i * row_step)
        draw.line([(left, y), (right, y)], fill=_GRID_COLOR)

    # Margin boundary lines (brighter)
    draw.line([(left, top), (left, bottom)], fill=_MARGIN_COLOR)
    draw.line([(right, top), (right, bottom)], fill=_MARGIN_COLOR)
    draw.line([(left, top), (right, top)], fill=_MARGIN_COLOR)
    draw.line([(left, bottom), (right, bottom)], fill=_MARGIN_COLOR)

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
