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
            "Button",
            "Card",
            "Control",
            "Deck",
            "DeckError",
            "DeckEvent",
            "DeviceInfo",
            "Dial",
            "DialPressEvent",
            "DialTurnEvent",
            "Element",
            "EncoderSlot",
            "EqualizerSlider",
            "EqualizerWidget",
            "EventType",
            "IconError",
            "IconManager",
            "IconWidget",
            "KeySlot",
            "KelvinSlider",
            "KeyEvent",
            "LargeDualValue",
            "LargeSlider",
            "LargeText",
            "MediaWidget",
            "Page",
            "RangeControl",
            "Screen",
            "Slider",
            "SliderWidget",
            "SmallDualValue",
            "SmallSlider",
            "SmallText",
            "StackCard",
            "StatusCard",
            "TemperatureSlider",
            "TouchEvent",
            "TouchPanel",
            "TouchScreen",
            "TouchStrip",
            "VolumeSlider",
            "Widget",
        }
        assert set(deckboard.__all__) == expected

    def test_button_importable(self):
        from deckboard import Button

        assert Button is not None

    def test_deck_importable(self):
        from deckboard import Deck

        assert Deck is not None

    def test_deck_error_importable(self):
        from deckboard import DeckError

        assert DeckError is not None

    def test_dial_importable(self):
        from deckboard import Dial

        assert Dial is not None

    def test_event_types_importable(self):
        from deckboard import (
            DeckEvent,
            DialPressEvent,
            DialTurnEvent,
            EventType,
            KeyEvent,
            TouchEvent,
        )

        assert KeyEvent is not None
        assert DialTurnEvent is not None
        assert DialPressEvent is not None
        assert TouchEvent is not None
        assert EventType is not None

    def test_icon_importable(self):
        from deckboard import IconError, IconManager

        assert IconManager is not None
        assert IconError is not None

    def test_page_importable(self):
        from deckboard import Page, Screen

        assert Page is not None
        assert Screen is not None

    def test_touchscreen_importable(self):
        from deckboard import Card, TouchScreen, TouchStrip, Widget

        assert TouchScreen is not None
        assert TouchStrip is not None
        assert Widget is not None
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
            IconWidget,
            KeySlot,
            KelvinSlider,
            LargeSlider,
            LargeText,
            RangeControl,
            Screen,
            Slider,
            SliderWidget,
            SmallSlider,
            SmallText,
            StackCard,
            StatusCard,
            TemperatureSlider,
            TouchPanel,
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
        assert IconWidget is not None
        assert StatusCard is not None
        assert SliderWidget is not None
        assert TouchPanel is not None
        assert StackCard is not None
        assert LargeText is not None
        assert SmallText is not None
