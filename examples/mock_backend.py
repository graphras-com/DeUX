"""Mock backend services for the Stream Deck demo.

This module contains pure-Python domain logic with **no DeckUI imports**.
Each service simulates a real-world backend (audio player, smart lights,
countdown timer, dashboard telemetry) so that ``streamdeck.py`` can focus
exclusively on demonstrating DeckUI's API.

Services emit async events when their state changes, allowing controllers
to react and update the UI accordingly -- exactly as a real integration
(Spotify, Home Assistant, etc.) would work.

Swap these classes for real integrations and the DeckUI wiring in
``streamdeck.py`` stays the same.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger(__name__)

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
# Async event helper
# ===========================================================================


class AsyncEvent:
    """A simple async event that can have multiple subscribers.

    Subscribers are registered with the call operator (used as a
    decorator) and invoked with :meth:`emit`.  This mirrors the
    pattern a real backend SDK would expose for property-change
    notifications.

    Examples
    --------
    ::

        svc = SomeService()

        @svc.on_brightness_changed
        async def _handle(value: int) -> None:
            print(f"brightness is now {value}")

        await svc.on_brightness_changed.emit(75)
    """

    def __init__(self) -> None:
        self._handlers: list[Callable[..., Awaitable[None]]] = []

    def __call__(
        self, fn: Callable[..., Awaitable[None]]
    ) -> Callable[..., Awaitable[None]]:
        """Register *fn* as a subscriber (decorator usage).

        Parameters
        ----------
        fn : Callable[..., Awaitable[None]]
            Async callback to invoke when the event fires.

        Returns
        -------
        Callable[..., Awaitable[None]]
            The original function, unmodified.
        """
        self._handlers.append(fn)
        return fn

    async def emit(self, *args: Any, **kwargs: Any) -> None:
        """Invoke all registered handlers with the given arguments.

        Parameters
        ----------
        *args : Any
            Positional arguments forwarded to each handler.
        **kwargs : Any
            Keyword arguments forwarded to each handler.
        """
        for handler in self._handlers:
            await handler(*args, **kwargs)


# ===========================================================================
# Mock services
# ===========================================================================


class MockAudioService:
    """Simulated audio player -- play/pause, volume, mute, track navigation.

    Events
    ------
    on_track_changed : AsyncEvent
        Emitted when the current track or playback state changes.
        Signature: ``(track: dict[str, str], is_playing: bool) -> None``.
    on_volume_changed : AsyncEvent
        Emitted when volume level or mute state changes.
        Signature: ``(volume_level: float, volume_text: str) -> None``.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries with ``artist``, ``album``, ``title``, ``cover``.
    initial_volume : float, default=0.3
        Starting volume (0.0 -- 1.0).
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

        self.on_track_changed = AsyncEvent()
        self.on_volume_changed = AsyncEvent()

    @property
    def current_track(self) -> dict[str, str]:
        """The currently selected media entry."""
        return self._catalog[self._index]

    @property
    def volume_text(self) -> str:
        """Human-readable volume or ``'Muted'``."""
        if self.is_muted:
            return "Muted"
        return f"{int(self.volume_level * 100)}%"

    async def play(self, track: dict[str, str] | None = None) -> None:
        """Start playback, optionally jumping to *track*.

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
        await self.on_track_changed.emit(t, self.is_playing)

    async def pause(self) -> None:
        """Pause playback."""
        self.is_playing = False
        log.info("Paused")
        await self.on_track_changed.emit(self.current_track, self.is_playing)

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
        await self.on_track_changed.emit(t, self.is_playing)
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
        await self.on_track_changed.emit(t, self.is_playing)
        return t

    async def set_volume(self, level: float) -> None:
        """Set volume in [0.0, 1.0] (clamped).

        Parameters
        ----------
        level : float
            Volume between 0.0 and 1.0.
        """
        self.volume_level = max(0.0, min(1.0, level))
        log.info("Volume: %.0f%%", self.volume_level * 100)
        await self.on_volume_changed.emit(self.volume_level, self.volume_text)

    async def toggle_mute(self) -> None:
        """Toggle mute."""
        self.is_muted = not self.is_muted
        log.info("Muted: %s", self.is_muted)
        await self.on_volume_changed.emit(self.volume_level, self.volume_text)


class MockLightsService:
    """Simulated smart-light backend -- on/off, brightness, colour temperature.

    Events
    ------
    on_toggled : AsyncEvent
        Emitted when the on/off state changes.
        Signature: ``(is_on: bool) -> None``.
    on_brightness_changed : AsyncEvent
        Emitted when brightness changes.
        Signature: ``(brightness: int) -> None``.
    on_kelvin_changed : AsyncEvent
        Emitted when colour temperature changes.
        Signature: ``(kelvin: int) -> None``.

    Parameters
    ----------
    is_on : bool, default=True
        Initial on/off state.
    brightness : int, default=80
        Initial brightness percentage (0 -- 100).
    kelvin : int, default=4000
        Initial colour temperature in Kelvin (2000 -- 6500).
    """

    BRIGHTNESS_MIN = 0
    BRIGHTNESS_MAX = 100
    KELVIN_MIN = 2000
    KELVIN_MAX = 6500

    def __init__(
        self,
        is_on: bool = True,
        brightness: int = 80,
        kelvin: int = 4000,
    ) -> None:
        self.is_on: bool = is_on
        self.brightness: int = brightness
        self.kelvin: int = kelvin

        self.on_toggled = AsyncEvent()
        self.on_brightness_changed = AsyncEvent()
        self.on_kelvin_changed = AsyncEvent()

    async def toggle(self) -> None:
        """Toggle lights on/off."""
        self.is_on = not self.is_on
        log.info("Lights: %s", "ON" if self.is_on else "OFF")
        await self.on_toggled.emit(self.is_on)

    async def set_brightness(self, value: int) -> None:
        """Set brightness percentage (clamped to 0 -- 100).

        Parameters
        ----------
        value : int
            Target brightness.
        """
        self.brightness = max(self.BRIGHTNESS_MIN, min(self.BRIGHTNESS_MAX, value))
        log.info("Brightness: %d%%", self.brightness)
        await self.on_brightness_changed.emit(self.brightness)

    async def set_kelvin(self, value: int) -> None:
        """Set colour temperature (clamped to 2000 -- 6500 K).

        Parameters
        ----------
        value : int
            Target colour temperature.
        """
        self.kelvin = max(self.KELVIN_MIN, min(self.KELVIN_MAX, value))
        log.info("Kelvin: %dK", self.kelvin)
        await self.on_kelvin_changed.emit(self.kelvin)


class MockTimerService:
    """Simulated countdown timer -- duration, remaining, start/pause/reset.

    Events
    ------
    on_timer_changed : AsyncEvent
        Emitted when the timer display should update (toggle, reset,
        adjust, or tick).
        Signature: ``(formatted_time: str) -> None``.
    on_finished : AsyncEvent
        Emitted when the countdown reaches zero.
        Signature: ``() -> None``.

    Parameters
    ----------
    initial_seconds : int
        Starting countdown duration in seconds.
    """

    COARSE_STEP_S = 600
    """Seconds added/removed per encoder-turn step (no hold) -- 10 minutes."""
    FINE_STEP_S = 30
    """Seconds added/removed per encoder-hold-turn step -- 30 seconds."""

    def __init__(self, initial_seconds: int) -> None:
        self._default_duration: int = initial_seconds
        self.duration: int = initial_seconds
        self.remaining: int = initial_seconds
        self.is_running: bool = False

        self.on_timer_changed = AsyncEvent()
        self.on_finished = AsyncEvent()

    @staticmethod
    def parse_hhmmss(text: str) -> int:
        """Parse an ``HH:MM:SS`` string into total seconds.

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

    async def toggle(self) -> None:
        """Start or pause the countdown.

        When starting, the current ``remaining`` value is captured as the
        new default duration.  If the timer was paused at zero, it restarts
        from the current default.
        """
        if not self.is_running:
            if self.remaining <= 0:
                self.remaining = self._default_duration
            self._default_duration = self.remaining
            self.duration = self.remaining
            log.info(
                "Timer started -- %s (new default: %d s)",
                self.format_time(),
                self._default_duration,
            )
        else:
            log.info("Timer paused -- %s", self.format_time())
        self.is_running = not self.is_running
        await self.on_timer_changed.emit(self.format_time())

    async def reset(self) -> None:
        """Stop the countdown and reload the current default duration."""
        self.is_running = False
        self.duration = self._default_duration
        self.remaining = self._default_duration
        log.info("Timer reset -- %s", self.format_time())
        await self.on_timer_changed.emit(self.format_time())

    async def adjust_duration(self, delta_seconds: int) -> None:
        """Add (or subtract) seconds to/from the configured duration.

        Parameters
        ----------
        delta_seconds : int
            Seconds to add (positive) or subtract (negative).
        """
        self.duration = max(0, self.duration + delta_seconds)
        self.remaining = self.duration
        log.info("Timer duration: %s", self.format_time())
        await self.on_timer_changed.emit(self.format_time())

    async def tick(self) -> None:
        """Decrement *remaining* by one second if running.

        Emits :attr:`on_timer_changed` on every active tick and
        :attr:`on_finished` when the countdown reaches zero.
        """
        if not self.is_running or self.remaining <= 0:
            return
        self.remaining -= 1
        await self.on_timer_changed.emit(self.format_time())
        if self.remaining <= 0 and self.is_running:
            self.is_running = False
            log.info("Timer finished")
            await self.on_finished.emit()


class MockDashboardService:
    """Simulated dashboard telemetry backend -- weather and clock.

    This service represents an external data source (e.g. a weather API
    or home-automation hub) that provides read-only telemetry.  Device
    control (deck brightness, screen cycling) is application logic and
    belongs in the controller layer, not here.

    Parameters
    ----------
    temperature : str, default="22C"
        Initial temperature reading.
    humidity : str, default="45%"
        Initial humidity reading.
    """

    def __init__(
        self,
        temperature: str = "22C",
        humidity: str = "45%",
    ) -> None:
        self.temperature: str = temperature
        self.humidity: str = humidity

    @staticmethod
    def get_date() -> str:
        """Return today's date as ``YYYY-MM-DD``."""
        return datetime.datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_time() -> str:
        """Return the current local time as ``HH:MM``."""
        return datetime.datetime.now().strftime("%H:%M")
