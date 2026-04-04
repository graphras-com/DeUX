"""Shared fixtures for deckboard tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from PIL import Image

from deckboard.button import Button
from deckboard.dial import Dial
from deckboard.icon import IconManager
from deckboard.page import Screen
from deckboard.image import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.touchscreen import TouchStrip, Card
from deckboard.widgets.icon_widget import StatusCard
from deckboard.widgets.touch_panel import StackCard


@pytest.fixture
def button():
    """A fresh Button at index 0."""
    return Button(0)


@pytest.fixture
def dial():
    """A fresh Dial at index 0."""
    return Dial(0)


@pytest.fixture
def widget():
    """A fresh StatusCard at index 0."""
    return StatusCard(0)


@pytest.fixture
def slider_widget():
    """A fresh StackCard at index 0."""
    return StackCard(0)


@pytest.fixture
def touchscreen():
    """A fresh TouchStrip with 4 widgets."""
    return TouchStrip()


@pytest.fixture
def page():
    """A fresh Screen named 'test'."""
    return Screen("test")


@pytest.fixture
def icon_manager(tmp_path):
    """An IconManager with a temporary cache directory."""
    return IconManager(cache_dir=tmp_path / "icons")


@pytest.fixture
def sample_icon():
    """A small 80x80 RGBA test icon."""
    return Image.new("RGBA", (80, 80), (255, 0, 0, 255))


@pytest.fixture
def sample_rgb_icon():
    """A small 80x80 RGB test icon (no alpha)."""
    return Image.new("RGB", (80, 80), (0, 255, 0))


@pytest.fixture
def sample_widget_image():
    """A PANEL_WIDTH x PANEL_HEIGHT RGB test image for widgets."""
    return Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), (0, 0, 255))


@pytest.fixture
def mock_streamdeck_device():
    """A MagicMock that mimics a StreamDeck device object."""
    device = MagicMock()
    device.DECK_TYPE = "Stream Deck +"
    device.KEY_PIXEL_WIDTH = 120
    device.KEY_PIXEL_HEIGHT = 120
    device.TOUCHSCREEN_PIXEL_WIDTH = 800
    device.TOUCHSCREEN_PIXEL_HEIGHT = 100
    device.KEY_IMAGE_FORMAT = "JPEG"

    device.deck_type.return_value = "Stream Deck +"
    device.get_serial_number.return_value = "TEST123"
    device.get_firmware_version.return_value = "1.0.0"
    device.key_count.return_value = 8
    device.key_layout.return_value = (4, 2)
    device.dial_count.return_value = 4

    device.open.return_value = None
    device.close.return_value = None
    device.reset.return_value = None
    device.set_brightness.return_value = None
    device.set_key_image.return_value = None
    device.set_touchscreen_image.return_value = None

    device.set_key_callback.return_value = None
    device.set_dial_callback.return_value = None
    device.set_touchscreen_callback.return_value = None

    return device
