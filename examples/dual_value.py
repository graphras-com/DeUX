#!/usr/bin/env python3
"""Dual-value card showcase — icon + value pairs on the touchscreen.

Demonstrates :class:`LargeDualValue` and :class:`SmallDualValue`
elements inside a :class:`StackCard`.  These cards display two
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
Zone 3: LargeDualValue info row + VolumeSlider (mixed with slider).

Run with::

    python examples/dual_value.py
"""

import asyncio
import logging

from deckboard import Deck, StackCard, VolumeSlider
from deckboard.widgets.dual_value import LargeDualValue, SmallDualValue

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.screen("dual_value")

        # -- Pre-fetch icons -----------------------------------------------
        #    DualValue elements accept PIL Images directly, so we fetch
        #    them via the deck's IconManager before building the panels.

        icon_temp = await deck.icons.get("mdi:thermometer", color="white")
        icon_humidity = await deck.icons.get("mdi:water-percent", color="#55aaff")
        icon_pressure = await deck.icons.get("mdi:gauge", color="#aaaaaa")
        icon_wind = await deck.icons.get("mdi:weather-windy", color="#aaaaaa")
        icon_upload = await deck.icons.get("mdi:arrow-up-bold", color="#00cc66")
        icon_download = await deck.icons.get("mdi:arrow-down-bold", color="#ff6644")
        icon_signal = await deck.icons.get("mdi:wifi", color="#5599ff")
        icon_latency = await deck.icons.get("mdi:timer-outline", color="#ffaa00")
        icon_freq = await deck.icons.get("mdi:access-point", color="#aaaaaa")
        icon_security = await deck.icons.get("mdi:lock", color="#00cc66")
        icon_devices = await deck.icons.get("mdi:devices", color="#aaaaaa")
        icon_data = await deck.icons.get("mdi:database", color="#aaaaaa")
        icon_bright = await deck.icons.get("mdi:white-balance-sunny", color="#ffcc00")
        icon_kelvin = await deck.icons.get("mdi:lightbulb-on", color="#ffaa44")
        icon_power = await deck.icons.get("mdi:power", color="#00cc66")
        icon_fan = await deck.icons.get("mdi:fan", color="#aaaaaa")

        # -- Buttons -------------------------------------------------------

        page.button(0).set_icon("mdi:refresh").set_label("Refresh")
        page.button(7).set_icon("mdi:close-circle").set_label("Exit")

        # -- Zone 0: Two large dual-value rows (climate) -------------------
        #    Each row shows a pair of readings side by side.

        climate1 = LargeDualValue(
            "22°C", "45%", left_icon=icon_temp, right_icon=icon_humidity
        )
        climate2 = LargeDualValue(
            "1013hPa", "3.2m/s", left_icon=icon_pressure, right_icon=icon_wind
        )

        panel0 = StackCard(0)
        panel0.add_element(climate1)
        panel0.add_element(climate2)
        page.set_card(0, panel0)

        # -- Zone 1: Four small dual-value rows (network) ------------------
        #    Compact layout for dense information.

        net1 = SmallDualValue(
            "95 Mb", "48 Mb", left_icon=icon_upload, right_icon=icon_download
        )
        net2 = SmallDualValue(
            "-42dBm", "12ms", left_icon=icon_signal, right_icon=icon_latency
        )
        net3 = SmallDualValue(
            "5 GHz", "WPA3", left_icon=icon_freq, right_icon=icon_security
        )
        net4 = SmallDualValue(
            "24 dev", "1.2GB", left_icon=icon_devices, right_icon=icon_data
        )

        panel1 = StackCard(1)
        panel1.add_element(net1)
        panel1.add_element(net2)
        panel1.add_element(net3)
        panel1.add_element(net4)
        page.set_card(1, panel1)

        # -- Zone 2: Mixed large + small dual-value rows -------------------
        #    One large row on top, two small rows below.

        mixed_large = LargeDualValue(
            "80%", "4000K", left_icon=icon_bright, right_icon=icon_kelvin
        )
        mixed_small1 = SmallDualValue(
            "22°C", "45%", left_icon=icon_temp, right_icon=icon_humidity
        )
        mixed_small2 = SmallDualValue(
            "On", "Auto", left_icon=icon_power, right_icon=icon_fan
        )

        panel2 = StackCard(2)
        panel2.add_element(mixed_large)
        panel2.add_element(mixed_small1)
        panel2.add_element(mixed_small2)
        page.set_card(2, panel2)

        # -- Zone 3: Dual-value + volume slider ----------------------------
        #    Demonstrates mixing dual-value with a slider.

        info_row = LargeDualValue(
            "22°C", "45%", left_icon=icon_temp, right_icon=icon_humidity
        )
        vol = VolumeSlider(value=65)

        panel3 = StackCard(3)
        panel3.add_element(info_row)
        panel3.add_element(vol)
        page.set_card(3, panel3)

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

        await deck.set_screen("dual_value")
        print("\nDual-value widget showcase ready!")
        print("  Zone 0: Climate readings (temp, humidity, pressure, wind).")
        print("  Zone 1: Network stats (upload, download, signal, latency).")
        print("  Zone 2: Mixed large + small dual-value rows.")
        print("  Zone 3: Dual-value info row + volume slider.")
        print("  Button 0 = Refresh values, Button 7 = Exit.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
