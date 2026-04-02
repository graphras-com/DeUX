"""Tests for deckboard.dial — Dial class."""

from __future__ import annotations

from deckboard.dial import Dial


class TestDialInit:
    def test_index(self, dial: Dial):
        assert dial.index == 0

    def test_no_handlers_by_default(self, dial: Dial):
        assert dial._turn_handler is None
        assert dial._press_handler is None
        assert dial._release_handler is None

    def test_custom_index(self):
        d = Dial(3)
        assert d.index == 3


class TestDialOnTurn:
    def test_registers_handler(self, dial: Dial):
        async def handler(direction: int):
            pass

        result = dial.on_turn(handler)
        assert dial._turn_handler is handler
        assert result is handler

    def test_as_decorator(self, dial: Dial):
        @dial.on_turn
        async def handler(direction: int):
            pass

        assert dial._turn_handler is handler


class TestDialOnPress:
    def test_registers_handler(self, dial: Dial):
        async def handler():
            pass

        result = dial.on_press(handler)
        assert dial._press_handler is handler
        assert result is handler

    def test_as_decorator(self, dial: Dial):
        @dial.on_press
        async def handler():
            pass

        assert dial._press_handler is handler


class TestDialOnRelease:
    def test_registers_handler(self, dial: Dial):
        async def handler():
            pass

        result = dial.on_release(handler)
        assert dial._release_handler is handler
        assert result is handler

    def test_as_decorator(self, dial: Dial):
        @dial.on_release
        async def handler():
            pass

        assert dial._release_handler is handler
