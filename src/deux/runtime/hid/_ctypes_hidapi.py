"""Minimal ctypes bindings to ``libhidapi``.

Exposes only the C functions required by the Stream Deck HID transport.
The shared library is located at import time via platform-specific search
paths; a :class:`HidApiError` is raised if it cannot be found.

No pip dependency is required -- only the ``libhidapi`` system library
(``brew install hidapi`` on macOS, ``libhidapi-dev`` on Debian/Ubuntu).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import platform
import struct
import sys
from ctypes import (
    POINTER,
    Structure,
    c_char_p,
    c_int,
    c_size_t,
    c_ushort,
    c_void_p,
    c_wchar_p,
)
from typing import Iterator


class HidApiError(OSError):
    """Raised when ``libhidapi`` cannot be loaded or returns an error."""


# ---------------------------------------------------------------------------
# HID device info structure (matches ``struct hid_device_info`` in hidapi.h)
# ---------------------------------------------------------------------------


class _HidDeviceInfo(Structure):
    """Mirror of ``struct hid_device_info`` from hidapi."""


_HidDeviceInfo._fields_ = [  # noqa: SLF001
    ("path", c_char_p),
    ("vendor_id", c_ushort),
    ("product_id", c_ushort),
    ("serial_number", c_wchar_p),
    ("release_number", c_ushort),
    ("manufacturer_string", c_wchar_p),
    ("product_string", c_wchar_p),
    ("usage_page", c_ushort),
    ("usage", c_ushort),
    ("interface_number", c_int),
    ("next", POINTER(_HidDeviceInfo)),
]


# ---------------------------------------------------------------------------
# Library loading
# ---------------------------------------------------------------------------

_lib: ctypes.CDLL | None = None


def _load_library() -> ctypes.CDLL:
    """Locate and load ``libhidapi``.

    Returns
    -------
    ctypes.CDLL
        The loaded shared library handle.

    Raises
    ------
    HidApiError
        If the library cannot be found on the system.
    """
    global _lib  # noqa: PLW0603
    if _lib is not None:
        return _lib

    candidates: list[str] = []
    system = platform.system()

    if system == "Darwin":
        candidates = [
            "libhidapi.dylib",
            "/opt/homebrew/lib/libhidapi.dylib",
            "/usr/local/lib/libhidapi.dylib",
        ]
    elif system == "Linux":
        candidates = [
            "libhidapi-hidraw.so.0",
            "libhidapi-hidraw.so",
            "libhidapi-libusb.so.0",
            "libhidapi-libusb.so",
        ]
    elif system == "Windows":
        candidates = ["hidapi.dll"]

    # Also try ctypes.util.find_library as a fallback
    found = ctypes.util.find_library("hidapi")
    if found:
        candidates.insert(0, found)

    for name in candidates:
        try:
            lib = ctypes.CDLL(name)
            _setup_signatures(lib)
            _lib = lib
            return lib
        except OSError:
            continue

    msg = (
        "Could not load libhidapi. "
        "Install it with: brew install hidapi (macOS) "
        "or apt install libhidapi-dev (Debian/Ubuntu)."
    )
    raise HidApiError(msg)


def _setup_signatures(lib: ctypes.CDLL) -> None:
    """Declare C function signatures on the loaded library.

    Parameters
    ----------
    lib : ctypes.CDLL
        The loaded ``libhidapi`` shared library.
    """
    lib.hid_init.restype = c_int
    lib.hid_init.argtypes = []

    lib.hid_exit.restype = c_int
    lib.hid_exit.argtypes = []

    lib.hid_enumerate.restype = POINTER(_HidDeviceInfo)
    lib.hid_enumerate.argtypes = [c_ushort, c_ushort]

    lib.hid_free_enumeration.restype = None
    lib.hid_free_enumeration.argtypes = [POINTER(_HidDeviceInfo)]

    lib.hid_open_path.restype = c_void_p
    lib.hid_open_path.argtypes = [c_char_p]

    lib.hid_close.restype = None
    lib.hid_close.argtypes = [c_void_p]

    lib.hid_write.restype = c_int
    lib.hid_write.argtypes = [c_void_p, c_char_p, c_size_t]

    lib.hid_read_timeout.restype = c_int
    lib.hid_read_timeout.argtypes = [c_void_p, c_char_p, c_size_t, c_int]

    lib.hid_send_feature_report.restype = c_int
    lib.hid_send_feature_report.argtypes = [c_void_p, c_char_p, c_size_t]

    lib.hid_get_feature_report.restype = c_int
    lib.hid_get_feature_report.argtypes = [c_void_p, c_char_p, c_size_t]

    lib.hid_error.restype = c_wchar_p
    lib.hid_error.argtypes = [c_void_p]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class HidDeviceInfo:
    """Lightweight container for enumerated HID device metadata.

    Attributes
    ----------
    path : bytes
        OS-specific device path used to open the device.
    vendor_id : int
        USB vendor ID.
    product_id : int
        USB product ID.
    serial_number : str
        Device serial number, or empty string if unavailable.
    product_string : str
        Product description string.
    """

    __slots__ = ("path", "vendor_id", "product_id", "serial_number", "product_string")

    def __init__(
        self,
        path: bytes,
        vendor_id: int,
        product_id: int,
        serial_number: str,
        product_string: str,
    ) -> None:
        self.path = path
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial_number = serial_number
        self.product_string = product_string

    def __repr__(self) -> str:
        return (
            f"HidDeviceInfo(vid=0x{self.vendor_id:04X}, "
            f"pid=0x{self.product_id:04X}, "
            f"serial={self.serial_number!r})"
        )


def hid_init() -> None:
    """Initialise the ``hidapi`` library.

    Must be called before any other ``hid_*`` function.

    Raises
    ------
    HidApiError
        If initialisation fails.
    """
    lib = _load_library()
    if lib.hid_init() != 0:
        raise HidApiError("hid_init() failed")


def hid_exit() -> None:
    """Shut down the ``hidapi`` library and free resources."""
    lib = _load_library()
    lib.hid_exit()


def hid_enumerate(vendor_id: int = 0, product_id: int = 0) -> list[HidDeviceInfo]:
    """Enumerate connected HID devices.

    Parameters
    ----------
    vendor_id : int, default=0
        USB vendor ID to filter by, or ``0`` for all vendors.
    product_id : int, default=0
        USB product ID to filter by, or ``0`` for all products.

    Returns
    -------
    list[HidDeviceInfo]
        List of matching device info objects.
    """
    lib = _load_library()
    head = lib.hid_enumerate(vendor_id, product_id)
    devices: list[HidDeviceInfo] = []
    try:
        cur = head
        while cur:
            info = cur.contents
            devices.append(
                HidDeviceInfo(
                    path=info.path or b"",
                    vendor_id=info.vendor_id,
                    product_id=info.product_id,
                    serial_number=info.serial_number or "",
                    product_string=info.product_string or "",
                )
            )
            cur = info.next
    finally:
        if head:
            lib.hid_free_enumeration(head)
    return devices


def hid_open(path: bytes) -> int:
    """Open a HID device by path.

    Parameters
    ----------
    path : bytes
        The OS-specific device path from :class:`HidDeviceInfo`.

    Returns
    -------
    int
        An opaque device handle.

    Raises
    ------
    HidApiError
        If the device cannot be opened.
    """
    lib = _load_library()
    handle = lib.hid_open_path(path)
    if not handle:
        err = lib.hid_error(None) or "unknown error"
        msg = f"Failed to open HID device at {path!r}: {err}"
        raise HidApiError(msg)
    return handle


def hid_close(handle: int) -> None:
    """Close an open HID device.

    Parameters
    ----------
    handle : int
        Device handle from :func:`hid_open`.
    """
    lib = _load_library()
    lib.hid_close(handle)


def hid_write(handle: int, data: bytes) -> int:
    """Send an output report to a HID device.

    Parameters
    ----------
    handle : int
        Device handle.
    data : bytes
        The report data to send (including report ID as first byte).

    Returns
    -------
    int
        Number of bytes written.

    Raises
    ------
    HidApiError
        If the write fails.
    """
    lib = _load_library()
    result = lib.hid_write(handle, data, len(data))
    if result < 0:
        err = lib.hid_error(handle) or "unknown error"
        raise HidApiError(f"hid_write failed: {err}")
    return result


def hid_read_timeout(handle: int, max_length: int, timeout_ms: int) -> bytes | None:
    """Read an input report with timeout.

    Parameters
    ----------
    handle : int
        Device handle.
    max_length : int
        Maximum number of bytes to read.
    timeout_ms : int
        Timeout in milliseconds. ``0`` for non-blocking, ``-1`` for blocking.

    Returns
    -------
    bytes or None
        The report data (without report ID prefix on some platforms), or
        ``None`` if the read timed out.

    Raises
    ------
    HidApiError
        If the read fails (device disconnected, etc.).
    """
    lib = _load_library()
    buf = ctypes.create_string_buffer(max_length)
    result = lib.hid_read_timeout(handle, buf, max_length, timeout_ms)
    if result < 0:
        err = lib.hid_error(handle) or "unknown error"
        raise HidApiError(f"hid_read_timeout failed: {err}")
    if result == 0:
        return None
    return buf.raw[:result]


def hid_send_feature_report(handle: int, data: bytes) -> int:
    """Send a feature report to a HID device.

    Parameters
    ----------
    handle : int
        Device handle.
    data : bytes
        The feature report data (first byte is report ID).

    Returns
    -------
    int
        Number of bytes sent.

    Raises
    ------
    HidApiError
        If the send fails.
    """
    lib = _load_library()
    result = lib.hid_send_feature_report(handle, data, len(data))
    if result < 0:
        err = lib.hid_error(handle) or "unknown error"
        raise HidApiError(f"hid_send_feature_report failed: {err}")
    return result


def hid_get_feature_report(handle: int, report_id: int, max_length: int = 32) -> bytes:
    """Request and read a feature report from a HID device.

    Parameters
    ----------
    handle : int
        Device handle.
    report_id : int
        The report ID to request.
    max_length : int, default=32
        Maximum report size.

    Returns
    -------
    bytes
        The feature report data (including report ID as first byte).

    Raises
    ------
    HidApiError
        If the read fails.
    """
    lib = _load_library()
    buf = ctypes.create_string_buffer(max_length)
    buf[0] = report_id
    result = lib.hid_get_feature_report(handle, buf, max_length)
    if result < 0:
        err = lib.hid_error(handle) or "unknown error"
        raise HidApiError(f"hid_get_feature_report failed: {err}")
    return buf.raw[:result]
