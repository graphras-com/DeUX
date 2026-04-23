"""Rendering metrics derived from device capabilities.

All metrics are computed from a
:class:`~deckui.runtime.capabilities.DeviceCapabilities` instance.
Default module-level constants are provided as convenience aliases
for the Stream Deck+ profile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..runtime.capabilities import DeviceCapabilities


class RenderMetrics:
    """Computed rendering metrics for a specific device.

    All layout constants (key sizes, touchscreen panel dimensions,
    info-screen dimensions) are derived from the device's
    :class:`~deckui.runtime.capabilities.DeviceCapabilities`.

    Args:
        caps: Device capabilities to derive metrics from.
    """

    def __init__(self, caps: DeviceCapabilities) -> None:
        self._caps = caps

        self.key_size: tuple[int, int] = (caps.key_pixel_width, caps.key_pixel_height)
        self.key_margin_top = max(1, round(caps.key_pixel_height * 7 / 120))
        self.key_margin_right = max(1, round(caps.key_pixel_width * 7 / 120))
        self.key_margin_bottom = max(1, round(caps.key_pixel_height * 7 / 120))
        self.key_margin_left = max(1, round(caps.key_pixel_width * 7 / 120))
        self.key_usable_width = (
            caps.key_pixel_width - self.key_margin_left - self.key_margin_right
        )
        self.key_usable_height = (
            caps.key_pixel_height - self.key_margin_top - self.key_margin_bottom
        )
        self.icon_size = max(1, round(caps.key_pixel_width * 80 / 120))
        self.icon_padding = max(0, (self.key_usable_width - self.icon_size) // 2)

        self.touchscreen_width = caps.touchscreen_width
        self.touchscreen_height = caps.touchscreen_height
        self.panel_count = caps.panel_count

        self.margin_top = 0
        self.margin_bottom = 2 if caps.has_touchscreen else 0
        self.margin_left = 2 if caps.has_touchscreen else 0
        self.margin_right = 2 if caps.has_touchscreen else 0
        self.panel_gap = 2 if caps.has_touchscreen else 0

        self.usable_width = (
            caps.touchscreen_width - self.margin_left - self.margin_right
        )
        self.usable_height = (
            caps.touchscreen_height - self.margin_top - self.margin_bottom
        )

        if self.panel_count > 0 and caps.has_touchscreen:
            self.panel_width = (
                self.usable_width - (self.panel_count - 1) * self.panel_gap
            ) // self.panel_count
        else:
            self.panel_width = 0

        self.panel_height = self.usable_height if caps.has_touchscreen else 0

        self.screen_width = caps.screen_width
        self.screen_height = caps.screen_height

        self.key_image_format = caps.key_image_format
        self.key_count = caps.key_count
        self.dial_count = caps.dial_count


def _default_metrics() -> RenderMetrics:
    """Create metrics for the default Stream Deck+ profile."""
    from ..runtime.capabilities import STREAM_DECK_PLUS

    return RenderMetrics(STREAM_DECK_PLUS)


_DEFAULT = _default_metrics()

KEY_SIZE = _DEFAULT.key_size
KEY_MARGIN_TOP = _DEFAULT.key_margin_top
KEY_MARGIN_RIGHT = _DEFAULT.key_margin_right
KEY_MARGIN_BOTTOM = _DEFAULT.key_margin_bottom
KEY_MARGIN_LEFT = _DEFAULT.key_margin_left
KEY_USABLE_WIDTH = _DEFAULT.key_usable_width
KEY_USABLE_HEIGHT = _DEFAULT.key_usable_height
ICON_SIZE = _DEFAULT.icon_size
ICON_PADDING = _DEFAULT.icon_padding

TOUCHSCREEN_WIDTH = _DEFAULT.touchscreen_width
TOUCHSCREEN_HEIGHT = _DEFAULT.touchscreen_height
PANEL_COUNT = _DEFAULT.panel_count

MARGIN_TOP = _DEFAULT.margin_top
MARGIN_BOTTOM = _DEFAULT.margin_bottom
MARGIN_LEFT = _DEFAULT.margin_left
MARGIN_RIGHT = _DEFAULT.margin_right
PANEL_GAP = _DEFAULT.panel_gap

USABLE_WIDTH = _DEFAULT.usable_width
USABLE_HEIGHT = _DEFAULT.usable_height

PANEL_WIDTH = _DEFAULT.panel_width
PANEL_HEIGHT = _DEFAULT.panel_height
