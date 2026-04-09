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


# -- Minimal SVG templates for dsui tests ----------------------------------

MINIMAL_CARD_SVG = (
    '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" '
    'width="197" height="98">'
    '<rect id="background" width="197" height="98" fill="#1c1c1c"/>'
    '<text id="title" x="4" y="40" font-size="14" fill="#ffffff">Default</text>'
    '<text id="artist" x="4" y="25" font-size="20" fill="#80bbff">Artist</text>'
    '<image id="cover" x="102" y="2" width="93" height="93" href=""/>'
    '<rect id="cover_placeholder" x="102" y="2" width="93" height="93" fill="#FFA165"/>'
    '<rect id="overlay" x="0" y="0" width="197" height="98" fill="none"/>'
    '<rect id="accent" x="0" y="90" width="197" height="8" fill="#ff0000"/>'
    "</svg>"
)

MINIMAL_KEY_SVG = (
    '<svg id="TestKey" xmlns="http://www.w3.org/2000/svg" '
    'width="120" height="120">'
    '<rect id="background" width="120" height="120" fill="#1c1c1c"/>'
    '<text id="label" x="60" y="100" font-size="14" fill="#ffffff" '
    'text-anchor="middle">Key</text>'
    '<rect id="indicator" x="10" y="10" width="100" height="100" fill="none"/>'
    "</svg>"
)


def _write_card_dsui_package(base_dir: Path) -> Path:
    """Create a valid TouchStripCard .dsui package on disk."""
    pkg_dir = base_dir / "TestCard.dsui"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "layout.svg").write_text(MINIMAL_CARD_SVG, encoding="utf-8")

    manifest = """\
name: TestCard
type: TouchStripCard
version: 1
layout: layout.svg

bindings:
  title:
    type: text
    node: title
    default: "Default Title"
    max_width: 90
    overflow: ellipsis
  artist:
    type: text
    node: artist
    default: ""
  cover:
    type: image
    node: cover
    fit: cover
    placeholder_node: cover_placeholder
  overlay_visible:
    type: visibility
    node: overlay
    default: true
  accent_color:
    type: color
    node: accent
    attribute: fill
    default: "#ff0000"

events:
  - name: toggle_play
    source: encoder_press_release
    max_duration_ms: 250
  - name: next
    source: encoder_turn
    direction: right
  - name: previous
    source: encoder_turn
    direction: left
  - name: seek
    source: encoder_press_turn

regions:
  card:
    x: 0
    y: 0
    width: 197
    height: 98
    events: [tap, long_press]
"""
    (pkg_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")

    # Create a small test asset
    assets_dir = pkg_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    img.save(assets_dir / "test_icon.png")

    return pkg_dir


def _write_key_dsui_package(base_dir: Path) -> Path:
    """Create a valid Key .dsui package on disk."""
    pkg_dir = base_dir / "TestKey.dsui"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "layout.svg").write_text(MINIMAL_KEY_SVG, encoding="utf-8")

    manifest = """\
name: TestKey
type: Key
version: 1
layout: layout.svg

bindings:
  label:
    type: text
    node: label
    default: "Key"
  indicator_color:
    type: color
    node: indicator
    attribute: fill
    default: "#333333"

events:
  - name: activate
    source: key_press_release
    max_duration_ms: 300
  - name: hold
    source: key_press
"""
    (pkg_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    return pkg_dir


@pytest.fixture
def card_dsui_path(tmp_path):
    """Path to a valid TouchStripCard .dsui package."""
    return _write_card_dsui_package(tmp_path)


@pytest.fixture
def key_dsui_path(tmp_path):
    """Path to a valid Key .dsui package."""
    return _write_key_dsui_package(tmp_path)


@pytest.fixture
def card_package_spec(card_dsui_path):
    """A loaded PackageSpec for a TouchStripCard."""
    from deckboard.dsui.loader import load_package

    return load_package(card_dsui_path)


@pytest.fixture
def key_package_spec(key_dsui_path):
    """A loaded PackageSpec for a Key."""
    from deckboard.dsui.loader import load_package

    return load_package(key_dsui_path)


@pytest.fixture
def dsui_packages_dir(tmp_path):
    """A directory containing multiple .dsui packages."""
    _write_card_dsui_package(tmp_path)
    _write_key_dsui_package(tmp_path)
    return tmp_path


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
