#!/usr/bin/env python3
"""Example: multi-device management with auto-reconnect.

Demonstrates the new multi-device features:

- ``list_devices()`` — enumerate connected Stream Decks
- ``Deck.wait_for_device()`` — wait for a specific device to appear
- ``DeckManager`` — orchestrate multiple devices with hot-plug detection
- ``auto_reconnect`` — survive USB disconnects gracefully
- ``deck_type`` filter — target specific hardware models

Run with::

    python examples/multi_device.py
"""

import asyncio
import logging

from deckboard import Deck, DeckManager, DeviceInfo, list_devices

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def demo_list_devices() -> None:
    """Show all connected Stream Deck devices."""
    print("=== list_devices() ===")
    devices = await list_devices()
    if not devices:
        print("  No devices found.\n")
        return
    for info in devices:
        print(f"  {info.deck_type} (serial={info.serial}, keys={info.key_count})")
    print()


async def demo_single_deck_reconnect() -> None:
    """Single deck with auto-reconnect enabled.

    If you unplug the device it will attempt to reconnect automatically.
    Plug it back in and the UI will be restored.
    """
    print("=== Single Deck with auto_reconnect ===")
    print("  Waiting for a Stream Deck to connect...")

    deck = await Deck.wait_for_device(
        auto_reconnect=True,
        poll_interval=1.0,
        brightness=80,
    )

    @deck.on_disconnect
    async def on_disc():
        print("  Device disconnected! Waiting for reconnect...")

    @deck.on_reconnect
    async def on_recon():
        print("  Device reconnected! UI restored.")

    screen = deck.screen("main")

    @screen.key(0).on_press
    async def on_home():
        print("  Key 0 pressed!")

    await deck.set_screen("main")
    print(f"  Connected: {deck.info.deck_type} (serial={deck.info.serial})")
    print("  Press Ctrl+C to exit.\n")

    try:
        await deck.wait_closed()
    except KeyboardInterrupt:
        await deck.stop()


async def demo_deck_manager() -> None:
    """Multi-device orchestration with DeckManager.

    The manager scans for devices every 2 seconds. When a matching
    device appears, the on_connect handler is called. When it
    disappears, on_disconnect fires.
    """
    print("=== DeckManager (multi-device) ===")

    manager = DeckManager(poll_interval=2.0, brightness=80)

    @manager.on_connect(deck_type="Stream Deck +")
    async def handle_plus(deck: Deck) -> None:
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

    @manager.on_connect()  # catch-all for any device type
    async def handle_any(deck: Deck) -> None:
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

    async with manager:
        print("  Scanning for devices... Press Ctrl+C to exit.\n")
        try:
            await manager.wait_closed()
        except KeyboardInterrupt:
            pass


async def main() -> None:
    # 1. Show connected devices
    await demo_list_devices()

    # 2. Pick which demo to run
    print("Choose a demo:")
    print("  1) Single deck with auto-reconnect")
    print("  2) DeckManager (multi-device)")
    print()

    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        await demo_single_deck_reconnect()
    elif choice == "2":
        await demo_deck_manager()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    asyncio.run(main())
