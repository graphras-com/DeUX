#!/usr/bin/env python3
"""Media controller — music player with volume, EQ, and balance sliders.

A practical example that turns the Stream Deck+ into a media controller:
transport buttons on row 1, playlist navigation on row 2, and encoder-
controlled volume/EQ/balance on the touchscreen.

Layout::

    ┌──────────┬──────────┬──────────┬──────────┐
    │   Prev   │  Play /  │   Next   │   Mute   │   ← row 1
    │          │  Pause   │          │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │ Shuffle  │  Repeat  │  Like    │  Queue   │   ← row 2
    ├──────────┼──────────┼──────────┼──────────┤
    │ Volume   │  Bass    │  Treble  │ Balance  │   ← touchscreen
    └──────────┴──────────┴──────────┴──────────┘
        enc 0      enc 1      enc 2      enc 3

Run with::

    python examples/media_controller.py
"""

import asyncio
import logging

from deckboard import BalanceSlider, Deck, EqualizerSlider, StackCard, VolumeSlider

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    async with Deck(brightness=70) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.screen("media")

        # -- Transport controls (row 1) ------------------------------------

        page.key(0).set_icon("mdi:skip-previous").set_label("Prev")
        page.key(1).set_icon("mdi:play").set_label("Play")
        page.key(2).set_icon("mdi:skip-next").set_label("Next")
        page.key(3).set_icon("mdi:volume-high").set_label("Mute")

        # -- Playlist controls (row 2) -------------------------------------

        page.key(4).set_icon("mdi:shuffle-variant").set_label("Shuffle")
        page.key(5).set_icon("mdi:repeat").set_label("Repeat")
        page.key(6).set_icon("mdi:heart-outline").set_label("Like")
        page.key(7).set_icon("mdi:playlist-music").set_label("Queue")

        # -- Sliders on touchscreen -----------------------------------------

        vol = VolumeSlider(value=65)
        bass = EqualizerSlider("Bass", value=50, min_value=-12, max_value=12, step=1)
        treble = EqualizerSlider(
            "Treble", value=50, min_value=-12, max_value=12, step=1
        )
        bal = BalanceSlider(value=50)

        sw0 = StackCard(0)
        sw0.add_control(vol)
        page.set_card(0, sw0)

        sw1 = StackCard(1)
        sw1.add_control(bass)
        page.set_card(1, sw1)

        sw2 = StackCard(2)
        sw2.add_control(treble)
        page.set_card(2, sw2)

        sw3 = StackCard(3)
        sw3.add_control(bal)
        page.set_card(3, sw3)

        # -- Playback state -------------------------------------------------

        playing = False
        muted = False
        saved_volume = vol.value

        @page.key(0).on_press
        async def on_prev() -> None:
            print("⏮ Previous track")

        @page.key(1).on_press
        async def on_play_pause() -> None:
            nonlocal playing
            playing = not playing
            if playing:
                page.key(1).set_icon("mdi:pause").set_label("Pause")
                print("▶ Playing")
            else:
                page.key(1).set_icon("mdi:play").set_label("Play")
                print("⏸ Paused")
            await deck.refresh()

        @page.key(2).on_press
        async def on_next() -> None:
            print("⏭ Next track")

        @page.key(3).on_press
        async def on_mute() -> None:
            nonlocal muted, saved_volume
            muted = not muted
            if muted:
                saved_volume = vol.value
                vol.set_value(0)
                page.key(3).set_icon("mdi:volume-off").set_label("Unmute")
                print("🔇 Muted")
            else:
                vol.set_value(saved_volume)
                page.key(3).set_icon("mdi:volume-high").set_label("Mute")
                print(f"🔊 Volume restored to {vol.format_value()}")
            await deck.refresh()

        liked = False

        @page.key(6).on_press
        async def on_like() -> None:
            nonlocal liked
            liked = not liked
            icon = "mdi:heart" if liked else "mdi:heart-outline"
            page.key(6).set_icon(icon)
            print("❤️ Liked!" if liked else "💔 Unliked")
            await deck.refresh()

        @page.key(7).on_press
        async def on_queue() -> None:
            print("📋 Queue (not implemented in this example)")

        # Encoder 0 press: toggle mute (same as button 3)
        @page.encoder(0).on_press
        async def on_encoder_mute() -> None:
            await on_mute()

        # -- Activate and run -----------------------------------------------

        await deck.set_screen("media")
        print("\nMedia controller ready!")
        print(
            "  Encoder 0: Volume | Encoder 1: Bass | Encoder 2: Treble | Encoder 3: Balance"
        )
        print("  Press encoder 0 to toggle mute.")
        print("  Button 1 = Play/Pause, Button 3 = Mute.")
        print("  Ctrl+C to exit.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
