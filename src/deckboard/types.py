"""Compatibility exports for deckboard runtime event and type models."""

from __future__ import annotations

from .runtime.device_info import DeviceInfo
from .runtime.events import (
    AsyncHandler,
    DeckEvent,
    DialPressEvent,
    DialTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)

__all__ = [
    "AsyncHandler",
    "DeckEvent",
    "DeviceInfo",
    "DialPressEvent",
    "DialTurnEvent",
    "EventType",
    "KeyEvent",
    "TouchEvent",
]
