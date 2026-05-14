"""deckui - A high-level, asyncio-native library for Elgato Stream Deck devices.

Examples
--------
::

    import asyncio
    from deckui import DeckManager

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
    ImageFetchError,
    RenderMetrics,
    SvgRasterizer,
    clear_image_cache,
    fetch_image,
    get_svg_backend,
    get_svg_stylesheet,
    list_svg_backends,
    load_svg_stylesheet,
    register_svg_backend,
    set_svg_backend,
    set_svg_stylesheet,
)
from .runtime import (
    AsyncEvent,
    Deck,
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
    CardController,
    EncoderSlot,
    InfoScreen,
    KeyController,
    KeySlot,
    Screen,
    TouchStrip,
)

__all__ = [
    "AsyncEvent",
    "BlankCard",
    "Card",
    "CardController",
    "Deck",
    "DeckError",
    "DeckEvent",
    "DeckManager",
    "DeviceCapabilities",
    "DeviceInfo",
    "DuiCard",
    "DuiKey",
    "DuiRepository",
    "EncoderPressEvent",
    "EncoderSlot",
    "EncoderTurnEvent",
    "EventType",
    "ImageFetchError",
    "InfoScreen",
    "KeyController",
    "KeyEvent",
    "KeySlot",
    "PackageError",
    "PackageSpec",
    "RenderMetrics",
    "Screen",
    "SvgRasterizer",
    "TouchEvent",
    "TouchStrip",
    "add_dui_path",
    "clear_dui_cache",
    "clear_image_cache",
    "fetch_image",
    "get_svg_backend",
    "get_svg_stylesheet",
    "list_devices",
    "list_dui_packages",
    "list_svg_backends",
    "load_all_packages",
    "load_package",
    "load_svg_stylesheet",
    "register_svg_backend",
    "remove_dui_path",
    "resolve_dui",
    "set_svg_backend",
    "set_svg_stylesheet",
]

from deckui._version import __version__

__all__ += ["__version__"]
