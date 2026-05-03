"""Tests for deckui.render — rendering helpers."""

from __future__ import annotations

import io

from PIL import Image

from deckui.render.key_renderer import (
    _encode_image,
    render_blank_key,
    render_key_image,
)
from deckui.render.touch_renderer import (
    compose_touchstrip,
    render_blank_touchscreen,
)

KEY_SIZE = (120, 120)
TOUCHSCREEN_SIZE = (800, 100)
PANEL_WIDTH = 200
PANEL_HEIGHT = 100


def _decode_jpeg(data: bytes) -> Image.Image:
    """Helper: decode JPEG bytes to PIL Image."""
    return Image.open(io.BytesIO(data))


class TestRenderKeyImage:
    def test_blank_returns_bytes(self):
        result = render_key_image(key_size=KEY_SIZE)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_blank_dimensions(self):
        img = _decode_jpeg(render_key_image(key_size=KEY_SIZE))
        assert img.size == KEY_SIZE

    def test_with_rgba_icon(self, sample_icon):
        img = _decode_jpeg(render_key_image(key_size=KEY_SIZE, icon=sample_icon))
        assert img.size == KEY_SIZE

    def test_with_rgb_icon(self, sample_rgb_icon):
        img = _decode_jpeg(render_key_image(key_size=KEY_SIZE, icon=sample_rgb_icon))
        assert img.size == KEY_SIZE

    def test_icon_resized_to_key_size(self):
        """An icon that's not key_size should be resized to fill the key."""
        big_icon = Image.new("RGBA", (200, 200), (255, 0, 0, 255))
        img = _decode_jpeg(render_key_image(key_size=KEY_SIZE, icon=big_icon))
        assert img.size == KEY_SIZE

    def test_custom_background(self):
        img = _decode_jpeg(render_key_image(key_size=KEY_SIZE, background="blue"))
        assert img.size == KEY_SIZE

    def test_is_jpeg(self):
        result = render_key_image(key_size=KEY_SIZE)
        assert result[:2] == b"\xff\xd8"

    def test_icon_fills_key_edge_to_edge(self):
        """Icon is rendered at full key size — no margin/padding."""
        red_icon = Image.new("RGBA", KEY_SIZE, (255, 0, 0, 255))
        result = render_key_image(key_size=KEY_SIZE, icon=red_icon)
        decoded = _decode_jpeg(result).convert("RGB")
        # Top-left corner pixel is part of the icon, not background.
        r, _, _ = decoded.getpixel((0, 0))
        assert r > 200

    def test_key_size_supports_non_default_devices(self):
        """A different key size (e.g. Mini's 80x80) renders at that size."""
        mini = (80, 80)
        result = render_key_image(key_size=mini, image_format="BMP")
        img = Image.open(io.BytesIO(result))
        assert img.size == mini


class TestComposeTouchscreen:
    def _full_args(self) -> dict[str, int]:
        return {
            "touchscreen_width": TOUCHSCREEN_SIZE[0],
            "touchscreen_height": TOUCHSCREEN_SIZE[1],
            "panel_count": 4,
            "panel_width": PANEL_WIDTH,
        }

    def test_all_none(self):
        result = compose_touchstrip([None, None, None, None], **self._full_args())
        img = _decode_jpeg(result)
        assert img.size == TOUCHSCREEN_SIZE

    def test_with_images(self, sample_widget_image):
        images = [sample_widget_image] * 4
        result = compose_touchstrip(images, **self._full_args())
        img = _decode_jpeg(result)
        assert img.size == TOUCHSCREEN_SIZE

    def test_mixed_none_and_images(self, sample_widget_image):
        result = compose_touchstrip(
            [sample_widget_image, None, sample_widget_image, None],
            **self._full_args(),
        )
        img = _decode_jpeg(result)
        assert img.size == TOUCHSCREEN_SIZE

    def test_more_than_panel_count_ignored(self, sample_widget_image):
        images = [sample_widget_image] * 6
        result = compose_touchstrip(images, **self._full_args())
        img = _decode_jpeg(result)
        assert img.size == TOUCHSCREEN_SIZE

    def test_empty_list(self):
        result = compose_touchstrip([], **self._full_args())
        img = _decode_jpeg(result)
        assert img.size == TOUCHSCREEN_SIZE

    def test_is_jpeg(self, sample_widget_image):
        result = compose_touchstrip([sample_widget_image] * 4, **self._full_args())
        assert result[:2] == b"\xff\xd8"

    def test_custom_background_color(self):
        result = compose_touchstrip([None] * 4, background="#ff0000", **self._full_args())
        img = _decode_jpeg(result)
        assert img.size == TOUCHSCREEN_SIZE
        r, g, b = img.getpixel((0, 0))
        assert r > 200
        assert g < 50
        assert b < 50

    def test_default_background_is_black(self):
        result = compose_touchstrip([None] * 4, **self._full_args())
        img = _decode_jpeg(result)
        r, g, b = img.getpixel((0, 0))
        assert r < 10
        assert g < 10
        assert b < 10

    def test_cards_tile_edge_to_edge(self):
        """Card 1 starts immediately after card 0 — no gap."""
        red = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), (255, 0, 0))
        green = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), (0, 255, 0))
        result = compose_touchstrip([red, green, None, None], **self._full_args())
        decoded = _decode_jpeg(result).convert("RGB")
        # Pixel inside card 0 (red), away from JPEG block boundaries.
        r0, g0, _ = decoded.getpixel((PANEL_WIDTH - 16, PANEL_HEIGHT // 2))
        # Pixel inside card 1 (green), away from JPEG block boundaries.
        r1, g1, _ = decoded.getpixel((PANEL_WIDTH + 16, PANEL_HEIGHT // 2))
        assert r0 > 200 and g0 < 50
        assert g1 > 200 and r1 < 50


class TestRenderBlankKey:
    def test_returns_bytes(self):
        result = render_blank_key(key_size=KEY_SIZE)
        assert isinstance(result, bytes)

    def test_dimensions(self):
        img = _decode_jpeg(render_blank_key(key_size=KEY_SIZE))
        assert img.size == KEY_SIZE

    def test_is_jpeg(self):
        assert render_blank_key(key_size=KEY_SIZE)[:2] == b"\xff\xd8"


class TestRenderBlankTouchscreen:
    def test_returns_bytes(self):
        result = render_blank_touchscreen(
            touchscreen_width=TOUCHSCREEN_SIZE[0],
            touchscreen_height=TOUCHSCREEN_SIZE[1],
            panel_count=4,
            panel_width=PANEL_WIDTH,
        )
        assert isinstance(result, bytes)

    def test_dimensions(self):
        img = _decode_jpeg(
            render_blank_touchscreen(
                touchscreen_width=TOUCHSCREEN_SIZE[0],
                touchscreen_height=TOUCHSCREEN_SIZE[1],
                panel_count=4,
                panel_width=PANEL_WIDTH,
            )
        )
        assert img.size == TOUCHSCREEN_SIZE


class TestEncodeImage:
    def test_jpeg_default(self):
        img = Image.new("RGB", (10, 10), "red")
        result = _encode_image(img)
        assert result[:2] == b"\xff\xd8"

    def test_bmp_format(self):
        img = Image.new("RGB", (10, 10), "red")
        result = _encode_image(img, image_format="BMP")
        assert result[:2] == b"BM"
