"""Tests for ``deux.runtime.hid.protocol``.

Covers input report parsing, feature report parsing, output report builders,
chunking logic, and protocol constants.
"""

from __future__ import annotations

import struct

import pytest

from deux.runtime.hid.protocol import (
    FEATURE_REPORT_SIZE,
    OUTPUT_REPORT_SIZE,
    PID_ROTATION,
    SUPPORTED_PIDS,
    EncoderButtonEvent,
    EncoderEventType,
    EncoderRotateEvent,
    FeatureCommand,
    InputCommand,
    KeyStateEvent,
    OutputCommand,
    ReportId,
    TouchEventType,
    TouchFlickEvent,
    TouchPressEvent,
    TouchTapEvent,
    UnitInfo,
    _chunk_payload,
    build_background_reports,
    build_fill_key_color,
    build_fill_lcd_color,
    build_full_screen_reports,
    build_get_firmware_version,
    build_get_serial_number,
    build_get_sleep_duration,
    build_get_unit_info,
    build_key_image_reports,
    build_partial_window_reports,
    build_set_brightness,
    build_set_sleep_duration,
    build_show_background,
    build_show_logo,
    build_window_reports,
    parse_firmware_version,
    parse_input_report,
    parse_serial_number,
    parse_unit_info,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_input(command: int, payload: bytes, payload_len: int | None = None) -> bytes:
    """Build a raw input report from command byte and payload.

    Parameters
    ----------
    command : int
        Input command byte.
    payload : bytes
        Payload bytes following the 3-byte header.
    payload_len : int or None
        Override for the little-endian length field. Defaults to ``len(payload)``.

    Returns
    -------
    bytes
        Raw input report bytes.
    """
    if payload_len is None:
        payload_len = len(payload)
    header = struct.pack("<BH", command, payload_len)
    return header + payload


# ===========================================================================
# 1. Input parsing — parse_input_report
# ===========================================================================


class TestParseInputReportKeyState:
    """Tests for KeyStateEvent parsing."""

    def test_all_keys_released(self) -> None:
        """All-zero key states are parsed as all-False tuple."""
        data = _build_input(InputCommand.KEY_STATE, b"\x00\x00\x00", payload_len=3)
        evt = parse_input_report(data)
        assert isinstance(evt, KeyStateEvent)
        assert evt.states == (False, False, False)

    def test_some_keys_pressed(self) -> None:
        """Non-zero bytes are parsed as True."""
        data = _build_input(InputCommand.KEY_STATE, b"\x01\x00\x01", payload_len=3)
        evt = parse_input_report(data)
        assert isinstance(evt, KeyStateEvent)
        assert evt.states == (True, False, True)


class TestParseInputReportTouch:
    """Tests for touch screen event parsing."""

    def test_tap_event(self) -> None:
        """TouchTapEvent with correct x/y coordinates."""
        x, y = 200, 150
        payload = struct.pack("<BxHH", TouchEventType.TAP, x, y)
        data = _build_input(InputCommand.TOUCH_SCREEN, payload)
        evt = parse_input_report(data)
        assert isinstance(evt, TouchTapEvent)
        assert evt.x == x
        assert evt.y == y

    def test_press_event(self) -> None:
        """TouchPressEvent with correct x/y coordinates."""
        x, y = 300, 50
        payload = struct.pack("<BxHH", TouchEventType.PRESS, x, y)
        data = _build_input(InputCommand.TOUCH_SCREEN, payload)
        evt = parse_input_report(data)
        assert isinstance(evt, TouchPressEvent)
        assert evt.x == x
        assert evt.y == y

    def test_flick_event(self) -> None:
        """TouchFlickEvent with correct start/end coordinates."""
        sx, sy, ex, ey = 10, 20, 400, 100
        payload = struct.pack("<BxHHHH", TouchEventType.FLICK, sx, sy, ex, ey)
        data = _build_input(InputCommand.TOUCH_SCREEN, payload)
        evt = parse_input_report(data)
        assert isinstance(evt, TouchFlickEvent)
        assert (evt.start_x, evt.start_y) == (sx, sy)
        assert (evt.end_x, evt.end_y) == (ex, ey)

    def test_too_short_payload_returns_none(self) -> None:
        """Touch report with fewer than 6 payload bytes returns None."""
        data = _build_input(InputCommand.TOUCH_SCREEN, b"\x01\x00")
        assert parse_input_report(data) is None

    def test_flick_too_short_returns_none(self) -> None:
        """Flick with fewer than 10 payload bytes returns None."""
        payload = struct.pack("<BxHH", TouchEventType.FLICK, 10, 20)
        data = _build_input(InputCommand.TOUCH_SCREEN, payload)
        assert parse_input_report(data) is None

    def test_unknown_touch_type_returns_none(self) -> None:
        """Unknown touch content_type returns None."""
        payload = struct.pack("<BxHH", 0xFF, 0, 0)
        data = _build_input(InputCommand.TOUCH_SCREEN, payload)
        assert parse_input_report(data) is None


class TestParseInputReportEncoder:
    """Tests for encoder event parsing."""

    def test_button_event(self) -> None:
        """EncoderButtonEvent with pressed states."""
        payload = bytes([EncoderEventType.BUTTON, 0x01, 0x00, 0x01])
        data = _build_input(InputCommand.ENCODER, payload)
        evt = parse_input_report(data)
        assert isinstance(evt, EncoderButtonEvent)
        assert evt.states == (True, False, True)

    def test_rotate_event(self) -> None:
        """EncoderRotateEvent with signed ticks."""
        # +2, -1 as signed bytes
        payload = bytes([EncoderEventType.ROTATE]) + struct.pack("bb", 2, -1)
        data = _build_input(InputCommand.ENCODER, payload)
        evt = parse_input_report(data)
        assert isinstance(evt, EncoderRotateEvent)
        assert evt.ticks == (2, -1)

    def test_too_short_payload_returns_none(self) -> None:
        """Encoder with fewer than 2 payload bytes returns None."""
        data = _build_input(InputCommand.ENCODER, b"\x00")
        assert parse_input_report(data) is None

    def test_unknown_encoder_type_returns_none(self) -> None:
        """Unknown encoder content_type returns None."""
        payload = bytes([0xFF, 0x00, 0x00])
        data = _build_input(InputCommand.ENCODER, payload)
        assert parse_input_report(data) is None


class TestParseInputReportEdgeCases:
    """Edge-case tests for parse_input_report."""

    def test_unknown_command_returns_none(self) -> None:
        """Unrecognised command byte returns None."""
        data = _build_input(0xFF, b"\x00\x00\x00")
        assert parse_input_report(data) is None

    def test_too_short_data_returns_none(self) -> None:
        """Data shorter than 4 bytes returns None."""
        assert parse_input_report(b"\x00\x00") is None
        assert parse_input_report(b"") is None


class TestParseInputReportWithReportId:
    """Tests that parse_input_report handles Report ID prefix.

    On macOS and Windows, ``hid_read_timeout`` returns data with the
    Report ID (``0x01``) as the first byte.  On Linux (hidraw) the
    Report ID is stripped.  The parser must handle both.
    """

    def test_key_state_with_report_id(self) -> None:
        """KeyStateEvent parsed correctly when Report ID 0x01 is present."""
        inner = _build_input(InputCommand.KEY_STATE, b"\x01\x00\x01", payload_len=3)
        data = bytes([ReportId.INPUT]) + inner
        evt = parse_input_report(data)
        assert isinstance(evt, KeyStateEvent)
        assert evt.states == (True, False, True)

    def test_touch_tap_with_report_id(self) -> None:
        """TouchTapEvent parsed correctly when Report ID 0x01 is present."""
        payload = struct.pack("<BxHH", TouchEventType.TAP, 300, 75)
        inner = _build_input(InputCommand.TOUCH_SCREEN, payload)
        data = bytes([ReportId.INPUT]) + inner
        evt = parse_input_report(data)
        assert isinstance(evt, TouchTapEvent)
        assert evt.x == 300
        assert evt.y == 75

    def test_encoder_button_with_report_id(self) -> None:
        """EncoderButtonEvent parsed correctly when Report ID 0x01 is present."""
        enc_payload = bytes([EncoderEventType.BUTTON, 0x00, 0x01, 0x00, 0x00])
        inner = _build_input(InputCommand.ENCODER, enc_payload)
        data = bytes([ReportId.INPUT]) + inner
        evt = parse_input_report(data)
        assert isinstance(evt, EncoderButtonEvent)
        assert evt.states[1] is True

    def test_encoder_rotate_with_report_id(self) -> None:
        """EncoderRotateEvent parsed correctly when Report ID 0x01 is present."""
        ticks = struct.pack("bbbb", 0, 3, -2, 0)
        enc_payload = bytes([EncoderEventType.ROTATE]) + ticks
        inner = _build_input(InputCommand.ENCODER, enc_payload)
        data = bytes([ReportId.INPUT]) + inner
        evt = parse_input_report(data)
        assert isinstance(evt, EncoderRotateEvent)
        assert evt.ticks[1] == 3
        assert evt.ticks[2] == -2

    def test_report_id_only_too_short(self) -> None:
        """Report ID + too few bytes returns None."""
        assert parse_input_report(bytes([ReportId.INPUT, 0x00, 0x00])) is None


# ===========================================================================
# 2. Feature report parsing
# ===========================================================================


class TestParseUnitInfo:
    """Tests for parse_unit_info."""

    def test_valid_data(self) -> None:
        """Parse a well-formed unit info report."""
        buf = bytearray(16)
        buf[0] = ReportId.UNIT_INFO
        buf[1] = 2  # rows
        buf[2] = 4  # cols
        struct.pack_into("<HH", buf, 3, 72, 72)  # key w/h
        struct.pack_into("<HH", buf, 7, 800, 100)  # lcd w/h
        buf[0x0B] = 24  # bpp
        buf[0x0C] = 1  # color_scheme
        info = parse_unit_info(bytes(buf))
        assert info == UnitInfo(
            rows=2, cols=4, key_width=72, key_height=72,
            lcd_width=800, lcd_height=100, image_bpp=24, color_scheme=1,
        )

    def test_too_short_raises(self) -> None:
        """Data shorter than 13 bytes raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            parse_unit_info(b"\x08" * 12)


class TestParseSerialNumber:
    """Tests for parse_serial_number."""

    def test_valid(self) -> None:
        """Parse a serial number string."""
        serial = b"AL12H1A00123"
        buf = bytearray(FEATURE_REPORT_SIZE)
        buf[0] = ReportId.SERIAL_NUMBER
        buf[1] = len(serial)
        buf[2 : 2 + len(serial)] = serial
        assert parse_serial_number(bytes(buf)) == "AL12H1A00123"

    def test_short_returns_empty(self) -> None:
        """Short data returns empty string."""
        assert parse_serial_number(b"\x06") == ""
        assert parse_serial_number(b"") == ""


class TestParseFirmwareVersion:
    """Tests for parse_firmware_version."""

    def test_valid(self) -> None:
        """Parse a firmware version string from bytes 6..13."""
        buf = bytearray(FEATURE_REPORT_SIZE)
        buf[0] = ReportId.FW_VERSION_AP2
        buf[6:14] = b"1.02.003"
        assert parse_firmware_version(bytes(buf)) == "1.02.003"

    def test_short_returns_empty(self) -> None:
        """Data shorter than 14 bytes returns empty string."""
        assert parse_firmware_version(b"\x05" * 13) == ""


# ===========================================================================
# 3. Report builders
# ===========================================================================


class TestBuildKeyImageReports:
    """Tests for build_key_image_reports."""

    def test_single_chunk(self) -> None:
        """Small image fits in one report."""
        data = b"\xff" * 100
        reports = build_key_image_reports(3, data)
        assert len(reports) == 1
        r = reports[0]
        assert len(r) == OUTPUT_REPORT_SIZE
        assert r[0] == ReportId.OUTPUT
        assert r[1] == OutputCommand.UPDATE_KEY_IMAGE
        assert r[2] == 3  # key_index
        assert r[3] == 0x01  # done
        assert struct.unpack_from("<H", r, 4)[0] == 100  # size
        assert struct.unpack_from("<H", r, 6)[0] == 0  # chunk_idx
        assert r[8 : 8 + 100] == data

    def test_multi_chunk(self) -> None:
        """Large image spans multiple reports."""
        chunk_cap = OUTPUT_REPORT_SIZE - 8
        data = bytes(range(256)) * 10  # 2560 bytes
        reports = build_key_image_reports(0, data)
        assert len(reports) >= 2
        # Last report has done flag
        assert reports[-1][3] == 0x01
        # Non-last reports do not
        for r in reports[:-1]:
            assert r[3] == 0x00

    def test_empty_data(self) -> None:
        """Empty image data produces one report with done flag."""
        reports = build_key_image_reports(0, b"")
        assert len(reports) == 1
        assert reports[0][3] == 0x01
        assert struct.unpack_from("<H", reports[0], 4)[0] == 0


class TestBuildFullScreenReports:
    """Tests for build_full_screen_reports."""

    def test_single_chunk(self) -> None:
        """Verify header fields for a single-chunk full screen report."""
        data = b"\xAB" * 50
        reports = build_full_screen_reports(data)
        r = reports[0]
        assert r[0] == ReportId.OUTPUT
        assert r[1] == OutputCommand.UPDATE_FULL_SCREEN
        assert r[2] == 0x00  # reserved
        assert r[3] == 0x01  # done


class TestBuildWindowReports:
    """Tests for build_window_reports."""

    def test_single_chunk(self) -> None:
        """Verify header fields for a single-chunk window report."""
        data = b"\xCD" * 50
        reports = build_window_reports(data)
        r = reports[0]
        assert r[1] == OutputCommand.UPDATE_WINDOW
        assert r[3] == 0x01


class TestBuildPartialWindowReports:
    """Tests for build_partial_window_reports."""

    def test_offsets(self) -> None:
        """Verify x/y/w/h are packed at correct offsets."""
        reports = build_partial_window_reports(10, 20, 100, 50, b"\x00" * 10)
        r = reports[0]
        assert r[0] == ReportId.OUTPUT
        assert r[1] == OutputCommand.UPDATE_PARTIAL_WINDOW
        assert struct.unpack_from("<H", r, 2)[0] == 10   # x
        assert struct.unpack_from("<H", r, 4)[0] == 20   # y
        assert struct.unpack_from("<H", r, 6)[0] == 100  # w
        assert struct.unpack_from("<H", r, 8)[0] == 50   # h
        assert r[0x0A] == 0x01  # done
        assert struct.unpack_from("<H", r, 0x0B)[0] == 0  # chunk_idx
        assert struct.unpack_from("<H", r, 0x0D)[0] == 10  # size


class TestBuildBackgroundReports:
    """Tests for build_background_reports."""

    def test_swapped_fields(self) -> None:
        """Verify chunk_idx and size fields are swapped vs other commands."""
        data = b"\xEE" * 30
        reports = build_background_reports(2, data)
        r = reports[0]
        assert r[1] == OutputCommand.UPDATE_BACKGROUND
        assert r[2] == 2  # bg_index
        assert r[3] == 0x01  # done
        # Swapped: offset 4 = chunk_idx, offset 6 = size
        assert struct.unpack_from("<H", r, 4)[0] == 0   # chunk_idx
        assert struct.unpack_from("<H", r, 6)[0] == 30  # size


class TestFeatureReportBuilders:
    """Tests for feature report builder functions."""

    def test_show_logo(self) -> None:
        """build_show_logo has correct report_id and command."""
        r = build_show_logo()
        assert len(r) == FEATURE_REPORT_SIZE
        assert r[0] == ReportId.FEATURE_SET
        assert r[1] == FeatureCommand.SHOW_LOGO

    def test_fill_lcd_color(self) -> None:
        """build_fill_lcd_color places r/g/b at offsets 2/3/4."""
        r = build_fill_lcd_color(10, 20, 30)
        assert r[0] == ReportId.FEATURE_SET
        assert r[1] == FeatureCommand.FILL_LCD_COLOR
        assert (r[2], r[3], r[4]) == (10, 20, 30)

    def test_fill_key_color(self) -> None:
        """build_fill_key_color places key_index and r/g/b correctly."""
        r = build_fill_key_color(5, 100, 200, 50)
        assert r[1] == FeatureCommand.FILL_KEY_COLOR
        assert r[2] == 5
        assert (r[3], r[4], r[5]) == (100, 200, 50)

    def test_set_brightness_clamping(self) -> None:
        """build_set_brightness clamps values to 0-100."""
        assert build_set_brightness(50)[2] == 50
        assert build_set_brightness(-10)[2] == 0
        assert build_set_brightness(200)[2] == 100

    def test_set_sleep_duration(self) -> None:
        """build_set_sleep_duration packs a signed int at offset 2."""
        r = build_set_sleep_duration(300)
        assert struct.unpack_from("<i", r, 2)[0] == 300
        r2 = build_set_sleep_duration(0)
        assert struct.unpack_from("<i", r2, 2)[0] == 0

    def test_show_background(self) -> None:
        """build_show_background places bg_index at offset 2."""
        r = build_show_background(7)
        assert r[1] == FeatureCommand.SHOW_BACKGROUND
        assert r[2] == 7

    def test_get_serial_number(self) -> None:
        """build_get_serial_number uses report ID 0x06."""
        r = build_get_serial_number()
        assert len(r) == FEATURE_REPORT_SIZE
        assert r[0] == ReportId.SERIAL_NUMBER

    def test_get_unit_info(self) -> None:
        """build_get_unit_info uses report ID 0x08."""
        r = build_get_unit_info()
        assert r[0] == ReportId.UNIT_INFO

    def test_get_firmware_version_default(self) -> None:
        """build_get_firmware_version defaults to AP2 report ID."""
        r = build_get_firmware_version()
        assert r[0] == ReportId.FW_VERSION_AP2

    def test_get_firmware_version_custom(self) -> None:
        """build_get_firmware_version accepts custom report ID."""
        r = build_get_firmware_version(ReportId.FW_VERSION_LD)
        assert r[0] == ReportId.FW_VERSION_LD

    def test_get_sleep_duration(self) -> None:
        """build_get_sleep_duration uses report ID 0x0A."""
        r = build_get_sleep_duration()
        assert r[0] == ReportId.SLEEP_DURATION


# ===========================================================================
# 4. Chunking
# ===========================================================================


class TestChunkPayload:
    """Tests for _chunk_payload."""

    def test_small_data_one_chunk(self) -> None:
        """Data smaller than chunk size fits in one chunk."""
        chunks = _chunk_payload(b"\x00" * 10, 100)
        assert len(chunks) == 1
        idx, done, data = chunks[0]
        assert idx == 0
        assert done is True
        assert len(data) == 10

    def test_large_data_splits(self) -> None:
        """Data larger than chunk size splits into multiple chunks."""
        chunks = _chunk_payload(b"\x00" * 250, 100)
        assert len(chunks) == 3
        assert chunks[0][0] == 0
        assert chunks[0][1] is False
        assert len(chunks[0][2]) == 100
        assert chunks[1][0] == 1
        assert chunks[1][1] is False
        assert len(chunks[1][2]) == 100
        assert chunks[2][0] == 2
        assert chunks[2][1] is True
        assert len(chunks[2][2]) == 50

    def test_empty_data(self) -> None:
        """Empty payload returns one empty chunk with done=True."""
        chunks = _chunk_payload(b"", 100)
        assert len(chunks) == 1
        assert chunks[0] == (0, True, b"")


# ===========================================================================
# 5. Constants
# ===========================================================================


class TestConstants:
    """Verify protocol constants consistency."""

    def test_supported_pids_matches_rotation_keys(self) -> None:
        """SUPPORTED_PIDS is exactly the keys of PID_ROTATION."""
        assert SUPPORTED_PIDS == frozenset(PID_ROTATION.keys())
