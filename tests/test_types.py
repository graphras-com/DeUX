"""Tests for deckui.runtime.events — events, enums, and dataclasses."""

from __future__ import annotations

import dataclasses

import pytest

from deckui.render.metrics import RenderMetrics
from deckui.runtime.capabilities import STREAM_DECK_PLUS
from deckui.runtime.device_info import DeviceInfo
from deckui.runtime.events import (
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)


class TestEventType:
    def test_members_exist(self):
        assert EventType.ENCODER_TURN is not None
        assert EventType.TOUCH_SHORT is not None
        assert EventType.TOUCH_LONG is not None
        assert EventType.TOUCH_DRAG is not None

    def test_member_count(self):
        assert len(EventType) == 4

    def test_members_are_distinct(self):
        values = [e.value for e in EventType]
        assert len(values) == len(set(values))


class TestKeyEvent:
    def test_construction(self):
        e = KeyEvent(key=3, pressed=True)
        assert e.key == 3
        assert e.pressed is True

    def test_frozen(self):
        e = KeyEvent(key=0, pressed=False)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.key = 1

    def test_equality(self):
        a = KeyEvent(key=1, pressed=True)
        b = KeyEvent(key=1, pressed=True)
        assert a == b

    def test_inequality(self):
        a = KeyEvent(key=1, pressed=True)
        b = KeyEvent(key=1, pressed=False)
        assert a != b


class TestEncoderTurnEvent:
    def test_construction(self):
        e = EncoderTurnEvent(encoder=2, direction=1)
        assert e.encoder == 2
        assert e.direction == 1

    def test_negative_direction(self):
        e = EncoderTurnEvent(encoder=0, direction=-3)
        assert e.direction == -3

    def test_frozen(self):
        e = EncoderTurnEvent(encoder=0, direction=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.encoder = 2

    def test_equality(self):
        assert EncoderTurnEvent(encoder=1, direction=2) == EncoderTurnEvent(
            encoder=1, direction=2
        )


class TestEncoderPressEvent:
    def test_construction(self):
        e = EncoderPressEvent(encoder=1, pressed=True)
        assert e.encoder == 1
        assert e.pressed is True

    def test_frozen(self):
        e = EncoderPressEvent(encoder=0, pressed=False)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.pressed = True

    def test_equality(self):
        assert EncoderPressEvent(encoder=0, pressed=True) == EncoderPressEvent(
            encoder=0, pressed=True
        )


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
            e.x = 5

    def test_zone_first_widget(self):
        """Touches within the first widget zone (left margin to end of widget 0)."""
        metrics = RenderMetrics(STREAM_DECK_PLUS)
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=0, y=0).compute_zone(metrics) == 0
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=4, y=0).compute_zone(metrics) == 0
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=198, y=0).compute_zone(metrics) == 0

    def test_zone_second_widget(self):
        """Touches within the second widget zone."""
        metrics = RenderMetrics(STREAM_DECK_PLUS)
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=203, y=0).compute_zone(metrics) == 1
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=397, y=0).compute_zone(metrics) == 1

    def test_zone_third_widget(self):
        """Touches within the third widget zone."""
        metrics = RenderMetrics(STREAM_DECK_PLUS)
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=402, y=0).compute_zone(metrics) == 2

    def test_zone_fourth_widget(self):
        """Touches within the fourth widget zone."""
        metrics = RenderMetrics(STREAM_DECK_PLUS)
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=601, y=0).compute_zone(metrics) == 3
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=799, y=0).compute_zone(metrics) == 3

    def test_zone_capped_at_3(self):
        """x >= 800 should still return zone 3 (capped)."""
        metrics = RenderMetrics(STREAM_DECK_PLUS)
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=1000, y=0).compute_zone(metrics) == 3
        assert TouchEvent(event_type=EventType.TOUCH_SHORT, x=800, y=0).compute_zone(metrics) == 3


class TestDeviceInfo:
    def test_construction(self):
        info = DeviceInfo(
            deck_type="Stream Deck +",
            serial="ABC123",
            firmware="1.0.0",
            key_count=8,
            key_layout=(4, 2),
            encoder_count=4,
            key_pixel_size=(120, 120),
            touchscreen_size=(800, 100),
            key_image_format="JPEG",
        )
        assert info.deck_type == "Stream Deck +"
        assert info.serial == "ABC123"
        assert info.firmware == "1.0.0"
        assert info.key_count == 8
        assert info.key_layout == (4, 2)
        assert info.encoder_count == 4
        assert info.key_pixel_size == (120, 120)
        assert info.touchscreen_size == (800, 100)
        assert info.key_image_format == "JPEG"

    def test_is_frozen(self):
        """DeviceInfo is a frozen dataclass."""
        info = DeviceInfo(
            deck_type="x",
            serial="x",
            firmware="x",
            key_count=0,
            key_layout=(0, 0),
            encoder_count=0,
            key_pixel_size=(0, 0),
            touchscreen_size=(0, 0),
            key_image_format="x",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.deck_type = "changed"


class TestDeckEvent:
    def test_key_event_is_deck_event(self):
        e = KeyEvent(key=0, pressed=True)
        assert isinstance(e, KeyEvent)

    def test_encoder_turn_is_deck_event(self):
        e = EncoderTurnEvent(encoder=0, direction=1)
        assert isinstance(e, EncoderTurnEvent)

    def test_touch_event_is_deck_event(self):
        e = TouchEvent(event_type=EventType.TOUCH_SHORT, x=0, y=0)
        assert isinstance(e, TouchEvent)
