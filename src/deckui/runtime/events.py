"""Runtime event models and handler types for deckui."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from ..render.metrics import RenderMetrics

# Type alias for async event handlers
AsyncHandler = Callable[..., Coroutine[Any, Any, None]]


class EventType(Enum):
    """Internal event types for the async bridge."""

    ENCODER_TURN = auto()
    TOUCH_SHORT = auto()
    TOUCH_LONG = auto()
    TOUCH_DRAG = auto()


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """A physical key press/release event."""

    key: int
    pressed: bool


@dataclass(frozen=True, slots=True)
class EncoderTurnEvent:
    """An encoder rotation event."""

    encoder: int
    direction: int  # positive = clockwise, negative = counter-clockwise


@dataclass(frozen=True, slots=True)
class EncoderPressEvent:
    """An encoder push/release event."""

    encoder: int
    pressed: bool


@dataclass(frozen=True, slots=True)
class TouchEvent:
    """A touchscreen interaction event."""

    event_type: EventType  # TOUCH_SHORT, TOUCH_LONG, or TOUCH_DRAG
    x: int
    y: int
    x_out: int | None = None  # only for DRAG
    y_out: int | None = None  # only for DRAG

    def compute_zone(self, metrics: RenderMetrics) -> int:
        """Compute which touch-strip zone this touch falls in.

        Args:
            metrics: The render metrics for the connected device.

        Returns:
            Zone index (0 to panel_count-1).
        """
        if metrics.panel_count == 0:
            return 0

        rel = self.x - metrics.margin_left
        stride = metrics.panel_width + metrics.panel_gap
        if stride <= 0:
            return 0
        zone = rel // stride
        return max(0, min(zone, metrics.panel_count - 1))

    @property
    def zone(self) -> int:
        """Which touch-strip zone (0-3) this touch falls in.

        Uses default Stream Deck+ metrics. For multi-device support,
        use :meth:`compute_zone` with the device's render metrics.
        """
        from ..render.metrics import MARGIN_LEFT, PANEL_GAP, PANEL_WIDTH

        rel = self.x - MARGIN_LEFT
        stride = PANEL_WIDTH + PANEL_GAP
        zone = rel // stride
        return max(0, min(zone, 3))


DeckEvent = KeyEvent | EncoderTurnEvent | EncoderPressEvent | TouchEvent
