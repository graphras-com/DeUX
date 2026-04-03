"""Tests for deckboard.render.debug_grid — debug alignment grid overlays."""

from __future__ import annotations

from PIL import Image

from deckboard.render.debug_grid import (
    _GRID_COLOR,
    _GRID_COLS,
    _GRID_ROWS,
    _MARGIN_COLOR,
    draw_key_grid,
    draw_touchscreen_grid,
)
from deckboard.render.metrics import (
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
)


class TestDrawTouchscreenGrid:
    def test_returns_new_image(self):
        """draw_touchscreen_grid returns a copy, not the original."""
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)
        assert result is not img

    def test_preserves_size(self):
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)
        assert result.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_preserves_mode(self):
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)
        assert result.mode == "RGB"

    def test_does_not_modify_original(self):
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        original_data = img.tobytes()
        draw_touchscreen_grid(img)
        assert img.tobytes() == original_data

    def test_draws_grid_lines(self):
        """Grid overlay should produce pixels different from all-black."""
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)
        # At least some pixels must have changed (grid lines)
        assert result.tobytes() != img.tobytes()

    def test_margin_lines_are_brighter_than_grid_lines(self):
        """Margin boundary colour is brighter than inner grid colour."""
        assert _MARGIN_COLOR[0] > _GRID_COLOR[0]
        assert _MARGIN_COLOR[1] > _GRID_COLOR[1]
        assert _MARGIN_COLOR[2] > _GRID_COLOR[2]

    def test_margin_pixels_present(self):
        """Check that margin boundary pixels are drawn at expected positions."""
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)

        # Left margin line at x=MARGIN_LEFT
        assert result.getpixel((MARGIN_LEFT, TOUCHSCREEN_HEIGHT // 2)) == _MARGIN_COLOR

        # Top margin line at y=MARGIN_TOP
        assert result.getpixel((TOUCHSCREEN_WIDTH // 2, MARGIN_TOP)) == _MARGIN_COLOR

        # Right margin line at x = W - MARGIN_RIGHT - 1
        right_x = TOUCHSCREEN_WIDTH - MARGIN_RIGHT - 1
        assert result.getpixel((right_x, TOUCHSCREEN_HEIGHT // 2)) == _MARGIN_COLOR

        # Bottom margin line at y = H - MARGIN_BOTTOM - 1
        bottom_y = TOUCHSCREEN_HEIGHT - MARGIN_BOTTOM - 1
        assert result.getpixel((TOUCHSCREEN_WIDTH // 2, bottom_y)) == _MARGIN_COLOR

    def test_inner_grid_pixels_present(self):
        """Inner grid lines should appear at expected positions."""
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)

        # Vertical grid line at column 5 (midpoint)
        col_step = TOUCHSCREEN_WIDTH / _GRID_COLS
        x = round(5 * col_step)
        pixel = result.getpixel((x, TOUCHSCREEN_HEIGHT // 2))
        # This pixel should be a grid or margin colour (not black)
        assert pixel != (0, 0, 0)

        # Horizontal grid line at row 5 (midpoint)
        row_step = TOUCHSCREEN_HEIGHT / _GRID_ROWS
        y = round(5 * row_step)
        pixel = result.getpixel((TOUCHSCREEN_WIDTH // 2, y))
        assert pixel != (0, 0, 0)

    def test_works_with_non_black_background(self):
        """Grid draws over arbitrary backgrounds without error."""
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "blue")
        result = draw_touchscreen_grid(img)
        assert result.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)


class TestDrawKeyGrid:
    def test_returns_new_image(self):
        img = Image.new("RGB", (120, 120), "black")
        result = draw_key_grid(img)
        assert result is not img

    def test_preserves_size(self):
        img = Image.new("RGB", (120, 120), "black")
        result = draw_key_grid(img)
        assert result.size == (120, 120)

    def test_preserves_mode(self):
        img = Image.new("RGB", (120, 120), "black")
        result = draw_key_grid(img)
        assert result.mode == "RGB"

    def test_does_not_modify_original(self):
        img = Image.new("RGB", (120, 120), "black")
        original_data = img.tobytes()
        draw_key_grid(img)
        assert img.tobytes() == original_data

    def test_draws_grid_lines(self):
        img = Image.new("RGB", (120, 120), "black")
        result = draw_key_grid(img)
        assert result.tobytes() != img.tobytes()

    def test_default_divisions_is_four(self):
        """Default 4 divisions produces 3 vertical + 3 horizontal lines."""
        img = Image.new("RGB", (120, 120), "black")
        result = draw_key_grid(img)
        # Check midpoint of a grid line (30px steps with 4 divisions)
        pixel = result.getpixel((30, 60))
        assert pixel == _GRID_COLOR

    def test_custom_divisions(self):
        """Passing divisions=2 draws a single cross."""
        img = Image.new("RGB", (120, 120), "black")
        result = draw_key_grid(img, divisions=2)
        # Grid line at x=60
        pixel = result.getpixel((60, 10))
        assert pixel == _GRID_COLOR
        # Grid line at y=60
        pixel = result.getpixel((10, 60))
        assert pixel == _GRID_COLOR

    def test_works_with_non_black_background(self):
        img = Image.new("RGB", (120, 120), "red")
        result = draw_key_grid(img)
        assert result.size == (120, 120)

    def test_works_with_non_square_image(self):
        """Should handle arbitrary dimensions gracefully."""
        img = Image.new("RGB", (200, 100), "black")
        result = draw_key_grid(img, divisions=5)
        assert result.size == (200, 100)
