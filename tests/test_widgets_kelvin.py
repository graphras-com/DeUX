"""Tests for deckboard.widgets.kelvin — KelvinSlider."""

from __future__ import annotations

from PIL import Image

from deckboard.image import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.widgets.kelvin import KelvinSlider


class TestKelvinSliderInit:
    def test_defaults(self):
        s = KelvinSlider()
        assert s.label == "Kelvin"
        assert s.min_value == 2000
        assert s.max_value == 6500
        assert s.value == 2000
        assert s.unit == "K"
        assert s.step == 100

    def test_custom_params(self):
        s = KelvinSlider("Light Temp", value=4000, min_value=2700, max_value=6500)
        assert s.label == "Light Temp"
        assert s.value == 4000


class TestKelvinSliderRender:
    def test_render_at_min(self):
        s = KelvinSlider(value=2000)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)

    def test_render_at_mid(self):
        s = KelvinSlider(value=4000)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_at_max(self):
        s = KelvinSlider(value=6500)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)

    def test_render_active(self):
        s = KelvinSlider(value=3000)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2, active=True)

    def test_format_value(self):
        s = KelvinSlider(value=3000)
        assert s.format_value() == "3000K"
