"""Tests for deckboard.__init__ — public API surface."""

from __future__ import annotations

import deckboard


class TestPublicAPI:
    def test_version(self):
        assert deckboard.__version__ == "0.1.0"

    def test_all_exports(self):
        expected = {
            "BlankCard",
            "Card",
            "Deck",
            "DeckError",
            "DeckEvent",
            "DeviceCapabilities",
            "DeviceInfo",
            "DsuiCard",
            "DsuiKey",
            "EncoderPressEvent",
            "EncoderSlot",
            "EncoderTurnEvent",
            "EventType",
            "InfoScreen",
            "KeyEvent",
            "KeySlot",
            "PackageError",
            "PackageSpec",
            "RenderMetrics",
            "Screen",
            "TouchEvent",
            "TouchStrip",
            "load_all_packages",
            "load_package",
        }
        assert set(deckboard.__all__) == expected

    def test_key_slot_importable(self):
        from deckboard import KeySlot

        assert KeySlot is not None

    def test_deck_importable(self):
        from deckboard import Deck

        assert Deck is not None

    def test_deck_error_importable(self):
        from deckboard import DeckError

        assert DeckError is not None

    def test_encoder_slot_importable(self):
        from deckboard import EncoderSlot

        assert EncoderSlot is not None

    def test_event_types_importable(self):
        from deckboard import (
            DeckEvent,
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
        from deckboard import Screen

        assert Screen is not None

    def test_touchscreen_importable(self):
        from deckboard import Card, TouchStrip

        assert TouchStrip is not None
        assert Card is not None

    def test_device_info_importable(self):
        from deckboard import DeviceInfo

        assert DeviceInfo is not None

    def test_dsui_importable(self):
        from deckboard import (
            DsuiCard,
            DsuiKey,
            PackageError,
            PackageSpec,
            load_all_packages,
            load_package,
        )

        assert DsuiCard is not None
        assert DsuiKey is not None
        assert PackageError is not None
        assert PackageSpec is not None
        assert load_all_packages is not None
        assert load_package is not None

    def test_blank_card_importable(self):
        from deckboard import BlankCard

        assert BlankCard is not None

    def test_core_ui_importable(self):
        from deckboard import (
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
        from deckboard import DeviceCapabilities, InfoScreen, RenderMetrics

        assert DeviceCapabilities is not None
        assert InfoScreen is not None
        assert RenderMetrics is not None
