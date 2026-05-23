"""Tests for ``deux.runtime.splash``.

Covers input classification, fit modes, rotation mapping, error paths,
and the solid-colour clear helper.  SVG inputs are exercised via the
real :func:`deux.render.svg_rasterize._svg_to_image` path (an in-repo
unit test, not a hardware test), guarded by an import-skip if ``resvg``
is unavailable in the test environment.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from deux.runtime.hid.protocol import ImageRotation
from deux.runtime.splash import (
    SplashError,
    _apply_fit,
    _apply_rotation,
    _looks_like_jpeg,
    _looks_like_svg,
    prepare_full_screen_jpeg,
    prepare_solid_color_jpeg,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_image(
    size: tuple[int, int] = (200, 100),
    color: tuple[int, int, int] = (255, 0, 0),
    mode: str = "RGB",
) -> Image.Image:
    """Construct a solid-colour PIL image for tests."""
    return Image.new(mode, size, color)


def _png_bytes(img: Image.Image) -> bytes:
    """Encode *img* as PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(img: Image.Image, quality: int = 90) -> bytes:
    """Encode *img* as JPEG bytes."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _decode_jpeg_size(data: bytes) -> tuple[int, int]:
    """Return the ``(width, height)`` of JPEG bytes."""
    return Image.open(io.BytesIO(data)).size


# ---------------------------------------------------------------------------
# Sniffing helpers
# ---------------------------------------------------------------------------


class TestLooksLikeSvg:
    """Sniff classification for SVG inputs."""

    @pytest.mark.parametrize(
        "data",
        [
            b"<svg xmlns='http://www.w3.org/2000/svg'/>",
            b"<?xml version='1.0'?><svg/>",
            b"   <svg/>",
            b"\xef\xbb\xbf<svg/>",
            b"<!-- comment --><svg/>",
            b"<!DOCTYPE svg ...><svg/>",
        ],
    )
    def test_positive(self, data):
        assert _looks_like_svg(data) is True

    @pytest.mark.parametrize(
        "data",
        [
            b"\xff\xd8\xffJPEG",
            b"\x89PNG\r\n",
            b"GIF87a...",
            b"plain text",
        ],
    )
    def test_negative(self, data):
        assert _looks_like_svg(data) is False


class TestLooksLikeJpeg:
    def test_positive(self):
        assert _looks_like_jpeg(b"\xff\xd8\xff\xe0rest") is True

    def test_negative(self):
        assert _looks_like_jpeg(b"\x89PNG") is False


# ---------------------------------------------------------------------------
# Fit modes
# ---------------------------------------------------------------------------


class TestApplyFit:
    """Per-mode behaviour of ``_apply_fit``."""

    def test_stretch_changes_size_exactly(self):
        src = _make_test_image((200, 100))
        out = _apply_fit(src, (400, 400), "stretch", (0, 0, 0))
        assert out.size == (400, 400)

    def test_cover_fills_and_crops(self):
        # Wider source than target — height matches, width is cropped.
        src = _make_test_image((400, 100))  # 4:1
        out = _apply_fit(src, (200, 200), "cover", (0, 0, 0))
        assert out.size == (200, 200)

    def test_cover_with_taller_source(self):
        src = _make_test_image((100, 400))  # 1:4
        out = _apply_fit(src, (200, 200), "cover", (0, 0, 0))
        assert out.size == (200, 200)

    def test_contain_letterboxes_horizontally(self):
        # Wider source than target — letterbox top/bottom.
        src = _make_test_image((400, 100), color=(255, 0, 0))
        out = _apply_fit(src, (200, 200), "contain", (0, 255, 0))
        assert out.size == (200, 200)
        # Top-left pixel should be background (green).
        assert out.getpixel((0, 0)) == (0, 255, 0)
        # Centre should be source colour (red).
        assert out.getpixel((100, 100)) == (255, 0, 0)

    def test_contain_letterboxes_vertically(self):
        src = _make_test_image((100, 400), color=(255, 0, 0))
        out = _apply_fit(src, (200, 200), "contain", (0, 0, 255))
        assert out.size == (200, 200)
        assert out.getpixel((0, 0)) == (0, 0, 255)

    def test_invalid_fit_mode_raises(self):
        src = _make_test_image()
        with pytest.raises(SplashError, match="Unknown fit mode"):
            _apply_fit(src, (100, 100), "weird", (0, 0, 0))  # type: ignore[arg-type]

    def test_invalid_target_raises(self):
        src = _make_test_image()
        with pytest.raises(SplashError, match="Invalid target size"):
            _apply_fit(src, (0, 100), "cover", (0, 0, 0))


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------


class TestApplyRotation:
    def test_none_returns_same_object(self):
        src = _make_test_image((10, 20))
        assert _apply_rotation(src, ImageRotation.NONE) is src

    def test_cw_180_preserves_size(self):
        src = _make_test_image((10, 20))
        out = _apply_rotation(src, ImageRotation.CW_180)
        assert out.size == (10, 20)

    def test_ccw_90_swaps_dims(self):
        # 800x1280 logical CCW-90 -> 1280x800 transmit (Plus XL spec).
        src = _make_test_image((800, 1280))
        out = _apply_rotation(src, ImageRotation.CCW_90)
        assert out.size == (1280, 800)


# ---------------------------------------------------------------------------
# prepare_full_screen_jpeg — full pipeline
# ---------------------------------------------------------------------------


class TestPrepareFullScreenJpeg:
    """End-to-end preparation of full-screen JPEG bytes."""

    def test_from_pil_image_no_rotation(self):
        src = _make_test_image((200, 100))
        out = prepare_full_screen_jpeg(
            src,
            logical_size=(800, 480),
            rotation=ImageRotation.NONE,
        )
        assert _looks_like_jpeg(out)
        assert _decode_jpeg_size(out) == (800, 480)

    def test_from_pil_image_with_180_rotation(self):
        src = _make_test_image((200, 100))
        out = prepare_full_screen_jpeg(
            src,
            logical_size=(480, 272),
            rotation=ImageRotation.CW_180,
        )
        # CW_180 preserves dimensions.
        assert _decode_jpeg_size(out) == (480, 272)

    def test_from_pil_image_with_ccw_90_rotation(self):
        src = _make_test_image((400, 200))
        # Plus XL logical 1280x800 -> transmit 800x1280.
        out = prepare_full_screen_jpeg(
            src,
            logical_size=(1280, 800),
            rotation=ImageRotation.CCW_90,
        )
        assert _decode_jpeg_size(out) == (800, 1280)

    def test_from_png_bytes(self):
        src = _make_test_image((300, 300))
        out = prepare_full_screen_jpeg(
            _png_bytes(src),
            logical_size=(480, 272),
        )
        assert _decode_jpeg_size(out) == (480, 272)

    def test_from_jpeg_bytes_round_trips(self):
        src = _make_test_image((300, 300))
        out = prepare_full_screen_jpeg(
            _jpeg_bytes(src),
            logical_size=(480, 272),
        )
        assert _decode_jpeg_size(out) == (480, 272)

    def test_from_path(self, tmp_path):
        path = tmp_path / "splash.png"
        _make_test_image((150, 100)).save(path, format="PNG")
        out = prepare_full_screen_jpeg(
            str(path),
            logical_size=(480, 272),
        )
        assert _decode_jpeg_size(out) == (480, 272)

    def test_from_pathlib_path(self, tmp_path):
        path = tmp_path / "splash.png"
        _make_test_image((150, 100)).save(path, format="PNG")
        out = prepare_full_screen_jpeg(
            path,
            logical_size=(480, 272),
        )
        assert _decode_jpeg_size(out) == (480, 272)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SplashError, match="does not exist"):
            prepare_full_screen_jpeg(
                tmp_path / "missing.png",
                logical_size=(100, 100),
            )

    def test_unsupported_type_raises(self):
        with pytest.raises(SplashError, match="Unsupported image input type"):
            prepare_full_screen_jpeg(
                42,  # type: ignore[arg-type]
                logical_size=(100, 100),
            )

    def test_invalid_bytes_raises(self):
        with pytest.raises(SplashError, match="Failed to decode image bytes"):
            prepare_full_screen_jpeg(
                b"not an image",
                logical_size=(100, 100),
            )

    def test_invalid_file_bytes_raises(self, tmp_path):
        path = tmp_path / "broken.png"
        path.write_bytes(b"not an image")
        with pytest.raises(SplashError, match="Failed to decode"):
            prepare_full_screen_jpeg(path, logical_size=(100, 100))

    def test_contain_with_background(self):
        src = _make_test_image((400, 100), color=(255, 0, 0))
        out = prepare_full_screen_jpeg(
            src,
            logical_size=(400, 400),
            fit="contain",
            background=(0, 255, 0),
        )
        # Letterboxed: top-left should be green.
        img = Image.open(io.BytesIO(out)).convert("RGB")
        # JPEG quantisation makes exact pixel equality risky — sample a
        # few rows in the letterbox region and check they are dominantly
        # green rather than red.
        top_pixel = img.getpixel((0, 0))
        assert top_pixel[1] > top_pixel[0]  # G > R

    def test_jpeg_quality_parameter_round_trips(self):
        src = _make_test_image((200, 200))
        low = prepare_full_screen_jpeg(
            src, logical_size=(400, 400), jpeg_quality=10
        )
        high = prepare_full_screen_jpeg(
            src, logical_size=(400, 400), jpeg_quality=95
        )
        # Higher quality should produce more bytes for the same content.
        assert len(high) > len(low)


# ---------------------------------------------------------------------------
# SVG input — exercises the resvg path
# ---------------------------------------------------------------------------


_SIMPLE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    b'<rect width="100" height="100" fill="red"/>'
    b"</svg>"
)


class TestSvgInputs:
    """SVG bytes and SVG file paths rasterise via resvg."""

    def test_svg_bytes(self):
        try:
            out = prepare_full_screen_jpeg(
                _SIMPLE_SVG,
                logical_size=(480, 272),
            )
        except SplashError as exc:
            if "resvg" in str(exc):
                pytest.skip("resvg not available in test environment")
            raise
        assert _decode_jpeg_size(out) == (480, 272)

    def test_svg_file(self, tmp_path):
        path = tmp_path / "logo.svg"
        path.write_bytes(_SIMPLE_SVG)
        try:
            out = prepare_full_screen_jpeg(
                path, logical_size=(480, 272)
            )
        except SplashError as exc:
            if "resvg" in str(exc):
                pytest.skip("resvg not available in test environment")
            raise
        assert _decode_jpeg_size(out) == (480, 272)


# ---------------------------------------------------------------------------
# prepare_solid_color_jpeg
# ---------------------------------------------------------------------------


class TestPrepareSolidColorJpeg:
    def test_produces_correct_transmit_size_no_rotation(self):
        out = prepare_solid_color_jpeg(
            (255, 0, 0),
            logical_size=(800, 480),
            rotation=ImageRotation.NONE,
        )
        assert _decode_jpeg_size(out) == (800, 480)

    def test_produces_rotated_transmit_size(self):
        # Plus XL: logical 1280x800 -> transmit 800x1280.
        out = prepare_solid_color_jpeg(
            (0, 0, 0),
            logical_size=(1280, 800),
            rotation=ImageRotation.CCW_90,
        )
        assert _decode_jpeg_size(out) == (800, 1280)

    def test_solid_colour_is_dominant(self):
        out = prepare_solid_color_jpeg(
            (255, 0, 0),
            logical_size=(100, 100),
            rotation=ImageRotation.NONE,
        )
        img = Image.open(io.BytesIO(out)).convert("RGB")
        r, g, b = img.getpixel((50, 50))
        assert r > 200 and g < 50 and b < 50
