#!/usr/bin/env python3
"""Example: multi-device management with device discovery.

Demonstrates the core deckui features:

- ``list_devices()`` — enumerate connected Stream Decks
- ``DeckManager`` — orchestrate multiple devices with hot-plug detection
- ``auto_reconnect`` — survive USB disconnects (on by default)
- ``deck_type`` / ``serial`` filters — target specific hardware

Run with::

    python examples/multi_device.py
"""

import asyncio
import logging

from deckui import DeckManager, DeviceInfo, list_devices

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    # Show connected devices
    print("=== Connected devices ===")
    devices = await list_devices()
    if not devices:
        print("  No devices found (plug one in and the manager will detect it).\n")
    else:
        for info in devices:
            print(f"  {info.deck_type} (serial={info.serial}, keys={info.key_count})")
        print()

    # Set up manager — auto_reconnect is True by default
    manager = DeckManager(poll_interval=2.0, brightness=80)

    @manager.on_connect(deck_type="Stream Deck +")
    async def handle_plus(deck) -> None:
        info = deck.info
        print(f"  [+] Stream Deck+ connected: {info.serial}")

        screen = deck.screen("main")

        @screen.key(0).on_press
        async def on_k0():
            print(f"    [{info.serial}] Key 0 pressed!")

        if deck.capabilities.has_encoders:

            @screen.encoder(0).on_turn
            async def on_turn(direction: int) -> None:
                print(f"    [{info.serial}] Encoder 0 turned: {direction}")

        await deck.set_screen("main")

    @manager.on_connect()  # catch-all for any other device type
    async def handle_any(deck) -> None:
        info = deck.info
        if info.deck_type == "Stream Deck +":
            return  # Already handled above
        print(f"  [+] {info.deck_type} connected: {info.serial}")

        screen = deck.screen("main")

        @screen.key(0).on_press
        async def on_k0():
            print(f"    [{info.serial}] Key 0 pressed!")

        await deck.set_screen("main")

    @manager.on_disconnect
    async def handle_lost(info: DeviceInfo) -> None:
        print(f"  [-] Lost: {info.serial} ({info.deck_type})")
        print("       (will reconnect automatically when plugged back in)")

    async with manager:
        print("Scanning for devices... Press Ctrl+C to exit.\n")
        try:
            await manager.wait_closed()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    asyncio.run(main())
