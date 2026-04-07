"""Tests for deckboard.presets.ha_media — HaMediaCard."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from PIL import Image

from deckboard.presets.ha_media import HaMediaCard
from deckboard.render.metrics import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.ui.cards.base import Card


# ── Helpers ──────────────────────────────────────────────────────────────


async def _short_press(card: HaMediaCard) -> None:
    """Simulate a short encoder press then immediate release."""
    await card.dispatch_encoder_press()
    await card.dispatch_encoder_release()


async def _long_press(card: HaMediaCard, hold: float = 2.1) -> None:
    """Simulate a long encoder press — hold past the threshold.

    Uses ``long_press_seconds=0`` on the card's internal timer
    so the asyncio task fires immediately, then release.
    """
    await card.dispatch_encoder_press()
    # Let the long-press task fire
    await asyncio.sleep(hold)
    await card.dispatch_encoder_release()


# ── Init ─────────────────────────────────────────────────────────────────


class TestHaMediaCardInit:
    def test_defaults(self):
        c = HaMediaCard(0)
        assert c.index == 0
        assert c.artist == ""
        assert c.title == "No Media"
        assert c.state == "Idle"
        assert c.volume == 50
        assert c.muted is False
        assert c.playing is False
        assert c.entity_picture is None
        assert c.long_press_seconds == 2.0

    def test_custom_values(self):
        pic = Image.new("RGB", (100, 100), "red")
        c = HaMediaCard(
            2,
            artist="Queen",
            title="Bohemian Rhapsody",
            state="Playing",
            volume=75,
            entity_picture=pic,
            long_press_seconds=1.5,
        )
        assert c.index == 2
        assert c.artist == "Queen"
        assert c.title == "Bohemian Rhapsody"
        assert c.state == "Playing"
        assert c.volume == 75
        assert c.playing is True
        assert c.entity_picture is pic
        assert c.long_press_seconds == 1.5

    def test_volume_clamped_high(self):
        c = HaMediaCard(0, volume=200)
        assert c.volume == 100

    def test_volume_clamped_low(self):
        c = HaMediaCard(0, volume=-10)
        assert c.volume == 0

    def test_is_card(self):
        c = HaMediaCard(0)
        assert isinstance(c, Card)

    def test_state_playing_sets_playing(self):
        c = HaMediaCard(0, state="playing")
        assert c.playing is True

    def test_state_paused_sets_not_playing(self):
        c = HaMediaCard(0, state="Paused")
        assert c.playing is False

    def test_long_press_seconds_clamped(self):
        c = HaMediaCard(0, long_press_seconds=-5)
        assert c.long_press_seconds == 0.0


# ── Accessors ────────────────────────────────────────────────────────────


class TestHaMediaCardAccessors:
    def test_volume_normalized_zero(self):
        c = HaMediaCard(0, volume=0)
        assert c.volume_normalized == 0.0

    def test_volume_normalized_full(self):
        c = HaMediaCard(0, volume=100)
        assert c.volume_normalized == 1.0

    def test_volume_normalized_half(self):
        c = HaMediaCard(0, volume=50)
        assert c.volume_normalized == 0.5

    def test_volume_step_default(self):
        c = HaMediaCard(0)
        assert c.volume_step == 1.0


# ── Mutators ─────────────────────────────────────────────────────────────


class TestHaMediaCardMutators:
    def test_set_artist(self):
        c = HaMediaCard(0)
        result = c.set_artist("Led Zeppelin")
        assert c.artist == "Led Zeppelin"
        assert result is c

    def test_set_title(self):
        c = HaMediaCard(0)
        result = c.set_title("Stairway to Heaven")
        assert c.title == "Stairway to Heaven"
        assert result is c

    def test_set_state(self):
        c = HaMediaCard(0)
        result = c.set_state("Playing")
        assert c.state == "Playing"
        assert c.playing is True
        assert result is c

    def test_set_state_paused(self):
        c = HaMediaCard(0, state="Playing")
        c.set_state("Paused")
        assert c.playing is False

    def test_set_volume(self):
        c = HaMediaCard(0)
        c.set_volume(80)
        assert c.volume == 80

    def test_set_volume_clamps_high(self):
        c = HaMediaCard(0)
        c.set_volume(200)
        assert c.volume == 100

    def test_set_volume_clamps_low(self):
        c = HaMediaCard(0)
        c.set_volume(-10)
        assert c.volume == 0

    def test_set_volume_marks_dirty(self):
        c = HaMediaCard(0)
        c.mark_clean()
        c.set_volume(70)
        assert c.is_dirty is True

    def test_set_artist_marks_dirty(self):
        c = HaMediaCard(0)
        c.mark_clean()
        c.set_artist("Beatles")
        assert c.is_dirty is True

    def test_set_title_marks_dirty(self):
        c = HaMediaCard(0)
        c.mark_clean()
        c.set_title("Yesterday")
        assert c.is_dirty is True

    def test_set_state_marks_dirty(self):
        c = HaMediaCard(0)
        c.mark_clean()
        c.set_state("Playing")
        assert c.is_dirty is True

    def test_set_entity_picture(self):
        c = HaMediaCard(0)
        pic = Image.new("RGB", (50, 50), "blue")
        result = c.set_entity_picture(pic)
        assert c.entity_picture is pic
        assert result is c

    def test_set_entity_picture_none(self):
        pic = Image.new("RGB", (50, 50), "blue")
        c = HaMediaCard(0, entity_picture=pic)
        c.set_entity_picture(None)
        assert c.entity_picture is None

    def test_set_entity_picture_marks_dirty(self):
        c = HaMediaCard(0)
        c.mark_clean()
        c.set_entity_picture(Image.new("RGB", (50, 50), "blue"))
        assert c.is_dirty is True

    def test_set_volume_step(self):
        c = HaMediaCard(0)
        result = c.set_volume_step(5)
        assert c.volume_step == 5.0
        assert result is c

    def test_set_volume_step_minimum(self):
        c = HaMediaCard(0)
        c.set_volume_step(0.01)
        assert c.volume_step == 0.1

    def test_set_long_press_seconds(self):
        c = HaMediaCard(0)
        result = c.set_long_press_seconds(3.0)
        assert c.long_press_seconds == 3.0
        assert result is c

    def test_set_long_press_seconds_clamped(self):
        c = HaMediaCard(0)
        c.set_long_press_seconds(-1)
        assert c.long_press_seconds == 0.0


# ── Mute control (direct method calls) ───────────────────────────────────


class TestHaMediaCardMute:
    def test_toggle_mute_sets_volume_to_zero(self):
        c = HaMediaCard(0, volume=75)
        c.toggle_mute()
        assert c.muted is True
        assert c.volume == 0

    def test_toggle_mute_restores_volume(self):
        c = HaMediaCard(0, volume=75)
        c.toggle_mute()
        c.toggle_mute()
        assert c.muted is False
        assert c.volume == 75

    def test_toggle_mute_saves_current_volume(self):
        c = HaMediaCard(0, volume=60)
        c.set_volume(80)
        c.toggle_mute()
        assert c.volume == 0
        c.toggle_mute()
        assert c.volume == 80

    def test_toggle_mute_marks_dirty(self):
        c = HaMediaCard(0, volume=50)
        c.mark_clean()
        c.toggle_mute()
        assert c.is_dirty is True

    def test_toggle_mute_marks_dirty_on_unmute(self):
        c = HaMediaCard(0, volume=50)
        c.toggle_mute()
        c.mark_clean()
        c.toggle_mute()
        assert c.is_dirty is True

    def test_mute_unmute_cycle(self):
        c = HaMediaCard(0, volume=65)
        c.toggle_mute()
        assert c.muted is True
        assert c.volume == 0
        c.toggle_mute()
        assert c.muted is False
        assert c.volume == 65
        c.toggle_mute()
        assert c.muted is True
        assert c.volume == 0

    def test_mute_preserves_zero_volume(self):
        c = HaMediaCard(0, volume=0)
        c.toggle_mute()
        assert c.muted is True
        assert c.volume == 0
        c.toggle_mute()
        assert c.muted is False
        assert c.volume == 0


# ── Play/Pause control (direct method calls) ─────────────────────────────


class TestHaMediaCardPlayPause:
    def test_toggle_play_pause_from_idle(self):
        c = HaMediaCard(0, state="Idle")
        c.toggle_play_pause()
        assert c.playing is True
        assert c.state == "Playing"

    def test_toggle_play_pause_from_playing(self):
        c = HaMediaCard(0, state="Playing")
        c.toggle_play_pause()
        assert c.playing is False
        assert c.state == "Paused"

    def test_toggle_play_pause_from_paused(self):
        c = HaMediaCard(0, state="Paused")
        c.toggle_play_pause()
        assert c.playing is True
        assert c.state == "Playing"

    def test_toggle_play_pause_marks_dirty(self):
        c = HaMediaCard(0)
        c.mark_clean()
        c.toggle_play_pause()
        assert c.is_dirty is True

    def test_double_toggle(self):
        c = HaMediaCard(0, state="Playing")
        c.toggle_play_pause()
        c.toggle_play_pause()
        assert c.playing is True
        assert c.state == "Playing"


# ── Encoder turn (sync — same as before) ─────────────────────────────────


class TestHaMediaCardEncoderTurn:
    def test_encoder_turn_adjusts_volume(self):
        c = HaMediaCard(0, volume=50)
        c.handle_encoder_turn(1)
        assert c.volume == 51

    def test_encoder_turn_negative(self):
        c = HaMediaCard(0, volume=50)
        c.handle_encoder_turn(-1)
        assert c.volume == 49

    def test_encoder_turn_clamps_high(self):
        c = HaMediaCard(0, volume=100)
        c.handle_encoder_turn(1)
        assert c.volume == 100

    def test_encoder_turn_clamps_low(self):
        c = HaMediaCard(0, volume=0)
        c.handle_encoder_turn(-1)
        assert c.volume == 0

    def test_encoder_turn_custom_step(self):
        c = HaMediaCard(0, volume=50)
        c.set_volume_step(5)
        c.handle_encoder_turn(1)
        assert c.volume == 55

    def test_encoder_turn_marks_dirty(self):
        c = HaMediaCard(0, volume=50)
        c.mark_clean()
        c.handle_encoder_turn(1)
        assert c.is_dirty is True

    def test_encoder_turn_while_muted(self):
        c = HaMediaCard(0, volume=50)
        c.toggle_mute()
        c.handle_encoder_turn(5)
        assert c.volume == 5


# ── Encoder short press → mute (async dispatch) ─────────────────────────


class TestHaMediaCardShortPress:
    """Short press (press + immediate release) should toggle mute."""

    async def test_short_press_mutes(self):
        c = HaMediaCard(0, volume=75, long_press_seconds=2.0)
        await _short_press(c)
        assert c.muted is True
        assert c.volume == 0

    async def test_short_press_unmutes(self):
        c = HaMediaCard(0, volume=75, long_press_seconds=2.0)
        await _short_press(c)
        await _short_press(c)
        assert c.muted is False
        assert c.volume == 75

    async def test_short_press_does_not_toggle_play_pause(self):
        c = HaMediaCard(0, state="Paused", long_press_seconds=2.0)
        await _short_press(c)
        assert c.state == "Paused"
        assert c.playing is False


# ── Encoder long press → play/pause (async dispatch with timer) ──────────


class TestHaMediaCardLongPress:
    """Holding the encoder past the threshold toggles play/pause."""

    async def test_long_press_toggles_play_pause(self):
        # Use a very short threshold so the test runs fast
        c = HaMediaCard(0, state="Paused", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)  # wait past threshold
        assert c._long_press_fired is True
        assert c.playing is True
        assert c.state == "Playing"
        await c.dispatch_encoder_release()
        # Still playing — release after long press is a no-op for mute
        assert c.muted is False

    async def test_long_press_does_not_mute(self):
        c = HaMediaCard(0, volume=75, state="Playing", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        await c.dispatch_encoder_release()
        assert c.muted is False
        assert c.volume == 75

    async def test_long_press_pauses(self):
        c = HaMediaCard(0, state="Playing", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        assert c.state == "Paused"
        await c.dispatch_encoder_release()

    async def test_long_press_requests_refresh(self):
        refresh_mock = AsyncMock()
        c = HaMediaCard(0, state="Paused", long_press_seconds=0.05)
        c.set_refresh_callback(refresh_mock)
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        await c.dispatch_encoder_release()
        refresh_mock.assert_awaited()

    async def test_release_before_threshold_mutes(self):
        c = HaMediaCard(0, volume=60, long_press_seconds=10.0)
        await c.dispatch_encoder_press()
        # Release immediately — well before 10s threshold
        await c.dispatch_encoder_release()
        assert c._long_press_fired is False
        assert c.muted is True
        assert c.playing is False

    async def test_cancel_long_press_on_release(self):
        c = HaMediaCard(0, long_press_seconds=10.0)
        await c.dispatch_encoder_press()
        task = c._long_press_task
        assert task is not None
        await c.dispatch_encoder_release()
        # After release, _cancel_long_press clears the task reference
        assert c._long_press_task is None
        # Give the event loop a tick so the cancellation propagates
        await asyncio.sleep(0)
        assert task.cancelled()

    async def test_long_press_with_no_refresh_callback(self):
        """Long press works even without a refresh callback (no crash)."""
        c = HaMediaCard(0, state="Paused", long_press_seconds=0.05)
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        assert c.playing is True
        await c.dispatch_encoder_release()

    async def test_encoder_press_handler_called(self):
        c = HaMediaCard(0, long_press_seconds=10.0)
        handler = AsyncMock()
        c.on_encoder_press(handler)
        await c.dispatch_encoder_press()
        handler.assert_awaited_once()
        await c.dispatch_encoder_release()

    async def test_encoder_release_handler_called(self):
        c = HaMediaCard(0, long_press_seconds=10.0)
        handler = AsyncMock()
        c.on_encoder_release(handler)
        await c.dispatch_encoder_press()
        await c.dispatch_encoder_release()
        handler.assert_awaited_once()

    async def test_release_handler_sees_muted_state(self):
        """The on_encoder_release handler must see the post-toggle state.

        This is the core of the mute/unmute ordering fix: toggle_mute()
        must run *before* the user's release handler so that sync logic
        (e.g. updating key icons) reads the correct muted state.
        """
        observed: dict[str, bool | float] = {}

        c = HaMediaCard(0, volume=60, long_press_seconds=10.0)

        @c.on_encoder_release
        async def capture_state() -> None:
            observed["muted"] = c.muted
            observed["volume"] = c.volume

        await c.dispatch_encoder_press()
        await c.dispatch_encoder_release()
        assert observed["muted"] is True
        assert observed["volume"] == 0

    async def test_release_handler_sees_unmuted_state(self):
        """Second short press: handler must see unmuted state."""
        observed: dict[str, bool | float] = {}

        c = HaMediaCard(0, volume=60, long_press_seconds=10.0)

        @c.on_encoder_release
        async def capture_state() -> None:
            observed["muted"] = c.muted
            observed["volume"] = c.volume

        # First short press → mute
        await c.dispatch_encoder_press()
        await c.dispatch_encoder_release()
        assert observed["muted"] is True

        # Second short press → unmute
        await c.dispatch_encoder_press()
        await c.dispatch_encoder_release()
        assert observed["muted"] is False
        assert observed["volume"] == 60

    async def test_press_handler_runs_after_timer_starts(self):
        """The on_encoder_press handler runs after the long-press timer
        has been started, so the task exists when the handler fires."""
        observed: dict[str, object] = {}

        c = HaMediaCard(0, long_press_seconds=10.0)

        @c.on_encoder_press
        async def capture_state() -> None:
            observed["task_exists"] = c._long_press_task is not None

        await c.dispatch_encoder_press()
        assert observed["task_exists"] is True
        await c.dispatch_encoder_release()


# ── Rendering ────────────────────────────────────────────────────────────


class TestHaMediaCardRender:
    def test_render_returns_correct_size(self):
        c = HaMediaCard(0)
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_with_custom_values(self):
        c = HaMediaCard(
            0, artist="Queen", title="Bohemian Rhapsody", state="Playing", volume=80
        )
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_with_entity_picture(self):
        pic = Image.new("RGB", (200, 200), "red")
        c = HaMediaCard(0, entity_picture=pic)
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_with_rgba_entity_picture(self):
        pic = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
        c = HaMediaCard(0, entity_picture=pic)
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_while_muted(self):
        c = HaMediaCard(0, volume=75)
        c.toggle_mute()
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_zero_volume(self):
        c = HaMediaCard(0, volume=0)
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_full_volume(self):
        c = HaMediaCard(0, volume=100)
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_empty_artist(self):
        c = HaMediaCard(0, artist="")
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_empty_state(self):
        c = HaMediaCard(0, state="")
        img = c.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_render_mode_is_rgb(self):
        c = HaMediaCard(0)
        img = c.render()
        assert img.mode == "RGB"


# ── on_volume_change callbacks ───────────────────────────────────────────


class TestHaMediaCardOnVolumeChange:
    def test_on_volume_change_queued_on_set_volume(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.set_volume(75)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (75.0,))

    def test_on_volume_change_queued_on_encoder_turn(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(3)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (53.0,))

    def test_on_volume_change_queued_on_mute(self):
        c = HaMediaCard(0, volume=75)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.toggle_mute()
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (0.0,))

    def test_on_volume_change_queued_on_unmute(self):
        c = HaMediaCard(0, volume=75)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.toggle_mute()
        c.drain_pending_callbacks()
        c.toggle_mute()
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (75.0,))

    def test_on_volume_change_not_queued_when_clamped_at_max(self):
        c = HaMediaCard(0, volume=100)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_on_volume_change_not_queued_when_clamped_at_min(self):
        c = HaMediaCard(0, volume=0)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(-1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_drain_clears_pending(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.set_volume(60)
        c.drain_pending_callbacks()
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_no_handler_no_callback(self):
        c = HaMediaCard(0, volume=50)
        c.set_volume(60)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0


# ── Gradient mask ────────────────────────────────────────────────────────


class TestHaMediaCardGradientMask:
    def test_gradient_mask_is_cached(self):
        from deckboard.presets.ha_media import _build_gradient_mask

        mask1 = _build_gradient_mask()
        mask2 = _build_gradient_mask()
        assert mask1 is mask2

    def test_gradient_mask_size(self):
        from deckboard.presets.ha_media import _build_gradient_mask

        mask = _build_gradient_mask()
        assert mask.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_gradient_mask_mode(self):
        from deckboard.presets.ha_media import _build_gradient_mask

        mask = _build_gradient_mask()
        assert mask.mode == "L"


# ── Method chaining ──────────────────────────────────────────────────────


class TestHaMediaCardMethodChaining:
    def test_set_artist_chains(self):
        c = HaMediaCard(0)
        assert c.set_artist("Test") is c

    def test_set_title_chains(self):
        c = HaMediaCard(0)
        assert c.set_title("Test") is c

    def test_set_state_chains(self):
        c = HaMediaCard(0)
        assert c.set_state("Playing") is c

    def test_set_entity_picture_chains(self):
        c = HaMediaCard(0)
        assert c.set_entity_picture(None) is c

    def test_set_volume_step_chains(self):
        c = HaMediaCard(0)
        assert c.set_volume_step(2) is c

    def test_set_long_press_seconds_chains(self):
        c = HaMediaCard(0)
        assert c.set_long_press_seconds(3) is c

    def test_chained_calls(self):
        c = HaMediaCard(0)
        result = (
            c.set_artist("Queen")
            .set_title("Bohemian Rhapsody")
            .set_state("Playing")
            .set_volume_step(2)
            .set_long_press_seconds(1.5)
        )
        assert result is c
        assert c.artist == "Queen"
        assert c.title == "Bohemian Rhapsody"
        assert c.state == "Playing"
        assert c.volume_step == 2.0
        assert c.long_press_seconds == 1.5
