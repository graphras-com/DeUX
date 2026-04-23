"""Tests for deckui.ui.controls.encoder_slot — EncoderSlot class."""

from __future__ import annotations

from deckui.ui.controls.encoder_slot import EncoderSlot


class TestEncoderSlotInit:
    def test_index(self, encoder: EncoderSlot):
        assert encoder.index == 0

    def test_no_handlers_by_default(self, encoder: EncoderSlot):
        assert encoder._turn_handler is None
        assert encoder._press_handler is None
        assert encoder._release_handler is None

    def test_custom_index(self):
        e = EncoderSlot(3)
        assert e.index == 3


class TestEncoderSlotOnTurn:
    def test_registers_handler(self, encoder: EncoderSlot):
        async def handler(direction: int):
            pass

        result = encoder.on_turn(handler)
        assert encoder._turn_handler is handler
        assert result is handler

    def test_as_decorator(self, encoder: EncoderSlot):
        @encoder.on_turn
        async def handler(direction: int):
            pass

        assert encoder._turn_handler is handler


class TestEncoderSlotOnPress:
    def test_registers_handler(self, encoder: EncoderSlot):
        async def handler():
            pass

        result = encoder.on_press(handler)
        assert encoder._press_handler is handler
        assert result is handler

    def test_as_decorator(self, encoder: EncoderSlot):
        @encoder.on_press
        async def handler():
            pass

        assert encoder._press_handler is handler


class TestEncoderSlotOnRelease:
    def test_registers_handler(self, encoder: EncoderSlot):
        async def handler():
            pass

        result = encoder.on_release(handler)
        assert encoder._release_handler is handler
        assert result is handler

    def test_as_decorator(self, encoder: EncoderSlot):
        @encoder.on_release
        async def handler():
            pass

        assert encoder._release_handler is handler
