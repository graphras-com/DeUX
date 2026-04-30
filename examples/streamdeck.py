#!/usr/bin/env python3
"""Stream Deck demo -- a complete walkthrough of the DeckUI library.

This single-file example showcases every major DeckUI concept against
any connected Stream Deck.  It is designed to read top-to-bottom as a
tutorial -- each section introduces one feature.

What it demonstrates
--------------------
* :class:`~deckui.DeckManager` for auto-discovery and hot-plug.
* Loading ``.dui`` packages via :func:`~deckui.load_package` and using
  :class:`~deckui.DuiCard` / :class:`~deckui.DuiKey`.
* Using :meth:`~deckui.DuiCard.set` / :meth:`~deckui.DuiCard.set_many`
  / :meth:`~deckui.DuiCard.set_range` / :meth:`~deckui.DuiCard.adjust_range`
  helpers instead of manual normalisation.
* Triggering re-renders from key handlers and background tasks via
  :meth:`~deckui.DuiCard.request_refresh`.
* A live, asyncio-driven countdown ``TimerCard`` and a dashboard clock
  that ticks every second.
* Multi-screen navigation -- a ``main`` screen and a ``settings`` screen.

Running
-------
::

    python examples/streamdeck.py

No real services are required -- every controller uses in-memory state
and logs actions to the console.  Press Ctrl+C to exit.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import logging
from pathlib import Path
from typing import Any

from PIL import Image

from deckui import DeckManager, DeviceInfo, DuiCard, DuiKey, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Resolve the directory holding the .dui packages and image assets used
# below.  Adjust if you move them elsewhere.
EXAMPLES_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Demo data -- four classic albums (favourites) and four "scenes"
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

SCENE_DEFS: list[dict[str, str]] = [
    {"label": "Normal", "icon": "fa-regular:smile-beam"},
    {"label": "Tired", "icon": "fa-regular:tired"},
    {"label": "Cinema", "icon": "mdi:cinema"},
    {"label": "Bedtime", "icon": "icon-park-outline:sleep-two"},
]


# ===========================================================================
# Controllers
# ===========================================================================
#
# Each controller owns one ``.dui`` widget (card or key), maps domain
# state -> bindings, and wires event handlers.  Controllers never touch
# the deck directly: they call :meth:`DuiCard.request_refresh` /
# :meth:`DuiKey.request_refresh` when state changes, and the deck
# re-renders dirty regions automatically.
# ===========================================================================


class AudioController:
    """Audio player card -- play/pause, mute, volume, track navigation.

    Loads ``AudioCard.dui`` and binds encoder events:

    * encoder hold     -> toggle play/pause
    * encoder turn     -> volume up/down
    * encoder click    -> mute toggle
    * encoder press+turn -> previous/next track

    Favourite keys (see :class:`FavoritesController`) call :meth:`play`
    to start a specific track.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries with ``artist``, ``album``, ``title``, ``cover``.
    initial_volume : float, default=0.3
        Starting volume (0.0 -- 1.0).
    packages_dir : Path | None
        Directory containing ``AudioCard.dui``.  Defaults to ``examples/``.
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

        self._pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(self._pkg_dir / "AudioCard.dui"))

        self._sync_card()
        self._bind_events()

    # -- public API -----------------------------------------------------

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    @property
    def current_track(self) -> dict[str, str]:
        """The currently selected media entry."""
        return self._catalog[self._index]

    async def play(self, track: dict[str, str] | None = None) -> None:
        """Start playback (optionally jumping to *track*) and refresh.

        Parameters
        ----------
        track : dict[str, str] | None
            If given and present in the catalog, jump to it first.
        """
        if track is not None and track in self._catalog:
            self._index = self._catalog.index(track)
        self.is_playing = True
        t = self.current_track
        log.info("Playing: %s -- %s", t["artist"], t["title"])
        self._sync_card()
        await self._card.request_refresh()

    async def pause(self) -> None:
        """Pause playback and refresh."""
        self.is_playing = False
        log.info("Paused")
        self._sync_card()
        await self._card.request_refresh()

    async def play_pause(self) -> None:
        """Toggle play/pause."""
        if self.is_playing:
            await self.pause()
        else:
            await self.play()

    async def next_track(self) -> dict[str, str]:
        """Advance to the next track (wraps).

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
        """Go back to the previous track (wraps).

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
        """Set volume in [0.0, 1.0] and refresh.

        Parameters
        ----------
        level : float
            Volume between 0.0 and 1.0.  Out-of-range values are clamped.
        """
        self.volume_level = max(0.0, min(1.0, level))
        log.info("Volume: %.0f%%", self.volume_level * 100)
        self._sync_volume_text()

    async def toggle_mute(self) -> None:
        """Toggle mute and refresh the volume text."""
        self.is_muted = not self.is_muted
        log.info("Muted: %s", self.is_muted)
        self._sync_volume_text()

    # -- internal -------------------------------------------------------

    def _sync_card(self) -> None:
        """Push the full player state into card bindings."""
        t = self.current_track
        self._card.set_many(
            artist=t["artist"],
            title=t["title"],
            album=t["album"],
            state="Playing" if self.is_playing else "Paused",
        )
        cover_path = self._pkg_dir / t["cover"]
        if cover_path.exists():
            self._card.set("cover", Image.open(cover_path))
        # set_range normalises 0-100 -> 0.0-1.0 so the SVG range binding
        # gets the value it expects.
        self._card.set_range("volume", self.volume_level * 100, min_val=0, max_val=100)
        self._sync_volume_text()

    def _sync_volume_text(self) -> None:
        """Update only the volume / mute text binding."""
        if self.is_muted:
            self._card.set("value_text", "Muted")
        else:
            self._card.set("value_text", f"{int(self.volume_level * 100)}%")

    def _bind_events(self) -> None:
        """Register card event handlers (declared in the manifest)."""
        card = self._card

        @card.on("toggle_play_pause")
        async def _toggle() -> None:
            await self.play_pause()

        @card.on("volume_up")
        async def _vol_up(steps: int) -> None:
            # adjust_range clamps and returns the new domain value, so we
            # don't have to re-compute the percentage ourselves.
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
        async def _next(_steps: int) -> None:
            await self.next_track()

        @card.on("previous")
        async def _prev(_steps: int) -> None:
            await self.previous_track()


