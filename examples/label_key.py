#!/usr/bin/env python3
"""Example: word-wrapped text label on a physical key.

Demonstrates the ``wrap`` text binding feature which automatically breaks
long text into multiple lines using ``<tspan>`` elements.  Font metrics
are auto-detected from the SVG ``<text>`` element and Pillow is used for
pixel-accurate text measurement.

The LabelKey.dui package defines:
- A ``text`` binding named ``label`` with ``wrap: true``, ``max_width: 90``,
  and ``max_height: 54``.  Long labels word-wrap across multiple lines and
  overflow is truncated with an ellipsis.
- A ``color`` binding for an indicator strip below the label.
- ``key_press_release`` and ``key_hold`` events.

Run with::

    python examples/label_key.py
"""

import asyncio
import logging
from pathlib import Path

from deckui import DeckManager, DsuiKey, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

EXAMPLES_DIR = Path(__file__).parent

# Sample labels — some short, some long enough to wrap
LABELS = [
    "Play",
    "Arthur Olsen's Favorites",
    "Morning Commute Playlist",
    "Lo-Fi Beats",
    "Saturday Night Dance Party Mix Vol. 2",
]


async def main():
    spec = load_package(EXAMPLES_DIR / "LabelKey.dui")

    print(f"Loaded: {spec.name} (v{spec.version})")
    print(f"  Bindings: {sorted(spec.bindings)}")
    print(f"  Events:   {[e.name for e in spec.events]}")

    manager = DeckManager(brightness=80)

    @manager.on_connect()
    async def handle(deck):
        screen = deck.screen("main")

        key = DsuiKey(spec)
        screen.set_key(0, key)

        label_index = 0
        key.set("label", LABELS[label_index])

        @key.on_event("activate")
        async def on_activate():
            nonlocal label_index
            label_index = (label_index + 1) % len(LABELS)
            label = LABELS[label_index]
            key.set("label", label)
            key.set("indicator_color", "#4CAF50")
            print(f"Label: {label!r}")
            await deck.refresh()

        @key.on_event("long_hold")
        async def on_hold():
            key.set("label", "Reset")
            key.set("indicator_color", "#333333")
            print("Reset to default")
            await deck.refresh()

        await deck.set_screen("main")
        print("\nDeck ready! Press key 0 to cycle labels, long-hold to reset.")

    async with manager:
        await manager.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
