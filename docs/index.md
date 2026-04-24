# DeckUI

A high-level, asyncio-native Python library for Elgato Stream Deck devices.

## Quick Start

```python
import asyncio
from deckui import DeckManager

async def main():
    manager = DeckManager()

    @manager.on_connect()
    async def handle(deck):
        screen = deck.screen("main")

        @screen.key(0).on_press
        async def on_home():
            print("Home pressed!")

        await deck.set_screen("main")

    async with manager:
        await manager.wait_closed()

asyncio.run(main())
```

## Installation

```bash
pip install deckui
```

## Modules

- **[Runtime](reference/runtime.md)** — Device discovery, capabilities, transport, and event handling
- **[UI](reference/ui.md)** — Screen, KeySlot, EncoderSlot, TouchStrip controls
- **[DSUI](reference/dsui.md)** — `.dui` package format (SVG layout + YAML manifest)
- **[Render](reference/render.md)** — Image rendering and metrics
- **[Tools](reference/tools.md)** — CLI utilities
