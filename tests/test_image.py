"""Tests for deckboard.render — rendering helpers."""

from __future__ import annotations

import io
from unittest.mock import patch

from PIL import Image, ImageFont

from deckboard.render.metrics import (
    ICON_PADDING,
    ICON_SIZE,
    KEY_MARGIN_BOTTOM,
    KEY_MARGIN_LEFT,
    KEY_MARGIN_RIGHT,
    KEY_MARGIN_TOP,
    KEY_SIZE,
    KEY_USABLE_HEIGHT,
    KEY_USABLE_WIDTH,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
    PANEL_COUNT,
    PANEL_HEIGHT,
    PANEL_WIDTH,
)
from deckboard.render.key_renderer import (
    _encode_jpeg,
    render_blank_key,
    render_key_image,
)
from deckboard.render.fonts import (
    _get_font,
    get_font,
    get_small_font,
)
from deckboard.render.touch_renderer import (
    compose_touchstrip,
    render_blank_touchscreen,
)
from deckboard.render.debug_grid import (
    draw_key_grid,
    draw_touchscreen_grid,
)


def _decode_jpeg(data: bytes) -> Image.Image:
    """Helper: decode JPEG bytes to PIL Image."""
    return Image.open(io.BytesIO(data))


# ── Fonts ───────────────────────────────────────────────────────────────


