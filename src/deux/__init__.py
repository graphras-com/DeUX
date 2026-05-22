"""deux - A high-level, asyncio-native library for Elgato Stream Deck devices.

Examples
--------
::

    import asyncio
    from deux import DeckManager

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

from ._errors import DeuxError
from ._url_safety import SSRFError, set_allow_private_urls
from .dui import (
    DuiCard,
    DuiKey,
    DuiRepository,
    PackageError,
    PackageSpec,
    add_dui_path,
    clear_dui_cache,
    list_dui_packages,
    load_all_packages,
    load_package,
    remove_dui_path,
    resolve_dui,
)
from .render import (
    Theme,
    get_active_theme,
    set_active_theme,
)
from .runtime import (
    Deck,
    DeckError,
    DeckEvent,
    DeckManager,
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
    CardController,
    EncoderSlot,
    InfoScreen,
    KeyController,
    KeySlot,
    Screen,
    TouchStrip,
)

__all__ = [
    "BlankCard",
    "Card",
    "CardController",
    "Deck",
    "DeckError",
    "DeckEvent",
    "DeckManager",
    "DeviceInfo",
    "DeuxError",
    "DuiCard",
    "DuiKey",
    "DuiRepository",
    "EncoderPressEvent",
    "EncoderSlot",
    "EncoderTurnEvent",
    "EventType",
    "InfoScreen",
    "KeyController",
    "KeyEvent",
    "KeySlot",
    "PackageError",
    "PackageSpec",
    "SSRFError",
    "Screen",
    "Theme",
    "TouchEvent",
    "TouchStrip",
    "__version__",
    "add_dui_path",
    "clear_dui_cache",
    "get_active_theme",
    "list_dui_packages",
    "load_all_packages",
    "load_package",
    "remove_dui_path",
    "resolve_dui",
    "set_active_theme",
    "set_allow_private_urls",
]

from deux._version_safe import __version__
