"""Tests for deckboard.icon — IconManager and _svg_to_png."""

from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from PIL import Image

from deckboard.icon import IconError, IconManager, _svg_to_png


# ── _svg_to_png ─────────────────────────────────────────────────────────


class TestSvgToPng:
    SIMPLE_SVG = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
        b'<rect width="24" height="24" fill="red"/></svg>'
    )

    def test_cairosvg_success(self):
        """If cairosvg is available, it should succeed."""
        # cairosvg is installed as a dependency, so this should work
        result = _svg_to_png(self.SIMPLE_SVG, 80, 80)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Verify it's valid PNG
        img = Image.open(BytesIO(result))
        assert img.format == "PNG"

    def test_cairosvg_fallback_to_rsvg(self):
        """When cairosvg import fails, try rsvg-convert."""
        with patch.dict("sys.modules", {"cairosvg": None}):
            with patch("deckboard.icon.subprocess.run") as mock_run:
                # Create a fake PNG (1x1 pixel)
                fake_png = BytesIO()
                Image.new("RGBA", (80, 80)).save(fake_png, "PNG")
                mock_run.return_value = MagicMock(stdout=fake_png.getvalue())

                result = _svg_to_png(self.SIMPLE_SVG, 80, 80)
                assert isinstance(result, bytes)
                mock_run.assert_called_once()

    def test_all_fallbacks_fail(self):
        """When all SVG renderers fail, raise IconError."""
        with patch("builtins.__import__", side_effect=ImportError("no cairosvg")):
            with patch(
                "deckboard.icon.subprocess.run",
                side_effect=FileNotFoundError("no rsvg"),
            ):
                with pytest.raises(IconError, match="No SVG renderer available"):
                    _svg_to_png(self.SIMPLE_SVG, 80, 80)

    def test_rsvg_subprocess_error(self):
        """When cairosvg fails and rsvg-convert returns error, raise IconError."""
        with patch("builtins.__import__", side_effect=ImportError("no cairosvg")):
            with patch(
                "deckboard.icon.subprocess.run",
                side_effect=subprocess.SubprocessError("failed"),
            ):
                with pytest.raises(IconError, match="No SVG renderer available"):
                    _svg_to_png(self.SIMPLE_SVG, 80, 80)


# ── IconManager helpers ─────────────────────────────────────────────────


