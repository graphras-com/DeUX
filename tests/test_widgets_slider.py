"""Tests for deckboard.widgets.slider — Slider, LargeSlider, SmallSlider."""

from __future__ import annotations

import pytest
from PIL import Image

from deckboard.image import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.touchscreen import Card
from deckboard.widgets.slider import LargeSlider, Slider, SmallSlider
from deckboard.widgets.touch_panel import StackCard


# ── Concrete test subclasses (since the bases are abstract) ──────────────


class _ConcreteLargeSlider(LargeSlider):
    """Minimal concrete LargeSlider for testing."""

    def _draw_bar_contents(self, draw, img, ix, iy, iw, ih):
        pass  # No-op — just test the frame/layout


class _ConcreteSmallSlider(SmallSlider):
    """Minimal concrete SmallSlider for testing."""

    def _draw_bar_contents(self, draw, img, ix, iy, iw, ih):
        pass


# ── Slider base class ────────────────────────────────────────────────────


class TestSliderInit:
    def test_defaults(self):
        s = _ConcreteLargeSlider("Test")
        assert s.label == "Test"
        assert s.value == 0
        assert s.min_value == 0
        assert s.max_value == 100
        assert s.unit == "%"
        assert s.step == 1

    def test_custom_params(self):
        s = _ConcreteLargeSlider(
            "Vol",
            min_value=10,
            max_value=50,
            value=30,
            unit="dB",
            step=2,
        )
        assert s.label == "Vol"
        assert s.value == 30
        assert s.min_value == 10
        assert s.max_value == 50
        assert s.unit == "dB"
        assert s.step == 2

    def test_value_defaults_to_min(self):
        s = _ConcreteLargeSlider("X", min_value=20, max_value=80)
        assert s.value == 20


class TestSliderNormalized:
    def test_at_min(self):
        s = _ConcreteLargeSlider("X", min_value=0, max_value=100, value=0)
        assert s.normalized == 0.0

    def test_at_max(self):
        s = _ConcreteLargeSlider("X", min_value=0, max_value=100, value=100)
        assert s.normalized == 1.0

    def test_midpoint(self):
        s = _ConcreteLargeSlider("X", min_value=0, max_value=100, value=50)
        assert s.normalized == pytest.approx(0.5)

    def test_custom_range(self):
        s = _ConcreteLargeSlider("X", min_value=2000, max_value=6500, value=3125)
        expected = (3125 - 2000) / (6500 - 2000)
        assert s.normalized == pytest.approx(expected)

    def test_zero_range(self):
        s = _ConcreteLargeSlider("X", min_value=50, max_value=50, value=50)
        assert s.normalized == 0.0

    def test_negative_range(self):
        s = _ConcreteLargeSlider("X", min_value=100, max_value=50, value=75)
        assert s.normalized == 0.0  # span <= 0


class TestSliderSetValue:
    def test_set_normal(self):
        s = _ConcreteLargeSlider("X")
        s.set_value(42)
        assert s.value == 42

    def test_clamp_low(self):
        s = _ConcreteLargeSlider("X", min_value=10, max_value=90)
        s.set_value(-5)
        assert s.value == 10

    def test_clamp_high(self):
        s = _ConcreteLargeSlider("X", min_value=10, max_value=90)
        s.set_value(200)
        assert s.value == 90


class TestSliderAdjust:
    def test_positive_direction(self):
        s = _ConcreteLargeSlider("X", value=50, step=5)
        s.adjust(1)
        assert s.value == 55

    def test_negative_direction(self):
        s = _ConcreteLargeSlider("X", value=50, step=5)
        s.adjust(-1)
        assert s.value == 45

    def test_clamped_at_max(self):
        s = _ConcreteLargeSlider("X", value=98, max_value=100, step=5)
        s.adjust(1)
        assert s.value == 100

    def test_clamped_at_min(self):
        s = _ConcreteLargeSlider("X", value=2, min_value=0, step=5)
        s.adjust(-1)
        assert s.value == 0

    def test_multi_step(self):
        s = _ConcreteLargeSlider("X", value=50, step=5)
        s.adjust(3)
        assert s.value == 65


