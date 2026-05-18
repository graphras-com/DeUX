"""DialAccumulator: debounce rapid dial/encoder ticks into a single callback."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class DialAccumulator:
    """Debounce rapid dial/encoder ticks and flush them with a single callback.

    *callback*   - ``async def callback(steps: int)`` called once per flush
                   with the net accumulated tick count (signed).
    *delay*      - seconds to wait after the last tick before flushing.
    *max_steps*  - cap on how many ticks can accumulate (positive number).
                   Use ``max_steps=1`` to collapse any number of ticks into
                   a single +1 / -1 event (useful for next/previous).

    Examples
    --------
    ::

        acc = DialAccumulator(my_handler, delay=0.2, max_steps=5)

        @encoder.on_turn
        async def on_turn(direction: int):
            acc.tick(direction)
    """

    def __init__(
        self,
        callback: Callable[[int], Awaitable[None]],
        *,
        delay: float = 0.25,
        max_steps: int = 10,
    ) -> None:
        if delay <= 0:
            msg = "delay must be positive"
            raise ValueError(msg)
        if max_steps < 1:
            msg = "max_steps must be >= 1"
            raise ValueError(msg)
        logger.debug("DialAccumulator.__init__: delay=%.2f max_steps=%d", delay, max_steps)
        self._callback = callback
        self._delay = delay
        self._max_steps = max_steps
        self._pending: int = 0
        self._flush_task: asyncio.Task[None] | None = None

    def tick(self, direction: int) -> None:
        """Add *direction* (+1 or -1). Clamps to ±max_steps.

        Cancels and awaits any previously scheduled flush task before
        creating a new one, preventing orphaned task accumulation.
        """
        logger.debug("DialAccumulator.tick: direction=%+d pending=%d", direction, self._pending)
        self._pending = max(-self._max_steps, min(self._max_steps, self._pending + direction))
        old_task = self._flush_task
        self._flush_task = asyncio.create_task(self._schedule_flush(old_task))

    async def _schedule_flush(self, old_task: asyncio.Task[None] | None) -> None:
        """Wait for the debounce delay, then flush accumulated ticks.

        Parameters
        ----------
        old_task : asyncio.Task[None] | None
            The previously scheduled flush task to cancel and await
            before starting the new debounce timer.
        """
        if old_task is not None:
            old_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await old_task
        try:
            logger.debug("DialAccumulator._schedule_flush: waiting %.2fs", self._delay)
            await asyncio.sleep(self._delay)
            await self._flush()
        except asyncio.CancelledError:
            pass

    async def _flush(self) -> None:
        """Invoke the callback with the net accumulated steps and reset."""
        steps = self._pending
        self._pending = 0
        self._flush_task = None
        logger.debug("DialAccumulator._flush: steps=%+d", steps)
        if steps == 0:
            return
        await self._callback(steps)

    async def cancel(self) -> None:
        """Cancel any pending flush and reset the accumulated count.

        Awaits the task's cancellation to ensure the flush handler has
        fully stopped before returning.
        """
        if self._flush_task is not None:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
            self._flush_task = None
        self._pending = 0
        logger.debug("DialAccumulator.cancel: reset")
