"""Tests for deckui.ui.controls.encoder_slot — EncoderSlot class."""

from __future__ import annotations

import asyncio

from deckui.ui.controls.dial_accumulator import DialAccumulator
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

    def test_no_accumulator_by_default(self, encoder: EncoderSlot):
        assert encoder._accumulator is None


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


class TestEncoderSlotOnTurnAccumulated:
    def test_plain_decorator(self, encoder: EncoderSlot):
        @encoder.on_turn_accumulated
        async def handle(steps: int):
            pass

        assert isinstance(handle, DialAccumulator)
        assert encoder._accumulator is handle
        assert encoder._turn_handler is not None

    def test_decorator_with_options(self, encoder: EncoderSlot):
        @encoder.on_turn_accumulated(delay=0.1, max_steps=5)
        async def handle(steps: int):
            pass

        assert isinstance(handle, DialAccumulator)
        assert handle._delay == 0.1
        assert handle._max_steps == 5

    async def test_dispatch_turn_triggers_accumulator(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_turn_accumulated(delay=0.05)
        async def handle(steps: int):
            results.append(steps)

        await encoder.dispatch_turn(1)
        await encoder.dispatch_turn(1)
        await encoder.dispatch_turn(1)
        await asyncio.sleep(0.1)
        assert results == [3]

    async def test_accumulator_clamps(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_turn_accumulated(delay=0.05, max_steps=2)
        async def handle(steps: int):
            results.append(steps)

        for _ in range(10):
            await encoder.dispatch_turn(1)
        await asyncio.sleep(0.1)
        assert results == [2]

    async def test_accumulator_cancel_via_instance(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_turn_accumulated(delay=0.05)
        async def handle(steps: int):
            results.append(steps)

        await encoder.dispatch_turn(1)
        assert isinstance(handle, DialAccumulator)
        handle.cancel()
        await asyncio.sleep(0.1)
        assert results == []


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
