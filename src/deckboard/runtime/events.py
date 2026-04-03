"""Runtime event models and handler types for deckboard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Coroutine

# Type alias for async event handlers
AsyncHandler = Callable[..., Coroutine[Any, Any, None]]


class EventType(Enum):
    """Internal event types for the async bridge."""

    DIAL_TURN = auto()
    TOUCH_SHORT = auto()
    TOUCH_LONG = auto()
    TOUCH_DRAG = auto()


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """A physical key press/release event."""

    key: int
    pressed: bool


@dataclass(frozen=True, slots=True)
class DialTurnEvent:
    """A dial rotation event."""

    dial: int
    direction: int  # positive = clockwise, negative = counter-clockwise


@dataclass(frozen=True, slots=True)
class DialPressEvent:
    """A dial push/release event."""

    dial: int
    pressed: bool


@dataclass(frozen=True, slots=True)
class TouchEvent:
    """A touchscreen interaction event."""

    event_type: EventType  # TOUCH_SHORT, TOUCH_LONG, or TOUCH_DRAG
    x: int
    y: int
    x_out: int | None = None  # only for DRAG
    y_out: int | None = None  # only for DRAG

    @property
    def zone(self) -> int:
        """Which touch-strip zone (0-3) this touch falls in."""
        from ..render.metrics import MARGIN_LEFT, PANEL_GAP, PANEL_WIDTH

        rel = self.x - MARGIN_LEFT
        stride = PANEL_WIDTH + PANEL_GAP
        zone = rel // stride
        return max(0, min(zone, 3))


DeckEvent = KeyEvent | DialTurnEvent | DialPressEvent | TouchEvent
