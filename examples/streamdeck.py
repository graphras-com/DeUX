#!/usr/bin/env python3
"""Stream Deck demo -- a complete walkthrough of the DeckUI library.

This single-file example showcases every major DeckUI concept against
any connected Stream Deck.  It is designed to read top-to-bottom as a
tutorial -- each section introduces one feature.

Domain logic (audio playback, smart lights, timer countdown, dashboard
telemetry, scene activation) lives in :mod:`mock_backend` so this file
focuses purely on DeckUI wiring.  Swap those mock services for real
integrations and the code below stays the same.

**Event-driven architecture**
-----------------------------

Every controller follows the same one-way data flow:

    DUI / device input  --->  service.method(...)
                                   |
                                   v
                         service emits change event
                                   |
                                   v
                         controller subscriber
                                   |
                                   v
                         card.set(...) + request_refresh()

DUI event handlers in this file **never** mutate card bindings
directly.  They only call service methods.  The service updates its
state and fires an async event with the *new value in domain units*;
the controller's subscriber is the single place that translates a
domain value into UI bindings (formatting, normalisation, etc.).

The same rule applies to deck-owned state:
:meth:`deckui.Deck.set_brightness` and :meth:`deckui.Deck.set_screen`
each emit an event, so brightness/screen UI updates only reflect
*confirmed* hardware/screen state.

What it demonstrates
--------------------
* :class:`~deckui.DeckManager` for auto-discovery and hot-plug.
* :class:`~deckui.AsyncEvent` as the property-change-notification
  primitive both for backend services and for ``Deck`` itself.
* Loading ``.dui`` packages via :func:`~deckui.load_package` and using
  :class:`~deckui.DuiCard` / :class:`~deckui.DuiKey`.
* Triggering re-renders from background tasks via
  :meth:`~deckui.DuiCard.request_refresh`.
* A live, asyncio-driven countdown ``TimerCard`` and a dashboard clock
  that ticks every second; weather telemetry pushed by a simulator.
* Multi-screen navigation -- a ``main`` screen and a ``settings``
  screen, cycled by an encoder press-release on the dashboard card.

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

from mock_backend import (
    MEDIA_CATALOG,
    SCENE_DEFS,
    MockAudioService,
    MockDashboardService,
    MockLightsService,
    MockScenesService,
    MockTimerService,
)
from PIL import Image

from deckui import Deck, DeckManager, DeviceInfo, DuiCard, DuiKey, load_package

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Resolve the directory holding the .dui packages and image assets used
# below.  Adjust if you move them elsewhere.
EXAMPLES_DIR = Path(__file__).resolve().parent


# ===========================================================================
# Controllers
# ===========================================================================


class AudioController:
    """Audio player card -- play/pause, mute, volume, track navigation.

    Loads ``AudioCard.dui`` and binds encoder events:

    * encoder hold       -> toggle play/pause
    * encoder turn       -> volume up/down
    * encoder click      -> mute toggle
    * encoder press+turn -> previous/next track

    All UI updates flow through the service's ``on_*`` events; DUI
    handlers only call service methods.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries with ``artist``, ``album``, ``title``, ``cover``.
    packages_dir : Path | None
        Directory containing ``AudioCard.dui``.  Defaults to ``examples/``.
    """

    VOLUME_MIN = 0
    VOLUME_MAX = 100

    def __init__(
        self,
        catalog: list[dict[str, str]],
        packages_dir: Path | None = None,
    ) -> None:
        self._pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(self._pkg_dir / "AudioCard.dui"))

        # The .dui range default (0.0-1.0) is the source of truth for
        # the initial volume.  Convert to domain percent and pass to
        # the service.
        initial_volume = int(
            round(self._card.get_range("volume", min_val=0, max_val=100))
        )
        self._svc = MockAudioService(catalog, initial_volume=initial_volume)

        self._subscribe_events()
        self._bind_dui_events()
        self._initialize_bindings()

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
    def volume(self) -> int:
        """Current volume in percent (0-100)."""
        return self._svc.volume

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

    # -- presentation helpers ------------------------------------------
    #
    # These are the *only* places that translate domain state into
    # card bindings.  Subscribers and the initial-binding routine both
    # call them, so there is one source of truth for "service state ->
    # bindings".

    def _apply_track(self, track: dict[str, str], is_playing: bool) -> None:
        self._card.set_many(
            artist=track["artist"],
            title=track["title"],
            album=track["album"],
            state="Playing" if is_playing else "Paused",
        )
        cover_path = self._pkg_dir / track["cover"]
        if cover_path.exists():
            self._card.set("cover", Image.open(cover_path))

    def _apply_volume(self, volume: int) -> None:
        self._card.set_range(
            "volume", volume, min_val=self.VOLUME_MIN, max_val=self.VOLUME_MAX
        )
        if not self._svc.is_muted:
            self._card.set("value_text", f"{volume}%")

    def _apply_mute(self, is_muted: bool) -> None:
        if is_muted:
            self._card.set("value_text", "Muted")
        else:
            self._card.set("value_text", f"{self._svc.volume}%")

    # -- internal -------------------------------------------------------

    def _initialize_bindings(self) -> None:
        """Populate the card from current service state.

        Called once during construction.  The deck's first
        :meth:`~deckui.Deck.set_screen` performs the actual render, so
        no ``request_refresh`` is needed here.
        """
        self._apply_track(self._svc.current_track, self._svc.is_playing)
        self._apply_volume(self._svc.volume)
        self._apply_mute(self._svc.is_muted)

    def _subscribe_events(self) -> None:
        """Subscribe to service state-change events."""

        @self._svc.on_track_changed
        async def _on_track(track: dict[str, str], is_playing: bool) -> None:
            self._apply_track(track, is_playing)
            await self._card.request_refresh()

        @self._svc.on_volume_changed
        async def _on_volume(volume: int) -> None:
            self._apply_volume(volume)
            await self._card.request_refresh()

        @self._svc.on_mute_changed
        async def _on_mute(is_muted: bool) -> None:
            self._apply_mute(is_muted)
            await self._card.request_refresh()

    def _bind_dui_events(self) -> None:
        """Register DUI event handlers -- these only call service methods."""
        card = self._card

        @card.on("toggle_play_pause")
        async def _toggle() -> None:
            await self._svc.play_pause()

        @card.on("volume_up")
        async def _vol_up(steps: int) -> None:
            await self._svc.set_volume(self._svc.volume + steps)

        @card.on("volume_down")
        async def _vol_down(steps: int) -> None:
            await self._svc.set_volume(self._svc.volume - abs(steps))

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

    Display ranges live on the controller because they are UI choices
    (a real Hue bridge clamps differently to the physical LEDs).

    Parameters
    ----------
    packages_dir : Path | None
        Directory containing ``LightCard.dui``.
    """

    BRIGHTNESS_MIN = 0
    BRIGHTNESS_MAX = 100
    KELVIN_MIN = 2000
    KELVIN_MAX = 6500
    BRIGHTNESS_STEP = 5
    KELVIN_STEP = 100

    def __init__(
        self,
        packages_dir: Path | None = None,
    ) -> None:
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(pkg_dir / "LightCard.dui"))

        # The card defaults are the source of truth for the initial
        # service state, mirroring the "backend bootstraps from device
        # last-known values" pattern of a real integration.
        initial_brightness = int(
            round(
                self._card.get_range(
                    "brightness",
                    min_val=self.BRIGHTNESS_MIN,
                    max_val=self.BRIGHTNESS_MAX,
                )
            )
        )
        initial_kelvin = int(
            round(
                self._card.get_range(
                    "kelvin", min_val=self.KELVIN_MIN, max_val=self.KELVIN_MAX
                )
            )
        )
        self._svc = MockLightsService(
            is_on=self._card.get("lights"),
            brightness=initial_brightness,
            kelvin=initial_kelvin,
        )

        self._subscribe_events()
        self._bind_dui_events()
        self._initialize_bindings()

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

    # -- presentation helpers ------------------------------------------

    def _apply_toggle(self, is_on: bool) -> None:
        self._card.set("lights", is_on)

    def _apply_brightness(self, brightness: int) -> None:
        self._card.set("brightness_value_text", f"{brightness}%")
        self._card.set_range(
            "brightness",
            brightness,
            min_val=self.BRIGHTNESS_MIN,
            max_val=self.BRIGHTNESS_MAX,
        )

    def _apply_kelvin(self, kelvin: int) -> None:
        self._card.set("kelvin_value_text", f"{kelvin}K")
        self._card.set_range(
            "kelvin", kelvin, min_val=self.KELVIN_MIN, max_val=self.KELVIN_MAX
        )

    # -- internal -------------------------------------------------------

    def _initialize_bindings(self) -> None:
        self._apply_toggle(self._svc.is_on)
        self._apply_brightness(self._svc.brightness)
        self._apply_kelvin(self._svc.kelvin)

    def _subscribe_events(self) -> None:
        """Subscribe to service state-change events."""

        @self._svc.on_toggled
        async def _on_toggled(is_on: bool) -> None:
            self._apply_toggle(is_on)
            await self._card.request_refresh()

        @self._svc.on_brightness_changed
        async def _on_brightness(brightness: int) -> None:
            self._apply_brightness(brightness)
            await self._card.request_refresh()

        @self._svc.on_kelvin_changed
        async def _on_kelvin(kelvin: int) -> None:
            self._apply_kelvin(kelvin)
            await self._card.request_refresh()

    def _bind_dui_events(self) -> None:
        """Register DUI event handlers -- these only call service methods."""

        @self._card.on("toggle")
        async def _toggle() -> None:
            await self._svc.toggle()

        @self._card.on("brightness_up")
        async def _bright_up(steps: int) -> None:
            await self._svc.set_brightness(
                self._svc.brightness + steps * self.BRIGHTNESS_STEP
            )

        @self._card.on("brightness_down")
        async def _bright_down(steps: int) -> None:
            await self._svc.set_brightness(
                self._svc.brightness - abs(steps) * self.BRIGHTNESS_STEP
            )

        @self._card.on("kelvin_up")
        async def _kelvin_up(steps: int) -> None:
            await self._svc.set_kelvin(
                self._svc.kelvin + steps * self.KELVIN_STEP
            )

        @self._card.on("kelvin_down")
        async def _kelvin_down(steps: int) -> None:
            await self._svc.set_kelvin(
                self._svc.kelvin - abs(steps) * self.KELVIN_STEP
            )


