"""Physical-to-semantic event routing for .dsui packages."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from .schema import EventMapping, Region

if TYPE_CHECKING:
    from ..runtime.events import AsyncHandler, EventType

logger = logging.getLogger(__name__)


class EventMap:
    """Map physical hardware events to named semantic events.

    Handles simple mappings (encoder_press → semantic name) as well as
    compound gestures:

    - ``encoder_press_release``: fires only if the press duration is
      within ``max_duration_ms``.
    - ``encoder_press_turn``: fires turn events only while the encoder
      is held down.
    - Direction filtering: ``encoder_turn`` with ``direction: left``
      only fires for counter-clockwise turns.

    Args:
        events: Event mappings from the package manifest.
        regions: Touch regions from the package manifest.
    """

    def __init__(
        self,
        events: tuple[EventMapping, ...],
        regions: tuple[Region, ...] = (),
    ) -> None:
        self._mappings = events
        self._regions = regions
        self._handlers: dict[str, AsyncHandler] = {}

        # Gesture state
        self._press_time: float | None = None
        self._pressed = False

        # Pre-index mappings by source for fast lookup
        self._by_source: dict[str, list[EventMapping]] = {}
        for mapping in events:
            self._by_source.setdefault(mapping.source, []).append(mapping)

    def on(self, event_name: str, handler: AsyncHandler) -> None:
        """Register a handler for a named semantic event.

        Args:
            event_name: The semantic event name (as defined in the manifest).
            handler: An async callable to invoke when the event fires.

        Raises:
            KeyError: If *event_name* is not defined in the manifest.
        """
        known = {m.name for m in self._mappings}
        if event_name not in known:
            raise KeyError(
                f"Unknown event '{event_name}'. Defined events: {sorted(known)}"
            )
        self._handlers[event_name] = handler

    @property
    def event_names(self) -> list[str]:
        """All semantic event names defined in this map."""
        return [m.name for m in self._mappings]

    # -- Encoder events ----------------------------------------------------

    def handle_encoder_turn(self, direction: int) -> AsyncHandler | None:
        """Match an encoder turn to a semantic event.

        Args:
            direction: Positive for clockwise, negative for counter-clockwise.

        Returns:
            The handler to call, or ``None`` if no mapping matched.
        """
        # Check encoder_press_turn first (turn while pressed)
        if self._pressed:
            for mapping in self._by_source.get("encoder_press_turn", []):
                if self._direction_matches(mapping, direction):
                    return self._handlers.get(mapping.name)

        # Then regular encoder_turn
        for mapping in self._by_source.get("encoder_turn", []):
            if self._direction_matches(mapping, direction):
                return self._handlers.get(mapping.name)

        return None

    def handle_encoder_press(self) -> AsyncHandler | None:
        """Match an encoder press to a semantic event.

        Records the press timestamp for gesture detection.

        Returns:
            The handler to call, or ``None`` if no mapping matched.
        """
        self._press_time = time.monotonic()
        self._pressed = True

        for mapping in self._by_source.get("encoder_press", []):
            return self._handlers.get(mapping.name)

        return None

    def handle_encoder_release(self) -> AsyncHandler | None:
        """Match an encoder release to a semantic event.

        Checks ``encoder_press_release`` gesture timing.

        Returns:
            The handler to call, or ``None`` if no mapping matched.
        """
        self._pressed = False

        # Check press_release gesture first
        if self._press_time is not None:
            elapsed_ms = (time.monotonic() - self._press_time) * 1000
            self._press_time = None

            for mapping in self._by_source.get("encoder_press_release", []):
                max_ms = mapping.max_duration_ms
                if max_ms is None or elapsed_ms <= max_ms:
                    return self._handlers.get(mapping.name)

        # Then simple encoder_release
        for mapping in self._by_source.get("encoder_release", []):
            return self._handlers.get(mapping.name)

        return None

    # -- Key events --------------------------------------------------------

    def handle_key_press(self) -> AsyncHandler | None:
        """Match a key press to a semantic event."""
        self._press_time = time.monotonic()
        self._pressed = True

        for mapping in self._by_source.get("key_press", []):
            return self._handlers.get(mapping.name)

        return None

    def handle_key_release(self) -> AsyncHandler | None:
        """Match a key release to a semantic event."""
        self._pressed = False

        # Check press_release gesture first
        if self._press_time is not None:
            elapsed_ms = (time.monotonic() - self._press_time) * 1000
            self._press_time = None

            for mapping in self._by_source.get("key_press_release", []):
                max_ms = mapping.max_duration_ms
                if max_ms is None or elapsed_ms <= max_ms:
                    return self._handlers.get(mapping.name)

        # Then simple key_release
        for mapping in self._by_source.get("key_release", []):
            return self._handlers.get(mapping.name)

        return None

    # -- Touch events ------------------------------------------------------

    def handle_touch(
        self, event_type: EventType, x: int, y: int
    ) -> AsyncHandler | None:
        """Match a touch event to a semantic event via regions.

        Args:
            event_type: The touch event type (TOUCH_SHORT or TOUCH_LONG).
            x: Touch x coordinate (relative to card origin).
            y: Touch y coordinate (relative to card origin).

        Returns:
            The handler to call, or ``None`` if no region/mapping matched.
        """
        from ..runtime.events import EventType as ET_Enum

        # Map EventType to region event name
        if event_type == ET_Enum.TOUCH_SHORT:
            touch_name = "tap"
        elif event_type == ET_Enum.TOUCH_LONG:
            touch_name = "long_press"
        else:
            return None

        # Check which region contains the touch point
        for region in self._regions:
            if touch_name not in region.events:
                continue
            if (
                region.x <= x < region.x + region.width
                and region.y <= y < region.y + region.height
            ):
                # Find a mapping for this source type
                for mapping in self._by_source.get(touch_name, []):
                    return self._handlers.get(mapping.name)

        # Also check top-level tap/long_press events (no region required)
        for mapping in self._by_source.get(touch_name, []):
            return self._handlers.get(mapping.name)

        return None

    # -- Helpers -----------------------------------------------------------

    @staticmethod
    def _direction_matches(mapping: EventMapping, direction: int) -> bool:
        """Check if a turn direction matches the mapping's filter."""
        if mapping.direction is None:
            return True
        if mapping.direction == "left" and direction < 0:
            return True
        if mapping.direction == "right" and direction > 0:
            return True
        return False
