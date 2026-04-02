"""Tests for deckboard.widgets.balance — BalanceSlider."""

from __future__ import annotations

import pytest
from PIL import Image

from deckboard.image import WIDGET_HEIGHT, WIDGET_WIDTH
from deckboard.widgets.balance import BalanceSlider


class TestBalanceSliderInit:
    def test_defaults(self):
        s = BalanceSlider()
        assert s.label == "Balance"
        assert s.min_value == 0
        assert s.max_value == 100
        assert s.value == 50  # centre by default
        assert s.unit == ""
        assert s.step == 1

    def test_custom_label(self):
        s = BalanceSlider("Pan")
        assert s.label == "Pan"

    def test_custom_value(self):
        s = BalanceSlider(value=75)
        assert s.value == 75


class TestBalanceSliderRender:
    def test_render_at_centre(self):
        """Both speakers full when centred (value=50)."""
        s = BalanceSlider(value=50)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 4)
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_full_left(self):
        """Only left speaker at value=0."""
        s = BalanceSlider(value=0)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 4)

    def test_render_full_right(self):
        """Only right speaker at value=100."""
        s = BalanceSlider(value=100)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 4)

    def test_render_active(self):
        s = BalanceSlider(value=50)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, WIDGET_HEIGHT // 4, active=True)

    def test_centre_line_drawn(self):
        """The centre line should produce a dark pixel at the midpoint."""
        s = BalanceSlider(value=50)
        slot_h = WIDGET_HEIGHT // 4
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "white")
        s.render_onto(img, 0, 0, WIDGET_WIDTH, slot_h)
        # The centre of the bar area should have the black centre line
        # bar_x starts at ~56, bar_w = WIDGET_WIDTH - 56, centre ≈ 56 + bar_w/2
        centre_x = 56 + (WIDGET_WIDTH - 56) // 2
        found_dark = False
        for y_px in range(0, slot_h):
            px = img.getpixel((centre_x, y_px))
            if px[0] < 50 and px[1] < 50 and px[2] < 50:
                found_dark = True
                break
        assert found_dark


class TestBalanceSliderSemantics:
    def test_normalized_at_centre(self):
        s = BalanceSlider(value=50)
        assert s.normalized == pytest.approx(0.5)

    def test_normalized_at_full_left(self):
        s = BalanceSlider(value=0)
        assert s.normalized == 0.0

    def test_normalized_at_full_right(self):
        s = BalanceSlider(value=100)
        assert s.normalized == 1.0
