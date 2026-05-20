"""Stream Deck device discovery via HID enumeration.

Enumerates connected Elgato HID devices filtered by a PID allowlist,
returning :class:`~deux.runtime.hid.device.HidDevice` instances.
"""

from __future__ import annotations

from deux.runtime.hid._ctypes_hidapi import hid_enumerate, hid_init
from deux.runtime.hid.device import HidDevice
from deux.runtime.hid.protocol import ELGATO_VID, SUPPORTED_PIDS

_initialized = False


def _ensure_init() -> None:
    """Initialise ``hidapi`` once on first use."""
    global _initialized  # noqa: PLW0603
    if not _initialized:
        hid_init()
        _initialized = True


def enumerate_devices() -> list[HidDevice]:
    """Enumerate all connected and supported Stream Deck devices.

    Scans for HID devices with Elgato's vendor ID (``0x0FD9``) and
    filters to the supported PID allowlist.

    Returns
    -------
    list[HidDevice]
        List of :class:`HidDevice` instances (not yet opened).

    Raises
    ------
    HidApiError
        If ``hidapi`` cannot be initialised or enumeration fails.
    """
    _ensure_init()
    infos = hid_enumerate(vendor_id=ELGATO_VID, product_id=0)
    devices: list[HidDevice] = []
    for info in infos:
        if info.product_id in SUPPORTED_PIDS:
            devices.append(HidDevice(info))
    return devices


def find_device_by_serial(serial: str) -> HidDevice | None:
    """Find a specific device by serial number.

    Parameters
    ----------
    serial : str
        The device serial number to match.

    Returns
    -------
    HidDevice or None
        The matching device (not yet opened), or ``None`` if not found.
    """
    for device in enumerate_devices():
        if device.serial_number == serial:
            return device
    return None


def find_device_by_path(path: bytes) -> HidDevice | None:
    """Find a specific device by OS device path.

    Parameters
    ----------
    path : bytes
        The OS-specific HID device path.

    Returns
    -------
    HidDevice or None
        The matching device (not yet opened), or ``None`` if not found.
    """
    for device in enumerate_devices():
        if device.path == path:
            return device
    return None
