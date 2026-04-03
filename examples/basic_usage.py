#!/usr/bin/env python3
"""Basic usage example for the deckboard library.

Demonstrates multi-page UI with buttons, dials, touchscreen widgets,
and event handlers on an Elgato Stream Deck+.

Run with::

    python examples/basic_usage.py
"""

import asyncio
import logging

from deckboard import Deck

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main():
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")
        print(f"  Keys: {info.key_count} ({info.key_layout[0]}x{info.key_layout[1]})")
        print(f"  Dials: {info.dial_count}")
        print(f"  Key size: {info.key_pixel_size[0]}x{info.key_pixel_size[1]}")
        print(f"  Touchscreen: {info.touchscreen_size[0]}x{info.touchscreen_size[1]}")

        # -- Main page -----------------------------------------------------

        main_page = deck.screen("main")

        # Row 1: navigation icons
        main_page.button(0).set_icon("mdi:home").set_label("Home")
        main_page.button(1).set_icon("mdi:music").set_label("Music")
        main_page.button(2).set_icon("mdi:lightbulb-outline").set_label("Lights")
        main_page.button(3).set_icon("mdi:thermometer").set_label("Climate")

        # Row 2: actions
        main_page.button(4).set_icon("mdi:play")
        main_page.button(5).set_icon("mdi:pause")
        main_page.button(6).set_icon("mdi:skip-next")
        main_page.button(7).set_icon("mdi:cog").set_label("Settings")

        # Touchscreen widgets (under each dial)
        main_page.card(0).set_icon("mdi:volume-high").set_label("Volume").set_value(
            "50%"
        )
        main_page.card(1).set_icon("mdi:lightbulb-on").set_label(
            "Brightness"
        ).set_value("80%")
        main_page.card(2).set_icon("mdi:thermostat").set_label("Temp").set_value(
            "22°C"
        )
        main_page.card(3).set_icon("mdi:fan").set_label("Fan").set_value("Auto")

        # Button event handlers
        volume = 50

        @main_page.button(0).on_press
        async def on_home():
            print("Home pressed!")

        @main_page.button(7).on_press
        async def on_settings():
            print("Switching to settings page")
            await deck.set_screen("settings")

        @main_page.button(4).on_press
        async def on_play():
            print("Play!")

        @main_page.button(5).on_press
        async def on_pause():
            print("Pause!")

        @main_page.button(6).on_press
        async def on_skip():
            print("Skip!")

        # Dial handlers
        @main_page.dial(0).on_turn
        async def on_volume_turn(direction: int):
            nonlocal volume
            volume = max(0, min(100, volume + direction * 5))
            print(f"Volume: {volume}%")
            main_page.card(0).set_value(f"{volume}%")
            await deck.refresh()

        @main_page.dial(0).on_press
        async def on_volume_mute():
            print("Volume muted!")
            main_page.card(0).set_icon("mdi:volume-off").set_value("Muted")
            await deck.refresh()

        @main_page.dial(0).on_release
        async def on_volume_unmute():
            main_page.card(0).set_icon("mdi:volume-high").set_value(f"{volume}%")
            await deck.refresh()

        # Widget touch handlers
        @main_page.card(0).on_tap
        async def on_volume_tap():
            print("Volume widget tapped!")

        # -- Settings page -------------------------------------------------

        settings = deck.screen("settings")

        settings.button(0).set_icon("mdi:arrow-left").set_label("Back")
        settings.button(1).set_icon("mdi:brightness-6").set_label("Bright")
        settings.button(2).set_icon("mdi:information-outline").set_label("Info")

        settings.card(0).set_label("Settings")
        settings.card(3).set_icon("mdi:close").set_label("Exit")

        @settings.button(0).on_press
        async def on_back():
            print("Back to main page")
            await deck.set_screen("main")

        @settings.dial(0).on_turn
        async def on_brightness_turn(direction: int):
            new_brightness = deck.brightness + direction * 10
            await deck.set_brightness(new_brightness)
            settings.card(0).set_value(f"{new_brightness}%")
            await deck.refresh()
            print(f"Brightness: {new_brightness}%")

        @settings.card(3).on_tap
        async def on_exit():
            print("Exit tapped - stopping deck")
            await deck.stop()

        # -- Activate main page and wait -----------------------------------

        await deck.set_screen("main")
        print("\nDeck is ready! Press buttons, turn dials, touch the screen.")
        print("Press dial 0 to mute, turn dial 0 for volume.")
        print("Press button 7 (Settings) to switch pages.")
        print("Tap widget 3 on settings page to exit.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
