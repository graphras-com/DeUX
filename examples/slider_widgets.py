#!/usr/bin/env python3
"""Stack card showcase — every slider type on one layout.

Demonstrates all six slider types on the Stream Deck+ touchscreen.
Each dial controls the sliders in its zone; press the dial to cycle
between sliders when a zone has more than one.

Layout::

    ┌──────────┬──────────┬──────────┬──────────┐
    │  Reset   │  Print   │          │   Exit   │   ← buttons (row 1)
    │  All     │  Values  │          │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │          │          │          │          │   ← buttons (row 2)
    ├──────────┼──────────┼──────────┼──────────┤
    │ Volume   │ Bright + │  Kelvin  │Sub+Bass │   ← touchscreen
    │          │  Temp    │          │+Treble  │
    │          │          │          │+Balance │
    └──────────┴──────────┴──────────┴──────────┘
        dial 0     dial 1     dial 2     dial 3

Run with::

    python examples/slider_widgets.py
"""

import asyncio
import logging

from deckboard import (
    BalanceSlider,
    BrightnessSlider,
    Deck,
    EqualizerSlider,
    KelvinSlider,
    StackCard,
    TemperatureSlider,
    VolumeSlider,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.screen("sliders")

        # -- Buttons -------------------------------------------------------

        page.key(0).set_icon("mdi:restore").set_label("Reset All")
        page.key(1).set_icon("mdi:printer").set_label("Values")
        page.key(7).set_icon("mdi:close-circle").set_label("Exit")

        # -- Zone 0: Volume (single large slider) -------------------------

        vol = VolumeSlider(value=50)
        sw0 = StackCard(0)
        sw0.add_control(vol)
        page.set_card(0, sw0)

        # -- Zone 1: Brightness + Temperature (two large sliders) ----------
        #    Press dial 1 to cycle between them.

        bright = BrightnessSlider(value=80)
        temp = TemperatureSlider(value=20)
        sw1 = StackCard(1)
        sw1.add_control(bright, default=True)
        sw1.add_control(temp)
        sw1.set_selection_timeout(3)  # revert to brightness after 3s
        page.set_card(1, sw1)

        # -- Zone 2: Kelvin (single large slider) -------------------------

        kelvin = KelvinSlider(value=4000)
        sw2 = StackCard(2)
        sw2.add_control(kelvin)
        page.set_card(2, sw2)

        # -- Zone 3: Sub + Bass + Treble + Balance (four small sliders) ----
        #    Press dial 3 to cycle through them.

        sub = EqualizerSlider("Sub", value=50)
        bass = EqualizerSlider("Bass", value=50)
        treble = EqualizerSlider("Treble", value=50)
        bal = BalanceSlider(value=50)
        sw3 = StackCard(3)
        sw3.add_control(sub, default=True)
        sw3.add_control(bass)
        sw3.add_control(treble)
        sw3.add_control(bal)
        sw3.set_selection_timeout(5)
        page.set_card(3, sw3)

        # -- Button handlers -----------------------------------------------

        @page.key(0).on_press
        async def on_reset() -> None:
            """Reset every slider to its default value."""
            vol.set_value(50)
            bright.set_value(80)
            temp.set_value(20)
            kelvin.set_value(4000)
            sub.set_value(50)
            bass.set_value(50)
            treble.set_value(50)
            bal.set_value(50)
            await deck.refresh()
            print("All sliders reset.")

        @page.key(1).on_press
        async def on_print() -> None:
            """Print current slider values to the console."""
            print(
                f"Volume={vol.format_value()}, "
                f"Brightness={bright.format_value()}, "
                f"Temp={temp.format_value()}, "
                f"Kelvin={kelvin.format_value()}, "
                f"Sub={sub.format_value()}, "
                f"Bass={bass.format_value()}, "
                f"Treble={treble.format_value()}, "
                f"Balance={bal.format_value()}"
            )

        @page.key(7).on_press
        async def on_exit() -> None:
            print("Exiting...")
            await deck.stop()

        # -- Go! -----------------------------------------------------------

        await deck.set_screen("sliders")
        print("\nSlider showcase ready!")
        print("  Turn dials to adjust values.")
        print("  Press dial 1 to cycle Brightness / Temperature.")
        print("  Press dial 3 to cycle Sub / Bass / Treble / Balance.")
        print("  Button 0 = Reset All, Button 1 = Print Values.")
        print("  Button 7 = Exit.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