class TimerController:
    """Live countdown timer -- a real ticking timer driven by an asyncio task.

    Loads ``TimerCard.dui`` and reads the initial duration from the
    package's ``timer`` binding default (e.g. ``"00:30:00"``), so the
    ``.dui`` manifest is the single source of truth for the starting
    time.

    Encoder bindings
    ~~~~~~~~~~~~~~~~
    * **encoder click** -- start / pause the countdown.
    * **encoder hold** -- reset to the current default duration.
    * **encoder turn** -- coarse adjustment: +/- 10 min per step.
    * **encoder hold+turn** -- fine adjustment: +/- 30 s per step.

    Format conversion (``int seconds`` <-> ``"HH:MM:SS"``) is the
    controller's responsibility -- the service deals only in seconds.

    Parameters
    ----------
    packages_dir : Path | None
        Directory containing ``TimerCard.dui``.
    """

    TICK_INTERVAL_S = 1.0
    FLASH_COUNT = 6
    FLASH_INTERVAL_S = 0.3
    COARSE_STEP_S = 600
    """Seconds added/removed per encoder-turn step (no hold) -- 10 minutes."""
    FINE_STEP_S = 30
    """Seconds added/removed per encoder-hold-turn step -- 30 seconds."""

    def __init__(
        self,
        packages_dir: Path | None = None,
    ) -> None:
        pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(pkg_dir / "TimerCard.dui"))
        self._tick_task: asyncio.Task[None] | None = None

        default_text: str = self._card.get("timer")
        initial_seconds = self._parse_hhmmss(default_text)
        log.info(
            "TimerCard default: %s (%d s)", default_text, initial_seconds
        )

        self._svc = MockTimerService(initial_seconds)

        self._default_background: str = self._card.get("background")
        self._default_foreground: str = self._card.get("foreground")

        self._subscribe_events()
        self._bind_dui_events()
        self._initialize_bindings()

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

    @staticmethod
    def _parse_hhmmss(text: str) -> int:
        """Parse ``HH:MM:SS`` into seconds.  Controller-side helper.

        Parameters
        ----------
        text : str
            Time string in ``HH:MM:SS`` format.

        Returns
        -------
        int
            Total number of seconds.

        Raises
        ------
        ValueError
            If *text* does not match the expected format.
        """
        parts = text.strip().split(":")
        if len(parts) != 3:
            raise ValueError(f"Expected HH:MM:SS, got {text!r}")
        hours, minutes, seconds = (int(p) for p in parts)
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _format_hhmmss(seconds: int) -> str:
        """Format seconds as ``HH:MM:SS``.  Controller-side helper.

        Parameters
        ----------
        seconds : int
            Number of seconds (negative values are treated as zero).

        Returns
        -------
        str
            Zero-padded ``HH:MM:SS`` string.
        """
        h, rem = divmod(max(0, seconds), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def format_time(self) -> str:
        """Format the service's current ``remaining`` as ``HH:MM:SS``.

        Returns
        -------
        str
            Zero-padded ``HH:MM:SS`` string.
        """
        return self._format_hhmmss(self._svc.remaining)

    async def start_runtime(self) -> None:
        """Start the background tick task (idempotent)."""
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

    # -- presentation helpers ------------------------------------------

    def _apply_remaining(self, remaining: int) -> None:
        self._card.set("timer", self._format_hhmmss(remaining))

    # -- internal -------------------------------------------------------

    def _initialize_bindings(self) -> None:
        self._apply_remaining(self._svc.remaining)

    def _subscribe_events(self) -> None:
        """Subscribe to service state-change events."""

        @self._svc.on_remaining_changed
        async def _on_remaining(remaining: int) -> None:
            self._apply_remaining(remaining)
            await self._card.request_refresh()

        @self._svc.on_finished
        async def _on_finished() -> None:
            await self._flash_notification()

    def _bind_dui_events(self) -> None:
        """Register DUI event handlers -- these only call service methods."""

        @self._card.on("toggle")
        async def _toggle() -> None:
            await self._svc.toggle()

        @self._card.on("reset")
        async def _reset() -> None:
            await self._svc.reset()

        @self._card.on("increase_duration")
        async def _increase(steps: int) -> None:
            await self._svc.adjust_duration(steps * self.COARSE_STEP_S)

        @self._card.on("decrease_duration")
        async def _decrease(steps: int) -> None:
            await self._svc.adjust_duration(
                -abs(steps) * self.COARSE_STEP_S
            )

        @self._card.on("increase_duration_alt")
        async def _increase_alt(steps: int) -> None:
            await self._svc.adjust_duration(steps * self.FINE_STEP_S)

        @self._card.on("decrease_duration_alt")
        async def _decrease_alt(steps: int) -> None:
            await self._svc.adjust_duration(-abs(steps) * self.FINE_STEP_S)

    async def _flash_notification(self) -> None:
        """Flash foreground/background colors when the countdown ends.

        This is pure UI animation -- not a backend state transition --
        so the controller drives the card directly.
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

        self._card.set_many(
            background=self._default_background,
            foreground=self._default_foreground,
        )
        await self._card.request_refresh()

    async def _tick_loop(self) -> None:
        """Drive the service tick once per second."""
        try:
            while True:
                await asyncio.sleep(self.TICK_INTERVAL_S)
                await self._svc.tick()
        except asyncio.CancelledError:
            pass


class DashboardController:
    """Dashboard card -- live clock, simulated weather, deck-brightness.

    Loads ``DashboardCard.dui``.  Brightness is **deck-owned** state:
    the controller does not store a brightness value of its own.  It
    subscribes to :attr:`deckui.Deck.on_brightness_changed` and
    delegates writes to :meth:`deckui.Deck.set_brightness`.  Telemetry
    arrives via :attr:`MockDashboardService.on_telemetry_changed`.  The
    clock is genuinely poll-driven (system time), so a small task ticks
    once a second.

    Parameters
    ----------
    packages_dir : Path | None
        Directory containing ``DashboardCard.dui``.
    """

    CLOCK_INTERVAL_S = 1.0
    BRIGHTNESS_MIN = 0
    BRIGHTNESS_MAX = 100
    BRIGHTNESS_STEP = 1

    def __init__(
        self,
        packages_dir: Path | None = None,
    ) -> None:
        self._deck: Deck | None = None
        self._clock_task: asyncio.Task[None] | None = None

        pkg_dir = packages_dir or EXAMPLES_DIR
        self._card = DuiCard(load_package(pkg_dir / "DashboardCard.dui"))

        # Manifest brightness default (normalised) is the cold-start
        # value; remembered across reconnects so the user's last value
        # survives ``Deck.start`` resetting hardware to the manager's
        # startup default.
        self._last_known_brightness: int = int(
            round(
                self._card.get_range(
                    "deck_brightness",
                    min_val=self.BRIGHTNESS_MIN,
                    max_val=self.BRIGHTNESS_MAX,
                )
            )
        )

        self._svc = MockDashboardService()

        self._subscribe_telemetry()
        self._bind_dui_events()
        self._initialize_bindings()

    @property
    def card(self) -> DuiCard:
        """The :class:`DuiCard` ready to install on a screen."""
        return self._card

    @property
    def deck_brightness(self) -> int:
        """Last confirmed deck brightness (0 -- 100)."""
        return self._last_known_brightness

    @property
    def temperature_c(self) -> float:
        """Current temperature reading in degrees Celsius."""
        return self._svc.temperature_c

    @property
    def humidity_pct(self) -> int:
        """Current humidity reading in percent."""
        return self._svc.humidity_pct

    @staticmethod
    def get_date() -> str:
        """Return today's date as ``YYYY-MM-DD``."""
        return datetime.datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_time() -> str:
        """Return the current local time as ``HH:MM``."""
        return datetime.datetime.now().strftime("%H:%M")

    async def bind_deck(self, deck: Deck) -> None:
        """Attach to *deck*: subscribe to brightness events and replay.

        Subscribes to :attr:`Deck.on_brightness_changed` so the slider
        reflects confirmed hardware state.  Also replays the last-known
        brightness onto the new deck instance so the user's value
        survives a disconnect/reconnect (``Deck.start`` resets the
        hardware to the manager's startup default).

        Parameters
        ----------
        deck
            The connected :class:`~deckui.Deck` instance.
        """
        self._deck = deck

        @deck.on_brightness_changed
        async def _on_brightness(value: int) -> None:
            self._last_known_brightness = value
            self._apply_brightness(value)
            await self._card.request_refresh()

        # Replay the user's last value onto the freshly-connected deck.
        # Idempotent -- if values match, the deck silently returns.
        await deck.set_brightness(self._last_known_brightness)

    async def start_runtime(self) -> None:
        """Start the clock tick and the telemetry simulator (idempotent)."""
        if self._clock_task is None or self._clock_task.done():
            self._clock_task = asyncio.create_task(
                self._clock_loop(), name="dashboard-clock"
            )
        await self._svc.start()

    async def stop_runtime(self) -> None:
        """Cancel the clock tick and stop the telemetry simulator."""
        task = self._clock_task
        self._clock_task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._svc.stop()

    # -- presentation helpers ------------------------------------------

    def _apply_brightness(self, brightness: int) -> None:
        self._card.set_range(
            "deck_brightness",
            brightness,
            min_val=self.BRIGHTNESS_MIN,
            max_val=self.BRIGHTNESS_MAX,
        )

    def _apply_telemetry(
        self, temperature_c: float, humidity_pct: int
    ) -> None:
        self._card.set_many(
            temperature=f"{temperature_c:.1f}C",
            humidity=f"{humidity_pct}%",
        )

    def _apply_clock(self) -> None:
        self._card.set_many(date=self.get_date(), time=self.get_time())

    # -- internal -------------------------------------------------------

    def _initialize_bindings(self) -> None:
        self._apply_brightness(self._last_known_brightness)
        self._apply_telemetry(self._svc.temperature_c, self._svc.humidity_pct)
        self._apply_clock()

    def _subscribe_telemetry(self) -> None:
        @self._svc.on_telemetry_changed
        async def _on_telemetry(temperature_c: float, humidity_pct: int) -> None:
            self._apply_telemetry(temperature_c, humidity_pct)
            await self._card.request_refresh()

    def _bind_dui_events(self) -> None:
        """Register DUI event handlers -- these only call deck methods."""

        @self._card.on("brightness_up")
        async def _bright_up(steps: int) -> None:
            if self._deck is None:
                return
            await self._deck.set_brightness(
                self._deck.brightness + steps * self.BRIGHTNESS_STEP
            )

        @self._card.on("brightness_down")
        async def _bright_down(steps: int) -> None:
            if self._deck is None:
                return
            await self._deck.set_brightness(
                self._deck.brightness - abs(steps) * self.BRIGHTNESS_STEP
            )

    async def _clock_loop(self) -> None:
        """Refresh the clock display every second.

        Only marks the card dirty when the visible value actually
        changes.
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

    Clicking a favourite calls :meth:`MockAudioService.play`.  The
    audio service then emits ``on_track_changed``; the
    :class:`AudioController` subscriber refreshes the audio card.

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
                log.info(
                    "Favourite pressed: %s -- %s", m["artist"], m["title"]
                )
                await self._audio_svc.play(m)

            self._keys.append(key)

    @property
    def keys(self) -> list[DuiKey]:
        """The created favourite keys (same order as *catalog*)."""
        return list(self._keys)

    def install(self, screen: Any, positions: list[int]) -> None:
        """Place favourite keys onto *screen* at the given *positions*."""
        for pos, key in zip(positions, self._keys, strict=False):
            screen.set_key(pos, key)


class SceneController:
    """Scene-activation keys -- one :class:`DuiKey` per scene definition.

    Click handlers call :meth:`MockScenesService.activate`.  The
    service emits ``on_scene_activated``; the controller's subscriber
    logs and (in a real app) would update an "active scene" indicator.

    The press/release colour-swap is **input feedback** for a confirmed
    device input event -- not a state transition -- so it lives in the
    key handler.  Same pattern as a button changing colour while held.

    Parameters
    ----------
    scenes : list[dict[str, str]]
        Scene definitions, each with ``label`` and ``icon``.
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
        self._svc = MockScenesService()
        self._keys: list[DuiKey] = []

        self._subscribe_events()

        for scene in self._scenes:
            key = DuiKey(self._spec)
            key.set_many(
                label=scene["label"],
                icon=scene["icon"],
            )
            self._bind_handlers(key, scene["label"])
            self._keys.append(key)

    @property
    def keys(self) -> list[DuiKey]:
        """The created scene keys (same order as *scenes*)."""
        return list(self._keys)

    @property
    def svc(self) -> MockScenesService:
        """The underlying scenes service."""
        return self._svc

    def install(self, screen: Any, positions: list[int]) -> None:
        """Place scene keys onto *screen* at the given *positions*."""
        for pos, key in zip(positions, self._keys, strict=False):
            screen.set_key(pos, key)

    def _subscribe_events(self) -> None:
        @self._svc.on_scene_activated
        async def _on_activated(label: str) -> None:
            log.info("Scene confirmed active: %s", label)

    def _bind_handlers(self, key: DuiKey, label: str) -> None:
        """Attach press/release/click handlers to *key*.

        Press/release swap fg<->bg as visual input feedback.  Click
        delegates to the scenes service.

        Parameters
        ----------
        key : DuiKey
            The key to wire.
        label : str
            Scene label, passed to the service on click.
        """
        bg = key.get("background")
        fg = key.get("foreground")

        @key.on_event("press")
        async def _press() -> None:
            key.set_many(background=fg, foreground=bg)
            await key.request_refresh()

        @key.on_event("release")
        async def _release() -> None:
            key.set_many(background=bg, foreground=fg)
            await key.request_refresh()

        @key.on_event("click")
        async def _click() -> None:
            await self._svc.activate(label)


class ScreenCycler:
    """Cycles the deck through a list of screens.

    Wires itself to a card event (the dashboard's ``next_screen`` event,
    emitted by an encoder press-release) and advances to the next
    screen on each trigger, wrapping around at the end.

    Source of truth for the *current* screen is
    :attr:`deckui.Deck.active_screen` -- the cycler does not maintain
    its own active-screen state.  It does remember the **last-cycled
    screen name** so that on reconnect the app can resume on the
    user's last choice.

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
        self._last_known: str = self._screens[0]
        self._deck: Deck | None = None

    @property
    def current(self) -> str:
        """Last-known active screen name.

        Reflects the most recent ``Deck.on_screen_changed`` event,
        falling back to the first configured screen before any change
        has been observed.
        """
        return self._last_known

    def bind_deck(self, deck: Deck) -> None:
        """Attach to *deck* and subscribe to its screen-changed event."""
        self._deck = deck

        @deck.on_screen_changed
        async def _on_screen(name: str) -> None:
            self._last_known = name

    def attach(self, card: DuiCard, event: str = "next_screen") -> None:
        """Register the cycler on *card*'s *event*.

        Parameters
        ----------
        card : DuiCard
            Card whose event triggers screen changes.
        event : str, default="next_screen"
            Event name declared in the card's manifest.
        """

        @card.on(event)
        async def _trigger() -> None:
            await self.advance()

    async def advance(self) -> None:
        """Move to the next screen, wrapping at the end."""
        if self._deck is None:
            return
        idx = self._screens.index(self._last_known)
        target = self._screens[(idx + 1) % len(self._screens)]
        log.info("Cycling to screen: %s", target)
        await self._deck.set_screen(target)


# ===========================================================================
# Application
# ===========================================================================


class StreamDeckApp:
    """Top-level demo app -- glues controllers to the deck.

    Build the controllers once.  :meth:`on_connect` is called from the
    manager's ``on_connect`` callback to install controllers on the
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
        self.audio = AudioController(catalog, packages_dir=self._packages_dir)
        self.lights = LightsController(packages_dir=self._packages_dir)
        self.timer = TimerController(packages_dir=self._packages_dir)
        self.dashboard = DashboardController(packages_dir=self._packages_dir)
        self.favorites = FavoritesController(
            catalog, self.audio, packages_dir=self._packages_dir
        )
        self.scenes = SceneController(
            scene_defs, packages_dir=self._packages_dir
        )
        self.nav = ScreenCycler(["main", "settings"])
        self.nav.attach(self.dashboard.card)

    async def on_connect(self, deck: Deck) -> None:
        """Configure screens for *deck* and start (or resume) the demo.

        Called on first connect and again on every reconnect when
        :class:`DeckManager` has ``auto_reconnect=True``.

        Parameters
        ----------
        deck
            The :class:`~deckui.runtime.deck.Deck` handle.
        """
        caps = deck.capabilities
        log.info(
            "Deck connected: %s (%d keys, %d encoders, touchscreen=%s)",
            caps.deck_type,
            caps.key_count,
            caps.dial_count,
            "yes" if caps.has_touchscreen else "no",
        )

        # Demonstrate Deck.on_screen_changed: log every screen switch.
        @deck.on_screen_changed
        async def _log_screen(name: str) -> None:
            log.info("Active screen confirmed: %s", name)

        # Hand the deck to controllers that need it.  bind_deck on the
        # dashboard subscribes to brightness events and replays the
        # last-known value -- this is what survives reconnect.
        await self.dashboard.bind_deck(deck)
        self.nav.bind_deck(deck)

        self._build_main_screen(deck)
        self._build_settings_screen(deck)

        # Resume on the user's last screen (cold start: first screen
        # in the cycler -- "main").  set_screen wires every key/card's
        # request_refresh() to deck.refresh() under the hood.
        await deck.set_screen(self.nav.current)

        # Background tasks AFTER the screen is active so their
        # request_refresh() calls go to the right place.
        await self.timer.start_runtime()
        await self.dashboard.start_runtime()

        log.info(
            "Deck ready -- try the encoders, keys, "
            "and press the dashboard encoder to switch screens!"
        )

    async def on_disconnect(self, info: DeviceInfo) -> None:
        """Stop background tasks when the deck goes away."""
        log.warning(
            "Deck disconnected: %s -- waiting for reconnect...", info.serial
        )
        await self.timer.stop_runtime()
        await self.dashboard.stop_runtime()

    # -- screen construction -------------------------------------------

    def _build_main_screen(self, deck: Deck) -> None:
        """Layout: favourites + scenes on keys, all four cards on the strip."""
        caps = deck.capabilities
        screen = deck.screen("main")

        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#1c1c1c"
            screen.set_card(0, self.audio.card)
            screen.set_card(1, self.lights.card)
            screen.set_card(2, self.timer.card)
            screen.set_card(3, self.dashboard.card)

        num_favs = min(len(self.favorites.keys), caps.key_count)
        remaining = max(0, caps.key_count - num_favs)
        num_scenes = min(len(self.scenes.keys), remaining)

        self.favorites.install(screen, list(range(num_favs)))
        self.scenes.install(
            screen, list(range(num_favs, num_favs + num_scenes))
        )

    def _build_settings_screen(self, deck: Deck) -> None:
        """Layout: dashboard pinned, otherwise template ``IconKey``s."""
        screen = deck.screen("settings")
        caps = deck.capabilities

        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#1c1c1c"
            screen.set_card(3, self.dashboard.card)

        pkg_dir = self._packages_dir or EXAMPLES_DIR
        iconkey_spec = load_package(pkg_dir / "IconKey.dui")
        for key_index in range(caps.key_count):
            key = DuiKey(iconkey_spec)
            key.set("label", "Unassigned")
            screen.set_key(key_index, key)


# ===========================================================================
# Entry point
# ===========================================================================


async def run() -> None:
    """Build the app, attach to :class:`DeckManager`, and run forever.

    1. Construct controllers.
    2. Create a :class:`DeckManager` with the cold-start brightness.
    3. Register ``on_connect`` / ``on_disconnect`` handlers.
    4. ``async with`` the manager and ``await manager.wait_closed()``.
    """
    app = StreamDeckApp(MEDIA_CATALOG, SCENE_DEFS)
    manager = DeckManager(
        brightness=app.dashboard.deck_brightness, auto_reconnect=True
    )

    @manager.on_connect()
    async def _on_connect(deck: Deck) -> None:
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