class TestSliderFormatValue:
    def test_integer_percent(self):
        s = _ConcreteLargeSlider("X", value=50, unit="%")
        assert s.format_value() == "50%"

    def test_float_value(self):
        s = _ConcreteLargeSlider("X", value=20.5, unit="\u00b0C")
        assert s.format_value() == "20.5\u00b0C"

    def test_kelvin(self):
        s = _ConcreteLargeSlider("X", value=3000, unit="K")
        assert s.format_value() == "3000K"

    def test_no_unit(self):
        s = _ConcreteLargeSlider("X", value=42, unit="")
        assert s.format_value() == "42"


class TestSliderDrawRoundedRect:
    def test_draws_without_error(self):
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        from PIL import ImageDraw

        draw = ImageDraw.Draw(img)
        Slider._draw_rounded_rect(
            draw,
            (10, 10, PANEL_WIDTH - 10, PANEL_HEIGHT - 10),
            radius=5,
            fill="white",
            outline="red",
        )
        # No assertion on pixels — just ensure it doesn't raise


class TestSliderDrawGradient:
    def test_gradient_basic(self):
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        Slider._draw_gradient(img, 10, 10, 50, 20, "#000000", "#FFFFFF")
        # Check left edge is dark, right edge is bright
        left_pixel = img.getpixel((10, 20))
        right_pixel = img.getpixel((59, 20))
        assert left_pixel[0] < right_pixel[0]

    def test_gradient_zero_width(self):
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        # Should not raise
        Slider._draw_gradient(img, 10, 10, 0, 20, "#000000", "#FFFFFF")

    def test_gradient_zero_height(self):
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        Slider._draw_gradient(img, 10, 10, 20, 0, "#000000", "#FFFFFF")

    def test_gradient_single_pixel_wide(self):
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        Slider._draw_gradient(img, 10, 10, 1, 10, "#FF0000", "#0000FF")


# ── LargeSlider ─────────────────────────────────────────────────────────


class TestLargeSliderRender:
    def test_renders_card_size_image(self):
        s = _ConcreteLargeSlider("Volume", value=50)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, x=0, y=0, width=PANEL_WIDTH, height=PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_active_highlight(self):
        s = _ConcreteLargeSlider("Volume", value=50)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(
            img, x=0, y=0, width=PANEL_WIDTH, height=PANEL_HEIGHT // 2, active=True
        )
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_at_min(self):
        s = _ConcreteLargeSlider("Volume", value=0)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, x=0, y=0, width=PANEL_WIDTH, height=PANEL_HEIGHT // 2)

    def test_renders_at_max(self):
        s = _ConcreteLargeSlider("Volume", value=100)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, x=0, y=0, width=PANEL_WIDTH, height=PANEL_HEIGHT // 2)


# ── SmallSlider ──────────────────────────────────────────────────────────