class LightsController:
    """Lights card -- on/off toggle, brightness, colour temperature.

    Loads ``LightCard.dui`` and binds:

    * encoder click       -> on/off toggle
    * encoder turn        -> brightness up/down (5 % per step)
    * encoder press+turn  -> kelvin up/down (100 K per step)

    Parameters
    ----------
    brightness : int, default=80
        Initial brightness percentage (0 -- 100).
    kelvin : int, default=4000
        Initial colour temperature in Kelvin (2000 -- 6500).
    packages_dir : Path | None
        Directory containing ``LightCard.dui``.
    """

    BRIGHTNESS_MIN = 0
    BRIGHTNESS_MAX = 100
    KELVIN_MIN = 2000
    KELVIN_MAX = 6500

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
        self._card = DuiCard(load_package(pkg_dir / "LightCard.dui"))

        self._sync_card()
        self._bind_events()

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    async def toggle(self) -> None:
        """Toggle lights on/off."""
        self.is_on = not self.is_on
        log.info("Lights: %s", "ON" if self.is_on else "OFF")
        self._card.set("lights", self.is_on)

    async def set_brightness(self, value: int) -> None:
        """Set brightness percentage (clamped to 0 -- 100)."""
        self.brightness = max(self.BRIGHTNESS_MIN, min(self.BRIGHTNESS_MAX, value))
        log.info("Brightness: %d%%", self.brightness)
        self._card.set("brightness_value_text", f"{self.brightness}%")
        self._card.set_range(
            "brightness",
            self.brightness,
            min_val=self.BRIGHTNESS_MIN,
            max_val=self.BRIGHTNESS_MAX,
        )

    async def set_kelvin(self, value: int) -> None:
        """Set colour temperature (clamped to 2000 -- 6500 K)."""
        self.kelvin = max(self.KELVIN_MIN, min(self.KELVIN_MAX, value))
        log.info("Kelvin: %dK", self.kelvin)
        self._card.set("kelvin_value_text", f"{self.kelvin}K")
        self._card.set_range(
            "kelvin",
            self.kelvin,
            min_val=self.KELVIN_MIN,
            max_val=self.KELVIN_MAX,
        )

    def _sync_card(self) -> None:
        """Push the full light state into card bindings."""
        self._card.set("lights", self.is_on)
        self._card.set("brightness_value_text", f"{self.brightness}%")
        self._card.set_range(
            "brightness",
            self.brightness,
            min_val=self.BRIGHTNESS_MIN,
            max_val=self.BRIGHTNESS_MAX,
        )
        self._card.set("kelvin_value_text", f"{self.kelvin}K")
        self._card.set_range(
            "kelvin",
            self.kelvin,
            min_val=self.KELVIN_MIN,
            max_val=self.KELVIN_MAX,
        )

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
    """Live countdown timer -- a real ticking timer driven by an asyncio task.

    Loads ``TimerCard.dui`` and binds:

    * encoder click  -> start/pause
    * encoder hold   -> reset to *initial_seconds*
    * encoder turn   -> add/remove 30 s

    While running, an internal asyncio task decrements ``remaining`` every
    second and calls :meth:`DuiCard.request_refresh` so the display
    updates live without any polling on the caller's side.

    Use :meth:`start_runtime` once the deck is connected and
    :meth:`stop_runtime` to clean up on disconnect.

    Parameters
    ----------
    initial_seconds : int, default=300
        Initial duration in seconds.
    packages_dir : Path | None
        Directory containing ``TimerCard.dui``.
    """

    TICK_INTERVAL_S = 1.0
    ADJUST_STEP_S = 30

    def __init__(
        self,
        initial_seconds: int = 300,
        packages_dir: Path | None = None,
    ) -> None:
        self.duration: int = initial_seconds
        self.remaining: int = initial_seconds
        self.is_running: bool = False

        pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(pkg_dir / "TimerCard.dui"))
        self._tick_task: asyncio.Task[None] | None = None

        self._sync_card()
        self._bind_events()

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    def format_time(self) -> str:
        """Format ``remaining`` as ``HH:MM:SS``.

        Returns
        -------
        str
            Zero-padded ``HH:MM:SS`` string.
        """
        h, rem = divmod(max(0, self.remaining), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    async def start_runtime(self) -> None:
        """Start the background tick task.

        Idempotent -- safe to call multiple times.  Should be called
        after the screen is active so the first tick can refresh the
        display.
        """
        if self._tick_task is None or self._tick_task.done():
            self._tick_task = asyncio.create_task(
                self._tick_loop(), name="timer-tick"
            )

    async def stop_runtime(self) -> None:
        """Cancel the background tick task and wait for it to exit."""
        task = self._tick_task
        self._tick_task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def toggle(self) -> None:
        """Start or pause the countdown."""
        # When the timer was paused at 0 (or has rolled to 0 since pause)
        # restart from the configured duration so the user gets a fresh run.
        if not self.is_running and self.remaining <= 0:
            self.remaining = self.duration
        self.is_running = not self.is_running
        log.info(
            "Timer %s -- %s",
            "started" if self.is_running else "paused",
            self.format_time(),
        )
        self._sync_card()
        await self._card.request_refresh()

    async def reset(self) -> None:
        """Stop the countdown and reload the configured duration."""
        self.is_running = False
        self.remaining = self.duration
        log.info("Timer reset -- %s", self.format_time())
        self._sync_card()
        await self._card.request_refresh()

    async def adjust_duration(self, delta_seconds: int) -> None:
        """Add (or subtract) seconds to/from the configured duration.

        Resets the running countdown to the new duration so adjustments
        are immediately visible.

        Parameters
        ----------
        delta_seconds : int
            Seconds to add (positive) or subtract (negative).
        """
        self.duration = max(0, self.duration + delta_seconds)
        self.remaining = self.duration
        log.info("Timer duration: %s", self.format_time())
        self._sync_card()
        await self._card.request_refresh()

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
            await self.adjust_duration(steps * self.ADJUST_STEP_S)

        @self._card.on("decrease_duration")
        async def _decrease(steps: int) -> None:
            await self.adjust_duration(-abs(steps) * self.ADJUST_STEP_S)

    async def _tick_loop(self) -> None:
        """Decrement *remaining* once per second while running."""
        try:
            while True:
                await asyncio.sleep(self.TICK_INTERVAL_S)
                if not self.is_running:
                    continue
                if self.remaining > 0:
                    self.remaining -= 1
                    self._sync_card()
                    await self._card.request_refresh()
                if self.remaining <= 0 and self.is_running:
                    self.is_running = False
                    log.info("Timer finished")
                    self._sync_card()
                    await self._card.request_refresh()
        except asyncio.CancelledError:
            pass


class DashboardController:
    """Dashboard card -- live clock, mock weather, deck-brightness control.

    Loads ``DashboardCard.dui``.  Brightness encoder events update both
    the internal state and the physical deck via the *deck* handle
    passed to :meth:`bind_deck`.  An asyncio task ticks every second to
    keep the displayed clock accurate.

    Use :meth:`start_runtime` once the deck is connected and
    :meth:`stop_runtime` to clean up on disconnect.

    Parameters
    ----------
    deck_brightness : int, default=60
        Initial deck brightness percentage (0 -- 100).
    packages_dir : Path | None
        Directory containing ``DashboardCard.dui``.
    """

    CLOCK_INTERVAL_S = 1.0

    def __init__(
        self,
        deck_brightness: int = 60,
        packages_dir: Path | None = None,
    ) -> None:
        self.deck_brightness: int = deck_brightness
        self.temperature: str = "22C"
        self.humidity: str = "45%"
        self._deck: Any = None
        self._clock_task: asyncio.Task[None] | None = None

        pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(pkg_dir / "DashboardCard.dui"))

        self._sync_card()
        self._bind_events()

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    def bind_deck(self, deck: Any) -> None:
        """Attach the deck handle so brightness changes reach the hardware."""
        self._deck = deck

    @staticmethod
    def get_date() -> str:
        """Return today's date as ``YYYY-MM-DD``."""
        return datetime.datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_time() -> str:
        """Return the current local time as ``HH:MM``."""
        return datetime.datetime.now().strftime("%H:%M")

    async def set_brightness(self, value: int) -> None:
        """Set the deck brightness (clamped to 0 -- 100).

        Updates internal state, the bound physical deck, and the slider
        binding on the card.
        """
        self.deck_brightness = max(0, min(100, value))
        log.info("Deck brightness: %d%%", self.deck_brightness)
        self._card.set_range(
            "deck_brightness",
            self.deck_brightness,
            min_val=0,
            max_val=100,
        )
        if self._deck is not None:
            await self._deck.set_brightness(self.deck_brightness)

    async def start_runtime(self) -> None:
        """Start the background clock-tick task (idempotent)."""
        if self._clock_task is None or self._clock_task.done():
            self._clock_task = asyncio.create_task(
                self._clock_loop(), name="dashboard-clock"
            )

    async def stop_runtime(self) -> None:
        """Cancel the clock-tick task."""
        task = self._clock_task
        self._clock_task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

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
            new = card.adjust_range(
                "deck_brightness", -abs(steps), min_val=0, max_val=100
            )
            await self.set_brightness(int(new))

    async def _clock_loop(self) -> None:
        """Refresh the clock display every second.

        Only marks the card dirty when the visible value actually changes
        so we don't churn the SVG renderer 60x per minute.
        """
        last_time = ""
        last_date = ""
        try:
            while True:
                await asyncio.sleep(self.CLOCK_INTERVAL_S)
                t = self.get_time()
                d = self.get_date()
                if t == last_time and d == last_date:
                    continue
                last_time, last_date = t, d
                self._card.set_many(time=t, date=d)
                await self._card.request_refresh()
        except asyncio.CancelledError:
            pass


