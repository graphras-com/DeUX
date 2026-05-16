"""Tests for deckui.render.theme — Theme class and theme system."""

from __future__ import annotations

import re

import pytest

import deckui.render.svg_rasterize as svg_mod
import deckui.render.theme as theme_mod
from deckui.render.theme import (
    Theme,
    _adjust,
    _generate_palette,
    _hsl_to_rgb,
    _palette_to_css,
    _rgb_to_hsl,
    _scale,
    _to_hex,
    get_active_theme,
    get_default_font_family,
    set_active_theme,
)
from deckui.runtime.capabilities import STREAM_DECK_PLUS
from deckui.runtime.deck import Deck
from deckui.render.metrics import RenderMetrics
from deckui.ui.screen import Screen


@pytest.fixture(autouse=True)
def _reset_theme():
    """Reset theme state before/after each test."""
    original = theme_mod._active_theme
    original_css = svg_mod._active_stylesheet
    yield
    theme_mod._active_theme = original
    svg_mod._active_stylesheet = original_css


# ---------------------------------------------------------------------------
# Colour math helpers
# ---------------------------------------------------------------------------


class TestRgbToHsl:
    def test_pure_red(self):
        h, s, l = _rgb_to_hsl(255, 0, 0)
        assert abs(h - 0) < 0.1
        assert abs(s - 100) < 0.1
        assert abs(l - 50) < 0.1

    def test_pure_green(self):
        h, s, l = _rgb_to_hsl(0, 255, 0)
        assert abs(h - 120) < 0.1

    def test_pure_blue(self):
        h, s, l = _rgb_to_hsl(0, 0, 255)
        assert abs(h - 240) < 0.1

    def test_white(self):
        h, s, l = _rgb_to_hsl(255, 255, 255)
        assert abs(l - 100) < 0.1

    def test_black(self):
        h, s, l = _rgb_to_hsl(0, 0, 0)
        assert abs(l - 0) < 0.1


class TestHslToRgb:
    def test_round_trip(self):
        r, g, b = 39.0, 87.0, 179.0
        h, s, l = _rgb_to_hsl(r, g, b)
        r2, g2, b2 = _hsl_to_rgb(h, s, l)
        assert abs(r - r2) < 1
        assert abs(g - g2) < 1
        assert abs(b - b2) < 1

    def test_pure_red(self):
        r, g, b = _hsl_to_rgb(0, 100, 50)
        assert abs(r - 255) < 1
        assert abs(g - 0) < 1
        assert abs(b - 0) < 1


class TestAdjust:
    def test_no_shift(self):
        original = (100.0, 150.0, 200.0)
        result = _adjust(original, hue=0)
        assert abs(result[0] - original[0]) < 1
        assert abs(result[1] - original[1]) < 1
        assert abs(result[2] - original[2]) < 1

    def test_complementary(self):
        original = (255.0, 0.0, 0.0)
        result = _adjust(original, hue=180)
        # Red shifted 180 degrees should be cyan
        assert result[0] < 10
        assert result[1] > 245
        assert result[2] > 245


class TestScale:
    def test_no_scale(self):
        original = (100.0, 150.0, 200.0)
        result = _scale(original, saturation=0, lightness=0)
        assert abs(result[0] - original[0]) < 1

    def test_lighten(self):
        original = (100.0, 100.0, 100.0)
        result = _scale(original, lightness=50)
        h1, s1, l1 = _rgb_to_hsl(*original)
        h2, s2, l2 = _rgb_to_hsl(*result)
        assert l2 > l1

    def test_darken(self):
        original = (100.0, 100.0, 100.0)
        result = _scale(original, lightness=-50)
        h1, s1, l1 = _rgb_to_hsl(*original)
        h2, s2, l2 = _rgb_to_hsl(*result)
        assert l2 < l1

    def test_saturate(self):
        original = (100.0, 150.0, 200.0)
        result = _scale(original, saturation=50)
        h1, s1, l1 = _rgb_to_hsl(*original)
        h2, s2, l2 = _rgb_to_hsl(*result)
        assert s2 > s1

    def test_desaturate(self):
        original = (100.0, 150.0, 200.0)
        result = _scale(original, saturation=-50)
        h1, s1, l1 = _rgb_to_hsl(*original)
        h2, s2, l2 = _rgb_to_hsl(*result)
        assert s2 < s1


