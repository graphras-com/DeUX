"""Async bridge between HID input polling and the deux event loop.

Replaces the callback-based ``AsyncTransport`` with a polling-based
approach that reads input reports from the device at a configurable
interval and translates them into :class:`DeckEvent` objects.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .events import (
    DeckEvent,
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from .hid.protocol import (
    EncoderButtonEvent,
    EncoderRotateEvent,
    InputEvent,
    KeyStateEvent,
    TouchFlickEvent,
    TouchPressEvent,
    TouchTapEvent,
)

if TYPE_CHECKING:
    from .capabilities import DeviceCapabilities
    from .hid.device import HidDevice

logger = logging.getLogger(__name__)

#: Default HID input poll interval in milliseconds.
_DEFAULT_POLL_MS = 50


class AsyncTransport:
    """Poll-based async bridge from HID input reports to deck events.

    Reads input reports from the device in a background task and
    translates them into :class:`DeckEvent` objects on an asyncio queue.

    Parameters
    ----------
    device : HidDevice
        An open HID device.
    caps : DeviceCapabilities or None
        Device capabilities (used to determine which events to process).
    poll_interval_ms : int, default=50
        HID read timeout per poll cycle in milliseconds.
    """

    def __init__(
        self,
        device: HidDevice,
        caps: DeviceCapabilities | None = None,
        poll_interval_ms: int = _DEFAULT_POLL_MS,
    ) -> None:
        self._device = device
        self._caps = caps
        self._poll_interval_ms = poll_interval_ms
        self._queue: asyncio.Queue[DeckEvent] = asyncio.Queue()
        self._running = False
        self._poll_task: asyncio.Task[None] | None = None
        self._prev_key_states: tuple[bool, ...] = ()
        self._prev_encoder_states: tuple[bool, ...] = ()

    @property
    def queue(self) -> asyncio.Queue[DeckEvent]:
        """The asyncio queue that receives decoded device events."""
        return self._queue

    def start(self) -> None:
        """Start the input polling background task."""
        self._running = True
        self._poll_task = asyncio.create_task(
            self._poll_loop(), name="deux-hid-poll"
        )

    def stop(self) -> None:
        """Stop polling."""
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()

    async def _poll_loop(self) -> None:
        """Background task: poll HID input and enqueue events."""
        from ._executor import get_executor
        from .hid._ctypes_hidapi import HidApiError

        loop = asyncio.get_running_loop()
        executor = get_executor()

        try:
            while self._running and self._device.is_open:
                try:
                    event = await loop.run_in_executor(
                        executor,
                        self._device.read_input,
                        self._poll_interval_ms,
                    )
                except HidApiError:
                    logger.warning("HID device disconnected during poll")
                    break

                if event is not None:
                    self._translate_event(event)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("HID poll loop crashed")

    def _translate_event(self, event: InputEvent) -> None:
        """Translate a HID input event into DeckEvent(s) on the queue.

        Parameters
        ----------
        event : InputEvent
            A parsed HID input event.
        """
        if isinstance(event, KeyStateEvent):
            self._handle_key_state(event)
        elif isinstance(event, TouchTapEvent):
            self._queue.put_nowait(
                TouchEvent(
                    event_type=EventType.TOUCH_SHORT,
                    x=event.x,
                    y=event.y,
                )
            )
        elif isinstance(event, TouchPressEvent):
            self._queue.put_nowait(
                TouchEvent(
                    event_type=EventType.TOUCH_LONG,
                    x=event.x,
                    y=event.y,
                )
            )
        elif isinstance(event, TouchFlickEvent):
            self._queue.put_nowait(
                TouchEvent(
                    event_type=EventType.TOUCH_DRAG,
                    x=event.start_x,
                    y=event.start_y,
                    x_out=event.end_x,
                    y_out=event.end_y,
                )
            )
        elif isinstance(event, EncoderButtonEvent):
            self._handle_encoder_buttons(event)
        elif isinstance(event, EncoderRotateEvent):
            self._handle_encoder_rotate(event)

    def _handle_key_state(self, event: KeyStateEvent) -> None:
        """Emit KeyEvents for keys that changed state.

        Parameters
        ----------
        event : KeyStateEvent
            The current key state snapshot.
        """
        for idx, pressed in enumerate(event.states):
            if idx < len(self._prev_key_states):
                if pressed == self._prev_key_states[idx]:
                    continue
            self._queue.put_nowait(KeyEvent(key=idx, pressed=pressed))
        self._prev_key_states = event.states

    def _handle_encoder_buttons(self, event: EncoderButtonEvent) -> None:
        """Emit EncoderPressEvents for encoders that changed state.

        Parameters
        ----------
        event : EncoderButtonEvent
            The current encoder button state snapshot.
        """
        for idx, pressed in enumerate(event.states):
            if idx < len(self._prev_encoder_states):
                if pressed == self._prev_encoder_states[idx]:
                    continue
            self._queue.put_nowait(
                EncoderPressEvent(encoder=idx, pressed=pressed)
            )
        self._prev_encoder_states = event.states

    def _handle_encoder_rotate(self, event: EncoderRotateEvent) -> None:
        """Emit EncoderTurnEvents for encoders that rotated.

        Parameters
        ----------
        event : EncoderRotateEvent
            The rotation ticks snapshot.
        """
        for idx, ticks in enumerate(event.ticks):
            if ticks != 0:
                self._queue.put_nowait(
                    EncoderTurnEvent(encoder=idx, direction=ticks)
                )
