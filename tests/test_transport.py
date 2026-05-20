"""Tests for deux.runtime.transport — AsyncTransport (polling-based).

The new transport polls HID input reports via ``device.read_input()``
and translates parsed ``InputEvent`` objects into ``DeckEvent`` items
on an asyncio queue.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from deux.runtime.capabilities import STREAM_DECK_PLUS
from deux.runtime.events import (
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from deux.runtime.hid.protocol import (
    EncoderButtonEvent,
    EncoderRotateEvent,
    KeyStateEvent,
    TouchFlickEvent,
    TouchPressEvent,
    TouchTapEvent,
)
from deux.runtime.transport import AsyncTransport


@pytest.fixture
def mock_device():
    """Create a mock HidDevice for transport tests.

    Returns
    -------
    MagicMock
        A mock with ``read_input``, ``is_open``, and basic attrs.
    """
    device = MagicMock()
    device.is_open = True
    device.read_input.return_value = None
    return device


class TestTransportLifecycle:
    """Start/stop behaviour of the polling-based transport."""

    async def test_start_creates_poll_task(self, mock_device):
        """start() sets _running and creates an asyncio task."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport.start()
        assert transport._running is True
        assert transport._poll_task is not None
        transport.stop()
        await asyncio.sleep(0.05)

    async def test_stop_cancels_poll_task(self, mock_device):
        """stop() sets _running to False and cancels the poll task."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport.start()
        transport.stop()
        assert transport._running is False
        await asyncio.sleep(0.05)

    async def test_queue_property(self, mock_device):
        """The queue property returns an asyncio.Queue."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        assert isinstance(transport.queue, asyncio.Queue)


class TestTranslateKeyState:
    """Key state change detection and event emission."""

    async def test_key_press(self, mock_device):
        """A newly pressed key produces a KeyEvent(pressed=True)."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        # Set initial all-released state
        transport._prev_key_states = (False, False, False, False)
        event = KeyStateEvent(states=(False, False, True, False))
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert isinstance(result, KeyEvent)
        assert result.key == 2
        assert result.pressed is True

    async def test_key_release(self, mock_device):
        """A released key produces a KeyEvent(pressed=False)."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        # Set initial state with key 1 pressed
        transport._prev_key_states = (False, True, False)
        event = KeyStateEvent(states=(False, False, False))
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert isinstance(result, KeyEvent)
        assert result.key == 1
        assert result.pressed is False

    async def test_no_change_no_event(self, mock_device):
        """Unchanged key states produce no events."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        transport._prev_key_states = (False, True, False)
        event = KeyStateEvent(states=(False, True, False))
        transport._translate_event(event)
        assert transport.queue.empty()

    async def test_initial_state_emits_all_keys(self, mock_device):
        """First key state with no previous state emits events for all keys."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        event = KeyStateEvent(states=(True, False, True, False))
        transport._translate_event(event)
        events = []
        while not transport.queue.empty():
            events.append(transport.queue.get_nowait())
        assert len(events) == 4  # all keys emit on first report


class TestTranslateTouchEvents:
    """Touch event translation."""

    async def test_touch_tap(self, mock_device):
        """TouchTapEvent produces a TOUCH_SHORT event."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        event = TouchTapEvent(x=100, y=50)
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert isinstance(result, TouchEvent)
        assert result.event_type == EventType.TOUCH_SHORT
        assert result.x == 100
        assert result.y == 50

    async def test_touch_press(self, mock_device):
        """TouchPressEvent produces a TOUCH_LONG event."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        event = TouchPressEvent(x=300, y=80)
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert result.event_type == EventType.TOUCH_LONG

    async def test_touch_flick(self, mock_device):
        """TouchFlickEvent produces a TOUCH_DRAG event with start/end coords."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        event = TouchFlickEvent(start_x=10, start_y=20, end_x=500, end_y=80)
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert result.event_type == EventType.TOUCH_DRAG
        assert result.x == 10
        assert result.y == 20
        assert result.x_out == 500
        assert result.y_out == 80


class TestTranslateEncoderEvents:
    """Encoder button and rotation event translation."""

    async def test_encoder_press(self, mock_device):
        """EncoderButtonEvent produces EncoderPressEvent for changed buttons."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        transport._prev_encoder_states = (False, False, False, False)
        event = EncoderButtonEvent(states=(False, True, False, False))
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert isinstance(result, EncoderPressEvent)
        assert result.encoder == 1
        assert result.pressed is True

    async def test_encoder_release(self, mock_device):
        """Released encoder produces EncoderPressEvent(pressed=False)."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        transport._prev_encoder_states = (False, True, False, False)
        event = EncoderButtonEvent(states=(False, False, False, False))
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert isinstance(result, EncoderPressEvent)
        assert result.encoder == 1
        assert result.pressed is False

    async def test_encoder_rotate_clockwise(self, mock_device):
        """EncoderRotateEvent produces EncoderTurnEvent for non-zero ticks."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        event = EncoderRotateEvent(ticks=(0, 3, 0, 0))
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert isinstance(result, EncoderTurnEvent)
        assert result.encoder == 1
        assert result.direction == 3

    async def test_encoder_rotate_counterclockwise(self, mock_device):
        """Negative ticks produce a negative direction."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        event = EncoderRotateEvent(ticks=(0, 0, -2, 0))
        transport._translate_event(event)
        result = transport.queue.get_nowait()
        assert isinstance(result, EncoderTurnEvent)
        assert result.encoder == 2
        assert result.direction == -2

    async def test_encoder_no_change_no_event(self, mock_device):
        """Unchanged encoder states produce no events."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        transport._prev_encoder_states = (False, False, False, False)
        event = EncoderButtonEvent(states=(False, False, False, False))
        transport._translate_event(event)
        assert transport.queue.empty()

    async def test_encoder_zero_rotation_ignored(self, mock_device):
        """Zero-tick encoders produce no events."""
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS)
        transport._running = True
        event = EncoderRotateEvent(ticks=(0, 0, 0, 0))
        transport._translate_event(event)
        assert transport.queue.empty()


class TestPollLoop:
    """Integration tests for the poll loop."""

    async def test_poll_loop_reads_device(self, mock_device):
        """The poll loop calls device.read_input and translates events."""
        call_count = 0

        def mock_read_input(timeout_ms):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return KeyStateEvent(states=(True, False))
            # Signal stop after first read
            mock_device.is_open = False
            return None

        mock_device.read_input.side_effect = mock_read_input

        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS, poll_interval_ms=10)
        transport.start()
        await asyncio.sleep(0.15)
        transport.stop()

        assert not transport.queue.empty()
        event = transport.queue.get_nowait()
        assert isinstance(event, KeyEvent)
        assert event.key == 0
        assert event.pressed is True

    async def test_poll_loop_stops_on_device_close(self, mock_device):
        """The poll loop exits when device.is_open becomes False."""
        mock_device.is_open = False
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS, poll_interval_ms=10)
        transport.start()
        await asyncio.sleep(0.1)
        # Task should have completed
        assert transport._poll_task is not None
        assert transport._poll_task.done()

    async def test_poll_loop_handles_hid_error(self, mock_device):
        """HidApiError during read stops the loop gracefully."""
        from deux.runtime.hid._ctypes_hidapi import HidApiError

        mock_device.read_input.side_effect = HidApiError("disconnected")
        transport = AsyncTransport(mock_device, STREAM_DECK_PLUS, poll_interval_ms=10)
        transport.start()
        await asyncio.sleep(0.1)
        assert transport._poll_task is not None
        assert transport._poll_task.done()