class FavoritesController:
    """Favourite-media keys -- one :class:`DuiKey` per catalog entry.

    Loads ``PictureKey.dui`` once and instantiates a key per favourite.
    Clicking a key calls :meth:`AudioController.play` with the matching
    track.  The audio controller refreshes the AudioCard automatically
    via ``card.request_refresh()`` -- which now works from key handlers
    too thanks to the deck wiring callbacks on every key/card.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries used as favourites.
    audio : AudioController
        The audio controller that handles playback.
    packages_dir : Path | None
        Directory containing ``PictureKey.dui``.
    """

    def __init__(
        self,
        catalog: list[dict[str, str]],
        audio: AudioController,
        packages_dir: Path | None = None,
    ) -> None:
        self._catalog = catalog
        self._audio = audio
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._spec = load_package(pkg_dir / "PictureKey.dui")
        self._keys: list[DuiKey] = []

        for media in self._catalog:
            key = DuiKey(self._spec)

            cover_path = pkg_dir / media["cover"]
            if cover_path.exists():
                key.set("picture", Image.open(cover_path))

            # Late-bind *media* per iteration so each handler captures
            # its own dict instead of the loop variable.
            @key.on_event("click")
            async def _click(m: dict[str, str] = media) -> None:
                log.info("Favourite pressed: %s -- %s", m["artist"], m["title"])
                await self._audio.play(m)

            self._keys.append(key)

    @property
    def keys(self) -> list[DuiKey]:
        """The created favourite keys (same order as *catalog*)."""
        return list(self._keys)

    def install(self, screen: Any, positions: list[int]) -> None:
        """Place favourite keys onto *screen* at the given *positions*.

        Installs ``min(len(keys), len(positions))`` keys.
        """
        for pos, key in zip(positions, self._keys, strict=False):
            screen.set_key(pos, key)


