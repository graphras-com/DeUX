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
    _inject_stylesheet,
    _svg_to_png,
    get_svg_backend,
    get_svg_stylesheet,
    list_svg_backends,
    register_svg_backend,
    set_svg_backend,
    set_svg_stylesheet,
)


def _fake_png(width: int = 10, height: int = 10) -> bytes:
    """Create a minimal valid PNG image."""
    img = Image.new("RGB", (width, height), "red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_backend():
    """Reset backend and stylesheet state before/after each test.

    Overrides the global conftest fixture so that tests in this module
    that modify the registry see a clean slate.
    """
    original_active = svg_mod._active_backend
    original_registry = svg_mod._registry.copy()
    original_stylesheet = svg_mod._active_stylesheet
    yield
    svg_mod._active_backend = original_active
    svg_mod._registry = original_registry
    svg_mod._active_stylesheet = original_stylesheet


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
                calls.append("cairo")
                return fake

        svg_mod._registry["pyvips"] = FailBackend("pyvips")  # type: ignore[assignment]
        svg_mod._registry["cairo"] = SuccessBackend()  # type: ignore[assignment]
        set_svg_backend("auto")

        result = _svg_to_png(b"<svg/>", 10, 10)
        assert result == fake
        assert calls == ["pyvips", "cairo"]

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


class TestSvgStylesheet:
    """Tests for application-wide CSS stylesheet support."""

    def test_default_stylesheet_is_none(self):
        """No stylesheet is active by default."""
        svg_mod._active_stylesheet = None
        assert get_svg_stylesheet() is None

    def test_set_and_get_stylesheet(self):
        """set_svg_stylesheet stores CSS; get_svg_stylesheet retrieves it."""
        css = ".text-primary { color: red; }"
        set_svg_stylesheet(css)
        assert get_svg_stylesheet() == css

    def test_clear_stylesheet(self):
        """Passing None clears the stylesheet."""
        set_svg_stylesheet(".foo { color: blue; }")
        set_svg_stylesheet(None)
        assert get_svg_stylesheet() is None


class TestInjectStylesheet:
    """Tests for _inject_stylesheet — <style> element injection."""

    _SIMPLE_SVG = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
        b'<rect width="100" height="50" fill="#000"/>'
        b"</svg>"
    )

    _SVG_WITH_STYLE = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
        b"<style>.bg { fill: black; }</style>"
        b'<rect class="bg" width="100" height="50"/>'
        b"</svg>"
    )

    def test_injects_style_element(self):
        """Injected CSS appears as a <style> element in the output."""
        css = ".text-primary { color: red; }"
        result = _inject_stylesheet(self._SIMPLE_SVG, css)
        assert b"<style" in result
        assert css.encode() in result

    def test_injected_style_is_first_child(self):
        """The injected <style> is the first child of the root <svg>."""
        import xml.etree.ElementTree as ET

        css = ".injected { color: green; }"
        result = _inject_stylesheet(self._SVG_WITH_STYLE, css)
        root = ET.fromstring(result)  # noqa: S314
        ns = "{http://www.w3.org/2000/svg}"
        first_child = root[0]
        assert first_child.tag == f"{ns}style"
        assert first_child.text is not None
        assert ".injected" in first_child.text

    def test_existing_styles_come_after_injected(self):
        """Existing <style> elements appear after the injected one."""
        import xml.etree.ElementTree as ET

        css = ".app-wide { font-size: 14px; }"
        result = _inject_stylesheet(self._SVG_WITH_STYLE, css)
        root = ET.fromstring(result)  # noqa: S314
        ns = "{http://www.w3.org/2000/svg}"
        style_elems = [el for el in root if el.tag == f"{ns}style"]
        assert len(style_elems) == 2
        # First style is the injected one
        assert style_elems[0].text is not None
        assert ".app-wide" in style_elems[0].text
        # Second style is the original
        assert style_elems[1].text is not None
        assert ".bg" in style_elems[1].text

    def test_preserves_svg_content(self):
        """Non-style SVG content is preserved after injection."""
        css = ".foo { color: red; }"
        result = _inject_stylesheet(self._SIMPLE_SVG, css)
        assert b"<rect" in result or b"rect" in result

    def test_result_is_valid_utf8(self):
        """Output is valid UTF-8 bytes."""
        css = ".unicode { content: '\u2026'; }"
        result = _inject_stylesheet(self._SIMPLE_SVG, css)
        decoded = result.decode("utf-8")
        assert "\u2026" in decoded


