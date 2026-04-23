"""Tests for deckui.dsui.event_map — event routing and gesture detection."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from deckui.dsui.event_map import EventMap
from deckui.dsui.schema import EventMapping, Region
from deckui.runtime.events import EventType

# -- Fixtures --------------------------------------------------------------


def _make_events(*specs: tuple) -> tuple[EventMapping, ...]:
    """Shorthand to create event mappings from (name, source, kwargs) tuples."""
    result = []
    for spec in specs:
        if len(spec) == 2:
            name, source = spec
            result.append(EventMapping(name=name, source=source))
        else:
            name, source, kwargs = spec
            result.append(EventMapping(name=name, source=source, **kwargs))
    return tuple(result)


class TestEncoderTurn:
    def test_turn_right(self):
        events = _make_events(
            ("next", "encoder_turn", {"direction": "right"}),
            ("prev", "encoder_turn", {"direction": "left"}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("next", handler)
        result = em.handle_encoder_turn(1)
        assert result is handler

    def test_turn_left(self):
        events = _make_events(
            ("next", "encoder_turn", {"direction": "right"}),
            ("prev", "encoder_turn", {"direction": "left"}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("prev", handler)
        result = em.handle_encoder_turn(-1)
        assert result is handler

    def test_turn_no_direction_filter(self):
        events = _make_events(("scroll", "encoder_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("scroll", handler)
        assert em.handle_encoder_turn(1) is handler
        assert em.handle_encoder_turn(-1) is handler

    def test_turn_no_match(self):
        events = _make_events(("next", "encoder_turn", {"direction": "right"}))
        em = EventMap(events)
        # No handler registered
        assert em.handle_encoder_turn(1) is None

    def test_turn_wrong_direction(self):
        events = _make_events(("next", "encoder_turn", {"direction": "right"}))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("next", handler)
        assert (
            em.handle_encoder_turn(-1) is None
        )  # left turn, but only right registered


class TestEncoderPressRelease:
    def test_simple_press(self):
        events = _make_events(("press", "encoder_press"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("press", handler)
        assert em.handle_encoder_press() == [handler]

    def test_simple_release(self):
        events = _make_events(("release", "encoder_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("release", handler)
        em.handle_encoder_press()  # establish pressed state
        assert em.handle_encoder_release() == [handler]

    def test_press_release_gesture_within_duration(self):
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 500}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("toggle", handler)

        em.handle_encoder_press()
        # Simulate fast release
        result = em.handle_encoder_release()
        assert handler in result

    def test_press_release_gesture_exceeded_duration(self):
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 1}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("toggle", handler)

        em.handle_encoder_press()
        # Simulate slow release (wait a bit)
        time.sleep(0.01)  # 10ms > 1ms max
        result = em.handle_encoder_release()
        assert handler not in result

    def test_press_release_no_max_duration(self):
        events = _make_events(("toggle", "encoder_press_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("toggle", handler)

        em.handle_encoder_press()
        time.sleep(0.01)
        result = em.handle_encoder_release()
        assert handler in result  # No max_duration -> always fires

    def test_release_without_press(self):
        events = _make_events(("release", "encoder_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("release", handler)
        # No press recorded
        result = em.handle_encoder_release()
        assert result == [handler]

    def test_release_always_fires_alongside_press_release(self):
        """encoder_release fires even when encoder_press_release also fires."""
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 500}),
            ("up", "encoder_release"),
        )
        em = EventMap(events)
        toggle_handler = AsyncMock()
        release_handler = AsyncMock()
        em.on("toggle", toggle_handler)
        em.on("up", release_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_release()
        assert toggle_handler in result
        assert release_handler in result


class TestEncoderPressTurn:
    def test_press_turn_while_pressed(self):
        events = _make_events(("seek", "encoder_press_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("seek", handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert result is handler

    def test_press_turn_not_pressed(self):
        events = _make_events(("seek", "encoder_press_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("seek", handler)

        # Not pressed — should not match press_turn
        result = em.handle_encoder_turn(1)
        assert result is None

    def test_press_turn_after_release(self):
        events = _make_events(("seek", "encoder_press_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("seek", handler)

        em.handle_encoder_press()
        em.handle_encoder_release()
        result = em.handle_encoder_turn(1)
        assert result is None

    def test_press_turn_direction_right(self):
        events = _make_events(
            ("seek_fwd", "encoder_press_turn", {"direction": "right"}),
            ("seek_bwd", "encoder_press_turn", {"direction": "left"}),
        )
        em = EventMap(events)
        fwd_handler = AsyncMock()
        bwd_handler = AsyncMock()
        em.on("seek_fwd", fwd_handler)
        em.on("seek_bwd", bwd_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert result is fwd_handler

    def test_press_turn_direction_left(self):
        events = _make_events(
            ("seek_fwd", "encoder_press_turn", {"direction": "right"}),
            ("seek_bwd", "encoder_press_turn", {"direction": "left"}),
        )
        em = EventMap(events)
        fwd_handler = AsyncMock()
        bwd_handler = AsyncMock()
        em.on("seek_fwd", fwd_handler)
        em.on("seek_bwd", bwd_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(-1)
        assert result is bwd_handler

    def test_press_turn_direction_no_match(self):
        events = _make_events(
            ("seek_fwd", "encoder_press_turn", {"direction": "right"}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("seek_fwd", handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(-1)  # left turn, only right registered
        assert result is None

    def test_press_turn_takes_priority_over_regular_turn(self):
        """encoder_press_turn is checked before encoder_turn when pressed."""
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("seek", "encoder_press_turn"),
        )
        em = EventMap(events)
        scroll_handler = AsyncMock()
        seek_handler = AsyncMock()
        em.on("scroll", scroll_handler)
        em.on("seek", seek_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert result is seek_handler  # press_turn wins

    def test_regular_turn_fires_when_press_turn_direction_mismatches(self):
        """Falls back to encoder_turn when press_turn direction doesn't match."""
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("seek_fwd", "encoder_press_turn", {"direction": "right"}),
        )
        em = EventMap(events)
        scroll_handler = AsyncMock()
        seek_handler = AsyncMock()
        em.on("scroll", scroll_handler)
        em.on("seek_fwd", seek_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(-1)  # left turn, press_turn only has right
        assert result is scroll_handler  # falls back to regular turn


class TestKeyEvents:
    def test_key_press(self):
        events = _make_events(("hold", "key_press"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("hold", handler)
        assert em.handle_key_press() == [handler]

    def test_key_release(self):
        events = _make_events(("up", "key_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("up", handler)
        em.handle_key_press()  # set state
        assert em.handle_key_release() == [handler]

    def test_key_press_release_within_duration(self):
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 500}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("activate", handler)

        em.handle_key_press()
        result = em.handle_key_release()
        assert handler in result

    def test_key_press_release_exceeded(self):
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 1}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("activate", handler)

        em.handle_key_press()
        time.sleep(0.01)
        result = em.handle_key_release()
        assert handler not in result

    def test_key_release_without_press(self):
        events = _make_events(("up", "key_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("up", handler)
        result = em.handle_key_release()
        assert result == [handler]

    def test_key_press_release_no_max(self):
        events = _make_events(("tap", "key_press_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("tap", handler)
        em.handle_key_press()
        time.sleep(0.01)
        assert handler in em.handle_key_release()

    def test_release_always_fires_alongside_press_release(self):
        """key_release fires even when key_press_release also fires."""
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 500}),
            ("up", "key_release"),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        release_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("up", release_handler)

        em.handle_key_press()
        result = em.handle_key_release()
        assert tap_handler in result
        assert release_handler in result

    def test_press_always_fires_with_hold_configured(self):
        """key_press fires even when key_hold is also configured."""
        events = _make_events(
            ("down", "key_press"),
            ("long_hold", "key_hold", {"hold_ms": 500}),
        )
        em = EventMap(events)
        press_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("down", press_handler)
        em.on("long_hold", hold_handler)

        result = em.handle_key_press()
        assert press_handler in result

    def test_no_key_press_mapping_returns_empty(self):
        """handle_key_press returns empty list when no key_press mapping."""
        events = _make_events(("up", "key_release"))
        em = EventMap(events)
        result = em.handle_key_press()
        assert result == []

    def test_no_key_release_mapping_returns_empty(self):
        """handle_key_release returns empty list when no key_release mapping."""
        events = _make_events(("down", "key_press"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("down", handler)
        em.handle_key_press()
        result = em.handle_key_release()
        assert result == []


class TestKeyHold:
    async def test_hold_fires_after_delay(self):
        """key_hold handler fires after hold_ms while key is still held."""
        events = _make_events(
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("long_hold", handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)  # wait well past 10ms
        handler.assert_awaited_once()

    async def test_hold_cancelled_on_early_release(self):
        """key_hold does NOT fire if released before hold_ms."""
        events = _make_events(
            ("long_hold", "key_hold", {"hold_ms": 5000}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("long_hold", handler)

        em.handle_key_press()
        em.handle_key_release()  # immediate release
        await asyncio.sleep(0.01)
        handler.assert_not_awaited()

    async def test_hold_suppresses_press_release(self):
        """After key_hold fires, key_press_release is suppressed on release."""
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 5000}),
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)  # hold fires
        hold_handler.assert_awaited_once()

        result = em.handle_key_release()
        assert tap_handler not in result  # press_release suppressed
        tap_handler.assert_not_awaited()

    async def test_hold_does_not_suppress_key_release(self):
        """After key_hold fires, key_release still fires."""
        events = _make_events(
            ("up", "key_release"),
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        release_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("up", release_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_key_release()
        assert release_handler in result

    async def test_short_tap_still_works_with_hold(self):
        """Quick release fires press_release, not the hold."""
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 300}),
            ("long_hold", "key_hold", {"hold_ms": 500}),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        # Release immediately — well before 500ms hold
        result = em.handle_key_release()
        assert tap_handler in result
        hold_handler.assert_not_awaited()

    async def test_hold_no_handler_registered(self):
        """If no handler is registered, no timer starts."""
        events = _make_events(
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        # Don't register any handler

        em.handle_key_press()
        await asyncio.sleep(0.05)
        # Should not crash — task was never created
        assert em._hold_task is None

    async def test_hold_reset_between_presses(self):
        """hold_fired is reset on each new press."""
        events = _make_events(
            ("activate", "key_press_release"),
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("long_hold", hold_handler)

        # First: long hold
        em.handle_key_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()
        em.handle_key_release()  # suppressed

        # Second: quick tap
        em.handle_key_press()
        result = em.handle_key_release()
        assert tap_handler in result

    async def test_hold_suppresses_press_release_but_not_release(self):
        """After key_hold fires, key_press_release is suppressed but key_release still fires."""
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 5000}),
            ("up", "key_release"),
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        release_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("up", release_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_key_release()
        assert tap_handler not in result  # compound gesture suppressed
        assert release_handler in result  # simple release still fires


class TestEncoderHold:
    async def test_encoder_hold_fires_after_delay(self):
        events = _make_events(
            ("enc_hold", "encoder_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("enc_hold", handler)

        em.handle_encoder_press()
        await asyncio.sleep(0.05)
        handler.assert_awaited_once()

    async def test_encoder_hold_cancelled_on_early_release(self):
        events = _make_events(
            ("enc_hold", "encoder_hold", {"hold_ms": 5000}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("enc_hold", handler)

        em.handle_encoder_press()
        em.handle_encoder_release()
        await asyncio.sleep(0.01)
        handler.assert_not_awaited()

    async def test_encoder_hold_suppresses_press_release(self):
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 5000}),
            ("enc_hold", "encoder_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        toggle_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("toggle", toggle_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_encoder_release()
        assert toggle_handler not in result  # compound gesture suppressed
        toggle_handler.assert_not_awaited()

    async def test_encoder_short_tap_still_works_with_hold(self):
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 300}),
            ("enc_hold", "encoder_hold", {"hold_ms": 500}),
        )
        em = EventMap(events)
        toggle_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("toggle", toggle_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_release()
        assert toggle_handler in result
        hold_handler.assert_not_awaited()

    async def test_encoder_release_fires_alongside_press_release(self):
        """encoder_release fires even when encoder_press_release also fires."""
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 500}),
            ("up", "encoder_release"),
            ("enc_hold", "encoder_hold", {"hold_ms": 500}),
        )
        em = EventMap(events)
        toggle_handler = AsyncMock()
        release_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("toggle", toggle_handler)
        em.on("up", release_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_release()
        assert toggle_handler in result
        assert release_handler in result

    async def test_encoder_hold_cancelled_by_turn_before_hold_ms(self):
        """encoder_hold does NOT fire if a turn occurs before hold_ms expires."""
        events = _make_events(
            ("seek", "encoder_press_turn"),
            ("enc_hold", "encoder_hold", {"hold_ms": 50}),
        )
        em = EventMap(events)
        seek_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("seek", seek_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        # Turn before hold_ms — should cancel hold timer
        result = em.handle_encoder_turn(1)
        assert result is seek_handler

        await asyncio.sleep(0.1)  # wait past hold_ms
        hold_handler.assert_not_awaited()

    async def test_encoder_hold_cancelled_by_turn_without_press_turn_mapping(self):
        """encoder_hold is cancelled by turn even without encoder_press_turn mapping."""
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("enc_hold", "encoder_hold", {"hold_ms": 50}),
        )
        em = EventMap(events)
        scroll_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("scroll", scroll_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        em.handle_encoder_turn(1)  # turn cancels hold

        await asyncio.sleep(0.1)
        hold_handler.assert_not_awaited()

    async def test_encoder_hold_does_not_suppress_release(self):
        """After encoder_hold fires, encoder_release still fires."""
        events = _make_events(
            ("up", "encoder_release"),
            ("enc_hold", "encoder_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        release_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("up", release_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_encoder_release()
        assert release_handler in result


class TestTouchEvents:
    def test_tap_in_region(self):
        events = _make_events(("card_tap", "tap"))
        regions = (
            Region(name="card", x=0, y=0, width=197, height=98, events=("tap",)),
        )
        em = EventMap(events, regions)
        handler = AsyncMock()
        em.on("card_tap", handler)

        result = em.handle_touch(EventType.TOUCH_SHORT, 50, 50)
        assert result is handler

    def test_tap_outside_region(self):
        events = _make_events(("card_tap", "tap"))
        regions = (Region(name="card", x=0, y=0, width=50, height=50, events=("tap",)),)
        em = EventMap(events, regions)
        handler = AsyncMock()
        em.on("card_tap", handler)

        # Touch at (100, 50) is outside the region but tap is also a top-level event
        result = em.handle_touch(EventType.TOUCH_SHORT, 100, 50)
        assert result is handler  # falls through to top-level

    def test_long_press_in_region(self):
        events = _make_events(("menu", "long_press"))
        regions = (
            Region(name="card", x=0, y=0, width=197, height=98, events=("long_press",)),
        )
        em = EventMap(events, regions)
        handler = AsyncMock()
        em.on("menu", handler)

        result = em.handle_touch(EventType.TOUCH_LONG, 50, 50)
        assert result is handler

    def test_drag_not_handled(self):
        events = _make_events(("card_tap", "tap"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("card_tap", handler)
        result = em.handle_touch(EventType.TOUCH_DRAG, 50, 50)
        assert result is None

    def test_no_regions_still_matches_top_level(self):
        events = _make_events(("card_tap", "tap"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("card_tap", handler)
        result = em.handle_touch(EventType.TOUCH_SHORT, 50, 50)
        assert result is handler

    def test_region_event_mismatch(self):
        """Region only accepts 'tap' but we send long_press."""
        events = _make_events(("menu", "long_press"))
        regions = (
            Region(name="card", x=0, y=0, width=197, height=98, events=("tap",)),
        )
        em = EventMap(events, regions)
        handler = AsyncMock()
        em.on("menu", handler)
        # Region doesn't have long_press, but top-level does
        result = em.handle_touch(EventType.TOUCH_LONG, 50, 50)
        assert result is handler


class TestEventMapRegistration:
    def test_on_unknown_event_raises(self):
        events = _make_events(("play", "encoder_press"))
        em = EventMap(events)
        with pytest.raises(KeyError, match="Unknown event"):
            em.on("nonexistent", AsyncMock())

    def test_event_names_property(self):
        events = _make_events(("play", "encoder_press"), ("stop", "encoder_release"))
        em = EventMap(events)
        assert em.event_names == ["play", "stop"]

    def test_unregistered_handler_returns_empty(self):
        events = _make_events(("play", "encoder_press"))
        em = EventMap(events)
        # Don't register any handler
        assert em.handle_encoder_press() == []