class TestSmallSliderRender:
    def test_renders_card_size_image(self):
        s = _ConcreteSmallSlider("Bass", value=50)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, x=0, y=0, width=PANEL_WIDTH, height=PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_active_highlight(self):
        s = _ConcreteSmallSlider("Bass", value=50)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(
            img, x=0, y=0, width=PANEL_WIDTH, height=PANEL_HEIGHT // 4, active=True
        )

    def test_renders_at_min(self):
        s = _ConcreteSmallSlider("Bass", value=0)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, x=0, y=0, width=PANEL_WIDTH, height=PANEL_HEIGHT // 4)

    def test_renders_at_max(self):
        s = _ConcreteSmallSlider("Bass", value=100)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        s.render_onto(img, x=0, y=0, width=PANEL_WIDTH, height=PANEL_HEIGHT // 4)


# ── Abstract class guards ────────────────────────────────────────────────


class TestSliderAbstractGuards:
    def test_cannot_instantiate_slider(self):
        with pytest.raises(TypeError):
            Slider("X")  # type: ignore[abstract]

    def test_cannot_instantiate_large_slider(self):
        with pytest.raises(TypeError):
            LargeSlider("X")  # type: ignore[abstract]

    def test_cannot_instantiate_small_slider(self):
        with pytest.raises(TypeError):
            SmallSlider("X")  # type: ignore[abstract]


# ── Dirty propagation to parent Card ───────────────────────────────────


class TestSliderWidgetBackReference:
    def test_no_card_by_default(self):
        s = _ConcreteLargeSlider("X", value=50)
        assert s._card is None

    def test_add_slider_sets_card(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=50)
        w.add_control(s)
        assert s._card is w

    def test_set_value_marks_card_dirty(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=50)
        w.add_control(s)
        w.mark_clean()
        assert w.is_dirty is False
        s.set_value(75)
        assert w.is_dirty is True

    def test_set_value_without_card_does_not_raise(self):
        s = _ConcreteLargeSlider("X", value=50)
        s.set_value(75)  # no widget attached — should not raise
        assert s.value == 75

    def test_adjust_marks_card_dirty(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=50, step=5)
        w.add_control(s)
        w.mark_clean()
        assert w.is_dirty is False
        s.adjust(1)
        assert s.value == 55
        assert w.is_dirty is True

    def test_adjust_without_card_does_not_raise(self):
        s = _ConcreteLargeSlider("X", value=50, step=5)
        s.adjust(1)
        assert s.value == 55


# ── on_change callback ──────────────────────────────────────────────────


class TestSliderOnChange:
    def test_handler_initially_none(self):
        s = _ConcreteLargeSlider("X", value=50)
        assert s._change_handler is None

    def test_on_change_registers_handler(self):
        s = _ConcreteLargeSlider("X", value=50)

        @s.on_change
        async def handler(value: float):
            pass

        assert s._change_handler is handler

    def test_on_change_returns_handler(self):
        s = _ConcreteLargeSlider("X", value=50)

        async def handler(value: float):
            pass

        result = s.on_change(handler)
        assert result is handler

    def test_set_value_queues_callback_on_card(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=50)
        w.add_control(s)

        @s.on_change
        async def handler(value: float):
            pass

        s.set_value(75)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (75.0,))

    def test_set_value_no_callback_when_value_unchanged(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=50)
        w.add_control(s)

        @s.on_change
        async def handler(value: float):
            pass

        s.set_value(50)  # same value
        callbacks = w.drain_pending_callbacks()
        assert callbacks == []

    def test_set_value_no_callback_without_handler(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=50)
        w.add_control(s)

        s.set_value(75)
        callbacks = w.drain_pending_callbacks()
        assert callbacks == []

    def test_set_value_no_callback_without_card(self):
        s = _ConcreteLargeSlider("X", value=50)

        @s.on_change
        async def handler(value: float):
            pass

        s.set_value(75)  # no widget — should not raise
        assert s.value == 75

    def test_adjust_queues_callback(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=50, step=5)
        w.add_control(s)

        @s.on_change
        async def handler(value: float):
            pass

        s.adjust(1)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (55.0,))

    def test_adjust_no_callback_when_clamped_at_same_value(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=100, max_value=100, step=5)
        w.add_control(s)

        @s.on_change
        async def handler(value: float):
            pass

        s.adjust(1)  # already at max, value stays 100
        callbacks = w.drain_pending_callbacks()
        assert callbacks == []

    def test_multiple_set_value_calls_queue_multiple_callbacks(self):
        w = StackCard(0)
        s = _ConcreteLargeSlider("X", value=50)
        w.add_control(s)

        @s.on_change
        async def handler(value: float):
            pass

        s.set_value(60)
        s.set_value(70)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 2
        assert callbacks[0] == (handler, (60.0,))
        assert callbacks[1] == (handler, (70.0,))
