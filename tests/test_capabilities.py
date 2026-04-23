"""Tests for deckui.runtime.capabilities — DeviceCapabilities class."""

from __future__ import annotations

from unittest.mock import MagicMock

from deckui.runtime.capabilities import (
    DeviceCapabilities,
    STREAM_DECK_PLUS,
)
from tests.conftest import STREAM_DECK_MINI, STREAM_DECK_NEO, STREAM_DECK_XL


class TestDeviceCapabilitiesConstants:
    def test_stream_deck_plus(self):
        caps = STREAM_DECK_PLUS
        assert caps.deck_type == "Stream Deck +"
        assert caps.key_count == 8
        assert caps.key_cols == 4
        assert caps.key_rows == 2
        assert caps.key_pixel_width == 120
        assert caps.key_pixel_height == 120
        assert caps.key_image_format == "JPEG"
        assert caps.dial_count == 4
        assert caps.has_visual is True
        assert caps.has_touch is True
        assert caps.touchscreen_width == 800
        assert caps.touchscreen_height == 100

    def test_stream_deck_mini(self):
        caps = STREAM_DECK_MINI
        assert caps.key_count == 6
        assert caps.key_pixel_width == 80
        assert caps.key_image_format == "BMP"
        assert caps.dial_count == 0

    def test_stream_deck_neo(self):
        caps = STREAM_DECK_NEO
        assert caps.key_count == 8
        assert caps.key_pixel_width == 96
        assert caps.has_screen is True
        assert caps.screen_width == 248
        assert caps.screen_height == 58
        assert caps.dial_count == 0

    def test_stream_deck_xl(self):
        caps = STREAM_DECK_XL
        assert caps.key_count == 32
        assert caps.key_cols == 8
        assert caps.key_rows == 4
        assert caps.key_pixel_width == 96


class TestDeviceCapabilitiesProperties:
    def test_key_size(self):
        assert STREAM_DECK_PLUS.key_size == (120, 120)
        assert STREAM_DECK_MINI.key_size == (80, 80)
        assert STREAM_DECK_NEO.key_size == (96, 96)

    def test_has_encoders(self):
        assert STREAM_DECK_PLUS.has_encoders is True
        assert STREAM_DECK_MINI.has_encoders is False
        assert STREAM_DECK_NEO.has_encoders is False

    def test_has_touchscreen(self):
        assert STREAM_DECK_PLUS.has_touchscreen is True
        assert STREAM_DECK_MINI.has_touchscreen is False
        assert STREAM_DECK_NEO.has_touchscreen is False

    def test_has_info_screen(self):
        assert STREAM_DECK_PLUS.has_info_screen is False
        assert STREAM_DECK_MINI.has_info_screen is False
        assert STREAM_DECK_NEO.has_info_screen is True

    def test_panel_count(self):
        assert STREAM_DECK_PLUS.panel_count == 4
        assert STREAM_DECK_MINI.panel_count == 0
        assert STREAM_DECK_NEO.panel_count == 0


class TestDeviceCapabilitiesFromDevice:
    def test_from_mock_device(self, mock_streamdeck_device):
        caps = DeviceCapabilities.from_device(mock_streamdeck_device)
        assert caps.deck_type == "Stream Deck +"
        assert caps.key_count == 8
        assert caps.key_cols == 4
        assert caps.key_rows == 2
        assert caps.key_pixel_width == 120
        assert caps.key_pixel_height == 120
        assert caps.key_image_format == "JPEG"
        assert caps.dial_count == 4
        assert caps.touchscreen_width == 800
        assert caps.touchscreen_height == 100

    def test_from_mock_mini(self, mock_mini_device):
        caps = DeviceCapabilities.from_device(mock_mini_device)
        assert caps.deck_type == "Stream Deck Mini"
        assert caps.key_count == 6
        assert caps.key_pixel_width == 80
        assert caps.key_image_format == "BMP"
        assert caps.dial_count == 0

    def test_from_mock_neo(self, mock_neo_device):
        caps = DeviceCapabilities.from_device(mock_neo_device)
        assert caps.deck_type == "Stream Deck Neo"
        assert caps.has_screen is True
        assert caps.screen_width == 248
        assert caps.screen_height == 58

    def test_frozen(self):
        import dataclasses
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            STREAM_DECK_PLUS.key_count = 99  # type: ignore[misc]
