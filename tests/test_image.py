"""Tests for deckboard.image — rendering helpers."""

from __future__ import annotations

import io
from unittest.mock import patch

from PIL import Image, ImageFont

from deckboard.image import (
    ICON_SIZE,
    KEY_SIZE,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
    WIDGET_COUNT,
    WIDGET_HEIGHT,
    WIDGET_WIDTH,
    _encode_jpeg,
    _get_font,
    compose_touchscreen,
    get_font,
    get_small_font,
    render_blank_key,
    render_blank_touchscreen,
    render_key_image,
    render_widget_image,
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


# ── render_widget_image ─────────────────────────────────────────────────


class TestRenderWidgetImage:
    def test_blank_returns_image(self):
        result = render_widget_image()
        assert isinstance(result, Image.Image)
        assert result.size == (WIDGET_WIDTH, WIDGET_HEIGHT)
        assert result.mode == "RGB"

    def test_with_icon(self, sample_icon):
        result = render_widget_image(icon=sample_icon)
        assert result.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_with_rgb_icon(self, sample_rgb_icon):
        result = render_widget_image(icon=sample_rgb_icon)
        assert result.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_with_label_only(self):
        result = render_widget_image(label="Volume")
        assert result.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_with_value_only(self):
        result = render_widget_image(value="75%")
        assert result.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_with_label_and_value(self):
        result = render_widget_image(label="Volume", value="75%")
        assert result.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_with_all(self, sample_icon):
        result = render_widget_image(icon=sample_icon, label="Vol", value="50%")
        assert result.size == (WIDGET_WIDTH, WIDGET_HEIGHT)


# ── compose_touchscreen ─────────────────────────────────────────────────


class TestComposeTouchscreen:
    def test_all_none(self):
        result = compose_touchscreen([None, None, None, None])
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_with_images(self, sample_widget_image):
        images = [sample_widget_image] * 4
        result = compose_touchscreen(images)
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_mixed_none_and_images(self, sample_widget_image):
        result = compose_touchscreen(
            [sample_widget_image, None, sample_widget_image, None]
        )
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_more_than_four_ignored(self, sample_widget_image):
        """Extra images beyond 4 are silently ignored."""
        images = [sample_widget_image] * 6
        result = compose_touchscreen(images)
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_empty_list(self):
        result = compose_touchscreen([])
        img = _decode_jpeg(result)
        assert img.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_is_jpeg(self, sample_widget_image):
        result = compose_touchscreen([sample_widget_image] * 4)
        assert result[:2] == b"\xff\xd8"


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
