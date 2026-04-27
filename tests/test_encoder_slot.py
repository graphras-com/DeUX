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
        assert encoder._press_turn_handler is None

    def test_custom_index(self):
        e = EncoderSlot(3)
        assert e.index == 3

    def test_no_accumulator_by_default(self, encoder: EncoderSlot):
        assert encoder._accumulator is None
        assert encoder._press_turn_accumulator is None

    def test_not_pressed_by_default(self, encoder: EncoderSlot):
        assert encoder._pressed is False


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


class TestEncoderSlotOnPressTurn:
    def test_registers_handler(self, encoder: EncoderSlot):
        async def handler(direction: int):
            pass

        result = encoder.on_press_turn(handler)
        assert encoder._press_turn_handler is handler
        assert result is handler

    def test_as_decorator(self, encoder: EncoderSlot):
        @encoder.on_press_turn
        async def handler(direction: int):
            pass

        assert encoder._press_turn_handler is handler

    async def test_fires_when_pressed(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_press_turn
        async def handle(direction: int):
            results.append(direction)

        await encoder.dispatch_press(True)
        await encoder.dispatch_turn(1)
        assert results == [1]

    async def test_does_not_fire_when_not_pressed(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_press_turn
        async def handle(direction: int):
            results.append(direction)

        await encoder.dispatch_turn(1)
        assert results == []

    async def test_does_not_fire_after_release(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_press_turn
        async def handle(direction: int):
            results.append(direction)

        await encoder.dispatch_press(True)
        await encoder.dispatch_press(False)
        await encoder.dispatch_turn(1)
        assert results == []

    async def test_takes_priority_over_on_turn(self, encoder: EncoderSlot):
        """When pressed and press_turn handler exists, on_turn does not fire."""
        turn_results: list[int] = []
        press_turn_results: list[int] = []

        @encoder.on_turn
        async def on_turn(direction: int):
            turn_results.append(direction)

        @encoder.on_press_turn
        async def on_press_turn(direction: int):
            press_turn_results.append(direction)

        await encoder.dispatch_press(True)
        await encoder.dispatch_turn(1)
        assert press_turn_results == [1]
        assert turn_results == []

    async def test_on_turn_fires_when_not_pressed(self, encoder: EncoderSlot):
        """When not pressed, on_turn fires even if press_turn is registered."""
        turn_results: list[int] = []

        @encoder.on_turn
        async def on_turn(direction: int):
            turn_results.append(direction)

        @encoder.on_press_turn
        async def on_press_turn(direction: int):
            pass

        await encoder.dispatch_turn(1)
        assert turn_results == [1]

    async def test_fallback_to_on_turn_when_no_press_turn_handler(self, encoder: EncoderSlot):
        """When pressed but no press_turn handler, on_turn fires as fallback."""
        turn_results: list[int] = []

        @encoder.on_turn
        async def on_turn(direction: int):
            turn_results.append(direction)

        await encoder.dispatch_press(True)
        await encoder.dispatch_turn(1)
        assert turn_results == [1]


class TestEncoderSlotOnPressTurnAccumulated:
    def test_plain_decorator(self, encoder: EncoderSlot):
        @encoder.on_press_turn_accumulated
        async def handle(steps: int):
            pass

        assert isinstance(handle, DialAccumulator)
        assert encoder._press_turn_accumulator is handle
        assert encoder._press_turn_handler is not None

    def test_decorator_with_options(self, encoder: EncoderSlot):
        @encoder.on_press_turn_accumulated(delay=0.1, max_steps=3)
        async def handle(steps: int):
            pass

        assert isinstance(handle, DialAccumulator)
        assert handle._delay == 0.1
        assert handle._max_steps == 3

    async def test_accumulates_while_pressed(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_press_turn_accumulated(delay=0.05)
        async def handle(steps: int):
            results.append(steps)

        await encoder.dispatch_press(True)
        await encoder.dispatch_turn(1)
        await encoder.dispatch_turn(1)
        await encoder.dispatch_turn(1)
        await asyncio.sleep(0.1)
        assert results == [3]

    async def test_does_not_fire_when_not_pressed(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_press_turn_accumulated(delay=0.05)
        async def handle(steps: int):
            results.append(steps)

        await encoder.dispatch_turn(1)
        await asyncio.sleep(0.1)
        assert results == []

    async def test_cancel_via_instance(self, encoder: EncoderSlot):
        results: list[int] = []

        @encoder.on_press_turn_accumulated(delay=0.05)
        async def handle(steps: int):
            results.append(steps)

        await encoder.dispatch_press(True)
        await encoder.dispatch_turn(1)
        assert isinstance(handle, DialAccumulator)
        handle.cancel()
        await asyncio.sleep(0.1)
        assert results == []


class TestEncoderSlotDispatchPress:
    async def test_tracks_pressed_state(self, encoder: EncoderSlot):
        assert encoder._pressed is False
        await encoder.dispatch_press(True)
        assert encoder._pressed is True
        await encoder.dispatch_press(False)
        assert encoder._pressed is False

    async def test_calls_press_handler(self, encoder: EncoderSlot):
        called: list[bool] = []

        @encoder.on_press
        async def handle():
            called.append(True)

        await encoder.dispatch_press(True)
        assert called == [True]

    async def test_calls_release_handler(self, encoder: EncoderSlot):
        called: list[bool] = []

        @encoder.on_release
        async def handle():
            called.append(True)

        await encoder.dispatch_press(False)
        assert called == [True]


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
