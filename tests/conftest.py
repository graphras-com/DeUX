"""Shared fixtures for deckui tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from PIL import Image

import deckui.render.svg_rasterize as _svg_mod
from deckui.render.metrics import RenderMetrics
from deckui.runtime.capabilities import (
    STREAM_DECK_PLUS,
    DeviceCapabilities,
)
from deckui.ui.controls.encoder_slot import EncoderSlot
from deckui.ui.controls.key_slot import KeySlot
from deckui.ui.screen import Screen
from deckui.ui.touch_strip import TouchStrip

# Capture pristine state BEFORE any test modules are imported
# (some examples set the backend at module level during collection).
_PRISTINE_ACTIVE_BACKEND: str | None = _svg_mod._active_backend
_PRISTINE_REGISTRY: dict[str, object] = _svg_mod._registry.copy()

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_svg_backend():
    """Reset SVG backend state before and after every test.

    Restores the pristine state captured at conftest import time
    (before any test module imports that may call ``set_svg_backend``
    at module level).
    """
    _svg_mod._active_backend = _PRISTINE_ACTIVE_BACKEND
    _svg_mod._registry = _PRISTINE_REGISTRY.copy()
    yield
    _svg_mod._active_backend = _PRISTINE_ACTIVE_BACKEND
    _svg_mod._registry = _PRISTINE_REGISTRY.copy()


_PLUS_METRICS = RenderMetrics(STREAM_DECK_PLUS)
PANEL_WIDTH = _PLUS_METRICS.panel_width
PANEL_HEIGHT = _PLUS_METRICS.panel_height


STREAM_DECK_MINI = DeviceCapabilities(
    deck_type="Stream Deck Mini",
    key_count=6,
    key_cols=3,
    key_rows=2,
    key_pixel_width=80,
    key_pixel_height=80,
    key_image_format="BMP",
    key_flip=(True, True),
    key_rotation=90,
    has_visual=True,
    has_touch=False,
    dial_count=0,
    touchscreen_width=0,
    touchscreen_height=0,
    touchscreen_image_format="",
    touchscreen_flip=(False, False),
    touchscreen_rotation=0,
    has_screen=False,
    screen_width=0,
    screen_height=0,
    screen_image_format="",
    screen_flip=(False, False),
    screen_rotation=0,
    touch_key_count=0,
)

STREAM_DECK_NEO = DeviceCapabilities(
    deck_type="Stream Deck Neo",
    key_count=8,
    key_cols=4,
    key_rows=2,
    key_pixel_width=96,
    key_pixel_height=96,
    key_image_format="JPEG",
    key_flip=(False, False),
    key_rotation=0,
    has_visual=True,
    has_touch=False,
    dial_count=0,
    touchscreen_width=0,
    touchscreen_height=0,
    touchscreen_image_format="",
    touchscreen_flip=(False, False),
    touchscreen_rotation=0,
    has_screen=True,
    screen_width=248,
    screen_height=58,
    screen_image_format="JPEG",
    screen_flip=(False, False),
    screen_rotation=0,
    touch_key_count=0,
)

STREAM_DECK_XL = DeviceCapabilities(
    deck_type="Stream Deck XL",
    key_count=32,
    key_cols=8,
    key_rows=4,
    key_pixel_width=96,
    key_pixel_height=96,
    key_image_format="JPEG",
    key_flip=(True, True),
    key_rotation=0,
    has_visual=True,
    has_touch=False,
    dial_count=0,
    touchscreen_width=0,
    touchscreen_height=0,
    touchscreen_image_format="",
    touchscreen_flip=(False, False),
    touchscreen_rotation=0,
    has_screen=False,
    screen_width=0,
    screen_height=0,
    screen_image_format="",
    screen_flip=(False, False),
    screen_rotation=0,
    touch_key_count=0,
)


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


def _write_card_dui_package(base_dir: Path) -> Path:
    """Create a valid TouchStripCard .dui package on disk.

    Parameters
    ----------
    base_dir : Path
        Parent directory in which the ``TestCard.dui`` directory is created.

    Returns
    -------
    Path
        Path to the created ``.dui`` package directory.
    """
    pkg_dir = base_dir / "TestCard.dui"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "layout.svg").write_text(MINIMAL_CARD_SVG, encoding="utf-8")

    manifest = """\
name: TestCard
type: TouchStripCard
version: 1
layout: layout.svg
description: "A test card for audio playback"
author: "Test Author <test@example.com>"
category: media
tags: [music, test]

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
  progress:
    type: range
    node: accent
    default: 0.5
    direction: horizontal

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
  - name: seek_forward
    source: encoder_press_turn
    direction: right
  - name: seek_backward
    source: encoder_press_turn
    direction: left

regions:
  card:
    x: 0
    y: 0
    width: 197
    height: 98
    events: [tap, long_press]
"""
    (pkg_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")

    assets_dir = pkg_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    img.save(assets_dir / "test_icon.png")

    return pkg_dir


def _write_key_dui_package(base_dir: Path) -> Path:
    """Create a valid Key .dui package on disk.

    Parameters
    ----------
    base_dir : Path
        Parent directory in which the ``TestKey.dui`` directory is created.

    Returns
    -------
    Path
        Path to the created ``.dui`` package directory.
    """
    pkg_dir = base_dir / "TestKey.dui"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "layout.svg").write_text(MINIMAL_KEY_SVG, encoding="utf-8")

    manifest = """\
