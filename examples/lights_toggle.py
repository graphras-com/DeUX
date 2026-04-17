#!/usr/bin/env python3
"""Example: toggle binding for on/off state on a physical key.

Demonstrates the ``toggle`` binding type which switches between two SVG
elements based on a boolean value — ideal for on/off indicators like
lights, mute/unmute, play/pause, etc.

The LightsKey.dsui package defines:
- A ``toggle`` binding named ``lights`` that swaps between a lit bulb icon
  (``lights_on``) and a crossed-out bulb icon (``lights_off``).
- A ``color`` binding for an indicator strip below the label.
- A ``key_press_release`` event named ``toggle``.

Run with::

    python examples/lights_toggle.py
"""

import asyncio
import logging
from pathlib import Path

from deckboard import Deck, DsuiKey, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

EXAMPLES_DIR = Path(__file__).parent


async def main():
    spec = load_package(EXAMPLES_DIR / "LightsKey.dsui")

    print(f"Loaded: {spec.name} (v{spec.version})")
    print(f"  Bindings: {sorted(spec.bindings)}")
    print(f"  Events:   {[e.name for e in spec.events]}")

    async with Deck(brightness=80) as deck:
        screen = deck.screen("main")

        key = DsuiKey(spec)
        screen.set_key(0, key)

        lights_on = False

        @key.on_event("toggle")
        async def on_toggle():
            nonlocal lights_on
            lights_on = not lights_on

            # Single set() call flips both icons at once
            key.set("lights", lights_on)

            # Update the indicator colour to match
            key.set("indicator_color", "#FFD700" if lights_on else "#333333")

            print(f"Lights {'ON' if lights_on else 'OFF'}")
            await deck.refresh()

        await deck.set_screen("main")
        print("\nDeck ready! Press key 0 to toggle lights on/off.")
        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
