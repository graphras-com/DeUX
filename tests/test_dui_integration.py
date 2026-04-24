"""Tests for deckui.dui integration — Screen.set_key, Deck rendering, public API."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from PIL import Image

from deckui.dui import (
    DuiCard,
    DuiKey,
    PackageSpec,
    load_all_packages,
    load_package,
)
from deckui.dui.schema import (
    EventMapping,
    PackageType,
    TextBinding,
)
from deckui.ui.controls.key_slot import KeySlot
from deckui.ui.screen import Screen

_KEY_SVG = (
    '<svg id="K" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<rect id="bg" width="120" height="120" fill="#333"/>'
    '<text id="label" x="60" y="100" fill="white">Key</text>'
    "</svg>"
)

_CARD_SVG = (
    '<svg id="C" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<rect id="bg" width="197" height="98" fill="#1c1c1c"/>'
    '<text id="title" x="4" y="40" fill="white">Card</text>'
    "</svg>"
)


def _key_spec() -> PackageSpec:
    return PackageSpec(
        name="K",
        type=PackageType.KEY,
        version=1,
        svg_source=_KEY_SVG,
        bindings={"label": TextBinding(node="label", default="Key")},
        events=(EventMapping(name="press", source="key_press"),),
    )


def _card_spec() -> PackageSpec:
    return PackageSpec(
        name="C",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_CARD_SVG,
        bindings={"title": TextBinding(node="title", default="Card")},
    )


class TestScreenSetKey:
    def test_set_key_installs_dui_key(self):
        screen = Screen("test")
        key = DuiKey(_key_spec())
        screen.set_key(0, key)
        assert screen.keys[0] is key

    def test_set_key_validates_index(self):
        screen = Screen("test")
        key = DuiKey(_key_spec())
        with pytest.raises(IndexError):
            screen.set_key(8, key)
        with pytest.raises(IndexError):
            screen.set_key(-1, key)

    def test_set_key_validates_type(self):
        screen = Screen("test")
        with pytest.raises(TypeError):
            screen.set_key(0, "not a key")

    def test_set_key_replaces_existing(self):
        screen = Screen("test")
        old = screen.key(0)
        new = DuiKey(_key_spec())
        screen.set_key(0, new)
        assert screen.keys[0] is new
        assert screen.keys[0] is not old

    def test_set_key_accepts_regular_key_slot(self):
        screen = Screen("test")
        key = KeySlot(0)
        screen.set_key(0, key)
        assert screen.keys[0] is key


class TestScreenSetCard:
    def test_set_card_with_dui_card(self):
        screen = Screen("test")
        card = DuiCard(_card_spec())
        screen.set_card(0, card)
        assert screen.card(0) is card


class TestDeckDuiKeyRendering:
    """Test that Deck._is_dui_key correctly identifies DuiKeys."""

    def test_is_dui_key_true(self):
        from deckui.runtime.deck import Deck

        key = DuiKey(_key_spec())
        assert Deck._is_dui_key(key) is True

    def test_is_dui_key_false_for_regular(self):
        from deckui.runtime.deck import Deck

        key = KeySlot(0)
        assert Deck._is_dui_key(key) is False


class TestPublicApiImports:
    """Verify that all dui types are importable from the top-level package."""

    def test_dui_card_importable(self):
        from deckui import DuiCard

        assert DuiCard is not None

    def test_dui_key_importable(self):
        from deckui import DuiKey

        assert DuiKey is not None

    def test_load_package_importable(self):
        from deckui import load_package

        assert load_package is not None

    def test_load_all_packages_importable(self):
        from deckui import load_all_packages

        assert load_all_packages is not None

    def test_package_error_importable(self):
        from deckui import PackageError

        assert PackageError is not None

    def test_package_spec_importable(self):
        from deckui import PackageSpec

        assert PackageSpec is not None

    def test_all_in_dunder_all(self):
        import deckui

        for name in [
            "DuiCard",
            "DuiKey",
            "PackageError",
            "PackageSpec",
            "load_package",
            "load_all_packages",
        ]:
            assert name in deckui.__all__


class TestDuiInitExports:
    """Verify that all types are exported from deckui.dui."""

    def test_all_exports(self):
        from deckui import dui

        expected = [
            "DuiCard",
            "DuiKey",
            "EventMap",
            "SvgRenderer",
            "PackageError",
            "PackageSpec",
            "PackageType",
            "load_package",
            "load_all_packages",
            "Binding",
            "BindingType",
            "TextBinding",
            "ImageBinding",
            "VisibilityBinding",
            "ColorBinding",
            "RangeBinding",
            "RangeDirection",
            "EventMapping",
            "Region",
            "ImageFit",
            "OverflowMode",
        ]
        for name in expected:
            assert name in dui.__all__, f"{name} not in dui.__all__"
            assert hasattr(dui, name), f"{name} not accessible on dui module"


class TestEndToEnd:
    """Integration test: load from disk, set bindings, render, dispatch."""

    def test_load_and_render_card(self, card_dui_path):
        spec = load_package(card_dui_path)
        card = DuiCard(spec)
        card.set("title", "Integration Test")
        img = card.render()
        assert isinstance(img, Image.Image)
        assert img.size == (197, 98)

    def test_load_and_render_key(self, key_dui_path):
        spec = load_package(key_dui_path)
        key = DuiKey(spec)
        key.set("label", "Power")
        data = key.render_image()
        assert isinstance(data, bytes)
        assert data[:2] == b"\xff\xd8"

    async def test_card_event_roundtrip(self, card_dui_path):
        spec = load_package(card_dui_path)
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("toggle_play", handler)

        await card.dispatch_encoder_press()
        await card.dispatch_encoder_release()

        callbacks = card.drain_pending_callbacks()
        for h, args in callbacks:
            await h(*args)

        handler.assert_awaited_once()

    async def test_key_event_roundtrip(self, key_dui_path):
        spec = load_package(key_dui_path)
        key = DuiKey(spec)
        handler = AsyncMock()
        key.bind_event("activate", handler)

        await key.dispatch(True)
        await key.dispatch(False)
        handler.assert_awaited_once()

    def test_load_all_and_use(self, dui_packages_dir):
        packages = load_all_packages(dui_packages_dir)
        assert len(packages) == 2

        screen = Screen("test")
        card = DuiCard(packages["TestCard"])
        screen.set_card(0, card)

        key = DuiKey(packages["TestKey"])
        screen.set_key(0, key)

        assert screen.card(0) is card
        assert screen.keys[0] is key
