"""Device information model for a connected Stream Deck."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Information about a connected Stream Deck device.

    Attributes
    ----------
    deck_type : str
        Human-readable device model name (e.g. ``"Stream Deck +"``).
    serial : str
        Unique serial number reported by the hardware.
    firmware : str
        Firmware version string.
    key_count : int
        Total number of physical keys on the device.
    key_layout : tuple[int, int]
        Key grid dimensions as ``(columns, rows)``.
    encoder_count : int
        Number of rotary encoders (dials) on the device.
    key_pixel_size : tuple[int, int]
        Pixel dimensions of a single key image as ``(width, height)``.
    touchscreen_size : tuple[int, int]
        Pixel dimensions of the touchscreen as ``(width, height)``.
        ``(0, 0)`` if the device has no touchscreen.
    key_image_format : str
        Image format expected by the device (e.g. ``"JPEG"``).
    """

    deck_type: str
    serial: str
    firmware: str
    key_count: int
    key_layout: tuple[int, int]
    encoder_count: int
    key_pixel_size: tuple[int, int]
    touchscreen_size: tuple[int, int]
    key_image_format: str
