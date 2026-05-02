"""Mock backend services for the Stream Deck demo.

This module contains pure-Python domain logic with **no DeckUI imports
beyond the** :class:`~deckui.AsyncEvent` **primitive**.  Each service
simulates a real-world backend (audio player, smart lights, countdown
timer, dashboard telemetry, scene activator) and emits events when its
state actually changes.

These services are intentionally hardware- and UI-ignorant:

* Values are kept in **domain units** (volume in percent 0-100, timer
  remaining in seconds, temperature in degrees Celsius).  No
  normalisation to slider ranges.  No formatted strings.
* Events carry the changed value, not pre-rendered text.

The controllers in :mod:`streamdeck` translate domain values to
presentation, exactly as a real integration with Spotify, Home
Assistant, etc. would do.

Swap these classes for real integrations and the DeckUI wiring in
``streamdeck.py`` stays the same.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random

from deckui import AsyncEvent

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
        Emitted when the volume value changes.
        Signature: ``(volume: int) -> None`` -- domain percent in
        ``[0, 100]``.
    on_mute_changed : AsyncEvent
        Emitted when the mute state changes.
        Signature: ``(is_muted: bool) -> None``.

    Parameters
    ----------
    catalog : list[dict[str, str]]
        Media entries with ``artist``, ``album``, ``title``, ``cover``.
    initial_volume : int, default=50
        Starting volume in percent (0-100, clamped).
    """

    def __init__(
        self,
        catalog: list[dict[str, str]],
        initial_volume: int = 50,
    ) -> None:
        self._catalog = list(catalog)
        self._index = 0
        self.volume: int = max(0, min(100, initial_volume))
        self.is_muted: bool = False
        self.is_playing: bool = False

        self.on_track_changed: AsyncEvent = AsyncEvent()
        self.on_volume_changed: AsyncEvent = AsyncEvent()
        self.on_mute_changed: AsyncEvent = AsyncEvent()

    @property
    def current_track(self) -> dict[str, str]:
        """The currently selected media entry."""
        return self._catalog[self._index]

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

    async def set_volume(self, value: int) -> None:
        """Set volume in percent ``[0, 100]`` (clamped).

        Idempotent: a same-value call neither logs nor emits.

        Parameters
        ----------
        value : int
            Target volume in percent.
        """
        clamped = max(0, min(100, value))
        if clamped == self.volume:
            return
        self.volume = clamped
        log.info("Volume: %d%%", self.volume)
        await self.on_volume_changed.emit(self.volume)

    async def toggle_mute(self) -> None:
        """Toggle mute and emit :attr:`on_mute_changed`."""
        self.is_muted = not self.is_muted
        log.info("Muted: %s", self.is_muted)
        await self.on_mute_changed.emit(self.is_muted)


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

        self.on_toggled: AsyncEvent = AsyncEvent()
        self.on_brightness_changed: AsyncEvent = AsyncEvent()
        self.on_kelvin_changed: AsyncEvent = AsyncEvent()

    async def toggle(self) -> None:
        """Toggle lights on/off."""
        self.is_on = not self.is_on
        log.info("Lights: %s", "ON" if self.is_on else "OFF")
        await self.on_toggled.emit(self.is_on)

    async def set_brightness(self, value: int) -> None:
        """Set brightness percentage (clamped to 0 -- 100).

        Idempotent: a same-value call emits nothing.

        Parameters
        ----------
        value : int
            Target brightness.
        """
        clamped = max(self.BRIGHTNESS_MIN, min(self.BRIGHTNESS_MAX, value))
        if clamped == self.brightness:
            return
        self.brightness = clamped
        log.info("Brightness: %d%%", self.brightness)
        await self.on_brightness_changed.emit(self.brightness)

    async def set_kelvin(self, value: int) -> None:
        """Set colour temperature (clamped to 2000 -- 6500 K).

        Parameters
        ----------
        value : int
            Target colour temperature.
        """
        clamped = max(self.KELVIN_MIN, min(self.KELVIN_MAX, value))
        if clamped == self.kelvin:
            return
        self.kelvin = clamped
        log.info("Kelvin: %dK", self.kelvin)
        await self.on_kelvin_changed.emit(self.kelvin)


