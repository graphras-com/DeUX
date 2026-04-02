"""Tests for deckboard.touchscreen — Widget and TouchScreen classes."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from PIL import Image

from deckboard.image import WIDGET_HEIGHT, WIDGET_WIDTH
from deckboard.touchscreen import TouchScreen, Widget
from deckboard.widgets.volume import VolumeSlider
from deckboard.widgets.brightness import BrightnessSlider
from deckboard.widgets.equalizer import EqualizerSlider
from deckboard.widgets.balance import BalanceSlider


# ── Widget ──────────────────────────────────────────────────────────────


class TestWidgetInit:
    def test_index(self, widget: Widget):
        assert widget.index == 0

    def test_defaults(self, widget: Widget):
        assert widget.icon_name is None
        assert widget.icon_color == "white"
        assert widget.label is None
        assert widget.value is None
        assert widget.rendered is None
        assert widget.is_dirty is True

    def test_custom_index(self):
        w = Widget(3)
        assert w.index == 3


class TestWidgetSetIcon:
    def test_sets_icon_name(self, widget: Widget):
        widget.set_icon("mdi:volume-high")
        assert widget.icon_name == "mdi:volume-high"

    def test_sets_color(self, widget: Widget):
        widget.set_icon("mdi:x", color="#ff0000")
        assert widget.icon_color == "#ff0000"

    def test_default_color(self, widget: Widget):
        widget.set_icon("mdi:x")
        assert widget.icon_color == "white"

    def test_marks_dirty(self, widget: Widget):
        widget.mark_clean()
        widget.set_icon("mdi:x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: Widget):
        assert widget.set_icon("mdi:x") is widget


class TestWidgetSetLabel:
    def test_sets_label(self, widget: Widget):
        widget.set_label("Volume")
        assert widget.label == "Volume"

    def test_none_removes(self, widget: Widget):
        widget.set_label("x")
        widget.set_label(None)
        assert widget.label is None

    def test_marks_dirty(self, widget: Widget):
        widget.mark_clean()
        widget.set_label("x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: Widget):
        assert widget.set_label("x") is widget


class TestWidgetSetValue:
    def test_sets_value(self, widget: Widget):
        widget.set_value("75%")
        assert widget.value == "75%"

    def test_none_removes(self, widget: Widget):
        widget.set_value("x")
        widget.set_value(None)
        assert widget.value is None

    def test_marks_dirty(self, widget: Widget):
        widget.mark_clean()
        widget.set_value("x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: Widget):
        assert widget.set_value("x") is widget


class TestWidgetClear:
    def test_clears_all(self, widget: Widget):
        widget.set_icon("mdi:x")
        widget.set_label("L")
        widget.set_value("V")
        widget.set_rendered(Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT)))
        widget.clear()
        assert widget.icon_name is None
        assert widget.label is None
        assert widget.value is None
        assert widget.rendered is None
        assert widget.is_dirty is True

    def test_returns_self(self, widget: Widget):
        assert widget.clear() is widget


class TestWidgetChaining:
    def test_chained_calls(self):
        w = Widget(0)
        result = w.set_icon("mdi:x").set_label("L").set_value("V")
        assert result is w
        assert w.icon_name == "mdi:x"
        assert w.label == "L"
        assert w.value == "V"


class TestWidgetEventHandlers:
    def test_on_tap(self, widget: Widget):
        @widget.on_tap
        async def handler():
            pass

        assert widget._tap_handler is handler

    def test_on_long_press(self, widget: Widget):
        @widget.on_long_press
        async def handler():
            pass

        assert widget._long_press_handler is handler

    def test_on_drag(self, widget: Widget):
        @widget.on_drag
        async def handler(x, y, x_out, y_out):
            pass

        assert widget._drag_handler is handler

    def test_on_tap_returns_handler(self, widget: Widget):
        async def handler():
            pass

        result = widget.on_tap(handler)
        assert result is handler

    def test_on_long_press_returns_handler(self, widget: Widget):
        async def handler():
            pass

        result = widget.on_long_press(handler)
        assert result is handler

    def test_on_drag_returns_handler(self, widget: Widget):
        async def handler(x, y, x_out, y_out):
            pass

        result = widget.on_drag(handler)
        assert result is handler


class TestWidgetRendering:
    def test_set_rendered(self, widget: Widget):
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT))
        widget.set_rendered(img)
        assert widget.rendered is img
        assert widget.is_dirty is False

    def test_mark_clean(self, widget: Widget):
        assert widget.is_dirty is True
        widget.mark_clean()
        assert widget.is_dirty is False


# ── TouchScreen ─────────────────────────────────────────────────────────


class TestTouchScreenInit:
    def test_creates_four_widgets(self, touchscreen: TouchScreen):
        assert len(touchscreen.widgets) == 4

    def test_widget_indices(self, touchscreen: TouchScreen):
        for i in range(4):
            assert touchscreen.widgets[i].index == i


class TestTouchScreenWidget:
    def test_get_by_index(self, touchscreen: TouchScreen):
        for i in range(4):
            w = touchscreen.widget(i)
            assert isinstance(w, Widget)
            assert w.index == i

    def test_same_instance(self, touchscreen: TouchScreen):
        """widget(i) returns the same object each time."""
        a = touchscreen.widget(0)
        b = touchscreen.widget(0)
        assert a is b

    def test_index_too_low(self, touchscreen: TouchScreen):
        with pytest.raises(IndexError, match="Widget index must be 0-3"):
            touchscreen.widget(-1)

    def test_index_too_high(self, touchscreen: TouchScreen):
        with pytest.raises(IndexError, match="Widget index must be 0-3"):
            touchscreen.widget(4)


class TestTouchScreenAnyDirty:
    def test_initially_dirty(self, touchscreen: TouchScreen):
        assert touchscreen.any_dirty is True

    def test_all_clean(self, touchscreen: TouchScreen):
        for w in touchscreen.widgets:
            w.mark_clean()
        assert touchscreen.any_dirty is False

    def test_one_dirty(self, touchscreen: TouchScreen):
        for w in touchscreen.widgets:
            w.mark_clean()
        touchscreen.widget(2).set_label("changed")
        assert touchscreen.any_dirty is True


# ── Widget.render() ─────────────────────────────────────────────────────


class TestWidgetRender:
    def test_classic_render_no_icon(self, widget: Widget):
        """render() without sliders uses classic icon+label+value layout."""
        widget.set_label("Test")
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)
        assert img.mode == "RGB"

    def test_classic_render_with_icon(self, widget: Widget, sample_icon):
        img = widget.render(icon=sample_icon)
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_classic_render_blank(self, widget: Widget):
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_slider_render_single(self, widget: Widget):
        vol = VolumeSlider("Volume", value=50)
        widget.add_slider(vol)
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)
        assert img.mode == "RGB"

    def test_slider_render_two_large(self, widget: Widget):
        vol = VolumeSlider("Volume", value=50)
        bri = BrightnessSlider("Bright", value=70)
        widget.add_slider(vol)
        widget.add_slider(bri)
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_slider_render_four_small(self, widget: Widget):
        s1 = EqualizerSlider("Sub", value=50)
        s2 = EqualizerSlider("Bass", value=40)
        s3 = EqualizerSlider("Treble", value=60)
        s4 = BalanceSlider("Balance", value=50)
        widget.add_slider(s1)
        widget.add_slider(s2)
        widget.add_slider(s3)
        widget.add_slider(s4)
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_slider_render_ignores_icon(self, widget: Widget, sample_icon):
        """When sliders are present, the icon argument is ignored."""
        vol = VolumeSlider("Volume", value=50)
        widget.add_slider(vol)
        img_with = widget.render(icon=sample_icon)
        img_without = widget.render()
        # Both should produce the same slider image (icon ignored)
        assert img_with.size == img_without.size


# ── Widget slider sub-element management ────────────────────────────────


class TestWidgetAddSlider:
    def test_add_single(self, widget: Widget):
        vol = VolumeSlider("Volume")
        result = widget.add_slider(vol)
        assert result is widget  # chaining
        assert len(widget.sliders) == 1
        assert widget.sliders[0] is vol

    def test_first_is_default(self, widget: Widget):
        vol = VolumeSlider("Volume")
        widget.add_slider(vol)
        assert widget.active_slider is vol
        assert widget.active_slider_index == 0
        assert widget._default_slider_index == 0

    def test_add_multiple(self, widget: Widget):
        s1 = VolumeSlider("Vol")
        s2 = BrightnessSlider("Bri")
        widget.add_slider(s1)
        widget.add_slider(s2)
        assert len(widget.sliders) == 2

    def test_explicit_default(self, widget: Widget):
        s1 = VolumeSlider("Vol")
        s2 = BrightnessSlider("Bri")
        widget.add_slider(s1)
        widget.add_slider(s2, default=True)
        assert widget._default_slider_index == 1
        assert widget.active_slider_index == 1
        assert widget.active_slider is s2

    def test_marks_dirty(self, widget: Widget):
        widget.mark_clean()
        widget.add_slider(VolumeSlider())
        assert widget.is_dirty is True

    def test_rejects_non_slider(self, widget: Widget):
        with pytest.raises(TypeError, match="Expected a Slider instance"):
            widget.add_slider("not a slider")  # type: ignore[arg-type]

    def test_sliders_returns_copy(self, widget: Widget):
        vol = VolumeSlider()
        widget.add_slider(vol)
        sliders = widget.sliders
        sliders.clear()  # mutating the copy
        assert len(widget.sliders) == 1  # original unchanged


class TestWidgetActiveSlider:
    def test_no_sliders(self, widget: Widget):
        assert widget.active_slider is None

    def test_default_active(self, widget: Widget):
        vol = VolumeSlider()
        widget.add_slider(vol)
        assert widget.active_slider is vol


class TestWidgetSelectionTimeout:
    def test_default_timeout(self, widget: Widget):
        assert widget.selection_timeout == 5.0

    def test_set_timeout(self, widget: Widget):
        result = widget.set_selection_timeout(10)
        assert result is widget
        assert widget.selection_timeout == 10.0

    def test_negative_clamped_to_zero(self, widget: Widget):
        widget.set_selection_timeout(-3)
        assert widget.selection_timeout == 0.0


class TestWidgetCycleSlider:
    def test_single_slider_noop(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.mark_clean()
        widget.cycle_active_slider()
        assert widget.active_slider_index == 0
        assert widget.is_dirty is False  # no change

    def test_two_sliders_cycle(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.add_slider(BrightnessSlider())
        assert widget.active_slider_index == 0
        widget.cycle_active_slider()
        assert widget.active_slider_index == 1
        widget.cycle_active_slider()
        assert widget.active_slider_index == 0  # wraps

    def test_marks_dirty(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.add_slider(BrightnessSlider())
        widget.mark_clean()
        widget.cycle_active_slider()
        assert widget.is_dirty is True


class TestWidgetCheckSelectionTimeout:
    def test_no_selection_no_change(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.add_slider(BrightnessSlider())
        # No cycle happened → _last_selection_time is None
        assert widget.check_selection_timeout() is False

    def test_already_at_default(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.add_slider(BrightnessSlider())
        # Even if we set a time, active == default, so no change
        widget._last_selection_time = time.monotonic() - 100
        assert widget.check_selection_timeout() is False

    def test_timeout_disabled(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.add_slider(BrightnessSlider())
        widget.set_selection_timeout(0)
        widget.cycle_active_slider()
        assert widget.check_selection_timeout() is False

    def test_timeout_not_elapsed(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.add_slider(BrightnessSlider())
        widget.set_selection_timeout(999)
        widget.cycle_active_slider()
        assert widget.active_slider_index == 1
        assert widget.check_selection_timeout() is False
        assert widget.active_slider_index == 1  # not reset

    def test_timeout_elapsed_resets(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.add_slider(BrightnessSlider())
        widget.set_selection_timeout(0.01)
        widget.cycle_active_slider()
        assert widget.active_slider_index == 1
        # Fake time passing
        widget._last_selection_time = time.monotonic() - 1.0
        widget.mark_clean()
        assert widget.check_selection_timeout() is True
        assert widget.active_slider_index == 0  # back to default
        assert widget._last_selection_time is None
        assert widget.is_dirty is True


class TestWidgetHandleDialTurn:
    def test_no_sliders_noop(self, widget: Widget):
        widget.handle_dial_turn(1)  # should not raise

    def test_adjusts_active_slider(self, widget: Widget):
        vol = VolumeSlider(value=50, step=5)
        widget.add_slider(vol)
        widget.mark_clean()
        widget.handle_dial_turn(1)
        assert vol.value == 55
        assert widget.is_dirty is True

    def test_adjusts_negative(self, widget: Widget):
        vol = VolumeSlider(value=50, step=5)
        widget.add_slider(vol)
        widget.handle_dial_turn(-2)
        assert vol.value == 40

    def test_resets_selection_timeout_on_non_default(self, widget: Widget):
        """Turning dial while a non-default slider is active should
        reset the selection timeout so it doesn't expire during use."""
        vol = VolumeSlider(value=50, step=5)
        bri = BrightnessSlider(value=50, step=5)
        widget.add_slider(vol, default=True)
        widget.add_slider(bri)

        # Select the non-default slider
        widget.cycle_active_slider()
        assert widget.active_slider_index == 1
        original_time = widget._last_selection_time
        assert original_time is not None

        # Simulate a small delay, then turn the dial
        widget._last_selection_time = time.monotonic() - 3.0
        widget.handle_dial_turn(1)

        # Timeout should have been refreshed to a recent timestamp
        assert widget._last_selection_time is not None
        assert widget._last_selection_time > original_time

    def test_no_timeout_reset_on_default_slider(self, widget: Widget):
        """Turning dial while the default slider is active should NOT
        set _last_selection_time (no timeout to manage)."""
        vol = VolumeSlider(value=50, step=5)
        bri = BrightnessSlider(value=50, step=5)
        widget.add_slider(vol, default=True)
        widget.add_slider(bri)

        # Active slider is already the default (index 0)
        assert widget.active_slider_index == widget._default_slider_index
        assert widget._last_selection_time is None

        widget.handle_dial_turn(1)
        assert widget._last_selection_time is None

    def test_dial_turn_prevents_timeout_expiry(self, widget: Widget):
        """Continuous dial turns should keep the selection alive past
        the configured timeout."""
        vol = VolumeSlider(value=50, step=5)
        bri = BrightnessSlider(value=50, step=5)
        widget.add_slider(vol, default=True)
        widget.add_slider(bri)
        widget.set_selection_timeout(2.0)

        # Select non-default slider
        widget.cycle_active_slider()
        assert widget.active_slider_index == 1

        # Simulate time passing almost to timeout, then turn
        widget._last_selection_time = time.monotonic() - 1.9
        widget.handle_dial_turn(1)

        # Should NOT have timed out
        assert widget.active_slider_index == 1
        assert widget.check_selection_timeout() is False


class TestWidgetHandleDialPress:
    def test_cycles_slider(self, widget: Widget):
        widget.add_slider(VolumeSlider())
        widget.add_slider(BrightnessSlider())
        assert widget.active_slider_index == 0
        widget.handle_dial_press()
        assert widget.active_slider_index == 1
