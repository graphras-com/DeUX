"""HID protocol constants, report builders, and input event parsers.

Implements the Elgato Stream Deck Main Protocol as documented in
``docs/elgato-hid-protocol.md``.  The legacy Stream Deck Mini protocol
is not supported.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELGATO_VID = 0x0FD9
"""Elgato USB vendor ID."""

OUTPUT_REPORT_SIZE = 1024
"""Maximum size of an HID output report in bytes."""

INPUT_REPORT_SIZE = 512
"""Maximum size of an HID input report in bytes."""

FEATURE_REPORT_SIZE = 32
"""Maximum size of an HID feature report in bytes."""


class ReportId(IntEnum):
    """HID report IDs used by the main protocol."""

    INPUT = 0x01
    OUTPUT = 0x02
    FEATURE_SET = 0x03
    FW_VERSION_LD = 0x04
    FW_VERSION_AP2 = 0x05
    SERIAL_NUMBER = 0x06
    FW_VERSION_AP1 = 0x07
    UNIT_INFO = 0x08
    SLEEP_DURATION = 0x0A


class OutputCommand(IntEnum):
    """Command bytes for output reports (Report ID 0x02)."""

    UPDATE_KEY_IMAGE = 0x07
    UPDATE_FULL_SCREEN = 0x08
    UPDATE_WINDOW = 0x0B
    UPDATE_PARTIAL_WINDOW = 0x0C
    UPDATE_BACKGROUND = 0x0D


class InputCommand(IntEnum):
    """Command bytes for input reports (Report ID 0x01)."""

    KEY_STATE = 0x00
    TOUCH_SCREEN = 0x02
    ENCODER = 0x03


class FeatureCommand(IntEnum):
    """Command bytes for setter feature reports (Report ID 0x03)."""

    SHOW_LOGO = 0x02
    FILL_LCD_COLOR = 0x05
    FILL_KEY_COLOR = 0x06
    SET_BRIGHTNESS = 0x08
    SET_SLEEP_DURATION = 0x0D
    SHOW_BACKGROUND = 0x13


class TouchEventType(IntEnum):
    """Touch screen event content types."""

    TAP = 0x01
    PRESS = 0x02
    FLICK = 0x03


class EncoderEventType(IntEnum):
    """Encoder event content types."""

    BUTTON = 0x00
    ROTATE = 0x01


# ---------------------------------------------------------------------------
# Image rotation per PID
# ---------------------------------------------------------------------------


class ImageRotation(IntEnum):
    """Image rotation to apply before upload."""

    NONE = 0
    CW_180 = 180
    CCW_90 = 270


#: PID -> rotation mapping.  Devices not in this table are not supported.
PID_ROTATION: dict[int, ImageRotation] = {
    # Classic family (15-key)
    0x006D: ImageRotation.CW_180,
    0x0080: ImageRotation.CW_180,
    0x00A5: ImageRotation.CW_180,
    0x00B9: ImageRotation.CW_180,
    # XL family (32-key)
    0x006C: ImageRotation.CW_180,
    0x008F: ImageRotation.CW_180,
    0x00BA: ImageRotation.CW_180,
    # Neo
    0x009A: ImageRotation.CW_180,
    # Plus
    0x0084: ImageRotation.NONE,
    # Plus XL
    0x00C6: ImageRotation.CCW_90,
}

#: Set of all supported product IDs.
SUPPORTED_PIDS: frozenset[int] = frozenset(PID_ROTATION.keys())


# ---------------------------------------------------------------------------
# Input event data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KeyStateEvent:
    """One or more keys changed press state.

    Attributes
    ----------
    states : tuple[bool, ...]
        Per-key pressed state.  Index matches the key index.
    """

    states: tuple[bool, ...]


@dataclass(frozen=True, slots=True)
class TouchTapEvent:
    """Short tap on the touchscreen window.

    Attributes
    ----------
    x : int
        Touch X-coordinate.
    y : int
        Touch Y-coordinate.
    """

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class TouchPressEvent:
    """Long press (hold) on the touchscreen window.

    Attributes
    ----------
    x : int
        Touch X-coordinate.
    y : int
        Touch Y-coordinate.
    """

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class TouchFlickEvent:
    """Flick gesture on the touchscreen window.

    Attributes
    ----------
    start_x : int
        Start X-coordinate.
    start_y : int
        Start Y-coordinate.
    end_x : int
        End X-coordinate.
    end_y : int
        End Y-coordinate.
    """

    start_x: int
    start_y: int
    end_x: int
    end_y: int


@dataclass(frozen=True, slots=True)
class EncoderButtonEvent:
    """One or more encoder buttons changed press state.

    Attributes
    ----------
    states : tuple[bool, ...]
        Per-encoder pressed state.
    """

    states: tuple[bool, ...]


@dataclass(frozen=True, slots=True)
class EncoderRotateEvent:
    """One or more encoders were rotated.

    Attributes
    ----------
    ticks : tuple[int, ...]
        Per-encoder rotation ticks.  Positive = CW, negative = CCW.
    """

    ticks: tuple[int, ...]


#: Union of all parsed input events.
InputEvent = (
    KeyStateEvent
    | TouchTapEvent
    | TouchPressEvent
    | TouchFlickEvent
    | EncoderButtonEvent
    | EncoderRotateEvent
)


# ---------------------------------------------------------------------------
# Unit information (from Get Unit Information feature report 0x08)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UnitInfo:
    """Hardware information parsed from the ``Get Unit Information`` feature report.

    Attributes
    ----------
    rows : int
        Keypad matrix rows.
    cols : int
        Keypad matrix columns.
    key_width : int
        Key/button image width in pixels.
    key_height : int
        Key/button image height in pixels.
    lcd_width : int
        Full LCD width in pixels.
    lcd_height : int
        Full LCD height in pixels.
    image_bpp : int
        Image bits per pixel.
    color_scheme : int
        Image color scheme identifier.
    """

    rows: int
    cols: int
    key_width: int
    key_height: int
    lcd_width: int
    lcd_height: int
    image_bpp: int
    color_scheme: int


# ---------------------------------------------------------------------------
# Input report parsing
# ---------------------------------------------------------------------------


def parse_input_report(data: bytes) -> InputEvent | None:
    """Parse a raw HID input report into a typed event.

    Handles platform differences in ``hid_read_timeout`` return data:
    on macOS and Windows the Report ID byte (``0x01``) is included as
    the first byte, while on Linux (hidraw) it is stripped.  This
    function detects the presence of the Report ID and skips it
    automatically.

    Parameters
    ----------
    data : bytes
        Raw input report bytes (up to 512 bytes).

    Returns
    -------
    InputEvent or None
        A typed event, or ``None`` if the report is unrecognised or
        malformed (e.g. the declared ``payload_len`` exceeds the actual
        bytes available, or an encoder report has no content type byte).
    """
    if len(data) < 4:
        return None

    # On macOS/Windows hidapi includes the Report ID (0x01) as the
    # first byte.  On Linux (hidraw) it is stripped and data starts
    # with the command byte.  Detect and skip the Report ID.
    if data[0] == ReportId.INPUT:
        data = data[1:]
        if len(data) < 4:
            return None

    command = data[0]
    payload_len = struct.unpack_from("<H", data, 1)[0]
    payload = data[3:]

    # Defensive bounds check: a malformed device report (or fuzzed input)
    # may declare a payload length larger than the bytes actually present.
    # Reject such reports rather than silently truncating to avoid producing
    # empty event tuples that mask buggy firmware or USB corruption.
    if payload_len > len(payload):
        logger.debug(
            "Truncated HID report: declared %d, actual %d", payload_len, len(payload)
        )
        return None

    if command == InputCommand.KEY_STATE:
        states = tuple(b != 0 for b in payload[:payload_len])
        return KeyStateEvent(states=states)

    if command == InputCommand.TOUCH_SCREEN:
        if len(payload) < 6:
            return None
        content_type = payload[0]
        if content_type == TouchEventType.TAP:
            x, y = struct.unpack_from("<HH", payload, 2)
            return TouchTapEvent(x=x, y=y)
        if content_type == TouchEventType.PRESS:
            x, y = struct.unpack_from("<HH", payload, 2)
            return TouchPressEvent(x=x, y=y)
        if content_type == TouchEventType.FLICK:
            if len(payload) < 10:
                return None
            sx, sy, ex, ey = struct.unpack_from("<HHHH", payload, 2)
            return TouchFlickEvent(start_x=sx, start_y=sy, end_x=ex, end_y=ey)
        return None

    if command == InputCommand.ENCODER:
        if len(payload) < 2 or payload_len < 2:
            return None
        content_type = payload[0]
        encoder_data = payload[1:payload_len]
        if content_type == EncoderEventType.BUTTON:
            states = tuple(b != 0 for b in encoder_data)
            return EncoderButtonEvent(states=states)
        if content_type == EncoderEventType.ROTATE:
            ticks = tuple(
                struct.unpack_from("b", encoder_data, i)[0]
                for i in range(len(encoder_data))
            )
            return EncoderRotateEvent(ticks=ticks)
        return None

    return None


# ---------------------------------------------------------------------------
# Feature report parsing
# ---------------------------------------------------------------------------


def parse_unit_info(data: bytes) -> UnitInfo:
    """Parse a ``Get Unit Information`` feature report response.

    Parameters
    ----------
    data : bytes
        Raw feature report bytes (report ID 0x08).

    Returns
    -------
    UnitInfo
        Parsed hardware information.

    Raises
    ------
    ValueError
        If the data is too short to parse.
    """
    if len(data) < 0x0D:
        msg = f"Unit info report too short: {len(data)} bytes (need >= 13)"
        raise ValueError(msg)

    rows = data[1]
    cols = data[2]
    key_width, key_height = struct.unpack_from("<HH", data, 3)
    lcd_width, lcd_height = struct.unpack_from("<HH", data, 7)
    image_bpp = data[0x0B]
    color_scheme = data[0x0C]

    return UnitInfo(
        rows=rows,
        cols=cols,
        key_width=key_width,
        key_height=key_height,
        lcd_width=lcd_width,
        lcd_height=lcd_height,
        image_bpp=image_bpp,
        color_scheme=color_scheme,
    )


def parse_serial_number(data: bytes) -> str:
    """Parse a ``Get Unit Serial Number`` feature report response.

    Parameters
    ----------
    data : bytes
        Raw feature report bytes (report ID 0x06).

    Returns
    -------
    str
        The serial number string.
    """
    if len(data) < 3:
        return ""
    length = data[1]
    raw = data[2 : 2 + length]
    return raw.decode("ascii", errors="replace").rstrip("\x00")


def parse_firmware_version(data: bytes) -> str:
    """Parse a ``Get Firmware Version`` feature report response.

    Parameters
    ----------
    data : bytes
        Raw feature report bytes (report ID 0x04, 0x05, or 0x07).

    Returns
    -------
    str
        The firmware version string.
    """
    if len(data) < 14:
        return ""
    # Bytes 6..13 are the version string ASCII
    raw = data[6:14]
    return raw.decode("ascii", errors="replace").rstrip("\x00")


# ---------------------------------------------------------------------------
# Output report builders (image chunking)
# ---------------------------------------------------------------------------

# Header sizes for each output command
_KEY_IMAGE_HEADER = 8  # report_id(1) + cmd(1) + key_idx(1) + done(1) + size(2) + idx(2)
_FULL_SCREEN_HEADER = 8  # report_id(1) + cmd(1) + reserved(1) + done(1) + size(2) + idx(2)
_WINDOW_HEADER = 8  # same layout as full screen
_PARTIAL_WINDOW_HEADER = 16  # report_id + cmd + x + y + w + h + done + idx + size + reserved
_BACKGROUND_HEADER = 8  # report_id(1) + cmd(1) + bg_idx(1) + done(1) + chunk_idx(2) + size(2)


def _chunk_payload(
    payload: bytes, chunk_data_size: int
) -> list[tuple[int, bool, bytes]]:
    """Split a payload into indexed chunks.

    Parameters
    ----------
    payload : bytes
        The JPEG image data.
    chunk_data_size : int
        Maximum bytes of payload data per chunk.

    Returns
    -------
    list[tuple[int, bool, bytes]]
        List of ``(chunk_index, is_last, chunk_data)`` tuples.
    """
    chunks: list[tuple[int, bool, bytes]] = []
    offset = 0
    idx = 0
    while offset < len(payload):
        end = min(offset + chunk_data_size, len(payload))
        is_last = end >= len(payload)
        chunks.append((idx, is_last, payload[offset:end]))
        offset = end
        idx += 1
    if not chunks:
        # Empty payload: send one empty chunk with done flag
        chunks.append((0, True, b""))
    return chunks


def build_key_image_reports(key_index: int, jpeg_data: bytes) -> list[bytes]:
    """Build output reports for ``Update Key Image`` (command 0x07).

    Parameters
    ----------
    key_index : int
        Zero-based key index.
    jpeg_data : bytes
        JPEG-encoded image data (already rotated as needed).

    Returns
    -------
    list[bytes]
        List of 1024-byte output reports ready for ``hid_write``.
    """
    max_data = OUTPUT_REPORT_SIZE - _KEY_IMAGE_HEADER
    chunks = _chunk_payload(jpeg_data, max_data)
    reports: list[bytes] = []
    for chunk_idx, is_last, chunk_data in chunks:
        buf = bytearray(OUTPUT_REPORT_SIZE)
        buf[0] = ReportId.OUTPUT
        buf[1] = OutputCommand.UPDATE_KEY_IMAGE
        buf[2] = key_index
        buf[3] = 0x01 if is_last else 0x00
        struct.pack_into("<H", buf, 4, len(chunk_data))
        struct.pack_into("<H", buf, 6, chunk_idx)
        buf[8 : 8 + len(chunk_data)] = chunk_data
        reports.append(bytes(buf))
    return reports


def build_full_screen_reports(jpeg_data: bytes) -> list[bytes]:
    """Build output reports for ``Update Full Screen Image`` (command 0x08).

    Parameters
    ----------
    jpeg_data : bytes
        JPEG-encoded full-screen image data (already rotated as needed).

    Returns
    -------
    list[bytes]
        List of 1024-byte output reports ready for ``hid_write``.
    """
    max_data = OUTPUT_REPORT_SIZE - _FULL_SCREEN_HEADER
    chunks = _chunk_payload(jpeg_data, max_data)
    reports: list[bytes] = []
    for chunk_idx, is_last, chunk_data in chunks:
        buf = bytearray(OUTPUT_REPORT_SIZE)
        buf[0] = ReportId.OUTPUT
        buf[1] = OutputCommand.UPDATE_FULL_SCREEN
        buf[2] = 0x00  # reserved
        buf[3] = 0x01 if is_last else 0x00
        struct.pack_into("<H", buf, 4, len(chunk_data))
        struct.pack_into("<H", buf, 6, chunk_idx)
        buf[8 : 8 + len(chunk_data)] = chunk_data
        reports.append(bytes(buf))
    return reports


def build_window_reports(jpeg_data: bytes) -> list[bytes]:
    """Build output reports for ``Update Window Image`` (command 0x0B).

    Parameters
    ----------
    jpeg_data : bytes
        JPEG-encoded window image data (already rotated as needed).

    Returns
    -------
    list[bytes]
        List of 1024-byte output reports ready for ``hid_write``.
    """
    max_data = OUTPUT_REPORT_SIZE - _WINDOW_HEADER
    chunks = _chunk_payload(jpeg_data, max_data)
    reports: list[bytes] = []
    for chunk_idx, is_last, chunk_data in chunks:
        buf = bytearray(OUTPUT_REPORT_SIZE)
        buf[0] = ReportId.OUTPUT
        buf[1] = OutputCommand.UPDATE_WINDOW
        buf[2] = 0x00  # reserved
        buf[3] = 0x01 if is_last else 0x00
        struct.pack_into("<H", buf, 4, len(chunk_data))
        struct.pack_into("<H", buf, 6, chunk_idx)
        buf[8 : 8 + len(chunk_data)] = chunk_data
        reports.append(bytes(buf))
    return reports


def build_partial_window_reports(
    x: int, y: int, width: int, height: int, jpeg_data: bytes
) -> list[bytes]:
    """Build output reports for ``Update Partial Window Image`` (command 0x0C).

    Parameters
    ----------
    x : int
        X-coordinate of the region (logical, no rotation accounting).
    y : int
        Y-coordinate of the region.
    width : int
        Width of the region in pixels.
    height : int
        Height of the region in pixels.
    jpeg_data : bytes
        JPEG-encoded partial image data (already rotated as needed).

    Returns
    -------
    list[bytes]
        List of 1024-byte output reports ready for ``hid_write``.
    """
    max_data = OUTPUT_REPORT_SIZE - _PARTIAL_WINDOW_HEADER
    chunks = _chunk_payload(jpeg_data, max_data)
    reports: list[bytes] = []
    for chunk_idx, is_last, chunk_data in chunks:
        buf = bytearray(OUTPUT_REPORT_SIZE)
        buf[0] = ReportId.OUTPUT
        buf[1] = OutputCommand.UPDATE_PARTIAL_WINDOW
        struct.pack_into("<H", buf, 2, x)
        struct.pack_into("<H", buf, 4, y)
        struct.pack_into("<H", buf, 6, width)
        struct.pack_into("<H", buf, 8, height)
        buf[0x0A] = 0x01 if is_last else 0x00
        struct.pack_into("<H", buf, 0x0B, chunk_idx)
        struct.pack_into("<H", buf, 0x0D, len(chunk_data))
        buf[0x0F] = 0x00  # reserved
        buf[0x10 : 0x10 + len(chunk_data)] = chunk_data
        reports.append(bytes(buf))
    return reports


def build_background_reports(bg_index: int, jpeg_data: bytes) -> list[bytes]:
    """Build output reports for ``Update Background`` (command 0x0D).

    Classic and XL families only.

    Parameters
    ----------
    bg_index : int
        Background storage index.
    jpeg_data : bytes
        JPEG-encoded background image data (already rotated as needed).

    Returns
    -------
    list[bytes]
        List of 1024-byte output reports ready for ``hid_write``.

    Notes
    -----
    The ``Update Background`` command has chunk index and chunk contents
    size fields swapped compared to the other output commands.
    """
    max_data = OUTPUT_REPORT_SIZE - _BACKGROUND_HEADER
    chunks = _chunk_payload(jpeg_data, max_data)
    reports: list[bytes] = []
    for chunk_idx, is_last, chunk_data in chunks:
        buf = bytearray(OUTPUT_REPORT_SIZE)
        buf[0] = ReportId.OUTPUT
        buf[1] = OutputCommand.UPDATE_BACKGROUND
        buf[2] = bg_index
        buf[3] = 0x01 if is_last else 0x00
        # Note: chunk_index and chunk_size are swapped vs other commands
        struct.pack_into("<H", buf, 4, chunk_idx)
        struct.pack_into("<H", buf, 6, len(chunk_data))
        buf[8 : 8 + len(chunk_data)] = chunk_data
        reports.append(bytes(buf))
    return reports


# ---------------------------------------------------------------------------
# Feature report builders
# ---------------------------------------------------------------------------


def build_show_logo() -> bytes:
    """Build a ``Show Logo`` feature report.

    Returns
    -------
    bytes
        32-byte feature report.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.FEATURE_SET
    buf[1] = FeatureCommand.SHOW_LOGO
    return bytes(buf)


