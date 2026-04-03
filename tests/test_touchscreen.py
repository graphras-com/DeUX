"""Tests for deckboard.touchscreen — Widget (abstract), IconWidget, SliderWidget, and TouchScreen."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from PIL import Image

from deckboard.image import WIDGET_HEIGHT, WIDGET_WIDTH
from deckboard.touchscreen import TouchScreen, Widget
from deckboard.widgets.icon_widget import IconWidget
from deckboard.widgets.slider_widget import SliderWidget
from deckboard.widgets.volume import VolumeSlider
from deckboard.widgets.brightness import BrightnessSlider
from deckboard.widgets.equalizer import EqualizerSlider
from deckboard.widgets.balance import BalanceSlider


# ── Widget (abstract base) ──────────────────────────────────────────────


class _ConcreteWidget(Widget):
    """Minimal concrete subclass for testing the abstract base."""

    def render(self) -> Image.Image:
        return Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), "black")


class TestWidgetAbstractBase:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            Widget(0)  # type: ignore[abstract]

    def test_index(self):
        w = _ConcreteWidget(0)
        assert w.index == 0

    def test_custom_index(self):
        w = _ConcreteWidget(3)
        assert w.index == 3

    def test_initially_dirty(self):
        w = _ConcreteWidget(0)
        assert w.is_dirty is True

    def test_mark_clean(self):
        w = _ConcreteWidget(0)
        w.mark_clean()
        assert w.is_dirty is False

    def test_mark_dirty(self):
        w = _ConcreteWidget(0)
        w.mark_clean()
        w.mark_dirty()
        assert w.is_dirty is True

    def test_rendered_initially_none(self):
        w = _ConcreteWidget(0)
        assert w.rendered is None

    def test_set_rendered(self):
        w = _ConcreteWidget(0)
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT))
        w.set_rendered(img)
        assert w.rendered is img
        assert w.is_dirty is False

    def test_on_tap(self):
        w = _ConcreteWidget(0)

        @w.on_tap
        async def handler():
            pass

        assert w._tap_handler is handler

    def test_on_long_press(self):
        w = _ConcreteWidget(0)

        @w.on_long_press
        async def handler():
            pass

        assert w._long_press_handler is handler

    def test_on_drag(self):
        w = _ConcreteWidget(0)

        @w.on_drag
        async def handler(x, y, x_out, y_out):
            pass

        assert w._drag_handler is handler

    def test_on_tap_returns_handler(self):
        w = _ConcreteWidget(0)

        async def handler():
            pass

        result = w.on_tap(handler)
        assert result is handler

    def test_on_long_press_returns_handler(self):
        w = _ConcreteWidget(0)

        async def handler():
            pass

        result = w.on_long_press(handler)
        assert result is handler

    def test_on_drag_returns_handler(self):
        w = _ConcreteWidget(0)

        async def handler(x, y, x_out, y_out):
            pass

        result = w.on_drag(handler)
        assert result is handler

    def test_handle_dial_turn_noop(self):
        w = _ConcreteWidget(0)
        w.handle_dial_turn(1)  # should not raise

    def test_handle_dial_press_noop(self):
        w = _ConcreteWidget(0)
        w.handle_dial_press()  # should not raise

    def test_check_selection_timeout_returns_false(self):
        w = _ConcreteWidget(0)
        assert w.check_selection_timeout() is False

    def test_render_returns_image(self):
        w = _ConcreteWidget(0)
        img = w.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)


# ── IconWidget ──────────────────────────────────────────────────────────


class TestIconWidgetInit:
    def test_index(self, widget: IconWidget):
        assert widget.index == 0

    def test_defaults(self, widget: IconWidget):
        assert widget.icon_name is None
        assert widget.icon_color == "white"
        assert widget.label is None
        assert widget.value is None
        assert widget.rendered is None
        assert widget.is_dirty is True

    def test_custom_index(self):
        w = IconWidget(3)
        assert w.index == 3

    def test_is_widget(self, widget: IconWidget):
        assert isinstance(widget, Widget)


class TestIconWidgetSetIcon:
    def test_sets_icon_name(self, widget: IconWidget):
        widget.set_icon("mdi:volume-high")
        assert widget.icon_name == "mdi:volume-high"

    def test_sets_color(self, widget: IconWidget):
        widget.set_icon("mdi:x", color="#ff0000")
        assert widget.icon_color == "#ff0000"

    def test_default_color(self, widget: IconWidget):
        widget.set_icon("mdi:x")
        assert widget.icon_color == "white"

    def test_marks_dirty(self, widget: IconWidget):
        widget.mark_clean()
        widget.set_icon("mdi:x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: IconWidget):
        assert widget.set_icon("mdi:x") is widget


class TestIconWidgetSetLabel:
    def test_sets_label(self, widget: IconWidget):
        widget.set_label("Volume")
        assert widget.label == "Volume"

    def test_none_removes(self, widget: IconWidget):
        widget.set_label("x")
        widget.set_label(None)
        assert widget.label is None

    def test_marks_dirty(self, widget: IconWidget):
        widget.mark_clean()
        widget.set_label("x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: IconWidget):
        assert widget.set_label("x") is widget


class TestIconWidgetSetValue:
    def test_sets_value(self, widget: IconWidget):
        widget.set_value("75%")
        assert widget.value == "75%"

    def test_none_removes(self, widget: IconWidget):
        widget.set_value("x")
        widget.set_value(None)
        assert widget.value is None

    def test_marks_dirty(self, widget: IconWidget):
        widget.mark_clean()
        widget.set_value("x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: IconWidget):
        assert widget.set_value("x") is widget


class TestIconWidgetClear:
    def test_clears_all(self, widget: IconWidget):
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

    def test_returns_self(self, widget: IconWidget):
        assert widget.clear() is widget


class TestIconWidgetChaining:
    def test_chained_calls(self):
        w = IconWidget(0)
        result = w.set_icon("mdi:x").set_label("L").set_value("V")
        assert result is w
        assert w.icon_name == "mdi:x"
        assert w.label == "L"
        assert w.value == "V"


class TestIconWidgetEventHandlers:
    def test_on_tap(self, widget: IconWidget):
        @widget.on_tap
        async def handler():
            pass

        assert widget._tap_handler is handler

    def test_on_long_press(self, widget: IconWidget):
        @widget.on_long_press
        async def handler():
            pass

        assert widget._long_press_handler is handler

    def test_on_drag(self, widget: IconWidget):
        @widget.on_drag
        async def handler(x, y, x_out, y_out):
            pass

        assert widget._drag_handler is handler

    def test_on_tap_returns_handler(self, widget: IconWidget):
        async def handler():
            pass

        result = widget.on_tap(handler)
        assert result is handler

    def test_on_long_press_returns_handler(self, widget: IconWidget):
        async def handler():
            pass

        result = widget.on_long_press(handler)
        assert result is handler

    def test_on_drag_returns_handler(self, widget: IconWidget):
        async def handler(x, y, x_out, y_out):
            pass

        result = widget.on_drag(handler)
        assert result is handler


class TestIconWidgetRendering:
    def test_set_rendered(self, widget: IconWidget):
        img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT))
        widget.set_rendered(img)
        assert widget.rendered is img
        assert widget.is_dirty is False

    def test_mark_clean(self, widget: IconWidget):
        assert widget.is_dirty is True
        widget.mark_clean()
        assert widget.is_dirty is False

    def test_mark_dirty(self, widget: IconWidget):
        widget.mark_clean()
        assert widget.is_dirty is False
        widget.mark_dirty()
        assert widget.is_dirty is True


class TestIconWidgetRender:
    def test_render_no_icon(self, widget: IconWidget):
        widget.set_label("Test")
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)
        assert img.mode == "RGB"

    def test_render_with_icon_image(self, widget: IconWidget, sample_icon):
        widget.set_icon_image(sample_icon)
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_blank(self, widget: IconWidget):
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_set_icon_image(self, widget: IconWidget, sample_icon):
        widget.set_icon_image(sample_icon)
        # The icon image is used internally during render
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_clear_clears_icon_image(self, widget: IconWidget, sample_icon):
        widget.set_icon_image(sample_icon)
        widget.clear()
        # After clear, icon_image should be None (blank render)
        img = widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)


# ── SliderWidget ────────────────────────────────────────────────────────


class TestSliderWidgetInit:
    def test_is_widget(self):
        sw = SliderWidget(0)
        assert isinstance(sw, Widget)

    def test_index(self, slider_widget: SliderWidget):
        assert slider_widget.index == 0

    def test_no_sliders(self, slider_widget: SliderWidget):
        assert slider_widget.sliders == []
        assert slider_widget.active_slider is None


class TestSliderWidgetAddSlider:
    def test_add_single(self, slider_widget: SliderWidget):
        vol = VolumeSlider("Volume")
        result = slider_widget.add_slider(vol)
        assert result is slider_widget  # chaining
        assert len(slider_widget.sliders) == 1
        assert slider_widget.sliders[0] is vol

    def test_first_is_default(self, slider_widget: SliderWidget):
        vol = VolumeSlider("Volume")
        slider_widget.add_slider(vol)
        assert slider_widget.active_slider is vol
        assert slider_widget.active_slider_index == 0
        assert slider_widget._default_slider_index == 0

    def test_add_multiple(self, slider_widget: SliderWidget):
        s1 = VolumeSlider("Vol")
        s2 = BrightnessSlider("Bri")
        slider_widget.add_slider(s1)
        slider_widget.add_slider(s2)
        assert len(slider_widget.sliders) == 2

    def test_explicit_default(self, slider_widget: SliderWidget):
        s1 = VolumeSlider("Vol")
        s2 = BrightnessSlider("Bri")
        slider_widget.add_slider(s1)
        slider_widget.add_slider(s2, default=True)
        assert slider_widget._default_slider_index == 1
        assert slider_widget.active_slider_index == 1
        assert slider_widget.active_slider is s2

    def test_marks_dirty(self, slider_widget: SliderWidget):
        slider_widget.mark_clean()
        slider_widget.add_slider(VolumeSlider())
        assert slider_widget.is_dirty is True

    def test_rejects_non_slider(self, slider_widget: SliderWidget):
        with pytest.raises(TypeError, match="Expected a Slider instance"):
            slider_widget.add_slider("not a slider")  # type: ignore[arg-type]

    def test_sliders_returns_copy(self, slider_widget: SliderWidget):
        vol = VolumeSlider()
        slider_widget.add_slider(vol)
        sliders = slider_widget.sliders
        sliders.clear()  # mutating the copy
        assert len(slider_widget.sliders) == 1  # original unchanged


class TestSliderWidgetActiveSlider:
    def test_no_sliders(self, slider_widget: SliderWidget):
        assert slider_widget.active_slider is None

    def test_default_active(self, slider_widget: SliderWidget):
        vol = VolumeSlider()
        slider_widget.add_slider(vol)
        assert slider_widget.active_slider is vol


class TestSliderWidgetSelectionTimeout:
    def test_default_timeout(self, slider_widget: SliderWidget):
        assert slider_widget.selection_timeout == 5.0

    def test_set_timeout(self, slider_widget: SliderWidget):
        result = slider_widget.set_selection_timeout(10)
        assert result is slider_widget
        assert slider_widget.selection_timeout == 10.0

    def test_negative_clamped_to_zero(self, slider_widget: SliderWidget):
        slider_widget.set_selection_timeout(-3)
        assert slider_widget.selection_timeout == 0.0


class TestSliderWidgetCycleSlider:
    def test_single_slider_noop(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.mark_clean()
        slider_widget.cycle_active_slider()
        assert slider_widget.active_slider_index == 0
        assert slider_widget.is_dirty is False  # no change

    def test_two_sliders_cycle(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.add_slider(BrightnessSlider())
        assert slider_widget.active_slider_index == 0
        slider_widget.cycle_active_slider()
        assert slider_widget.active_slider_index == 1
        slider_widget.cycle_active_slider()
        assert slider_widget.active_slider_index == 0  # wraps

    def test_marks_dirty(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.add_slider(BrightnessSlider())
        slider_widget.mark_clean()
        slider_widget.cycle_active_slider()
        assert slider_widget.is_dirty is True


class TestSliderWidgetCheckSelectionTimeout:
    def test_no_selection_no_change(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.add_slider(BrightnessSlider())
        # No cycle happened → _last_selection_time is None
        assert slider_widget.check_selection_timeout() is False

    def test_already_at_default(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.add_slider(BrightnessSlider())
        # Even if we set a time, active == default, so no change
        slider_widget._last_selection_time = time.monotonic() - 100
        assert slider_widget.check_selection_timeout() is False

    def test_timeout_disabled(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.add_slider(BrightnessSlider())
        slider_widget.set_selection_timeout(0)
        slider_widget.cycle_active_slider()
        assert slider_widget.check_selection_timeout() is False

    def test_timeout_not_elapsed(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.add_slider(BrightnessSlider())
        slider_widget.set_selection_timeout(999)
        slider_widget.cycle_active_slider()
        assert slider_widget.active_slider_index == 1
        assert slider_widget.check_selection_timeout() is False
        assert slider_widget.active_slider_index == 1  # not reset

    def test_timeout_elapsed_resets(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.add_slider(BrightnessSlider())
        slider_widget.set_selection_timeout(0.01)
        slider_widget.cycle_active_slider()
        assert slider_widget.active_slider_index == 1
        # Fake time passing
        slider_widget._last_selection_time = time.monotonic() - 1.0
        slider_widget.mark_clean()
        assert slider_widget.check_selection_timeout() is True
        assert slider_widget.active_slider_index == 0  # back to default
        assert slider_widget._last_selection_time is None
        assert slider_widget.is_dirty is True


class TestSliderWidgetHandleDialTurn:
    def test_no_sliders_noop(self, slider_widget: SliderWidget):
        slider_widget.handle_dial_turn(1)  # should not raise

    def test_adjusts_active_slider(self, slider_widget: SliderWidget):
        vol = VolumeSlider(value=50, step=5)
        slider_widget.add_slider(vol)
        slider_widget.mark_clean()
        slider_widget.handle_dial_turn(1)
        assert vol.value == 55
        assert slider_widget.is_dirty is True

    def test_adjusts_negative(self, slider_widget: SliderWidget):
        vol = VolumeSlider(value=50, step=5)
        slider_widget.add_slider(vol)
        slider_widget.handle_dial_turn(-2)
        assert vol.value == 40

    def test_resets_selection_timeout_on_non_default(self, slider_widget: SliderWidget):
        """Turning dial while a non-default slider is active should
        reset the selection timeout so it doesn't expire during use."""
        vol = VolumeSlider(value=50, step=5)
        bri = BrightnessSlider(value=50, step=5)
        slider_widget.add_slider(vol, default=True)
        slider_widget.add_slider(bri)

        # Select the non-default slider
        slider_widget.cycle_active_slider()
        assert slider_widget.active_slider_index == 1
        original_time = slider_widget._last_selection_time
        assert original_time is not None

        # Simulate a small delay, then turn the dial
        slider_widget._last_selection_time = time.monotonic() - 3.0
        slider_widget.handle_dial_turn(1)

        # Timeout should have been refreshed to a recent timestamp
        assert slider_widget._last_selection_time is not None
        assert slider_widget._last_selection_time > original_time

    def test_no_timeout_reset_on_default_slider(self, slider_widget: SliderWidget):
        """Turning dial while the default slider is active should NOT
        set _last_selection_time (no timeout to manage)."""
        vol = VolumeSlider(value=50, step=5)
        bri = BrightnessSlider(value=50, step=5)
        slider_widget.add_slider(vol, default=True)
        slider_widget.add_slider(bri)

        # Active slider is already the default (index 0)
        assert slider_widget.active_slider_index == slider_widget._default_slider_index
        assert slider_widget._last_selection_time is None

        slider_widget.handle_dial_turn(1)
        assert slider_widget._last_selection_time is None

    def test_dial_turn_prevents_timeout_expiry(self, slider_widget: SliderWidget):
        """Continuous dial turns should keep the selection alive past
        the configured timeout."""
        vol = VolumeSlider(value=50, step=5)
        bri = BrightnessSlider(value=50, step=5)
        slider_widget.add_slider(vol, default=True)
        slider_widget.add_slider(bri)
        slider_widget.set_selection_timeout(2.0)

        # Select non-default slider
        slider_widget.cycle_active_slider()
        assert slider_widget.active_slider_index == 1

        # Simulate time passing almost to timeout, then turn
        slider_widget._last_selection_time = time.monotonic() - 1.9
        slider_widget.handle_dial_turn(1)

        # Should NOT have timed out
        assert slider_widget.active_slider_index == 1
        assert slider_widget.check_selection_timeout() is False


