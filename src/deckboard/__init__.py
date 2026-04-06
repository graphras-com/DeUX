"""deckboard - A high-level, asyncio-native library for Elgato Stream Deck devices.

Example::

    import asyncio
    from deckboard import Deck

    async def main():
        async with Deck() as deck:
            main = deck.screen("main")
            main.key(0).set_icon("mdi:home")

            @main.key(0).on_press
            async def on_home():
                print("Home pressed!")

            await deck.set_screen("main")
            await deck.wait_closed()

    asyncio.run(main())
"""

from __future__ import annotations

from .presets import EqualizerCard, HaMediaCard, LightCard, MediaCard
from .render import IconError, IconManager
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
    BalanceSlider,
    BrightnessSlider,
    Card,
    Control,
    Element,
    EncoderSlot,
    EqualizerSlider,
    KelvinSlider,
    KeySlot,
    LargeDualValue,
    LargeSlider,
    LargeText,
    RangeControl,
    Screen,
    Slider,
    SmallDualValue,
    SmallSlider,
    SmallText,
    StackCard,
    StatusCard,
    TemperatureSlider,
    TouchStrip,
    VolumeSlider,
)

__all__ = [
    "BalanceSlider",
    "BrightnessSlider",
    "Card",
    "Control",
    "Deck",
    "DeckError",
    "DeckEvent",
    "DeviceInfo",
    "Element",
    "EncoderPressEvent",
    "EncoderSlot",
    "EncoderTurnEvent",
    "EqualizerCard",
    "EqualizerSlider",
    "EventType",
    "HaMediaCard",
    "IconError",
    "IconManager",
    "KelvinSlider",
    "KeyEvent",
    "KeySlot",
    "LargeDualValue",
    "LargeSlider",
    "LargeText",
    "LightCard",
    "MediaCard",
    "RangeControl",
    "Screen",
    "Slider",
    "SmallDualValue",
    "SmallSlider",
    "SmallText",
    "StackCard",
    "StatusCard",
    "TemperatureSlider",
    "TouchEvent",
    "TouchStrip",
    "VolumeSlider",
]

__version__ = "0.1.0"
