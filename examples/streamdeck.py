#!/usr/bin/env python3
"""Stream Deck+ demo -- showcases DeckUI with mockup controllers.

This example demonstrates how to build a complete Stream Deck+ application
using DeckUI's declarative UI system.  It sets up four touchscreen cards
(audio player, lights, timer, dashboard) and eight physical keys (four
album-art favorites and four scene-activation buttons).

No real hardware or external services are required -- every controller uses
in-memory state and logs actions to the console.

Layout
------
Keys (8-key, 2×4 grid)::

    ┌──────┬──────┬──────┬──────┐
    │ Fav0 │ Fav1 │Scene0│Scene1│
    ├──────┼──────┼──────┼──────┤
    │ Fav2 │ Fav3 │Scene2│Scene3│
    └──────┴──────┴──────┴──────┘

Touch-strip cards (left → right)::

    [ Audio Player ] [ Lights ] [ Timer ] [ Dashboard ]

Running
-------
::

    python examples/streamdeck.py
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from pathlib import Path
from typing import Any

from deckui import DeckManager, DeviceInfo, DuiCard, DuiKey, load_package

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Media catalog -- four classic albums used as favorites
# ---------------------------------------------------------------------------

MEDIA_CATALOG: list[dict[str, str]] = [
    {
        "artist": "The Beatles",
        "album": "Abbey Road",
        "title": "Come Together",
        "cover": "assets/album_cover_1.png",
    },
    {
        "artist": "King Crimson",
        "album": "In the Court of the Crimson King",
        "title": "In the Court of the Crimson King",
        "cover": "assets/album_cover_2.png",
    },
    {
        "artist": "Procol Harum",
        "album": "Procol Harum",
        "title": "A Whiter Shade of Pale",
        "cover": "assets/album_cover_3.png",
    },
    {
        "artist": "The Velvet Underground",
        "album": "The Velvet Underground & Nico",
        "title": "Sunday Morning",
        "cover": "assets/album_cover_4.png",
    },
]

# ---------------------------------------------------------------------------
# Key definitions
# ---------------------------------------------------------------------------

SCENE_KEYS: list[dict[str, Any]] = [
    {"position": 2, "label": "Normal", "icon": "fa-regular:smile-beam"},
    {"position": 3, "label": "Tired", "icon": "fa-regular:tired"},
    {"position": 6, "label": "Cinema", "icon": "mdi:cinema"},
    {"position": 7, "label": "Bedtime", "icon": "icon-park-outline:sleep-two"},
]

FAVORITE_KEYS: list[dict[str, Any]] = [
    {"position": 0, "media": MEDIA_CATALOG[0]},
    {"position": 1, "media": MEDIA_CATALOG[1]},
    {"position": 4, "media": MEDIA_CATALOG[2]},
    {"position": 5, "media": MEDIA_CATALOG[3]},
]

# Resolve examples directory for .dui package loading
EXAMPLES_DIR = Path(__file__).resolve().parent


# ═══════════════════════════════════════════════════════════════════════════
# Mock controllers
# ═══════════════════════════════════════════════════════════════════════════


class AudioPlayer:
    """In-memory mock audio player with volume, mute, and track state.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        List of media entries, each with ``artist``, ``album``, ``title``,
        and ``cover`` keys.
    initial_volume : float, default=0.3
        Starting volume level (0.0–1.0).
    """

    def __init__(
        self,
        catalog: list[dict[str, str]],
        initial_volume: float = 0.3,
    ) -> None:
        self._catalog = list(catalog)
        self._index = 0
        self.volume_level: float = initial_volume
        self.is_muted: bool = False
        self.is_playing: bool = False

    @property
    def current_track(self) -> dict[str, str]:
        """The currently selected media entry."""
        return self._catalog[self._index]

    async def play(self, track: dict[str, str] | None = None) -> None:
        """Start playback, optionally jumping to a specific track.

        Parameters
        ----------
        track : dict[str, str] | None
            If provided, switch to this track before playing.
        """
        if track is not None and track in self._catalog:
            self._index = self._catalog.index(track)
        self.is_playing = True
        t = self.current_track
        log.info("Playing: %s -- %s", t["artist"], t["title"])

    async def pause(self) -> None:
        """Pause playback."""
        self.is_playing = False
        log.info("Paused")

    async def play_pause(self) -> None:
        """Toggle between play and pause."""
        if self.is_playing:
            await self.pause()
        else:
            await self.play()

    async def next_track(self) -> dict[str, str]:
        """Advance to the next track (wraps around).

        Returns
        -------
        dict[str, str]
            The new current track.
        """
        self._index = (self._index + 1) % len(self._catalog)
        t = self.current_track
        log.info("Next: %s -- %s", t["artist"], t["title"])
        return t

    async def previous_track(self) -> dict[str, str]:
        """Go back to the previous track (wraps around).

        Returns
        -------
        dict[str, str]
            The new current track.
        """
        self._index = (self._index - 1) % len(self._catalog)
        t = self.current_track
        log.info("Previous: %s -- %s", t["artist"], t["title"])
        return t

    async def set_volume(self, level: float) -> None:
        """Set volume level.

        Parameters
        ----------
        level : float
            Volume between 0.0 and 1.0.
        """
        self.volume_level = max(0.0, min(1.0, level))
        log.info("Volume: %.0f%%", self.volume_level * 100)

    async def toggle_mute(self) -> None:
        """Toggle mute state."""
        self.is_muted = not self.is_muted
        log.info("Muted: %s", self.is_muted)


class LightsController:
    """Mock controller for a lights card with brightness and colour-temperature.

    Parameters
    ----------
    brightness : int, default=80
        Initial brightness percentage (0–100).
    kelvin : int, default=4000
        Initial colour temperature in Kelvin (2000–6500).
    """

    def __init__(self, brightness: int = 80, kelvin: int = 4000) -> None:
        self.is_on: bool = True
        self.brightness: int = brightness
        self.kelvin: int = kelvin

    async def toggle(self) -> None:
        """Toggle lights on/off."""
        self.is_on = not self.is_on
        log.info("Lights: %s", "ON" if self.is_on else "OFF")

    async def set_brightness(self, value: int) -> None:
        """Set brightness percentage.

        Parameters
        ----------
        value : int
            Brightness between 0 and 100.
        """
        self.brightness = max(0, min(100, value))
        log.info("Brightness: %d%%", self.brightness)

    async def set_kelvin(self, value: int) -> None:
        """Set colour temperature.

        Parameters
        ----------
        value : int
            Colour temperature in Kelvin (clamped to 2000–6500).
        """
        self.kelvin = max(2000, min(6500, value))
        log.info("Kelvin: %dK", self.kelvin)


class TimerController:
    """Mock countdown timer with start/pause/reset.

    Parameters
    ----------
    initial_seconds : int, default=300
        Initial duration in seconds.
    """

    def __init__(self, initial_seconds: int = 300) -> None:
        self.duration: int = initial_seconds
        self.remaining: int = initial_seconds
        self.is_running: bool = False

    def _format(self) -> str:
        """Format remaining time as ``HH:MM:SS``.

        Returns
        -------
        str
            Formatted time string.
        """
        h, rem = divmod(self.remaining, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    async def toggle(self) -> None:
        """Start or pause the timer."""
        self.is_running = not self.is_running
        log.info("Timer %s -- %s", "started" if self.is_running else "paused", self._format())

    async def reset(self) -> None:
        """Reset the timer to its initial duration."""
        self.is_running = False
        self.remaining = self.duration
        log.info("Timer reset -- %s", self._format())

    async def adjust_duration(self, delta_seconds: int) -> None:
        """Adjust the timer duration.

        Parameters
        ----------
        delta_seconds : int
            Seconds to add (positive) or subtract (negative).
        """
        self.duration = max(0, self.duration + delta_seconds)
        self.remaining = self.duration
        log.info("Timer duration: %s", self._format())


class DashboardController:
    """Mock dashboard displaying time, weather, and deck brightness.

    Parameters
    ----------
    deck_brightness : int, default=60
        Initial deck brightness percentage (0–100).
    """

    def __init__(self, deck_brightness: int = 60) -> None:
        self.deck_brightness: int = deck_brightness
        self.temperature: str = "22°C"
        self.humidity: str = "45%"

    def get_date(self) -> str:
        """Return the current date formatted as ``YYYY-MM-DD``.

        Returns
        -------
        str
            Formatted date string.
        """
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def get_time(self) -> str:
        """Return the current time formatted as ``HH:MM``.

        Returns
        -------
        str
            Formatted time string.
        """
        return datetime.datetime.now().strftime("%H:%M")

    async def set_brightness(self, value: int) -> None:
        """Set the deck brightness.

        Parameters
        ----------
        value : int
            Brightness percentage (0–100).
        """
        self.deck_brightness = max(0, min(100, value))
        log.info("Deck brightness: %d%%", self.deck_brightness)


# ═══════════════════════════════════════════════════════════════════════════
# Card setup helpers
# ═══════════════════════════════════════════════════════════════════════════


def setup_audio_card(card: DuiCard, player: AudioPlayer) -> None:
    """Wire an AudioCard DUI card to the mock audio player.

    Binds encoder events (volume, mute, play/pause, next/previous)
    and populates the card with the player's current state.

    Parameters
    ----------
    card : DuiCard
        A loaded ``AudioCard`` DUI card.
    player : AudioPlayer
        The mock audio player instance.
    """
    track = player.current_track
    card.set_many(
        artist=track["artist"],
        title=track["title"],
        album=track["album"],
        state="Playing" if player.is_playing else "Paused",
    )
    vol_pct = player.volume_level * 100
    card.set_range("volume", vol_pct, min_val=0, max_val=100)
    card.set("value_text", f"{int(vol_pct)}%")

    @card.on("toggle_play_pause")
    async def _toggle() -> None:
        await player.play_pause()
        card.set("state", "Playing" if player.is_playing else "Paused")

    @card.on("volume_up")
    async def _vol_up(steps: int) -> None:
        new = card.adjust_range("volume", steps, min_val=0, max_val=100)
        await player.set_volume(new / 100.0)
        card.set("value_text", f"{int(new)}%")

    @card.on("volume_down")
    async def _vol_down(steps: int) -> None:
        new = card.adjust_range("volume", -abs(steps), min_val=0, max_val=100)
        await player.set_volume(new / 100.0)
        card.set("value_text", f"{int(new)}%")

    @card.on("mute_toggle")
    async def _mute() -> None:
        await player.toggle_mute()
        if player.is_muted:
            card.set("value_text", "Muted")
        else:
            vol_pct = player.volume_level * 100
            card.set("value_text", f"{int(vol_pct)}%")

    @card.on("next")
    async def _next(steps: int) -> None:
        track = await player.next_track()
        card.set_many(artist=track["artist"], title=track["title"], album=track["album"])

    @card.on("previous")
    async def _prev(steps: int) -> None:
        track = await player.previous_track()
        card.set_many(artist=track["artist"], title=track["title"], album=track["album"])


def setup_lights_card(card: DuiCard, lights: LightsController) -> None:
    """Wire a LightCard DUI card to the mock lights controller.

    Parameters
    ----------
    card : DuiCard
        A loaded ``LightCard`` DUI card.
    lights : LightsController
        The mock lights controller instance.
    """
    card.set("lights", lights.is_on)
    card.set("brightness_value_text", f"{lights.brightness}%")
    card.set("kelvin_value_text", f"{lights.kelvin}K")

    @card.on("toggle")
    async def _toggle() -> None:
        await lights.toggle()
        card.set("lights", lights.is_on)

    @card.on("brightness_up")
    async def _bright_up(steps: int) -> None:
        await lights.set_brightness(lights.brightness + steps * 5)
        card.set("brightness_value_text", f"{lights.brightness}%")

    @card.on("brightness_down")
    async def _bright_down(steps: int) -> None:
        await lights.set_brightness(lights.brightness - abs(steps) * 5)
        card.set("brightness_value_text", f"{lights.brightness}%")

    @card.on("kelvin_up")
    async def _kelvin_up(steps: int) -> None:
        await lights.set_kelvin(lights.kelvin + steps * 100)
        card.set("kelvin_value_text", f"{lights.kelvin}K")

    @card.on("kelvin_down")
    async def _kelvin_down(steps: int) -> None:
        await lights.set_kelvin(lights.kelvin - abs(steps) * 100)
        card.set("kelvin_value_text", f"{lights.kelvin}K")


def setup_timer_card(card: DuiCard, timer: TimerController) -> None:
    """Wire a TimerCard DUI card to the mock timer controller.

    Parameters
    ----------
    card : DuiCard
        A loaded ``TimerCard`` DUI card.
    timer : TimerController
        The mock timer controller instance.
    """
    card.set("timer", timer._format())

    @card.on("toggle")
    async def _toggle() -> None:
        await timer.toggle()
        card.set("timer", timer._format())

    @card.on("reset")
    async def _reset() -> None:
        await timer.reset()
        card.set("timer", timer._format())

    @card.on("increase_duration")
    async def _increase(steps: int) -> None:
        await timer.adjust_duration(steps * 30)
        card.set("timer", timer._format())

    @card.on("decrease_duration")
    async def _decrease(steps: int) -> None:
        await timer.adjust_duration(-abs(steps) * 30)
        card.set("timer", timer._format())


def setup_dashboard_card(
    card: DuiCard,
    dashboard: DashboardController,
    deck: Any,
) -> None:
    """Wire a DashboardCard DUI card to the mock dashboard controller.

    The ``brightness_up`` / ``brightness_down`` events update both the
    dashboard state and the physical deck brightness.

    Parameters
    ----------
    card : DuiCard
        A loaded ``DashboardCard`` DUI card.
    dashboard : DashboardController
        The mock dashboard controller instance.
    deck
        The :class:`~deckui.runtime.deck.Deck` handle, used to set
        hardware brightness.
    """
    card.set_many(
        date=dashboard.get_date(),
        time=dashboard.get_time(),
        temperature=dashboard.temperature,
        humidity=dashboard.humidity,
    )
    card.set_range(
        "deck_brightness",
        dashboard.deck_brightness,
        min_val=0,
        max_val=100,
    )

    @card.on("brightness_up")
    async def _bright_up(steps: int) -> None:
        new = card.adjust_range("deck_brightness", steps, min_val=0, max_val=100)
        await dashboard.set_brightness(int(new))
        await deck.set_brightness(int(new))

    @card.on("brightness_down")
    async def _bright_down(steps: int) -> None:
        new = card.adjust_range("deck_brightness", -abs(steps), min_val=0, max_val=100)
        await dashboard.set_brightness(int(new))
        await deck.set_brightness(int(new))


# ═══════════════════════════════════════════════════════════════════════════
# Key setup helpers
# ═══════════════════════════════════════════════════════════════════════════


def setup_favorites(
    screen: Any,
    player: AudioPlayer,
    picturekey_spec: Any,
) -> list[DuiKey]:
    """Create favourite-media keys that play a track on press.

    Parameters
    ----------
    screen
        The active :class:`~deckui.ui.screen.Screen`.
    player : AudioPlayer
        The mock audio player instance.
    picturekey_spec
        A loaded ``PictureKey`` :class:`~deckui.dui.schema.PackageSpec`.

    Returns
    -------
    list[DuiKey]
        The created DuiKey instances.
    """
    keys: list[DuiKey] = []
    for fav in FAVORITE_KEYS:
        key = DuiKey(picturekey_spec)
        media = fav["media"]

        @key.on_event("click")
        async def _click(m: dict[str, str] = media) -> None:
            log.info("Favorite pressed: %s -- %s", m["artist"], m["title"])
            await player.play(m)

        screen.set_key(fav["position"], key)
        keys.append(key)
    return keys


def setup_scenes(screen: Any, iconkey_spec: Any) -> None:
    """Create scene-activation keys that log the activated scene.

    Parameters
    ----------
    screen
        The active :class:`~deckui.ui.screen.Screen`.
    iconkey_spec
        A loaded ``IconKey`` :class:`~deckui.dui.schema.PackageSpec`.
    """
    for scene in SCENE_KEYS:
        key = DuiKey(iconkey_spec)
        key.set("label", scene["label"])
        key.set("icon", scene["icon"])

        @key.on_event("click")
        async def _click(name: str = scene["label"]) -> None:
            log.info("Scene activated: %s", name)

        screen.set_key(scene["position"], key)


# ═══════════════════════════════════════════════════════════════════════════
# Main application
# ═══════════════════════════════════════════════════════════════════════════


async def run() -> None:
    """Start the Stream Deck+ demo application.

    Creates a :class:`~deckui.DeckManager`, registers connect/disconnect
    handlers, loads all DUI packages, and wires up the controllers.
    Runs until interrupted.
    """
    player = AudioPlayer(MEDIA_CATALOG, initial_volume=0.3)
    lights = LightsController(brightness=80, kelvin=4000)
    timer = TimerController(initial_seconds=300)
    dashboard = DashboardController(deck_brightness=60)

    manager = DeckManager(brightness=60, auto_reconnect=True)

    # Load .dui packages from the examples directory
    audiocard_spec = load_package(EXAMPLES_DIR / "AudioCard.dui")
    lightcard_spec = load_package(EXAMPLES_DIR / "LightCard.dui")
    timercard_spec = load_package(EXAMPLES_DIR / "TimerCard.dui")
    dashcard_spec = load_package(EXAMPLES_DIR / "DashboardCard.dui")
    iconkey_spec = load_package(EXAMPLES_DIR / "IconKey.dui")
    picturekey_spec = load_package(EXAMPLES_DIR / "PictureKey.dui")

    @manager.on_connect()
    async def on_deck_connect(deck: Any) -> None:
        """Handle a new deck connection -- set up the full UI."""
        log.info("Deck connected")

        screen = deck.screen("main")

        # -- Touch-strip cards --
        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#1c1c1c"

            audio_card = DuiCard(audiocard_spec)
            setup_audio_card(audio_card, player)
            screen.set_card(0, audio_card)

            light_card = DuiCard(lightcard_spec)
            setup_lights_card(light_card, lights)
            screen.set_card(1, light_card)

            timer_card = DuiCard(timercard_spec)
            setup_timer_card(timer_card, timer)
            screen.set_card(2, timer_card)

            dash_card = DuiCard(dashcard_spec)
            setup_dashboard_card(dash_card, dashboard, deck)
            screen.set_card(3, dash_card)

        # -- Physical keys --
        setup_favorites(screen, player, picturekey_spec)
        setup_scenes(screen, iconkey_spec)

        await deck.set_screen("main")
        log.info("Deck ready!")

    @manager.on_disconnect
    async def on_deck_disconnect(info: DeviceInfo) -> None:
        """Log when a deck disconnects."""
        log.warning("Deck disconnected: %s -- waiting for reconnect...", info.serial)

    async with manager:
        await manager.wait_closed()


def main() -> None:
    """Entry point for the Stream Deck+ demo."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
