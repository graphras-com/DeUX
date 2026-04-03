#!/usr/bin/env python3
"""Media widget — ready-to-use media panel with title display and volume control.

Shows how ``MediaWidget`` bundles a title text and volume slider into a
single widget zone with built-in mute toggling on dial press.

Layout::

    ┌──────────┬──────────┬──────────┬──────────┐
    │   Prev   │  Play /  │   Next   │   Mute   │   ← buttons (row 1)
    │          │  Pause   │          │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │ Shuffle  │  Repeat  │  Like    │  Print   │   ← buttons (row 2)
    ├──────────┼──────────┼──────────┼──────────┤
    │          │          │          │  Title   │   ← touchscreen
    │          │          │          │  Volume  │
    └──────────┴──────────┴──────────┴──────────┘
        dial 0     dial 1     dial 2     dial 3

    Dial 3: turn to adjust volume, press to toggle mute.

Run with::

    python examples/media_widget.py
"""

import asyncio
import logging

from deckboard import Deck, MediaWidget

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Simulated playlist
PLAYLIST = [
    "Bohemian Rhapsody — Queen",
    "Hotel California — Eagles",
    "Stairway to Heaven — Led Zeppelin",
    "Comfortably Numb — Pink Floyd",
    "Imagine — John Lennon",
]


async def main() -> None:
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.screen("media_widget")

        # -- MediaWidget on zone 3 (dial 3) -------------------------------

        media = MediaWidget(3, title=PLAYLIST[0], volume=65)
        page.set_card(3, media)

        # -- Transport buttons (row 1) ------------------------------------

        page.button(0).set_icon("mdi:skip-previous").set_label("Prev")
        page.button(1).set_icon("mdi:play").set_label("Play")
        page.button(2).set_icon("mdi:skip-next").set_label("Next")
        page.button(3).set_icon("mdi:volume-high").set_label("Mute")

        # -- Utility buttons (row 2) --------------------------------------

        page.button(4).set_icon("mdi:shuffle-variant").set_label("Shuffle")
        page.button(5).set_icon("mdi:repeat").set_label("Repeat")
        page.button(6).set_icon("mdi:heart-outline").set_label("Like")
        page.button(7).set_icon("mdi:printer").set_label("Print")

        # -- Playback state ------------------------------------------------

        playing = False
        track_index = 0

        async def update_mute_button() -> None:
            if media.muted:
                page.button(3).set_icon("mdi:volume-off").set_label("Unmute")
            else:
                page.button(3).set_icon("mdi:volume-high").set_label("Mute")
            await deck.refresh()

        @page.button(0).on_press
        async def on_prev() -> None:
            nonlocal track_index
            track_index = (track_index - 1) % len(PLAYLIST)
            media.title_text.set_text(PLAYLIST[track_index])
            print(f"Now playing: {PLAYLIST[track_index]}")
            await deck.refresh()

        @page.button(1).on_press
        async def on_play_pause() -> None:
            nonlocal playing
            playing = not playing
            if playing:
                page.button(1).set_icon("mdi:pause").set_label("Pause")
                print(f"Playing: {PLAYLIST[track_index]}")
            else:
                page.button(1).set_icon("mdi:play").set_label("Play")
                print("Paused")
            await deck.refresh()

        @page.button(2).on_press
        async def on_next() -> None:
            nonlocal track_index
            track_index = (track_index + 1) % len(PLAYLIST)
            media.title_text.set_text(PLAYLIST[track_index])
            print(f"Now playing: {PLAYLIST[track_index]}")
            await deck.refresh()

        @page.button(3).on_press
        async def on_mute_button() -> None:
            media.toggle_mute()
            if media.muted:
                print(f"Muted (saved volume: {media.volume.value})")
            else:
                print(f"Unmuted — Volume: {media.volume.format_value()}")
            await update_mute_button()

        liked = False

        @page.button(6).on_press
        async def on_like() -> None:
            nonlocal liked
            liked = not liked
            icon = "mdi:heart" if liked else "mdi:heart-outline"
            page.button(6).set_icon(icon)
            print("Liked!" if liked else "Unliked")
            await deck.refresh()

        @page.button(7).on_press
        async def on_print() -> None:
            print(
                f"Track: {media.title_text.text}, "
                f"Volume: {media.volume.format_value()}, "
                f"Muted: {media.muted}"
            )

        # -- Volume on_change callback -------------------------------------

        @media.volume.on_change
        async def on_volume_change(value: float) -> None:
            print(f"Volume: {media.volume.format_value()}")

        # -- Dial 3 press also updates the mute button --------------------

        @media.on_dial_press
        async def on_dial_mute() -> None:
            if media.muted:
                print("Muted via dial press")
            else:
                print(f"Unmuted via dial press — Volume: {media.volume.format_value()}")
            await update_mute_button()

        # -- Activate and run ----------------------------------------------

        await deck.set_screen("media_widget")
        print("\nMedia widget ready!")
        print(f"  Now playing: {PLAYLIST[0]}")
        print("  Turn dial 3 to adjust volume.")
        print("  Press dial 3 to toggle mute.")
        print("  Row 1: Prev, Play/Pause, Next, Mute.")
        print("  Row 2: Shuffle, Repeat, Like, Print status.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
