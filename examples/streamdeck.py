#!/usr/bin/env python3
"""Stream Deck demo -- a complete walkthrough of the DeckUI library.

This single-file example showcases every major DeckUI concept against
any connected Stream Deck.  It is designed to read top-to-bottom as a
tutorial -- each section introduces one feature.

Domain logic (audio playback, smart lights, timer countdown, dashboard
telemetry) lives in :mod:`mock_backend` so this file focuses purely on
DeckUI wiring.  Swap those mock services for real integrations and the
code below stays the same.

**Event-driven architecture** -- controllers never update the UI directly
in response to user input.  Instead, DUI event handlers call service
methods (e.g. ``svc.set_brightness(80)``), and the service emits an
async event (e.g. ``on_brightness_changed``) once the state has actually
changed.  The controller subscribes to that event and updates the card
bindings there.  This is the same pattern a real backend would use:
the UI always reflects *confirmed* state, not *requested* state.

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
* Multi-screen navigation -- a ``main`` screen and a ``settings``
  screen, cycled by an encoder press-release on the dashboard card
  (see ``DashboardCard.dui``'s ``next_screen`` event).

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
import logging
from pathlib import Path
from typing import Any

from mock_backend import (
    MEDIA_CATALOG,
    SCENE_DEFS,
    MockAudioService,
    MockDashboardService,
    MockLightsService,
    MockTimerService,
)
from PIL import Image

from deckui import DeckManager, DeviceInfo, DuiCard, DuiKey, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Resolve the directory holding the .dui packages and image assets used
# below.  Adjust if you move them elsewhere.
EXAMPLES_DIR = Path(__file__).resolve().parent


# ===========================================================================
# Controllers
# ===========================================================================
#
# Each controller owns one ``.dui`` widget (card or key) and a mock
# service from ``mock_backend``.
#
# The flow is:
#
#   1. A DUI event fires (encoder turn, key press, etc.).
#   2. The controller's event handler calls the *service* method
#      (e.g. ``svc.set_brightness(80)``).
#   3. The service updates its internal state and emits an async event
#      (e.g. ``on_brightness_changed``).
#   4. The controller's *subscriber* for that event updates the card
#      bindings and calls ``request_refresh()``.
#
# This decouples "what happened" from "how the UI reacts" -- exactly
# how a real integration (Spotify, Home Assistant, etc.) would work.
# ===========================================================================


class AudioController:
    """Audio player card -- play/pause, mute, volume, track navigation.

    Loads ``AudioCard.dui`` and binds encoder events:

    * encoder hold     -> toggle play/pause
    * encoder turn     -> volume up/down
    * encoder click    -> mute toggle
    * encoder press+turn -> previous/next track

    Favourite keys (see :class:`FavoritesController`) call
    :meth:`MockAudioService.play` via the service to start a specific
    track.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries with ``artist``, ``album``, ``title``, ``cover``.
    packages_dir : Path | None
        Directory containing ``AudioCard.dui``.  Defaults to ``examples/``.
    """

    def __init__(
        self,
        catalog: list[dict[str, str]],
        packages_dir: Path | None = None,
    ) -> None:
        self._pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(self._pkg_dir / "AudioCard.dui"))

        # Read the initial volume from the .dui package's range binding
        # default so the package is the single source of truth.
        initial_volume: float = self._card.get("volume")
        self._svc = MockAudioService(catalog, initial_volume=initial_volume)

        self._sync_card()
        self._subscribe_events()
        self._bind_dui_events()

    # -- public API -----------------------------------------------------

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    @property
    def svc(self) -> MockAudioService:
        """The underlying audio service (for external callers like favourites)."""
        return self._svc

    @property
    def volume_level(self) -> float:
        """Current volume level (0.0 -- 1.0)."""
        return self._svc.volume_level

    @property
    def is_muted(self) -> bool:
        """Whether audio is muted."""
        return self._svc.is_muted

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently playing."""
        return self._svc.is_playing

    @property
    def current_track(self) -> dict[str, str]:
        """The currently selected media entry."""
        return self._svc.current_track

    # -- internal -------------------------------------------------------

    def _sync_card(self) -> None:
        """Push the full player state into card bindings (initial load only)."""
        t = self._svc.current_track
        self._card.set_many(
            artist=t["artist"],
            title=t["title"],
            album=t["album"],
            state="Playing" if self._svc.is_playing else "Paused",
        )
        cover_path = self._pkg_dir / t["cover"]
        if cover_path.exists():
            self._card.set("cover", Image.open(cover_path))
        self._card.set_range(
            "volume", self._svc.volume_level * 100, min_val=0, max_val=100
        )
        self._card.set("value_text", self._svc.volume_text)

    def _subscribe_events(self) -> None:
        """Subscribe to service state-change events."""

        @self._svc.on_track_changed
        async def _on_track(track: dict[str, str], is_playing: bool) -> None:
            self._card.set_many(
                artist=track["artist"],
                title=track["title"],
                album=track["album"],
                state="Playing" if is_playing else "Paused",
            )
            cover_path = self._pkg_dir / track["cover"]
            if cover_path.exists():
                self._card.set("cover", Image.open(cover_path))
            await self._card.request_refresh()

        @self._svc.on_volume_changed
        async def _on_volume(volume_level: float, volume_text: str) -> None:
            self._card.set_range(
                "volume", volume_level * 100, min_val=0, max_val=100
            )
            self._card.set("value_text", volume_text)
            await self._card.request_refresh()

    def _bind_dui_events(self) -> None:
        """Register DUI event handlers -- these only call service methods."""
        card = self._card

        @card.on("toggle_play_pause")
        async def _toggle() -> None:
            await self._svc.play_pause()

        @card.on("volume_up")
        async def _vol_up(steps: int) -> None:
            new = card.adjust_range("volume", steps, min_val=0, max_val=100)
            await self._svc.set_volume(new / 100.0)

        @card.on("volume_down")
        async def _vol_down(steps: int) -> None:
            new = card.adjust_range("volume", -abs(steps), min_val=0, max_val=100)
            await self._svc.set_volume(new / 100.0)

        @card.on("mute_toggle")
        async def _mute() -> None:
            await self._svc.toggle_mute()

        @card.on("next")
        async def _next(_steps: int) -> None:
            await self._svc.next_track()

        @card.on("previous")
        async def _prev(_steps: int) -> None:
            await self._svc.previous_track()


