#!/usr/bin/env python3
"""Example: declarative UI packages (.dsui) for Stream Deck+.

Demonstrates how to use .dsui packages to define touchscreen cards and
physical keys with SVG layouts and YAML manifests — no rendering code needed.

The AudioCard.dsui package defines a media player card with text bindings
for artist/title/album, an image binding for album art, and encoder events
for play/pause and track navigation.

The PowerKey.dsui package defines a power button key with colour bindings
and press/hold events.

Run with::

    python examples/dsui_packages.py
"""

import asyncio
import logging
from pathlib import Path

from deckboard import DeckManager, DsuiCard, DsuiKey, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

EXAMPLES_DIR = Path(__file__).parent


async def main():
    # -- Load .dsui packages -----------------------------------------------

    audio_spec = load_package(EXAMPLES_DIR / "AudioCard.dsui")
    power_spec = load_package(EXAMPLES_DIR / "PowerKey.dsui")

    print(f"Loaded: {audio_spec.name} (v{audio_spec.version})")
    print(f"  Bindings: {sorted(audio_spec.bindings)}")
    print(f"  Events:   {[e.name for e in audio_spec.events]}")
    print(f"Loaded: {power_spec.name} (v{power_spec.version})")
    print(f"  Bindings: {sorted(power_spec.bindings)}")
    print(f"  Events:   {[e.name for e in power_spec.events]}")

    # -- Set up the manager ------------------------------------------------

    manager = DeckManager(brightness=80)

    @manager.on_connect()
    async def handle(deck):
        screen = deck.screen("main")

        # Install the audio card on touch-strip zone 0
        audio = DsuiCard(audio_spec)
        audio.set("artist", "Ash Walker")
        audio.set("title", "Afghanistan")
        audio.set("album", "Echo Chamber (Deluxe)")
        audio.set("state", "Playing")
        audio.set("progress", 0.35)  # 35% through the track
        screen.set_card(0, audio)

        # Install the power key on key slot 7
        power = DsuiKey(power_spec)
        power.set("label", "Shutdown")
        power.set("ring_color", "#ff4444")
        power.set("line_color", "#ff4444")
        power.set("indicator_color", "#ff4444")
        screen.set_key(7, power)

        # -- Register event handlers ---------------------------------------

        playing = True
        track_index = 0
        tracks = [
            ("Ash Walker", "Afghanistan", "Echo Chamber (Deluxe)"),
            ("Bonobo", "Kerala", "Migration"),
            ("Khruangbin", "Maria También", "Con Todo El Mundo"),
        ]

        @audio.on("toggle_play_pause")
        async def on_toggle():
            nonlocal playing
            playing = not playing
            audio.set("state", "Playing" if playing else "Paused")
            print(f"{'▶ Playing' if playing else '⏸ Paused'}")
            await deck.refresh()

        @audio.on("next")
        async def on_next():
            nonlocal track_index
            track_index = (track_index + 1) % len(tracks)
            artist, title, album = tracks[track_index]
            audio.set_many(artist=artist, title=title, album=album)
            print(f"⏭ {artist} — {title}")
            await deck.refresh()

        @audio.on("previous")
        async def on_prev():
            nonlocal track_index
            track_index = (track_index - 1) % len(tracks)
            artist, title, album = tracks[track_index]
            audio.set_many(artist=artist, title=title, album=album)
            print(f"⏮ {artist} — {title}")
            await deck.refresh()

        @power.on_event("activate")
        async def on_power():
            print("Power SHORT press — shutting down")
            power.set("indicator_color", "#44ff44")  # flash green
            await deck.refresh()
            await asyncio.sleep(0.5)
            await manager.stop()

        @power.on_event("long_hold")
        async def on_power_hold():
            print("Power LONG HOLD — force restart")
            power.set("ring_color", "#ff8800")
            power.set("line_color", "#ff8800")
            power.set("indicator_color", "#ff8800")  # orange = held
            await deck.refresh()

        # -- Activate and run ----------------------------------------------

        await deck.set_screen("main")
        print("\nDeck ready!")
        print("  Encoder 0: turn for next/prev track, press for play/pause")
        print("  Key 7 (Shutdown):")
        print("    Short press (<300ms): clean shutdown (green flash)")
        print("    Long hold  (>500ms):  force restart  (turns orange)")

    async with manager:
        await manager.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
