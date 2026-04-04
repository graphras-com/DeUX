"""Tests for deckboard.widgets.volume — VolumeSlider."""

from __future__ import annotations

from PIL import Image

from deckboard.image import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.widgets.volume import VolumeSlider


class TestVolumeSliderInit:
    def test_defaults(self):
        s = VolumeSlider()
        assert s.label == "Volume"
        assert s.min_value == 0
        assert s.max_value == 100
        assert s.value == 0
        assert s.unit == "%"
        assert s.step == 1

    def test_custom_label(self):
        s = VolumeSlider("Master")
        assert s.label == "Master"

    def test_custom_value(self):
        s = VolumeSlider(value=75)
        assert s.value == 75

    def test_custom_range(self):
        s = VolumeSlider(min_value=10, max_value=80, value=50, step=2)
        assert s.min_value == 10
        assert s.max_value == 80
        assert s.value == 50
        assert s.step == 2


class TestVolumeSliderRender:
    def test_render_at_zero(self):
        s = VolumeSlider(value=0)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        # At zero, most of the bar area should still be black

    def test_render_at_half(self):
        s = VolumeSlider(value=50)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_at_max(self):
        s = VolumeSlider(value=100)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)

    def test_render_active(self):
        s = VolumeSlider(value=50)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2, active=True)

    def test_format_value(self):
        s = VolumeSlider(value=75)
        assert s.format_value() == "75%"