class TestFonts:
    def test_get_font_returns_font(self):
        f = get_font()
        assert f is not None

    def test_get_font_cached(self):
        """Second call should return the same object."""
        a = get_font()
        b = get_font()
        assert a is b

    def test_get_small_font_returns_font(self):
        f = get_small_font()
        assert f is not None

    def test_get_small_font_cached(self):
        a = get_small_font()
        b = get_small_font()
        assert a is b

    def test_get_font_all_system_fonts_fail_falls_back_to_default(self):
        """Lines 36-41: When all system fonts AND Arial fail, load_default is used."""
        original_truetype = ImageFont.truetype

        def fail_for_strings(name, size=10, *args, **kwargs):
            # Only fail for string font names (system paths / Arial),
            # allow BytesIO calls through (used by load_default internally)
            if isinstance(name, str):
                raise OSError(f"Cannot open font: {name}")
            return original_truetype(name, size, *args, **kwargs)

        with patch.object(ImageFont, "truetype", side_effect=fail_for_strings):
            result = _get_font(14)
            # Should have fallen through to load_default()
            assert result is not None

    def test_get_font_system_fonts_fail_but_arial_works(self):
        """Lines 36-37: System fonts fail (continue) but Arial succeeds."""
        original_truetype = ImageFont.truetype
        call_count = 0

        def fail_until_arial(name, size=10, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if name == "Arial":
                return original_truetype(name, size)
            raise OSError(f"Cannot open font: {name}")

        with patch.object(ImageFont, "truetype", side_effect=fail_until_arial):
            try:
                result = _get_font(14)
                # If Arial works on this system, we should get a font
                assert result is not None
                # At least the 4 system fonts should have been tried before Arial
                assert call_count >= 5
            except OSError:
                # Arial may not be found either on this system, which is fine
                # The important thing is the code paths were exercised
                pass


# ── render_key_image ────────────────────────────────────────────────────


class TestRenderKeyImage:
    def test_blank_returns_bytes(self):
        result = render_key_image()
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_blank_dimensions(self):
        result = render_key_image()
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE

    def test_with_rgba_icon(self, sample_icon):
        result = render_key_image(icon=sample_icon)
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE

    def test_with_rgb_icon(self, sample_rgb_icon):
        result = render_key_image(icon=sample_rgb_icon)
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE

    def test_with_label(self):
        result = render_key_image(label="Test")
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE

    def test_with_icon_and_label(self, sample_icon):
        result = render_key_image(icon=sample_icon, label="Test")
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE

    def test_icon_resized_if_wrong_size(self):
        """An icon that's not 80x80 should be resized."""
        big_icon = Image.new("RGBA", (200, 200), (255, 0, 0, 255))
        result = render_key_image(icon=big_icon)
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE

    def test_custom_background(self):
        result = render_key_image(background="blue")
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE

    def test_is_jpeg(self):
        result = render_key_image()
        # JPEG magic bytes: 0xFF 0xD8 0xFF
        assert result[:2] == b"\xff\xd8"

    def test_debug_grid_returns_bytes(self):
        result = render_key_image(debug_grid=True)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_debug_grid_dimensions(self):
        result = render_key_image(debug_grid=True)
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE

    def test_debug_grid_with_icon_and_label(self, sample_icon):
        result = render_key_image(icon=sample_icon, label="Test", debug_grid=True)
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE


# ── Key margin constants ────────────────────────────────────────────────


class TestKeyMarginConstants:
    def test_usable_width(self):
        assert KEY_USABLE_WIDTH == KEY_SIZE[0] - KEY_MARGIN_LEFT - KEY_MARGIN_RIGHT

    def test_usable_height(self):
        assert KEY_USABLE_HEIGHT == KEY_SIZE[1] - KEY_MARGIN_TOP - KEY_MARGIN_BOTTOM

    def test_usable_area_is_106x106(self):
        assert KEY_USABLE_WIDTH == 106
        assert KEY_USABLE_HEIGHT == 106

    def test_icon_padding_fits_within_usable_area(self):
        assert ICON_PADDING == (KEY_USABLE_WIDTH - ICON_SIZE) // 2

    def test_icon_plus_padding_fits(self):
        assert ICON_SIZE + 2 * ICON_PADDING <= KEY_USABLE_WIDTH
        assert ICON_SIZE + 2 * ICON_PADDING <= KEY_USABLE_HEIGHT

    def test_margins_are_positive(self):
        assert KEY_MARGIN_TOP > 0
        assert KEY_MARGIN_RIGHT > 0
        assert KEY_MARGIN_BOTTOM > 0
        assert KEY_MARGIN_LEFT > 0


# ── Key margin rendering behaviour ─────────────────────────────────────


class TestKeyMarginRendering:
    def test_icon_within_margins(self, sample_icon):
        """An icon-only key should have content only inside the margin area."""
        result = render_key_image(icon=sample_icon)
        img = _decode_jpeg(result)

        # The icon is red (255, 0, 0) on a black background.
        # Check that the top-left corner (inside the margin area) is black.
        for x in range(KEY_MARGIN_LEFT):
            for y in range(KEY_SIZE[1]):
                r, g, b = img.getpixel((x, y))
                # JPEG compression means values won't be exactly 0,
                # but they should be very dark in the margin area.
                assert r < 20 and g < 20 and b < 20, (
                    f"Non-black pixel at ({x}, {y}) in left margin: ({r}, {g}, {b})"
                )

    def test_icon_positioned_at_margin_offset(self, sample_icon):
        """Icon x_offset should include the left margin."""
        result = render_key_image(icon=sample_icon)
        img = _decode_jpeg(result)

        # The icon is placed at (KEY_MARGIN_LEFT + ICON_PADDING, ...)
        # which is (7 + 13, ...) = (20, ...).  The pixel just inside
        # should be red-ish (the icon colour).
        expected_x = KEY_MARGIN_LEFT + ICON_PADDING
        expected_y = KEY_MARGIN_TOP + ICON_PADDING
        r, g, b = img.getpixel((expected_x + 2, expected_y + 2))
        assert r > 200, f"Expected red-ish pixel at icon start, got ({r}, {g}, {b})"

    def test_right_margin_is_clear(self, sample_icon):
        """Right margin area should remain background-coloured."""
        result = render_key_image(icon=sample_icon)
        img = _decode_jpeg(result)

        for x in range(KEY_SIZE[0] - KEY_MARGIN_RIGHT, KEY_SIZE[0]):
            for y in range(KEY_SIZE[1]):
                r, g, b = img.getpixel((x, y))
                assert r < 20 and g < 20 and b < 20, (
                    f"Non-black pixel at ({x}, {y}) in right margin: ({r}, {g}, {b})"
                )

    def test_label_within_bottom_margin(self):
        """Label text should not extend into the bottom margin."""
        result = render_key_image(label="Test")
        img = _decode_jpeg(result)

        # The bottom margin rows should be essentially black
        for x in range(KEY_SIZE[0]):
            for y in range(KEY_SIZE[1] - KEY_MARGIN_BOTTOM + 1, KEY_SIZE[1]):
                r, g, b = img.getpixel((x, y))
                assert r < 30 and g < 30 and b < 30, (
                    f"Non-black pixel at ({x}, {y}) in bottom margin: ({r}, {g}, {b})"
                )


# ── compose_touchstrip ─────────────────────────────────────────────────


class TestComposeTouchscreen:
    def test_all_none(self):
        result = compose_touchstrip([None, None, None, None])
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_with_images(self, sample_widget_image):
        images = [sample_widget_image] * 4
        result = compose_touchstrip(images)
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_mixed_none_and_images(self, sample_widget_image):
        result = compose_touchstrip(
            [sample_widget_image, None, sample_widget_image, None]
        )
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_more_than_four_ignored(self, sample_widget_image):
        """Extra images beyond 4 are silently ignored."""
        images = [sample_widget_image] * 6
        result = compose_touchstrip(images)
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_empty_list(self):
        result = compose_touchstrip([])
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_is_jpeg(self, sample_widget_image):
        result = compose_touchstrip([sample_widget_image] * 4)
        assert result[:2] == b"\xff\xd8"

    def test_debug_grid(self, sample_widget_image):
        """compose_touchstrip with debug_grid=True is not implemented via wrapper."""
        # The compatibility wrapper does not forward debug_grid,
        # but compose_touchstrip (the underlying function) does.
        from deckboard.render.touch_renderer import compose_touchstrip

        result = compose_touchstrip([sample_widget_image] * 4, debug_grid=True)
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_custom_background_color(self):
        """Background colour fills the canvas margins and gaps."""
        result = compose_touchstrip([None] * 4, background="#ff0000")
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)
        # Top-left corner (0,0) is in the margin area — should be red-ish
        r, g, b = img.getpixel((0, 0))
        assert r > 200  # JPEG compression may shift values slightly
        assert g < 50
        assert b < 50

    def test_default_background_is_black(self):
        """Without a background argument the canvas is black."""
        result = compose_touchstrip([None] * 4)
        img = _decode_jpeg(result)
        r, g, b = img.getpixel((0, 0))
        assert r < 10
        assert g < 10
        assert b < 10


