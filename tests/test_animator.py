"""Tests for deux.dui.animator — SpinnerAnimator class."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from deux.dui.animator import DeviceUnavailable, SpinnerAnimator


class TestSpinnerAnimatorLifecycle:
    async def test_start_stop_lifecycle(self):
        push_fn = AsyncMock()
        animator = SpinnerAnimator(frames=[b"a", b"b"], interval_ms=50, push_fn=push_fn)

        await animator.start()
        assert animator.is_running is True

        await asyncio.sleep(0.12)
        await animator.stop()
        assert animator.is_running is False
        assert push_fn.await_count >= 1

    async def test_is_running_property(self):
        push_fn = AsyncMock()
        animator = SpinnerAnimator(frames=[b"a"], interval_ms=50, push_fn=push_fn)
        assert animator.is_running is False

        await animator.start()
        assert animator.is_running is True

        await animator.stop()
        assert animator.is_running is False

    async def test_frames_are_pushed(self):
        """Verify push_fn is called with frame bytes."""
        push_fn = AsyncMock()
        frames = [b"frame0", b"frame1"]
        animator = SpinnerAnimator(frames=frames, interval_ms=20, push_fn=push_fn)

        await animator.start()
        await asyncio.sleep(0.08)
        await animator.stop()

        assert push_fn.await_count >= 2
        # First call should be frame0
        push_fn.assert_any_await(b"frame0")

    async def test_stop_when_not_running_is_noop(self):
        push_fn = AsyncMock()
        animator = SpinnerAnimator(frames=[b"a"], interval_ms=50, push_fn=push_fn)
        # Should not raise
        await animator.stop()
        assert animator.is_running is False

    async def test_start_when_already_running_is_noop(self):
        push_fn = AsyncMock()
        animator = SpinnerAnimator(frames=[b"a"], interval_ms=50, push_fn=push_fn)

        await animator.start()
        task1 = animator._task
        await animator.start()  # no-op
        task2 = animator._task
        assert task1 is task2

        await animator.stop()

    def test_empty_frames_raises(self):
        push_fn = AsyncMock()
        with pytest.raises(ValueError, match="must not be empty"):
            SpinnerAnimator(frames=[], interval_ms=50, push_fn=push_fn)


class TestSpinnerAnimatorErrors:
    async def test_device_unavailable_stops_loop(self):
        """A push raising DeviceUnavailable terminates the loop quietly."""
        calls = 0

        async def push_fn(_frame: bytes) -> None:
            nonlocal calls
            calls += 1
            raise DeviceUnavailable("device gone")

        animator = SpinnerAnimator(
            frames=[b"a", b"b"], interval_ms=5, push_fn=push_fn
        )
        await animator.start()
        # Give the loop time to attempt one push and exit.
        await asyncio.sleep(0.05)
        assert animator.is_running is False
        # Only one push should be attempted before the loop bails out.
        assert calls == 1
        # stop() must be idempotent / safe after self-termination.
        await animator.stop()

    async def test_generic_exception_keeps_loop_running(self):
        """Non-DeviceUnavailable errors are logged and looping continues."""
        calls = 0

        async def push_fn(_frame: bytes) -> None:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("transient")

        animator = SpinnerAnimator(
            frames=[b"a"], interval_ms=10, push_fn=push_fn
        )
        await animator.start()
        await asyncio.sleep(0.1)
        await animator.stop()
        assert calls >= 3
