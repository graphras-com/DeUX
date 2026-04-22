"""Tests for deckboard.runtime.discovery — list_devices function."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deckboard.runtime.discovery import list_devices


def _make_raw_device(
    deck_type: str = "Stream Deck +",
    serial: str = "ABC123",
    visual: bool = True,
) -> MagicMock:
    """Create a MagicMock mimicking a raw python-elgato-streamdeck device."""
    d = MagicMock()
    d.DECK_VISUAL = visual
    d.DECK_TYPE = deck_type
    d.KEY_PIXEL_WIDTH = 120
    d.KEY_PIXEL_HEIGHT = 120
    d.KEY_IMAGE_FORMAT = "JPEG"
    d.TOUCHSCREEN_PIXEL_WIDTH = 800
    d.TOUCHSCREEN_PIXEL_HEIGHT = 100
    d.deck_type.return_value = deck_type
    d.get_serial_number.return_value = serial
    d.get_firmware_version.return_value = "1.0.0"
    d.key_count.return_value = 8
    d.key_layout.return_value = (4, 2)
    d.dial_count.return_value = 4
    d.open.return_value = None
    d.close.return_value = None
    return d


class TestListDevices:
    async def test_no_devices(self):
        with patch("deckboard.runtime.discovery.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            result = await list_devices()
            assert result == []

    async def test_returns_device_info(self):
        dev = _make_raw_device()
        with patch("deckboard.runtime.discovery.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            result = await list_devices()
            assert len(result) == 1
            assert result[0].serial == "ABC123"
            assert result[0].deck_type == "Stream Deck +"
            assert result[0].key_count == 8

    async def test_filters_non_visual(self):
        dev = _make_raw_device(visual=False)
        with patch("deckboard.runtime.discovery.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            result = await list_devices()
            assert result == []

    async def test_visual_only_false_includes_all(self):
        dev = _make_raw_device(visual=False, serial="PEDAL1")
        with patch("deckboard.runtime.discovery.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            result = await list_devices(visual_only=False)
            assert len(result) == 1
            assert result[0].serial == "PEDAL1"

    async def test_filter_by_deck_type(self):
        plus = _make_raw_device(deck_type="Stream Deck +", serial="PLUS1")
        mini = _make_raw_device(deck_type="Stream Deck Mini", serial="MINI1")
        with patch("deckboard.runtime.discovery.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [plus, mini]
            result = await list_devices(deck_type="Stream Deck +")
            assert len(result) == 1
            assert result[0].serial == "PLUS1"

    async def test_filter_by_deck_type_no_match(self):
        dev = _make_raw_device(deck_type="Stream Deck Mini")
        with patch("deckboard.runtime.discovery.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            result = await list_devices(deck_type="Stream Deck XL")
            assert result == []

    async def test_multiple_devices(self):
        d1 = _make_raw_device(serial="DEV1")
        d2 = _make_raw_device(serial="DEV2")
        with patch("deckboard.runtime.discovery.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [d1, d2]
            result = await list_devices()
            assert len(result) == 2
            serials = {r.serial for r in result}
            assert serials == {"DEV1", "DEV2"}

    async def test_device_open_error_skipped(self):
        d1 = _make_raw_device(serial="OK1")
        d2 = _make_raw_device(serial="BAD1")
        d2.open.side_effect = OSError("HID error")
        with patch("deckboard.runtime.discovery.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [d1, d2]
            result = await list_devices()
            assert len(result) == 1
            assert result[0].serial == "OK1"
