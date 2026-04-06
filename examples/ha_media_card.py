#!/usr/bin/env python3
"""Home Assistant media card — album art, metadata, and volume bar.

Shows how ``HaMediaCard`` renders a media player panel with album art,
artist/title text, playback state, and a volume bar.

Encoder interaction is handled automatically by the card:

* **Turn** — adjust volume.
* **Short press** (press and release quickly) — toggle mute/unmute.
* **Long press** (hold for 2 seconds) — toggle play/pause.  The state
  changes while the encoder is still held — no need to release first.

Layout::

    ┌──────────┬──────────┬──────────┬──────────┐
    │   Prev   │  Play /  │   Next   │   Mute   │   ← keys (row 1)
    │          │  Pause   │          │          │
    ├──────────┼──────────┼──────────┼──────────┤
    │ Shuffle  │  Repeat  │  Like    │  Print   │   ← keys (row 2)
    ├──────────┼──────────┼──────────┼──────────┤
    │          │          │          │HA Media  │   ← touchscreen
    │          │          │          │  Card    │
    └──────────┴──────────┴──────────┴──────────┘
        enc 0      enc 1      enc 2      enc 3

Run with::

    python examples/ha_media_card.py
"""

import asyncio
import logging

from deckboard import Deck, HaMediaCard

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PLAYLIST = [
    ("Tórshavnar Big Band", "Sólsetur"),
    ("Queen", "Bohemian Rhapsody"),
    ("Pink Floyd", "Comfortably Numb"),
    ("Eagles", "Hotel California"),
    ("Led Zeppelin", "Stairway to Heaven"),
]


async def main() -> None:
    async with Deck(brightness=80) as deck:
        info = deck.info
        print(f"Connected: {info.deck_type} (serial: {info.serial})")

        page = deck.screen("ha_media")

        # -- HaMediaCard on zone 3 (encoder 3) ----------------------------

        artist, title = PLAYLIST[0]
        card = HaMediaCard(
            3,
            artist=artist,
            title=title,
            state="Paused",
            volume=24,
        )
        page.set_card(3, card)

        # -- Transport keys (row 1) ----------------------------------------

        page.key(0).set_icon("mdi:skip-previous").set_label("Prev")
        page.key(1).set_icon("mdi:play").set_label("Play")
        page.key(2).set_icon("mdi:skip-next").set_label("Next")
        page.key(3).set_icon("mdi:volume-high").set_label("Mute")

        # -- Utility keys (row 2) ------------------------------------------

        page.key(4).set_icon("mdi:shuffle-variant").set_label("Shuffle")
        page.key(5).set_icon("mdi:repeat").set_label("Repeat")
        page.key(6).set_icon("mdi:heart-outline").set_label("Like")
        page.key(7).set_icon("mdi:printer").set_label("Print")

        # -- State ---------------------------------------------------------

        track_index = 0

        async def sync_buttons() -> None:
            """Keep key icons in sync with the card state."""
            if card.muted:
                page.key(3).set_icon("mdi:volume-off").set_label("Unmute")
            else:
                page.key(3).set_icon("mdi:volume-high").set_label("Mute")
            if card.playing:
                page.key(1).set_icon("mdi:pause").set_label("Pause")
            else:
                page.key(1).set_icon("mdi:play").set_label("Play")

        @page.key(0).on_press
        async def on_prev() -> None:
            nonlocal track_index
            track_index = (track_index - 1) % len(PLAYLIST)
            a, t = PLAYLIST[track_index]
            card.set_artist(a).set_title(t)
            print(f"Now playing: {a} — {t}")
            await deck.refresh()

        @page.key(1).on_press
        async def on_play_pause() -> None:
            card.toggle_play_pause()
            await sync_buttons()
            print(f"State: {card.state}")
            await deck.refresh()

        @page.key(2).on_press
        async def on_next() -> None:
            nonlocal track_index
            track_index = (track_index + 1) % len(PLAYLIST)
            a, t = PLAYLIST[track_index]
            card.set_artist(a).set_title(t)
            print(f"Now playing: {a} — {t}")
            await deck.refresh()

        @page.key(3).on_press
        async def on_mute_button() -> None:
            card.toggle_mute()
            await sync_buttons()
            await deck.refresh()

        @page.key(7).on_press
        async def on_print() -> None:
            print(
                f"Artist: {card.artist}, Title: {card.title}, "
                f"State: {card.state}, Volume: {card.volume:.0f}%, "
                f"Muted: {card.muted}"
            )

        # -- Encoder callbacks (for logging / syncing buttons) -------------

        @card.on_volume_change
        async def on_vol(volume: float) -> None:
            print(f"Volume: {volume:.0f}%")

        @card.on_encoder_release
        async def on_enc_release() -> None:
            await sync_buttons()
            await deck.refresh()

        # -- Activate and run ----------------------------------------------

        await deck.set_screen("ha_media")
        print("\nHA Media Card ready!")
        print(f"  Now playing: {PLAYLIST[0][0]} — {PLAYLIST[0][1]}")
        print("  Turn encoder 3 to adjust volume.")
        print("  Short press encoder 3 to toggle mute.")
        print("  Hold encoder 3 for 2s to toggle play/pause.")
        print("  Row 1: Prev, Play/Pause, Next, Mute.")
        print("  Row 2: Shuffle, Repeat, Like, Print status.\n")

        await deck.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