class TestSliderWidgetHandleDialPress:
    def test_cycles_slider(self, slider_widget: SliderWidget):
        slider_widget.add_slider(VolumeSlider())
        slider_widget.add_slider(BrightnessSlider())
        assert slider_widget.active_slider_index == 0
        slider_widget.handle_dial_press()
        assert slider_widget.active_slider_index == 1


class TestSliderWidgetRender:
    def test_render_empty(self, slider_widget: SliderWidget):
        img = slider_widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)
        assert img.mode == "RGB"

    def test_render_single(self, slider_widget: SliderWidget):
        vol = VolumeSlider("Volume", value=50)
        slider_widget.add_slider(vol)
        img = slider_widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)
        assert img.mode == "RGB"

    def test_render_two_large(self, slider_widget: SliderWidget):
        vol = VolumeSlider("Volume", value=50)
        bri = BrightnessSlider("Bright", value=70)
        slider_widget.add_slider(vol)
        slider_widget.add_slider(bri)
        img = slider_widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_four_small(self, slider_widget: SliderWidget):
        s1 = EqualizerSlider("Sub", value=50)
        s2 = EqualizerSlider("Bass", value=40)
        s3 = EqualizerSlider("Treble", value=60)
        s4 = BalanceSlider("Balance", value=50)
        slider_widget.add_slider(s1)
        slider_widget.add_slider(s2)
        slider_widget.add_slider(s3)
        slider_widget.add_slider(s4)
        img = slider_widget.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)