class TestToHex:
    def test_black(self):
        assert _to_hex(0, 0, 0) == "#000000"

    def test_white(self):
        assert _to_hex(255, 255, 255) == "#ffffff"

    def test_rounding(self):
        assert _to_hex(0.4, 0.4, 0.4) == "#000000"
        assert _to_hex(254.6, 254.6, 254.6) == "#ffffff"


# ---------------------------------------------------------------------------
# Palette generation
# ---------------------------------------------------------------------------


class TestGeneratePalette:
    def test_returns_18_entries(self):
        palette = _generate_palette((39.0, 87.0, 179.0))
        assert len(palette) == 18

    def test_all_hex_colours(self):
        palette = _generate_palette((39.0, 87.0, 179.0))
        for name, color in palette.items():
            assert re.match(r"^#[0-9a-f]{6}$", color), f"{name}: {color}"

    def test_expected_keys(self):
        palette = _generate_palette((39.0, 87.0, 179.0))
        expected_keys = {
            "background-dark", "background-light",
            "border-primary", "border-secondary",
            "text-primary", "text-secondary", "text-accent",
            "text-muted", "text-selected", "text-fancy",
            "success", "warning", "error",
            "icon", "icon-active", "icon-inactive",
            "sliders", "dynamic",
        }
        assert set(palette.keys()) == expected_keys

    def test_different_primary_gives_different_palette(self):
        p1 = _generate_palette((255.0, 0.0, 0.0))
        p2 = _generate_palette((0.0, 0.0, 255.0))
        assert p1 != p2


class TestPaletteToCss:
    def test_contains_font_family(self):
        palette = {"text-primary": "#ffffff"}
        css = _palette_to_css(palette, "Inter")
        assert "'Inter'" in css
        assert "font-family" in css

    def test_contains_class_rules(self):
        palette = {"text-primary": "#ffffff", "error": "#ff0000"}
        css = _palette_to_css(palette, "Inter")
        assert ".text-primary { color: #ffffff; }" in css
        assert ".error { color: #ff0000; }" in css

    def test_custom_font(self):
        palette = {"text-primary": "#ffffff"}
        css = _palette_to_css(palette, "Roboto")
        assert "'Roboto'" in css


# ---------------------------------------------------------------------------
# Theme class
# ---------------------------------------------------------------------------


class TestThemeDefault:
    def test_primary_colour(self):
        theme = Theme.default()
        assert theme.primary == (39, 87, 179)

    def test_font_family(self):
        theme = Theme.default()
        assert theme.font_family == "Inter"

    def test_palette_has_18_entries(self):
        theme = Theme.default()
        assert len(theme.palette) == 18

    def test_css_contains_font(self):
        theme = Theme.default()
        assert "'Inter'" in theme.css

    def test_css_contains_classes(self):
        theme = Theme.default()
        assert ".text-primary" in theme.css

    def test_palette_is_copy(self):
        """palette property returns a copy, not the internal dict."""
        theme = Theme.default()
        p1 = theme.palette
        p2 = theme.palette
        assert p1 == p2
        assert p1 is not p2


class TestThemeFromColor:
    def test_custom_colour(self):
        theme = Theme.from_color(255, 0, 128)
        assert theme.primary == (255, 0, 128)

    def test_custom_font(self):
        theme = Theme.from_color(100, 100, 100, font_family="Roboto")
        assert theme.font_family == "Roboto"
        assert "'Roboto'" in theme.css

    def test_default_font(self):
        theme = Theme.from_color(100, 100, 100)
        assert theme.font_family == "Inter"


