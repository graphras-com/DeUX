"""Asyncio-based frame animator for spinner animations."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from contextlib import suppress
from typing import Any

logger = logging.getLogger(__name__)

PushFn = Callable[[bytes], Coroutine[Any, Any, None]]
"""Async callable that pushes a single image frame to the device."""


class SpinnerAnimator:
    """Drive frame-by-frame spinner animation on an asyncio event loop.

    The animator cycles through pre-rendered frames at a fixed interval,
    pushing each frame to the device via the provided *push_fn*.

    Parameters
    ----------
    frames
        List of encoded image bytes (one per frame).
    interval_ms
        Milliseconds between frame updates.
    push_fn
        Async callable ``(frame_bytes) -> None`` that sends a frame
        to the hardware.
    """

    def __init__(
        self,
        frames: list[bytes],
        interval_ms: int,
        push_fn: PushFn,
    ) -> None:
        if not frames:
            raise ValueError("frames must not be empty")
        self._frames = frames
        self._interval = interval_ms / 1000.0
        self._push_fn = push_fn
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether the animation is currently playing."""
        return self._running

    async def start(self) -> None:
        """Begin the animation loop.

        If already running, this is a no-op.
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="deux-spinner")

    async def stop(self) -> None:
        """Stop the animation loop.

        Cancels the running task and waits for it to finish.
        """
        if not self._running:
            return
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        """Cycle through frames at the configured interval."""
        idx = 0
        n = len(self._frames)
        try:
            while self._running:
                frame = self._frames[idx % n]
                try:
                    await self._push_fn(frame)
                except Exception:
                    logger.exception("Error pushing spinner frame")
                idx += 1
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            pass
