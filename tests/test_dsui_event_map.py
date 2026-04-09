"""Tests for deckboard.dsui.event_map — event routing and gesture detection."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from deckboard.dsui.event_map import EventMap
from deckboard.dsui.schema import EventMapping, Region
from deckboard.runtime.events import EventType


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
        assert em.handle_encoder_press() is handler

    def test_simple_release(self):
        events = _make_events(("release", "encoder_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("release", handler)
        em.handle_encoder_press()  # establish pressed state
        assert em.handle_encoder_release() is handler

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
        assert result is handler

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
        assert result is None

    def test_press_release_no_max_duration(self):
        events = _make_events(("toggle", "encoder_press_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("toggle", handler)

        em.handle_encoder_press()
        time.sleep(0.01)
        result = em.handle_encoder_release()
        assert result is handler  # No max_duration → always fires

    def test_release_without_press(self):
        events = _make_events(("release", "encoder_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("release", handler)
        # No press recorded
        result = em.handle_encoder_release()
        assert result is handler


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


class TestKeyEvents:
    def test_key_press(self):
        events = _make_events(("hold", "key_press"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("hold", handler)
        assert em.handle_key_press() is handler

    def test_key_release(self):
        events = _make_events(("up", "key_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("up", handler)
        em.handle_key_press()  # set state
        assert em.handle_key_release() is handler

    def test_key_press_release_within_duration(self):
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 500}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("activate", handler)

        em.handle_key_press()
        result = em.handle_key_release()
        assert result is handler

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
        assert result is None

    def test_key_release_without_press(self):
        events = _make_events(("up", "key_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("up", handler)
        result = em.handle_key_release()
        assert result is handler

    def test_key_press_release_no_max(self):
        events = _make_events(("tap", "key_press_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("tap", handler)
        em.handle_key_press()
        time.sleep(0.01)
        assert em.handle_key_release() is handler


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

    def test_unregistered_handler_returns_none(self):
        events = _make_events(("play", "encoder_press"))
        em = EventMap(events)
        # Don't register any handler
        assert em.handle_encoder_press() is None
