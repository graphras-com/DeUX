"""Tests for deckboard.presets.ha_media — HaMediaCard."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from PIL import Image, ImageDraw

from deckboard.presets.ha_media import HaMediaCard
from deckboard.presets.ha_media import (
    _MUTE_ICON_COLOR,
    _MUTE_ICON_RIGHT_MARGIN,
    _MUTE_ICON_SIZE,
    _MUTE_ICON_Y,
    _STATE_TEXT_Y,
    _draw_mute_icon,
)
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
        assert c.requested_volume == 50
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
    def test_toggle_mute_sets_muted_flag(self):
        c = HaMediaCard(0, volume=75)
        c.toggle_mute()
        assert c.muted is True

    def test_toggle_mute_does_not_change_volume(self):
        c = HaMediaCard(0, volume=75)
        c.toggle_mute()
        assert c.volume == 75

    def test_toggle_mute_twice_clears_muted(self):
        c = HaMediaCard(0, volume=75)
        c.toggle_mute()
        c.toggle_mute()
        assert c.muted is False
        assert c.volume == 75

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
        assert c.volume == 65
        c.toggle_mute()
        assert c.muted is False
        assert c.volume == 65
        c.toggle_mute()
        assert c.muted is True
        assert c.volume == 65

    def test_mute_preserves_zero_volume(self):
        c = HaMediaCard(0, volume=0)
        c.toggle_mute()
        assert c.muted is True
        assert c.volume == 0
        c.toggle_mute()
        assert c.muted is False
        assert c.volume == 0

    def test_set_muted_true(self):
        c = HaMediaCard(0)
        c.set_muted(True)
        assert c.muted is True

    def test_set_muted_false(self):
        c = HaMediaCard(0)
        c.toggle_mute()
        c.set_muted(False)
        assert c.muted is False

    def test_set_muted_marks_dirty(self):
        c = HaMediaCard(0)
        c.mark_clean()
        c.set_muted(True)
        assert c.is_dirty is True

    def test_set_muted_does_not_emit_callback(self):
        c = HaMediaCard(0)
        handler = AsyncMock()
        c.on_mute_toggle(handler)
        c.set_muted(True)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_set_muted_does_not_change_volume(self):
        c = HaMediaCard(0, volume=75)
        c.set_muted(True)
        assert c.volume == 75


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
    def test_encoder_turn_does_not_change_volume(self):
        c = HaMediaCard(0, volume=50)
        c.handle_encoder_turn(1)
        assert c.volume == 50

    def test_encoder_turn_accumulates_requested_volume(self):
        c = HaMediaCard(0, volume=50)
        c.handle_encoder_turn(1)
        assert c.requested_volume == 51
        c.handle_encoder_turn(1)
        assert c.requested_volume == 52

    def test_encoder_turn_emits_requested_volume(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (51.0,))

    def test_rapid_turns_emit_accumulated_values(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(1)
        c.handle_encoder_turn(1)
        c.handle_encoder_turn(1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 3
        assert callbacks[0] == (handler, (51.0,))
        assert callbacks[1] == (handler, (52.0,))
        assert callbacks[2] == (handler, (53.0,))

    def test_encoder_turn_negative_emits(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(-1)
        callbacks = c.drain_pending_callbacks()
        assert callbacks[0] == (handler, (49.0,))

    def test_encoder_turn_clamps_high(self):
        c = HaMediaCard(0, volume=100)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0
        assert c.requested_volume == 100

    def test_encoder_turn_clamps_low(self):
        c = HaMediaCard(0, volume=0)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(-1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0
        assert c.requested_volume == 0

    def test_encoder_turn_custom_step(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.set_volume_step(5)
        c.handle_encoder_turn(1)
        callbacks = c.drain_pending_callbacks()
        assert callbacks[0] == (handler, (55.0,))

    def test_encoder_turn_no_handler_no_callback(self):
        c = HaMediaCard(0, volume=50)
        c.handle_encoder_turn(1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0
        # requested_volume still accumulates even without handler
        assert c.requested_volume == 51

    def test_encoder_turn_while_muted(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.toggle_mute()
        c.drain_pending_callbacks()
        c.handle_encoder_turn(5)
        callbacks = c.drain_pending_callbacks()
        assert callbacks[0] == (handler, (55.0,))
        assert c.volume == 50

    def test_set_volume_resets_requested_volume(self):
        c = HaMediaCard(0, volume=50)
        c.handle_encoder_turn(3)
        assert c.requested_volume == 53
        c.set_volume(53)
        assert c.requested_volume == 53
        assert c.volume == 53

    def test_set_volume_resets_accumulator_to_confirmed(self):
        """Backend may confirm a different value than requested."""
        c = HaMediaCard(0, volume=50)
        c.handle_encoder_turn(10)
        assert c.requested_volume == 60
        # Backend clamps or adjusts to a different value
        c.set_volume(55)
        assert c.requested_volume == 55
        # Next turn starts from 55
        c.handle_encoder_turn(1)
        assert c.requested_volume == 56


# ── Encoder short press → mute (async dispatch) ─────────────────────────


class TestHaMediaCardShortPress:
    """Short press (press + immediate release) should toggle mute."""

    async def test_short_press_mutes(self):
        c = HaMediaCard(0, volume=75, long_press_seconds=2.0)
        await _short_press(c)
        assert c.muted is True
        assert c.volume == 75

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
    """Holding the encoder past the threshold emits play/pause toggle."""

    async def test_long_press_emits_play_pause(self):
        c = HaMediaCard(0, state="Paused", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        handler = AsyncMock()
        c.on_play_pause_toggle(handler)
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        assert c._long_press_fired is True
        # State is NOT changed — emit only
        assert c.playing is False
        assert c.state == "Paused"
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (True,))
        await c.dispatch_encoder_release()
        assert c.muted is False

    async def test_long_press_does_not_mute(self):
        c = HaMediaCard(0, volume=75, state="Playing", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        await c.dispatch_encoder_release()
        assert c.muted is False
        assert c.volume == 75

    async def test_long_press_does_not_change_state(self):
        c = HaMediaCard(0, state="Playing", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        assert c.state == "Playing"
        assert c.playing is True
        await c.dispatch_encoder_release()

    async def test_long_press_emits_pause_request(self):
        c = HaMediaCard(0, state="Playing", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        handler = AsyncMock()
        c.on_play_pause_toggle(handler)
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (False,))
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
        # State is unchanged — emit only
        assert c.playing is False
        await c.dispatch_encoder_release()

    async def test_long_press_no_handler_no_callback(self):
        """Long press without an on_play_pause_toggle handler is fine."""
        c = HaMediaCard(0, state="Paused", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0
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
        assert observed["volume"] == 60

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


# ── Mute icon rendering ─────────────────────────────────────────────────


class TestHaMediaCardMuteIconRender:
    """Verify the mute icon is drawn only when muted and occupies the
    expected region of the card image."""

    def _icon_region_pixels(self, img: Image.Image) -> list[tuple[int, int, int]]:
        """Extract pixels from the mute-icon bounding box."""
        icon_x = PANEL_WIDTH - _MUTE_ICON_SIZE - _MUTE_ICON_RIGHT_MARGIN
        pixels = []
        for y in range(_MUTE_ICON_Y, _MUTE_ICON_Y + _MUTE_ICON_SIZE):
            for x in range(icon_x, icon_x + _MUTE_ICON_SIZE):
                pixels.append(img.getpixel((x, y)))
        return pixels

    def test_mute_icon_drawn_when_muted(self):
        """When muted, non-black pixels must appear in the icon area."""
        c = HaMediaCard(0, volume=75, state="")
        c.toggle_mute()
        img = c.render()
        pixels = self._icon_region_pixels(img)
        non_black = [p for p in pixels if p != (0, 0, 0)]
        assert len(non_black) > 0, "Expected mute icon pixels but found none"

    def test_mute_icon_not_drawn_when_unmuted(self):
        """When not muted and no state text overlaps, the icon area is black."""
        c = HaMediaCard(0, volume=75, state="")
        img = c.render()
        pixels = self._icon_region_pixels(img)
        non_black = [p for p in pixels if p != (0, 0, 0)]
        assert len(non_black) == 0, "Expected no mute icon pixels when unmuted"

    def test_mute_icon_uses_white_color(self):
        """The mute icon should be drawn in white (#ffffff)."""
        c = HaMediaCard(0, volume=75, state="")
        c.toggle_mute()
        img = c.render()
        pixels = self._icon_region_pixels(img)
        white_pixels = [p for p in pixels if p == (255, 255, 255)]
        assert len(white_pixels) > 0, "Expected white pixels in mute icon"

    def test_mute_icon_disappears_after_unmute(self):
        """Toggling mute off should remove the icon from the render."""
        c = HaMediaCard(0, volume=75, state="")
        c.toggle_mute()
        img_muted = c.render()
        muted_pixels = self._icon_region_pixels(img_muted)
        assert any(p != (0, 0, 0) for p in muted_pixels)

        c.toggle_mute()
        img_unmuted = c.render()
        unmuted_pixels = self._icon_region_pixels(img_unmuted)
        non_black = [p for p in unmuted_pixels if p != (0, 0, 0)]
        assert len(non_black) == 0

    def test_set_muted_true_shows_icon(self):
        """Using set_muted(True) should also draw the mute icon."""
        c = HaMediaCard(0, volume=75, state="")
        c.set_muted(True)
        img = c.render()
        pixels = self._icon_region_pixels(img)
        non_black = [p for p in pixels if p != (0, 0, 0)]
        assert len(non_black) > 0


# ── _draw_mute_icon unit tests ───────────────────────────────────────────


class TestDrawMuteIcon:
    """Direct unit tests for the _draw_mute_icon helper function."""

    @staticmethod
    def _all_pixels(img: Image.Image) -> list[tuple[int, int, int]]:
        """Return all pixels from the image without using deprecated getdata."""
        w, h = img.size
        return [img.getpixel((x, y)) for y in range(h) for x in range(w)]

    def test_draws_non_black_pixels(self):
        img = Image.new("RGB", (24, 24), "black")
        draw = ImageDraw.Draw(img)
        _draw_mute_icon(draw, 4, 4, 16)
        pixels = self._all_pixels(img)
        non_black = [p for p in pixels if p != (0, 0, 0)]
        assert len(non_black) > 0

    def test_draws_white_pixels(self):
        img = Image.new("RGB", (24, 24), "black")
        draw = ImageDraw.Draw(img)
        _draw_mute_icon(draw, 4, 4, 16)
        pixels = self._all_pixels(img)
        white = [p for p in pixels if p == (255, 255, 255)]
        assert len(white) > 0

    def test_icon_stays_within_bounds(self):
        """All drawn pixels must lie within the declared bounding box."""
        size = 16
        padding = 4
        total = size + 2 * padding
        img = Image.new("RGB", (total, total), "black")
        draw = ImageDraw.Draw(img)
        _draw_mute_icon(draw, padding, padding, size)

        # Check that the outside border rows/cols are still black
        for x in range(total):
            assert img.getpixel((x, 0)) == (0, 0, 0)
            assert img.getpixel((x, total - 1)) == (0, 0, 0)
        for y in range(total):
            assert img.getpixel((0, y)) == (0, 0, 0)
            assert img.getpixel((total - 1, y)) == (0, 0, 0)

    def test_different_sizes(self):
        """The icon should scale to different sizes without errors."""
        for size in (8, 12, 16, 24, 32):
            img = Image.new("RGB", (size + 8, size + 8), "black")
            draw = ImageDraw.Draw(img)
            _draw_mute_icon(draw, 4, 4, size)
            pixels = self._all_pixels(img)
            non_black = [p for p in pixels if p != (0, 0, 0)]
            assert len(non_black) > 0, f"No pixels drawn at size={size}"


# ── State text Y-position ────────────────────────────────────────────────


class TestHaMediaCardStateTextPosition:
    """Verify the state text has moved higher to make room for the mute icon."""

    def test_state_text_y_constant(self):
        """The state text Y position should be 52 (moved from 60)."""
        assert _STATE_TEXT_Y == 52

    def test_mute_icon_y_below_state_text(self):
        """The mute icon Y position should be below the state text."""
        assert _MUTE_ICON_Y > _STATE_TEXT_Y

    def test_mute_icon_color_is_white(self):
        assert _MUTE_ICON_COLOR == "#ffffff"

    def test_mute_icon_size(self):
        assert _MUTE_ICON_SIZE == 16

    def test_mute_icon_right_margin(self):
        assert _MUTE_ICON_RIGHT_MARGIN == 5


# ── on_volume_change callbacks ───────────────────────────────────────────


class TestHaMediaCardOnVolumeChange:
    def test_on_volume_change_not_queued_on_set_volume(self):
        """set_volume is a confirmed setter — no callback emitted."""
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.set_volume(75)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_on_volume_change_queued_on_encoder_turn(self):
        c = HaMediaCard(0, volume=50)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.handle_encoder_turn(3)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (53.0,))

    def test_on_volume_change_not_queued_on_mute(self):
        c = HaMediaCard(0, volume=75)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.toggle_mute()
        callbacks = c.drain_pending_callbacks()
        # Only the mute_toggle callback should be present, not volume
        vol_callbacks = [cb for cb in callbacks if cb[0] is handler]
        assert len(vol_callbacks) == 0

    def test_on_volume_change_not_queued_on_unmute(self):
        c = HaMediaCard(0, volume=75)
        handler = AsyncMock()
        c.on_volume_change(handler)
        c.toggle_mute()
        c.drain_pending_callbacks()
        c.toggle_mute()
        callbacks = c.drain_pending_callbacks()
        vol_callbacks = [cb for cb in callbacks if cb[0] is handler]
        assert len(vol_callbacks) == 0

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
        c.handle_encoder_turn(10)
        c.drain_pending_callbacks()
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_no_handler_no_callback(self):
        c = HaMediaCard(0, volume=50)
        c.handle_encoder_turn(10)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0


