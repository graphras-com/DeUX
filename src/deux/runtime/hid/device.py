"""Generic, self-describing Stream Deck HID device.

A single :class:`HidDevice` class handles all supported Stream Deck models.
Hardware capabilities are read at open time via the ``Get Unit Information``
feature report rather than being hardcoded per model.
"""

from __future__ import annotations

from deux.runtime.hid._ctypes_hidapi import (
    HidApiError,
    HidDeviceInfo,
    hid_close,
    hid_get_feature_report,
    hid_open,
    hid_read_timeout,
    hid_send_feature_report,
    hid_write,
)
from deux.runtime.hid.protocol import (
    FEATURE_REPORT_SIZE,
    INPUT_REPORT_SIZE,
    PID_ROTATION,
    ImageRotation,
    InputEvent,
    ReportId,
    UnitInfo,
    build_fill_key_color,
    build_fill_lcd_color,
    build_full_screen_reports,
    build_key_image_reports,
    build_partial_window_reports,
    build_set_brightness,
    build_set_sleep_duration,
    build_show_logo,
    build_window_reports,
    parse_firmware_version,
    parse_input_report,
    parse_serial_number,
    parse_unit_info,
)

# ---------------------------------------------------------------------------
# Device family names derived from PID
# ---------------------------------------------------------------------------

_PID_FAMILY: dict[int, str] = {
    0x006D: "Stream Deck Classic",
    0x0080: "Stream Deck Classic",
    0x00A5: "Stream Deck Classic",
    0x00B9: "Stream Deck Classic",
    0x006C: "Stream Deck XL",
    0x008F: "Stream Deck XL",
    0x00BA: "Stream Deck XL",
    0x009A: "Stream Deck Neo",
    0x0084: "Stream Deck +",
    0x00C6: "Stream Deck + XL",
}

# PIDs with window (touchscreen or info strip)
_WINDOW_PIDS: frozenset[int] = frozenset({
    0x009A,  # Neo (info strip, 248x58)
    0x0084,  # Plus (touchscreen, 800x100)
    0x00C6,  # Plus XL (touchscreen, 1200x100)
})

# PIDs with encoders
_ENCODER_PIDS: frozenset[int] = frozenset({
    0x0084,  # Plus (4 encoders)
    0x00C6,  # Plus XL (6 encoders)
})

# PIDs with touch capability (not just info strip)
_TOUCH_PIDS: frozenset[int] = frozenset({
    0x0084,  # Plus
    0x00C6,  # Plus XL
})

# Encoder counts per PID
_ENCODER_COUNTS: dict[int, int] = {
    0x0084: 4,
    0x00C6: 6,
}

# Window sizes per PID (width, height)
_WINDOW_SIZES: dict[int, tuple[int, int]] = {
    0x009A: (248, 58),
    0x0084: (800, 100),
    0x00C6: (1200, 100),
}

# Neo sensor count (capacitive touch sensors mapped as extra buttons)
_NEO_SENSOR_COUNT: dict[int, int] = {
    0x009A: 2,
}