class TestIconManagerInit:
    def test_creates_cache_dir(self, tmp_path):
        cache_dir = tmp_path / "icon_cache"
        mgr = IconManager(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_default_cache_dir(self):
        mgr = IconManager()
        expected = Path.home() / ".cache" / "deckboard" / "icons"
        assert mgr._cache_dir == expected

    def test_empty_memory_cache(self, icon_manager: IconManager):
        assert icon_manager._memory_cache == {}

    def test_no_client_initially(self, icon_manager: IconManager):
        assert icon_manager._client is None


class TestIconManagerCacheKey:
    def test_basic_key(self, icon_manager: IconManager):
        key = icon_manager._cache_key("mdi:home", 80, "white")
        assert key == "mdi--home--80--white"

    def test_strips_hash_from_color(self, icon_manager: IconManager):
        key = icon_manager._cache_key("mdi:home", 80, "#ff0000")
        assert key == "mdi--home--80--ff0000"

    def test_slash_format(self, icon_manager: IconManager):
        key = icon_manager._cache_key("mdi/home", 80, "white")
        assert key == "mdi--home--80--white"

    def test_different_sizes(self, icon_manager: IconManager):
        k1 = icon_manager._cache_key("mdi:home", 80, "white")
        k2 = icon_manager._cache_key("mdi:home", 60, "white")
        assert k1 != k2

    def test_different_colors(self, icon_manager: IconManager):
        k1 = icon_manager._cache_key("mdi:home", 80, "white")
        k2 = icon_manager._cache_key("mdi:home", 80, "red")
        assert k1 != k2


class TestIconManagerCachePath:
    def test_returns_png_path(self, icon_manager: IconManager):
        path = icon_manager._cache_path("mdi--home--80--white")
        assert path.suffix == ".png"
        assert path.parent == icon_manager._cache_dir


class TestIconManagerParseIconName:
    def test_colon_format(self, icon_manager: IconManager):
        prefix, name = icon_manager._parse_icon_name("mdi:home")
        assert prefix == "mdi"
        assert name == "home"

    def test_slash_format(self, icon_manager: IconManager):
        prefix, name = icon_manager._parse_icon_name("mdi/home")
        assert prefix == "mdi"
        assert name == "home"

    def test_complex_name(self, icon_manager: IconManager):
        prefix, name = icon_manager._parse_icon_name("mdi-light:arrow-up-circle")
        assert prefix == "mdi-light"
        assert name == "arrow-up-circle"

    def test_invalid_format(self, icon_manager: IconManager):
        with pytest.raises(IconError, match="Invalid icon name"):
            icon_manager._parse_icon_name("nocolonorslash")


class TestIconManagerBuildUrl:
    def test_basic_url(self, icon_manager: IconManager):
        url = icon_manager._build_url("mdi", "home", "white")
        assert url == "https://api.iconify.design/mdi/home.svg?color=white"

    def test_encodes_hash_color(self, icon_manager: IconManager):
        url = icon_manager._build_url("mdi", "home", "#ff0000")
        assert url == "https://api.iconify.design/mdi/home.svg?color=%23ff0000"


# ── IconManager.get (async) ─────────────────────────────────────────────


class TestIconManagerGet:
    @pytest.fixture
    def _fake_svg_response(self):
        """An SVG response body for mocking."""
        return (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
            b'<rect width="24" height="24" fill="white"/></svg>'
        )

    async def test_memory_cache_hit(self, icon_manager: IconManager):
        """Returns cached image without HTTP call."""
        fake_img = Image.new("RGBA", (80, 80))
        key = icon_manager._cache_key("mdi:home", 80, "white")
        icon_manager._memory_cache[key] = fake_img

        result = await icon_manager.get("mdi:home")
        assert result is fake_img

    async def test_disk_cache_hit(self, icon_manager: IconManager):
        """Loads from disk cache and populates memory cache."""
        fake_img = Image.new("RGBA", (80, 80), (255, 0, 0, 128))
        key = icon_manager._cache_key("mdi:home", 80, "white")
        path = icon_manager._cache_path(key)
        fake_img.save(path, "PNG")

        result = await icon_manager.get("mdi:home")
        assert result.mode == "RGBA"
        assert key in icon_manager._memory_cache

    async def test_http_fetch(self, icon_manager: IconManager, _fake_svg_response):
        """Fetches from Iconify API when not cached."""
        mock_response = MagicMock()
        mock_response.content = _fake_svg_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False

        async def mock_get(url):
            return mock_response

        mock_client.get = mock_get
        icon_manager._client = mock_client

        result = await icon_manager.get("mdi:home")
        assert isinstance(result, Image.Image)
        assert result.mode == "RGBA"

        # Should be in both caches now
        key = icon_manager._cache_key("mdi:home", 80, "white")
        assert key in icon_manager._memory_cache
        assert icon_manager._cache_path(key).exists()

    async def test_http_error_raises_icon_error(self, icon_manager: IconManager):
        """HTTP errors are wrapped in IconError."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False

        async def mock_get(url):
            raise httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )

        mock_client.get = mock_get
        icon_manager._client = mock_client

        with pytest.raises(IconError, match="Failed to fetch icon"):
            await icon_manager.get("mdi:nonexistent")

    async def test_invalid_svg_raises_icon_error(self, icon_manager: IconManager):
        """Non-SVG response raises IconError."""
        mock_response = MagicMock()
        mock_response.content = b"not an svg"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False

        async def mock_get(url):
            return mock_response

        mock_client.get = mock_get
        icon_manager._client = mock_client

        with pytest.raises(IconError, match="Invalid SVG response"):
            await icon_manager.get("mdi:test")

    async def test_empty_response_raises_icon_error(self, icon_manager: IconManager):
        """Empty response raises IconError."""
        mock_response = MagicMock()
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False

        async def mock_get(url):
            return mock_response

        mock_client.get = mock_get
        icon_manager._client = mock_client

        with pytest.raises(IconError, match="Invalid SVG response"):
            await icon_manager.get("mdi:test")

    async def test_svg_conversion_failure_raises_icon_error(
        self, icon_manager: IconManager, _fake_svg_response
    ):
        """Lines 191-192: _svg_to_png failure is wrapped in IconError."""
        mock_response = MagicMock()
        mock_response.content = _fake_svg_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False

        async def mock_get(url):
            return mock_response

        mock_client.get = mock_get
        icon_manager._client = mock_client

        with patch(
            "deckboard.icon._svg_to_png", side_effect=RuntimeError("render failed")
        ):
            with pytest.raises(IconError, match="Failed to convert SVG to PNG"):
                await icon_manager.get("mdi:home")


# ── IconManager.get_cached (sync) ───────────────────────────────────────


class TestIconManagerGetCached:
    def test_memory_hit(self, icon_manager: IconManager):
        fake_img = Image.new("RGBA", (80, 80))
        key = icon_manager._cache_key("mdi:home", 80, "white")
        icon_manager._memory_cache[key] = fake_img

        result = icon_manager.get_cached("mdi:home")
        assert result is fake_img

    def test_disk_hit(self, icon_manager: IconManager):
        fake_img = Image.new("RGBA", (80, 80))
        key = icon_manager._cache_key("mdi:home", 80, "white")
        path = icon_manager._cache_path(key)
        fake_img.save(path, "PNG")

        result = icon_manager.get_cached("mdi:home")
        assert result is not None
        assert result.mode == "RGBA"
        assert key in icon_manager._memory_cache

    def test_miss_returns_none(self, icon_manager: IconManager):
        result = icon_manager.get_cached("mdi:nonexistent")
        assert result is None


# ── IconManager.clear_cache / clear_disk_cache ──────────────────────────


class TestIconManagerCacheManagement:
    def test_clear_cache(self, icon_manager: IconManager):
        icon_manager._memory_cache["test"] = Image.new("RGBA", (1, 1))
        icon_manager.clear_cache()
        assert icon_manager._memory_cache == {}

    def test_clear_disk_cache(self, icon_manager: IconManager):
        # Create a fake cached file
        path = icon_manager._cache_dir / "test.png"
        Image.new("RGBA", (1, 1)).save(path, "PNG")
        assert path.exists()

        icon_manager.clear_disk_cache()
        assert not path.exists()
        assert icon_manager._memory_cache == {}

    def test_clear_disk_cache_no_dir(self, tmp_path):
        """No error if cache dir doesn't exist."""
        mgr = IconManager(cache_dir=tmp_path / "nonexistent")
        # Remove the created dir
        mgr._cache_dir.rmdir()
        mgr.clear_disk_cache()  # Should not raise


# ── IconManager.close ───────────────────────────────────────────────────


class TestIconManagerClose:
    async def test_close_with_client(self, icon_manager: IconManager):
        # Force client creation
        icon_manager._client = httpx.AsyncClient()
        await icon_manager.close()
        assert icon_manager._client is None

    async def test_close_without_client(self, icon_manager: IconManager):
        """Close is safe when no client exists."""
        await icon_manager.close()  # Should not raise

    async def test_close_already_closed_client(self, icon_manager: IconManager):
        """Close is safe when client is already closed."""
        client = httpx.AsyncClient()
        await client.aclose()
        icon_manager._client = client
        await icon_manager.close()  # Should not raise


# ── IconManager._get_client ─────────────────────────────────────────────


class TestIconManagerGetClient:
    async def test_creates_client(self, icon_manager: IconManager):
        client = await icon_manager._get_client()
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed
        await client.aclose()

    async def test_reuses_client(self, icon_manager: IconManager):
        c1 = await icon_manager._get_client()
        c2 = await icon_manager._get_client()
        assert c1 is c2
        await c1.aclose()

    async def test_recreates_after_close(self, icon_manager: IconManager):
        c1 = await icon_manager._get_client()
        await c1.aclose()
        c2 = await icon_manager._get_client()
        assert c1 is not c2
        assert not c2.is_closed
        await c2.aclose()
