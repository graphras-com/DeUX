"""deckboard - A high-level, asyncio-native library for Elgato Stream Deck devices.

Example::

    import asyncio
    from deckboard import DeckManager

    async def main():
        manager = DeckManager()

        @manager.on_connect()
        async def handle(deck):
            screen = deck.screen("main")

            @screen.key(0).on_press
            async def on_home():
                print("Home pressed!")

            await deck.set_screen("main")

        async with manager:
            await manager.wait_closed()

    asyncio.run(main())
"""

from __future__ import annotations

from .dsui import (
    DsuiCard,
    DsuiKey,
    PackageError,
    PackageSpec,
    load_all_packages,
    load_package,
)
from .render import RenderMetrics
from .runtime import (
    DeckError,
    DeckEvent,
    DeckManager,
    DeviceCapabilities,
    DeviceInfo,
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
    list_devices,
)
from .ui import (
    BlankCard,
    Card,
    EncoderSlot,
    InfoScreen,
    KeySlot,
    Screen,
    TouchStrip,
)

__all__ = [
    "BlankCard",
    "Card",
    "DeckError",
    "DeckEvent",
    "DeckManager",
    "DeviceCapabilities",
    "DeviceInfo",
    "DsuiCard",
    "DsuiKey",
    "EncoderPressEvent",
    "EncoderSlot",
    "EncoderTurnEvent",
    "EventType",
    "InfoScreen",
    "KeyEvent",
    "KeySlot",
    "PackageError",
    "PackageSpec",
    "RenderMetrics",
    "Screen",
    "TouchEvent",
    "TouchStrip",
    "list_devices",
    "load_all_packages",
    "load_package",
]

__version__ = "0.1.0"
