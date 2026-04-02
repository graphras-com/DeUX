"""Type definitions, enums, and event dataclasses for deckboard."""

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
        """Which widget zone (0-3) this touch falls in, based on x position.

        Accounts for left margin and inter-widget gaps so that touches
        map correctly to the inset widget layout.
        """
        from .image import MARGIN_LEFT, WIDGET_GAP, WIDGET_WIDTH

        # Shift x into the usable coordinate space
        rel = self.x - MARGIN_LEFT
        # Each zone spans WIDGET_WIDTH pixels plus the gap to its right
        stride = WIDGET_WIDTH + WIDGET_GAP
        zone = rel // stride
        return max(0, min(zone, 3))


# Union of all event types
DeckEvent = KeyEvent | DialTurnEvent | DialPressEvent | TouchEvent


@dataclass
class DeviceInfo:
    """Information about a connected Stream Deck device."""

    deck_type: str
    serial: str
    firmware: str
    key_count: int
    key_layout: tuple[int, int]
    dial_count: int
    key_pixel_size: tuple[int, int]
    touchscreen_size: tuple[int, int]
    key_image_format: str
