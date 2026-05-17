"""Tests for the default backgrounds loader."""

from __future__ import annotations

import pytest

from deux.render.defaults import (
    get_default_backgrounds,
    list_supported_devices,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _clean_defaults_cache():
    """Reset the defaults manifest cache before and after each test."""
    reset_cache()
    yield
    reset_cache()


class TestGetDefaultBackgrounds:
    """Tests for :func:`get_default_backgrounds`."""

    def test_returns_key_svg_for_classic_device(self):
        """Classic devices (72x72 keys) return a key background."""
        result = get_default_backgrounds(0x0FD9, 0x0080)  # Mk.2
        assert "key" in result
        assert b"<svg" in result["key"]

    def test_returns_key_svg_for_xl_device(self):
        """XL devices (96x96 keys) return a key background."""
        result = get_default_backgrounds(0x0FD9, 0x006C)  # XL
        assert "key" in result
        assert b"<svg" in result["key"]

    def test_returns_key_and_touchscreen_for_plus(self):
        """Stream Deck + returns both key and touchscreen backgrounds."""
        result = get_default_backgrounds(0x0FD9, 0x0084)
        assert "key" in result
        assert "touchscreen" in result
        assert b"<svg" in result["key"]
        assert b"<svg" in result["touchscreen"]

    def test_returns_key_and_touchscreen_for_plus_xl(self):
        """Stream Deck + XL returns both key and touchscreen backgrounds."""
        result = get_default_backgrounds(0x0FD9, 0x00C6)
        assert "key" in result
        assert "touchscreen" in result

    def test_returns_key_and_screen_for_neo(self):
        """Stream Deck Neo returns key and info screen backgrounds."""
        result = get_default_backgrounds(0x0FD9, 0x009A)
        assert "key" in result
        assert "screen" in result
        assert b"<svg" in result["screen"]

    def test_returns_empty_for_unknown_device(self):
        """Unknown VID:PID returns an empty dict."""
        result = get_default_backgrounds(0xDEAD, 0xBEEF)
        assert result == {}

    def test_plus_and_plus_xl_have_different_backgrounds(self):
        """Plus and Plus XL use different key sizes despite same model number."""
        plus = get_default_backgrounds(0x0FD9, 0x0084)
        plus_xl = get_default_backgrounds(0x0FD9, 0x00C6)
        # Different key sizes → different SVG content
        assert plus["key"] != plus_xl["key"]
        # Different touchscreen widths → different SVG content
        assert plus["touchscreen"] != plus_xl["touchscreen"]

    def test_caching_returns_same_result(self):
        """Subsequent calls return the same data (cache hit)."""
        first = get_default_backgrounds(0x0FD9, 0x0084)
        second = get_default_backgrounds(0x0FD9, 0x0084)
        assert first == second


class TestListSupportedDevices:
    """Tests for :func:`list_supported_devices`."""

    def test_returns_all_devices(self):
        """All devices from the manifest are listed."""
        devices = list_supported_devices()
        assert len(devices) >= 10
        # All should be Elgato VID
        assert all(vid == 0x0FD9 for vid, _ in devices)

    def test_sorted_output(self):
        """Device list is sorted by VID, then PID."""
        devices = list_supported_devices()
        assert devices == sorted(devices)

    def test_plus_and_plus_xl_both_present(self):
        """Both Plus (0x0084) and Plus XL (0x00C6) are listed."""
        devices = list_supported_devices()
        pids = {pid for _, pid in devices}
        assert 0x0084 in pids
        assert 0x00C6 in pids


class TestResetCache:
    """Tests for :func:`reset_cache`."""

    def test_reset_forces_reload(self):
        """After reset, the manifest is reloaded on next access."""
        # Populate cache
        result1 = get_default_backgrounds(0x0FD9, 0x0084)
        assert "key" in result1

        # Reset and verify it still works
        reset_cache()
        result2 = get_default_backgrounds(0x0FD9, 0x0084)
        assert "key" in result2
