"""Device discovery utilities for enumerating Stream Deck hardware."""

from __future__ import annotations

import asyncio

from ._executor import get_executor
from .device_info import DeviceInfo
from .hid._ctypes_hidapi import HidApiError
from .hid.discovery import enumerate_devices


async def list_devices(
    *,
    deck_type: str | None = None,
) -> list[DeviceInfo]:
    """Enumerate all connected Stream Deck devices.

    Discovers devices via HID, opens each briefly to read serial and
    firmware information, then closes them.  Returns a list of
    :class:`DeviceInfo` snapshots.

    Parameters
    ----------
    deck_type
        If set, only return devices matching this type
        (e.g. ``"Stream Deck +"``).

    Returns
    -------
    list[DeviceInfo]
        A list of :class:`DeviceInfo` for each discovered device.
    """
    loop = asyncio.get_running_loop()
    executor = get_executor()

    devices = await loop.run_in_executor(executor, enumerate_devices)

    results: list[DeviceInfo] = []
    for d in devices:
        try:
            await loop.run_in_executor(executor, d.open)
            info = DeviceInfo(
                deck_type=d.family,
                serial=d.serial_number,
                firmware=d.firmware_version,
                key_count=d.key_count,
                key_layout=d.key_layout,
                encoder_count=d.encoder_count,
                key_pixel_size=d.key_size,
                touchscreen_size=d.window_size if d.has_touch else (0, 0),
                key_image_format="JPEG",
            )
            if deck_type is not None and info.deck_type != deck_type:
                await loop.run_in_executor(executor, d.close)
                continue
            results.append(info)
            await loop.run_in_executor(executor, d.close)
        except (HidApiError, Exception):
            continue

    return results
