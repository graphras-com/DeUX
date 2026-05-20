"""Tests for ``deux.runtime.hid.transport``.

Validates the async HID call wrapper and input polling loop.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from deux.runtime.hid._ctypes_hidapi import HidApiError
from deux.runtime.hid.transport import (
    HidWriteTimeout,
    async_hid_call,
    poll_input,
)


# ---------------------------------------------------------------------------
# async_hid_call
# ---------------------------------------------------------------------------


class TestAsyncHidCall:
    """Tests for :func:`async_hid_call`."""

    async def test_returns_result(self) -> None:
        """Returns the function's return value."""
        result = await async_hid_call(lambda: 42, timeout=2.0)
        assert result == 42

    async def test_passes_arguments(self) -> None:
        """Passes positional arguments to the function."""
        result = await async_hid_call(lambda a, b: a + b, 3, 4, timeout=2.0)
        assert result == 7

    async def test_raises_hid_write_timeout(self) -> None:
        """Raises ``HidWriteTimeout`` when the call exceeds timeout."""

        def slow_func() -> None:
            """Block longer than the timeout."""
            time.sleep(5)

        with pytest.raises(HidWriteTimeout):
            await async_hid_call(slow_func, timeout=0.05)

    async def test_hid_write_timeout_is_timeout_error(self) -> None:
        """``HidWriteTimeout`` is a :class:`TimeoutError` subclass."""
        assert issubclass(HidWriteTimeout, TimeoutError)


# ---------------------------------------------------------------------------
# poll_input
# ---------------------------------------------------------------------------


class TestPollInput:
    """Tests for :func:`poll_input`."""

    async def test_yields_events(self) -> None:
        """Yields events returned by ``device.read_input``."""
        event = MagicMock()
        device = MagicMock()
        # is_open returns True twice (one event + one stop), then False
        type(device).is_open = PropertyMock(side_effect=[True, True, False])
        device.read_input.side_effect = [event, None]

        events: list[object] = []
        async for e in poll_input(device, poll_interval_ms=10):
            events.append(e)

        assert events == [event]

    async def test_stops_when_device_closed(self) -> None:
        """Stops iteration when ``device.is_open`` is ``False``."""
        device = MagicMock()
        type(device).is_open = PropertyMock(return_value=False)

        events: list[object] = []
        async for e in poll_input(device, poll_interval_ms=10):
            events.append(e)

        assert events == []

    async def test_stops_on_hid_api_error(self) -> None:
        """Stops iteration when ``read_input`` raises ``HidApiError``."""
        device = MagicMock()
        type(device).is_open = PropertyMock(return_value=True)
        device.read_input.side_effect = HidApiError("disconnected")

        events: list[object] = []
        async for e in poll_input(device, poll_interval_ms=10):
            events.append(e)

        assert events == []
