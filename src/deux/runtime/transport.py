"""Async bridge between Stream Deck callbacks and the deux event loop."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from StreamDeck.Devices.StreamDeck import DialEventType, TouchscreenEventType

from .events import (
    DeckEvent,
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from StreamDeck.Devices.StreamDeck import StreamDeck

    from .capabilities import DeviceCapabilities

logger = logging.getLogger(__name__)


def _coerce_int(value: object, default: int = 0) -> int:
    """Convert a callback payload value to ``int``.

    Parameters
    ----------
    value : object
        The raw value from the device callback payload.
    default : int, default=0
        Fallback returned when *value* is not an ``int``.

    Returns
    -------
    int
        *value* if it is an ``int``, otherwise *default*.
    """
    return value if isinstance(value, int) else default


def _optional_int(value: object) -> int | None:
    """Convert a callback payload value to an optional ``int``.

    Parameters
    ----------
    value : object
        The raw value from the device callback payload.

    Returns
    -------
    int or None
        *value* if it is an ``int``, otherwise ``None``.
    """
    return value if isinstance(value, int) else None


class AsyncTransport:
    """Bridge sync streamdeck callbacks into an asyncio event queue.

    Conditionally registers dial and touchscreen callbacks only when
    the device supports those features.

    Parameters
    ----------
    device
        An open Stream Deck device.
    loop
        The running asyncio event loop.
    caps
        Device capabilities (used to determine which callbacks to register).
    """

    def __init__(
        self,
        device: StreamDeck,
        loop: asyncio.AbstractEventLoop,
        caps: DeviceCapabilities | None = None,
    ) -> None:
        self._device = device
        self._loop = loop
        self._caps = caps
        self._queue: asyncio.Queue[DeckEvent] = asyncio.Queue()
        self._running = False

    @property
    def queue(self) -> asyncio.Queue[DeckEvent]:
        """The asyncio queue that receives decoded device events."""
        return self._queue

    def start(self) -> None:
        """Register callbacks on the low-level device."""
        self._running = True
        self._device.set_key_callback(self._on_key)

        if self._caps is None or self._caps.has_encoders:
            self._device.set_dial_callback(self._on_encoder)
        if self._caps is None or self._caps.has_touchscreen:
            self._device.set_touchscreen_callback(self._on_touch)

    def stop(self) -> None:
        """Unregister callbacks."""
        self._running = False
        self._device.set_key_callback(None)

        if self._caps is None or self._caps.has_encoders:
            self._device.set_dial_callback(None)
        if self._caps is None or self._caps.has_touchscreen:
            self._device.set_touchscreen_callback(None)

    def _enqueue(self, event: DeckEvent) -> None:
        """Thread-safe: put an event onto the asyncio queue."""
        if not self._running:
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    def _on_key(self, deck: StreamDeck, key: int, pressed: bool) -> None:
        """Handle a physical key press/release callback.

        Parameters
        ----------
        deck : StreamDeck
            The device that generated the event.
        key : int
            Zero-based key index.
        pressed : bool
            ``True`` on key-down, ``False`` on key-up.
        """
        try:
            self._enqueue(KeyEvent(key=key, pressed=pressed))
        except Exception:
            logger.exception("Error in key callback (key=%d)", key)

    def _on_encoder(
        self, deck: StreamDeck, encoder: int, event: DialEventType, value: object
    ) -> None:
        """Handle an encoder push or turn callback.

        Parameters
        ----------
        deck : StreamDeck
            The device that generated the event.
        encoder : int
            Zero-based encoder index.
        event : DialEventType
            Whether the dial was pushed or turned.
        value : object
            ``bool`` for push events, ``int`` direction for turn events.
        """
        try:
            if event == DialEventType.PUSH:
                self._enqueue(EncoderPressEvent(encoder=encoder, pressed=bool(value)))
            elif event == DialEventType.TURN:
                direction = value if isinstance(value, int) else 0
                self._enqueue(EncoderTurnEvent(encoder=encoder, direction=direction))
        except Exception:
            logger.exception("Error in encoder callback (encoder=%d)", encoder)

    def _on_touch(
        self,
        deck: StreamDeck,
        evt_type: TouchscreenEventType,
        value: Mapping[str, object],
    ) -> None:
        """Handle a touchscreen interaction callback.

        Parameters
        ----------
        deck : StreamDeck
            The device that generated the event.
        evt_type : TouchscreenEventType
            The kind of touch (short, long, or drag).
        value : Mapping[str, object]
            Touch coordinates (``x``, ``y``, and optionally ``x_out``, ``y_out``).
        """
        try:
            if evt_type == TouchscreenEventType.SHORT:
                event_type = EventType.TOUCH_SHORT
            elif evt_type == TouchscreenEventType.LONG:
                event_type = EventType.TOUCH_LONG
            elif evt_type == TouchscreenEventType.DRAG:
                event_type = EventType.TOUCH_DRAG
            else:
                return

            self._enqueue(
                TouchEvent(
                    event_type=event_type,
                    x=_coerce_int(value.get("x", 0)),
                    y=_coerce_int(value.get("y", 0)),
                    x_out=_optional_int(value.get("x_out")),
                    y_out=_optional_int(value.get("y_out")),
                )
            )
        except Exception:
            logger.exception("Error in touch callback")
