"""Shared fixtures for deckboard tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from PIL import Image

from deckboard.ui.controls.key_slot import KeySlot
from deckboard.ui.controls.encoder_slot import EncoderSlot
from deckboard.render.icons import IconManager
from deckboard.ui.screen import Screen
from deckboard.render.metrics import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.ui.touch_strip import TouchStrip
from deckboard.ui.cards.base import Card
from deckboard.ui.cards.status import StatusCard
from deckboard.ui.cards.stack import StackCard


@pytest.fixture
def key_slot():
    """A fresh KeySlot at index 0."""
    return KeySlot(0)


@pytest.fixture
def encoder():
    """A fresh EncoderSlot at index 0."""
    return EncoderSlot(0)


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
