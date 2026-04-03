#!/usr/bin/env python3
"""Dual-value widget showcase — icon + value pairs on the touchscreen.

Demonstrates :class:`LargeDualValue` and :class:`SmallDualValue`
elements inside a :class:`TouchPanel`.  These widgets display two
side-by-side sections, each with a small icon and a left-aligned
value — ideal for showing paired readings (e.g. temperature +
humidity, upload + download speeds).

Layout::

    ┌──────────┬──────────┬──────────┬──────────┐
    │ Refresh  │          │          │   Exit   │   ← buttons (row 1)
    ├──────────┼──────────┼──────────┼──────────┤
    │          │          │          │          │   ← buttons (row 2)
    ├──────────┼──────────┼──────────┼──────────┤
    │ 🌡 22°C  │ ↑ 95 Mb  │ ☀ 80%   │ 🌡 22°C  │   ← touchscreen
    │ 💧 45%   │ ↓ 48 Mb  │ 🔆 4000K │ 💧 45%   │
    │          │ 📶 -42dB │ 🌡 22°C  │ ☀ 80%   │
    │          │ ⏱ 12ms  │ 💧 45%   │ 🔆 4000K │
    └──────────┴──────────┴──────────┴──────────┘
        dial 0     dial 1     dial 2     dial 3

Zone 0: Two LargeDualValue rows (climate readings).
Zone 1: Four SmallDualValue rows (network stats).
Zone 2: One LargeDualValue + two SmallDualValue rows (mixed).
Zone 3: Two LargeDualValue + VolumeSlider (mixed with slider).

Run with::

    python examples/dual_value.py
"""

import asyncio
import logging

from deckboard import Deck, TouchPanel, VolumeSlider
from deckboard.widgets.dual_value import LargeDualValue, SmallDualValue

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.page("dual_value")

        # -- Buttons -------------------------------------------------------

        page.button(0).set_icon("mdi:refresh").set_label("Refresh")
        page.button(7).set_icon("mdi:close-circle").set_label("Exit")

        # -- Zone 0: Two large dual-value rows (climate) -------------------
        #    Each row shows a pair of readings side by side.

        climate1 = LargeDualValue("22°C", "45%")
        climate2 = LargeDualValue("1013hPa", "3.2m/s")

        panel0 = TouchPanel(0)
        panel0.add_element(climate1)
        panel0.add_element(climate2)
        page.set_widget(0, panel0)

        # -- Zone 1: Four small dual-value rows (network) ------------------
        #    Compact layout for dense information.

        net1 = SmallDualValue("95 Mb", "48 Mb")
        net2 = SmallDualValue("-42dBm", "12ms")
        net3 = SmallDualValue("5 GHz", "WPA3")
        net4 = SmallDualValue("24 dev", "1.2GB")

        panel1 = TouchPanel(1)
        panel1.add_element(net1)
        panel1.add_element(net2)
        panel1.add_element(net3)
        panel1.add_element(net4)
        page.set_widget(1, panel1)

        # -- Zone 2: Mixed large + small dual-value rows -------------------
        #    One large row on top, two small rows below.

        mixed_large = LargeDualValue("80%", "4000K")
        mixed_small1 = SmallDualValue("22°C", "45%")
        mixed_small2 = SmallDualValue("On", "Auto")

        panel2 = TouchPanel(2)
        panel2.add_element(mixed_large)
        panel2.add_element(mixed_small1)
        panel2.add_element(mixed_small2)
        page.set_widget(2, panel2)

        # -- Zone 3: Dual-value + volume slider ----------------------------
        #    Demonstrates mixing dual-value with a slider.

        info_row = LargeDualValue("22°C", "45%")
        vol = VolumeSlider(value=65)

        panel3 = TouchPanel(3)
        panel3.add_element(info_row)
        panel3.add_element(vol)
        page.set_widget(3, panel3)

        # -- Button handlers -----------------------------------------------

        @page.button(0).on_press
        async def on_refresh() -> None:
            """Simulate refreshing sensor values."""
            climate1.set_left_value("23°C")
            climate1.set_right_value("42%")
            climate2.set_left_value("1015hPa")
            net1.set_left_value("102 Mb")
            net2.set_right_value("8ms")
            await deck.refresh()
            print("Values refreshed.")

        @page.button(7).on_press
        async def on_exit() -> None:
            print("Exiting...")
            await deck.stop()

        # -- Go! -----------------------------------------------------------

        await deck.set_page("dual_value")
        print("\nDual-value widget showcase ready!")
        print("  Zone 0: Climate readings (temp, humidity, pressure, wind).")
        print("  Zone 1: Network stats (upload, download, signal, latency).")
        print("  Zone 2: Mixed large + small dual-value rows.")
        print("  Zone 3: Dual-value info row + volume slider.")
        print("  Button 0 = Refresh values, Button 7 = Exit.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
