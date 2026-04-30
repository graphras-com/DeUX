#!/usr/bin/env python3
"""Stream Deck+ demo -- showcases DeckUI with self-contained controllers.

This example demonstrates how to build a complete Stream Deck+ application
using DeckUI's declarative UI system.  Each controller owns its DUI card,
loads the ``.dui`` package, manages internal state, and wires up all event
handlers -- making every controller a single, readable unit.

Four touchscreen cards (audio, lights, timer, dashboard) and eight physical
keys (four album-art favourites, four scene buttons) are set up.

No real hardware or external services are required -- every controller uses
in-memory state and logs actions to the console.

Layout
------
Keys (8-key, 2x4 grid)::

    +------+------+------+------+
    | Fav0 | Fav1 |Scene0|Scene1|
    +------+------+------+------+
    | Fav2 | Fav3 |Scene2|Scene3|
    +------+------+------+------+

Touch-strip cards (left to right)::

    [ Audio ] [ Lights ] [ Timer ] [ Dashboard ]

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

from PIL import Image

from deckui import DeckManager, DeviceInfo, DuiCard, DuiKey, load_package

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Resolve examples directory for .dui package loading
EXAMPLES_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Media catalog -- four classic albums used as favourites
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

# Key layout definitions
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


# ===================================================================
# Controllers -- each owns its card, state, and event handlers
# ===================================================================


class AudioController:
    """Audio player card controller.

    Loads the ``AudioCard.dui`` package, manages playback state (volume,
    mute, play/pause, track navigation) and exposes the wired
    :class:`~deckui.DuiCard` via the :pyattr:`card` property.

    Favourite keys call :meth:`play` to start a specific track.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries, each with ``artist``, ``album``, ``title``,
        and ``cover`` keys.
    initial_volume : float, default=0.3
        Starting volume level (0.0 -- 1.0).
    packages_dir : Path | None
        Directory containing ``.dui`` packages.  Defaults to the
        ``examples/`` directory next to this script.
    """

    def __init__(
        self,
        catalog: list[dict[str, str]],
        initial_volume: float = 0.3,
        packages_dir: Path | None = None,
    ) -> None:
        self._catalog = list(catalog)
        self._index = 0
        self.volume_level: float = initial_volume
        self.is_muted: bool = False
        self.is_playing: bool = False

        pkg_dir = packages_dir or EXAMPLES_DIR
        spec = load_package(pkg_dir / "AudioCard.dui")
        self._card = DuiCard(spec)

        self._sync_card()
        self._bind_events()

    # -- public API --------------------------------------------------------

    @property
    def card(self) -> DuiCard:
        """The wired DuiCard ready to install on a screen."""
        return self._card

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
        self._sync_card()

    async def pause(self) -> None:
        """Pause playback."""
        self.is_playing = False
        log.info("Paused")
        self._sync_card()

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
        self._sync_card()
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
        self._sync_card()
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
        self._sync_volume_text()

    async def toggle_mute(self) -> None:
        """Toggle mute state."""
        self.is_muted = not self.is_muted
        log.info("Muted: %s", self.is_muted)
        self._sync_volume_text()

    # -- internal ----------------------------------------------------------

    def _sync_card(self) -> None:
        """Push the full player state into card bindings."""
        t = self.current_track
        self._card.set_many(
            artist=t["artist"],
            title=t["title"],
            album=t["album"],
            state="Playing" if self.is_playing else "Paused",
        )
        vol_pct = self.volume_level * 100
        self._card.set_range("volume", vol_pct, min_val=0, max_val=100)
        self._sync_volume_text()

    def _sync_volume_text(self) -> None:
        """Update only the volume / mute text binding."""
        if self.is_muted:
            self._card.set("value_text", "Muted")
        else:
            self._card.set("value_text", f"{int(self.volume_level * 100)}%")

    def _bind_events(self) -> None:
        """Register card event handlers."""
        card = self._card

        @card.on("toggle_play_pause")
        async def _toggle() -> None:
            await self.play_pause()

        @card.on("volume_up")
        async def _vol_up(steps: int) -> None:
            new = card.adjust_range("volume", steps, min_val=0, max_val=100)
            await self.set_volume(new / 100.0)

        @card.on("volume_down")
        async def _vol_down(steps: int) -> None:
            new = card.adjust_range("volume", -abs(steps), min_val=0, max_val=100)
            await self.set_volume(new / 100.0)

        @card.on("mute_toggle")
        async def _mute() -> None:
            await self.toggle_mute()

        @card.on("next")
        async def _next(steps: int) -> None:
            await self.next_track()

        @card.on("previous")
        async def _prev(steps: int) -> None:
            await self.previous_track()


class LightsController:
    """Lights card controller with on/off, brightness, and colour temperature.

    Loads the ``LightCard.dui`` package and manages the light state
    internally.

    Parameters
    ----------
    brightness : int, default=80
        Initial brightness percentage (0 -- 100).
    kelvin : int, default=4000
        Initial colour temperature in Kelvin (2000 -- 6500).
    packages_dir : Path | None
        Directory containing ``.dui`` packages.
    """

    def __init__(
        self,
        brightness: int = 80,
        kelvin: int = 4000,
        packages_dir: Path | None = None,
    ) -> None:
        self.is_on: bool = True
        self.brightness: int = brightness
        self.kelvin: int = kelvin

        pkg_dir = packages_dir or EXAMPLES_DIR
        spec = load_package(pkg_dir / "LightCard.dui")
        self._card = DuiCard(spec)

        self._sync_card()
        self._bind_events()

    @property
    def card(self) -> DuiCard:
        """The wired DuiCard ready to install on a screen."""
        return self._card

    async def toggle(self) -> None:
        """Toggle lights on/off."""
        self.is_on = not self.is_on
        log.info("Lights: %s", "ON" if self.is_on else "OFF")
        self._card.set("lights", self.is_on)

    async def set_brightness(self, value: int) -> None:
        """Set brightness percentage.

        Parameters
        ----------
        value : int
            Brightness between 0 and 100.
        """
        self.brightness = max(0, min(100, value))
        log.info("Brightness: %d%%", self.brightness)
        self._card.set("brightness_value_text", f"{self.brightness}%")
        self._card.set_range("brightness", self.brightness, min_val=0, max_val=100)

    async def set_kelvin(self, value: int) -> None:
        """Set colour temperature.

        Parameters
        ----------
        value : int
            Colour temperature in Kelvin (clamped to 2000 -- 6500).
        """
        self.kelvin = max(2000, min(6500, value))
        log.info("Kelvin: %dK", self.kelvin)
        self._card.set("kelvin_value_text", f"{self.kelvin}K")
        self._card.set_range("kelvin", self.kelvin, min_val=2000, max_val=6500)

    def _sync_card(self) -> None:
        """Push the full light state into card bindings."""
        self._card.set("lights", self.is_on)
        self._card.set("brightness_value_text", f"{self.brightness}%")
        self._card.set_range("brightness", self.brightness, min_val=0, max_val=100)
        self._card.set("kelvin_value_text", f"{self.kelvin}K")
        self._card.set_range("kelvin", self.kelvin, min_val=2000, max_val=6500)

    def _bind_events(self) -> None:
        """Register card event handlers."""

        @self._card.on("toggle")
        async def _toggle() -> None:
            await self.toggle()

        @self._card.on("brightness_up")
        async def _bright_up(steps: int) -> None:
            await self.set_brightness(self.brightness + steps * 5)

        @self._card.on("brightness_down")
        async def _bright_down(steps: int) -> None:
            await self.set_brightness(self.brightness - abs(steps) * 5)

        @self._card.on("kelvin_up")
        async def _kelvin_up(steps: int) -> None:
            await self.set_kelvin(self.kelvin + steps * 100)

        @self._card.on("kelvin_down")
        async def _kelvin_down(steps: int) -> None:
            await self.set_kelvin(self.kelvin - abs(steps) * 100)


class TimerController:
    """Countdown timer card controller.

    Loads the ``TimerCard.dui`` package and manages a simple countdown
    timer with start/pause, reset, and duration adjustment.

    Parameters
    ----------
    initial_seconds : int, default=300
        Initial duration in seconds.
    packages_dir : Path | None
        Directory containing ``.dui`` packages.
    """

    def __init__(
        self,
        initial_seconds: int = 300,
        packages_dir: Path | None = None,
    ) -> None:
        self.duration: int = initial_seconds
        self.remaining: int = initial_seconds
        self.is_running: bool = False

        pkg_dir = packages_dir or EXAMPLES_DIR
        spec = load_package(pkg_dir / "TimerCard.dui")
        self._card = DuiCard(spec)

        self._sync_card()
        self._bind_events()

    @property
    def card(self) -> DuiCard:
        """The wired DuiCard ready to install on a screen."""
        return self._card

    def format_time(self) -> str:
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
        log.info(
            "Timer %s -- %s",
            "started" if self.is_running else "paused",
            self.format_time(),
        )
        self._sync_card()

    async def reset(self) -> None:
        """Reset the timer to its initial duration."""
        self.is_running = False
        self.remaining = self.duration
        log.info("Timer reset -- %s", self.format_time())
        self._sync_card()

    async def adjust_duration(self, delta_seconds: int) -> None:
        """Adjust the timer duration.

        Parameters
        ----------
        delta_seconds : int
            Seconds to add (positive) or subtract (negative).
        """
        self.duration = max(0, self.duration + delta_seconds)
        self.remaining = self.duration
        log.info("Timer duration: %s", self.format_time())
        self._sync_card()

    def _sync_card(self) -> None:
        """Push the timer display into the card binding."""
        self._card.set("timer", self.format_time())

    def _bind_events(self) -> None:
        """Register card event handlers."""

        @self._card.on("toggle")
        async def _toggle() -> None:
            await self.toggle()

        @self._card.on("reset")
        async def _reset() -> None:
            await self.reset()

        @self._card.on("increase_duration")
        async def _increase(steps: int) -> None:
            await self.adjust_duration(steps * 30)

        @self._card.on("decrease_duration")
        async def _decrease(steps: int) -> None:
            await self.adjust_duration(-abs(steps) * 30)


class DashboardController:
    """Dashboard card controller showing time, weather, and deck brightness.

    Loads the ``DashboardCard.dui`` package.  Brightness encoder events
    update both the internal state and the physical deck brightness via
    the *deck* handle passed to :meth:`bind_deck`.

    Parameters
    ----------
    deck_brightness : int, default=60
        Initial deck brightness percentage (0 -- 100).
    packages_dir : Path | None
        Directory containing ``.dui`` packages.
    """

    def __init__(
        self,
        deck_brightness: int = 60,
        packages_dir: Path | None = None,
    ) -> None:
        self.deck_brightness: int = deck_brightness
        self.temperature: str = "22C"
        self.humidity: str = "45%"
        self._deck: Any = None

        pkg_dir = packages_dir or EXAMPLES_DIR
        spec = load_package(pkg_dir / "DashboardCard.dui")
        self._card = DuiCard(spec)

        self._sync_card()
        self._bind_events()

    @property
    def card(self) -> DuiCard:
        """The wired DuiCard ready to install on a screen."""
        return self._card

    def bind_deck(self, deck: Any) -> None:
        """Attach the deck handle so brightness changes reach the hardware.

        Parameters
        ----------
        deck
            The :class:`~deckui.runtime.deck.Deck` instance.
        """
        self._deck = deck

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

        Updates both internal state and the physical deck (if bound).

        Parameters
        ----------
        value : int
            Brightness percentage (0 -- 100).
        """
        self.deck_brightness = max(0, min(100, value))
        log.info("Deck brightness: %d%%", self.deck_brightness)
        if self._deck is not None:
            await self._deck.set_brightness(self.deck_brightness)

    def _sync_card(self) -> None:
        """Push the full dashboard state into card bindings."""
        self._card.set_many(
            date=self.get_date(),
            time=self.get_time(),
            temperature=self.temperature,
            humidity=self.humidity,
        )
        self._card.set_range(
            "deck_brightness",
            self.deck_brightness,
            min_val=0,
            max_val=100,
        )

    def _bind_events(self) -> None:
        """Register card event handlers."""
        card = self._card

        @card.on("brightness_up")
        async def _bright_up(steps: int) -> None:
            new = card.adjust_range("deck_brightness", steps, min_val=0, max_val=100)
            await self.set_brightness(int(new))

        @card.on("brightness_down")
        async def _bright_down(steps: int) -> None:
            new = card.adjust_range("deck_brightness", -abs(steps), min_val=0, max_val=100)
            await self.set_brightness(int(new))


