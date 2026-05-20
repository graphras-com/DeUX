"""Tests for ``deux.runtime.hid.discovery``.

Validates device enumeration, filtering by supported PIDs, and
device lookup by serial number or path.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import deux.runtime.hid.discovery as discovery_mod
from deux.runtime.hid._ctypes_hidapi import HidDeviceInfo
from deux.runtime.hid.discovery import (
    _ensure_init,
    enumerate_devices,
    find_device_by_path,
    find_device_by_serial,
)
from deux.runtime.hid.protocol import SUPPORTED_PIDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Pick a known-supported PID from the set for test fixtures.
_SUPPORTED_PID = next(iter(SUPPORTED_PIDS))
_UNSUPPORTED_PID = 0xFFFF  # guaranteed not in allowlist


def _make_info(
    pid: int,
    serial: str = "SN001",
    path: bytes = b"/dev/hid0",
) -> HidDeviceInfo:
    """Build a :class:`HidDeviceInfo` with Elgato VID.

    Parameters
    ----------
    pid : int
        USB product ID.
    serial : str, default="SN001"
        Device serial number.
    path : bytes, default=b"/dev/hid0"
        Device path.

    Returns
    -------
    HidDeviceInfo
        A populated device info object.
    """
    return HidDeviceInfo(
        path=path,
        vendor_id=0x0FD9,
        product_id=pid,
        serial_number=serial,
        product_string="Test Device",
    )


@pytest.fixture(autouse=True)
def _reset_init_flag() -> None:
    """Reset the module-level ``_initialized`` flag before each test."""
    discovery_mod._initialized = False  # noqa: SLF001


# ---------------------------------------------------------------------------
# _ensure_init
# ---------------------------------------------------------------------------


class TestEnsureInit:
    """Tests for :func:`_ensure_init`."""

    def test_calls_hid_init_once(self) -> None:
        """``hid_init`` is called only on the first invocation."""
        with patch("deux.runtime.hid.discovery.hid_init") as mock_init:
            _ensure_init()
            _ensure_init()
            mock_init.assert_called_once()

    def test_sets_initialized_flag(self) -> None:
        """The module flag is set after init."""
        with patch("deux.runtime.hid.discovery.hid_init"):
            _ensure_init()
            assert discovery_mod._initialized is True  # noqa: SLF001


# ---------------------------------------------------------------------------
# enumerate_devices
# ---------------------------------------------------------------------------


class TestEnumerateDevices:
    """Tests for :func:`enumerate_devices`."""

    def test_returns_supported_devices(self) -> None:
        """Devices with supported PIDs are included."""
        infos = [_make_info(_SUPPORTED_PID, serial="A")]
        with (
            patch("deux.runtime.hid.discovery.hid_init"),
            patch("deux.runtime.hid.discovery.hid_enumerate", return_value=infos),
        ):
            devices = enumerate_devices()
            assert len(devices) == 1
            assert devices[0].product_id == _SUPPORTED_PID

    def test_filters_unsupported_pids(self) -> None:
        """Devices with unsupported PIDs are excluded."""
        infos = [
            _make_info(_SUPPORTED_PID, serial="A", path=b"/dev/hid0"),
            _make_info(_UNSUPPORTED_PID, serial="B", path=b"/dev/hid1"),
        ]
        with (
            patch("deux.runtime.hid.discovery.hid_init"),
            patch("deux.runtime.hid.discovery.hid_enumerate", return_value=infos),
        ):
            devices = enumerate_devices()
            assert len(devices) == 1
            assert devices[0].serial_number == "A"

    def test_returns_empty_when_no_devices(self) -> None:
        """Returns empty list when no HID devices are found."""
        with (
            patch("deux.runtime.hid.discovery.hid_init"),
            patch("deux.runtime.hid.discovery.hid_enumerate", return_value=[]),
        ):
            devices = enumerate_devices()
            assert devices == []


# ---------------------------------------------------------------------------
# find_device_by_serial
# ---------------------------------------------------------------------------


class TestFindDeviceBySerial:
    """Tests for :func:`find_device_by_serial`."""

    def test_returns_matching_device(self) -> None:
        """Returns the device when serial matches."""
        infos = [_make_info(_SUPPORTED_PID, serial="TARGET")]
        with (
            patch("deux.runtime.hid.discovery.hid_init"),
            patch("deux.runtime.hid.discovery.hid_enumerate", return_value=infos),
        ):
            device = find_device_by_serial("TARGET")
            assert device is not None
            assert device.serial_number == "TARGET"

    def test_returns_none_when_not_found(self) -> None:
        """Returns ``None`` when no device has the given serial."""
        infos = [_make_info(_SUPPORTED_PID, serial="OTHER")]
        with (
            patch("deux.runtime.hid.discovery.hid_init"),
            patch("deux.runtime.hid.discovery.hid_enumerate", return_value=infos),
        ):
            assert find_device_by_serial("MISSING") is None


# ---------------------------------------------------------------------------
# find_device_by_path
# ---------------------------------------------------------------------------


class TestFindDeviceByPath:
    """Tests for :func:`find_device_by_path`."""

    def test_returns_matching_device(self) -> None:
        """Returns the device when path matches."""
        infos = [_make_info(_SUPPORTED_PID, path=b"/dev/hidX")]
        with (
            patch("deux.runtime.hid.discovery.hid_init"),
            patch("deux.runtime.hid.discovery.hid_enumerate", return_value=infos),
        ):
            device = find_device_by_path(b"/dev/hidX")
            assert device is not None
            assert device.path == b"/dev/hidX"

    def test_returns_none_when_not_found(self) -> None:
        """Returns ``None`` when no device has the given path."""
        with (
            patch("deux.runtime.hid.discovery.hid_init"),
            patch("deux.runtime.hid.discovery.hid_enumerate", return_value=[]),
        ):
            assert find_device_by_path(b"/dev/missing") is None
