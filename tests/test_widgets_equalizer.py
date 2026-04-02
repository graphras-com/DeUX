"""Tests for deckboard.widgets.equalizer — EqualizerSlider."""

from __future__ import annotations

from PIL import Image

from deckboard.widgets.equalizer import EqualizerSlider


class TestEqualizerSliderInit:
    def test_defaults(self):
        s = EqualizerSlider()
        assert s.label == "EQ"
        assert s.min_value == 0
        assert s.max_value == 100
        assert s.value == 0
        assert s.unit == "%"
        assert s.step == 1

    def test_custom_params(self):
        s = EqualizerSlider("Bass", value=60, min_value=0, max_value=100, step=2)
        assert s.label == "Bass"
        assert s.value == 60


class TestEqualizerSliderRender:
    def test_render_at_zero(self):
        s = EqualizerSlider("Sub", value=0)
        img = Image.new("RGB", (200, 100), "black")
        s.render_onto(img, 0, 0, 200, 25)

    def test_render_at_half(self):
        s = EqualizerSlider("Bass", value=50)
        img = Image.new("RGB", (200, 100), "black")
        s.render_onto(img, 0, 0, 200, 25)
        assert img.size == (200, 100)

    def test_render_at_max(self):
        s = EqualizerSlider("Treble", value=100)
        img = Image.new("RGB", (200, 100), "black")
        s.render_onto(img, 0, 0, 200, 25)

    def test_render_active(self):
        s = EqualizerSlider("Sub", value=50)
        img = Image.new("RGB", (200, 100), "black")
        s.render_onto(img, 0, 0, 200, 25, active=True)