class LightsController:
    """Lights card -- on/off toggle, brightness, colour temperature.

    Loads ``LightCard.dui`` and binds:

    * encoder click       -> on/off toggle
    * encoder turn        -> brightness up/down (5 % per step)
    * encoder press+turn  -> kelvin up/down (100 K per step)

    Parameters
    ----------
    packages_dir : Path | None
        Directory containing ``LightCard.dui``.
    """

    def __init__(
        self,
        packages_dir: Path | None = None,
    ) -> None:
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(pkg_dir / "LightCard.dui"))

        # Read initial values from the .dui package defaults.
        # Slider defaults are normalised (0.0-1.0); denormalise to domain.
        bright_norm: float = self._card.get("brightness")
        kelvin_norm: float = self._card.get("kelvin")
        brightness = int(
            MockLightsService.BRIGHTNESS_MIN
            + bright_norm * (MockLightsService.BRIGHTNESS_MAX - MockLightsService.BRIGHTNESS_MIN)
        )
        kelvin = int(
            MockLightsService.KELVIN_MIN
            + kelvin_norm * (MockLightsService.KELVIN_MAX - MockLightsService.KELVIN_MIN)
        )
        self._svc = MockLightsService(
            is_on=self._card.get("lights"),
            brightness=brightness,
            kelvin=kelvin,
        )

        self._sync_card()
        self._subscribe_events()
        self._bind_dui_events()

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    @property
    def is_on(self) -> bool:
        """Whether lights are on."""
        return self._svc.is_on

    @property
    def brightness(self) -> int:
        """Current brightness percentage."""
        return self._svc.brightness

    @property
    def kelvin(self) -> int:
        """Current colour temperature in Kelvin."""
        return self._svc.kelvin

    def _sync_card(self) -> None:
        """Push the full light state into card bindings (initial load only)."""
        self._card.set("lights", self._svc.is_on)
        self._card.set("brightness_value_text", f"{self._svc.brightness}%")
        self._card.set_range(
            "brightness",
            self._svc.brightness,
            min_val=MockLightsService.BRIGHTNESS_MIN,
            max_val=MockLightsService.BRIGHTNESS_MAX,
        )
        self._card.set("kelvin_value_text", f"{self._svc.kelvin}K")
        self._card.set_range(
            "kelvin",
            self._svc.kelvin,
            min_val=MockLightsService.KELVIN_MIN,
            max_val=MockLightsService.KELVIN_MAX,
        )

    def _subscribe_events(self) -> None:
        """Subscribe to service state-change events."""

        @self._svc.on_toggled
        async def _on_toggled(is_on: bool) -> None:
            self._card.set("lights", is_on)
            await self._card.request_refresh()

        @self._svc.on_brightness_changed
        async def _on_brightness(brightness: int) -> None:
            self._card.set("brightness_value_text", f"{brightness}%")
            self._card.set_range(
                "brightness",
                brightness,
                min_val=MockLightsService.BRIGHTNESS_MIN,
                max_val=MockLightsService.BRIGHTNESS_MAX,
            )
            await self._card.request_refresh()

        @self._svc.on_kelvin_changed
        async def _on_kelvin(kelvin: int) -> None:
            self._card.set("kelvin_value_text", f"{kelvin}K")
            self._card.set_range(
                "kelvin",
                kelvin,
                min_val=MockLightsService.KELVIN_MIN,
                max_val=MockLightsService.KELVIN_MAX,
            )
            await self._card.request_refresh()

    def _bind_dui_events(self) -> None:
        """Register DUI event handlers -- these only call service methods."""

        @self._card.on("toggle")
        async def _toggle() -> None:
            await self._svc.toggle()

        @self._card.on("brightness_up")
        async def _bright_up(steps: int) -> None:
            await self._svc.set_brightness(self._svc.brightness + steps * 5)

        @self._card.on("brightness_down")
        async def _bright_down(steps: int) -> None:
            await self._svc.set_brightness(self._svc.brightness - abs(steps) * 5)

        @self._card.on("kelvin_up")
        async def _kelvin_up(steps: int) -> None:
            await self._svc.set_kelvin(self._svc.kelvin + steps * 100)

        @self._card.on("kelvin_down")
        async def _kelvin_down(steps: int) -> None:
            await self._svc.set_kelvin(self._svc.kelvin - abs(steps) * 100)


