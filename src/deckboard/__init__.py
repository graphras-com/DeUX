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
from .page import Page, Screen
from .runtime import (
    DeckEvent,
    DeviceInfo,
    DialPressEvent,
    DialTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from .touchscreen import TouchScreen, Widget
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
    EqualizerSlider,
    EqualizerWidget,
    IconWidget,
    KelvinSlider,
    LargeDualValue,
    LargeSlider,
    LargeText,
    Slider,
    SliderWidget,
    SmallDualValue,
    SmallSlider,
    SmallText,
    TemperatureSlider,
    TouchPanel,
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
    "EqualizerWidget",
    "EventType",
    "IconError",
    "IconManager",
    "IconWidget",
    "KeySlot",
    "KelvinSlider",
    "KeyEvent",
    "LargeDualValue",
    "LargeSlider",
    "LargeText",
    "Page",
    "RangeControl",
    "Screen",
    "Slider",
    "SliderWidget",
    "SmallDualValue",
    "SmallSlider",
    "SmallText",
    "StackCard",
    "StatusCard",
    "TemperatureSlider",
    "TouchEvent",
    "TouchPanel",
    "TouchScreen",
    "TouchStrip",
    "VolumeSlider",
    "Widget",
]

__version__ = "0.1.0"
