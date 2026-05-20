"""Tests for the resvg SVG rasterisation module."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

import deux.render.svg_rasterize as svg_mod
from deux.render.svg_rasterize import (
    RasterizeError,
    _inject_stylesheet,
    _resvg_rasterize,
    _svg_to_png,
    get_svg_stylesheet,
    load_svg_stylesheet,
    set_svg_stylesheet,
)


def _fake_png(width: int = 10, height: int = 10) -> bytes:
    """Create a minimal valid PNG image."""
    img = Image.new("RGB", (width, height), "red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_stylesheet():
    """Reset stylesheet state before/after each test."""
    original_stylesheet = svg_mod._active_stylesheet
    yield
    svg_mod._active_stylesheet = original_stylesheet


class TestResvgRasterizer:
    """Tests for the resvg rasterisation function."""

    _SVG = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        b'<rect width="100" height="100" fill="red"/></svg>'
    )

    def test_resvg_success(self):
        """_resvg_rasterize delegates to resvg.render via usvg.Tree."""
        fake = _fake_png(20, 20)
        mock_usvg = MagicMock()
        mock_tree = MagicMock()
        mock_usvg.Options.default.return_value = mock_usvg
        mock_usvg.Tree.from_str.return_value = mock_tree

        mock_render = MagicMock(return_value=fake)
        mock_resvg_mod = MagicMock()
        mock_resvg_mod.usvg = mock_usvg

        with patch.dict("sys.modules", {"resvg": mock_resvg_mod, "resvg.usvg": mock_usvg}):
            mock_resvg_mod.render = mock_render
            mock_resvg_mod.usvg = mock_usvg

            result = _resvg_rasterize(self._SVG, 20, 20)

        assert result == fake
        mock_usvg.load_system_fonts.assert_called_once()
        mock_usvg.Tree.from_str.assert_called_once()
        mock_render.assert_called_once()

    def test_resvg_import_error(self):
        """_resvg_rasterize raises RasterizeError when resvg is missing."""
        with patch.dict("sys.modules", {"resvg": None}), \
             pytest.raises(RasterizeError, match="resvg unavailable"):
            _resvg_rasterize(self._SVG, 10, 10)

    def test_resvg_preserves_viewbox(self):
        """_resvg_rasterize preserves existing viewBox when resizing."""
        svg_with_vb = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"'
            b' viewBox="0 0 100 100"><rect width="100" height="100" fill="blue"/></svg>'
        )
        fake = _fake_png(50, 50)
        mock_usvg = MagicMock()
        mock_tree = MagicMock()
        mock_usvg.Options.default.return_value = mock_usvg
        mock_usvg.Tree.from_str.return_value = mock_tree
        mock_render = MagicMock(return_value=fake)
        mock_resvg_mod = MagicMock()
        mock_resvg_mod.render = mock_render
        mock_resvg_mod.usvg = mock_usvg

        with patch.dict("sys.modules", {"resvg": mock_resvg_mod, "resvg.usvg": mock_usvg}):
            _resvg_rasterize(svg_with_vb, 50, 50)

        svg_arg = mock_usvg.Tree.from_str.call_args[0][0]
        assert 'viewBox="0 0 100 100"' in svg_arg
        assert 'width="50"' in svg_arg
        assert 'height="50"' in svg_arg


class TestSvgToPng:
    """Tests for the _svg_to_png entry point."""

    _SVG = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        b'<rect width="10" height="10"/></svg>'
    )

    def test_svg_to_png_calls_resvg(self):
        """_svg_to_png delegates to _resvg_rasterize."""
        fake = _fake_png()
        with patch.object(svg_mod, "_resvg_rasterize", return_value=fake) as mock:
            result = _svg_to_png(self._SVG, 10, 10)
            assert result == fake
            mock.assert_called_once()

    def test_svg_to_png_injects_stylesheet(self):
        """_svg_to_png injects CSS when a stylesheet is set."""
        fake = _fake_png()
        set_svg_stylesheet(".test { color: red; }")

        with patch.object(svg_mod, "_resvg_rasterize", return_value=fake) as mock:
            _svg_to_png(self._SVG, 10, 10)
            # The SVG data passed to resvg should contain the injected style
            svg_arg = mock.call_args[0][0]
            assert b".test" in svg_arg
            assert b"<style" in svg_arg

    def test_svg_to_png_no_stylesheet(self):
        """_svg_to_png passes SVG unchanged when no stylesheet is set."""
        fake = _fake_png()
        set_svg_stylesheet(None)

        with patch.object(svg_mod, "_resvg_rasterize", return_value=fake) as mock:
            _svg_to_png(self._SVG, 10, 10)
            svg_arg = mock.call_args[0][0]
            assert svg_arg == self._SVG


class TestPublicExports:
    """Tests for public API re-exports."""

    def test_render_exports(self):
        """render.__init__ exports the rasterise API."""
        from deux.render import (
            RasterizeError,
            get_svg_stylesheet,
            load_svg_stylesheet,
            set_svg_stylesheet,
        )

        assert RasterizeError is not None
        assert callable(set_svg_stylesheet)
        assert callable(get_svg_stylesheet)
        assert callable(load_svg_stylesheet)

    def test_toplevel_exports_stylesheet(self):
        """deux.__init__ exports stylesheet API via deprecated path."""
        import deux

        assert callable(deux.set_svg_stylesheet)
        assert callable(deux.get_svg_stylesheet)
        assert callable(deux.load_svg_stylesheet)


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
        assert style_elems[0].text is not None
        assert ".app-wide" in style_elems[0].text
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


class TestLoadSvgStylesheet:
    """Tests for load_svg_stylesheet — file-based convenience function."""

    def test_loads_css_from_file(self, tmp_path):
        """load_svg_stylesheet reads a CSS file and sets it as active."""
        css_file = tmp_path / "theme.css"
        css_file.write_text(".text-primary { color: red; }", encoding="utf-8")

        load_svg_stylesheet(css_file)

        assert get_svg_stylesheet() == ".text-primary { color: red; }"

    def test_loads_from_string_path(self, tmp_path):
        """load_svg_stylesheet accepts a string path."""
        css_file = tmp_path / "style.css"
        css_file.write_text(".bg { fill: black; }", encoding="utf-8")

        load_svg_stylesheet(str(css_file))

        assert get_svg_stylesheet() == ".bg { fill: black; }"

    def test_file_not_found_raises(self):
        """load_svg_stylesheet raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_svg_stylesheet("/nonexistent/path/theme.css")

    def test_preserves_utf8_content(self, tmp_path):
        """load_svg_stylesheet preserves UTF-8 content including special chars."""
        css_file = tmp_path / "unicode.css"
        css_file.write_text(
            ".fancy { content: '\u2026\u2014'; }", encoding="utf-8"
        )

        load_svg_stylesheet(css_file)

        result = get_svg_stylesheet()
        assert result is not None
        assert "\u2026" in result
        assert "\u2014" in result