def build_fill_lcd_color(r: int, g: int, b: int) -> bytes:
    """Build a ``Fill LCD with Color`` feature report.

    Parameters
    ----------
    r : int
        Red component (0-255).
    g : int
        Green component (0-255).
    b : int
        Blue component (0-255).

    Returns
    -------
    bytes
        32-byte feature report.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.FEATURE_SET
    buf[1] = FeatureCommand.FILL_LCD_COLOR
    buf[2] = r
    buf[3] = g
    buf[4] = b
    return bytes(buf)


def build_fill_key_color(key_index: int, r: int, g: int, b: int) -> bytes:
    """Build a ``Fill Key with Color`` feature report.

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

    Returns
    -------
    bytes
        32-byte feature report.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.FEATURE_SET
    buf[1] = FeatureCommand.FILL_KEY_COLOR
    buf[2] = key_index
    buf[3] = r
    buf[4] = g
    buf[5] = b
    return bytes(buf)


def build_set_brightness(percent: int) -> bytes:
    """Build a ``Set Backlight Brightness`` feature report.

    Parameters
    ----------
    percent : int
        Brightness level from 0 to 100.

    Returns
    -------
    bytes
        32-byte feature report.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.FEATURE_SET
    buf[1] = FeatureCommand.SET_BRIGHTNESS
    buf[2] = max(0, min(100, percent))
    return bytes(buf)


def build_set_sleep_duration(seconds: int) -> bytes:
    """Build a ``Set Sleep Mode Duration`` feature report.

    Parameters
    ----------
    seconds : int
        Duration in seconds (0 = disabled).

    Returns
    -------
    bytes
        32-byte feature report.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.FEATURE_SET
    buf[1] = FeatureCommand.SET_SLEEP_DURATION
    struct.pack_into("<i", buf, 2, seconds)
    return bytes(buf)