class TimerController:
    """Live countdown timer -- a real ticking timer driven by an asyncio task.

    Loads ``TimerCard.dui`` and reads the initial duration from the
    package's ``timer`` binding default value (e.g. ``"00:30:00"``),
    so the ``.dui`` manifest is the single source of truth for the
    starting time.

    Encoder bindings
    ~~~~~~~~~~~~~~~~
    * **encoder click** -- start / pause the countdown.
    * **encoder hold** -- reset to the current default duration.
    * **encoder turn** -- coarse adjustment: +/- 10 min per step
      (``increase_duration`` / ``decrease_duration``).
    * **encoder hold+turn** -- fine adjustment: +/- 30 s per step
      (``increase_duration_alt`` / ``decrease_duration_alt``).

    Default-duration semantics
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    Every time the timer is **started**, the value of ``remaining`` at
    that moment becomes the new default duration.  This means:

    * Adjust the time with the encoder, then press to start -- the
      adjusted value is now the default.
    * **Reset** (encoder hold) always returns to the most recent default.

    Use :meth:`start_runtime` once the deck is connected and
    :meth:`stop_runtime` to clean up on disconnect.

    Parameters
    ----------
    packages_dir : Path | None
        Directory containing ``TimerCard.dui``.
    """

    TICK_INTERVAL_S = 1.0
    FLASH_COUNT = 6
    FLASH_INTERVAL_S = 0.3

    def __init__(
        self,
        packages_dir: Path | None = None,
    ) -> None:
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(pkg_dir / "TimerCard.dui"))
        self._tick_task: asyncio.Task[None] | None = None

        # Read the initial duration from the .dui manifest's timer
        # binding default (e.g. "00:30:00") so the package is the
        # single source of truth.
        default_text: str = self._card.get("timer")
        initial_seconds = MockTimerService.parse_hhmmss(default_text)
        log.info("TimerCard default: %s (%d s)", default_text, initial_seconds)

        self._svc = MockTimerService(initial_seconds)

        # Read default colours from the manifest so the controller stays
        # in sync with the .dui package.
        self._default_background: str = self._card.get("background")
        self._default_foreground: str = self._card.get("foreground")

        self._subscribe_events()
        self._bind_dui_events()

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    @property
    def is_running(self) -> bool:
        """Whether the timer is currently counting down."""
        return self._svc.is_running

    @property
    def remaining(self) -> int:
        """Seconds remaining on the countdown."""
        return self._svc.remaining

    @property
    def duration(self) -> int:
        """Current configured duration in seconds."""
        return self._svc.duration

    @property
    def COARSE_STEP_S(self) -> int:  # noqa: N802
        """Seconds per coarse encoder-turn step."""
        return MockTimerService.COARSE_STEP_S

    @property
    def FINE_STEP_S(self) -> int:  # noqa: N802
        """Seconds per fine encoder-hold-turn step."""
        return MockTimerService.FINE_STEP_S

    def format_time(self) -> str:
        """Format ``remaining`` as ``HH:MM:SS``.

        Returns
        -------
        str
            Zero-padded ``HH:MM:SS`` string.
        """
        return self._svc.format_time()

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

    def _subscribe_events(self) -> None:
        """Subscribe to service state-change events."""

        @self._svc.on_timer_changed
        async def _on_timer(formatted_time: str) -> None:
            self._card.set("timer", formatted_time)
            await self._card.request_refresh()

        @self._svc.on_finished
        async def _on_finished() -> None:
            await self._flash_notification()

    def _bind_dui_events(self) -> None:
        """Register DUI event handlers -- these only call service methods.

        Events wired here correspond to the ``events`` section in the
        ``TimerCard.dui`` manifest:

        * ``toggle`` (encoder click) -- start / pause.
        * ``reset`` (encoder hold) -- reset to default.
        * ``increase_duration`` / ``decrease_duration`` (encoder turn)
          -- coarse adjustment, :attr:`MockTimerService.COARSE_STEP_S`
          per step.
        * ``increase_duration_alt`` / ``decrease_duration_alt``
          (encoder hold+turn) -- fine adjustment,
          :attr:`MockTimerService.FINE_STEP_S` per step.
        """

        @self._card.on("toggle")
        async def _toggle() -> None:
            await self._svc.toggle()

        @self._card.on("reset")
        async def _reset() -> None:
            await self._svc.reset()

        # -- coarse: encoder turn (no hold) -- +/- 10 min per step ---

        @self._card.on("increase_duration")
        async def _increase(steps: int) -> None:
            await self._svc.adjust_duration(steps * MockTimerService.COARSE_STEP_S)

        @self._card.on("decrease_duration")
        async def _decrease(steps: int) -> None:
            await self._svc.adjust_duration(-abs(steps) * MockTimerService.COARSE_STEP_S)

        # -- fine: encoder hold+turn -- +/- 30 s per step ------------

        @self._card.on("increase_duration_alt")
        async def _increase_alt(steps: int) -> None:
            await self._svc.adjust_duration(steps * MockTimerService.FINE_STEP_S)

        @self._card.on("decrease_duration_alt")
        async def _decrease_alt(steps: int) -> None:
            await self._svc.adjust_duration(-abs(steps) * MockTimerService.FINE_STEP_S)

    async def _flash_notification(self) -> None:
        """Flash foreground/background colors to signal timer completion.

        Swaps the foreground and background colors three times with a
        short interval, then restores the original colors.  This gives
        a visible pulse on the touch-strip card so the user knows the
        countdown has ended.
        """
        swapped = False
        for _ in range(self.FLASH_COUNT):
            swapped = not swapped
            if swapped:
                self._card.set_many(
                    background=self._default_foreground,
                    foreground=self._default_background,
                )
            else:
                self._card.set_many(
                    background=self._default_background,
                    foreground=self._default_foreground,
                )
            await self._card.request_refresh()
            await asyncio.sleep(self.FLASH_INTERVAL_S)

        # Ensure colors are restored to their original values.
        self._card.set_many(
            background=self._default_background,
            foreground=self._default_foreground,
        )
        await self._card.request_refresh()

    async def _tick_loop(self) -> None:
        """Call the service's tick once per second.

        The service emits ``on_timer_changed`` and ``on_finished``
        events as needed -- the controller's subscribers handle the
        card updates.
        """
        try:
            while True:
                await asyncio.sleep(self.TICK_INTERVAL_S)
                await self._svc.tick()
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
    packages_dir : Path | None
        Directory containing ``DashboardCard.dui``.
    """

    CLOCK_INTERVAL_S = 1.0

    def __init__(
        self,
        packages_dir: Path | None = None,
    ) -> None:
        self._deck: Any = None
        self._clock_task: asyncio.Task[None] | None = None

        pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(pkg_dir / "DashboardCard.dui"))

        # Read initial brightness from the .dui package's range binding
        # default (normalised 0.0-1.0) and convert to 0-100 domain.
        bright_norm: float = self._card.get("deck_brightness")
        deck_brightness = int(bright_norm * 100)
        self._svc = MockDashboardService(deck_brightness=deck_brightness)

        self._sync_card()
        self._subscribe_events()
        self._bind_dui_events()

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    @property
    def deck_brightness(self) -> int:
        """Current deck brightness percentage."""
        return self._svc.deck_brightness

    @property
    def temperature(self) -> str:
        """Current temperature reading."""
        return self._svc.temperature

    @property
    def humidity(self) -> str:
        """Current humidity reading."""
        return self._svc.humidity

    @staticmethod
    def get_date() -> str:
        """Return today's date as ``YYYY-MM-DD``."""
        return MockDashboardService.get_date()

    @staticmethod
    def get_time() -> str:
        """Return the current local time as ``HH:MM``."""
        return MockDashboardService.get_time()

    def bind_deck(self, deck: Any) -> None:
        """Attach the deck handle so brightness changes reach the hardware."""
        self._deck = deck

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
        """Push the full dashboard state into card bindings (initial load only)."""
        self._card.set_many(
            date=self._svc.get_date(),
            time=self._svc.get_time(),
            temperature=self._svc.temperature,
            humidity=self._svc.humidity,
        )
        self._card.set_range(
            "deck_brightness",
            self._svc.deck_brightness,
            min_val=0,
            max_val=100,
        )

    def _subscribe_events(self) -> None:
        """Subscribe to service state-change events."""

        @self._svc.on_brightness_changed
        async def _on_brightness(deck_brightness: int) -> None:
            self._card.set_range(
                "deck_brightness",
                deck_brightness,
                min_val=0,
                max_val=100,
            )
            if self._deck is not None:
                await self._deck.set_brightness(deck_brightness)
            await self._card.request_refresh()

    def _bind_dui_events(self) -> None:
        """Register DUI event handlers -- these only call service methods."""
        card = self._card

        @card.on("brightness_up")
        async def _bright_up(steps: int) -> None:
            new = card.adjust_range("deck_brightness", steps, min_val=0, max_val=100)
            await self._svc.set_brightness(int(new))

        @card.on("brightness_down")
        async def _bright_down(steps: int) -> None:
            new = card.adjust_range(
                "deck_brightness", -abs(steps), min_val=0, max_val=100
            )
            await self._svc.set_brightness(int(new))

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
                t = self._svc.get_time()
                d = self._svc.get_date()
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
    Clicking a key calls :meth:`MockAudioService.play` on the audio
    service.  The audio service emits ``on_track_changed`` which the
    :class:`AudioController` subscriber picks up to refresh the card.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries used as favourites.
    audio : AudioController
        The audio controller whose service handles playback.
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
        self._audio_svc = audio.svc
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
                await self._audio_svc.play(m)

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
            )

            # Bind handlers via a helper so each key captures its own
            # *key* reference instead of the loop variable.
            self._bind_handlers(key, scene["label"])
            self._keys.append(key)

    def _bind_handlers(self, key: DuiKey, label: str) -> None:
        """Attach press/release/click handlers to *key*.

        Splitting this into a helper guarantees correct closure capture
        for *key* and *label* per iteration.  The original background and
        foreground colours are read from the key's current bindings (set
        by the manifest defaults) so the controller stays in sync with
        the ``.dui`` package.

        Parameters
        ----------
        key : DuiKey
            The key to wire.
        label : str
            Scene label, logged on click.
        """
        bg = key.get("background")
        fg = key.get("foreground")

        @key.on_event("press")
        async def _press() -> None:
            # Invert colours by swapping background <-> foreground.
            key.set_many(background=fg, foreground=bg)
            await key.request_refresh()

        @key.on_event("release")
        async def _release() -> None:
            key.set_many(background=bg, foreground=fg)
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