class MockTimerService:
    """Simulated countdown timer -- duration, remaining, start/pause/reset.

    All times are in **seconds**.  Conversion to display strings is the
    controller's responsibility.

    Events
    ------
    on_remaining_changed : AsyncEvent
        Emitted whenever ``remaining`` changes.
        Signature: ``(remaining_seconds: int) -> None``.
    on_running_changed : AsyncEvent
        Emitted when the timer transitions between running and paused.
        Signature: ``(is_running: bool) -> None``.
    on_finished : AsyncEvent
        Emitted once when the countdown reaches zero while running.
        Signature: ``() -> None``.

    Parameters
    ----------
    initial_seconds : int
        Starting countdown duration in seconds.
    """

    def __init__(self, initial_seconds: int) -> None:
        self._default_duration: int = initial_seconds
        self.duration: int = initial_seconds
        self.remaining: int = initial_seconds
        self.is_running: bool = False

        self.on_remaining_changed: AsyncEvent = AsyncEvent()
        self.on_running_changed: AsyncEvent = AsyncEvent()
        self.on_finished: AsyncEvent = AsyncEvent()

    async def toggle(self) -> None:
        """Start or pause the countdown.

        When starting, the current ``remaining`` value is captured as
        the new default duration.  If the timer was paused at zero, it
        restarts from the current default.
        """
        if not self.is_running:
            if self.remaining <= 0:
                self.remaining = self._default_duration
                await self.on_remaining_changed.emit(self.remaining)
            self._default_duration = self.remaining
            self.duration = self.remaining
            log.info(
                "Timer started -- %d s (new default: %d s)",
                self.remaining,
                self._default_duration,
            )
        else:
            log.info("Timer paused -- %d s", self.remaining)
        self.is_running = not self.is_running
        await self.on_running_changed.emit(self.is_running)

    async def reset(self) -> None:
        """Stop the countdown and reload the current default duration."""
        was_running = self.is_running
        self.is_running = False
        self.duration = self._default_duration
        previous_remaining = self.remaining
        self.remaining = self._default_duration
        log.info("Timer reset -- %d s", self.remaining)
        if was_running:
            await self.on_running_changed.emit(False)
        if previous_remaining != self.remaining:
            await self.on_remaining_changed.emit(self.remaining)

    async def adjust_duration(self, delta_seconds: int) -> None:
        """Add (or subtract) seconds to/from the configured duration.

        Parameters
        ----------
        delta_seconds : int
            Seconds to add (positive) or subtract (negative).
        """
        new_duration = max(0, self.duration + delta_seconds)
        if new_duration == self.duration:
            return
        self.duration = new_duration
        self.remaining = new_duration
        log.info("Timer duration: %d s", self.remaining)
        await self.on_remaining_changed.emit(self.remaining)

    async def tick(self) -> None:
        """Decrement *remaining* by one second if running.

        Emits :attr:`on_remaining_changed` on every active tick and
        :attr:`on_finished` when the countdown reaches zero.
        """
        if not self.is_running or self.remaining <= 0:
            return
        self.remaining -= 1
        await self.on_remaining_changed.emit(self.remaining)
        if self.remaining <= 0 and self.is_running:
            self.is_running = False
            log.info("Timer finished")
            await self.on_running_changed.emit(False)
            await self.on_finished.emit()


class MockDashboardService:
    """Simulated dashboard telemetry backend -- weather telemetry.

    Represents an external sensor / weather-API integration that pushes
    updates to its subscribers.  In a real system this would be a
    long-lived MQTT subscription, a websocket connection, etc.; here we
    simulate it with a background coroutine that nudges the readings
    every :attr:`UPDATE_INTERVAL_S` seconds.

    Clock display is intentionally **not** the dashboard service's
    concern -- the system clock is a poll-driven ambient signal, so the
    controller just reads :func:`datetime.datetime.now` directly.

    Events
    ------
    on_telemetry_changed : AsyncEvent
        Emitted whenever a telemetry value changes.
        Signature: ``(temperature_c: float, humidity_pct: int) -> None``.

    Parameters
    ----------
    temperature_c : float, default=22.0
        Initial temperature in degrees Celsius.
    humidity_pct : int, default=45
        Initial relative humidity in percent (0 -- 100).
    """

    UPDATE_INTERVAL_S = 5.0
    """Seconds between simulated telemetry pushes."""

    def __init__(
        self,
        temperature_c: float = 22.0,
        humidity_pct: int = 45,
    ) -> None:
        self.temperature_c: float = temperature_c
        self.humidity_pct: int = max(0, min(100, humidity_pct))

        self.on_telemetry_changed: AsyncEvent = AsyncEvent()
        self._task: asyncio.Task[None] | None = None

    async def set_telemetry(
        self, temperature_c: float, humidity_pct: int
    ) -> None:
        """Push new telemetry values.

        Idempotent: emits only if at least one value has changed.

        Parameters
        ----------
        temperature_c : float
            New temperature reading (°C).
        humidity_pct : int
            New humidity reading (percent, clamped).
        """
        new_humidity = max(0, min(100, humidity_pct))
        if (
            temperature_c == self.temperature_c
            and new_humidity == self.humidity_pct
        ):
            return
        self.temperature_c = temperature_c
        self.humidity_pct = new_humidity
        await self.on_telemetry_changed.emit(
            self.temperature_c, self.humidity_pct
        )

    async def start(self) -> None:
        """Start the telemetry-simulator background task (idempotent)."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._simulate(), name="dashboard-telemetry"
            )

    async def stop(self) -> None:
        """Cancel the simulator and wait for it to exit."""
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _simulate(self) -> None:
        """Nudge readings periodically to demonstrate event-driven push."""
        try:
            while True:
                await asyncio.sleep(self.UPDATE_INTERVAL_S)
                temperature = round(
                    self.temperature_c + random.uniform(-0.4, 0.4), 1
                )
                humidity = max(
                    0,
                    min(100, self.humidity_pct + random.randint(-2, 2)),
                )
                await self.set_telemetry(temperature, humidity)
        except asyncio.CancelledError:
            pass


class MockScenesService:
    """Simulated scene activator -- "set the room to Cinema mode".

    A real implementation would call out to Home Assistant, Hue, etc.
    Here we just track the most recently activated scene and emit an
    event so subscribers (e.g. a UI controller) can react.

    Events
    ------
    on_scene_activated : AsyncEvent
        Emitted on every successful :meth:`activate` call.
        Signature: ``(label: str) -> None``.

    Attributes
    ----------
    active_scene : str | None
        Label of the most recently activated scene, or ``None`` before
        the first activation.
    """

    def __init__(self) -> None:
        self.active_scene: str | None = None
        self.on_scene_activated: AsyncEvent = AsyncEvent()

    async def activate(self, label: str) -> None:
        """Activate the named scene and emit :attr:`on_scene_activated`.

        Parameters
        ----------
        label : str
            Scene label to activate.
        """
        self.active_scene = label
        log.info("Scene activated: %s", label)
        await self.on_scene_activated.emit(label)
