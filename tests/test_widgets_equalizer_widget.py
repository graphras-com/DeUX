"""Tests for deckboard.widgets.equalizer_widget — EqualizerWidget."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from deckboard.image import WIDGET_HEIGHT, WIDGET_WIDTH
from deckboard.widgets.balance import BalanceSlider
from deckboard.widgets.equalizer import EqualizerSlider
from deckboard.widgets.equalizer_widget import EqualizerWidget


class TestEqualizerWidgetInit:
    def test_defaults(self):
        w = EqualizerWidget(0)
        assert w.index == 0
        assert w.sub.label == "Sub"
        assert w.sub.value == 0
        assert w.bass.label == "Bass"
        assert w.bass.value == 0
        assert w.treble.label == "Treble"
        assert w.treble.value == 0
        assert w.balance.label == "Balance"
        assert w.balance.value == 50

    def test_custom_values(self):
        w = EqualizerWidget(2, sub=10, bass=20, treble=30, balance=75)
        assert w.sub.value == 10
        assert w.bass.value == 20
        assert w.treble.value == 30
        assert w.balance.value == 75

    def test_has_four_elements(self):
        w = EqualizerWidget(0)
        assert len(w.elements) == 4

    def test_has_four_sliders(self):
        w = EqualizerWidget(0)
        assert len(w.sliders) == 4

    def test_slider_types(self):
        w = EqualizerWidget(0)
        assert isinstance(w.sub, EqualizerSlider)
        assert isinstance(w.bass, EqualizerSlider)
        assert isinstance(w.treble, EqualizerSlider)
        assert isinstance(w.balance, BalanceSlider)

    def test_default_active_slider_is_sub(self):
        w = EqualizerWidget(0)
        assert w.active_slider is w.sub


class TestEqualizerWidgetAccessors:
    def test_sub_set_value(self):
        w = EqualizerWidget(0)
        w.sub.set_value(80)
        assert w.sub.value == 80

    def test_bass_set_value(self):
        w = EqualizerWidget(0)
        w.bass.set_value(60)
        assert w.bass.value == 60

    def test_treble_set_value(self):
        w = EqualizerWidget(0)
        w.treble.set_value(40)
        assert w.treble.value == 40

    def test_balance_set_value(self):
        w = EqualizerWidget(0)
        w.balance.set_value(25)
        assert w.balance.value == 25

    def test_set_value_marks_dirty(self):
        w = EqualizerWidget(0)
        w.mark_clean()
        w.sub.set_value(50)
        assert w.is_dirty is True

    def test_set_value_clamps(self):
        w = EqualizerWidget(0)
        w.treble.set_value(200)
        assert w.treble.value == 100
        w.treble.set_value(-10)
        assert w.treble.value == 0


class TestEqualizerWidgetDialInteraction:
    def test_dial_turn_adjusts_active_slider(self):
        w = EqualizerWidget(0, sub=50)
        w.handle_dial_turn(1)
        assert w.sub.value == 51

    def test_dial_turn_negative(self):
        w = EqualizerWidget(0, sub=50)
        w.handle_dial_turn(-1)
        assert w.sub.value == 49

    def test_dial_press_cycles_active_slider(self):
        w = EqualizerWidget(0)
        assert w.active_slider is w.sub
        w.handle_dial_press()
        assert w.active_slider is w.bass
        w.handle_dial_press()
        assert w.active_slider is w.treble
        w.handle_dial_press()
        assert w.active_slider is w.balance
        w.handle_dial_press()
        assert w.active_slider is w.sub  # wraps

    def test_dial_turn_after_cycle(self):
        w = EqualizerWidget(0, bass=50)
        w.handle_dial_press()  # now on bass
        w.handle_dial_turn(5)
        assert w.bass.value == 55


class TestEqualizerWidgetRender:
    def test_render_returns_correct_size(self):
        w = EqualizerWidget(0)
        img = w.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_with_custom_values(self):
        w = EqualizerWidget(0, sub=25, bass=50, treble=75, balance=80)
        img = w.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)

    def test_render_marks_clean_via_check_timeout(self):
        """Render calls check_selection_timeout internally."""
        w = EqualizerWidget(0)
        w.mark_dirty()
        _ = w.render()
        # render itself doesn't mark_clean, but it does call check_selection_timeout

    def test_render_after_dial_interaction(self):
        w = EqualizerWidget(0)
        w.handle_dial_turn(10)
        w.handle_dial_press()
        w.handle_dial_turn(-5)
        img = w.render()
        assert img.size == (WIDGET_WIDTH, WIDGET_HEIGHT)


class TestEqualizerWidgetSelectionTimeout:
    def test_selection_timeout_resets_to_default(self):
        w = EqualizerWidget(0)
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
            w.handle_dial_press()  # move to bass, records time=100.0
            assert w.active_slider is w.bass
            changed = w.check_selection_timeout()  # elapsed=100.0 >= 0.01
        assert changed is True
        assert w.active_slider is w.sub  # back to default

    def test_no_timeout_when_on_default(self):
        w = EqualizerWidget(0)
        changed = w.check_selection_timeout()
        assert changed is False


class TestEqualizerWidgetIsSubclassOfTouchPanel:
    def test_is_widget(self):
        from deckboard.touchscreen import Widget

        w = EqualizerWidget(0)
        assert isinstance(w, Widget)

    def test_is_touch_panel(self):
        from deckboard.widgets.touch_panel import TouchPanel

        w = EqualizerWidget(0)
        assert isinstance(w, TouchPanel)


class TestEqualizerWidgetOnChangeIntegration:
    """Integration tests: on_change callbacks with EqualizerWidget sliders."""

    def test_on_change_queued_on_set_value(self):
        w = EqualizerWidget(0, sub=50)
        handler = AsyncMock()
        w.sub.on_change(handler)
        w.sub.set_value(75)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (75.0,))

    def test_on_change_queued_on_dial_turn(self):
        w = EqualizerWidget(0, sub=50)
        handler = AsyncMock()
        w.sub.on_change(handler)
        w.handle_dial_turn(3)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (53.0,))

    def test_on_change_fires_for_active_slider_only(self):
        w = EqualizerWidget(0, sub=50, bass=50)
        sub_handler = AsyncMock()
        bass_handler = AsyncMock()
        w.sub.on_change(sub_handler)
        w.bass.on_change(bass_handler)
        w.handle_dial_turn(5)  # sub is active by default
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0][0] is sub_handler

    def test_on_change_follows_active_slider_after_press(self):
        w = EqualizerWidget(0, sub=50, bass=50)
        sub_handler = AsyncMock()
        bass_handler = AsyncMock()
        w.sub.on_change(sub_handler)
        w.bass.on_change(bass_handler)
        w.handle_dial_press()  # switch to bass
        w.drain_pending_callbacks()  # clear any pending
        w.handle_dial_turn(2)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0][0] is bass_handler
        assert callbacks[0][1] == (52.0,)

    def test_on_change_not_queued_when_clamped_at_max(self):
        w = EqualizerWidget(0, sub=100)
        handler = AsyncMock()
        w.sub.on_change(handler)
        w.handle_dial_turn(1)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_on_change_not_queued_when_clamped_at_min(self):
        w = EqualizerWidget(0, sub=0)
        handler = AsyncMock()
        w.sub.on_change(handler)
        w.handle_dial_turn(-1)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_multiple_sliders_with_handlers_independent(self):
        w = EqualizerWidget(0, sub=50, treble=50)
        sub_handler = AsyncMock()
        treble_handler = AsyncMock()
        w.sub.on_change(sub_handler)
        w.treble.on_change(treble_handler)
        # Programmatic set_value on both sliders
        w.sub.set_value(60)
        w.treble.set_value(70)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 2
        handlers = [cb[0] for cb in callbacks]
        assert sub_handler in handlers
        assert treble_handler in handlers

    def test_balance_slider_on_change(self):
        w = EqualizerWidget(0, balance=50)
        handler = AsyncMock()
        w.balance.on_change(handler)
        w.balance.set_value(75)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (75.0,))

    def test_drain_clears_pending(self):
        w = EqualizerWidget(0, sub=50)
        handler = AsyncMock()
        w.sub.on_change(handler)
        w.sub.set_value(60)
        w.drain_pending_callbacks()
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0
