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

Every controller follows the same one-way data flow::

    DUI / device input
            |
            v   card.forward(event_name, svc.method)
    service.method(...)
            |
            v
    service emits typed change event
            |
            v   card.bind / bind_range / bind_many
    card binding updated, refresh requested

DUI handlers in this file **never** mutate card bindings directly --
they forward the input to a service method via
:meth:`~deckui.DuiCard.forward`.  The service updates its state and
emits a typed event with the new value in *domain units*.  Reactive
bindings registered with :meth:`~deckui.DuiCard.bind`,
:meth:`~deckui.DuiCard.bind_range`, and :meth:`~deckui.DuiCard.bind_many`
translate domain values into card bindings and request a refresh
automatically.

The same pattern applies to deck-owned state: brightness flows through
``deck.set_brightness`` -> ``deck.on_brightness_changed`` -> the
controller's :meth:`bind_range`, so the slider reflects *confirmed*
hardware state.

What it demonstrates
--------------------
* :class:`~deckui.DeckManager` for auto-discovery and hot-plug.
* :class:`~deckui.AsyncEvent` as the property-change-notification
  primitive both for backend services and for ``Deck`` itself.
* Name-based DUI package resolution via the DUI repository.
  ``DuiCard("AudioCard")`` and ``DuiKey("IconKey")`` resolve packages
  from registered search paths — no manual ``load_package`` calls.
* :class:`~deckui.CardController` lifecycle hooks (:meth:`on_attach` /
  :meth:`on_detach`) and reactive ``bind``/``forward`` wiring.
* Triggering re-renders from background tasks via
  :meth:`~deckui.DuiCard.request_refresh`.
* A live, asyncio-driven countdown ``TimerCard`` and a dashboard clock
  that ticks every second; weather telemetry pushed by a simulator.
* Multi-screen navigation -- a ``Main`` screen and a ``Settings``
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
    MockGaugeService,
    MockLightsService,
    MockScenesService,
    MockTimerService,
)
from PIL import Image

