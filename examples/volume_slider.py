#!/usr/bin/env python3
"""Example: volume slider using a .dui range binding.

Demonstrates the ``range`` binding type which scales an SVG element's
width (or height) proportionally to a 0.0-1.0 value.  The encoder
controls the volume level and the bar updates in real time.

Run with::

    python examples/volume_slider.py
"""

import asyncio
import logging
from pathlib import Path

from deckui import DeckManager, DsuiCard, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

EXAMPLES_DIR = Path(__file__).parent


async def main():
    spec = load_package(EXAMPLES_DIR / "VolumeSlider.dui")

    print(f"Loaded: {spec.name} (v{spec.version})")
    print(f"  Bindings: {sorted(spec.bindings)}")
    print(f"  Events:   {[e.name for e in spec.events]}")

    manager = DeckManager(brightness=80)

    @manager.on_connect()
    async def handle(deck):
        screen = deck.screen("main")

        card = DsuiCard(spec)
        muted = False

        card.set_range("volume", 50, min_val=0, max_val=100)
        card.set("value_text", "50%")
        screen.set_card(0, card)

        @card.on("volume_up")
        async def on_up():
            vol = card.adjust_range("volume", 5, min_val=0, max_val=100)
            card.set("value_text", f"{int(vol)}%")
            if muted:
                card.set("bar_color", "#dedede")
            print(f"Volume: {int(vol)}%")
            await deck.refresh()

        @card.on("volume_down")
        async def on_down():
            vol = card.adjust_range("volume", -5, min_val=0, max_val=100)
            card.set("value_text", f"{int(vol)}%")
            print(f"Volume: {int(vol)}%")
            await deck.refresh()

        @card.on("mute_toggle")
        async def on_mute():
            nonlocal muted
            muted = not muted
            if muted:
                card.set("bar_color", "#ff4444")
                card.set("value_text", "MUTED")
            else:
                card.set("bar_color", "#dedede")
                vol = card.get_range("volume", min_val=0, max_val=100)
                card.set("value_text", f"{int(vol)}%")
            print(f"{'Muted' if muted else 'Unmuted'}")
            await deck.refresh()

        await deck.set_screen("main")
        print("\nDeck ready!")
        print("  Encoder 0: turn to adjust volume, press to mute/unmute")

    async with manager:
        await manager.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
