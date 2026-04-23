"""End-to-end tests for the IconKey.dui example package."""

from __future__ import annotations

from pathlib import Path

import pytest

import deckui.dsui.svg_renderer as svg_renderer_mod
from deckui.dsui import DsuiKey, load_package
from deckui.dsui.iconify import clear_cache
from deckui.dsui.schema import IconifyBinding, TextBinding

_SAMPLE_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" '
    'viewBox="0 0 24 24"><path fill="currentColor" d="M0 0"/></svg>'
)

_EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "examples" / "IconKey.dui"


@pytest.fixture(autouse=True)
def _isolate_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def patch_fetch(monkeypatch):
    """Replace the network-backed fetch with a deterministic local SVG."""
    monkeypatch.setattr(
        svg_renderer_mod, "fetch_icon", lambda name: _SAMPLE_ICON_SVG, raising=True
    )


class TestIconKeyExamplePackage:
    def test_example_package_loads(self):
        spec = load_package(_EXAMPLE_DIR)
        assert spec.name == "IconKey"

    def test_icon_binding_parsed(self):
        spec = load_package(_EXAMPLE_DIR)
        icon = spec.bindings["icon"]
        assert isinstance(icon, IconifyBinding)
        assert icon.node == "icon"
        assert icon.size == 55
        assert icon.default == "line-md:home"

    def test_label_binding_parsed(self):
        spec = load_package(_EXAMPLE_DIR)
        label = spec.bindings["label"]
        assert isinstance(label, TextBinding)
        assert label.default == "Label"

    def test_events_parsed(self):
        spec = load_package(_EXAMPLE_DIR)
        names = [e.name for e in spec.events]
        assert "activate" in names
        assert "long_hold" in names

    def test_dsui_key_renders_with_icon(self, patch_fetch):
        spec = load_package(_EXAMPLE_DIR)
        key = DsuiKey(spec)
        jpeg_bytes = key.render_image()
        assert isinstance(jpeg_bytes, (bytes, bytearray))
        assert len(jpeg_bytes) > 0

    def test_dsui_key_updates_label_and_icon(self, patch_fetch):
        spec = load_package(_EXAMPLE_DIR)
        key = DsuiKey(spec)
        assert key.set("label", "Home") is key
        assert key.set("icon", "line-md:settings") is key
        jpeg_bytes = key.render_image()
        assert isinstance(jpeg_bytes, (bytes, bytearray))
        assert len(jpeg_bytes) > 0