class SceneController:
    """Scene-activation keys -- one :class:`DuiKey` per scene definition.

    Loads ``IconKey.dui`` once and instantiates a key per scene.  Each
    key has three handlers, demonstrating that ``press`` and ``release``
    are emitted alongside the higher-level ``click`` event:

    * ``press``   -- inverts the foreground / background colours so the
      key visually flashes while held.
    * ``release`` -- restores the original colours.
    * ``click``   -- logs the scene name (replace with your automation).

    The colour swap also showcases how to update bindings from a key
    handler and call :meth:`DuiKey.request_refresh` to push the change
    to the device immediately.

    Parameters
    ----------
    scenes : list[dict[str, str]]
        Scene definitions, each with ``label`` and ``icon`` (an Iconify
        identifier such as ``"mdi:cinema"``).
    packages_dir : Path | None
        Directory containing ``IconKey.dui``.
    """

    # Defaults match the IconKey.dui manifest.
    DEFAULT_BACKGROUND = "#1c1c1c"
    DEFAULT_FOREGROUND = "#dedede"

    def __init__(
        self,
        scenes: list[dict[str, str]],
        packages_dir: Path | None = None,
    ) -> None:
        self._scenes = scenes
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._spec = load_package(pkg_dir / "IconKey.dui")
        self._keys: list[DuiKey] = []

        for scene in self._scenes:
            key = DuiKey(self._spec)
            key.set_many(
                label=scene["label"],
                icon=scene["icon"],
                background=self.DEFAULT_BACKGROUND,
                foreground=self.DEFAULT_FOREGROUND,
            )

            # Bind handlers via a helper so each key captures its own
            # *key* reference instead of the loop variable.
            self._bind_handlers(key, scene["label"])
            self._keys.append(key)

    def _bind_handlers(self, key: DuiKey, label: str) -> None:
        """Attach press/release/click handlers to *key*.

        Splitting this into a helper guarantees correct closure capture
        for *key* and *label* per iteration.

        Parameters
        ----------
        key : DuiKey
            The key to wire.
        label : str
            Scene label, logged on click.
        """

        @key.on_event("press")
        async def _press() -> None:
            # Invert colours by swapping background <-> foreground.
            key.set_many(
                background=self.DEFAULT_FOREGROUND,
                foreground=self.DEFAULT_BACKGROUND,
            )
            await key.request_refresh()

        @key.on_event("release")
        async def _release() -> None:
            key.set_many(
                background=self.DEFAULT_BACKGROUND,
                foreground=self.DEFAULT_FOREGROUND,
            )
            await key.request_refresh()

        @key.on_event("click")
        async def _click() -> None:
            log.info("Scene activated: %s", label)

    @property
    def keys(self) -> list[DuiKey]:
        """The created scene keys (same order as *scenes*)."""
        return list(self._keys)

    def install(self, screen: Any, positions: list[int]) -> None:
        """Place scene keys onto *screen* at the given *positions*."""
        for pos, key in zip(positions, self._keys, strict=False):
            screen.set_key(pos, key)


