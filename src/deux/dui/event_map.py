"""Physical-to-semantic event routing for .dui packages."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from ..ui.controls.dial_accumulator import DialAccumulator
from .schema import DEFAULT_RELEASE_TURN_GRACE_MS

if TYPE_CHECKING:
    from ..runtime.events import AsyncHandler, EventType
    from .schema import EventMapping, Region

logger = logging.getLogger(__name__)


class EventMap:
    """Map physical hardware events to named semantic events.

    Handles simple mappings (encoder_press → semantic name) as well as
    compound gestures:

    - ``encoder_press_release``: fires only if the press duration is
      within ``max_duration_ms``.
    - ``encoder_hold`` / ``key_hold``: starts a timer on press and fires
      the handler after ``hold_ms`` while the key/encoder is still held.
      Suppresses any ``press_release`` or ``release`` event for that
      press–release cycle.
    - ``encoder_turn``: fires turn events only while the encoder is
      **not** pressed.  Turning while pressed never falls through to
      this mapping.  Immediately after releasing a press cycle that
      included at least one turn, ``encoder_turn`` is suppressed for
      ``release_turn_grace_ms`` to debounce the spurious tick a finger
      often produces while lifting off the dial.
    - ``encoder_press_turn``: fires turn events only while the encoder
      is held down.  When declared with a direction filter, mismatching
      turns while pressed are silent — there is no fallback to
      ``encoder_turn``.  Any turn while pressed cancels a pending
      ``encoder_hold`` regardless of whether a handler fires.
    - Direction filtering: ``encoder_turn`` with ``direction: left``
      only fires for counter-clockwise turns.

    Parameters
    ----------
    events
        Event mappings from the package manifest.
    regions
        Touch regions from the package manifest.
    release_turn_grace_ms
        Suppression window (in milliseconds) applied to plain
        ``encoder_turn`` events immediately after the encoder is released
        following a press cycle that included at least one turn.  Defaults
        to :data:`~deux.dui.schema.DEFAULT_RELEASE_TURN_GRACE_MS`.  Pass
        ``0`` to disable.
    """

    def __init__(
        self,
        events: tuple[EventMapping, ...],
        regions: tuple[Region, ...] = (),
        release_turn_grace_ms: int = DEFAULT_RELEASE_TURN_GRACE_MS,
    ) -> None:
        self._mappings = events
        self._regions = regions
        self._handlers: dict[str, AsyncHandler] = {}

        self._press_time: float | None = None
        self._pressed = False

        self._hold_task: asyncio.Task[None] | None = None
        self._hold_fired = False

        self._press_had_turn = False
        self._release_turn_grace_s = max(0, release_turn_grace_ms) / 1000.0
        self._turn_suppressed_until = 0.0

        self._by_source: dict[str, list[EventMapping]] = {}
        for mapping in events:
            self._by_source.setdefault(mapping.source, []).append(mapping)

        self._accumulators: dict[str, DialAccumulator] = {}

    def on(self, event_name: str, handler: AsyncHandler) -> None:
        """Register a handler for a named semantic event.

        Parameters
        ----------
        event_name
            The semantic event name (as defined in the manifest).
        handler
            An async callable to invoke when the event fires.
            For accumulated events the handler signature must accept
            a single ``int`` argument (the net accumulated steps).

        Raises
        ------
        KeyError
            If *event_name* is not defined in the manifest.
        """
        known = {m.name for m in self._mappings}
        if event_name not in known:
            raise KeyError(
                f"Unknown event '{event_name}'. Defined events: {sorted(known)}"
            )

        mapping = next(m for m in self._mappings if m.name == event_name)
        if mapping.accumulate:
            kwargs: dict[str, Any] = {}
            if mapping.accumulate_delay is not None:
                kwargs["delay"] = mapping.accumulate_delay
            if mapping.accumulate_max_steps is not None:
                kwargs["max_steps"] = mapping.accumulate_max_steps
            self._accumulators[event_name] = DialAccumulator(handler, **kwargs)

        self._handlers[event_name] = handler

    @property
    def event_names(self) -> list[str]:
        """All semantic event names defined in this map."""
        return [m.name for m in self._mappings]

    def _start_hold_timer(self, source: str) -> None:
        """Start a hold timer for the first matching hold mapping.

        Parameters
        ----------
        source
            ``"key_hold"`` or ``"encoder_hold"``.
        """
        for mapping in self._by_source.get(source, []):
            handler = self._handlers.get(mapping.name)
            if handler is None:
                continue
            hold_ms = mapping.hold_ms
            if hold_ms is None:
                continue  # pragma: no cover — validated by loader
            self._hold_task = asyncio.create_task(
                self._hold_delay(hold_ms / 1000.0, handler),
                name="dui-hold-timer",
            )
            return

    async def _hold_delay(self, seconds: float, handler: AsyncHandler) -> None:
        """Sleep then fire the hold handler if still pressed.

        Detaches ``_hold_task`` before invoking the handler so that a
        subsequent encoder release does not cancel the in-flight handler
        via :meth:`_cancel_hold_timer`.
        """
        await asyncio.sleep(seconds)
        if self._pressed:
            self._hold_fired = True
            self._hold_task = None
            try:
                await handler()
            except Exception:
                logger.exception("Hold-timer handler raised an exception")

    def _cancel_hold_timer(self) -> None:
        """Cancel an in-progress hold timer if one is running."""
        if self._hold_task is not None:
            self._hold_task.cancel()
            self._hold_task = None

    async def cancel_accumulators(self) -> None:
        """Cancel all active dial accumulators and discard pending ticks."""
        for acc in self._accumulators.values():
            await acc.cancel()

    def handle_encoder_turn(self, direction: int) -> AsyncHandler | None:
        """Match an encoder turn to a semantic event.

        Parameters
        ----------
        direction
            Positive for clockwise, negative for counter-clockwise.

        Returns
        -------
        AsyncHandler or None
            The matched handler, or ``None`` if no mapping matched.
            For accumulated events this returns ``None`` because the
            tick is forwarded to the :class:`DialAccumulator` which
            schedules its own async flush.
        """
        if self._pressed:
            self._cancel_hold_timer()
            self._press_had_turn = True

            for mapping in self._by_source.get("encoder_press_turn", []):
                if self._direction_matches(mapping, direction):
                    acc = self._accumulators.get(mapping.name)
                    if acc is not None:
                        acc.tick(direction)
                        return None
                    h = self._handlers.get(mapping.name)
                    if h is not None:
                        return h
            return None

        if time.monotonic() < self._turn_suppressed_until:
            return None

        for mapping in self._by_source.get("encoder_turn", []):
            if self._direction_matches(mapping, direction):
                acc = self._accumulators.get(mapping.name)
                if acc is not None:
                    acc.tick(direction)
                    return None
                h = self._handlers.get(mapping.name)
                if h is not None:
                    return h

        return None

    def handle_encoder_press(self) -> list[AsyncHandler]:
        """Match an encoder press to semantic events.

        Records the press timestamp for gesture detection and starts
        a hold timer if an ``encoder_hold`` mapping exists.

        Returns
        -------
        list[AsyncHandler]
            A list of matched handlers (may be empty).
        """
        self._press_time = time.monotonic()
        self._pressed = True
        self._hold_fired = False
        self._press_had_turn = False

        self._start_hold_timer("encoder_hold")

        handlers: list[AsyncHandler] = []
        for mapping in self._by_source.get("encoder_press", []):
            handler = self._handlers.get(mapping.name)
            if handler is not None:
                handlers.append(handler)
        return handlers

    def handle_encoder_release(self) -> list[AsyncHandler]:
        """Match an encoder release to semantic events.

        Cancels any running hold timer.  The simple ``encoder_release``
        event always fires regardless of whether a hold fired.
        ``encoder_press_release`` is suppressed when a hold already
        fired for this press–release cycle (since the interaction was
        a hold, not a press-release gesture).

        If at least one turn occurred during the press cycle, opens a
        ``release_turn_grace_ms`` window during which subsequent plain
        ``encoder_turn`` events are ignored.

        Returns
        -------
        list[AsyncHandler]
            A list of matched handlers (may be empty).
        """
        self._pressed = False
        self._cancel_hold_timer()

        hold_fired = self._hold_fired
        self._hold_fired = False

        if self._press_had_turn and self._release_turn_grace_s > 0:
            self._turn_suppressed_until = (
                time.monotonic() + self._release_turn_grace_s
            )
        self._press_had_turn = False

        handlers: list[AsyncHandler] = []

        if not hold_fired and self._press_time is not None:
            elapsed_ms = (time.monotonic() - self._press_time) * 1000

            for mapping in self._by_source.get("encoder_press_release", []):
                max_ms = mapping.max_duration_ms
                if max_ms is None or elapsed_ms <= max_ms:
                    handler = self._handlers.get(mapping.name)
                    if handler is not None:
                        handlers.append(handler)

        self._press_time = None

        for mapping in self._by_source.get("encoder_release", []):
            handler = self._handlers.get(mapping.name)
            if handler is not None:
                handlers.append(handler)

        return handlers

    def handle_key_press(self) -> list[AsyncHandler]:
        """Match a key press to semantic events.

        Records the press timestamp and starts a hold timer if a
        ``key_hold`` mapping exists.

        Returns
        -------
        list[AsyncHandler]
            A list of matched handlers (may be empty).
        """
        self._press_time = time.monotonic()
        self._pressed = True
        self._hold_fired = False

        self._start_hold_timer("key_hold")

        handlers: list[AsyncHandler] = []
        for mapping in self._by_source.get("key_press", []):
            handler = self._handlers.get(mapping.name)
            if handler is not None:
                handlers.append(handler)
        return handlers

    def handle_key_release(self) -> list[AsyncHandler]:
        """Match a key release to semantic events.

        Cancels any running hold timer.  The simple ``key_release``
        event always fires regardless of whether a hold fired.
        ``key_press_release`` is suppressed when a hold already
        fired for this press–release cycle (since the interaction was
        a hold, not a press-release gesture).

        Returns
        -------
        list[AsyncHandler]
            A list of matched handlers (may be empty).
        """
        self._pressed = False
        self._cancel_hold_timer()

        hold_fired = self._hold_fired
        self._hold_fired = False

        handlers: list[AsyncHandler] = []

        if not hold_fired and self._press_time is not None:
            elapsed_ms = (time.monotonic() - self._press_time) * 1000

            for mapping in self._by_source.get("key_press_release", []):
                max_ms = mapping.max_duration_ms
                if max_ms is None or elapsed_ms <= max_ms:
                    handler = self._handlers.get(mapping.name)
                    if handler is not None:
                        handlers.append(handler)

        self._press_time = None

        for mapping in self._by_source.get("key_release", []):
            handler = self._handlers.get(mapping.name)
            if handler is not None:
                handlers.append(handler)

        return handlers

    def handle_touch(
        self, event_type: EventType, x: int, y: int
    ) -> AsyncHandler | None:
        """Match a touch event to a semantic event via regions.

        Parameters
        ----------
        event_type
            The touch event type (TOUCH_SHORT or TOUCH_LONG).
        x
            Touch x coordinate (relative to card origin).
        y
            Touch y coordinate (relative to card origin).

        Returns
        -------
        AsyncHandler or None
            The matched handler, or ``None`` if no region/mapping matched.
        """
        from ..runtime.events import EventType as ET_Enum

        if event_type == ET_Enum.TOUCH_SHORT:
            touch_name = "tap"
        elif event_type == ET_Enum.TOUCH_LONG:
            touch_name = "long_press"
        else:
            return None

        for region in self._regions:
            if touch_name not in region.events:
                continue
            if (
                region.x <= x < region.x + region.width
                and region.y <= y < region.y + region.height
            ):
                for mapping in self._by_source.get(touch_name, []):
                    h = self._handlers.get(mapping.name)
                    if h is not None:
                        return h

        for mapping in self._by_source.get(touch_name, []):
            h = self._handlers.get(mapping.name)
            if h is not None:
                return h

        return None

    @staticmethod
    def _direction_matches(mapping: EventMapping, direction: int) -> bool:
        """Check if a turn direction matches the mapping's filter."""
        if mapping.direction is None:
            return True
        if mapping.direction == "left" and direction < 0:
            return True
        return mapping.direction == "right" and direction > 0
