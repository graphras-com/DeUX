"""Tests for deckui.render.metrics — RenderMetrics class."""

from __future__ import annotations

from deckui.render.metrics import (
    ICON_PADDING,
    ICON_SIZE,
    KEY_MARGIN_BOTTOM,
    KEY_MARGIN_LEFT,
    KEY_MARGIN_RIGHT,
    KEY_MARGIN_TOP,
    KEY_SIZE,
    KEY_USABLE_HEIGHT,
    KEY_USABLE_WIDTH,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    PANEL_COUNT,
    PANEL_GAP,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    RenderMetrics,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
    USABLE_HEIGHT,
    USABLE_WIDTH,
)
from deckui.runtime.capabilities import STREAM_DECK_PLUS
from tests.conftest import STREAM_DECK_MINI, STREAM_DECK_NEO, STREAM_DECK_XL


class TestDefaultMetrics:
    """Module-level constants should match Stream Deck+ values."""

    def test_key_size(self):
        assert KEY_SIZE == (120, 120)

    def test_key_margins(self):
        assert KEY_MARGIN_TOP == 7
        assert KEY_MARGIN_RIGHT == 7
        assert KEY_MARGIN_BOTTOM == 7
        assert KEY_MARGIN_LEFT == 7

    def test_key_usable(self):
        assert KEY_USABLE_WIDTH == 106
        assert KEY_USABLE_HEIGHT == 106

    def test_icon_size(self):
        assert ICON_SIZE == 80

    def test_icon_padding(self):
        assert ICON_PADDING == (KEY_USABLE_WIDTH - ICON_SIZE) // 2

    def test_touchscreen(self):
        assert TOUCHSCREEN_WIDTH == 800
        assert TOUCHSCREEN_HEIGHT == 100

    def test_panel_count(self):
        assert PANEL_COUNT == 4

    def test_panel_dimensions(self):
        assert PANEL_WIDTH == 197
        assert PANEL_HEIGHT == 98

    def test_margins(self):
        assert MARGIN_TOP == 0
        assert MARGIN_BOTTOM == 2
        assert MARGIN_LEFT == 2
        assert MARGIN_RIGHT == 2
        assert PANEL_GAP == 2

    def test_usable(self):
        assert USABLE_WIDTH == 796
        assert USABLE_HEIGHT == 98


class TestRenderMetricsPlus:
    def test_key_metrics(self):
        m = RenderMetrics(STREAM_DECK_PLUS)
        assert m.key_size == (120, 120)
        assert m.key_count == 8
        assert m.dial_count == 4

    def test_panel_metrics(self):
        m = RenderMetrics(STREAM_DECK_PLUS)
        assert m.panel_count == 4
        assert m.panel_width == 197
        assert m.panel_height == 98

    def test_touchscreen_metrics(self):
        m = RenderMetrics(STREAM_DECK_PLUS)
        assert m.touchscreen_width == 800
        assert m.touchscreen_height == 100


class TestRenderMetricsMini:
    def test_key_metrics(self):
        m = RenderMetrics(STREAM_DECK_MINI)
        assert m.key_size == (80, 80)
        assert m.key_count == 6
        assert m.dial_count == 0

    def test_no_touchscreen(self):
        m = RenderMetrics(STREAM_DECK_MINI)
        assert m.panel_count == 0
        assert m.panel_width == 0
        assert m.panel_height == 0
        assert m.touchscreen_width == 0
        assert m.touchscreen_height == 0

    def test_key_margins_proportional(self):
        m = RenderMetrics(STREAM_DECK_MINI)
        # 80 * 7/120 = 4.67 -> round = 5
        assert m.key_margin_top == 5
        assert m.key_usable_width == 80 - 2 * 5


class TestRenderMetricsNeo:
    def test_info_screen(self):
        m = RenderMetrics(STREAM_DECK_NEO)
        assert m.screen_width == 248
        assert m.screen_height == 58

    def test_key_size(self):
        m = RenderMetrics(STREAM_DECK_NEO)
        assert m.key_size == (96, 96)


class TestRenderMetricsXL:
    def test_key_count(self):
        m = RenderMetrics(STREAM_DECK_XL)
        assert m.key_count == 32

    def test_key_size(self):
        m = RenderMetrics(STREAM_DECK_XL)
        assert m.key_size == (96, 96)

    def test_no_touchscreen(self):
        m = RenderMetrics(STREAM_DECK_XL)
        assert m.panel_count == 0