class NavigationController:
    """A single key that toggles the deck between two screens.

    Demonstrates :meth:`Deck.set_screen` -- screens are independent
    layouts that swap atomically, so you can reuse the same physical
    keys/encoders for completely different functionality.

    Parameters
    ----------
    primary : str
        Name of the primary screen.
    secondary : str
        Name of the secondary screen.
    label_primary, label_secondary : str
        Labels shown on the key in each mode.
    icon_primary, icon_secondary : str
        Iconify icons shown in each mode.
    packages_dir : Path | None
        Directory containing ``IconKey.dui``.
    """

    def __init__(
        self,
        primary: str,
        secondary: str,
        *,
        label_primary: str = "Settings",
        label_secondary: str = "Back",
        icon_primary: str = "mdi:cog",
        icon_secondary: str = "mdi:arrow-left",
        packages_dir: Path | None = None,
    ) -> None:
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._primary = primary
        self._secondary = secondary
        self._labels = (label_primary, label_secondary)
        self._icons = (icon_primary, icon_secondary)
        self._deck: Any = None
        self._on_secondary = False

        self._key = DuiKey(load_package(pkg_dir / "IconKey.dui"))
        self._render_label()

        @self._key.on_event("click")
        async def _click() -> None:
            await self._toggle()

    @property
    def key(self) -> DuiKey:
        """The navigation :class:`DuiKey`."""
        return self._key

    def bind_deck(self, deck: Any) -> None:
        """Attach the deck so the controller can call ``set_screen``."""
        self._deck = deck

    async def _toggle(self) -> None:
        """Swap between primary and secondary screens."""
        if self._deck is None:
            return
        target = self._primary if self._on_secondary else self._secondary
        self._on_secondary = not self._on_secondary
        self._render_label()
        log.info("Navigating to screen: %s", target)
        await self._deck.set_screen(target)

    def _render_label(self) -> None:
        """Update the key label/icon for the current mode."""
        idx = 1 if self._on_secondary else 0
        self._key.set_many(label=self._labels[idx], icon=self._icons[idx])


