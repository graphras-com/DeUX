"""Device capabilities queried from a connected Stream Deck."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from StreamDeck.Devices.StreamDeck import StreamDeck


def _coerce_flip(value: object) -> tuple[bool, bool]:
    """Coerce a device flip tuple to a typed `(bool, bool)` pair."""
    if isinstance(value, tuple) and len(value) == 2:
        return (bool(value[0]), bool(value[1]))
    return (False, False)


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    """Immutable snapshot of a Stream Deck device's hardware capabilities.

    Constructed from a connected device via :meth:`from_device`, this
    dataclass captures every property needed to drive layout, rendering,
    and event routing without hardcoded constants.
    """

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

    @classmethod
    def from_device(cls, device: StreamDeck) -> DeviceCapabilities:
        """Build capabilities from a connected (opened) device.

        Args:
            device: An open ``StreamDeck`` device object.

        Returns:
            A frozen :class:`DeviceCapabilities` instance.
        """
        key_layout = device.key_layout()
        return cls(
            deck_type=device.DECK_TYPE,
            key_count=device.key_count(),
            key_cols=key_layout[0],
            key_rows=key_layout[1],
            key_pixel_width=device.KEY_PIXEL_WIDTH,
            key_pixel_height=device.KEY_PIXEL_HEIGHT,
            key_image_format=device.KEY_IMAGE_FORMAT,
            key_flip=_coerce_flip(device.KEY_FLIP),
            key_rotation=device.KEY_ROTATION,
            has_visual=device.DECK_VISUAL,
            has_touch=getattr(device, "DECK_TOUCH", False),
            dial_count=device.dial_count(),
            touchscreen_width=device.TOUCHSCREEN_PIXEL_WIDTH,
            touchscreen_height=device.TOUCHSCREEN_PIXEL_HEIGHT,
            touchscreen_image_format=getattr(
                device, "TOUCHSCREEN_IMAGE_FORMAT", ""
            ),
            touchscreen_flip=_coerce_flip(
                getattr(device, "TOUCHSCREEN_FLIP", (False, False))
            ),
            touchscreen_rotation=getattr(device, "TOUCHSCREEN_ROTATION", 0),
            has_screen=getattr(device, "SCREEN_PIXEL_WIDTH", 0) > 0,
            screen_width=getattr(device, "SCREEN_PIXEL_WIDTH", 0),
            screen_height=getattr(device, "SCREEN_PIXEL_HEIGHT", 0),
            screen_image_format=getattr(device, "SCREEN_IMAGE_FORMAT", ""),
            screen_flip=_coerce_flip(getattr(device, "SCREEN_FLIP", (False, False))),
            screen_rotation=getattr(device, "SCREEN_ROTATION", 0),
            touch_key_count=getattr(device, "TOUCH_KEY_COUNT", 0),
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
)
