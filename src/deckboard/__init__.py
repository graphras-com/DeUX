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

from .button import Button
from .deck import Deck, DeckError
from .dial import Dial
from .icon import IconError, IconManager
from .page import Screen
from .runtime import (
    DeckEvent,
    DeviceInfo,
    DialPressEvent,
    DialTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from .touchscreen import Card, TouchStrip
from .ui import (
    Card,
    Control,
    Element,
    EncoderSlot,
    KeySlot,
    RangeControl,
    StackCard,
    StatusCard,
    TouchStrip,
)
from .widgets import (
    BalanceSlider,
    BrightnessSlider,
    EqualizerCard,
    EqualizerSlider,
    KelvinSlider,
    LargeDualValue,
    LargeSlider,
    LargeText,
    LightCard,
    MediaCard,
    Slider,
    SmallDualValue,
    SmallSlider,
    SmallText,
    StackCard,
    StatusCard,
    TemperatureSlider,
    VolumeSlider,
)

__all__ = [
    "BalanceSlider",
    "BrightnessSlider",
    "Button",
    "Card",
    "Control",
    "Deck",
    "DeckError",
    "DeckEvent",
    "DeviceInfo",
    "Dial",
    "DialPressEvent",
    "DialTurnEvent",
    "Element",
    "EncoderSlot",
    "EqualizerSlider",
    "EqualizerCard",
    "EventType",
    "IconError",
    "IconManager",
    "KeySlot",
    "KelvinSlider",
    "KeyEvent",
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
