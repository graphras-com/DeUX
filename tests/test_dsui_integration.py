"""Tests for deckboard.dsui integration — Screen.set_key, Deck rendering, public API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from deckboard.dsui import (
    DsuiCard,
    DsuiKey,
    PackageError,
    PackageSpec,
    load_all_packages,
    load_package,
)
from deckboard.dsui.schema import (
    EventMapping,
    PackageType,
    TextBinding,
)
from deckboard.ui.controls.key_slot import KeySlot
from deckboard.ui.screen import Screen


# -- Helpers ---------------------------------------------------------------

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
    def test_set_key_installs_dsui_key(self):
        screen = Screen("test")
        key = DsuiKey(0, _key_spec())
        screen.set_key(0, key)
        assert screen.keys[0] is key

    def test_set_key_validates_index(self):
        screen = Screen("test")
        key = DsuiKey(0, _key_spec())
        with pytest.raises(IndexError):
            screen.set_key(8, key)
        with pytest.raises(IndexError):
            screen.set_key(-1, key)

    def test_set_key_validates_type(self):
        screen = Screen("test")
        with pytest.raises(TypeError):
            screen.set_key(0, "not a key")  # type: ignore[arg-type]

    def test_set_key_replaces_existing(self):
        screen = Screen("test")
        old = screen.key(0)
        new = DsuiKey(0, _key_spec())
        screen.set_key(0, new)
        assert screen.keys[0] is new
        assert screen.keys[0] is not old

    def test_set_key_accepts_regular_key_slot(self):
        screen = Screen("test")
        key = KeySlot(0)
        screen.set_key(0, key)
        assert screen.keys[0] is key


class TestScreenSetCard:
    def test_set_card_with_dsui_card(self):
        screen = Screen("test")
        card = DsuiCard(0, _card_spec())
        screen.set_card(0, card)
        assert screen.card(0) is card


class TestDeckDsuiKeyRendering:
    """Test that Deck._is_dsui_key correctly identifies DsuiKeys."""

    def test_is_dsui_key_true(self):
        from deckboard.runtime.deck import Deck

        key = DsuiKey(0, _key_spec())
        assert Deck._is_dsui_key(key) is True

    def test_is_dsui_key_false_for_regular(self):
        from deckboard.runtime.deck import Deck

        key = KeySlot(0)
        assert Deck._is_dsui_key(key) is False


class TestPublicApiImports:
    """Verify that all dsui types are importable from the top-level package."""

    def test_dsui_card_importable(self):
        from deckboard import DsuiCard

        assert DsuiCard is not None

    def test_dsui_key_importable(self):
        from deckboard import DsuiKey

        assert DsuiKey is not None

    def test_load_package_importable(self):
        from deckboard import load_package

        assert load_package is not None

    def test_load_all_packages_importable(self):
        from deckboard import load_all_packages

        assert load_all_packages is not None

    def test_package_error_importable(self):
        from deckboard import PackageError

        assert PackageError is not None

    def test_package_spec_importable(self):
        from deckboard import PackageSpec

        assert PackageSpec is not None

    def test_all_in_dunder_all(self):
        import deckboard

        for name in [
            "DsuiCard",
            "DsuiKey",
            "PackageError",
            "PackageSpec",
            "load_package",
            "load_all_packages",
        ]:
            assert name in deckboard.__all__


class TestDsuiInitExports:
    """Verify that all types are exported from deckboard.dsui."""

    def test_all_exports(self):
        from deckboard import dsui

        expected = [
            "DsuiCard",
            "DsuiKey",
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
            assert name in dsui.__all__, f"{name} not in dsui.__all__"
            assert hasattr(dsui, name), f"{name} not accessible on dsui module"


class TestEndToEnd:
    """Integration test: load from disk, set bindings, render, dispatch."""

    def test_load_and_render_card(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        card = DsuiCard(0, spec)
        card.set("title", "Integration Test")
        img = card.render()
        assert isinstance(img, Image.Image)
        assert img.size == (197, 98)

    def test_load_and_render_key(self, key_dsui_path):
        spec = load_package(key_dsui_path)
        key = DsuiKey(0, spec)
        key.set("label", "Power")
        data = key.render_image()
        assert isinstance(data, bytes)
        assert data[:2] == b"\xff\xd8"

    async def test_card_event_roundtrip(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("toggle_play", handler)

        # Simulate press + release
        await card.dispatch_encoder_press()
        await card.dispatch_encoder_release()

        # Drain pending callbacks and invoke them
        callbacks = card.drain_pending_callbacks()
        for h, args in callbacks:
            await h(*args)

        handler.assert_awaited_once()

    async def test_key_event_roundtrip(self, key_dsui_path):
        spec = load_package(key_dsui_path)
        key = DsuiKey(0, spec)
        handler = AsyncMock()
        key.bind_event("activate", handler)

        await key.dispatch(True)  # press
        await key.dispatch(False)  # release
        handler.assert_awaited_once()

    def test_load_all_and_use(self, dsui_packages_dir):
        packages = load_all_packages(dsui_packages_dir)
        assert len(packages) == 2

        screen = Screen("test")
        card = DsuiCard(0, packages["TestCard"])
        screen.set_card(0, card)

        key = DsuiKey(0, packages["TestKey"])
        screen.set_key(0, key)

        assert screen.card(0) is card
        assert screen.keys[0] is key