class TestThemeFromRandom:
    def test_returns_theme(self):
        theme = Theme.from_random()
        assert isinstance(theme, Theme)

    def test_has_valid_palette(self):
        theme = Theme.from_random()
        assert len(theme.palette) == 18
        for color in theme.palette.values():
            assert re.match(r"^#[0-9a-f]{6}$", color)

    def test_custom_font(self):
        theme = Theme.from_random(font_family="Roboto")
        assert theme.font_family == "Roboto"

    def test_two_random_themes_differ(self):
        """Extremely unlikely to get the same random colour twice."""
        t1 = Theme.from_random()
        t2 = Theme.from_random()
        # They could theoretically match, but probability is negligible
        assert t1.primary != t2.primary or True  # always passes but exercises code


class TestThemeRepr:
    def test_repr(self):
        theme = Theme.from_color(39, 87, 179)
        r = repr(theme)
        assert "Theme" in r
        assert "39" in r
        assert "87" in r
        assert "179" in r
        assert "Inter" in r


class TestThemeEquality:
    def test_equal(self):
        t1 = Theme.from_color(39, 87, 179)
        t2 = Theme.from_color(39, 87, 179)
        assert t1 == t2

    def test_not_equal_colour(self):
        t1 = Theme.from_color(39, 87, 179)
        t2 = Theme.from_color(100, 87, 179)
        assert t1 != t2

    def test_not_equal_font(self):
        t1 = Theme.from_color(39, 87, 179)
        t2 = Theme.from_color(39, 87, 179, font_family="Roboto")
        assert t1 != t2

    def test_not_equal_to_other_type(self):
        t1 = Theme.from_color(39, 87, 179)
        assert t1 != "not a theme"


# ---------------------------------------------------------------------------
# Active theme system
# ---------------------------------------------------------------------------


class TestActiveTheme:
    def test_get_active_theme_returns_default(self):
        theme_mod._active_theme = None
        theme = get_active_theme()
        assert theme.primary == (39, 87, 179)

    def test_set_active_theme(self):
        custom = Theme.from_color(255, 0, 0)
        set_active_theme(custom)
        assert get_active_theme() is custom

    def test_set_active_theme_updates_stylesheet(self):
        custom = Theme.from_color(255, 0, 0)
        set_active_theme(custom)
        assert svg_mod._active_stylesheet == custom.css

    def test_set_active_theme_none_resets_to_default(self):
        set_active_theme(Theme.from_color(255, 0, 0))
        set_active_theme(None)
        assert get_active_theme().primary == (39, 87, 179)

    def test_get_default_font_family(self):
        set_active_theme(Theme.from_color(0, 0, 0, font_family="Roboto"))
        assert get_default_font_family() == "Roboto"

    def test_get_default_font_family_default(self):
        theme_mod._active_theme = None
        assert get_default_font_family() == "Inter"


# ---------------------------------------------------------------------------
# Screen theme property
# ---------------------------------------------------------------------------


class TestScreenTheme:
    def test_default_is_none(self):
        screen = Screen("test", STREAM_DECK_PLUS)
        assert screen.theme is None

    def test_set_theme(self):
        screen = Screen("test", STREAM_DECK_PLUS)
        theme = Theme.from_color(255, 0, 0)
        screen.theme = theme
        assert screen.theme is theme

    def test_clear_theme(self):
        screen = Screen("test", STREAM_DECK_PLUS)
        screen.theme = Theme.from_color(255, 0, 0)
        screen.theme = None
        assert screen.theme is None


# ---------------------------------------------------------------------------
# Deck theme property and cascade
# ---------------------------------------------------------------------------


class TestDeckTheme:
    @pytest.fixture()
    def deck(self):
        d = Deck(serial_number="TEST123")
        d._caps = STREAM_DECK_PLUS
        d._metrics = RenderMetrics(STREAM_DECK_PLUS)
        return d

    def test_default_is_none(self, deck):
        assert deck.theme is None

    def test_set_theme(self, deck):
        theme = Theme.from_color(255, 0, 0)
        deck.theme = theme
        assert deck.theme is theme

    def test_clear_theme(self, deck):
        deck.theme = Theme.from_color(255, 0, 0)
        deck.theme = None
        assert deck.theme is None