# ── on_mute_toggle callbacks ─────────────────────────────────────────────


class TestHaMediaCardOnMuteToggle:
    def test_on_mute_toggle_queued_on_mute(self):
        c = HaMediaCard(0, volume=75)
        handler = AsyncMock()
        c.on_mute_toggle(handler)
        c.toggle_mute()
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (True,))

    def test_on_mute_toggle_queued_on_unmute(self):
        c = HaMediaCard(0, volume=75)
        handler = AsyncMock()
        c.on_mute_toggle(handler)
        c.toggle_mute()
        c.drain_pending_callbacks()
        c.toggle_mute()
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (False,))

    def test_on_mute_toggle_not_queued_without_handler(self):
        c = HaMediaCard(0, volume=75)
        c.toggle_mute()
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_on_mute_toggle_returns_handler(self):
        c = HaMediaCard(0)
        handler = AsyncMock()
        result = c.on_mute_toggle(handler)
        assert result is handler

    async def test_on_mute_toggle_queued_on_short_press(self):
        c = HaMediaCard(0, volume=75, long_press_seconds=10.0)
        handler = AsyncMock()
        c.on_mute_toggle(handler)
        await _short_press(c)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (True,))

    async def test_on_mute_toggle_not_queued_on_long_press(self):
        c = HaMediaCard(0, volume=75, long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        handler = AsyncMock()
        c.on_mute_toggle(handler)
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        await c.dispatch_encoder_release()
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0


# ── on_play_pause_toggle callbacks ───────────────────────────────────────


class TestHaMediaCardOnPlayPauseToggle:
    def test_on_play_pause_toggle_returns_handler(self):
        c = HaMediaCard(0)
        handler = AsyncMock()
        result = c.on_play_pause_toggle(handler)
        assert result is handler

    async def test_on_play_pause_toggle_queued_on_long_press_from_paused(self):
        c = HaMediaCard(0, state="Paused", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        handler = AsyncMock()
        c.on_play_pause_toggle(handler)
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (True,))
        await c.dispatch_encoder_release()

    async def test_on_play_pause_toggle_queued_on_long_press_from_playing(self):
        c = HaMediaCard(0, state="Playing", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        handler = AsyncMock()
        c.on_play_pause_toggle(handler)
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (False,))
        await c.dispatch_encoder_release()

    async def test_on_play_pause_toggle_not_queued_on_short_press(self):
        c = HaMediaCard(0, state="Paused", long_press_seconds=10.0)
        handler = AsyncMock()
        c.on_play_pause_toggle(handler)
        await _short_press(c)
        callbacks = c.drain_pending_callbacks()
        pp_callbacks = [cb for cb in callbacks if cb[0] is handler]
        assert len(pp_callbacks) == 0

    async def test_on_play_pause_toggle_not_queued_without_handler(self):
        c = HaMediaCard(0, state="Paused", long_press_seconds=0.05)
        c.set_refresh_callback(AsyncMock())
        await c.dispatch_encoder_press()
        await asyncio.sleep(0.1)
        callbacks = c.drain_pending_callbacks()
        assert len(callbacks) == 0
        await c.dispatch_encoder_release()


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
