"""Tests for deckboard.widgets.media_widget — MediaCard."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from deckboard.image import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.widgets.media_widget import MediaCard
from deckboard.widgets.text import LargeText
from deckboard.widgets.volume import VolumeSlider


class TestMediaWidgetInit:
    def test_defaults(self):
        w = MediaCard(0)
        assert w.index == 0
        assert w.title_text.text == "No Media"
        assert w.volume.label == "Volume"
        assert w.volume.value == 50
        assert w.muted is False

    def test_custom_values(self):
        w = MediaCard(2, title="Bohemian Rhapsody", volume=75)
        assert w.title_text.text == "Bohemian Rhapsody"
        assert w.volume.value == 75

    def test_has_two_elements(self):
        w = MediaCard(0)
        assert len(w.elements) == 2

    def test_has_one_slider(self):
        w = MediaCard(0)
        assert len(w.controls) == 1

    def test_element_types(self):
        w = MediaCard(0)
        assert isinstance(w.title_text, LargeText)
        assert isinstance(w.volume, VolumeSlider)

    def test_default_active_control_is_volume(self):
        w = MediaCard(0)
        assert w.active_control is w.volume


class TestMediaWidgetAccessors:
    def test_title_text_set_text(self):
        w = MediaCard(0)
        w.title_text.set_text("New Song")
        assert w.title_text.text == "New Song"

    def test_volume_set_value(self):
        w = MediaCard(0)
        w.volume.set_value(80)
        assert w.volume.value == 80

    def test_set_text_marks_dirty(self):
        w = MediaCard(0)
        w.mark_clean()
        w.title_text.set_text("Changed")
        assert w.is_dirty is True

    def test_set_value_marks_dirty(self):
        w = MediaCard(0)
        w.mark_clean()
        w.volume.set_value(30)
        assert w.is_dirty is True

    def test_set_value_clamps(self):
        w = MediaCard(0)
        w.volume.set_value(200)
        assert w.volume.value == 100
        w.volume.set_value(-10)
        assert w.volume.value == 0


class TestMediaWidgetMute:
    def test_toggle_mute_sets_volume_to_zero(self):
        w = MediaCard(0, volume=75)
        w.toggle_mute()
        assert w.muted is True
        assert w.volume.value == 0

    def test_toggle_mute_restores_volume(self):
        w = MediaCard(0, volume=75)
        w.toggle_mute()
        w.toggle_mute()
        assert w.muted is False
        assert w.volume.value == 75

    def test_toggle_mute_saves_current_volume(self):
        w = MediaCard(0, volume=60)
        w.volume.set_value(80)
        w.toggle_mute()
        assert w.volume.value == 0
        w.toggle_mute()
        assert w.volume.value == 80

    def test_toggle_mute_marks_dirty(self):
        w = MediaCard(0, volume=50)
        w.mark_clean()
        w.toggle_mute()
        assert w.is_dirty is True

    def test_toggle_mute_marks_dirty_on_unmute(self):
        w = MediaCard(0, volume=50)
        w.toggle_mute()
        w.mark_clean()
        w.toggle_mute()
        assert w.is_dirty is True

    def test_mute_unmute_cycle(self):
        w = MediaCard(0, volume=65)
        # Mute
        w.toggle_mute()
        assert w.muted is True
        assert w.volume.value == 0
        # Unmute
        w.toggle_mute()
        assert w.muted is False
        assert w.volume.value == 65
        # Mute again
        w.toggle_mute()
        assert w.muted is True
        assert w.volume.value == 0

    def test_mute_preserves_zero_volume(self):
        w = MediaCard(0, volume=0)
        w.toggle_mute()
        assert w.muted is True
        assert w.volume.value == 0
        w.toggle_mute()
        assert w.muted is False
        assert w.volume.value == 0


class TestMediaWidgetDialInteraction:
    def test_dial_turn_adjusts_volume(self):
        w = MediaCard(0, volume=50)
        w.handle_dial_turn(1)
        assert w.volume.value == 51

    def test_dial_turn_negative(self):
        w = MediaCard(0, volume=50)
        w.handle_dial_turn(-1)
        assert w.volume.value == 49

    def test_dial_press_toggles_mute(self):
        w = MediaCard(0, volume=75)
        w.handle_dial_press()
        assert w.muted is True
        assert w.volume.value == 0

    def test_dial_press_unmutes(self):
        w = MediaCard(0, volume=75)
        w.handle_dial_press()
        w.handle_dial_press()
        assert w.muted is False
        assert w.volume.value == 75

    def test_dial_press_does_not_cycle_sliders(self):
        """With only one slider, dial press should mute, not cycle."""
        w = MediaCard(0, volume=50)
        w.handle_dial_press()
        # active_control should still be the volume slider
        assert w.active_control is w.volume

    def test_dial_turn_while_muted(self):
        w = MediaCard(0, volume=50)
        w.handle_dial_press()  # mute
        w.handle_dial_turn(5)  # adjust while muted
        assert w.volume.value == 5  # volume changes even when muted


class TestMediaWidgetRender:
    def test_render_returns_correct_size(self):
        w = MediaCard(0)
        img = w.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_with_custom_values(self):
        w = MediaCard(0, title="My Song", volume=80)
        img = w.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_while_muted(self):
        w = MediaCard(0, volume=75)
        w.toggle_mute()
        img = w.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_after_dial_interaction(self):
        w = MediaCard(0)
        w.handle_dial_turn(10)
        w.handle_dial_press()  # mute
        img = w.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)


class TestMediaWidgetIsSubclassOfTouchPanel:
    def test_is_card(self):
        from deckboard.touchscreen import Card

        w = MediaCard(0)
        assert isinstance(w, Card)

    def test_is_touch_panel(self):
        from deckboard.widgets.touch_panel import StackCard

        w = MediaCard(0)
        assert isinstance(w, StackCard)


class TestMediaWidgetOnChangeIntegration:
    """Integration tests: on_change callbacks with MediaCard volume slider."""

    def test_on_change_queued_on_set_value(self):
        w = MediaCard(0, volume=50)
        handler = AsyncMock()
        w.volume.on_change(handler)
        w.volume.set_value(75)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (75.0,))

    def test_on_change_queued_on_dial_turn(self):
        w = MediaCard(0, volume=50)
        handler = AsyncMock()
        w.volume.on_change(handler)
        w.handle_dial_turn(3)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (53.0,))

    def test_on_change_queued_on_mute(self):
        w = MediaCard(0, volume=75)
        handler = AsyncMock()
        w.volume.on_change(handler)
        w.toggle_mute()
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (0.0,))

    def test_on_change_queued_on_unmute(self):
        w = MediaCard(0, volume=75)
        handler = AsyncMock()
        w.volume.on_change(handler)
        w.toggle_mute()
        w.drain_pending_callbacks()  # clear mute callback
        w.toggle_mute()
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (75.0,))

    def test_on_change_not_queued_when_clamped_at_max(self):
        w = MediaCard(0, volume=100)
        handler = AsyncMock()
        w.volume.on_change(handler)
        w.handle_dial_turn(1)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_on_change_not_queued_when_clamped_at_min(self):
        w = MediaCard(0, volume=0)
        handler = AsyncMock()
        w.volume.on_change(handler)
        w.handle_dial_turn(-1)
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_drain_clears_pending(self):
        w = MediaCard(0, volume=50)
        handler = AsyncMock()
        w.volume.on_change(handler)
        w.volume.set_value(60)
        w.drain_pending_callbacks()
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 0


class TestMediaWidgetTitleUpdates:
    """Tests for updating the media title dynamically."""

    def test_set_title_updates_text(self):
        w = MediaCard(0, title="Song A")
        w.title_text.set_text("Song B")
        assert w.title_text.text == "Song B"

    def test_set_title_marks_dirty(self):
        w = MediaCard(0)
        w.mark_clean()
        w.title_text.set_text("New Title")
        assert w.is_dirty is True

    def test_set_color_marks_dirty(self):
        w = MediaCard(0)
        w.mark_clean()
        w.title_text.set_color("red")
        assert w.is_dirty is True
        assert w.title_text.color == "red"

    def test_empty_title(self):
        w = MediaCard(0, title="")
        assert w.title_text.text == ""
        img = w.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_long_title_renders(self):
        w = MediaCard(0, title="A Very Long Song Title That Should Be Truncated")
        img = w.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)
