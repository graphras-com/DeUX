"""Tests for DialAccumulator."""

from __future__ import annotations

import asyncio

import pytest

from deux.ui.controls.dial_accumulator import DialAccumulator


class TestDialAccumulatorInit:
    """Constructor validation."""

    def test_invalid_delay_raises(self) -> None:
        async def cb(steps: int) -> None:
            pass

        with pytest.raises(ValueError, match="delay must be positive"):
            DialAccumulator(cb, delay=0)

    def test_invalid_max_steps_raises(self) -> None:
        async def cb(steps: int) -> None:
            pass

        with pytest.raises(ValueError, match="max_steps must be >= 1"):
            DialAccumulator(cb, max_steps=0)


class TestDialAccumulatorTick:
    """Core tick / flush behaviour."""

    async def test_single_tick_flushes_after_delay(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05)
        acc.tick(1)
        await asyncio.sleep(0.1)
        assert results == [1]

    async def test_multiple_ticks_accumulate(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05)
        acc.tick(1)
        acc.tick(1)
        acc.tick(1)
        await asyncio.sleep(0.1)
        assert results == [3]

    async def test_opposite_ticks_cancel_out(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05)
        acc.tick(1)
        acc.tick(-1)
        await asyncio.sleep(0.1)
        # Net is zero — callback should not fire
        assert results == []

    async def test_negative_ticks(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05)
        acc.tick(-1)
        acc.tick(-1)
        await asyncio.sleep(0.1)
        assert results == [-2]

    async def test_clamps_to_max_steps(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05, max_steps=3)
        for _ in range(10):
            acc.tick(1)
        await asyncio.sleep(0.1)
        assert results == [3]

    async def test_clamps_negative_to_max_steps(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05, max_steps=3)
        for _ in range(10):
            acc.tick(-1)
        await asyncio.sleep(0.1)
        assert results == [-3]

    async def test_max_steps_one_collapses(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05, max_steps=1)
        acc.tick(1)
        acc.tick(1)
        acc.tick(1)
        await asyncio.sleep(0.1)
        assert results == [1]

    async def test_debounce_resets_timer(self) -> None:
        """Ticks spaced within the delay window should still accumulate."""
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.1)
        acc.tick(1)
        await asyncio.sleep(0.05)
        acc.tick(1)
        await asyncio.sleep(0.05)
        # Should not have flushed yet (timer restarted)
        assert results == []
        await asyncio.sleep(0.1)
        assert results == [2]


class TestDialAccumulatorCancel:
    """cancel() behaviour."""

    async def test_cancel_prevents_flush(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05)
        acc.tick(1)
        acc.cancel()
        await asyncio.sleep(0.1)
        assert results == []

    async def test_cancel_resets_pending(self) -> None:
        results: list[int] = []

        async def cb(steps: int) -> None:
            results.append(steps)

        acc = DialAccumulator(cb, delay=0.05)
        acc.tick(1)
        acc.tick(1)
        acc.cancel()
        # New tick after cancel should only have its own value
        acc.tick(-1)
        await asyncio.sleep(0.1)
        assert results == [-1]

    async def test_cancel_when_idle_is_noop(self) -> None:
        async def cb(steps: int) -> None:
            pass

        acc = DialAccumulator(cb, delay=0.05)
        acc.cancel()  # should not raise