class HidDevice:
    """A connected Stream Deck HID device.

    This class wraps a single HID device handle and provides typed methods
    for all supported operations.  Hardware capabilities are queried from
    the device itself at open time via ``Get Unit Information``.

    Parameters
    ----------
    info : HidDeviceInfo
        Enumeration info for the device.

    Attributes
    ----------
    path : bytes
        OS-specific HID device path.
    vendor_id : int
        USB vendor ID (always 0x0FD9 for Elgato).
    product_id : int
        USB product ID.
    """

    __slots__ = (
        "path",
        "vendor_id",
        "product_id",
        "_handle",
        "_unit_info",
        "_serial",
        "_firmware_version",
        "_rotation",
        "_family",
    )

    def __init__(self, info: HidDeviceInfo) -> None:
        self.path: bytes = info.path
        self.vendor_id: int = info.vendor_id
        self.product_id: int = info.product_id
        self._handle: int | None = None
        self._unit_info: UnitInfo | None = None
        self._serial: str = info.serial_number
        self._firmware_version: str = ""
        self._rotation: ImageRotation = PID_ROTATION.get(
            info.product_id, ImageRotation.NONE
        )
        self._family: str = _PID_FAMILY.get(info.product_id, "Unknown")

    # -- lifecycle ----------------------------------------------------------

    def open(self) -> None:
        """Open the HID device and read hardware capabilities.

        Raises
        ------
        HidApiError
            If the device cannot be opened.
        """
        self._handle = hid_open(self.path)
        self._read_device_info()

    def close(self) -> None:
        """Close the HID device handle."""
        if self._handle is not None:
            hid_close(self._handle)
            self._handle = None

    @property
    def is_open(self) -> bool:
        """Whether the device handle is open."""
        return self._handle is not None

    def _ensure_open(self) -> int:
        """Return the handle, raising if not open.

        Returns
        -------
        int
            The HID device handle.

        Raises
        ------
        HidApiError
            If the device is not open.
        """
        if self._handle is None:
            raise HidApiError("Device is not open")
        return self._handle

    # -- device info --------------------------------------------------------

    def _read_device_info(self) -> None:
        """Read unit info, serial, and firmware version from the device."""
        handle = self._ensure_open()

        # Unit information
        try:
            data = hid_get_feature_report(handle, ReportId.UNIT_INFO, FEATURE_REPORT_SIZE)
            self._unit_info = parse_unit_info(data)
        except (HidApiError, ValueError):
            self._unit_info = None

        # Serial number (may already be populated from enumeration)
        if not self._serial:
            try:
                data = hid_get_feature_report(
                    handle, ReportId.SERIAL_NUMBER, FEATURE_REPORT_SIZE
                )
                self._serial = parse_serial_number(data)
            except HidApiError:
                self._serial = ""

        # Firmware version (AP2 = primary)
        try:
            data = hid_get_feature_report(
                handle, ReportId.FW_VERSION_AP2, FEATURE_REPORT_SIZE
            )
            self._firmware_version = parse_firmware_version(data)
        except HidApiError:
            self._firmware_version = ""

    @property
    def unit_info(self) -> UnitInfo | None:
        """Hardware information from ``Get Unit Information``, or ``None``."""
        return self._unit_info

    @property
    def serial_number(self) -> str:
        """Device serial number."""
        return self._serial

    @property
    def firmware_version(self) -> str:
        """Primary firmware version string."""
        return self._firmware_version

    @property
    def family(self) -> str:
        """Device family name (e.g. ``'Stream Deck +'``)."""
        return self._family

    @property
    def rotation(self) -> ImageRotation:
        """Image rotation to apply before upload."""
        return self._rotation

    @property
    def key_count(self) -> int:
        """Number of keys (buttons)."""
        if self._unit_info:
            return self._unit_info.rows * self._unit_info.cols
        return 0

    @property
    def key_layout(self) -> tuple[int, int]:
        """Key matrix as ``(columns, rows)``."""
        if self._unit_info:
            return (self._unit_info.cols, self._unit_info.rows)
        return (0, 0)

    @property
    def key_size(self) -> tuple[int, int]:
        """Key image dimensions as ``(width, height)``."""
        if self._unit_info:
            return (self._unit_info.key_width, self._unit_info.key_height)
        return (0, 0)

    @property
    def lcd_size(self) -> tuple[int, int]:
        """Full LCD dimensions as ``(width, height)``."""
        if self._unit_info:
            return (self._unit_info.lcd_width, self._unit_info.lcd_height)
        return (0, 0)

    @property
    def has_window(self) -> bool:
        """Whether the device has a window strip (touchscreen or info)."""
        return self.product_id in _WINDOW_PIDS

    @property
    def window_size(self) -> tuple[int, int]:
        """Window strip dimensions as ``(width, height)``, or ``(0, 0)``."""
        return _WINDOW_SIZES.get(self.product_id, (0, 0))

    @property
    def has_touch(self) -> bool:
        """Whether the device has a touchscreen (not just info strip)."""
        return self.product_id in _TOUCH_PIDS

    @property
    def has_encoders(self) -> bool:
        """Whether the device has rotary encoders."""
        return self.product_id in _ENCODER_PIDS

    @property
    def encoder_count(self) -> int:
        """Number of rotary encoders."""
        return _ENCODER_COUNTS.get(self.product_id, 0)

    @property
    def sensor_count(self) -> int:
        """Number of capacitive touch sensors (Neo only)."""
        return _NEO_SENSOR_COUNT.get(self.product_id, 0)

    # -- input --------------------------------------------------------------

    def read_input(self, timeout_ms: int = 50) -> InputEvent | None:
        """Poll for an input event.

        Parameters
        ----------
        timeout_ms : int, default=50
            Read timeout in milliseconds.

        Returns
        -------
        InputEvent or None
            A parsed input event, or ``None`` on timeout.

        Raises
        ------
        HidApiError
            If the read fails (device disconnected, etc.).
        """
        handle = self._ensure_open()
        data = hid_read_timeout(handle, INPUT_REPORT_SIZE, timeout_ms)
        if data is None:
            return None
        return parse_input_report(data)

    # -- output: images -----------------------------------------------------

    def set_key_image(self, key_index: int, jpeg_data: bytes) -> None:
        """Upload a JPEG image for a single key.

        Parameters
        ----------
        key_index : int
            Zero-based key index.
        jpeg_data : bytes
            JPEG-encoded image data (must already be rotated).
        """
        handle = self._ensure_open()
        for report in build_key_image_reports(key_index, jpeg_data):
            hid_write(handle, report)

    def set_full_screen_image(self, jpeg_data: bytes) -> None:
        """Upload a JPEG image covering the entire LCD.

        Parameters
        ----------
        jpeg_data : bytes
            JPEG-encoded full-screen image (must already be rotated).
        """
        handle = self._ensure_open()
        for report in build_full_screen_reports(jpeg_data):
            hid_write(handle, report)

    def set_window_image(self, jpeg_data: bytes) -> None:
        """Upload a JPEG image for the full window strip.

        Parameters
        ----------
        jpeg_data : bytes
            JPEG-encoded window image (must already be rotated).
        """
        handle = self._ensure_open()
        for report in build_window_reports(jpeg_data):
            hid_write(handle, report)

    def set_partial_window_image(
        self, x: int, y: int, width: int, height: int, jpeg_data: bytes
    ) -> None:
        """Upload a JPEG image to a rectangular region of the window.

        Parameters
        ----------
        x : int
            X-coordinate (logical, no rotation accounting).
        y : int
            Y-coordinate.
        width : int
            Region width in pixels.
        height : int
            Region height in pixels.
        jpeg_data : bytes
            JPEG-encoded image (must already be rotated).
        """
        handle = self._ensure_open()
        for report in build_partial_window_reports(x, y, width, height, jpeg_data):
            hid_write(handle, report)

    # -- output: feature reports --------------------------------------------

    def set_brightness(self, percent: int) -> None:
        """Set the LCD backlight brightness.

        Parameters
        ----------
        percent : int
            Brightness level from 0 to 100.
        """
        handle = self._ensure_open()
        hid_send_feature_report(handle, build_set_brightness(percent))

    def show_logo(self) -> None:
        """Display the boot logo on the device."""
        handle = self._ensure_open()
        hid_send_feature_report(handle, build_show_logo())

    def fill_lcd_color(self, r: int, g: int, b: int) -> None:
        """Fill the entire LCD with an RGB color.

        Parameters
        ----------
        r : int
            Red component (0-255).
        g : int
            Green component (0-255).
        b : int
            Blue component (0-255).
        """
        handle = self._ensure_open()
        hid_send_feature_report(handle, build_fill_lcd_color(r, g, b))

    def fill_key_color(self, key_index: int, r: int, g: int, b: int) -> None:
        """Fill a single key with an RGB color.

        Parameters
        ----------
        key_index : int
            Zero-based key index.
        r : int
            Red component (0-255).
        g : int
            Green component (0-255).
        b : int
            Blue component (0-255).
        """
        handle = self._ensure_open()
        hid_send_feature_report(handle, build_fill_key_color(key_index, r, g, b))

    def set_sleep_duration(self, seconds: int) -> None:
        """Set the idle duration before the device enters sleep mode.

        Parameters
        ----------
        seconds : int
            Duration in seconds (0 = disabled).
        """
        handle = self._ensure_open()
        hid_send_feature_report(handle, build_set_sleep_duration(seconds))

    def __repr__(self) -> str:
        state = "open" if self.is_open else "closed"
        return (
            f"HidDevice({self._family}, "
            f"pid=0x{self.product_id:04X}, "
            f"serial={self._serial!r}, "
            f"{state})"
        )
