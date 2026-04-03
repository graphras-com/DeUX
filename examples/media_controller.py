#!/usr/bin/env python3
"""Media controller — music player with volume, EQ, and balance sliders.

A practical example that turns the Stream Deck+ into a media controller:
transport buttons on row 1, playlist navigation on row 2, and dial-
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
        dial 0     dial 1     dial 2     dial 3

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

        page.button(0).set_icon("mdi:skip-previous").set_label("Prev")
        page.button(1).set_icon("mdi:play").set_label("Play")
        page.button(2).set_icon("mdi:skip-next").set_label("Next")
        page.button(3).set_icon("mdi:volume-high").set_label("Mute")

        # -- Playlist controls (row 2) -------------------------------------

        page.button(4).set_icon("mdi:shuffle-variant").set_label("Shuffle")
        page.button(5).set_icon("mdi:repeat").set_label("Repeat")
        page.button(6).set_icon("mdi:heart-outline").set_label("Like")
        page.button(7).set_icon("mdi:playlist-music").set_label("Queue")

        # -- Sliders on touchscreen -----------------------------------------

        vol = VolumeSlider(value=65)
        bass = EqualizerSlider("Bass", value=50, min_value=-12, max_value=12, step=1)
        treble = EqualizerSlider(
            "Treble", value=50, min_value=-12, max_value=12, step=1
        )
        bal = BalanceSlider(value=50)

        sw0 = StackCard(0)
        sw0.add_slider(vol)
        page.set_card(0, sw0)

        sw1 = StackCard(1)
        sw1.add_slider(bass)
        page.set_card(1, sw1)

        sw2 = StackCard(2)
        sw2.add_slider(treble)
        page.set_card(2, sw2)

        sw3 = StackCard(3)
        sw3.add_slider(bal)
        page.set_card(3, sw3)

        # -- Playback state -------------------------------------------------

        playing = False
        muted = False
        saved_volume = vol.value

        @page.button(0).on_press
        async def on_prev() -> None:
            print("⏮ Previous track")

        @page.button(1).on_press
        async def on_play_pause() -> None:
            nonlocal playing
            playing = not playing
            if playing:
                page.button(1).set_icon("mdi:pause").set_label("Pause")
                print("▶ Playing")
            else:
                page.button(1).set_icon("mdi:play").set_label("Play")
                print("⏸ Paused")
            await deck.refresh()

        @page.button(2).on_press
        async def on_next() -> None:
            print("⏭ Next track")

        @page.button(3).on_press
        async def on_mute() -> None:
            nonlocal muted, saved_volume
            muted = not muted
            if muted:
                saved_volume = vol.value
                vol.set_value(0)
                page.button(3).set_icon("mdi:volume-off").set_label("Unmute")
                print("🔇 Muted")
            else:
                vol.set_value(saved_volume)
                page.button(3).set_icon("mdi:volume-high").set_label("Mute")
                print(f"🔊 Volume restored to {vol.format_value()}")
            await deck.refresh()

        liked = False

        @page.button(6).on_press
        async def on_like() -> None:
            nonlocal liked
            liked = not liked
            icon = "mdi:heart" if liked else "mdi:heart-outline"
            page.button(6).set_icon(icon)
            print("❤️ Liked!" if liked else "💔 Unliked")
            await deck.refresh()

        @page.button(7).on_press
        async def on_queue() -> None:
            print("📋 Queue (not implemented in this example)")

        # Dial 0 press: toggle mute (same as button 3)
        @page.dial(0).on_press
        async def on_dial_mute() -> None:
            await on_mute()

        # -- Activate and run -----------------------------------------------

        await deck.set_screen("media")
        print("\nMedia controller ready!")
        print("  Dial 0: Volume | Dial 1: Bass | Dial 2: Treble | Dial 3: Balance")
        print("  Press dial 0 to toggle mute.")
        print("  Button 1 = Play/Pause, Button 3 = Mute.")
        print("  Ctrl+C to exit.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
