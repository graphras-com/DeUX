"""Tests for deckboard.__init__ — public API surface."""

from __future__ import annotations

import deckboard


class TestPublicAPI:
    def test_version(self):
        assert deckboard.__version__ == "0.1.0"

    def test_all_exports(self):
        expected = {
            "BalanceSlider",
            "BrightnessSlider",
            "Card",
            "Control",
            "Deck",
            "DeckError",
            "DeckEvent",
            "DeviceInfo",
            "DsuiCard",
            "DsuiKey",
            "Element",
            "EncoderPressEvent",
            "EncoderSlot",
            "EncoderTurnEvent",
            "EqualizerCard",
            "EqualizerSlider",
            "EventType",
            "HaMediaCard",
            "IconError",
            "IconManager",
            "KelvinSlider",
            "KeyEvent",
            "KeySlot",
            "LargeDualValue",
            "LargeSlider",
            "LargeText",
            "LightCard",
            "MediaCard",
            "PackageError",
            "PackageSpec",
            "RangeControl",
            "Screen",
            "Slider",
            "SmallDualValue",
            "SmallSlider",
            "SmallText",
            "StackCard",
            "StatusCard",
            "TemperatureSlider",
            "TouchEvent",
            "TouchStrip",
            "VolumeSlider",
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

    def test_icon_importable(self):
        from deckboard import IconError, IconManager

        assert IconManager is not None
        assert IconError is not None

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

    def test_widgets_importable(self):
        from deckboard import (
            BalanceSlider,
            BrightnessSlider,
            Control,
            Element,
            EncoderSlot,
            EqualizerSlider,
            KelvinSlider,
            KeySlot,
            LargeDualValue,
            LargeSlider,
            LargeText,
            RangeControl,
            Screen,
            Slider,
            SmallDualValue,
            SmallSlider,
            SmallText,
            StackCard,
            StatusCard,
            TemperatureSlider,
            TouchStrip,
            VolumeSlider,
        )

        assert Screen is not None
        assert KeySlot is not None
        assert EncoderSlot is not None
        assert Control is not None
        assert Element is not None
        assert Slider is not None
        assert RangeControl is not None
        assert LargeSlider is not None
        assert SmallSlider is not None
        assert VolumeSlider is not None
        assert BrightnessSlider is not None
        assert KelvinSlider is not None
        assert TemperatureSlider is not None
        assert EqualizerSlider is not None
        assert BalanceSlider is not None
        assert StatusCard is not None
        assert StackCard is not None
        assert LargeText is not None
        assert SmallText is not None
        assert LargeDualValue is not None
        assert SmallDualValue is not None
        assert TouchStrip is not None

    def test_preset_cards_importable(self):
        from deckboard import EqualizerCard, HaMediaCard, LightCard, MediaCard

        assert EqualizerCard is not None
        assert HaMediaCard is not None
        assert LightCard is not None
        assert MediaCard is not None
