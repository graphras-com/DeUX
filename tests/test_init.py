"""Tests for deux.__init__ — public API surface."""

from __future__ import annotations

import deux


class TestPublicAPI:
    def test_version(self):
        assert isinstance(deux.__version__, str)
        assert len(deux.__version__) > 0

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
            "DuiRepository",
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
            "SSRFError",
            "Screen",
            "SurfaceBackgrounds",
            "SvgRasterizer",
            "Theme",
            "TouchEvent",
            "TouchStrip",
            "add_dui_path",
            "clear_dui_cache",
            "clear_image_cache",
            "fetch_image",
            "get_active_theme",
            "get_default_backgrounds",
            "get_default_font_family",
            "get_svg_backend",
            "get_svg_stylesheet",
            "list_devices",
            "list_dui_packages",
            "list_supported_devices",
            "list_svg_backends",
            "load_all_packages",
            "load_package",
            "load_svg_stylesheet",
            "register_svg_backend",
            "remove_dui_path",
            "resolve_dui",
            "set_active_theme",
            "set_allow_private_urls",
            "set_svg_backend",
            "set_svg_stylesheet",
        }
        assert set(deux.__all__) == expected

    def test_key_slot_importable(self):
        from deux import KeySlot

        assert KeySlot is not None

    def test_deck_error_importable(self):
        from deux import DeckError

        assert DeckError is not None

    def test_encoder_slot_importable(self):
        from deux import EncoderSlot

        assert EncoderSlot is not None

    def test_event_types_importable(self):
        from deux import (
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
        from deux import Screen

        assert Screen is not None

    def test_touchscreen_importable(self):
        from deux import Card, TouchStrip

        assert TouchStrip is not None
        assert Card is not None

    def test_device_info_importable(self):
        from deux import DeviceInfo

        assert DeviceInfo is not None

    def test_dui_importable(self):
        from deux import (
            DuiCard,
            DuiKey,
            DuiRepository,
            PackageError,
            PackageSpec,
            add_dui_path,
            clear_dui_cache,
            list_dui_packages,
            load_all_packages,
            load_package,
            remove_dui_path,
            resolve_dui,
        )

        assert DuiCard is not None
        assert DuiKey is not None
        assert DuiRepository is not None
        assert PackageError is not None
        assert PackageSpec is not None
        assert add_dui_path is not None
        assert clear_dui_cache is not None
        assert list_dui_packages is not None
        assert load_all_packages is not None
        assert load_package is not None
        assert remove_dui_path is not None
        assert resolve_dui is not None

    def test_blank_card_importable(self):
        from deux import BlankCard

        assert BlankCard is not None

    def test_core_ui_importable(self):
        from deux import (
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
        from deux import DeviceCapabilities, InfoScreen, RenderMetrics

        assert DeviceCapabilities is not None
        assert InfoScreen is not None
        assert RenderMetrics is not None

    def test_async_event_importable(self):
        from deux import AsyncEvent

        assert AsyncEvent is not None

    def test_deck_importable(self):
        from deux import Deck

        assert Deck is not None

    def test_controllers_importable(self):
        from deux import CardController, KeyController

        assert CardController is not None
        assert KeyController is not None