# ===========================================================================
# Application
# ===========================================================================


class StreamDeckApp:
    """Top-level demo app -- glues controllers to the deck.

    Build the controllers once, then :meth:`build_screens` is called from
    the manager's ``on_connect`` callback to install them on the
    appropriate screens for the connected device.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media catalog used by the audio + favourites controllers.
    scene_defs : list[dict[str, str]]
        Scene definitions used by the scene controller.
    packages_dir : Path | None
        Directory containing the ``.dui`` packages.
    """

    def __init__(
        self,
        catalog: list[dict[str, str]],
        scene_defs: list[dict[str, str]],
        packages_dir: Path | None = None,
    ) -> None:
        self._packages_dir = packages_dir or EXAMPLES_DIR
        self.audio = AudioController(
            catalog, initial_volume=0.3, packages_dir=self._packages_dir
        )
        self.lights = LightsController(
            brightness=80, kelvin=4000, packages_dir=self._packages_dir
        )
        self.timer = TimerController(
            initial_seconds=300, packages_dir=self._packages_dir
        )
        self.dashboard = DashboardController(
            deck_brightness=60, packages_dir=self._packages_dir
        )
        self.favorites = FavoritesController(
            catalog, self.audio, packages_dir=self._packages_dir
        )
        self.scenes = SceneController(
            scene_defs, packages_dir=self._packages_dir
        )
        self.nav = NavigationController(
            primary="main",
            secondary="settings",
            packages_dir=self._packages_dir,
        )

    async def on_connect(self, deck: Any) -> None:
        """Configure screens for *deck* and start the demo.

        Parameters
        ----------
        deck
            The :class:`~deckui.runtime.deck.Deck` handle from the
            manager's ``on_connect`` callback.
        """
        caps = deck.capabilities
        log.info(
            "Deck connected: %s (%d keys, %d encoders, touchscreen=%s)",
            caps.deck_type,
            caps.key_count,
            caps.dial_count,
            "yes" if caps.has_touchscreen else "no",
        )

        # Wire deck-aware controllers
        self.dashboard.bind_deck(deck)
        self.nav.bind_deck(deck)

        # Build both screens up-front so the navigation controller can
        # switch between them at any time.
        self._build_main_screen(deck)
        self._build_settings_screen(deck)

        # Activate the main screen.  This also wires every key/card's
        # request_refresh() to deck.refresh() under the hood.
        await deck.set_screen("main")

        # Start background tasks AFTER the screen is active so their
        # request_refresh() calls go to the right place.
        await self.timer.start_runtime()
        await self.dashboard.start_runtime()

        log.info("Deck ready -- try the encoders, keys, and Settings button!")

    async def on_disconnect(self, info: DeviceInfo) -> None:
        """Stop background tasks when the deck goes away."""
        log.warning("Deck disconnected: %s -- waiting for reconnect...", info.serial)
        await self.timer.stop_runtime()
        await self.dashboard.stop_runtime()

    # -- screen construction -------------------------------------------

    def _build_main_screen(self, deck: Any) -> None:
        """Layout: favourites + scenes on keys, all four cards on the strip.

        Parameters
        ----------
        deck
            Open deck handle.
        """
        caps = deck.capabilities
        screen = deck.screen("main")

        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#1c1c1c"
            screen.set_card(0, self.audio.card)
            screen.set_card(1, self.lights.card)
            screen.set_card(2, self.timer.card)
            screen.set_card(3, self.dashboard.card)

        # Favourites first, then scenes, then a single navigation key at
        # the very last position if there's room.
        num_favs = min(len(self.favorites.keys), caps.key_count)
        remaining = max(0, caps.key_count - num_favs)
        num_scenes = min(len(self.scenes.keys), remaining)

        self.favorites.install(screen, list(range(num_favs)))
        self.scenes.install(screen, list(range(num_favs, num_favs + num_scenes)))

        # Reserve the last key for navigation if at least one slot is free.
        nav_index = caps.key_count - 1
        if nav_index >= num_favs + num_scenes:
            screen.set_key(nav_index, self.nav.key)

    def _build_settings_screen(self, deck: Any) -> None:
        """Layout: just the navigation key + dashboard card.

        Demonstrates that the same controller can appear on multiple
        screens -- DeckUI does not care, it simply renders whatever's
        installed when the screen is active.

        Parameters
        ----------
        deck
            Open deck handle.
        """
        screen = deck.screen("settings")
        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#0a0a0a"
            screen.set_card(0, self.dashboard.card)
            screen.set_card(1, self.lights.card)

        # Place the navigation key at slot 0 so users always know where
        # to go to get back.
        if deck.capabilities.key_count > 0:
            screen.set_key(0, self.nav.key)


# ===========================================================================
# Entry point
# ===========================================================================


async def run() -> None:
    """Build the app, attach to :class:`DeckManager`, and run forever.

    This is the canonical DeckUI lifecycle:

    1. Construct your controllers.
    2. Create a :class:`DeckManager`.
    3. Register ``on_connect`` / ``on_disconnect`` handlers.
    4. ``async with`` the manager and ``await manager.wait_closed()``.
    """
    app = StreamDeckApp(MEDIA_CATALOG, SCENE_DEFS)
    manager = DeckManager(brightness=60, auto_reconnect=True)

    @manager.on_connect()
    async def _on_connect(deck: Any) -> None:
        await app.on_connect(deck)

    @manager.on_disconnect
    async def _on_disconnect(info: DeviceInfo) -> None:
        await app.on_disconnect(info)

    async with manager:
        await manager.wait_closed()


def main() -> None:
    """Entry point for ``python examples/streamdeck.py``."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Bye!")


if __name__ == "__main__":
    main()
