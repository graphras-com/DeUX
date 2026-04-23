"""Tests for deckui.runtime.transport — AsyncTransport class."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from deckui.runtime.capabilities import STREAM_DECK_PLUS
from deckui.runtime.events import (
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from deckui.runtime.transport import AsyncTransport
from tests.conftest import STREAM_DECK_MINI


@pytest.fixture
def mock_device():
    device = MagicMock()
    device.set_key_callback = MagicMock()
    device.set_dial_callback = MagicMock()
    device.set_touchscreen_callback = MagicMock()
    return device


# ── start / stop ────────────────────────────────────────────────────────


class TestTransportLifecycle:
    async def test_start_registers_callbacks(self, mock_device):
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        mock_device.set_key_callback.assert_called_once_with(transport._on_key)
        mock_device.set_dial_callback.assert_called_once_with(transport._on_encoder)
        mock_device.set_touchscreen_callback.assert_called_once_with(
            transport._on_touch
        )
        assert transport._running is True

    async def test_start_no_encoders_skips_dial_callback(self, mock_device):
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_MINI)
        transport.start()
        mock_device.set_key_callback.assert_called_once()
        mock_device.set_dial_callback.assert_not_called()
        mock_device.set_touchscreen_callback.assert_not_called()

    async def test_stop_unregisters_callbacks(self, mock_device):
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport.stop()
        mock_device.set_key_callback.assert_called_with(None)
        mock_device.set_dial_callback.assert_called_with(None)
        mock_device.set_touchscreen_callback.assert_called_with(None)
        assert transport._running is False

    async def test_stop_no_encoders_skips_dial_callback(self, mock_device):
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_MINI)
        transport.start()
        transport.stop()
        # set_dial_callback should never have been called (not even with None)
        mock_device.set_dial_callback.assert_not_called()

    async def test_queue_property(self, mock_device):
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        assert isinstance(transport.queue, asyncio.Queue)

    async def test_start_with_no_caps_registers_all(self, mock_device):
        """When caps is None, all callbacks are registered (backward compat)."""
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, None)
        transport.start()
        mock_device.set_key_callback.assert_called_once()
        mock_device.set_dial_callback.assert_called_once()
        mock_device.set_touchscreen_callback.assert_called_once()


# ── _enqueue ────────────────────────────────────────────────────────────


class TestTransportEnqueue:
    async def test_enqueue_puts_event(self, mock_device):
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        event = KeyEvent(key=0, pressed=True)
        transport._enqueue(event)
        await asyncio.sleep(0.01)
        result = transport.queue.get_nowait()
        assert result == event

    async def test_enqueue_ignored_when_stopped(self, mock_device):
        """Events are dropped when transport is not running."""
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        # Don't call start() — transport._running is False
        event = KeyEvent(key=0, pressed=True)
        transport._enqueue(event)
        await asyncio.sleep(0.01)
        assert transport.queue.empty()


# ── _on_key ─────────────────────────────────────────────────────────────


class TestTransportOnKey:
    async def test_key_press(self, mock_device):
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_key(mock_device, 3, True)
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert isinstance(event, KeyEvent)
        assert event.key == 3
        assert event.pressed is True

    async def test_key_release(self, mock_device):
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_key(mock_device, 5, False)
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert event.key == 5
        assert event.pressed is False


# ── _on_encoder ─────────────────────────────────────────────────────────


class TestTransportOnEncoder:
    async def test_encoder_push(self, mock_device):
        from StreamDeck.Devices.StreamDeck import DialEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_encoder(mock_device, 1, DialEventType.PUSH, True)
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert isinstance(event, EncoderPressEvent)
        assert event.encoder == 1
        assert event.pressed is True

    async def test_encoder_push_release(self, mock_device):
        from StreamDeck.Devices.StreamDeck import DialEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_encoder(mock_device, 2, DialEventType.PUSH, False)
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert isinstance(event, EncoderPressEvent)
        assert event.pressed is False

    async def test_encoder_turn_clockwise(self, mock_device):
        from StreamDeck.Devices.StreamDeck import DialEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_encoder(mock_device, 0, DialEventType.TURN, 3)
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert isinstance(event, EncoderTurnEvent)
        assert event.encoder == 0
        assert event.direction == 3

    async def test_encoder_turn_counterclockwise(self, mock_device):
        from StreamDeck.Devices.StreamDeck import DialEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_encoder(mock_device, 1, DialEventType.TURN, -2)
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert isinstance(event, EncoderTurnEvent)
        assert event.direction == -2


# ── _on_touch ───────────────────────────────────────────────────────────


class TestTransportOnTouch:
    async def test_touch_short(self, mock_device):
        from StreamDeck.Devices.StreamDeck import TouchscreenEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_touch(
            mock_device,
            TouchscreenEventType.SHORT,
            {"x": 100, "y": 50},
        )
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert isinstance(event, TouchEvent)
        assert event.event_type == EventType.TOUCH_SHORT
        assert event.x == 100
        assert event.y == 50
        assert event.x_out is None
        assert event.y_out is None

    async def test_touch_long(self, mock_device):
        from StreamDeck.Devices.StreamDeck import TouchscreenEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_touch(
            mock_device,
            TouchscreenEventType.LONG,
            {"x": 300, "y": 80},
        )
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert event.event_type == EventType.TOUCH_LONG

    async def test_touch_drag(self, mock_device):
        from StreamDeck.Devices.StreamDeck import TouchscreenEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_touch(
            mock_device,
            TouchscreenEventType.DRAG,
            {"x": 10, "y": 20, "x_out": 500, "y_out": 80},
        )
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert event.event_type == EventType.TOUCH_DRAG
        assert event.x == 10
        assert event.y == 20
        assert event.x_out == 500
        assert event.y_out == 80

    async def test_touch_missing_keys_default_zero(self, mock_device):
        from StreamDeck.Devices.StreamDeck import TouchscreenEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._on_touch(
            mock_device,
            TouchscreenEventType.SHORT,
            {},  # no x, y keys
        )
        await asyncio.sleep(0.01)
        event = transport.queue.get_nowait()
        assert event.x == 0
        assert event.y == 0

    async def test_unknown_touch_type_ignored(self, mock_device):
        """Unknown touch event types should be silently ignored."""
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        unknown_type = MagicMock()
        transport._on_touch(mock_device, unknown_type, {"x": 0, "y": 0})
        await asyncio.sleep(0.01)
        assert transport.queue.empty()


# ── Error handling in callbacks ─────────────────────────────────────────


class TestTransportErrorHandling:
    async def test_key_callback_error_logged(self, mock_device):
        """Errors in key callback are caught and logged."""
        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._enqueue = MagicMock(side_effect=RuntimeError("test error"))
        transport._on_key(mock_device, 0, True)
        # Should not propagate the exception
        assert transport.queue.empty()

    async def test_encoder_callback_error_logged(self, mock_device):
        from StreamDeck.Devices.StreamDeck import DialEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._enqueue = MagicMock(side_effect=RuntimeError("test"))
        transport._on_encoder(mock_device, 0, DialEventType.PUSH, True)
        # Should not propagate

    async def test_touch_callback_error_logged(self, mock_device):
        from StreamDeck.Devices.StreamDeck import TouchscreenEventType

        loop = asyncio.get_running_loop()
        transport = AsyncTransport(mock_device, loop, STREAM_DECK_PLUS)
        transport.start()
        transport._enqueue = MagicMock(side_effect=RuntimeError("test"))
        transport._on_touch(mock_device, TouchscreenEventType.SHORT, {"x": 0, "y": 0})
        # Should not propagate
