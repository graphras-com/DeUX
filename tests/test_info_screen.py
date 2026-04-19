"""Tests for deckboard.ui.info_screen — InfoScreen class."""

from __future__ import annotations

from PIL import Image

from deckboard.ui.info_screen import InfoScreen


class TestInfoScreenInit:
    def test_dimensions(self):
        s = InfoScreen(248, 58)
        assert s.width == 248
        assert s.height == 58
        assert s.size == (248, 58)

    def test_default_format(self):
        s = InfoScreen(248, 58)
        assert s.image_format == "JPEG"

    def test_custom_format(self):
        s = InfoScreen(248, 58, image_format="BMP")
        assert s.image_format == "BMP"

    def test_initially_dirty(self):
        s = InfoScreen(248, 58)
        assert s.is_dirty is True

    def test_image_initially_none(self):
        s = InfoScreen(248, 58)
        assert s.image is None


class TestInfoScreenSetImage:
    def test_sets_image(self):
        s = InfoScreen(248, 58)
        img = Image.new("RGB", (248, 58), "red")
        s.set_image(img)
        assert s.image is not None
        assert s.image.size == (248, 58)

    def test_resizes_wrong_size(self):
        s = InfoScreen(248, 58)
        img = Image.new("RGB", (500, 100), "red")
        s.set_image(img)
        assert s.image.size == (248, 58)

    def test_marks_dirty(self):
        s = InfoScreen(248, 58)
        s.mark_clean()
        img = Image.new("RGB", (248, 58), "red")
        s.set_image(img)
        assert s.is_dirty is True


class TestInfoScreenClear:
    def test_clear(self):
        s = InfoScreen(248, 58)
        s.mark_clean()
        s.clear()
        assert s.image is not None
        assert s.image.size == (248, 58)
        assert s.is_dirty is True


class TestInfoScreenDirtyTracking:
    def test_mark_clean(self):
        s = InfoScreen(248, 58)
        s.mark_clean()
        assert s.is_dirty is False

    def test_mark_dirty(self):
        s = InfoScreen(248, 58)
        s.mark_clean()
        s.mark_dirty()
        assert s.is_dirty is True


class TestInfoScreenRenderBytes:
    def test_render_blank(self):
        s = InfoScreen(248, 58)
        data = s.render_bytes()
        assert isinstance(data, bytes)
        assert len(data) > 0
        # JPEG magic bytes
        assert data[:2] == b"\xff\xd8"

    def test_render_with_image(self):
        s = InfoScreen(248, 58)
        s.set_image(Image.new("RGB", (248, 58), "red"))
        data = s.render_bytes()
        assert isinstance(data, bytes)
        assert data[:2] == b"\xff\xd8"

    def test_render_bmp_format(self):
        s = InfoScreen(248, 58, image_format="BMP")
        data = s.render_bytes()
        assert isinstance(data, bytes)
        # BMP magic bytes
        assert data[:2] == b"BM"

    def test_render_rgba_image(self):
        s = InfoScreen(248, 58)
        s.set_image(Image.new("RGBA", (248, 58), (255, 0, 0, 128)))
        data = s.render_bytes()
        assert isinstance(data, bytes)