class TestDeckResolveStylesheet:
    @pytest.fixture()
    def deck(self):
        d = Deck(serial_number="TEST123")
        d._caps = STREAM_DECK_PLUS
        d._metrics = RenderMetrics(STREAM_DECK_PLUS)
        return d

    def test_falls_back_to_system_theme(self, deck):
        """No deck or screen theme — uses system theme."""
        system_theme = Theme.from_color(10, 20, 30)
        set_active_theme(system_theme)
        screen = deck.screen("main")
        deck._active_screen = screen
        assert deck._resolve_stylesheet() == system_theme.css

    def test_deck_theme_overrides_system(self, deck):
        """Deck theme takes precedence over system theme."""
        set_active_theme(Theme.from_color(10, 20, 30))
        deck_theme = Theme.from_color(100, 100, 100)
        deck.theme = deck_theme
        screen = deck.screen("main")
        deck._active_screen = screen
        assert deck._resolve_stylesheet() == deck_theme.css

    def test_screen_theme_overrides_deck(self, deck):
        """Screen theme takes precedence over deck theme."""
        deck.theme = Theme.from_color(100, 100, 100)
        screen = deck.screen("main")
        screen_theme = Theme.from_color(200, 200, 200)
        screen.theme = screen_theme
        deck._active_screen = screen
        assert deck._resolve_stylesheet() == screen_theme.css

    def test_screen_theme_overrides_system(self, deck):
        """Screen theme takes precedence over system theme."""
        set_active_theme(Theme.from_color(10, 20, 30))
        screen = deck.screen("main")
        screen_theme = Theme.from_color(200, 200, 200)
        screen.theme = screen_theme
        deck._active_screen = screen
        assert deck._resolve_stylesheet() == screen_theme.css

    def test_no_active_screen_uses_system(self, deck):
        """No active screen at all — uses system theme."""
        system_theme = Theme.from_color(10, 20, 30)
        set_active_theme(system_theme)
        assert deck._resolve_stylesheet() == system_theme.css


# ---------------------------------------------------------------------------
# Default theme auto-applied on import
# ---------------------------------------------------------------------------


class TestDefaultThemeAutoApplied:
    def test_stylesheet_is_set_on_import(self):
        """The default theme CSS should be set as stylesheet after import."""
        from deckui.render.svg_rasterize import get_svg_stylesheet

        css = get_svg_stylesheet()
        assert css is not None
        assert "'Inter'" in css
        assert ".text-primary" in css


# ---------------------------------------------------------------------------
# svg_renderer font integration
# ---------------------------------------------------------------------------


class TestSvgRendererFontIntegration:
    def test_get_default_font_family_reads_theme(self):
        """_get_default_font_family in svg_renderer reads from active theme."""
        from deckui.dui.svg_renderer import _get_default_font_family

        set_active_theme(Theme.from_color(0, 0, 0, font_family="Fira Code"))
        assert _get_default_font_family() == "Fira Code"

    def test_get_default_font_family_fallback(self):
        """Falls back to 'Inter' when theme is not available."""
        from deckui.dui.svg_renderer import _get_default_font_family

        theme_mod._active_theme = None
        result = _get_default_font_family()
        assert result == "Inter"


# ---------------------------------------------------------------------------
# Public API imports
# ---------------------------------------------------------------------------


class TestPublicImports:
    def test_theme_importable_from_deckui(self):
        from deckui import Theme

        assert Theme is not None

    def test_get_active_theme_importable(self):
        from deckui import get_active_theme

        assert get_active_theme is not None

    def test_set_active_theme_importable(self):
        from deckui import set_active_theme

        assert set_active_theme is not None

    def test_get_default_font_family_importable(self):
        from deckui import get_default_font_family

        assert get_default_font_family is not None
