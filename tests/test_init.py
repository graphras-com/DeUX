"""Tests for deckboard.__init__ — public API surface."""

from __future__ import annotations

import deckboard


class TestPublicAPI:
    def test_version(self):
        assert deckboard.__version__ == "0.1.0"

    def test_all_exports(self):
        expected = {
            "Button",
            "Deck",
            "DeckError",
            "DeckEvent",
            "DeviceInfo",
            "Dial",
            "DialPressEvent",
            "DialTurnEvent",
            "EventType",
            "IconError",
            "IconManager",
            "KeyEvent",
            "Page",
            "TouchEvent",
            "TouchScreen",
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
        from deckboard import Page

        assert Page is not None

    def test_touchscreen_importable(self):
        from deckboard import TouchScreen, Widget

        assert TouchScreen is not None
        assert Widget is not None

    def test_device_info_importable(self):
        from deckboard import DeviceInfo

        assert DeviceInfo is not None
