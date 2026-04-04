#!/usr/bin/env python3
"""Media widget — ready-to-use media panel with title display and volume control.

Shows how ``MediaCard`` bundles a title text and volume slider into a
single widget zone with built-in mute toggling on encoder press.

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
        enc 0      enc 1      enc 2      enc 3

    Encoder 3: turn to adjust volume, press to toggle mute.

Run with::

    python examples/media_widget.py
"""

import asyncio
import logging

from deckboard import Deck, MediaCard

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

        # -- MediaCard on zone 3 (dial 3) -------------------------------

        media = MediaCard(3, title=PLAYLIST[0], volume=65)
        page.set_card(3, media)

        # -- Transport buttons (row 1) ------------------------------------

        page.key(0).set_icon("mdi:skip-previous").set_label("Prev")
        page.key(1).set_icon("mdi:play").set_label("Play")
        page.key(2).set_icon("mdi:skip-next").set_label("Next")
        page.key(3).set_icon("mdi:volume-high").set_label("Mute")

        # -- Utility buttons (row 2) --------------------------------------

        page.key(4).set_icon("mdi:shuffle-variant").set_label("Shuffle")
        page.key(5).set_icon("mdi:repeat").set_label("Repeat")
        page.key(6).set_icon("mdi:heart-outline").set_label("Like")
        page.key(7).set_icon("mdi:printer").set_label("Print")

        # -- Playback state ------------------------------------------------

        playing = False
        track_index = 0

        async def update_mute_button() -> None:
            if media.muted:
                page.key(3).set_icon("mdi:volume-off").set_label("Unmute")
            else:
                page.key(3).set_icon("mdi:volume-high").set_label("Mute")
            await deck.refresh()

        @page.key(0).on_press
        async def on_prev() -> None:
            nonlocal track_index
            track_index = (track_index - 1) % len(PLAYLIST)
            media.title_text.set_text(PLAYLIST[track_index])
            print(f"Now playing: {PLAYLIST[track_index]}")
            await deck.refresh()

        @page.key(1).on_press
        async def on_play_pause() -> None:
            nonlocal playing
            playing = not playing
            if playing:
                page.key(1).set_icon("mdi:pause").set_label("Pause")
                print(f"Playing: {PLAYLIST[track_index]}")
            else:
                page.key(1).set_icon("mdi:play").set_label("Play")
                print("Paused")
            await deck.refresh()

        @page.key(2).on_press
        async def on_next() -> None:
            nonlocal track_index
            track_index = (track_index + 1) % len(PLAYLIST)
            media.title_text.set_text(PLAYLIST[track_index])
            print(f"Now playing: {PLAYLIST[track_index]}")
            await deck.refresh()

        @page.key(3).on_press
        async def on_mute_button() -> None:
            media.toggle_mute()
            if media.muted:
                print(f"Muted (saved volume: {media.volume.value})")
            else:
                print(f"Unmuted — Volume: {media.volume.format_value()}")
            await update_mute_button()

        liked = False

        @page.key(6).on_press
        async def on_like() -> None:
            nonlocal liked
            liked = not liked
            icon = "mdi:heart" if liked else "mdi:heart-outline"
            page.key(6).set_icon(icon)
            print("Liked!" if liked else "Unliked")
            await deck.refresh()

        @page.key(7).on_press
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

        # -- Encoder 3 press also updates the mute button --------------------

        @media.on_encoder_press
        async def on_encoder_mute() -> None:
            if media.muted:
                print("Muted via encoder press")
            else:
                print(
                    f"Unmuted via encoder press — Volume: {media.volume.format_value()}"
                )
            await update_mute_button()

        # -- Activate and run ----------------------------------------------

        await deck.set_screen("media_widget")
        print("\nMedia widget ready!")
        print(f"  Now playing: {PLAYLIST[0]}")
        print("  Turn encoder 3 to adjust volume.")
        print("  Press encoder 3 to toggle mute.")
        print("  Row 1: Prev, Play/Pause, Next, Mute.")
        print("  Row 2: Shuffle, Repeat, Like, Print status.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