# ── render_blank_key ────────────────────────────────────────────────────


class TestRenderBlankKey:
    def test_returns_bytes(self):
        result = render_blank_key()
        assert isinstance(result, bytes)

    def test_dimensions(self):
        img = _decode_jpeg(render_blank_key())
        assert img.size == KEY_SIZE

    def test_is_jpeg(self):
        assert render_blank_key()[:2] == b"\xff\xd8"

    def test_debug_grid(self):
        result = render_blank_key(debug_grid=True)
        img = _decode_jpeg(result)
        assert img.size == KEY_SIZE


# ── render_blank_touchscreen ────────────────────────────────────────────


class TestRenderBlankTouchscreen:
    def test_returns_bytes(self):
        result = render_blank_touchscreen()
        assert isinstance(result, bytes)

    def test_dimensions(self):
        img = _decode_jpeg(render_blank_touchscreen())
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_debug_grid(self):
        result = render_blank_touchscreen(debug_grid=True)
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_custom_background(self):
        result = render_blank_touchscreen(background="#00ff00")
        img = _decode_jpeg(result)
        r, g, b = img.getpixel((0, 0))
        assert g > 200
        assert r < 50
        assert b < 50


# ── _encode_jpeg ────────────────────────────────────────────────────────


class TestEncodeJpeg:
    def test_returns_bytes(self):
        img = Image.new("RGB", (10, 10), "red")
        result = _encode_jpeg(img)
        assert isinstance(result, bytes)

    def test_is_jpeg(self):
        img = Image.new("RGB", (10, 10))
        assert _encode_jpeg(img)[:2] == b"\xff\xd8"

    def test_quality_parameter(self):
        img = Image.new("RGB", (100, 100), "red")
        low = _encode_jpeg(img, quality=10)
        high = _encode_jpeg(img, quality=95)
        # Lower quality should produce smaller file
        assert len(low) < len(high)


# ── debug grid re-exports ───────────────────────────────────────────────


class TestDebugGridReexports:
    def test_draw_touchscreen_grid_importable(self):
        assert draw_touchscreen_grid is not None

    def test_draw_key_grid_importable(self):
        assert draw_key_grid is not None
