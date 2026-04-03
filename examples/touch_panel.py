#!/usr/bin/env python3
"""Touch panel showcase — mixing text labels with sliders.

Demonstrates the :class:`TouchPanel` container with :class:`LargeText`,
:class:`SmallText`, and slider sub-elements.  Text elements display
read-only information while sliders remain interactive.  Pressing a
dial cycles only through the sliders; text elements are skipped.

Layout::

    ┌──────────┬──────────┬──────────┬──────────┐
    │  Reset   │  Print   │          │   Exit   │   ← buttons (row 1)
    │  All     │  Values  │          │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │          │          │          │          │   ← buttons (row 2)
    ├──────────┼──────────┼──────────┼──────────┤
    │ "Room"   │ Volume + │ Bass   ← │ Status ← │   ← touchscreen
    │  Bright  │ "65%"    │ Treble   │ Sub      │
    │          │          │ "EQ"     │ Balance  │
    │          │          │ Balance  │ "OK"     │
    └──────────┴──────────┴──────────┴──────────┘
        dial 0     dial 1     dial 2     dial 3

Zone 0: Large text header + large slider underneath.
Zone 1: Large slider on top + large text readout below.
Zone 2: Two small sliders + small text label + small slider (4 rows).
Zone 3: Small text status + two small sliders + small text footer.

Run with::

    python examples/touch_panel.py
"""

import asyncio
import logging

from deckboard import (
    BalanceSlider,
    BrightnessSlider,
    Deck,
    EqualizerSlider,
    TouchPanel,
    VolumeSlider,
)
from deckboard.widgets.text import LargeText, SmallText

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.page("panels")

        # -- Buttons -------------------------------------------------------

        page.button(0).set_icon("mdi:restore").set_label("Reset All")
        page.button(1).set_icon("mdi:printer").set_label("Values")
        page.button(7).set_icon("mdi:close-circle").set_label("Exit")

        # -- Zone 0: Large text header + brightness slider -----------------
        #    The text shows a room name; the slider controls brightness.
        #    Only one selectable element → dial press does nothing extra.

        header0 = LargeText("Room", color="#aaaaaa")
        bright = BrightnessSlider(value=80)

        panel0 = TouchPanel(0)
        panel0.add_element(header0)
        panel0.add_element(bright)
        page.set_widget(0, panel0)

        # -- Zone 1: Volume slider + text readout --------------------------
        #    The slider adjusts volume; the text shows the formatted value
        #    and is updated programmatically on every dial turn.

        vol = VolumeSlider(value=65)
        readout = LargeText(vol.format_value(), color="#5599ff")

        panel1 = TouchPanel(1)
        panel1.add_element(vol)
        panel1.add_element(readout)
        page.set_widget(1, panel1)

        # -- Zone 2: Two EQ sliders + text label + balance slider ----------
        #    Press dial 2 to cycle among the three sliders (Bass, Treble,
        #    Balance).  The text label "EQ" is decorative and skipped.

        bass = EqualizerSlider("Bass", value=50)
        treble = EqualizerSlider("Treble", value=50)
        eq_label = SmallText("EQ", color="#aaaaaa")
        bal2 = BalanceSlider(value=50)

        panel2 = TouchPanel(2)
        panel2.add_element(bass, default=True)
        panel2.add_element(treble)
        panel2.add_element(eq_label)
        panel2.add_element(bal2)
        panel2.set_selection_timeout(4)
        page.set_widget(2, panel2)

        # -- Zone 3: Status text + two sliders + footer text ---------------
        #    Demonstrates text at both ends of the stack.  Pressing dial 3
        #    cycles between Sub and Balance only.

        status = SmallText("Online", color="#00cc66")
        sub = EqualizerSlider("Sub", value=50)
        bal3 = BalanceSlider(value=50)
        footer = SmallText("OK", color="#aaaaaa")

        panel3 = TouchPanel(3)
        panel3.add_element(status)
        panel3.add_element(sub, default=True)
        panel3.add_element(bal3)
        panel3.add_element(footer)
        panel3.set_selection_timeout(4)
        page.set_widget(3, panel3)

        # -- Dial handler: update volume readout on turn -------------------

        @page.dial(1).on_turn
        async def on_vol_turn(direction: int) -> None:
            # The slider value is adjusted automatically by TouchPanel;
            # we just need to sync the text readout.
            readout.set_text(vol.format_value())
            await deck.refresh()

        # -- Button handlers -----------------------------------------------

        @page.button(0).on_press
        async def on_reset() -> None:
            """Reset every slider to its default value."""
            bright.set_value(80)
            vol.set_value(65)
            readout.set_text(vol.format_value())
            bass.set_value(50)
            treble.set_value(50)
            bal2.set_value(50)
            sub.set_value(50)
            bal3.set_value(50)
            status.set_text("Online")
            status.set_color("#00cc66")
            footer.set_text("OK")
            await deck.refresh()
            print("All values reset.")

        @page.button(1).on_press
        async def on_print() -> None:
            """Print current values to the console."""
            print(
                f"Brightness={bright.format_value()}, "
                f"Volume={vol.format_value()}, "
                f"Bass={bass.format_value()}, "
                f"Treble={treble.format_value()}, "
                f"Balance(z2)={bal2.format_value()}, "
                f"Sub={sub.format_value()}, "
                f"Balance(z3)={bal3.format_value()}, "
                f"Status={status.text}, "
                f"Footer={footer.text}"
            )

        @page.button(7).on_press
        async def on_exit() -> None:
            print("Exiting...")
            await deck.stop()

        # -- Go! -----------------------------------------------------------

        await deck.set_page("panels")
        print("\nTouch panel showcase ready!")
        print("  Zone 0: 'Room' header + Brightness slider.")
        print("  Zone 1: Volume slider + live text readout.")
        print("  Zone 2: Bass + Treble + 'EQ' label + Balance (press dial to cycle).")
        print("  Zone 3: Status + Sub + Balance + footer (press dial to cycle).")
        print("  Button 0 = Reset All, Button 1 = Print Values, Button 7 = Exit.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
