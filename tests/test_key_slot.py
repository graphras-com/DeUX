"""Tests for deckboard.ui.controls.key_slot — KeySlot (Button) class."""

from __future__ import annotations

import pytest

from deckboard.ui.controls.key_slot import Button, KeySlot


class TestButtonInit:
    def test_index(self, button: Button):
        assert button.index == 0

    def test_defaults(self, button: Button):
        assert button.icon_name is None
        assert button.label is None
        assert button.image_bytes is None
        assert button.is_dirty is True

    def test_custom_index(self):
        b = Button(7)
        assert b.index == 7


class TestButtonSetIcon:
    def test_sets_icon_name(self, button: Button):
        button.set_icon("mdi:home")
        assert button.icon_name == "mdi:home"

    def test_sets_icon_color(self, button: Button):
        button.set_icon("mdi:home", color="red")
        assert button._icon_color == "red"

    def test_default_color_is_white(self, button: Button):
        button.set_icon("mdi:home")
        assert button._icon_color == "white"

    def test_marks_dirty(self, button: Button):
        button.mark_clean()
        assert button.is_dirty is False
        button.set_icon("mdi:home")
        assert button.is_dirty is True

    def test_returns_self(self, button: Button):
        result = button.set_icon("mdi:home")
        assert result is button


class TestButtonSetLabel:
    def test_sets_label(self, button: Button):
        button.set_label("Home")
        assert button.label == "Home"

    def test_set_none_removes_label(self, button: Button):
        button.set_label("Home")
        button.set_label(None)
        assert button.label is None

    def test_marks_dirty(self, button: Button):
        button.mark_clean()
        button.set_label("test")
        assert button.is_dirty is True

    def test_returns_self(self, button: Button):
        result = button.set_label("x")
        assert result is button


class TestButtonClear:
    def test_clears_icon(self, button: Button):
        button.set_icon("mdi:home")
        button.clear()
        assert button.icon_name is None

    def test_clears_label(self, button: Button):
        button.set_label("test")
        button.clear()
        assert button.label is None

    def test_clears_image_bytes(self, button: Button):
        button.set_rendered_image(b"jpeg")
        button.clear()
        assert button.image_bytes is None

    def test_marks_dirty(self, button: Button):
        button.mark_clean()
        button.clear()
        assert button.is_dirty is True

    def test_returns_self(self, button: Button):
        assert button.clear() is button


class TestButtonChaining:
    def test_chained_calls(self):
        b = Button(0)
        result = b.set_icon("mdi:home", color="red").set_label("Home")
        assert result is b
        assert b.icon_name == "mdi:home"
        assert b.label == "Home"


class TestButtonEventHandlers:
    def test_on_press_registers_handler(self, button: Button):
        async def handler():
            pass

        result = button.on_press(handler)
        assert button._press_handler is handler
        assert result is handler

    def test_on_release_registers_handler(self, button: Button):
        async def handler():
            pass

        result = button.on_release(handler)
        assert button._release_handler is handler
        assert result is handler

    def test_on_press_as_decorator(self, button: Button):
        @button.on_press
        async def handler():
            pass

        assert button._press_handler is handler

    def test_on_release_as_decorator(self, button: Button):
        @button.on_release
        async def handler():
            pass

        assert button._release_handler is handler


class TestButtonRendering:
    def test_set_rendered_image(self, button: Button):
        button.set_rendered_image(b"jpeg-data")
        assert button.image_bytes == b"jpeg-data"
        assert button.is_dirty is False

    def test_mark_clean(self, button: Button):
        assert button.is_dirty is True
        button.mark_clean()
        assert button.is_dirty is False
