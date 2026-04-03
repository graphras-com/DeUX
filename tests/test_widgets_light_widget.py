"""Tests for deckboard.widgets.light_widget — LightWidget."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from deckboard.image import WIDGET_HEIGHT, WIDGET_WIDTH
from deckboard.widgets.brightness import BrightnessSlider
from deckboard.widgets.kelvin import KelvinSlider
from deckboard.widgets.light_widget import LightWidget


class TestLightWidgetInit:
    def test_defaults(self):
        w = LightWidget(0)
        assert w.index == 0
        assert w.brightness.label == "Brightness"
        assert w.brightness.value == 100
        assert w.kelvin.label == "Kelvin"
        assert w.kelvin.value == 4000

    def test_custom_values(self):
        w = LightWidget(2, brightness=60, kelvin=3200)
        assert w.brightness.value == 60
        assert w.kelvin.value == 3200

    def test_has_two_elements(self):
        w = LightWidget(0)
        assert len(w.elements) == 2

    def test_has_two_sliders(self):
        w = LightWidget(0)
        assert len(w.sliders) == 2

    def test_slider_types(self):
        w = LightWidget(0)
        assert isinstance(w.brightness, BrightnessSlider)
        assert isinstance(w.kelvin, KelvinSlider)

    def test_default_active_slider_is_brightness(self):
        w = LightWidget(0)
        assert w.active_slider is w.brightness


class TestLightWidgetAccessors:
    def test_brightness_set_value(self):
        w = LightWidget(0)
        w.brightness.set_value(80)
        assert w.brightness.value == 80

    def test_kelvin_set_value(self):
        w = LightWidget(0)
        w.kelvin.set_value(5000)
        assert w.kelvin.value == 5000

    def test_set_value_marks_dirty(self):
        w = LightWidget(0)
        w.mark_clean()
        w.brightness.set_value(50)
        assert w.is_dirty is True

    def test_set_value_clamps_brightness(self):
        w = LightWidget(0)
        w.brightness.set_value(200)
        assert w.brightness.value == 100
        w.brightness.set_value(-10)
        assert w.brightness.value == 0

    def test_set_value_clamps_kelvin(self):
        w = LightWidget(0)
        w.kelvin.set_value(10000)
        assert w.kelvin.value == 6500
        w.kelvin.set_value(500)
        assert w.kelvin.value == 2000


class TestLightWidgetDialInteraction:
    def test_dial_turn_adjusts_active_slider(self):
        w = LightWidget(0, brightness=50)
        w.handle_dial_turn(1)
        assert w.brightness.value == 51

    def test_dial_turn_negative(self):
        w = LightWidget(0, brightness=50)
        w.handle_dial_turn(-1)
        assert w.brightness.value == 49

    def test_dial_press_cycles_active_slider(self):
        w = LightWidget(0)
        assert w.active_slider is w.brightness
        w.handle_dial_press()
        assert w.active_slider is w.kelvin
        w.handle_dial_press()
        assert w.active_slider is w.brightness  # wraps

    def test_dial_turn_after_cycle(self):
        w = LightWidget(0, kelvin=4000)
        w.handle_dial_press()  # now on kelvin
        w.handle_dial_turn(5)
        assert w.kelvin.value == 4500  # step=100, 5 turns = +500

    def test_dial_turn_kelvin_step_size(self):
        """Kelvin slider defaults to step=100."""
        w = LightWidget(0, kelvin=3000)
        w.handle_dial_press()  # switch to kelvin
        w.handle_dial_turn(1)
        assert w.kelvin.value == 3100

    def test_dial_turn_brightness_step_size(self):
        """Brightness slider defaults to step=1."""
        w = LightWidget(0, brightness=50)
        w.handle_dial_turn(1)
        assert w.brightness.value == 51


class TestLightWidgetRender:
    def test_render_returns_correct_size(self):
        w = LightWidget(0)
        img = w.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_with_custom_values(self):
        w = LightWidget(0, brightness=75, kelvin=5500)
        img = w.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_marks_clean_via_check_timeout(self):
        """Render calls check_selection_timeout internally."""
        w = LightWidget(0)
        w.mark_dirty()
        _ = w.render()
        # render itself doesn't mark_clean, but it does call check_selection_timeout

    def test_render_after_dial_interaction(self):
        w = LightWidget(0)
        w.handle_dial_turn(10)
        w.handle_dial_press()
        w.handle_dial_turn(-5)
        img = w.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)


class TestLightWidgetSelectionTimeout:
    def test_selection_timeout_resets_to_default(self):
        w = LightWidget(0)
        w.set_selection_timeout(0.01)
        call_count = 0
        fake_times = [100.0, 200.0]  # press time, then check time (large gap)

        def fake_monotonic() -> float:
            nonlocal call_count
            t = fake_times[min(call_count, len(fake_times) - 1)]
            call_count += 1
            return t

        with patch("deckboard.widgets.touch_panel.time") as mock_time:
            mock_time.monotonic = fake_monotonic
            w.handle_dial_press()  # move to kelvin, records time=100.0
            assert w.active_slider is w.kelvin
            changed = w.check_selection_timeout()  # elapsed=100.0 >= 0.01
        assert changed is True
        assert w.active_slider is w.brightness  # back to default

    def test_no_timeout_when_on_default(self):
        w = LightWidget(0)
        changed = w.check_selection_timeout()
        assert changed is False


class TestLightWidgetIsSubclassOfTouchPanel:
    def test_is_widget(self):
        from deckboard.touchscreen import Widget

        w = LightWidget(0)
        assert isinstance(w, Widget)

    def test_is_touch_panel(self):
        from deckboard.widgets.touch_panel import TouchPanel

        w = LightWidget(0)
        assert isinstance(w, TouchPanel)


class TestLightWidgetOnChangeIntegration:
    """Integration tests: on_change callbacks with LightWidget sliders."""

    def test_on_change_queued_on_set_value(self):
        w = LightWidget(0, brightness=50)
        handler = AsyncMock()
        w.brightness.on_change(handler)
        w.brightness.set_value(75)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (75.0,))

    def test_on_change_queued_on_dial_turn(self):
        w = LightWidget(0, brightness=50)
        handler = AsyncMock()
        w.brightness.on_change(handler)
        w.handle_dial_turn(3)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (53.0,))

    def test_on_change_fires_for_active_slider_only(self):
        w = LightWidget(0, brightness=50, kelvin=4000)
        bright_handler = AsyncMock()
        kelvin_handler = AsyncMock()
        w.brightness.on_change(bright_handler)
        w.kelvin.on_change(kelvin_handler)
        w.handle_dial_turn(5)  # brightness is active by default
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0][0] is bright_handler

    def test_on_change_follows_active_slider_after_press(self):
        w = LightWidget(0, brightness=50, kelvin=4000)
        bright_handler = AsyncMock()
        kelvin_handler = AsyncMock()
        w.brightness.on_change(bright_handler)
        w.kelvin.on_change(kelvin_handler)
        w.handle_dial_press()  # switch to kelvin
        w.drain_pending_callbacks()  # clear any pending
        w.handle_dial_turn(2)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0][0] is kelvin_handler
        assert callbacks[0][1] == (4200.0,)

    def test_on_change_not_queued_when_clamped_at_max(self):
        w = LightWidget(0, brightness=100)
        handler = AsyncMock()
        w.brightness.on_change(handler)
        w.handle_dial_turn(1)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_on_change_not_queued_when_clamped_at_min(self):
        w = LightWidget(0, brightness=0)
        handler = AsyncMock()
        w.brightness.on_change(handler)
        w.handle_dial_turn(-1)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_both_sliders_with_handlers_independent(self):
        w = LightWidget(0, brightness=50, kelvin=4000)
        bright_handler = AsyncMock()
        kelvin_handler = AsyncMock()
        w.brightness.on_change(bright_handler)
        w.kelvin.on_change(kelvin_handler)
        # Programmatic set_value on both sliders
        w.brightness.set_value(60)
        w.kelvin.set_value(5000)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 2
        handlers = [cb[0] for cb in callbacks]
        assert bright_handler in handlers
        assert kelvin_handler in handlers

    def test_kelvin_slider_on_change(self):
        w = LightWidget(0, kelvin=4000)
        handler = AsyncMock()
        w.kelvin.on_change(handler)
        w.kelvin.set_value(5500)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (5500.0,))

    def test_drain_clears_pending(self):
        w = LightWidget(0, brightness=50)
        handler = AsyncMock()
        w.brightness.on_change(handler)
        w.brightness.set_value(60)
        w.drain_pending_callbacks()
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0
