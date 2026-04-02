"""deckboard - A high-level, asyncio-native library for Elgato Stream Deck devices.

Example::

    import asyncio
    from deckboard import Deck

    async def main():
        async with Deck() as deck:
            main = deck.page("main")
            main.button(0).set_icon("mdi:home")

            @main.button(0).on_press
            async def on_home():
                print("Home pressed!")

            await deck.set_page("main")
            await deck.wait_closed()

    asyncio.run(main())
"""

from .button import Button
from .deck import Deck, DeckError
from .dial import Dial
from .icon import IconError, IconManager
from .page import Page
from .touchscreen import TouchScreen, Widget
from .types import (
    DeckEvent,
    DeviceInfo,
    DialPressEvent,
    DialTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from .widgets import (
    BalanceSlider,
    BrightnessSlider,
    EqualizerSlider,
    KelvinSlider,
    LargeSlider,
    Slider,
    SmallSlider,
    TemperatureSlider,
    VolumeSlider,
)

__all__ = [
    "BalanceSlider",
    "BrightnessSlider",
    "Button",
    "Deck",
    "DeckError",
    "DeckEvent",
    "DeviceInfo",
    "Dial",
    "DialPressEvent",
    "DialTurnEvent",
    "EqualizerSlider",
    "EventType",
    "IconError",
    "IconManager",
    "KelvinSlider",
    "KeyEvent",
    "LargeSlider",
    "Page",
    "Slider",
    "SmallSlider",
    "TemperatureSlider",
    "TouchEvent",
    "TouchScreen",
    "VolumeSlider",
    "Widget",
]

__version__ = "0.1.0"
