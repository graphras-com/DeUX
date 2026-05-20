"""Tests for ``deux.runtime.hid.device.HidDevice``.

All ``hid_*`` ctypes functions are mocked so no real hardware is needed.
"""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, call, patch

import pytest

from deux.runtime.hid._ctypes_hidapi import HidApiError, HidDeviceInfo
from deux.runtime.hid.device import HidDevice
from deux.runtime.hid.protocol import (
    FEATURE_REPORT_SIZE,
    ImageRotation,
    KeyStateEvent,
    ReportId,
    UnitInfo,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MODULE = "deux.runtime.hid.device"

ELGATO_VID = 0x0FD9


def _make_info(
    pid: int = 0x0084,
    serial: str = "AB123",
    path: bytes = b"/dev/hid0",
) -> HidDeviceInfo:
    """Build a ``HidDeviceInfo`` for testing.

    Parameters
    ----------
    pid : int
        USB product ID.
    serial : str
        Device serial number.
    path : bytes
        OS device path.

    Returns
    -------
    HidDeviceInfo
        A populated info object.
    """
    return HidDeviceInfo(
        path=path,
        vendor_id=ELGATO_VID,
        product_id=pid,
        serial_number=serial,
        product_string="Stream Deck",
    )


def _make_unit_info_report(
    rows: int = 2,
    cols: int = 4,
    key_w: int = 120,
    key_h: int = 120,
    lcd_w: int = 800,
    lcd_h: int = 480,
    bpp: int = 24,
    color_scheme: int = 0,
) -> bytes:
    """Build a raw unit-info feature report response.

    Parameters
    ----------
    rows : int
        Keypad matrix rows.
    cols : int
        Keypad matrix columns.
    key_w : int
        Key image width in pixels.
    key_h : int
        Key image height in pixels.
    lcd_w : int
        Full LCD width.
    lcd_h : int
        Full LCD height.
    bpp : int
        Bits per pixel.
    color_scheme : int
        Colour scheme identifier.

    Returns
    -------
    bytes
        At least 13 bytes matching the unit-info format.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.UNIT_INFO
    buf[1] = rows
    buf[2] = cols
    struct.pack_into("<HH", buf, 3, key_w, key_h)
    struct.pack_into("<HH", buf, 7, lcd_w, lcd_h)
    buf[0x0B] = bpp
    buf[0x0C] = color_scheme
    return bytes(buf)


def _make_serial_report(serial: str = "CL123456789") -> bytes:
    """Build a raw serial-number feature report response.

    Parameters
    ----------
    serial : str
        ASCII serial number.

    Returns
    -------
    bytes
        Feature report bytes.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.SERIAL_NUMBER
    encoded = serial.encode("ascii")
    buf[1] = len(encoded)
    buf[2 : 2 + len(encoded)] = encoded
    return bytes(buf)


def _make_firmware_report(version: str = "1.02.003") -> bytes:
    """Build a raw firmware-version feature report response.

    Parameters
    ----------
    version : str
        Version string (up to 8 ASCII chars).

    Returns
    -------
    bytes
        Feature report bytes.
    """
    buf = bytearray(FEATURE_REPORT_SIZE)
    buf[0] = ReportId.FW_VERSION_AP2
    encoded = version.encode("ascii")[:8]
    buf[6 : 6 + len(encoded)] = encoded
    return bytes(buf)


def _feature_report_side_effect(
    unit: bytes | None = None,
    serial: bytes | None = None,
    firmware: bytes | None = None,
):
    """Return a side-effect function for ``hid_get_feature_report``.

    Parameters
    ----------
    unit : bytes or None
        Unit-info report bytes, or ``None`` to raise.
    serial : bytes or None
        Serial report bytes, or ``None`` to raise.
    firmware : bytes or None
        Firmware report bytes, or ``None`` to raise.

    Returns
    -------
    callable
        Side-effect for the mock.
    """
    mapping: dict[int, bytes | None] = {
        ReportId.UNIT_INFO: unit,
        ReportId.SERIAL_NUMBER: serial,
        ReportId.FW_VERSION_AP2: firmware,
    }

    def _side_effect(_handle: int, report_id: int, _size: int) -> bytes:
        val = mapping.get(report_id)
        if val is None:
            raise HidApiError(f"no report {report_id}")
        return val

    return _side_effect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hid_mocks():
    """Patch all ``hid_*`` functions used by :mod:`deux.runtime.hid.device`.

    Yields
    ------
    dict[str, MagicMock]
        Mapping of function name to its mock.
    """
    names = [
        "hid_open",
        "hid_close",
        "hid_get_feature_report",
        "hid_read_timeout",
        "hid_write",
        "hid_send_feature_report",
    ]
    patchers = {n: patch(f"{_MODULE}.{n}") for n in names}
    mocks = {n: p.start() for n, p in patchers.items()}
    yield mocks
    for p in patchers.values():
        p.stop()


@pytest.fixture
def open_device(hid_mocks):
    """Return an opened ``HidDevice`` (Plus, pid=0x0084) with standard mocks.

    Returns
    -------
    tuple[HidDevice, dict[str, MagicMock]]
        The device and mock dictionary.
    """
    hid_mocks["hid_open"].return_value = 42
    hid_mocks["hid_get_feature_report"].side_effect = _feature_report_side_effect(
        unit=_make_unit_info_report(),
        serial=_make_serial_report(),
        firmware=_make_firmware_report(),
    )
    info = _make_info(pid=0x0084)
    dev = HidDevice(info)
    dev.open()
    return dev, hid_mocks


# ---------------------------------------------------------------------------
# 1. Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    """Verify HidDevice.__init__ sets attributes from HidDeviceInfo."""

    @pytest.mark.parametrize(
        ("pid", "expected_family", "expected_rotation"),
        [
            (0x0084, "Stream Deck +", ImageRotation.NONE),
            (0x006D, "Stream Deck Classic", ImageRotation.CW_180),
            (0x00C6, "Stream Deck + XL", ImageRotation.CCW_90),
            (0x006C, "Stream Deck XL", ImageRotation.CW_180),
            (0x009A, "Stream Deck Neo", ImageRotation.CW_180),
        ],
    )
    def test_construction_from_pid(self, pid, expected_family, expected_rotation):
        """Construction sets path, IDs, family, rotation from PID."""
        info = _make_info(pid=pid, serial="S1", path=b"/dev/x")
        dev = HidDevice(info)

        assert dev.path == b"/dev/x"
        assert dev.vendor_id == ELGATO_VID
        assert dev.product_id == pid
        assert dev.family == expected_family
        assert dev.rotation == expected_rotation
        assert dev.serial_number == "S1"
        assert not dev.is_open

    def test_unknown_pid_defaults(self):
        """Unknown PID gets 'Unknown' family and NONE rotation."""
        info = _make_info(pid=0xFFFF)
        dev = HidDevice(info)

        assert dev.family == "Unknown"
        assert dev.rotation == ImageRotation.NONE


# ---------------------------------------------------------------------------
# 2. open()
# ---------------------------------------------------------------------------


class TestOpen:
    """Verify open() reads unit info, serial, firmware."""

    def test_open_populates_properties(self, open_device):
        """After open(), properties reflect parsed reports."""
        dev, _ = open_device

        assert dev.is_open
        assert dev.unit_info is not None
        assert dev.unit_info.rows == 2
        assert dev.unit_info.cols == 4
        assert dev.serial_number == "AB123"  # from enumeration, not overwritten
        assert dev.firmware_version == "1.02.003"

    def test_open_calls_hid_open(self, open_device):
        """open() invokes hid_open with the device path."""
        dev, mocks = open_device
        mocks["hid_open"].assert_called_once_with(b"/dev/hid0")

    def test_open_reads_serial_when_empty(self, hid_mocks):
        """If enumeration serial is empty, open() reads it from device."""
        hid_mocks["hid_open"].return_value = 99
        hid_mocks["hid_get_feature_report"].side_effect = _feature_report_side_effect(
            unit=_make_unit_info_report(),
            serial=_make_serial_report("FROM_DEV"),
            firmware=_make_firmware_report(),
        )
        info = _make_info(pid=0x0084, serial="")
        dev = HidDevice(info)
        dev.open()

        assert dev.serial_number == "FROM_DEV"

    def test_open_unit_info_failure_is_none(self, hid_mocks):
        """If unit-info read fails, unit_info is None."""
        hid_mocks["hid_open"].return_value = 1
        hid_mocks["hid_get_feature_report"].side_effect = _feature_report_side_effect(
            unit=None,
            serial=_make_serial_report(),
            firmware=_make_firmware_report(),
        )
        info = _make_info(pid=0x0084, serial="S")
        dev = HidDevice(info)
        dev.open()

        assert dev.unit_info is None


# ---------------------------------------------------------------------------
# 3. close()
# ---------------------------------------------------------------------------


class TestClose:
    """Verify close() releases the HID handle."""

    def test_close_calls_hid_close(self, open_device):
        """close() invokes hid_close and clears is_open."""
        dev, mocks = open_device
        dev.close()

        mocks["hid_close"].assert_called_once_with(42)
        assert not dev.is_open

    def test_close_when_not_open_is_noop(self, hid_mocks):
        """close() on an unopened device does nothing."""
        dev = HidDevice(_make_info())
        dev.close()

        hid_mocks["hid_close"].assert_not_called()


# ---------------------------------------------------------------------------
# 4. is_open
# ---------------------------------------------------------------------------


class TestIsOpen:
    """Verify is_open reflects handle state."""

    def test_false_initially(self):
        """is_open is False before open()."""
        dev = HidDevice(_make_info())
        assert not dev.is_open

    def test_true_after_open(self, open_device):
        """is_open is True after open()."""
        dev, _ = open_device
        assert dev.is_open

    def test_false_after_close(self, open_device):
        """is_open is False after close()."""
        dev, _ = open_device
        dev.close()
        assert not dev.is_open


# ---------------------------------------------------------------------------
# 5. Properties with/without unit_info
# ---------------------------------------------------------------------------


class TestUnitInfoProperties:
    """Verify key_count, key_layout, key_size, lcd_size with and without unit_info."""

    def test_with_unit_info(self, open_device):
        """Properties return correct values when unit_info is available."""
        dev, _ = open_device

        assert dev.key_count == 8  # 2 * 4
        assert dev.key_layout == (4, 2)  # (cols, rows)
        assert dev.key_size == (120, 120)
        assert dev.lcd_size == (800, 480)

    def test_without_unit_info(self):
        """Properties return zero defaults when unit_info is None."""
        dev = HidDevice(_make_info())

        assert dev.key_count == 0
        assert dev.key_layout == (0, 0)
        assert dev.key_size == (0, 0)
        assert dev.lcd_size == (0, 0)


# ---------------------------------------------------------------------------
# 6. PID-based properties
# ---------------------------------------------------------------------------


class TestPidProperties:
    """Verify window, touch, encoder, sensor properties per PID."""

    @pytest.mark.parametrize(
        ("pid", "has_window", "window_size", "has_touch", "has_enc", "enc_count", "sensors"),
        [
            (0x0084, True, (800, 100), True, True, 4, 0),
            (0x00C6, True, (1200, 100), True, True, 6, 0),
            (0x009A, True, (248, 58), False, False, 0, 2),
            (0x006D, False, (0, 0), False, False, 0, 0),
            (0x006C, False, (0, 0), False, False, 0, 0),
        ],
    )
    def test_pid_properties(
        self, pid, has_window, window_size, has_touch, has_enc, enc_count, sensors
    ):
        """PID-based properties match the hardware tables."""
        dev = HidDevice(_make_info(pid=pid))

        assert dev.has_window is has_window
        assert dev.window_size == window_size
        assert dev.has_touch is has_touch
        assert dev.has_encoders is has_enc
        assert dev.encoder_count == enc_count
        assert dev.sensor_count == sensors


# ---------------------------------------------------------------------------
# 7. read_input
# ---------------------------------------------------------------------------


class TestReadInput:
    """Verify read_input polling and parsing."""

    def test_returns_none_on_timeout(self, open_device):
        """read_input returns None when hid_read_timeout returns None."""
        dev, mocks = open_device
        mocks["hid_read_timeout"].return_value = None

        assert dev.read_input(100) is None

    def test_returns_parsed_event(self, open_device):
        """read_input returns a parsed InputEvent on data."""
        dev, mocks = open_device
        # Simulate a key-state report: command=0x00, payload_len=4, 4 key bytes
        report = struct.pack("<BH", 0x00, 4) + bytes([1, 0, 1, 0])
        mocks["hid_read_timeout"].return_value = report

        event = dev.read_input()
        assert isinstance(event, KeyStateEvent)
        assert event.states == (True, False, True, False)


# ---------------------------------------------------------------------------
# 8. Image methods
# ---------------------------------------------------------------------------


class TestImageMethods:
    """Verify image upload methods call hid_write."""

    def test_set_key_image(self, open_device):
        """set_key_image writes reports via hid_write."""
        dev, mocks = open_device
        dev.set_key_image(0, b"\xff\xd8JPEG")

        assert mocks["hid_write"].call_count >= 1

    def test_set_full_screen_image(self, open_device):
        """set_full_screen_image writes reports via hid_write."""
        dev, mocks = open_device
        dev.set_full_screen_image(b"\xff\xd8JPEG")

        assert mocks["hid_write"].call_count >= 1

    def test_set_window_image(self, open_device):
        """set_window_image writes reports via hid_write."""
        dev, mocks = open_device
        dev.set_window_image(b"\xff\xd8JPEG")

        assert mocks["hid_write"].call_count >= 1

    def test_set_partial_window_image(self, open_device):
        """set_partial_window_image writes reports via hid_write."""
        dev, mocks = open_device
        dev.set_partial_window_image(0, 0, 200, 100, b"\xff\xd8JPEG")

        assert mocks["hid_write"].call_count >= 1

    def test_hid_write_receives_handle(self, open_device):
        """hid_write is called with the device handle."""
        dev, mocks = open_device
        dev.set_key_image(0, b"\xff\xd8JPEG")

        first_call = mocks["hid_write"].call_args_list[0]
        assert first_call[0][0] == 42  # handle


# ---------------------------------------------------------------------------
# 9. Feature methods
# ---------------------------------------------------------------------------


class TestFeatureMethods:
    """Verify feature report methods call hid_send_feature_report."""

    def test_set_brightness(self, open_device):
        """set_brightness sends a feature report."""
        dev, mocks = open_device
        dev.set_brightness(75)

        mocks["hid_send_feature_report"].assert_called_once()
        args = mocks["hid_send_feature_report"].call_args[0]
        assert args[0] == 42  # handle

    def test_show_logo(self, open_device):
        """show_logo sends a feature report."""
        dev, mocks = open_device
        dev.show_logo()

        mocks["hid_send_feature_report"].assert_called_once()

    def test_fill_lcd_color(self, open_device):
        """fill_lcd_color sends a feature report."""
        dev, mocks = open_device
        dev.fill_lcd_color(255, 0, 128)

        mocks["hid_send_feature_report"].assert_called_once()

    def test_fill_key_color(self, open_device):
        """fill_key_color sends a feature report."""
        dev, mocks = open_device
        dev.fill_key_color(3, 10, 20, 30)

        mocks["hid_send_feature_report"].assert_called_once()

    def test_set_sleep_duration(self, open_device):
        """set_sleep_duration sends a feature report."""
        dev, mocks = open_device
        dev.set_sleep_duration(300)

        mocks["hid_send_feature_report"].assert_called_once()


# ---------------------------------------------------------------------------
# 10. _ensure_open
# ---------------------------------------------------------------------------


class TestEnsureOpen:
    """Verify _ensure_open raises when device is not open."""

    def test_raises_when_not_open(self):
        """_ensure_open raises HidApiError on closed device."""
        dev = HidDevice(_make_info())

        with pytest.raises(HidApiError, match="not open"):
            dev._ensure_open()

    def test_returns_handle_when_open(self, open_device):
        """_ensure_open returns the handle when open."""
        dev, _ = open_device
        assert dev._ensure_open() == 42

    def test_read_input_raises_when_not_open(self):
        """read_input raises via _ensure_open on closed device."""
        dev = HidDevice(_make_info())

        with pytest.raises(HidApiError):
            dev.read_input()

    def test_set_brightness_raises_when_not_open(self):
        """set_brightness raises via _ensure_open on closed device."""
        dev = HidDevice(_make_info())

        with pytest.raises(HidApiError):
            dev.set_brightness(50)


# ---------------------------------------------------------------------------
# 11. __repr__
# ---------------------------------------------------------------------------


class TestRepr:
    """Verify __repr__ output."""

    def test_repr_closed(self):
        """repr shows family, PID, serial, and 'closed' state."""
        dev = HidDevice(_make_info(pid=0x0084, serial="XY99"))
        result = repr(dev)

        assert "Stream Deck +" in result
        assert "0x0084" in result
        assert "XY99" in result
        assert "closed" in result

    def test_repr_open(self, open_device):
        """repr shows 'open' state after open()."""
        dev, _ = open_device
        result = repr(dev)

        assert "open" in result
