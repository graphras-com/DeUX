#!/usr/bin/env python3
"""Light widget — ready-to-use light control with Brightness and Kelvin sliders.

Shows how ``LightCard`` bundles a brightness slider and a colour-temperature
(Kelvin) slider into a single widget zone.  Buttons provide scene presets and
a print-values action.

Layout::

    ┌──────────┬──────────┬──────────┬──────────┐
    │  Reset   │  Movie   │  Bright  │   Exit   │   ← buttons (row 1)
    │          │  Night   │  Day     │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │  Candle  │  Sunset  │  Reading │  Focus   │   ← buttons (row 2) — presets
    │          │          │          │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │          │          │          │Brightness│   ← touchscreen
    │          │          │          │  Kelvin  │
    └──────────┴──────────┴──────────┴──────────┘
        enc 0      enc 1      enc 2      enc 3

Run with::

    python examples/light_widget.py
"""

import asyncio
import logging

from deckboard import Deck, LightCard

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.screen("light")

        # -- LightCard on zone 3 (dial 3) -------------------------------
        #    One line instead of creating two sliders + a StackCard.

        light = LightCard(3, brightness=80, kelvin=4000)
        page.set_card(3, light)

        # -- Buttons (row 1) — actions ------------------------------------

        page.key(0).set_icon("mdi:restore").set_label("Reset")
        page.key(1).set_icon("mdi:movie-open").set_label("Movie")
        page.key(2).set_icon("mdi:white-balance-sunny").set_label("Bright")
        page.key(3).set_icon("mdi:close-circle").set_label("Exit")

        # -- Buttons (row 2) — scene presets -------------------------------

        page.key(4).set_icon("mdi:candle").set_label("Candle")
        page.key(5).set_icon("mdi:weather-sunset").set_label("Sunset")
        page.key(6).set_icon("mdi:book-open-variant").set_label("Reading")
        page.key(7).set_icon("mdi:head-lightbulb").set_label("Focus")

        # -- Helper to apply a preset and refresh --------------------------

        async def apply_preset(brightness: float, kelvin: float, name: str) -> None:
            light.brightness.set_value(brightness)
            light.kelvin.set_value(kelvin)
            await deck.refresh()
            print(f"Preset: {name}")

        # -- Button handlers -----------------------------------------------

        @page.key(0).on_press
        async def on_reset() -> None:
            await apply_preset(80, 4000, "Reset")

        @page.key(1).on_press
        async def on_movie() -> None:
            await apply_preset(20, 2700, "Movie Night")

        @page.key(2).on_press
        async def on_bright() -> None:
            await apply_preset(100, 6500, "Bright Day")

        @page.key(3).on_press
        async def on_exit() -> None:
            print("Exiting...")
            await deck.stop()

        # -- Scene presets -------------------------------------------------

        @page.key(4).on_press
        async def on_candle() -> None:
            await apply_preset(10, 2000, "Candle")

        @page.key(5).on_press
        async def on_sunset() -> None:
            await apply_preset(50, 3000, "Sunset")

        @page.key(6).on_press
        async def on_reading() -> None:
            await apply_preset(70, 4500, "Reading")

        @page.key(7).on_press
        async def on_focus() -> None:
            await apply_preset(100, 5500, "Focus")

        # -- Go! -----------------------------------------------------------

        await deck.set_screen("light")
        print("\nLight widget ready!")
        print("  Turn encoder 3 to adjust the active slider.")
        print("  Press encoder 3 to toggle Brightness ↔ Kelvin.")
        print("  Row 1: Reset, Movie Night, Bright Day, Exit.")
        print("  Row 2: Candle, Sunset, Reading, Focus presets.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
