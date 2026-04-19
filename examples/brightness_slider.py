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

        card.set_range("brightness", 50, min_val=0, max_val=100)
        card.set("value_text", "50%")
        screen.set_card(0, card)

        @card.on("brightness_up")
        async def on_up():
            val = card.adjust_range("brightness", 5, min_val=0, max_val=100)
            card.set("value_text", f"{int(val)}%")
            deck.set_brightness(int(val))
            print(f"Brightness: {int(val)}%")
            await deck.refresh()

        @card.on("brightness_down")
        async def on_down():
            val = card.adjust_range("brightness", -5, min_val=0, max_val=100)
            card.set("value_text", f"{int(val)}%")
            deck.set_brightness(int(val))
            print(f"Brightness: {int(val)}%")
            await deck.refresh()

        @card.on("brightness_reset")
        async def on_reset():
            card.set_range("brightness", 50, min_val=0, max_val=100)
            card.set("value_text", "50%")
            deck.set_brightness(50)
            print("Brightness reset to 50%")
            await deck.refresh()

        await deck.set_screen("main")
        print("\nDeck ready!")
        print("  Encoder 0: turn to adjust brightness, press to reset to 50%")
        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
