"""Device discovery utilities for enumerating Stream Deck hardware."""

from __future__ import annotations

import asyncio
from typing import Any

from StreamDeck.DeviceManager import DeviceManager

from ._executor import get_executor
from .device_info import DeviceInfo


async def list_devices(
    *,
    deck_type: str | None = None,
    visual_only: bool = True,
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
    visual_only
        If ``True`` (default), exclude non-visual devices
        such as the Stream Deck Pedal.

    Returns
    -------
    list[DeviceInfo]
        A list of :class:`DeviceInfo` for each discovered device.
    """
    loop = asyncio.get_running_loop()
    executor = get_executor()

    devices: list[Any] = await loop.run_in_executor(executor, DeviceManager().enumerate)

    if visual_only:
        devices = [d for d in devices if d.DECK_VISUAL]

    results: list[DeviceInfo] = []
    for d in devices:
        try:
            await loop.run_in_executor(executor, d.open)
            info = DeviceInfo(
                deck_type=d.deck_type(),
                serial=d.get_serial_number(),
                firmware=d.get_firmware_version(),
                key_count=d.key_count(),
                key_layout=d.key_layout(),
                encoder_count=d.dial_count(),
                key_pixel_size=(d.KEY_PIXEL_WIDTH, d.KEY_PIXEL_HEIGHT),
                touchscreen_size=(
                    d.TOUCHSCREEN_PIXEL_WIDTH,
                    d.TOUCHSCREEN_PIXEL_HEIGHT,
                ),
                key_image_format=d.KEY_IMAGE_FORMAT,
            )
            if deck_type is not None and info.deck_type != deck_type:
                await loop.run_in_executor(executor, d.close)
                continue
            results.append(info)
            await loop.run_in_executor(executor, d.close)
        except Exception:
            continue

    return results
