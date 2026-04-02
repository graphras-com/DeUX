"""Tests for deckboard.widgets.temperature — TemperatureSlider."""

from __future__ import annotations

from PIL import Image

from deckboard.image import WIDGET_HEIGHT, WIDGET_WIDTH
from deckboard.widgets.temperature import TemperatureSlider


class TestTemperatureSliderInit:
    def test_defaults(self):
        s = TemperatureSlider()
        assert s.label == "Temperature"
        assert s.min_value == 15
        assert s.max_value == 25
        assert s.value == 15
        assert s.unit == "\u00b0C"
        assert s.step == 0.5

    def test_custom_params(self):
        s = TemperatureSlider("Room", value=21, min_value=10, max_value=30, step=1)
        assert s.label == "Room"
        assert s.value == 21


class TestTemperatureSliderRender:
    def test_render_at_min(self):
        s = TemperatureSlider(value=15)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 2)

    def test_render_at_mid(self):
        s = TemperatureSlider(value=20)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 2)
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_at_max(self):
        s = TemperatureSlider(value=25)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 2)

    def test_render_active(self):
        s = TemperatureSlider(value=21)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 2, active=True)

    def test_format_value_integer(self):
        s = TemperatureSlider(value=21)
        assert s.format_value() == "21\u00b0C"

    def test_format_value_half(self):
        s = TemperatureSlider(value=21.5)
        assert s.format_value() == "21.5\u00b0C"
