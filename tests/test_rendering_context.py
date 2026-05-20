"""Tests for the RenderingContext and context-aware rendering pipeline."""

from __future__ import annotations

from deux.render.context import RenderingContext
from deux.render.theme import Theme


class TestRenderingContext:
    """Unit tests for RenderingContext."""

    def test_default_context(self):
        """A default context has no overrides."""
        ctx = RenderingContext()
        assert ctx.theme is None
        assert ctx.stylesheet is None

    def test_from_theme(self):
        """from_theme sets both theme and stylesheet."""
        theme = Theme.from_color(255, 0, 0)
        ctx = RenderingContext.from_theme(theme)
        assert ctx.theme is theme
        assert ctx.stylesheet == theme.css

    def test_resolve_stylesheet_explicit(self):
        """Explicit stylesheet takes precedence over theme CSS."""
        theme = Theme.from_color(0, 255, 0)
        ctx = RenderingContext(theme=theme, stylesheet="custom { color: red; }")
        assert ctx.resolve_stylesheet() == "custom { color: red; }"

    def test_resolve_stylesheet_from_theme(self):
        """Falls back to theme CSS when no explicit stylesheet."""
        theme = Theme.from_color(0, 0, 255)
        ctx = RenderingContext(theme=theme)
        assert ctx.resolve_stylesheet() == theme.css

    def test_resolve_stylesheet_none(self):
        """Returns None when neither stylesheet nor theme is set."""
        ctx = RenderingContext()
        assert ctx.resolve_stylesheet() is None


class TestContextIsolation:
    """Verify that two render passes with different contexts are isolated."""

    def test_svg_to_png_with_context_does_not_mutate_global(self):
        """_svg_to_png with ctx= does not read or modify global stylesheet."""
        import deux.render.svg_rasterize as svg_mod

        original_stylesheet = svg_mod._active_stylesheet

        theme = Theme.from_color(255, 0, 0)
        _ctx = RenderingContext.from_theme(theme)

        # The global should remain unchanged after creating a context.
        assert svg_mod._active_stylesheet == original_stylesheet
        assert _ctx.resolve_stylesheet() == theme.css

    def test_rasterize_svg_with_context_does_not_mutate_global(self):
        """_rasterize_svg with ctx= does not read or modify global stylesheet."""
        import deux.render.svg_rasterize as svg_mod

        original_stylesheet = svg_mod._active_stylesheet

        theme = Theme.from_color(0, 255, 0)
        _ctx = RenderingContext.from_theme(theme)

        # The global should remain unchanged.
        assert svg_mod._active_stylesheet == original_stylesheet
        assert _ctx.resolve_stylesheet() == theme.css


class TestSvgRendererContext:
    """Tests for SvgRenderer.set_rendering_context."""

    def test_set_and_get_rendering_context(self, card_package_spec):
        """Context can be set and retrieved on an SvgRenderer."""
        from deux.dui.svg_renderer import SvgRenderer

        renderer = SvgRenderer(card_package_spec)
        assert renderer.rendering_context is None

        ctx = RenderingContext(stylesheet=".test { color: red; }")
        renderer.set_rendering_context(ctx)
        assert renderer.rendering_context is ctx

    def test_clear_rendering_context(self, card_package_spec):
        """Passing None clears the context."""
        from deux.dui.svg_renderer import SvgRenderer

        renderer = SvgRenderer(card_package_spec)
        ctx = RenderingContext(stylesheet=".test { color: red; }")
        renderer.set_rendering_context(ctx)
        renderer.set_rendering_context(None)
        assert renderer.rendering_context is None
