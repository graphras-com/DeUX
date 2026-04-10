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
    KEY_MARGIN_BOTTOM,
    KEY_MARGIN_LEFT,
    KEY_MARGIN_RIGHT,
    KEY_MARGIN_TOP,
    KEY_SIZE,
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

        left = MARGIN_LEFT
        right = TOUCHSCREEN_WIDTH - MARGIN_RIGHT - 1
        top = MARGIN_TOP
        bottom = TOUCHSCREEN_HEIGHT - MARGIN_BOTTOM - 1
        mid_x = (left + right) // 2
        mid_y = (top + bottom) // 2

        # Left margin line
        assert result.getpixel((left, mid_y)) == _MARGIN_COLOR
        # Right margin line
        assert result.getpixel((right, mid_y)) == _MARGIN_COLOR
        # Top margin line
        assert result.getpixel((mid_x, top)) == _MARGIN_COLOR
        # Bottom margin line
        assert result.getpixel((mid_x, bottom)) == _MARGIN_COLOR

    def test_margin_lines_stay_within_bounds(self):
        """Margin lines should not extend beyond the margin rectangle."""
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)

        # Pixels outside the margin rectangle should remain black
        if MARGIN_TOP > 0:
            # Above the top margin on the left margin column
            assert result.getpixel((MARGIN_LEFT, 0)) == (0, 0, 0)
        # Below the bottom margin on the left margin column
        assert result.getpixel((MARGIN_LEFT, TOUCHSCREEN_HEIGHT - 1)) == (0, 0, 0)
        if MARGIN_LEFT > 1:
            # Left of the left margin on the top margin row
            assert result.getpixel((0, MARGIN_TOP)) == (0, 0, 0)
        # Right of the right margin on the top margin row
        assert result.getpixel((TOUCHSCREEN_WIDTH - 1, MARGIN_TOP)) == (0, 0, 0)

    def test_inner_grid_pixels_present(self):
        """Inner grid lines should appear within the usable area."""
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)

        left = MARGIN_LEFT
        right = TOUCHSCREEN_WIDTH - MARGIN_RIGHT - 1
        top = MARGIN_TOP
        bottom = TOUCHSCREEN_HEIGHT - MARGIN_BOTTOM - 1
        usable_w = right - left
        usable_h = bottom - top

        # Vertical grid line at column 2
        col_step = usable_w / _GRID_COLS
        x = round(left + 2 * col_step)
        mid_y = (top + bottom) // 2
        pixel = result.getpixel((x, mid_y))
        assert pixel != (0, 0, 0)

        # Horizontal grid line at row 2 (midpoint of 4 rows)
        row_step = usable_h / _GRID_ROWS
        y = round(top + 2 * row_step)
        mid_x = (left + right) // 2
        pixel = result.getpixel((mid_x, y))
        assert pixel != (0, 0, 0)

    def test_inner_grid_lines_stay_within_margins(self):
        """Inner grid lines should not extend beyond the margin rectangle."""
        img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        result = draw_touchscreen_grid(img)

        left = MARGIN_LEFT
        right = TOUCHSCREEN_WIDTH - MARGIN_RIGHT - 1
        top = MARGIN_TOP
        bottom = TOUCHSCREEN_HEIGHT - MARGIN_BOTTOM - 1
        usable_w = right - left

        # Pick a vertical inner grid line
        col_step = usable_w / _GRID_COLS
        x = round(left + 1 * col_step)

        if MARGIN_TOP > 0:
            # The pixel above the top margin on that column should be black
            assert result.getpixel((x, 0)) == (0, 0, 0)
        # The pixel below the bottom margin on that column should be black
        assert result.getpixel((x, TOUCHSCREEN_HEIGHT - 1)) == (0, 0, 0)

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

    def test_margin_pixels_present(self):
        """Margin boundary pixels should be drawn at key margin positions."""
        img = Image.new("RGB", KEY_SIZE, "black")
        result = draw_key_grid(img)

        left = KEY_MARGIN_LEFT
        right = KEY_SIZE[0] - KEY_MARGIN_RIGHT - 1
        top = KEY_MARGIN_TOP
        bottom = KEY_SIZE[1] - KEY_MARGIN_BOTTOM - 1
        mid_x = (left + right) // 2
        mid_y = (top + bottom) // 2

        # Left margin line
        assert result.getpixel((left, mid_y)) == _MARGIN_COLOR
        # Right margin line
        assert result.getpixel((right, mid_y)) == _MARGIN_COLOR
        # Top margin line
        assert result.getpixel((mid_x, top)) == _MARGIN_COLOR
        # Bottom margin line
        assert result.getpixel((mid_x, bottom)) == _MARGIN_COLOR

    def test_margin_lines_stay_within_bounds(self):
        """Margin lines should not extend beyond the margin rectangle."""
        img = Image.new("RGB", KEY_SIZE, "black")
        result = draw_key_grid(img)

        # Pixels outside the margin rectangle should remain black
        if KEY_MARGIN_TOP > 0:
            assert result.getpixel((KEY_MARGIN_LEFT, 0)) == (0, 0, 0)
        if KEY_MARGIN_BOTTOM > 0:
            assert result.getpixel((KEY_MARGIN_LEFT, KEY_SIZE[1] - 1)) == (0, 0, 0)
        if KEY_MARGIN_LEFT > 1:
            assert result.getpixel((0, KEY_MARGIN_TOP)) == (0, 0, 0)
        if KEY_MARGIN_RIGHT > 1:
            assert result.getpixel((KEY_SIZE[0] - 1, KEY_MARGIN_TOP)) == (0, 0, 0)
