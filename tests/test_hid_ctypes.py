"""Tests for ``deux.runtime.hid._ctypes_hidapi``.

Validates the ctypes-based hidapi bindings using mocks, since the real
``libhidapi`` shared library is not available in the test environment.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deux.runtime.hid._ctypes_hidapi import (
    HidApiError,
    HidDeviceInfo,
)

# ---------------------------------------------------------------------------
# HidApiError
# ---------------------------------------------------------------------------


class TestHidApiError:
    """Tests for :class:`HidApiError`."""

    def test_is_oserror_subclass(self) -> None:
        """``HidApiError`` is a subclass of :class:`OSError`."""
        assert issubclass(HidApiError, OSError)

    def test_can_be_raised_and_caught(self) -> None:
        """``HidApiError`` can be raised and caught as ``OSError``."""
        with pytest.raises(OSError):
            raise HidApiError("test")


# ---------------------------------------------------------------------------
# HidDeviceInfo
# ---------------------------------------------------------------------------


class TestHidDeviceInfo:
    """Tests for :class:`HidDeviceInfo`."""

    def test_construction(self) -> None:
        """All attributes are stored correctly."""
        info = HidDeviceInfo(
            path=b"/dev/hid0",
            vendor_id=0x0FD9,
            product_id=0x0084,
            serial_number="ABC123",
            product_string="Stream Deck +",
        )
        assert info.path == b"/dev/hid0"
        assert info.vendor_id == 0x0FD9
        assert info.product_id == 0x0084
        assert info.serial_number == "ABC123"
        assert info.product_string == "Stream Deck +"

    def test_repr(self) -> None:
        """``__repr__`` includes vid, pid, and serial."""
        info = HidDeviceInfo(
            path=b"/dev/hid0",
            vendor_id=0x0FD9,
            product_id=0x0084,
            serial_number="ABC123",
            product_string="Stream Deck +",
        )
        r = repr(info)
        assert "0x0FD9" in r
        assert "0x0084" in r
        assert "ABC123" in r


# ---------------------------------------------------------------------------
# _load_library
# ---------------------------------------------------------------------------


class TestLoadLibrary:
    """Tests for :func:`_load_library`."""

    def test_raises_when_library_not_found(self) -> None:
        """Raises ``HidApiError`` when no candidate library can be loaded."""
        with (
            patch("deux.runtime.hid._ctypes_hidapi._lib", None),
            patch("deux.runtime.hid._ctypes_hidapi.ctypes.CDLL", side_effect=OSError),
            patch("deux.runtime.hid._ctypes_hidapi.ctypes.util.find_library", return_value=None),
        ):
            from deux.runtime.hid._ctypes_hidapi import _load_library

            with pytest.raises(HidApiError, match="Could not load libhidapi"):
                _load_library()


# ---------------------------------------------------------------------------
# Helpers for mock-lib tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_lib() -> MagicMock:
    """Return a ``MagicMock`` pretending to be the loaded hidapi library.

    Returns
    -------
    MagicMock
        Mock library with default return values for success paths.
    """
    lib = MagicMock()
    lib.hid_init.return_value = 0
    lib.hid_exit.return_value = 0
    lib.hid_error.return_value = "mock error"
    return lib


# ---------------------------------------------------------------------------
# hid_init / hid_exit
# ---------------------------------------------------------------------------


class TestHidInit:
    """Tests for :func:`hid_init`."""

    def test_success(self, mock_lib: MagicMock) -> None:
        """Succeeds when ``hid_init`` returns 0."""
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_init

            hid_init()
            mock_lib.hid_init.assert_called_once()

    def test_failure(self, mock_lib: MagicMock) -> None:
        """Raises ``HidApiError`` when ``hid_init`` returns non-zero."""
        mock_lib.hid_init.return_value = -1
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_init

            with pytest.raises(HidApiError, match="hid_init"):
                hid_init()


class TestHidExit:
    """Tests for :func:`hid_exit`."""

    def test_calls_lib(self, mock_lib: MagicMock) -> None:
        """Delegates to ``lib.hid_exit``."""
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_exit

            hid_exit()
            mock_lib.hid_exit.assert_called_once()


# ---------------------------------------------------------------------------
# hid_open / hid_close
# ---------------------------------------------------------------------------


class TestHidOpen:
    """Tests for :func:`hid_open`."""

    def test_success(self, mock_lib: MagicMock) -> None:
        """Returns handle on success."""
        mock_lib.hid_open_path.return_value = 42
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_open

            handle = hid_open(b"/dev/hid0")
            assert handle == 42

    def test_failure(self, mock_lib: MagicMock) -> None:
        """Raises ``HidApiError`` when handle is null/zero."""
        mock_lib.hid_open_path.return_value = 0
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_open

            with pytest.raises(HidApiError, match="Failed to open"):
                hid_open(b"/dev/hid0")


class TestHidClose:
    """Tests for :func:`hid_close`."""

    def test_delegates(self, mock_lib: MagicMock) -> None:
        """Calls ``lib.hid_close`` with handle."""
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_close

            hid_close(42)
            mock_lib.hid_close.assert_called_once_with(42)


# ---------------------------------------------------------------------------
# hid_write
# ---------------------------------------------------------------------------


class TestHidWrite:
    """Tests for :func:`hid_write`."""

    def test_success(self, mock_lib: MagicMock) -> None:
        """Returns byte count on success."""
        mock_lib.hid_write.return_value = 5
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_write

            result = hid_write(42, b"\x00\x01\x02\x03\x04")
            assert result == 5

    def test_failure(self, mock_lib: MagicMock) -> None:
        """Raises ``HidApiError`` on negative return."""
        mock_lib.hid_write.return_value = -1
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_write

            with pytest.raises(HidApiError, match="hid_write failed"):
                hid_write(42, b"\x00")


# ---------------------------------------------------------------------------
# hid_read_timeout
# ---------------------------------------------------------------------------


class TestHidReadTimeout:
    """Tests for :func:`hid_read_timeout`."""

    def test_returns_bytes_on_data(self, mock_lib: MagicMock) -> None:
        """Returns bytes when data is available."""
        mock_lib.hid_read_timeout.return_value = 3
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_read_timeout

            result = hid_read_timeout(42, 64, 100)
            assert isinstance(result, bytes)

    def test_returns_none_on_timeout(self, mock_lib: MagicMock) -> None:
        """Returns ``None`` when read times out (result == 0)."""
        mock_lib.hid_read_timeout.return_value = 0
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_read_timeout

            result = hid_read_timeout(42, 64, 100)
            assert result is None

    def test_failure(self, mock_lib: MagicMock) -> None:
        """Raises ``HidApiError`` on negative return."""
        mock_lib.hid_read_timeout.return_value = -1
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_read_timeout

            with pytest.raises(HidApiError, match="hid_read_timeout failed"):
                hid_read_timeout(42, 64, 100)


# ---------------------------------------------------------------------------
# hid_send_feature_report
# ---------------------------------------------------------------------------


class TestHidSendFeatureReport:
    """Tests for :func:`hid_send_feature_report`."""

    def test_success(self, mock_lib: MagicMock) -> None:
        """Returns byte count on success."""
        mock_lib.hid_send_feature_report.return_value = 4
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_send_feature_report

            result = hid_send_feature_report(42, b"\x03\x01\x02\x03")
            assert result == 4

    def test_failure(self, mock_lib: MagicMock) -> None:
        """Raises ``HidApiError`` on negative return."""
        mock_lib.hid_send_feature_report.return_value = -1
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_send_feature_report

            with pytest.raises(HidApiError, match="hid_send_feature_report failed"):
                hid_send_feature_report(42, b"\x03")


# ---------------------------------------------------------------------------
# hid_get_feature_report
# ---------------------------------------------------------------------------


class TestHidGetFeatureReport:
    """Tests for :func:`hid_get_feature_report`."""

    def test_success(self, mock_lib: MagicMock) -> None:
        """Returns bytes on success."""
        mock_lib.hid_get_feature_report.return_value = 8
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_get_feature_report

            result = hid_get_feature_report(42, 0x03, 32)
            assert isinstance(result, bytes)
            assert len(result) == 8

    def test_failure(self, mock_lib: MagicMock) -> None:
        """Raises ``HidApiError`` on negative return."""
        mock_lib.hid_get_feature_report.return_value = -1
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_get_feature_report

            with pytest.raises(HidApiError, match="hid_get_feature_report failed"):
                hid_get_feature_report(42, 0x03, 32)


# ---------------------------------------------------------------------------
# hid_enumerate (mock-based)
# ---------------------------------------------------------------------------


class TestHidEnumerate:
    """Tests for :func:`hid_enumerate` with a mocked library."""

    def test_returns_empty_when_no_devices(self, mock_lib: MagicMock) -> None:
        """Returns empty list when enumeration pointer is falsy."""
        mock_lib.hid_enumerate.return_value = None
        with patch("deux.runtime.hid._ctypes_hidapi._lib", mock_lib):
            from deux.runtime.hid._ctypes_hidapi import hid_enumerate

            result = hid_enumerate()
            assert result == []
