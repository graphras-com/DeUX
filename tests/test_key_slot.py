"""Tests for deckboard.ui.controls.key_slot — KeySlot class."""

from __future__ import annotations

import pytest

from deckboard.ui.controls.key_slot import KeySlot


class TestKeySlotInit:
    def test_index(self, key_slot: KeySlot):
        assert key_slot.index == 0

    def test_defaults(self, key_slot: KeySlot):
        assert key_slot.icon_name is None
        assert key_slot.label is None
        assert key_slot.image_bytes is None
        assert key_slot.is_dirty is True

    def test_custom_index(self):
        k = KeySlot(7)
        assert k.index == 7


class TestKeySlotSetIcon:
    def test_sets_icon_name(self, key_slot: KeySlot):
        key_slot.set_icon("mdi:home")
        assert key_slot.icon_name == "mdi:home"

    def test_sets_icon_color(self, key_slot: KeySlot):
        key_slot.set_icon("mdi:home", color="red")
        assert key_slot._icon_color == "red"

    def test_default_color_is_white(self, key_slot: KeySlot):
        key_slot.set_icon("mdi:home")
        assert key_slot._icon_color == "white"

    def test_marks_dirty(self, key_slot: KeySlot):
        key_slot.mark_clean()
        assert key_slot.is_dirty is False
        key_slot.set_icon("mdi:home")
        assert key_slot.is_dirty is True

    def test_returns_self(self, key_slot: KeySlot):
        result = key_slot.set_icon("mdi:home")
        assert result is key_slot


class TestKeySlotSetLabel:
    def test_sets_label(self, key_slot: KeySlot):
        key_slot.set_label("Home")
        assert key_slot.label == "Home"

    def test_set_none_removes_label(self, key_slot: KeySlot):
        key_slot.set_label("Home")
        key_slot.set_label(None)
        assert key_slot.label is None

    def test_marks_dirty(self, key_slot: KeySlot):
        key_slot.mark_clean()
        key_slot.set_label("test")
        assert key_slot.is_dirty is True

    def test_returns_self(self, key_slot: KeySlot):
        result = key_slot.set_label("x")
        assert result is key_slot


class TestKeySlotClear:
    def test_clears_icon(self, key_slot: KeySlot):
        key_slot.set_icon("mdi:home")
        key_slot.clear()
        assert key_slot.icon_name is None

    def test_clears_label(self, key_slot: KeySlot):
        key_slot.set_label("test")
        key_slot.clear()
        assert key_slot.label is None

    def test_clears_image_bytes(self, key_slot: KeySlot):
        key_slot.set_rendered_image(b"jpeg")
        key_slot.clear()
        assert key_slot.image_bytes is None

    def test_marks_dirty(self, key_slot: KeySlot):
        key_slot.mark_clean()
        key_slot.clear()
        assert key_slot.is_dirty is True

    def test_returns_self(self, key_slot: KeySlot):
        assert key_slot.clear() is key_slot


class TestKeySlotChaining:
    def test_chained_calls(self):
        k = KeySlot(0)
        result = k.set_icon("mdi:home", color="red").set_label("Home")
        assert result is k
        assert k.icon_name == "mdi:home"
        assert k.label == "Home"


class TestKeySlotEventHandlers:
    def test_on_press_registers_handler(self, key_slot: KeySlot):
        async def handler():
            pass

        result = key_slot.on_press(handler)
        assert key_slot._press_handler is handler
        assert result is handler

    def test_on_release_registers_handler(self, key_slot: KeySlot):
        async def handler():
            pass

        result = key_slot.on_release(handler)
        assert key_slot._release_handler is handler
        assert result is handler

    def test_on_press_as_decorator(self, key_slot: KeySlot):
        @key_slot.on_press
        async def handler():
            pass

        assert key_slot._press_handler is handler

    def test_on_release_as_decorator(self, key_slot: KeySlot):
        @key_slot.on_release
        async def handler():
            pass

        assert key_slot._release_handler is handler


class TestKeySlotRendering:
    def test_set_rendered_image(self, key_slot: KeySlot):
        key_slot.set_rendered_image(b"jpeg-data")
        assert key_slot.image_bytes == b"jpeg-data"
        assert key_slot.is_dirty is False

    def test_mark_clean(self, key_slot: KeySlot):
        assert key_slot.is_dirty is True
        key_slot.mark_clean()
        assert key_slot.is_dirty is False
