"""Tests for deckboard.runtime.events — events, enums, and dataclasses."""

from __future__ import annotations

import dataclasses

import pytest

from deckboard.runtime.events import (
    DeckEvent,
    DialPressEvent,
    DialTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from deckboard.runtime.device_info import DeviceInfo


# ── EventType enum ──────────────────────────────────────────────────────


class TestEventType:
    def test_members_exist(self):
        assert EventType.DIAL_TURN is not None
        assert EventType.TOUCH_SHORT is not None
        assert EventType.TOUCH_LONG is not None
        assert EventType.TOUCH_DRAG is not None

    def test_member_count(self):
        assert len(EventType) == 4

    def test_members_are_distinct(self):
        values = [e.value for e in EventType]
        assert len(values) == len(set(values))


# ── KeyEvent ────────────────────────────────────────────────────────────


class TestKeyEvent:
    def test_construction(self):
        e = KeyEvent(key=3, pressed=True)
        assert e.key == 3
        assert e.pressed is True

    def test_frozen(self):
        e = KeyEvent(key=0, pressed=False)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.key = 1  # type: ignore[misc]

    def test_equality(self):
        a = KeyEvent(key=1, pressed=True)
        b = KeyEvent(key=1, pressed=True)
        assert a == b

    def test_inequality(self):
        a = KeyEvent(key=1, pressed=True)
        b = KeyEvent(key=1, pressed=False)
        assert a != b


# ── DialTurnEvent ───────────────────────────────────────────────────────


class TestDialTurnEvent:
    def test_construction(self):
        e = DialTurnEvent(dial=2, direction=1)
        assert e.dial == 2
        assert e.direction == 1

    def test_negative_direction(self):
        e = DialTurnEvent(dial=0, direction=-3)
        assert e.direction == -3

    def test_frozen(self):
        e = DialTurnEvent(dial=0, direction=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.dial = 2  # type: ignore[misc]

    def test_equality(self):
        assert DialTurnEvent(dial=1, direction=2) == DialTurnEvent(dial=1, direction=2)


# ── DialPressEvent ──────────────────────────────────────────────────────


class TestDialPressEvent:
    def test_construction(self):
        e = DialPressEvent(dial=1, pressed=True)
        assert e.dial == 1
        assert e.pressed is True

    def test_frozen(self):
        e = DialPressEvent(dial=0, pressed=False)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.pressed = True  # type: ignore[misc]

    def test_equality(self):
        assert DialPressEvent(dial=0, pressed=True) == DialPressEvent(
            dial=0, pressed=True
        )


# ── TouchEvent ──────────────────────────────────────────────────────────


class TestTouchEvent:
    def test_construction_short(self):
        e = TouchEvent(event_type=EventType.TOUCH_SHORT, x=100, y=50)
        assert e.event_type == EventType.TOUCH_SHORT
        assert e.x == 100
        assert e.y == 50
        assert e.x_out is None
        assert e.y_out is None

    def test_construction_drag(self):
        e = TouchEvent(
            event_type=EventType.TOUCH_DRAG,
            x=10,
            y=20,
            x_out=300,
            y_out=80,
        )
        assert e.x_out == 300
        assert e.y_out == 80

    def test_frozen(self):
        e = TouchEvent(event_type=EventType.TOUCH_SHORT, x=0, y=0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.x = 5  # type: ignore[misc]

    def test_zone_first_widget(self):
        """Touches within the first widget zone (left margin to end of widget 0)."""
        # Left edge of screen (within left margin) still maps to zone 0
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=0, y=0).zone == 0
        # Inside widget 0 area
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=4, y=0).zone == 0
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=198, y=0).zone == 0

    def test_zone_second_widget(self):
        """Touches within the second widget zone."""
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=203, y=0).zone == 1
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=397, y=0).zone == 1

    def test_zone_third_widget(self):
        """Touches within the third widget zone."""
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=402, y=0).zone == 2

    def test_zone_fourth_widget(self):
        """Touches within the fourth widget zone."""
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=601, y=0).zone == 3
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=799, y=0).zone == 3

    def test_zone_capped_at_3(self):
        """x >= 800 should still return zone 3 (capped)."""
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=1000, y=0).zone == 3
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=800, y=0).zone == 3


# ── DeviceInfo ──────────────────────────────────────────────────────────


class TestDeviceInfo:
    def test_construction(self):
        info = DeviceInfo(
            deck_type="Stream Deck +",
            serial="ABC123",
            firmware="1.0.0",
            key_count=8,
            key_layout=(4, 2),
            dial_count=4,
            key_pixel_size=(120, 120),
            touchscreen_size=(800, 100),
            key_image_format="JPEG",
        )
        assert info.deck_type == "Stream Deck +"
        assert info.serial == "ABC123"
        assert info.firmware == "1.0.0"
        assert info.key_count == 8
        assert info.key_layout == (4, 2)
        assert info.dial_count == 4
        assert info.key_pixel_size == (120, 120)
        assert info.touchscreen_size == (800, 100)
        assert info.key_image_format == "JPEG"

    def test_is_mutable(self):
        """DeviceInfo is a regular (non-frozen) dataclass."""
        info = DeviceInfo(
            deck_type="x",
            serial="x",
            firmware="x",
            key_count=0,
            key_layout=(0, 0),
            dial_count=0,
            key_pixel_size=(0, 0),
            touchscreen_size=(0, 0),
            key_image_format="x",
        )
        info.deck_type = "changed"
        assert info.deck_type == "changed"


# ── DeckEvent union ─────────────────────────────────────────────────────


class TestDeckEvent:
    def test_key_event_is_deck_event(self):
        e = KeyEvent(key=0, pressed=True)
        assert isinstance(e, KeyEvent)

    def test_dial_turn_is_deck_event(self):
        e = DialTurnEvent(dial=0, direction=1)
        assert isinstance(e, DialTurnEvent)

    def test_touch_event_is_deck_event(self):
        e = TouchEvent(event_type=EventType.TOUCH_SHORT, x=0, y=0)
        assert isinstance(e, TouchEvent)
