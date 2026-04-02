"""Async bridge: connects the sync streamdeck reader thread to an asyncio event loop."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from StreamDeck.Devices.StreamDeck import DialEventType, TouchscreenEventType

from .types import (
    DeckEvent,
    DialPressEvent,
    DialTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)

if TYPE_CHECKING:
    from StreamDeck.Devices.StreamDeck import StreamDeck

logger = logging.getLogger(__name__)


class AsyncTransport:
    """Bridges sync streamdeck callbacks into an asyncio event queue.

    The low-level ``streamdeck`` library spawns a reader thread that calls
    callbacks synchronously.  This class registers those callbacks and
    translates them into typed event objects placed on an ``asyncio.Queue``
    that the ``Deck`` event loop consumes.
    """

    def __init__(self, device: StreamDeck, loop: asyncio.AbstractEventLoop) -> None:
        self._device = device
        self._loop = loop
        self._queue: asyncio.Queue[DeckEvent] = asyncio.Queue()
        self._running = False

    @property
    def queue(self) -> asyncio.Queue[DeckEvent]:
        return self._queue

    def start(self) -> None:
        """Register callbacks on the low-level device and open it."""
        self._running = True
        self._device.set_key_callback(self._on_key)
        self._device.set_dial_callback(self._on_dial)
        self._device.set_touchscreen_callback(self._on_touch)

    def stop(self) -> None:
        """Unregister callbacks."""
        self._running = False
        self._device.set_key_callback(None)
        self._device.set_dial_callback(None)
        self._device.set_touchscreen_callback(None)

    def _enqueue(self, event: DeckEvent) -> None:
        """Thread-safe: put an event onto the asyncio queue."""
        if not self._running:
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    # -- Low-level callbacks (called from reader thread) -------------------

    def _on_key(self, deck: StreamDeck, key: int, pressed: bool) -> None:
        try:
            self._enqueue(KeyEvent(key=key, pressed=pressed))
        except Exception:
            logger.exception("Error in key callback (key=%d)", key)

    def _on_dial(
        self, deck: StreamDeck, dial: int, event: DialEventType, value: object
    ) -> None:
        try:
            if event == DialEventType.PUSH:
                self._enqueue(DialPressEvent(dial=dial, pressed=bool(value)))
            elif event == DialEventType.TURN:
                self._enqueue(DialTurnEvent(dial=dial, direction=int(value)))
        except Exception:
            logger.exception("Error in dial callback (dial=%d)", dial)

    def _on_touch(
        self, deck: StreamDeck, evt_type: TouchscreenEventType, value: dict
    ) -> None:
        try:
            if evt_type == TouchscreenEventType.SHORT:
                et = EventType.TOUCH_SHORT
            elif evt_type == TouchscreenEventType.LONG:
                et = EventType.TOUCH_LONG
            elif evt_type == TouchscreenEventType.DRAG:
                et = EventType.TOUCH_DRAG
            else:
                return

            self._enqueue(
                TouchEvent(
                    event_type=et,
                    x=value.get("x", 0),
                    y=value.get("y", 0),
                    x_out=value.get("x_out"),
                    y_out=value.get("y_out"),
                )
            )
        except Exception:
            logger.exception("Error in touch callback")
