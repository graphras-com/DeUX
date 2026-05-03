"""Tests for deckui.render.metrics — RenderMetrics class."""

from __future__ import annotations

from deckui.render.metrics import RenderMetrics
from deckui.runtime.capabilities import STREAM_DECK_PLUS
from tests.conftest import STREAM_DECK_MINI, STREAM_DECK_NEO, STREAM_DECK_XL


class TestRenderMetricsPlus:
    def test_key_metrics(self):
        m = RenderMetrics(STREAM_DECK_PLUS)
        assert m.key_size == (120, 120)
        assert m.key_count == 8
        assert m.dial_count == 4

    def test_panel_metrics_no_gap(self):
        """Panels tile edge-to-edge: panel_width = touchscreen_width // panel_count."""
        m = RenderMetrics(STREAM_DECK_PLUS)
        assert m.panel_count == 4
        assert m.panel_width == 200
        assert m.panel_height == 100

    def test_touchscreen_metrics(self):
        m = RenderMetrics(STREAM_DECK_PLUS)
        assert m.touchscreen_width == 800
        assert m.touchscreen_height == 100

    def test_key_image_format(self):
        m = RenderMetrics(STREAM_DECK_PLUS)
        assert m.key_image_format == "JPEG"


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


class TestRenderMetricsNeo:
    def test_info_screen(self):
        m = RenderMetrics(STREAM_DECK_NEO)
        assert m.screen_width == 248
        assert m.screen_height == 58

    def test_key_size(self):
        m = RenderMetrics(STREAM_DECK_NEO)
        assert m.key_size == (96, 96)

    def test_no_touchscreen(self):
        m = RenderMetrics(STREAM_DECK_NEO)
        assert m.panel_width == 0
        assert m.panel_height == 0


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
        assert m.panel_width == 0
        assert m.panel_height == 0