class SceneController:
    """Scene-activation key controller.

    Loads the ``IconKey.dui`` package and creates one :class:`~deckui.DuiKey`
    per scene definition.  Each key click logs the scene name.

    Parameters
    ----------
    scenes : list[dict[str, Any]]
        Scene definitions, each with ``position``, ``label``, and ``icon``.
    packages_dir : Path | None
        Directory containing ``.dui`` packages.
    """

    def __init__(
        self,
        scenes: list[dict[str, Any]],
        packages_dir: Path | None = None,
    ) -> None:
        self._scenes = scenes
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._spec = load_package(pkg_dir / "IconKey.dui")
        self._keys: list[DuiKey] = []

        for scene in self._scenes:
            key = DuiKey(self._spec)
            key.set("label", scene["label"])
            key.set("icon", scene["icon"])

            @key.on_event("click")
            async def _click(name: str = scene["label"]) -> None:
                log.info("Scene activated: %s", name)

            self._keys.append(key)

    @property
    def keys(self) -> list[DuiKey]:
        """The created scene keys (same order as *scenes*)."""
        return list(self._keys)

    def install(self, screen: Any) -> None:
        """Place all scene keys onto a screen at their configured positions.

        Parameters
        ----------
        screen
            The :class:`~deckui.ui.screen.Screen` to install keys on.
        """
        for scene, key in zip(self._scenes, self._keys, strict=True):
            screen.set_key(scene["position"], key)