class ScreenCycler:
    """Cycles the deck through a list of screens.

    Wires itself to a card event (the dashboard's ``next_screen`` event,
    emitted by an encoder press-release) and advances to the next screen
    on each trigger, wrapping around at the end.

    Demonstrates two ideas at once:

    * :meth:`Deck.set_screen` -- screens are independent layouts that
      swap atomically, so the same encoders/keys can host completely
      different functionality on each one.
    * Card-level events -- a ``.dui`` package can declare arbitrary
      events (here ``encoder_press_release`` named ``next_screen``) and
      controllers bind handlers to them, with no key required.

    Parameters
    ----------
    screens : list[str]
        Ordered screen names. The cycler starts on the first one and
        advances to the next on each trigger, wrapping around.

    Raises
    ------
    ValueError
        If *screens* is empty.
    """

    def __init__(self, screens: list[str]) -> None:
        if not screens:
            raise ValueError("ScreenCycler requires at least one screen")
        self._screens = list(screens)
        self._index = 0
        self._deck: Any = None

    @property
    def current(self) -> str:
        """Name of the screen the cycler currently points to."""
        return self._screens[self._index]

    def bind_deck(self, deck: Any) -> None:
        """Attach the deck so the controller can call ``set_screen``."""
        self._deck = deck

    def attach(self, card: DuiCard, event: str = "next_screen") -> None:
        """Register the cycler on *card*'s *event*.

        Parameters
        ----------
        card : DuiCard
            Card whose event will trigger screen changes (typically the
            dashboard card).
        event : str, default="next_screen"
            Name of the event declared in the card's manifest.
        """

        @card.on(event)
        async def _trigger() -> None:
            await self.advance()

    async def advance(self) -> None:
        """Move to the next screen, wrapping at the end."""
        if self._deck is None:
            return
        self._index = (self._index + 1) % len(self._screens)
        target = self._screens[self._index]
        log.info("Cycling to screen: %s", target)
        await self._deck.set_screen(target)


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
            catalog, packages_dir=self._packages_dir
        )
        self.lights = LightsController(
            packages_dir=self._packages_dir
        )
        self.timer = TimerController(
            packages_dir=self._packages_dir
        )
        self.dashboard = DashboardController(
            packages_dir=self._packages_dir
        )
        self.favorites = FavoritesController(
            catalog, self.audio, packages_dir=self._packages_dir
        )
        self.scenes = SceneController(
            scene_defs, packages_dir=self._packages_dir
        )
        # Cycle "main" -> "settings" -> back via the dashboard encoder
        # press-release (the manifest declares it as ``next_screen``).
        self.nav = ScreenCycler(["main", "settings"])
        self.nav.attach(self.dashboard.card)

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

        # Favourites first, then scenes -- using every available key.
        # Screen cycling is driven by the dashboard encoder, so no
        # navigation key is needed.
        num_favs = min(len(self.favorites.keys), caps.key_count)
        remaining = max(0, caps.key_count - num_favs)
        num_scenes = min(len(self.scenes.keys), remaining)

        self.favorites.install(screen, list(range(num_favs)))
        self.scenes.install(screen, list(range(num_favs, num_favs + num_scenes)))

    def _build_settings_screen(self, deck: Any) -> None:
        """Layout: focused settings view -- dashboard + lights cards only.

        Demonstrates that the same controllers can appear on multiple
        screens -- DeckUI does not care, it simply renders whatever's
        installed when the screen is active. The dashboard card is
        reused here so the user can keep cycling screens with its
        encoder press-release.

        Parameters
        ----------
        deck
            Open deck handle.
        """
        screen = deck.screen("settings")
        caps = deck.capabilities

        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#1c1c1c"
            pkg_dir = self._packages_dir or EXAMPLES_DIR
            iconkey_spec = load_package(pkg_dir / "IconKey.dui")
            for key_index in range(caps.key_count):
                key = DuiKey(iconkey_spec)
                key.set("label","Unassigned")
                screen.set_key(key_index, key)

            #caps.key_count
            # Keep the dashboard in the same slot on every screen so the
            # encoder used to cycle screens is always the rightmost one.
            #screen.set_card(0, self.lights.card)
            screen.set_card(3, self.dashboard.card)


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
    manager = DeckManager(
        brightness=app.dashboard.deck_brightness, auto_reconnect=True
    )

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
