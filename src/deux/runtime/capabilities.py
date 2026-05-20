"""Device capabilities queried from a connected Stream Deck."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hid.device import HidDevice


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    """Immutable snapshot of a Stream Deck device's hardware capabilities.

    Constructed from a connected device via :meth:`from_device`, this
    dataclass captures every property needed to drive layout, rendering,
    and event routing without hardcoded constants.
    """

    vendor_id: int
    product_id: int
    deck_type: str
    key_count: int
    key_cols: int
    key_rows: int
    key_pixel_width: int
    key_pixel_height: int
    key_image_format: str
    key_flip: tuple[bool, bool]
    key_rotation: int
    has_visual: bool
    has_touch: bool
    dial_count: int
    touchscreen_width: int
    touchscreen_height: int
    touchscreen_image_format: str
    touchscreen_flip: tuple[bool, bool]
    touchscreen_rotation: int
    has_screen: bool
    screen_width: int
    screen_height: int
    screen_image_format: str
    screen_flip: tuple[bool, bool]
    screen_rotation: int
    touch_key_count: int
    lcd_width: int = 0
    lcd_height: int = 0

    @classmethod
    def from_device(cls, device: HidDevice) -> DeviceCapabilities:
        """Build capabilities from a connected (opened) HID device.

        Reads hardware information from the device's ``Get Unit Information``
        feature report and derives all capabilities from the product ID and
        self-reported geometry.

        Parameters
        ----------
        device : HidDevice
            An open :class:`~deux.runtime.hid.device.HidDevice`.

        Returns
        -------
        DeviceCapabilities
            A frozen :class:`DeviceCapabilities` instance.
        """
        key_layout = device.key_layout  # (cols, rows)
        key_w, key_h = device.key_size
        lcd_w, lcd_h = device.lcd_size
        win_w, win_h = device.window_size
        rotation = device.rotation.value

        return cls(
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            deck_type=device.family,
            key_count=device.key_count,
            key_cols=key_layout[0],
            key_rows=key_layout[1],
            key_pixel_width=key_w,
            key_pixel_height=key_h,
            key_image_format="JPEG",
            key_flip=(False, False),
            key_rotation=rotation,
            has_visual=True,
            has_touch=device.has_touch,
            dial_count=device.encoder_count,
            touchscreen_width=win_w if device.has_touch else 0,
            touchscreen_height=win_h if device.has_touch else 0,
            touchscreen_image_format="JPEG" if device.has_touch else "",
            touchscreen_flip=(False, False),
            touchscreen_rotation=0,
            has_screen=device.has_window and not device.has_touch,
            screen_width=win_w if (device.has_window and not device.has_touch) else 0,
            screen_height=win_h if (device.has_window and not device.has_touch) else 0,
            screen_image_format="JPEG" if (device.has_window and not device.has_touch) else "",
            screen_flip=(False, False),
            screen_rotation=rotation if (device.has_window and not device.has_touch) else 0,
            touch_key_count=device.sensor_count,
            lcd_width=lcd_w,
            lcd_height=lcd_h,
        )

    @property
    def key_size(self) -> tuple[int, int]:
        """Key image dimensions as ``(width, height)``."""
        return (self.key_pixel_width, self.key_pixel_height)

    @property
    def has_encoders(self) -> bool:
        """Whether the device has rotary encoders (dials)."""
        return self.dial_count > 0

    @property
    def has_touchscreen(self) -> bool:
        """Whether the device has a touchscreen strip."""
        return self.touchscreen_width > 0 and self.touchscreen_height > 0

    @property
    def has_info_screen(self) -> bool:
        """Whether the device has a non-touch info screen (e.g. Neo)."""
        return self.has_screen

    @property
    def panel_count(self) -> int:
        """Number of touchscreen card zones (equals dial count)."""
        return self.dial_count


STREAM_DECK_PLUS = DeviceCapabilities(
    vendor_id=0x0FD9,
    product_id=0x0084,
    deck_type="Stream Deck +",
    key_count=8,
    key_cols=4,
    key_rows=2,
    key_pixel_width=120,
    key_pixel_height=120,
    key_image_format="JPEG",
    key_flip=(False, False),
    key_rotation=0,
    has_visual=True,
    has_touch=True,
    dial_count=4,
    touchscreen_width=800,
    touchscreen_height=100,
    touchscreen_image_format="JPEG",
    touchscreen_flip=(False, False),
    touchscreen_rotation=0,
    has_screen=False,
    screen_width=0,
    screen_height=0,
    screen_image_format="",
    screen_flip=(False, False),
    screen_rotation=0,
    touch_key_count=0,
    lcd_width=800,
    lcd_height=480,
)
