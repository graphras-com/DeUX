"""Direct HID transport for Elgato Stream Deck devices.

This package replaces the ``python-elgato-streamdeck`` library with a minimal
ctypes binding to ``libhidapi``, providing full access to the official Elgato
HID protocol including full-screen image uploads.

Modules
-------
_ctypes_hidapi
    Low-level ctypes wrappers around ``libhidapi`` C functions.
protocol
    HID report constants, packet builders, and input event parsers.
device
    Generic, self-describing device class backed by ``Get Unit Information``.
discovery
    Device enumeration by VID/PID allowlist.
transport
    Async wrappers for blocking HID I/O and input polling loop.
"""

from __future__ import annotations