class FavoritesController:
    """Favourite-media key controller.

    Loads the ``PictureKey.dui`` package and creates one
    :class:`~deckui.DuiKey` per favourite.  Clicking a key calls
    :meth:`AudioController.play` with the associated track.

    Parameters
    ----------
    favorites : list[dict[str, Any]]
        Favourite definitions, each with ``position`` and ``media``.
    audio : AudioController
        The audio controller that handles playback.
    packages_dir : Path | None
        Directory containing ``.dui`` packages.
    """

    def __init__(
        self,
        favorites: list[dict[str, Any]],
        audio: AudioController,
        packages_dir: Path | None = None,
    ) -> None:
        self._favorites = favorites
        self._audio = audio
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._spec = load_package(pkg_dir / "PictureKey.dui")
        self._keys: list[DuiKey] = []

        for fav in self._favorites:
            key = DuiKey(self._spec)
            media = fav["media"]

            # Load the album cover and set it on the key
            cover_path = pkg_dir / media["cover"]
            if cover_path.exists():
                key.set("picture", Image.open(cover_path))

            @key.on_event("click")
            async def _click(m: dict[str, str] = media) -> None:
                log.info("Favourite pressed: %s -- %s", m["artist"], m["title"])
                await self._audio.play(m)

            self._keys.append(key)

    @property
    def keys(self) -> list[DuiKey]:
        """The created favourite keys (same order as *favorites*)."""
        return list(self._keys)

    def install(self, screen: Any) -> None:
        """Place all favourite keys onto a screen at their configured positions.

        Parameters
        ----------
        screen
            The :class:`~deckui.ui.screen.Screen` to install keys on.
        """
        for fav, key in zip(self._favorites, self._keys, strict=True):
            screen.set_key(fav["position"], key)


# ===================================================================
# Main application
# ===================================================================


async def run() -> None:
    """Start the Stream Deck+ demo application.

    Creates controllers, registers connect/disconnect handlers, and runs
    until interrupted.
    """
    audio = AudioController(MEDIA_CATALOG, initial_volume=0.3)
    lights = LightsController(brightness=80, kelvin=4000)
    timer = TimerController(initial_seconds=300)
    dashboard = DashboardController(deck_brightness=60)
    scenes = SceneController(SCENE_KEYS)
    favorites = FavoritesController(FAVORITE_KEYS, audio)

    manager = DeckManager(brightness=60, auto_reconnect=True)

    @manager.on_connect()
    async def on_deck_connect(deck: Any) -> None:
        """Handle a new deck connection -- set up the full UI."""
        log.info("Deck connected")

        dashboard.bind_deck(deck)
        screen = deck.screen("main")

        # Touch-strip cards
        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#1c1c1c"
            screen.set_card(0, audio.card)
            screen.set_card(1, lights.card)
            screen.set_card(2, timer.card)
            screen.set_card(3, dashboard.card)

        # Physical keys
        favorites.install(screen)
        scenes.install(screen)

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