from deckui import (
    CardController,
    Deck,
    DeckManager,
    DeviceInfo,
    DuiCard,
    DuiKey,
    add_dui_path,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Resolve the directory holding example-specific .dui packages and image
# assets.  Register it with the DUI repository so packages can be resolved
# by name (e.g. ``DuiCard("AudioCard")``).
EXAMPLES_DIR = Path(__file__).resolve().parent
add_dui_path(EXAMPLES_DIR)

# ===========================================================================
# Time helpers (used by TimerController)
# ===========================================================================

def _parse_hhmmss(text: str) -> int:
    """Parse ``HH:MM:SS`` into seconds.

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

def _format_hhmmss(seconds: int) -> str:
    """Format seconds as ``HH:MM:SS``.

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

# ===========================================================================
# Controllers
# ===========================================================================

class AudioController(CardController):
    """Audio player card -- play/pause, mute, volume, track navigation.

    Loads ``AudioCard.dui`` and binds encoder events:

    * encoder hold       -> toggle play/pause
    * encoder turn       -> volume up/down
    * encoder click      -> mute toggle
    * encoder press+turn -> previous/next track

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries with ``artist``, ``album``, ``title``, ``cover``.
    assets_dir : Path | None
        Directory containing cover-art images referenced by the catalog.
        Defaults to ``examples/``.
    """

    VOLUME_MIN = 0
    VOLUME_MAX = 100

    def __init__(
        self,
        catalog: list[dict[str, str]],
        assets_dir: Path | None = None,
    ) -> None:
        self._assets_dir = assets_dir or EXAMPLES_DIR
        self.card = DuiCard("AudioCard")

        # The card's range default (0--1) is the source of truth for the
        # initial volume.  Convert to domain percent so the service and
        # the slider start in sync.
        initial_volume = int(
            round(self.card.get_range("volume", min_val=0, max_val=100))
        )
        self.svc = MockAudioService(catalog, initial_volume=initial_volume)

        # ----- bindings (service event -> card binding) -----
        self.card.bind_range(
            "volume",
            self.svc.on_volume_changed,
            min_val=self.VOLUME_MIN,
            max_val=self.VOLUME_MAX,
        )
        self.card.bind(
            "value_text",
            self.svc.on_volume_changed,
            transform=lambda v: f"{v}%" if not self.svc.is_muted else "Muted",
        )
        self.card.bind(
            "value_text",
            self.svc.on_mute_changed,
            transform=lambda m: "Muted" if m else f"{self.svc.volume}%",
        )
        self.card.bind_many(self.svc.on_track_changed, self._track_bindings)

        # ----- forwards (DUI event -> service method) -----
        self.card.forward("toggle_play_pause", self.svc.play_pause)
        self.card.forward("mute_toggle", self.svc.toggle_mute)
        self.card.forward("next", lambda _steps: self.svc.next_track())
        self.card.forward("previous", lambda _steps: self.svc.previous_track())
        self.card.forward(
            "volume_up",
            lambda steps: self.svc.set_volume(self.svc.volume + steps),
        )
        self.card.forward(
            "volume_down",
            lambda steps: self.svc.set_volume(self.svc.volume - abs(steps)),
        )

        # Initial population of bindings whose source isn't a manifest
        # default (track metadata, mute-aware value_text).  Subsequent
        # changes flow through the bindings above.
        self.card.set_many(
            **self._track_bindings(self.svc.current_track, self.svc.is_playing)
        )
        self.card.set(
            "value_text",
            "Muted" if self.svc.is_muted else f"{self.svc.volume}%",
        )

    @property
    def volume(self) -> int:
        """Current volume in percent (0-100)."""
        return self.svc.volume

    @property
    def is_muted(self) -> bool:
        """Whether audio is muted."""
        return self.svc.is_muted

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently playing."""
        return self.svc.is_playing

    @property
    def current_track(self) -> dict[str, str]:
        """The currently selected media entry."""
        return self.svc.current_track

    def _track_bindings(
        self, track: dict[str, str], is_playing: bool
    ) -> dict[str, Any]:
        """Compute the card-binding dict for a (track, is_playing) pair.

        Used both for initial population and as the ``bind_many``
        transform for ``on_track_changed``.

        Parameters
        ----------
        track
            The active media entry.
        is_playing
            Whether playback is active.

        Returns
        -------
        dict[str, Any]
            Mapping of binding name to value.  ``cover`` is included
            only when its file exists on disk.
        """
        out: dict[str, Any] = {
            "artist": track["artist"],
            "title": track["title"],
            "album": track["album"],
            "state": "Playing" if is_playing else "Paused",
        }
        cover_path = self._assets_dir / track["cover"]
        if cover_path.exists():
            out["cover"] = Image.open(cover_path)
        return out

class LightsController(CardController):
    """Lights card -- on/off toggle, brightness, colour temperature.

    Loads ``LightCard.dui`` and binds:

    * encoder click       -> on/off toggle
    * encoder turn        -> brightness up/down (5 % per step)
    * encoder press+turn  -> kelvin up/down (100 K per step)

    Display ranges live on the controller because they are UI choices
    (a real Hue bridge clamps differently to the physical LEDs).
    """

    BRIGHTNESS_MIN = 0
    BRIGHTNESS_MAX = 100
    KELVIN_MIN = 2000
    KELVIN_MAX = 6500
    BRIGHTNESS_STEP = 5
    KELVIN_STEP = 100

    def __init__(self) -> None:
        self.card = DuiCard("LightCard")

        # Card defaults bootstrap the service so they start in lock-step.
        initial_brightness = int(
            round(
                self.card.get_range(
                    "brightness",
                    min_val=self.BRIGHTNESS_MIN,
                    max_val=self.BRIGHTNESS_MAX,
                )
            )
        )
        initial_kelvin = int(
            round(
                self.card.get_range(
                    "kelvin", min_val=self.KELVIN_MIN, max_val=self.KELVIN_MAX
                )
            )
        )
        self._svc = MockLightsService(
            is_on=self.card.get("lights"),
            brightness=initial_brightness,
            kelvin=initial_kelvin,
        )

        # ----- bindings -----
        self.card.bind("lights", self._svc.on_toggled)
        self.card.bind_range(
            "brightness",
            self._svc.on_brightness_changed,
            min_val=self.BRIGHTNESS_MIN,
            max_val=self.BRIGHTNESS_MAX,
        )
        self.card.bind(
            "brightness_value_text",
            self._svc.on_brightness_changed,
            transform=lambda b: f"{b}%",
        )
        self.card.bind_range(
            "kelvin",
            self._svc.on_kelvin_changed,
            min_val=self.KELVIN_MIN,
            max_val=self.KELVIN_MAX,
        )
        self.card.bind(
            "kelvin_value_text",
            self._svc.on_kelvin_changed,
            transform=lambda k: f"{k}K",
        )

        # ----- forwards -----
        self.card.forward("toggle", self._svc.toggle)
        self.card.forward(
            "brightness_up",
            lambda steps: self._svc.set_brightness(
                self._svc.brightness + steps * self.BRIGHTNESS_STEP
            ),
        )
        self.card.forward(
            "brightness_down",
            lambda steps: self._svc.set_brightness(
                self._svc.brightness - abs(steps) * self.BRIGHTNESS_STEP
            ),
        )
        self.card.forward(
            "kelvin_up",
            lambda steps: self._svc.set_kelvin(
                self._svc.kelvin + steps * self.KELVIN_STEP
            ),
        )
        self.card.forward(
            "kelvin_down",
            lambda steps: self._svc.set_kelvin(
                self._svc.kelvin - abs(steps) * self.KELVIN_STEP
            ),
        )

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

class TimerController(CardController):
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
    """

    TICK_INTERVAL_S = 1.0
    FLASH_COUNT = 6
    FLASH_INTERVAL_S = 0.3
    COARSE_STEP_S = 600
    FINE_STEP_S = 30

    def __init__(self) -> None:
        self.card = DuiCard("TimerCard")
        self._tick_task: asyncio.Task[None] | None = None

        default_text: str = self.card.get("timer")
        initial_seconds = _parse_hhmmss(default_text)
        log.info("TimerCard default: %s (%d s)", default_text, initial_seconds)

        self._svc = MockTimerService(initial_seconds)

        self._default_background: str = self.card.get("background")
        self._default_foreground: str = self.card.get("foreground")

        # ----- bindings -----
        self.card.bind(
            "timer", self._svc.on_remaining_changed, transform=_format_hhmmss
        )
        # The flash animation is pure UI feedback (not a binding update),
        # so it lives outside bind() as an explicit subscriber.
        self._svc.on_finished.subscribe(self._flash_notification)

        # ----- forwards -----
        self.card.forward("toggle", self._svc.toggle)
        self.card.forward("reset", self._svc.reset)
        self.card.forward(
            "increase_duration",
            lambda steps: self._svc.adjust_duration(steps * self.COARSE_STEP_S),
        )
        self.card.forward(
            "decrease_duration",
            lambda steps: self._svc.adjust_duration(
                -abs(steps) * self.COARSE_STEP_S
            ),
        )
        self.card.forward(
            "increase_duration_alt",
            lambda steps: self._svc.adjust_duration(steps * self.FINE_STEP_S),
        )
        self.card.forward(
            "decrease_duration_alt",
            lambda steps: self._svc.adjust_duration(
                -abs(steps) * self.FINE_STEP_S
            ),
        )

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

    def format_time(self) -> str:
        """Format the service's current ``remaining`` as ``HH:MM:SS``.

        Returns
        -------
        str
            Zero-padded ``HH:MM:SS`` string.
        """
        return _format_hhmmss(self._svc.remaining)

    async def on_attach(self, deck: Deck) -> None:
        """Start the background tick task.

        Idempotent so successive reconnects don't stack tasks.

        Parameters
        ----------
        deck
            The :class:`~deckui.Deck` instance (unused -- the timer is
            independent of deck state).
        """
        del deck
        if self._tick_task is None or self._tick_task.done():
            self._tick_task = asyncio.create_task(
                self._tick_loop(), name="timer-tick"
            )

    async def on_detach(self) -> None:
        """Cancel the background tick task and wait for it to exit."""
        task = self._tick_task
        self._tick_task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _flash_notification(self) -> None:
        """Flash foreground/background colors when the countdown ends.

        This is pure UI animation -- not a backend state transition --
        so the controller drives the card directly.
        """
        swapped = False
        for _ in range(self.FLASH_COUNT):
            swapped = not swapped
            if swapped:
                self.card.set_many(
                    background=self._default_foreground,
                    foreground=self._default_background,
                )
            else:
                self.card.set_many(
                    background=self._default_background,
                    foreground=self._default_foreground,
                )
            await self.card.request_refresh()
            await asyncio.sleep(self.FLASH_INTERVAL_S)

        self.card.set_many(
            background=self._default_background,
            foreground=self._default_foreground,
        )
        await self.card.request_refresh()

    async def _tick_loop(self) -> None:
        """Drive the service tick once per second."""
        try:
            while True:
                await asyncio.sleep(self.TICK_INTERVAL_S)
                await self._svc.tick()
        except asyncio.CancelledError:
            pass

class DashboardController(CardController):
    """Dashboard card -- live clock, simulated weather, deck-brightness.

    Loads ``DashboardCard.dui``.  Brightness is **deck-owned** state:
    the controller does not store a brightness value of its own.  It
    subscribes to :attr:`deckui.Deck.on_brightness_changed` (via
    :meth:`~deckui.DuiCard.bind_range`) and delegates writes to
    :meth:`deckui.Deck.set_brightness`.  Telemetry arrives via
    :attr:`MockDashboardService.on_telemetry_changed`.  The clock is
    genuinely poll-driven (system time), so a small task ticks once a
    second.
    """

    CLOCK_INTERVAL_S = 1.0
    BRIGHTNESS_MIN = 0
    BRIGHTNESS_MAX = 100
    BRIGHTNESS_STEP = 1

    def __init__(self) -> None:
        self._deck: Deck | None = None
        self._clock_task: asyncio.Task[None] | None = None

        self.card = DuiCard("DashboardCard")

        # Manifest brightness default (normalised) is the cold-start
        # value; remembered across reconnects so the user's last value
        # survives ``Deck.start`` resetting hardware to the manager's
        # startup default.
        self._last_known_brightness: int = int(
            round(
                self.card.get_range(
                    "brightness",
                    min_val=self.BRIGHTNESS_MIN,
                    max_val=self.BRIGHTNESS_MAX,
                )
            )
        )

        self._svc = MockDashboardService()

        # Initial telemetry/clock population (no manifest defaults for
        # these readings).
        self.card.set_many(
            date=self.get_date(),
            time=self.get_time(),
        )

        # ----- DUI handlers route through the deck (deck-owned state) -----
        self.card.forward("brightness_up", self._brightness_up)
        self.card.forward("brightness_down", self._brightness_down)

    @property
    def brightness(self) -> int:
        """Last confirmed deck brightness (0 -- 100)."""
        return self._last_known_brightness

    @staticmethod
    def get_date() -> str:
        """Return today's date as ``YYYY-MM-DD``."""
        return datetime.datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_time() -> str:
        """Return the current local time as ``HH:MM``."""
        return datetime.datetime.now().strftime("%H:%M")

    async def on_attach(self, deck: Deck) -> None:
        """Subscribe to deck-owned brightness, replay last-known, and start tasks.

        Reconnect contract: ``Deck.start`` resets hardware brightness
        to the manager's startup default, so we replay the user's
        last-known value here.

        Parameters
        ----------
        deck
            The freshly-connected :class:`~deckui.Deck` instance.
        """
        self._deck = deck

        # Reflect the deck's confirmed brightness on the slider.
        self.card.bind_range(
            "brightness",
            deck.on_brightness_changed,
            min_val=self.BRIGHTNESS_MIN,
            max_val=self.BRIGHTNESS_MAX,
        )

        # Remember the latest confirmed value so reconnect can replay it.
        @deck.on_brightness_changed
        async def _track_last_known(value: int) -> None:
            self._last_known_brightness = value

        @deck.on_screen_changed
        async def _screen_changed(name: str, screens: dict) -> None:
            _screens = list(screens)
            self.card.set("nav", {"items": _screens, "index": _screens.index(name)})
            await self.card.request_refresh()

        # Replay onto the freshly-connected deck.  Idempotent: if the
        # values match, ``set_brightness`` silently no-ops.
        await deck.set_brightness(self._last_known_brightness)

        # Background tasks (idempotent so reconnect doesn't double up).
        if self._clock_task is None or self._clock_task.done():
            self._clock_task = asyncio.create_task(
                self._clock_loop(), name="dashboard-clock"
            )
        await self._svc.start()

    async def on_detach(self) -> None:
        """Cancel the clock tick and stop the telemetry simulator."""
        task = self._clock_task
        self._clock_task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._svc.stop()

    async def _brightness_up(self, steps: int) -> None:
        if self._deck is None:
            return
        await self._deck.set_brightness(
            self._deck.brightness + steps * self.BRIGHTNESS_STEP
        )

    async def _brightness_down(self, steps: int) -> None:
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
                self.card.set_many(time=t, date=d)
                await self.card.request_refresh()
        except asyncio.CancelledError:
            pass

class FavoritesController:
    """Favourite-media keys -- one :class:`DuiKey` per catalog entry.

    Multi-instance "list of keys" controller -- one key per catalog row
    -- so it doesn't subclass :class:`~deckui.KeyController` (which is
    intentionally 1:1).  Instead it manages its own list of keys and
    provides :meth:`install` to slot them onto a screen.

    Clicking a favourite sets :meth:`DuiKey.start_busy` and then calls
    :meth:`MockAudioService.play`.  A random artificial delay is added
    to the audo service which then emits ``on_track_changed``; the
    :class:`AudioController`'s :meth:`bind_many` subscriber refreshes
    the audio card. Additionally self.finish_busy subscribes to same event
    and and calls :meth:`DuiKey.finish_busy`.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries used as favourites.
    audio : AudioController
        The audio controller whose service handles playback.
    assets_dir : Path | None
        Directory containing cover-art images referenced by the catalog.
        Defaults to ``examples/``.
    """

    def __init__(
        self,
        catalog: list[dict[str, str]],
        audio: AudioController,
        assets_dir: Path | None = None,
    ) -> None:
        self._catalog = catalog
        self._audio_svc = audio.svc
        self._assets_dir = assets_dir or EXAMPLES_DIR
        self._keys: list[DuiKey] = []

        for media in self._catalog:
            key = DuiKey("PictureKey")

            cover_path = self._assets_dir / media["cover"]
            if cover_path.exists():
                key.set("picture", Image.open(cover_path))

            # Late-bind *media* per iteration so each forward target
            # captures its own dict instead of the shared loop variable.
            @key.on_event("click")
            async def _click(k=key, m=media):
                await k.start_busy()
                await self._audio_svc.play(m)

            self._keys.append(key)
        self._audio_svc.on_track_changed.subscribe(self.finish_busy)

    @property
    def keys(self) -> list[DuiKey]:
        """The created favourite keys (same order as *catalog*)."""
        return list(self._keys)

    async def finish_busy(self, *args, **kwargs) -> None:
        """Stop busy animation on all favourite keys."""
        log.info("Finish busy on all keys")
        for k in self._keys:
            await k.finish_busy()

    def install(self, screen: Any, positions: list[int]) -> None:
        """Place favourite keys onto *screen* at the given *positions*."""
        for pos, key in zip(positions, self._keys, strict=False):
            screen.set_key(pos, key)

class GaugeController(CardController):
    """Gauge card -- a needle indicator driven by a simulated sensor.

    Loads ``GaugeCard.dui`` and binds a single normalised value
    (``0.0`` -- ``1.0``) to a rotating needle transform.  The
    underlying :class:`MockGaugeService` simulates a drifting sensor
    reading; manual encoder turns adjust the value through the service.

    Encoder bindings
    ~~~~~~~~~~~~~~~~
    * **encoder turn left**  -- decrease gauge value by one step.
    * **encoder turn right** -- increase gauge value by one step.

    The controller follows the same event-driven pattern as the other
    controllers: encoder input is forwarded to the service, the service
    clamps and emits ``on_value_changed``, and a reactive binding
    pushes the confirmed value back to the card.

    Parameters
    ----------
    simulate : bool, default=True
        When ``True``, the service drifts the gauge value randomly in
        the background.
    """

    def __init__(self, simulate: bool = True) -> None:
        self.card = DuiCard("GaugeCard")

        initial_value: float = self.card.get("gauge")
        self._svc = MockGaugeService(
            initial_value=initial_value,
            simulate=simulate,
        )

        # ----- static bindings (text / icon ) -----
        self.card.set("min_label", "-50")
        self.card.set("mid_label", "0")
        self.card.set("max_label", "+50")
        self.card.set("icon", "ph:car-battery-light")

        # ----- bindings (service event -> card binding) -----
        self.card.bind("gauge", self._svc.on_value_changed)

        # ----- forwards (DUI event -> service method) -----
        self.card.forward(
            "value_down",
            lambda steps: self._svc.adjust(-abs(steps) * self._svc.step),
        )
        self.card.forward(
            "value_up",
            lambda steps: self._svc.adjust(steps * self._svc.step),
        )
        self.card.forward("toggle_simulator", self._toggle_simulator)

    @property
    def value(self) -> float:
        """Current gauge value (0.0 -- 1.0)."""
        return self._svc.value

    async def _toggle_simulator(self) -> None:
        """Toggle the background drift simulator on or off."""
        if self._svc._task is not None and not self._svc._task.done():
            await self._svc.stop()
            self._svc._simulate = False
        else:
            self._svc._simulate = True
            await self._svc.start()

    async def on_attach(self, deck: Deck) -> None:
        """Start the background drift simulator.

        Parameters
        ----------
        deck
            The :class:`~deckui.Deck` instance (unused -- the gauge is
            independent of deck state).
        """
        del deck
        await self._svc.start()

    async def on_detach(self) -> None:
        """Stop the background drift simulator."""
        await self._svc.stop()

class SceneController:
    """Scene-activation keys -- one :class:`DuiKey` per scene definition.

    Multi-instance controller (same shape as :class:`FavoritesController`).
    Click handlers call :meth:`MockScenesService.activate`.  The press/
    release colour-swap is **input feedback** for a confirmed device
    input event (not a state transition), so it lives in the key handler.

    Parameters
    ----------
    scenes : list[dict[str, str]]
        Scene definitions, each with ``label`` and ``icon``.
    """

    def __init__(self, scenes: list[dict[str, str]]) -> None:
        self._scenes = scenes
        self._svc = MockScenesService()
        self._keys: list[DuiKey] = []

        # In a real app this subscriber would update an "active scene"
        # indicator.  Here it just demonstrates that the activation
        # round-trips through the service.
        @self._svc.on_scene_activated
        async def _on_activated(label: str) -> None:
            log.info("Scene confirmed active: %s", label)

        for scene in self._scenes:
            key = DuiKey("IconKey")
            key.set_many(label=scene["label"], icon=scene["icon"])
            self._wire_key(key, scene["label"])
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

    def _wire_key(self, key: DuiKey, label: str) -> None:
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

        key.forward("click", lambda: self._svc.activate(label))

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

    def on_attach(self, deck: Deck) -> None:
        """Attach to *deck* and subscribe to its screen-changed event."""
        self._deck = deck

        @deck.on_screen_changed
        async def _on_screen(name: str, screens: dict) -> None:
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
        card.forward(event, self.advance)

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

    Build the controllers once; iterate over them in
    :meth:`on_connect` / :meth:`on_disconnect` to drive the uniform
    :meth:`~deckui.CardController.on_attach` /
    :meth:`~deckui.CardController.on_detach` lifecycle.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media catalog used by the audio + favourites controllers.
    scene_defs : list[dict[str, str]]
        Scene definitions used by the scene controller.
    """

    def __init__(
        self,
        catalog: list[dict[str, str]],
        scene_defs: list[dict[str, str]],
    ) -> None:
        self.audio = AudioController(catalog)
        self.lights = LightsController()
        self.timer = TimerController()
        self.gauge = GaugeController()
        self.dashboard = DashboardController()
        self.favorites = FavoritesController(catalog, self.audio)
        self.scenes = SceneController(scene_defs)
        self.nav = ScreenCycler(["Main", "Settings"])
        self.nav.attach(self.dashboard.card)

        # Every CardController-derived object gets a uniform lifecycle
        # via on_attach / on_detach.  Keeping this list as the single
        # source of truth means adding a new controller is a one-line
        # change here.
        self._controllers: list[CardController] = [
            self.audio,
            self.lights,
            self.timer,
            self.gauge,
            self.dashboard,
        ]

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
        async def _log_screen(name: str, screens: dict) -> None:
            log.info("Active screen confirmed: %s", name)

        # Drive the uniform lifecycle on every controller.
        for controller in self._controllers:
            await controller.on_attach(deck)
        self.nav.on_attach(deck)

        self._build_main_screen(deck)
        self._build_settings_screen(deck)

        # Resume on the user's last screen (cold start: first screen
        # in the cycler -- "Main").  set_screen wires every key/card's
        # request_refresh() to deck.refresh() under the hood.
        await deck.set_screen(self.nav.current)

        log.info(
            "Deck ready -- try the encoders, keys, "
            "and press the dashboard encoder to switch screens!"
        )

    async def on_disconnect(self, info: DeviceInfo) -> None:
        """Stop background tasks when the deck goes away."""
        log.warning(
            "Deck disconnected: %s -- waiting for reconnect...", info.serial
        )
        for controller in self._controllers:
            await controller.on_detach()

    # -- screen construction -------------------------------------------

    def _build_main_screen(self, deck: Deck) -> None:
        """Layout: favourites + scenes on keys, all four cards on the strip."""
        caps = deck.capabilities
        screen = deck.screen("Main")

        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#1c1c1c"
            screen.set_touchstrip_background_svg_from_file(EXAMPLES_DIR.joinpath("background.svg"))
            screen.set_card(0, self.audio.card)
            screen.set_card(1, self.lights.card)
            screen.set_card(2, self.gauge.card)
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
        screen = deck.screen("Settings")
        caps = deck.capabilities

        if screen.touch_strip is not None:
            screen.touch_strip.background_color = "#1c1c1c"
            screen.set_card(2, self.timer.card)
            screen.set_card(3, self.dashboard.card)

        for key_index in range(caps.key_count):
            key = DuiKey("IconKey")
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
        brightness=app.dashboard.brightness, auto_reconnect=True
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
