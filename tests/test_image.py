"""Tests for deckui.render — rendering helpers."""

from __future__ import annotations

import io

from PIL import Image

from deckui.render.metrics import (
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
from deckui.render.key_renderer import (
    _encode_jpeg,
    render_blank_key,
    render_key_image,
)
from deckui.render.touch_renderer import (
    compose_touchstrip,
    render_blank_touchscreen,
)


def _decode_jpeg(data: bytes) -> Image.Image:
    """Helper: decode JPEG bytes to PIL Image."""
    return Image.open(io.BytesIO(data))


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
        # Check that the left margin area is black.
        for x in range(KEY_MARGIN_LEFT):
            for y in range(KEY_SIZE[1]):
                r, g, b = img.getpixel((x, y))
                # JPEG compression means values won't be exactly 0,
                # but they should be very dark in the margin area.
                assert r < 20 and g < 20 and b < 20, (
                    f"Non-black pixel at ({x}, {y}) in left margin: ({r}, {g}, {b})"
                )

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


# ── render_blank_touchscreen ────────────────────────────────────────────


class TestRenderBlankTouchscreen:
    def test_returns_bytes(self):
        result = render_blank_touchscreen()
        assert isinstance(result, bytes)

    def test_dimensions(self):
        img = _decode_jpeg(render_blank_touchscreen())
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
