"""Rendering metrics derived from device capabilities.

All metrics are computed from a
:class:`~deux.runtime.capabilities.DeviceCapabilities` instance.
Geometry is hardware-agnostic: the library renders edge-to-edge at the
device's native pixel sizes and does not impose any margins, padding,
gaps, or icon-centering defaults of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..runtime.capabilities import DeviceCapabilities


class RenderMetrics:
    """Computed rendering metrics for a specific device.

    All fields are derived from the device's
    :class:`~deux.runtime.capabilities.DeviceCapabilities` — there are
    no model-specific defaults. Panel dimensions are computed without
    margins or gaps; consumers are responsible for any spacing they want
    to apply in their own SVG/layout.

    Parameters
    ----------
    caps
        Device capabilities to derive metrics from.
    """

    def __init__(self, caps: DeviceCapabilities) -> None:
        self._caps = caps

        self.key_size: tuple[int, int] = (caps.key_pixel_width, caps.key_pixel_height)
        self.key_image_format = caps.key_image_format
        self.key_count = caps.key_count

        self.touchscreen_width = caps.touchscreen_width
        self.touchscreen_height = caps.touchscreen_height
        self.panel_count = caps.panel_count

        if caps.has_touchscreen and self.panel_count > 0:
            self.panel_width = caps.touchscreen_width // self.panel_count
            self.panel_height = caps.touchscreen_height
        else:
            self.panel_width = 0
            self.panel_height = 0

        self.screen_width = caps.screen_width
        self.screen_height = caps.screen_height

        self.dial_count = caps.dial_count
