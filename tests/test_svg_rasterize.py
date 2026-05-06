"""Tests for the pluggable SVG backend registry."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

import deckui.render.svg_rasterize as svg_mod
from deckui.render.svg_rasterize import (
    CairoRasterizer,
    PyvipsRasterizer,
    RasterizeError,
    RsvgCliRasterizer,
    SvgRasterizer,
    _svg_to_png,
    get_svg_backend,
    list_svg_backends,
    register_svg_backend,
    set_svg_backend,
)


def _fake_png(width: int = 10, height: int = 10) -> bytes:
    """Create a minimal valid PNG image."""
    img = Image.new("RGB", (width, height), "red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_backend():
    """Reset backend state before/after each test.

    Overrides the global conftest fixture so that tests in this module
    that modify the registry see a clean slate.
    """
    original_active = svg_mod._active_backend
    original_registry = svg_mod._registry.copy()
    yield
    svg_mod._active_backend = original_active
    svg_mod._registry = original_registry


class TestRegistry:
    """Tests for register/set/get/list backend functions."""

    def test_builtin_backends_registered(self):
        """Built-in backends are registered at import time."""
        names = list_svg_backends()
        assert "cairo" in names
        assert "pyvips" in names
        assert "rsvg-cli" in names

    def test_default_backend_is_auto(self):
        """Default backend is 'auto' when nothing is explicitly set."""
        svg_mod._active_backend = None
        assert get_svg_backend() == "auto"

    def test_set_and_get_backend(self):
        """set_svg_backend changes the active backend."""
        set_svg_backend("cairo", verify=False)
        assert get_svg_backend() == "cairo"

    def test_set_auto_backend(self):
        """'auto' is always valid for set_svg_backend."""
        set_svg_backend("auto")
        assert get_svg_backend() == "auto"

    def test_set_unknown_backend_raises(self):
        """Setting an unregistered backend raises ValueError."""
        with pytest.raises(ValueError, match="Unknown SVG backend"):
            set_svg_backend("nonexistent")

    def test_register_custom_backend(self):
        """A custom backend implementing the protocol can be registered."""

        class CustomRasterizer:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                return _fake_png(width, height)

        register_svg_backend("custom", CustomRasterizer())
        assert "custom" in list_svg_backends()

        set_svg_backend("custom")
        result = _svg_to_png(b"<svg/>", 10, 10)
        img = Image.open(io.BytesIO(result))
        assert img.size == (10, 10)

    def test_register_invalid_backend_raises(self):
        """Registering a non-protocol object raises TypeError."""
        with pytest.raises(TypeError, match="SvgRasterizer protocol"):
            register_svg_backend("bad", "not a rasterizer")  # type: ignore[arg-type]

    def test_protocol_check(self):
        """SvgRasterizer protocol runtime check works."""

        class Good:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                return b""

        assert isinstance(Good(), SvgRasterizer)
        assert not isinstance("string", SvgRasterizer)

    def test_set_backend_verify_catches_broken(self):
        """set_svg_backend raises RasterizeError when verify detects a broken backend."""

        class BrokenBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                raise RasterizeError("broken")

        register_svg_backend("broken", BrokenBackend())
        with pytest.raises(RasterizeError, match="broken"):
            set_svg_backend("broken")

    def test_set_backend_verify_false_skips_check(self):
        """set_svg_backend with verify=False skips the smoke test."""

        class BrokenBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                raise RasterizeError("broken")

        register_svg_backend("broken", BrokenBackend())
        set_svg_backend("broken", verify=False)
        assert get_svg_backend() == "broken"


class TestCairoRasterizer:
    """Tests for the CairoSVG backend."""

    def test_cairo_success(self):
        """CairoRasterizer delegates to cairosvg.svg2png."""
        fake = _fake_png(20, 20)
        with patch.dict("sys.modules", {"cairosvg": MagicMock()}):
            import sys

            sys.modules["cairosvg"].svg2png.return_value = fake
            rasterizer = CairoRasterizer()
            result = rasterizer.rasterize(b"<svg/>", 20, 20)
            assert result == fake

    def test_cairo_import_error(self):
        """CairoRasterizer raises RasterizeError when cairosvg is missing."""
        rasterizer = CairoRasterizer()
        with patch.dict("sys.modules", {"cairosvg": None}), \
             pytest.raises(RasterizeError, match="cairosvg unavailable"):
            rasterizer.rasterize(b"<svg/>", 10, 10)


class TestPyvipsRasterizer:
    """Tests for the pyvips backend."""

    def test_pyvips_success(self):
        """PyvipsRasterizer delegates to pyvips.Image.svgload_buffer."""
        fake = _fake_png(20, 20)
        mock_pyvips = MagicMock()
        mock_image = MagicMock()
        mock_image.width = 100
        mock_image.height = 100
        mock_image.resize.return_value = mock_image
        mock_image.write_to_buffer.return_value = fake
        mock_pyvips.Image.svgload_buffer.return_value = mock_image

        with patch.dict("sys.modules", {"pyvips": mock_pyvips}):
            rasterizer = PyvipsRasterizer()
            result = rasterizer.rasterize(b"<svg/>", 20, 20)
            assert result == fake
            mock_image.resize.assert_called_once_with(0.2, vscale=0.2)

    def test_pyvips_import_error(self):
        """PyvipsRasterizer raises RasterizeError when pyvips is missing."""
        rasterizer = PyvipsRasterizer()
        with patch.dict("sys.modules", {"pyvips": None}), \
             pytest.raises(RasterizeError, match="pyvips unavailable"):
            rasterizer.rasterize(b"<svg/>", 10, 10)


class TestRsvgCliRasterizer:
    """Tests for the rsvg-convert CLI backend."""

    def test_rsvg_success(self):
        """RsvgCliRasterizer calls rsvg-convert subprocess."""
        fake = _fake_png()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake)
            rasterizer = RsvgCliRasterizer()
            result = rasterizer.rasterize(b"<svg/>", 10, 10)
            assert result == fake

    def test_rsvg_not_found(self):
        """RsvgCliRasterizer raises RasterizeError when rsvg-convert missing."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            rasterizer = RsvgCliRasterizer()
            with pytest.raises(RasterizeError, match="rsvg-convert unavailable"):
                rasterizer.rasterize(b"<svg/>", 10, 10)


