"""Device information model for a connected Stream Deck."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeviceInfo:
    """Information about a connected Stream Deck device."""

    deck_type: str
    serial: str
    firmware: str
    key_count: int
    key_layout: tuple[int, int]
    dial_count: int
    key_pixel_size: tuple[int, int]
    touchscreen_size: tuple[int, int]
    key_image_format: str
