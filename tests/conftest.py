"""Shared fixtures for deux tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from PIL import Image

import deux.dui.repository as _repo_mod
import deux.render.svg_rasterize as _svg_mod
import deux.render.theme as _theme_mod
from deux.render.metrics import RenderMetrics
from deux.runtime.capabilities import (
    STREAM_DECK_PLUS,
    DeviceCapabilities,
)
from deux.ui.controls.encoder_slot import EncoderSlot
from deux.ui.controls.key_slot import KeySlot
from deux.ui.screen import Screen
from deux.ui.touch_strip import TouchStrip

# Capture pristine state BEFORE any test modules are imported.
_PRISTINE_ACTIVE_STYLESHEET: str | None = _svg_mod._active_stylesheet
_PRISTINE_ACTIVE_THEME = _theme_mod._active_theme

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _reset_svg_state():
    """Reset SVG stylesheet state before and after every test.

    Restores the pristine state captured at conftest import time.
    Also resets ``_active_theme`` to prevent cross-test state bleed.
    """
    _svg_mod._active_stylesheet = _PRISTINE_ACTIVE_STYLESHEET
    _theme_mod._active_theme = _PRISTINE_ACTIVE_THEME
    yield
    _svg_mod._active_stylesheet = _PRISTINE_ACTIVE_STYLESHEET
    _theme_mod._active_theme = _PRISTINE_ACTIVE_THEME


@pytest.fixture(autouse=True)
def _reset_dui_repository():
    """Reset the global DUI repository singleton between tests.

    Ensures each test starts with a fresh repository so that
    ``add_dui_path`` / ``remove_dui_path`` calls in one test do not
    leak into subsequent tests.
    """
    _repo_mod._default_repository = None
    yield
    _repo_mod._default_repository = None


_PLUS_METRICS = RenderMetrics(STREAM_DECK_PLUS)
PANEL_WIDTH = _PLUS_METRICS.panel_width
PANEL_HEIGHT = _PLUS_METRICS.panel_height


STREAM_DECK_MINI = DeviceCapabilities(
    vendor_id=0x0FD9,
    product_id=0x0063,
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
    vendor_id=0x0FD9,
    product_id=0x009A,
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
    vendor_id=0x0FD9,
    product_id=0x006C,
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
    from deux.dui.loader import load_package

    return load_package(card_dui_path)


@pytest.fixture
def key_package_spec(key_dui_path):
    """A loaded PackageSpec for a Key."""
    from deux.dui.loader import load_package

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
    """Create a MagicMock mimicking an HidDevice from capabilities.

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

    # Properties matching HidDevice interface
    device.vendor_id = caps.vendor_id
    device.product_id = caps.product_id
    device.family = caps.deck_type
    device.serial_number = "TEST123"
    device.firmware_version = "1.0.0"
    device.key_count = caps.key_count
    device.key_layout = (caps.key_cols, caps.key_rows)
    device.key_size = (caps.key_pixel_width, caps.key_pixel_height)
    device.lcd_size = (getattr(caps, "lcd_width", 0), getattr(caps, "lcd_height", 0))
    device.has_window = caps.has_touch or caps.has_screen
    device.window_size = (
        (caps.touchscreen_width, caps.touchscreen_height) if caps.has_touch
        else (caps.screen_width, caps.screen_height) if caps.has_screen
        else (0, 0)
    )
    device.has_touch = caps.has_touch
    device.has_encoders = caps.has_encoders
    device.encoder_count = caps.dial_count
    device.sensor_count = caps.touch_key_count
    device.is_open = True
    device.path = b"/dev/mock_streamdeck"

    # ImageRotation enum value
    from deux.runtime.hid.protocol import ImageRotation

    rotation = (
        ImageRotation(caps.key_rotation)
        if caps.key_rotation in (0, 180, 270)
        else ImageRotation.NONE
    )
    device.rotation = rotation

    # Unit info mock
    unit_info = MagicMock()
    unit_info.rows = caps.key_rows
    unit_info.cols = caps.key_cols
    unit_info.key_width = caps.key_pixel_width
    unit_info.key_height = caps.key_pixel_height
    unit_info.lcd_width = getattr(caps, "lcd_width", 0)
    unit_info.lcd_height = getattr(caps, "lcd_height", 0)
    device.unit_info = unit_info

    # Methods matching HidDevice interface
    device.open.return_value = None
    device.close.return_value = None
    device.show_logo.return_value = None
    device.set_brightness.return_value = None
    device.set_key_image.return_value = None
    device.set_full_screen_image.return_value = None
    device.set_window_image.return_value = None
    device.set_partial_window_image.return_value = None
    device.fill_lcd_color.return_value = None
    device.fill_key_color.return_value = None
    device.read_input.return_value = None

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