name: TestKey
type: Key
version: 1
layout: layout.svg
description: "A test key for status indication"
author: "Test Author <test@example.com>"

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
    source: key_hold
    hold_ms: 500
"""
    (pkg_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    return pkg_dir


@pytest.fixture
def card_dui_path(tmp_path):
    """Path to a valid TouchStripCard .dui package."""
    return _write_card_dui_package(tmp_path)


@pytest.fixture
def key_dui_path(tmp_path):
    """Path to a valid Key .dui package."""
    return _write_key_dui_package(tmp_path)


@pytest.fixture
def card_package_spec(card_dui_path):
    """A loaded PackageSpec for a TouchStripCard."""
    from deckui.dui.loader import load_package

    return load_package(card_dui_path)


@pytest.fixture
def key_package_spec(key_dui_path):
    """A loaded PackageSpec for a Key."""
    from deckui.dui.loader import load_package

    return load_package(key_dui_path)


@pytest.fixture
def dui_packages_dir(tmp_path):
    """A directory containing multiple .dui packages."""
    _write_card_dui_package(tmp_path)
    _write_key_dui_package(tmp_path)
    return tmp_path


@pytest.fixture
def key_slot():
    """A fresh KeySlot."""
    return KeySlot()


@pytest.fixture
def encoder():
    """A fresh EncoderSlot."""
    return EncoderSlot()


@pytest.fixture
def touchscreen():
    """A fresh TouchStrip with 4 blank cards (Stream Deck+ default)."""
    return TouchStrip(panel_count=4)


@pytest.fixture
def page():
    """A fresh Screen named 'test' with Stream Deck+ capabilities."""
    return Screen("test", STREAM_DECK_PLUS)


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


def _make_mock_streamdeck(caps: DeviceCapabilities) -> MagicMock:
    """Create a MagicMock mimicking a StreamDeck device from capabilities.

    Parameters
    ----------
    caps : DeviceCapabilities
        The capability profile to replicate on the mock.

    Returns
    -------
    MagicMock
        A mock object with all device attributes and methods configured
        to match *caps*.
    """
    device = MagicMock()
    device.DECK_TYPE = caps.deck_type
    device.DECK_VISUAL = caps.has_visual
    device.DECK_TOUCH = caps.has_touch
    device.KEY_PIXEL_WIDTH = caps.key_pixel_width
    device.KEY_PIXEL_HEIGHT = caps.key_pixel_height
    device.KEY_IMAGE_FORMAT = caps.key_image_format
    device.KEY_FLIP = list(caps.key_flip)
    device.KEY_ROTATION = caps.key_rotation
    device.TOUCHSCREEN_PIXEL_WIDTH = caps.touchscreen_width
    device.TOUCHSCREEN_PIXEL_HEIGHT = caps.touchscreen_height
    device.TOUCHSCREEN_IMAGE_FORMAT = caps.touchscreen_image_format
    device.TOUCHSCREEN_FLIP = list(caps.touchscreen_flip)
    device.TOUCHSCREEN_ROTATION = caps.touchscreen_rotation
    device.SCREEN_PIXEL_WIDTH = caps.screen_width
    device.SCREEN_PIXEL_HEIGHT = caps.screen_height
    device.SCREEN_IMAGE_FORMAT = caps.screen_image_format
    device.SCREEN_FLIP = list(caps.screen_flip)
    device.SCREEN_ROTATION = caps.screen_rotation
    device.TOUCH_KEY_COUNT = caps.touch_key_count

    device.deck_type.return_value = caps.deck_type
    device.get_serial_number.return_value = "TEST123"
    device.get_firmware_version.return_value = "1.0.0"
    device.key_count.return_value = caps.key_count
    device.key_layout.return_value = (caps.key_cols, caps.key_rows)
    device.dial_count.return_value = caps.dial_count

    device.open.return_value = None
    device.close.return_value = None
    device.reset.return_value = None
    device.set_brightness.return_value = None
    device.set_key_image.return_value = None
    device.set_touchscreen_image.return_value = None
    device.set_screen_image.return_value = None

    device.set_key_callback.return_value = None
    device.set_dial_callback.return_value = None
    device.set_touchscreen_callback.return_value = None

    return device


@pytest.fixture
def mock_streamdeck_device():
    """A MagicMock that mimics a Stream Deck+ device object."""
    return _make_mock_streamdeck(STREAM_DECK_PLUS)


@pytest.fixture
def mock_mini_device():
    """A MagicMock that mimics a Stream Deck Mini device object."""
    return _make_mock_streamdeck(STREAM_DECK_MINI)


@pytest.fixture
def mock_neo_device():
    """A MagicMock that mimics a Stream Deck Neo device object."""
    return _make_mock_streamdeck(STREAM_DECK_NEO)


@pytest.fixture
def mock_xl_device():
    """A MagicMock that mimics a Stream Deck XL device object."""
    return _make_mock_streamdeck(STREAM_DECK_XL)
