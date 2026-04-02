"""Tests for deckboard.widgets.brightness — BrightnessSlider."""

from __future__ import annotations

from PIL import Image

from deckboard.image import WIDGET_HEIGHT, WIDGET_WIDTH
from deckboard.widgets.brightness import BrightnessSlider


class TestBrightnessSliderInit:
    def test_defaults(self):
        s = BrightnessSlider()
        assert s.label == "Brightness"
        assert s.min_value == 0
        assert s.max_value == 100
        assert s.value == 0
        assert s.unit == "%"
        assert s.step == 1

    def test_custom_params(self):
        s = BrightnessSlider("Screen", value=80, min_value=5, max_value=100, step=5)
        assert s.label == "Screen"
        assert s.value == 80


class TestBrightnessSliderRender:
    def test_render_at_zero(self):
        s = BrightnessSlider(value=0)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 2)

    def test_render_at_half(self):
        s = BrightnessSlider(value=50)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 2)
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_at_max(self):
        s = BrightnessSlider(value=100)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 2)

    def test_render_active(self):
        s = BrightnessSlider(value=50)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 2, active=True)

    def test_has_gradient(self):
        """The gradient should produce non-black pixels in the bar area."""
        s = BrightnessSlider(value=50)
        slot_h = WIDGET_HEIGHT // 2
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, slot_h, WIDGET_WIDTH, slot_h)
        # Check that there are some non-black pixels in the lower area
        has_non_black = False
        for x_px in range(WIDGET_WIDTH):
            for y_px in range(slot_h, WIDGET_HEIGHT):
                if img.getpixel((x_px, y_px)) != (0, 0, 0):
                    has_non_black = True
                    break
            if has_non_black:
                break
        assert has_non_black