class TestStylesheetDispatch:
    """Tests for stylesheet routing in _svg_to_png."""

    _SVG = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        b'<rect width="10" height="10"/></svg>'
    )

    def test_pyvips_receives_native_stylesheet(self):
        """When pyvips is active, stylesheet is passed via kwarg, not injected."""
        fake = _fake_png()
        mock_pyvips = MagicMock()
        mock_image = MagicMock()
        mock_image.width = 10
        mock_image.height = 10
        mock_image.resize.return_value = mock_image
        mock_image.write_to_buffer.return_value = fake
        mock_pyvips.Image.svgload_buffer.return_value = mock_image

        set_svg_stylesheet(".test { color: red; }")

        with patch.dict("sys.modules", {"pyvips": mock_pyvips}):
            set_svg_backend("pyvips", verify=False)
            result = _svg_to_png(self._SVG, 10, 10)

        assert result == fake
        # Verify stylesheet was passed as kwarg to svgload_buffer
        call_kwargs = mock_pyvips.Image.svgload_buffer.call_args
        assert call_kwargs[1]["stylesheet"] == ".test { color: red; }"

    def test_non_pyvips_backend_gets_injected_style(self):
        """When a non-pyvips backend is active, CSS is injected into SVG."""
        received_data: list[bytes] = []

        class SpyBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                received_data.append(svg_data)
                return _fake_png(width, height)

        register_svg_backend("spy", SpyBackend())
        set_svg_backend("spy", verify=False)
        set_svg_stylesheet(".injected { color: blue; }")

        _svg_to_png(self._SVG, 10, 10)

        assert len(received_data) == 1
        assert b".injected" in received_data[0]
        assert b"<style" in received_data[0]

    def test_no_stylesheet_no_injection(self):
        """When no stylesheet is set, SVG data is passed unchanged."""
        received_data: list[bytes] = []

        class SpyBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                received_data.append(svg_data)
                return _fake_png(width, height)

        register_svg_backend("spy", SpyBackend())
        set_svg_backend("spy", verify=False)
        set_svg_stylesheet(None)

        _svg_to_png(self._SVG, 10, 10)

        assert len(received_data) == 1
        assert received_data[0] == self._SVG

    def test_pyvips_no_stylesheet_no_kwarg(self):
        """When no stylesheet is set, pyvips gets no stylesheet kwarg."""
        fake = _fake_png()
        mock_pyvips = MagicMock()
        mock_image = MagicMock()
        mock_image.width = 10
        mock_image.height = 10
        mock_image.resize.return_value = mock_image
        mock_image.write_to_buffer.return_value = fake
        mock_pyvips.Image.svgload_buffer.return_value = mock_image

        set_svg_stylesheet(None)

        with patch.dict("sys.modules", {"pyvips": mock_pyvips}):
            set_svg_backend("pyvips", verify=False)
            _svg_to_png(self._SVG, 10, 10)

        call_kwargs = mock_pyvips.Image.svgload_buffer.call_args
        assert "stylesheet" not in call_kwargs[1]

    def test_auto_mode_pyvips_gets_native_stylesheet(self):
        """In auto mode, pyvips (first in order) receives native stylesheet."""
        fake = _fake_png()
        mock_pyvips = MagicMock()
        mock_image = MagicMock()
        mock_image.width = 10
        mock_image.height = 10
        mock_image.resize.return_value = mock_image
        mock_image.write_to_buffer.return_value = fake
        mock_pyvips.Image.svgload_buffer.return_value = mock_image

        set_svg_stylesheet(".auto-test { font-size: 16px; }")
        set_svg_backend("auto")

        with patch.dict("sys.modules", {"pyvips": mock_pyvips}):
            # Replace the pyvips registry entry with a fresh PyvipsRasterizer
            # so the mocked module is used.
            svg_mod._registry["pyvips"] = PyvipsRasterizer()
            result = _svg_to_png(self._SVG, 10, 10)

        assert result == fake
        call_kwargs = mock_pyvips.Image.svgload_buffer.call_args
        assert call_kwargs[1]["stylesheet"] == ".auto-test { font-size: 16px; }"

    def test_auto_mode_fallback_injects_style(self):
        """In auto mode, when pyvips fails, fallback backend gets injected CSS."""
        received_data: list[bytes] = []

        class FailBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                raise RasterizeError("pyvips failed")

        class SpyBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                received_data.append(svg_data)
                return _fake_png(width, height)

        svg_mod._registry["pyvips"] = FailBackend()  # type: ignore[assignment]
        svg_mod._registry["cairo"] = SpyBackend()  # type: ignore[assignment]
        set_svg_backend("auto")
        set_svg_stylesheet(".fallback { color: green; }")

        _svg_to_png(self._SVG, 10, 10)

        assert len(received_data) == 1
        assert b".fallback" in received_data[0]


class TestStylesheetExports:
    """Tests for stylesheet public API re-exports."""

    def test_render_exports_stylesheet(self):
        """render.__init__ exports stylesheet API."""
        from deckui.render import get_svg_stylesheet, set_svg_stylesheet

        assert callable(set_svg_stylesheet)
        assert callable(get_svg_stylesheet)

    def test_toplevel_exports_stylesheet(self):
        """deckui.__init__ exports stylesheet API."""
        import deckui

        assert callable(deckui.set_svg_stylesheet)
        assert callable(deckui.get_svg_stylesheet)
