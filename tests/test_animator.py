"""Tests for deckui.dui.animator — SpinnerAnimator class."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from deckui.dui.animator import SpinnerAnimator


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
