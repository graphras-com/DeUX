#!/usr/bin/env python3
"""Example: volume slider using a .dsui range binding.

Demonstrates the ``range`` binding type which scales an SVG element's
width (or height) proportionally to a 0.0–1.0 value.  The encoder
controls the volume level and the bar updates in real time.

Run with::

    python examples/volume_slider.py
"""

import asyncio
import logging
from pathlib import Path

from deckboard import Deck, DsuiCard, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

EXAMPLES_DIR = Path(__file__).parent


async def main():
    spec = load_package(EXAMPLES_DIR / "VolumeSlider.dsui")

    print(f"Loaded: {spec.name} (v{spec.version})")
    print(f"  Bindings: {sorted(spec.bindings)}")
    print(f"  Events:   {[e.name for e in spec.events]}")

    async with Deck(brightness=80) as deck:
        screen = deck.screen("main")

        card = DsuiCard(0, spec)
        volume = 0.5
        muted = False

        card.set("volume", volume)
        card.set("value_text", f"{int(volume * 100)}%")
        screen.set_card(0, card)

        @card.on("volume_up")
        async def on_up():
            nonlocal volume
            volume = min(1.0, volume + 0.05)
            card.set("volume", volume)
            card.set("value_text", f"{int(volume * 100)}%")
            if muted:
                card.set("bar_color", "#dedede")
            print(f"Volume: {int(volume * 100)}%")
            await deck.refresh()

        @card.on("volume_down")
        async def on_down():
            nonlocal volume
            volume = max(0.0, volume - 0.05)
            card.set("volume", volume)
            card.set("value_text", f"{int(volume * 100)}%")
            print(f"Volume: {int(volume * 100)}%")
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
                card.set("value_text", f"{int(volume * 100)}%")
            print(f"{'Muted' if muted else 'Unmuted'}")
            await deck.refresh()

        await deck.set_screen("main")
        print("\nDeck ready!")
        print("  Encoder 0: turn to adjust volume, press to mute/unmute")
        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
