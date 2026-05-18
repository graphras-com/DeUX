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

import warnings
from typing import Any

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

from deux._version import __version__

# ---------------------------------------------------------------------------
# Deprecated re-exports – available for one release cycle with a warning.
# Advanced users should import from the relevant subpackage directly.
# ---------------------------------------------------------------------------

_DEPRECATED_IMPORTS: dict[str, tuple[str, str]] = {
    "AsyncEvent": ("deux.runtime", "deux.runtime.AsyncEvent"),
    "DeviceCapabilities": ("deux.runtime", "deux.runtime.DeviceCapabilities"),
    "ImageFetchError": ("deux.render", "deux.render.ImageFetchError"),
    "RenderMetrics": ("deux.render", "deux.render.RenderMetrics"),
    "SurfaceBackgrounds": ("deux.render", "deux.render.SurfaceBackgrounds"),
    "SvgRasterizer": ("deux.render", "deux.render.SvgRasterizer"),
    "clear_image_cache": ("deux.render", "deux.render.clear_image_cache"),
    "fetch_image": ("deux.render", "deux.render.fetch_image"),
    "get_default_backgrounds": ("deux.render", "deux.render.get_default_backgrounds"),
    "get_default_font_family": ("deux.render", "deux.render.get_default_font_family"),
    "get_svg_backend": ("deux.render", "deux.render.get_svg_backend"),
    "get_svg_stylesheet": ("deux.render", "deux.render.get_svg_stylesheet"),
    "list_devices": ("deux.runtime", "deux.runtime.list_devices"),
    "list_supported_devices": ("deux.render", "deux.render.list_supported_devices"),
    "list_svg_backends": ("deux.render", "deux.render.list_svg_backends"),
    "load_svg_stylesheet": ("deux.render", "deux.render.load_svg_stylesheet"),
    "register_svg_backend": ("deux.render", "deux.render.register_svg_backend"),
    "set_svg_backend": ("deux.render", "deux.render.set_svg_backend"),
    "set_svg_stylesheet": ("deux.render", "deux.render.set_svg_stylesheet"),
}


def __getattr__(name: str) -> Any:
    """Provide deprecated access to internal symbols with a warning."""
    if name in _DEPRECATED_IMPORTS:
        subpackage, qualified = _DEPRECATED_IMPORTS[name]
        warnings.warn(
            f"Importing '{name}' from 'deux' is deprecated. "
            f"Use '{qualified}' instead. "
            f"This re-export will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        import importlib

        module = importlib.import_module(subpackage)
        return getattr(module, name)
    raise AttributeError(f"module 'deux' has no attribute {name!r}")
