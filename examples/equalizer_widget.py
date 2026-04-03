#!/usr/bin/env python3
"""Equalizer widget — ready-to-use EQ panel with Sub, Bass, Treble, and Balance.

Shows how ``EqualizerWidget`` replaces manual slider assembly with a single
class that bundles three EQ bands and a balance control.  Compare this with
the manual setup in ``slider_widgets.py`` (zone 3) or ``media_controller.py``.

Layout::

    ┌──────────┬──────────┬──────────┬──────────┐
    │  Reset   │  Flat    │  Print   │   Exit   │   ← buttons (row 1)
    │          │          │  Values  │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │  Bass    │  V-Shape │  Vocal   │  Warm    │   ← buttons (row 2) — presets
    │  Boost   │          │          │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │          │          │          │Sub+Bass │   ← touchscreen
    │          │          │          │+Treble  │
    │          │          │          │+Balance │
    └──────────┴──────────┴──────────┴──────────┘
        dial 0     dial 1     dial 2     dial 3

Run with::

    python examples/equalizer_widget.py
"""

import asyncio
import logging

from deckboard import Deck, EqualizerWidget

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.screen("equalizer")

        # -- EqualizerWidget on zone 3 (dial 3) ---------------------------
        #    One line instead of creating four sliders + a StackCard.

        eq = EqualizerWidget(3, sub=50, bass=50, treble=50, balance=50)
        page.set_card(3, eq)

        # -- Buttons (row 1) — actions ------------------------------------

        page.button(0).set_icon("mdi:restore").set_label("Reset")
        page.button(1).set_icon("mdi:tune-vertical").set_label("Flat")
        page.button(2).set_icon("mdi:printer").set_label("Values")
        page.button(3).set_icon("mdi:close-circle").set_label("Exit")

        # -- Buttons (row 2) — EQ presets ----------------------------------

        page.button(4).set_icon("mdi:speaker").set_label("Bass+")
        page.button(5).set_icon("mdi:alpha-v-box").set_label("V-Shape")
        page.button(6).set_icon("mdi:microphone").set_label("Vocal")
        page.button(7).set_icon("mdi:weather-sunny").set_label("Warm")

        # -- Helper to apply a preset and refresh --------------------------

        async def apply_preset(
            sub: float, bass: float, treble: float, balance: float, name: str
        ) -> None:
            eq.sub.set_value(sub)
            eq.bass.set_value(bass)
            eq.treble.set_value(treble)
            eq.balance.set_value(balance)
            await deck.refresh()
            print(f"Preset: {name}")

        # -- Button handlers -----------------------------------------------

        @page.button(0).on_press
        async def on_reset() -> None:
            await apply_preset(50, 50, 50, 50, "Reset")

        @page.button(1).on_press
        async def on_flat() -> None:
            await apply_preset(0, 0, 0, 50, "Flat")

        @page.button(2).on_press
        async def on_print() -> None:
            print(
                f"Sub={eq.sub.format_value()}, "
                f"Bass={eq.bass.format_value()}, "
                f"Treble={eq.treble.format_value()}, "
                f"Balance={eq.balance.format_value()}"
            )

        @page.button(3).on_press
        async def on_exit() -> None:
            print("Exiting...")
            await deck.stop()

        # -- EQ presets ----------------------------------------------------

        @page.button(4).on_press
        async def on_bass_boost() -> None:
            await apply_preset(80, 75, 30, 50, "Bass Boost")

        @page.button(5).on_press
        async def on_v_shape() -> None:
            await apply_preset(70, 65, 70, 50, "V-Shape")

        @page.button(6).on_press
        async def on_vocal() -> None:
            await apply_preset(20, 40, 60, 50, "Vocal")

        @page.button(7).on_press
        async def on_warm() -> None:
            await apply_preset(60, 55, 25, 45, "Warm")

        # -- Go! -----------------------------------------------------------

        await deck.set_screen("equalizer")
        print("\nEqualizer widget ready!")
        print("  Turn dial 3 to adjust the active band.")
        print("  Press dial 3 to cycle Sub → Bass → Treble → Balance.")
        print("  Row 1: Reset, Flat, Print Values, Exit.")
        print("  Row 2: Bass Boost, V-Shape, Vocal, Warm presets.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
