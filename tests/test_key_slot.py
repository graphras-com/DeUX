"""Tests for deckui.ui.controls.key_slot — KeySlot class."""

from __future__ import annotations

import pytest

from deckui.ui.controls.key_slot import KeySlot


class TestKeySlotInit:
    def test_index(self, key_slot: KeySlot):
        assert key_slot.index == 0

    def test_defaults(self, key_slot: KeySlot):
        assert key_slot.image_bytes is None
        assert key_slot.is_dirty is True

    def test_custom_index(self):
        k = KeySlot(7)
        assert k.index == 7


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
