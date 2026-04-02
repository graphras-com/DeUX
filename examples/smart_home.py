#!/usr/bin/env python3
"""Smart home dashboard — multi-page control with sliders.

Two pages: **Living Room** and **Bedroom**.  Each page has light/climate
controls on the touchscreen (brightness, colour temperature, room
temperature) and quick-action buttons for scenes and devices.

Press the page-switch button to toggle between rooms.

Layout (Living Room)::

    ┌──────────┬──────────┬──────────┬──────────┐
    │  Living  │  Scene:  │  Scene:  │ Bedroom  │   ← row 1
    │  Room    │  Movie   │  Bright  │  →       │
    ├──────────┼──────────┼──────────┼──────────┤
    │  Lamp    │  Fan     │  AC      │  All Off │   ← row 2
    │  Toggle  │  Toggle  │  Toggle  │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │  Light   │ Colour   │   Room   │  Fan     │   ← touchscreen
    │ Bright.  │  Temp    │  Temp    │ Balance  │
    └──────────┴──────────┴──────────┴──────────┘
        dial 0     dial 1     dial 2     dial 3

Run with::

    python examples/smart_home.py
"""

import asyncio
import logging

from deckboard import (
    BalanceSlider,
    BrightnessSlider,
    Deck,
    KelvinSlider,
    TemperatureSlider,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_room_page(
    deck: Deck,
    name: str,
    *,
    other_page: str,
    icon: str,
    other_icon: str,
) -> dict[str, object]:
    """Wire up buttons and sliders for a single room page.

    Returns a dict of slider references so the caller can inspect them.
    """
    page = deck.page(name)

    # -- Row 1: scenes & navigation ----------------------------------------

    page.button(0).set_icon(icon).set_label(name)
    page.button(1).set_icon("mdi:movie-open").set_label("Movie")
    page.button(2).set_icon("mdi:white-balance-sunny").set_label("Bright")
    page.button(3).set_icon(other_icon).set_label(f"{other_page} →")

    # -- Row 2: device toggles ---------------------------------------------

    page.button(4).set_icon("mdi:lamp").set_label("Lamp")
    page.button(5).set_icon("mdi:fan").set_label("Fan")
    page.button(6).set_icon("mdi:air-conditioner").set_label("AC")
    page.button(7).set_icon("mdi:power").set_label("All Off")

    # -- Touchscreen sliders -----------------------------------------------

    bright = BrightnessSlider(value=80)
    kelvin = KelvinSlider(value=4000)
    temp = TemperatureSlider(value=22)
    bal = BalanceSlider("Fan Spd", value=50)

    page.widget(0).add_slider(bright)
    page.widget(1).add_slider(kelvin)
    page.widget(2).add_slider(temp)
    page.widget(3).add_slider(bal)

    # -- Scene handlers (set slider values in one shot) --------------------

    @page.button(1).on_press
    async def on_movie() -> None:
        bright.set_value(20)
        kelvin.set_value(2700)
        print(f"[{name}] Movie scene: dim warm light")
        await deck.refresh()

    @page.button(2).on_press
    async def on_bright() -> None:
        bright.set_value(100)
        kelvin.set_value(6500)
        print(f"[{name}] Bright scene: full cool light")
        await deck.refresh()

    # -- Page navigation ---------------------------------------------------

    @page.button(3).on_press
    async def on_switch() -> None:
        print(f"Switching to {other_page}")
        await deck.set_page(other_page)

    # -- Device toggles (simulated) ----------------------------------------

    devices = {"lamp": True, "fan": True, "ac": True}

    @page.button(4).on_press
    async def on_lamp() -> None:
        devices["lamp"] = not devices["lamp"]
        state = "ON" if devices["lamp"] else "OFF"
        print(f"[{name}] Lamp: {state}")

    @page.button(5).on_press
    async def on_fan() -> None:
        devices["fan"] = not devices["fan"]
        state = "ON" if devices["fan"] else "OFF"
        print(f"[{name}] Fan: {state}")

    @page.button(6).on_press
    async def on_ac() -> None:
        devices["ac"] = not devices["ac"]
        state = "ON" if devices["ac"] else "OFF"
        print(f"[{name}] AC: {state}")

    @page.button(7).on_press
    async def on_all_off() -> None:
        for key in devices:
            devices[key] = False
        bright.set_value(0)
        print(f"[{name}] All devices OFF, lights at 0%")
        await deck.refresh()

    return {
        "brightness": bright,
        "kelvin": kelvin,
        "temperature": temp,
        "balance": bal,
    }


async def main() -> None:
    async with Deck(brightness=75) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        # Build both room pages
        build_room_page(
            deck,
            "Living Room",
            other_page="Bedroom",
            icon="mdi:sofa",
            other_icon="mdi:bed",
        )
        build_room_page(
            deck,
            "Bedroom",
            other_page="Living Room",
            icon="mdi:bed",
            other_icon="mdi:sofa",
        )

        # Start on the living room page
        await deck.set_page("Living Room")
        print("\nSmart home dashboard ready!")
        print("  Turn dials to adjust brightness, colour temp, room temp, fan speed.")
        print("  Button 1 = Movie scene, Button 2 = Bright scene.")
        print("  Button 3 = Switch rooms.")
        print("  Button 7 = All Off.")
        print("  Ctrl+C to exit.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
