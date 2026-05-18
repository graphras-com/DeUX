"""Tests for deux.render.image_fetch — remote image fetch and cache."""

from __future__ import annotations

import io
import urllib.error
from unittest.mock import patch

import pytest
from PIL import Image

from deux.render import image_fetch as mod
from deux.render.image_fetch import (
    ALLOWED_FORMATS,
    ImageFetchError,
    _validate_url,
    clear_cache,
    fetch_image,
)


def _png_bytes(size: tuple[int, int] = (4, 4), color: str = "red") -> bytes:
    """Create minimal valid PNG bytes for testing."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _image_bytes(fmt: str, size: tuple[int, int] = (4, 4), color: str = "red") -> bytes:
    """Create minimal image bytes in a given format for testing."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Reset the image cache around every test."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture(autouse=True)
def _bypass_ssrf():
    """Bypass SSRF checks in image fetch tests (tested separately)."""
    with patch("deux.render.image_fetch.check_url"):
        yield


class TestValidateUrl:
    """Tests for :func:`_validate_url`."""

    def test_valid_https(self):
        _validate_url("https://example.com/img.png")

    def test_valid_http(self):
        _validate_url("http://example.com/img.png")

    def test_empty_raises(self):
        with pytest.raises(ImageFetchError, match="non-empty"):
            _validate_url("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ImageFetchError, match="non-empty"):
            _validate_url("   ")

    def test_non_string_raises(self):
        with pytest.raises(ImageFetchError, match="non-empty"):
            _validate_url(None)  # type: ignore[arg-type]

    def test_ftp_scheme_raises(self):
        with pytest.raises(ImageFetchError, match="http://"):
            _validate_url("ftp://example.com/img.png")

    def test_no_scheme_raises(self):
        with pytest.raises(ImageFetchError, match="http://"):
            _validate_url("example.com/img.png")


class TestFetchImage:
    """Tests for :func:`fetch_image`."""

    def test_fetch_returns_pil_image(self):
        data = _png_bytes()
        with patch.object(mod, "_http_get_bytes", return_value=data) as mock:
            result = fetch_image("https://example.com/icon.png")
        assert isinstance(result, Image.Image)
        assert result.size == (4, 4)
        mock.assert_called_once_with("https://example.com/icon.png")

    def test_cache_hit_skips_http(self):
        data = _png_bytes()
        with patch.object(mod, "_http_get_bytes", return_value=data) as mock:
            fetch_image("https://example.com/icon.png")
            fetch_image("https://example.com/icon.png")
            fetch_image("https://example.com/icon.png")
        assert mock.call_count == 1

    def test_cached_image_is_copy(self):
        """Mutating a returned image must not affect the cache."""
        data = _png_bytes()
        with patch.object(mod, "_http_get_bytes", return_value=data):
            a = fetch_image("https://example.com/icon.png")
            b = fetch_image("https://example.com/icon.png")
        assert a is not b

    def test_different_urls_cached_separately(self):
        red = _png_bytes(color="red")
        blue = _png_bytes(color="blue")

        def side_effect(url: str) -> bytes:
            return red if "red" in url else blue

        with patch.object(mod, "_http_get_bytes", side_effect=side_effect) as mock:
            a = fetch_image("https://example.com/red.png")
            b = fetch_image("https://example.com/blue.png")
            fetch_image("https://example.com/red.png")
            fetch_image("https://example.com/blue.png")
        assert mock.call_count == 2
        # Both images differ in pixel content
        assert list(a.tobytes()) != list(b.tobytes())

    def test_invalid_url_raises(self):
        with pytest.raises(ImageFetchError, match="non-empty"):
            fetch_image("")

    def test_network_error_raises_and_caches(self):
        err = urllib.error.URLError("unreachable")
        with patch.object(mod, "_http_get_bytes", side_effect=err) as mock:
            with pytest.raises(ImageFetchError, match="Failed to fetch"):
                fetch_image("https://example.com/gone.png")
            with pytest.raises(ImageFetchError, match="previously failed"):
                fetch_image("https://example.com/gone.png")
        assert mock.call_count == 1

    def test_os_error_also_caught(self):
        with (
            patch.object(mod, "_http_get_bytes", side_effect=OSError("boom")),
            pytest.raises(ImageFetchError, match="Failed to fetch"),
        ):
            fetch_image("https://example.com/boom.png")

    def test_invalid_image_data_raises_and_caches(self):
        with patch.object(mod, "_http_get_bytes", return_value=b"not-an-image") as mock:
            with pytest.raises(ImageFetchError, match="not a valid image"):
                fetch_image("https://example.com/bad.png")
            with pytest.raises(ImageFetchError, match="previously failed"):
                fetch_image("https://example.com/bad.png")
        assert mock.call_count == 1

    def test_clear_cache_forces_refetch(self):
        data = _png_bytes()
        with patch.object(mod, "_http_get_bytes", return_value=data) as mock:
            fetch_image("https://example.com/icon.png")
            clear_cache()
            fetch_image("https://example.com/icon.png")
        assert mock.call_count == 2

    def test_clear_cache_drops_negative_entries(self):
        err = urllib.error.URLError("gone")
        with patch.object(mod, "_http_get_bytes", side_effect=err) as mock:
            with pytest.raises(ImageFetchError):
                fetch_image("https://example.com/gone.png")
            clear_cache()
            with pytest.raises(ImageFetchError):
                fetch_image("https://example.com/gone.png")
        assert mock.call_count == 2


class TestHttpGetBytes:
    """Verify transport-level behaviour of :func:`_http_get_bytes`."""

    def test_sends_user_agent_header(self):
        captured: dict[str, object] = {}
        sample = _png_bytes()

        class _FakeResp:
            def read(self) -> bytes:
                return sample

            def __enter__(self) -> _FakeResp:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

        def fake_urlopen(req, timeout):
            captured["request"] = req
            return _FakeResp()

        with patch.object(mod.urllib.request, "urlopen", fake_urlopen):
            result = mod._http_get_bytes("https://example.test/img.png")

        assert result == sample
        req = captured["request"]
        assert req.get_header("User-agent") == mod.USER_AGENT


class TestPackageExports:
    """Ensure fetch_image is accessible from the package root."""

    def test_render_package_exports(self):
        from deux.render import ImageFetchError as IE
        from deux.render import clear_image_cache
        from deux.render import fetch_image as fi

        assert IE is ImageFetchError
        assert fi is fetch_image
        assert callable(clear_image_cache)

    def test_root_package_exports(self):
        import deux

        assert hasattr(deux, "fetch_image")
        assert hasattr(deux, "ImageFetchError")
        assert hasattr(deux, "clear_image_cache")


class TestImageSecurity:
    """Tests for decompression bomb and format restrictions."""

    def test_disallowed_format_bmp_rejected(self):
        data = _image_bytes("BMP")
        with (
            patch.object(mod, "_http_get_bytes", return_value=data),
            pytest.raises(ImageFetchError, match="not allowed"),
        ):
            fetch_image("https://example.com/img.bmp")

    def test_disallowed_format_tiff_rejected(self):
        data = _image_bytes("TIFF")
        with (
            patch.object(mod, "_http_get_bytes", return_value=data),
            pytest.raises(ImageFetchError, match="not allowed"),
        ):
            fetch_image("https://example.com/img.tiff")

    def test_allowed_formats_accepted(self):
        for fmt in ("PNG", "JPEG", "GIF", "WEBP"):
            clear_cache()
            mode = "RGBA" if fmt in ("PNG", "GIF", "WEBP") else "RGB"
            img = Image.new(mode, (4, 4), "red")
            buf = io.BytesIO()
            img.save(buf, format=fmt)
            data = buf.getvalue()
            with patch.object(mod, "_http_get_bytes", return_value=data):
                result = fetch_image(f"https://example.com/img.{fmt.lower()}")
            assert isinstance(result, Image.Image)

    def test_decompression_bomb_rejected(self):
        """An image exceeding MAX_IMAGE_PIXELS is rejected."""
        # Pillow raises DecompressionBombError at 2x MAX_IMAGE_PIXELS
        data = _png_bytes(size=(5, 5))  # 25 pixels > 2*4=8
        with (
            patch.object(mod.Image, "MAX_IMAGE_PIXELS", 4),
            patch.object(mod, "_http_get_bytes", return_value=data),
            pytest.raises(ImageFetchError, match="not a valid image"),
        ):
            fetch_image("https://example.com/bomb.png")

    def test_max_image_pixels_is_set(self):
        assert mod.MAX_IMAGE_PIXELS == 20_000_000
        assert Image.MAX_IMAGE_PIXELS == 20_000_000

    def test_allowed_formats_constant(self):
        assert frozenset({"PNG", "JPEG", "GIF", "WEBP"}) == ALLOWED_FORMATS
