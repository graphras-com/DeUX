"""Tests for deux.runtime.discovery — list_devices function."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from deux.runtime.discovery import list_devices


def _make_hid_device(
    family: str = "Stream Deck +",
    serial: str = "ABC123",
    firmware: str = "1.0.0",
    key_count: int = 8,
    key_layout: tuple[int, int] = (4, 2),
    encoder_count: int = 4,
    key_size: tuple[int, int] = (120, 120),
    window_size: tuple[int, int] = (800, 100),
    has_touch: bool = True,
) -> MagicMock:
    """Create a MagicMock mimicking an HidDevice.

    Parameters
    ----------
    family : str
        The device family name.
    serial : str
        Device serial number.
    firmware : str
        Firmware version string.
    key_count : int
        Number of keys.
    key_layout : tuple[int, int]
        Key layout as (cols, rows).
    encoder_count : int
        Number of rotary encoders.
    key_size : tuple[int, int]
        Per-key pixel dimensions (width, height).
    window_size : tuple[int, int]
        Touchscreen pixel dimensions (width, height).
    has_touch : bool
        Whether the device has a touchscreen.

    Returns
    -------
    MagicMock
        A mock HidDevice.
    """
    d = MagicMock()
    d.family = family
    d.serial_number = serial
    d.firmware_version = firmware
    d.key_count = key_count
    d.key_layout = key_layout
    d.encoder_count = encoder_count
    d.key_size = key_size
    d.window_size = window_size
    d.has_touch = has_touch
    d.open.return_value = None
    d.close.return_value = None
    return d


class TestListDevices:
    """Tests for the list_devices async function."""

    async def test_no_devices(self):
        """Return empty list when no devices are connected."""
        with patch("deux.runtime.discovery.enumerate_devices") as mock_enum:
            mock_enum.return_value = []
            result = await list_devices()
            assert result == []

    async def test_returns_device_info(self):
        """Return DeviceInfo for a discovered device."""
        dev = _make_hid_device()
        with patch("deux.runtime.discovery.enumerate_devices") as mock_enum:
            mock_enum.return_value = [dev]
            result = await list_devices()
            assert len(result) == 1
            assert result[0].serial == "ABC123"
            assert result[0].deck_type == "Stream Deck +"
            assert result[0].key_count == 8

    async def test_filter_by_deck_type(self):
        """Filter results by deck_type parameter."""
        plus = _make_hid_device(family="Stream Deck +", serial="PLUS1")
        xl = _make_hid_device(family="Stream Deck XL", serial="XL1")
        with patch("deux.runtime.discovery.enumerate_devices") as mock_enum:
            mock_enum.return_value = [plus, xl]
            result = await list_devices(deck_type="Stream Deck +")
            assert len(result) == 1
            assert result[0].serial == "PLUS1"

    async def test_filter_by_deck_type_no_match(self):
        """Return empty list when no device matches deck_type."""
        dev = _make_hid_device(family="Stream Deck +")
        with patch("deux.runtime.discovery.enumerate_devices") as mock_enum:
            mock_enum.return_value = [dev]
            result = await list_devices(deck_type="Stream Deck XL")
            assert result == []

    async def test_multiple_devices(self):
        """Return info for multiple discovered devices."""
        d1 = _make_hid_device(serial="DEV1")
        d2 = _make_hid_device(serial="DEV2")
        with patch("deux.runtime.discovery.enumerate_devices") as mock_enum:
            mock_enum.return_value = [d1, d2]
            result = await list_devices()
            assert len(result) == 2
            serials = {r.serial for r in result}
            assert serials == {"DEV1", "DEV2"}

    async def test_device_open_error_skipped(self):
        """Skip devices that raise on open."""
        d1 = _make_hid_device(serial="OK1")
        d2 = _make_hid_device(serial="BAD1")
        d2.open.side_effect = OSError("HID error")
        with patch("deux.runtime.discovery.enumerate_devices") as mock_enum:
            mock_enum.return_value = [d1, d2]
            result = await list_devices()
            assert len(result) == 1
            assert result[0].serial == "OK1"

    async def test_no_touchscreen_device(self):
        """Touchscreen size is (0, 0) when device has no touch."""
        dev = _make_hid_device(has_touch=False)
        with patch("deux.runtime.discovery.enumerate_devices") as mock_enum:
            mock_enum.return_value = [dev]
            result = await list_devices()
            assert result[0].touchscreen_size == (0, 0)
