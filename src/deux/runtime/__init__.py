"""Runtime package for deux device sessions and events."""

from __future__ import annotations

from ._executor import get_executor, shutdown_executor
from .async_event import AsyncEvent
from .capabilities import DeviceCapabilities
from .deck import Deck, DeckError
from .device_info import DeviceInfo
from .discovery import list_devices
from .events import (
    AsyncHandler,
    DeckEvent,
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from .manager import DeckManager
from .transport import AsyncTransport

__all__ = [
    "AsyncEvent",
    "AsyncHandler",
    "AsyncTransport",
    "Deck",
    "DeckError",
    "DeckEvent",
    "DeckManager",
    "DeviceCapabilities",
    "DeviceInfo",
    "EncoderPressEvent",
    "EncoderTurnEvent",
    "EventType",
    "KeyEvent",
    "TouchEvent",
    "get_executor",
    "list_devices",
    "shutdown_executor",
]