# ── TouchScreen ─────────────────────────────────────────────────────────


class TestTouchScreenInit:
    def test_creates_four_widgets(self, touchscreen: TouchScreen):
        assert len(touchscreen.widgets) == 4

    def test_widget_indices(self, touchscreen: TouchScreen):
        for i in range(4):
            assert touchscreen.widgets[i].index == i

    def test_default_widgets_are_icon_widgets(self, touchscreen: TouchScreen):
        for w in touchscreen.widgets:
            assert isinstance(w, IconWidget)


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


class TestTouchScreenSetWidget:
    def test_replace_with_slider_widget(self, touchscreen: TouchScreen):
        sw = SliderWidget(0)
        touchscreen.set_widget(0, sw)
        assert touchscreen.widget(0) is sw

    def test_replace_with_custom_widget(self, touchscreen: TouchScreen):
        cw = _ConcreteWidget(2)
        touchscreen.set_widget(2, cw)
        assert touchscreen.widget(2) is cw

    def test_index_too_low(self, touchscreen: TouchScreen):
        with pytest.raises(IndexError, match="Widget index must be 0-3"):
            touchscreen.set_widget(-1, _ConcreteWidget(0))

    def test_index_too_high(self, touchscreen: TouchScreen):
        with pytest.raises(IndexError, match="Widget index must be 0-3"):
            touchscreen.set_widget(4, _ConcreteWidget(0))

    def test_rejects_non_widget(self, touchscreen: TouchScreen):
        with pytest.raises(TypeError, match="Expected a Widget instance"):
            touchscreen.set_widget(0, "not a widget")  # type: ignore[arg-type]


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
        w0 = touchscreen.widget(2)
        assert isinstance(w0, IconWidget)
        w0.set_label("changed")
        assert touchscreen.any_dirty is True