class TestSvgToPngDispatch:
    """Tests for the _svg_to_png dispatch function."""

    def test_explicit_backend(self):
        """Explicit backend selection dispatches correctly."""
        fake = _fake_png()

        class FakeBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                return fake

        register_svg_backend("fake", FakeBackend())
        set_svg_backend("fake")
        assert _svg_to_png(b"<svg/>", 10, 10) == fake

    def test_auto_fallback_order(self):
        """Auto mode falls back through backends in order."""
        fake = _fake_png()
        calls: list[str] = []

        class FailBackend:
            def __init__(self, name: str):
                self._name = name

            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                calls.append(self._name)
                raise RasterizeError(f"{self._name} failed")

        class SuccessBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                calls.append("pyvips")
                return fake

        svg_mod._registry["cairo"] = FailBackend("cairo")  # type: ignore[assignment]
        svg_mod._registry["pyvips"] = SuccessBackend()  # type: ignore[assignment]
        set_svg_backend("auto")

        result = _svg_to_png(b"<svg/>", 10, 10)
        assert result == fake
        assert calls == ["cairo", "pyvips"]

    def test_auto_all_fail_raises(self):
        """Auto mode raises RasterizeError when all backends fail."""

        class FailBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                raise RasterizeError("fail")

        svg_mod._registry = {
            "cairo": FailBackend(),  # type: ignore[assignment]
            "pyvips": FailBackend(),  # type: ignore[assignment]
            "rsvg-cli": FailBackend(),  # type: ignore[assignment]
        }
        set_svg_backend("auto")

        with pytest.raises(RasterizeError, match="No SVG renderer available"):
            _svg_to_png(b"<svg/>", 10, 10)

    def test_auto_empty_registry_raises(self):
        """Auto mode raises RasterizeError when no backends registered."""
        svg_mod._registry = {}
        set_svg_backend("auto")

        with pytest.raises(RasterizeError, match="No SVG renderer available"):
            _svg_to_png(b"<svg/>", 10, 10)


class TestPublicExports:
    """Tests for public API re-exports."""

    def test_render_exports(self):
        """render.__init__ exports backend API."""
        from deckui.render import (
            SvgRasterizer,
            get_svg_backend,
            list_svg_backends,
            register_svg_backend,
            set_svg_backend,
        )

        assert callable(register_svg_backend)
        assert callable(set_svg_backend)
        assert callable(get_svg_backend)
        assert callable(list_svg_backends)
        assert SvgRasterizer is not None

    def test_toplevel_exports(self):
        """deckui.__init__ exports backend API."""
        import deckui

        assert callable(deckui.register_svg_backend)
        assert callable(deckui.set_svg_backend)
        assert callable(deckui.get_svg_backend)
        assert callable(deckui.list_svg_backends)
        assert deckui.SvgRasterizer is not None
