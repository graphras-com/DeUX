"""deckboard - A high-level, asyncio-native library for Elgato Stream Deck devices.

Example::

    import asyncio
    from deckboard import Deck

    async def main():
        async with Deck() as deck:
            main = deck.screen("main")

            @main.key(0).on_press
            async def on_home():
                print("Home pressed!")

            await deck.set_screen("main")
            await deck.wait_closed()

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
from .runtime import (
    Deck,
    DeckError,
    DeckEvent,
    DeviceInfo,
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from .ui import (
    BlankCard,
    Card,
    EncoderSlot,
    KeySlot,
    Screen,
    TouchStrip,
)

__all__ = [
    "BlankCard",
    "Card",
    "Deck",
    "DeckError",
    "DeckEvent",
    "DeviceInfo",
    "DsuiCard",
    "DsuiKey",
    "EncoderPressEvent",
    "EncoderSlot",
    "EncoderTurnEvent",
    "EventType",
    "KeyEvent",
    "KeySlot",
    "PackageError",
    "PackageSpec",
    "Screen",
    "TouchEvent",
    "TouchStrip",
    "load_all_packages",
    "load_package",
]

__version__ = "0.1.0"
