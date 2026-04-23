"""Tests for deckui.render.screen_renderer — info screen rendering."""

from __future__ import annotations

from PIL import Image

from deckui.render.screen_renderer import render_info_screen


class TestRenderInfoScreen:
    def test_blank(self):
        data = render_info_screen(None, 248, 58)
        assert isinstance(data, bytes)
        assert data[:2] == b"\xff\xd8"

    def test_with_image(self):
        img = Image.new("RGB", (248, 58), "red")
        data = render_info_screen(img, 248, 58)
        assert isinstance(data, bytes)
        assert data[:2] == b"\xff\xd8"

    def test_with_rgba_image(self):
        img = Image.new("RGBA", (248, 58), (0, 255, 0, 128))
        data = render_info_screen(img, 248, 58)
        assert isinstance(data, bytes)

    def test_resizes_wrong_size(self):
        img = Image.new("RGB", (500, 100), "red")
        data = render_info_screen(img, 248, 58)
        assert isinstance(data, bytes)

    def test_bmp_format(self):
        data = render_info_screen(None, 248, 58, image_format="BMP")
        assert isinstance(data, bytes)
        assert data[:2] == b"BM"

    def test_custom_background(self):
        data = render_info_screen(None, 248, 58, background="#ff0000")
        assert isinstance(data, bytes)

    def test_rgb_image_no_alpha(self):
        img = Image.new("RGB", (248, 58), (0, 0, 255))
        data = render_info_screen(img, 248, 58)
        assert isinstance(data, bytes)
