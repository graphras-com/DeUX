"""Tests for deckui.__init__ — public API surface."""

from __future__ import annotations

import deckui


class TestPublicAPI:
    def test_version(self):
        assert isinstance(deckui.__version__, str)
        assert len(deckui.__version__) > 0

    def test_all_exports(self):
        expected = {
            "__version__",
            "AsyncEvent",
            "BlankCard",
            "Card",
            "CardController",
            "Deck",
            "DeckError",
            "DeckEvent",
            "DeckManager",
            "DeviceCapabilities",
            "DeviceInfo",
            "DuiCard",
            "DuiKey",
            "EncoderPressEvent",
            "EncoderSlot",
            "EncoderTurnEvent",
            "EventType",
            "ImageFetchError",
            "InfoScreen",
            "KeyController",
            "KeyEvent",
            "KeySlot",
            "PackageError",
            "PackageSpec",
            "RenderMetrics",
            "Screen",
            "TouchEvent",
            "TouchStrip",
            "clear_image_cache",
            "fetch_image",
            "list_devices",
            "load_all_packages",
            "load_package",
        }
        assert set(deckui.__all__) == expected

    def test_key_slot_importable(self):
        from deckui import KeySlot

        assert KeySlot is not None

    def test_deck_error_importable(self):
        from deckui import DeckError

        assert DeckError is not None

    def test_encoder_slot_importable(self):
        from deckui import EncoderSlot

        assert EncoderSlot is not None

    def test_event_types_importable(self):
        from deckui import (
            EncoderPressEvent,
            EncoderTurnEvent,
            EventType,
            KeyEvent,
            TouchEvent,
        )

        assert KeyEvent is not None
        assert EncoderTurnEvent is not None
        assert EncoderPressEvent is not None
        assert TouchEvent is not None
        assert EventType is not None

    def test_screen_importable(self):
        from deckui import Screen

        assert Screen is not None

    def test_touchscreen_importable(self):
        from deckui import Card, TouchStrip

        assert TouchStrip is not None
        assert Card is not None

    def test_device_info_importable(self):
        from deckui import DeviceInfo

        assert DeviceInfo is not None

    def test_dui_importable(self):
        from deckui import (
            DuiCard,
            DuiKey,
            PackageError,
            PackageSpec,
            load_all_packages,
            load_package,
        )

        assert DuiCard is not None
        assert DuiKey is not None
        assert PackageError is not None
        assert PackageSpec is not None
        assert load_all_packages is not None
        assert load_package is not None

    def test_blank_card_importable(self):
        from deckui import BlankCard

        assert BlankCard is not None

    def test_core_ui_importable(self):
        from deckui import (
            BlankCard,
            Card,
            EncoderSlot,
            KeySlot,
            Screen,
            TouchStrip,
        )

        assert Screen is not None
        assert KeySlot is not None
        assert EncoderSlot is not None
        assert Card is not None
        assert BlankCard is not None
        assert TouchStrip is not None

    def test_new_multi_device_exports(self):
        from deckui import DeviceCapabilities, InfoScreen, RenderMetrics

        assert DeviceCapabilities is not None
        assert InfoScreen is not None
        assert RenderMetrics is not None

    def test_async_event_importable(self):
        from deckui import AsyncEvent

        assert AsyncEvent is not None

    def test_deck_importable(self):
        from deckui import Deck

        assert Deck is not None

    def test_controllers_importable(self):
        from deckui import CardController, KeyController

        assert CardController is not None
        assert KeyController is not None