def build_show_background(bg_index: int) -> bytes:
    """Build a ``Show Background by Index`` feature report.

    XL family only.

    Parameters
    ----------
    bg_index : int
        Background storage index.

    Returns
    -------
    bytes
        32-byte feature report.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.FEATURE_SET
    buf[1] = FeatureCommand.SHOW_BACKGROUND
    buf[2] = bg_index
    return bytes(buf)


def build_get_serial_number() -> bytes:
    """Build a ``Get Unit Serial Number`` feature report request.

    Returns
    -------
    bytes
        32-byte feature report with report ID 0x06.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.SERIAL_NUMBER
    return bytes(buf)


def build_get_unit_info() -> bytes:
    """Build a ``Get Unit Information`` feature report request.

    Returns
    -------
    bytes
        32-byte feature report with report ID 0x08.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.UNIT_INFO
    return bytes(buf)


def build_get_firmware_version(report_id: int = ReportId.FW_VERSION_AP2) -> bytes:
    """Build a ``Get Firmware Version`` feature report request.

    Parameters
    ----------
    report_id : int, default=ReportId.FW_VERSION_AP2
        Report ID for the desired firmware component.
        Use ``0x04`` (LD), ``0x05`` (AP2, primary), or ``0x07`` (AP1).

    Returns
    -------
    bytes
        32-byte feature report.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = report_id
    return bytes(buf)


def build_get_sleep_duration() -> bytes:
    """Build a ``Get Sleep Mode Duration`` feature report request.

    Returns
    -------
    bytes
        32-byte feature report with report ID 0x0A.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.SLEEP_DURATION
    return bytes(buf)
