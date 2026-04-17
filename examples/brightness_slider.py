#!/usr/bin/env python3
"""Example: brightness slider using a .dsui slider binding.

Demonstrates the ``slider`` binding type which translates an SVG
element between two fixed positions (min_pos and max_pos) proportional
to a 0.0-1.0 value.  Unlike ``range`` which scales width/height,
``slider`` moves a fixed-size indicator along a track.

Run with::

    python examples/brightness_slider.py
"""

import asyncio
import logging
from pathlib import Path

from deckboard import Deck, DsuiCard, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

EXAMPLES_DIR = Path(__file__).parent


async def main():
    spec = load_package(EXAMPLES_DIR / "BrightnessSlider.dsui")

    print(f"Loaded: {spec.name} (v{spec.version})")
    print(f"  Bindings: {sorted(spec.bindings)}")
    print(f"  Events:   {[e.name for e in spec.events]}")

    async with Deck(brightness=80) as deck:
        screen = deck.screen("main")

        card = DsuiCard(spec)
        brightness = 0.5

        card.set("brightness", brightness)
        card.set("value_text", f"{int(brightness * 100)}%")
        screen.set_card(0, card)

        @card.on("brightness_up")
        async def on_up():
            nonlocal brightness
            brightness = min(1.0, brightness + 0.05)
            card.set("brightness", brightness)
            card.set("value_text", f"{int(brightness * 100)}%")
            deck.set_brightness(int(brightness * 100))
            print(f"Brightness: {int(brightness * 100)}%")
            await deck.refresh()

        @card.on("brightness_down")
        async def on_down():
            nonlocal brightness
            brightness = max(0.0, brightness - 0.05)
            card.set("brightness", brightness)
            card.set("value_text", f"{int(brightness * 100)}%")
            deck.set_brightness(int(brightness * 100))
            print(f"Brightness: {int(brightness * 100)}%")
            await deck.refresh()

        @card.on("brightness_reset")
        async def on_reset():
            nonlocal brightness
            brightness = 0.5
            card.set("brightness", brightness)
            card.set("value_text", f"{int(brightness * 100)}%")
            deck.set_brightness(int(brightness * 100))
            print("Brightness reset to 50%")
            await deck.refresh()

        await deck.set_screen("main")
        print("\nDeck ready!")
        print("  Encoder 0: turn to adjust brightness, press to reset to 50%")
        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
