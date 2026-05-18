"""Deck class: per-device handle managed by DeckManager."""

from __future__ import annotations

import asyncio
import io
import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any, cast

from PIL import Image
from StreamDeck.DeviceManager import DeviceManager

from ..render.key_renderer import render_blank_key
from ..render.metrics import RenderMetrics
from ..render.touch_renderer import compose_card_with_background
from ._executor import get_executor, shutdown_executor
from .async_event import AsyncEvent
from .capabilities import DeviceCapabilities
from .device_info import DeviceInfo
from .events import (
    DeckEvent,
    EncoderPressEvent,
    EncoderTurnEvent,
    KeyEvent,
    TouchEvent,
)
from .transport import AsyncTransport

if TYPE_CHECKING:
    from ..dui.animator import PushFn
    from ..dui.key import DuiKey
    from ..render.theme import Theme
    from ..ui.cards.base import Card
    from ..ui.controls.key_slot import KeySlot
    from ..ui.screen import Screen

logger = logging.getLogger(__name__)

#: Timeout in seconds for HID write calls dispatched to the executor.
#: If a call blocks longer than this (e.g. USB suspend), the device is
#: treated as potentially disconnected.
_HID_WRITE_TIMEOUT: float = 2.0


class HidWriteTimeout(Exception):
    """Raised when a HID write exceeds :data:`_HID_WRITE_TIMEOUT`."""


class DeckError(Exception):
    """Raised for deck-level errors."""


class Deck:
    """Per-device handle for an Elgato Stream Deck.

    Instances are created and managed by :class:`DeckManager`.  Do not
    instantiate ``Deck`` directly — use ``DeckManager.on_connect`` to
    receive connected ``Deck`` instances.

    The ``Deck`` object provides the per-device API for screens, keys,
    encoders, touchscreen cards, brightness, and rendering.

    Attributes
    ----------
    on_brightness_changed : AsyncEvent
        Fires after :meth:`set_brightness` confirms a change to a *new*
        value (the hardware push has returned).  Subscribers receive
        the new brightness percentage as an ``int`` in ``[0, 100]``.
        Idempotent calls (same value) do not emit.
    on_screen_changed : AsyncEvent
        Fires after :meth:`set_screen` finishes rendering a new active
        screen.  Subscribers receive the new screen name (``str``).
        Idempotent calls (same screen) do not emit.
    """

    def __init__(
        self,
        serial_number: str,
        brightness: int = 80,
    ) -> None:
        """
        Parameters
        ----------
        serial_number
            The serial number of the target device.
        brightness
            Initial brightness (0-100).
        """
        self._serial_number = serial_number
        self._brightness = brightness
        self._device: Any = None
        self._caps: DeviceCapabilities | None = None
        self._metrics: RenderMetrics | None = None
        self._transport: AsyncTransport | None = None
        self._event_task: asyncio.Task[None] | None = None
        self._timeout_task: asyncio.Task[None] | None = None
        self._timeout_event: asyncio.Event = asyncio.Event()
        self._closed_event = asyncio.Event()
        self._running = False
        self._device_lock = asyncio.Lock()

        self._screens: dict[str, Screen] = {}
        self._active_screen: Screen | None = None
        self._theme: Theme | None = None

        self.on_brightness_changed = AsyncEvent()
        self.on_screen_changed = AsyncEvent()

    async def start(self) -> None:
        """Discover the device by serial, open it, and start the event loop."""
        if self._running:
            return

        loop = asyncio.get_running_loop()

        devices = await loop.run_in_executor(get_executor(), DeviceManager().enumerate)

        if not devices:
            raise DeckError("No Stream Deck devices found")

        visual = [d for d in devices if d.DECK_VISUAL]
        if not visual:
            raise DeckError("No visual Stream Deck devices found")

        target = None
        for d in visual:
            try:
                await loop.run_in_executor(get_executor(), d.open)
                serial = d.get_serial_number()
                if serial == self._serial_number:
                    target = d
                    break
                await loop.run_in_executor(get_executor(), d.close)
            except Exception:
                continue
        if target is None:
            raise DeckError(
                f"No device with serial '{self._serial_number}' found"
            )
        self._device = target

        await self._exec_device_io(self._device.reset)
        await self._exec_device_io(self._device.set_brightness, self._brightness)

        self._caps = DeviceCapabilities.from_device(self._device)
        self._metrics = RenderMetrics(self._caps)

        logger.info(
            "Opened %s (serial: %s, firmware: %s, keys: %d, dials: %d)",
            self._device.deck_type(),
            self._device.get_serial_number(),
            self._device.get_firmware_version(),
            self._caps.key_count,
            self._caps.dial_count,
        )

        self._transport = AsyncTransport(self._device, loop, self._caps)
        self._transport.start()

        self._running = True
        self._closed_event.clear()

        self._event_task = asyncio.create_task(
            self._event_loop(), name="deux-events"
        )

    async def stop(self) -> None:
        """Stop the event loop and close the device."""
        if not self._running:
            return

        self._running = False

        if self._transport:
            self._transport.stop()

        if self._event_task and not self._event_task.done():
            self._event_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._event_task

        if self._device:
            try:
                await self._exec_device_io(self._device.reset)
                await self._exec_device_io(self._device.close)
            except (HidWriteTimeout, Exception) as e:
                logger.warning("Error closing device: %s", e)

        self._closed_event.set()
        shutdown_executor(wait=True)
        logger.info("Deck stopped")

    async def wait_closed(self) -> None:
        """Block until the deck is closed (e.g. by stop() or disconnect)."""
        await self._closed_event.wait()

    async def _exec_device_io(self, func: Any, *args: Any) -> None:
        """Run a device I/O call in the executor with a timeout.

        Parameters
        ----------
        func
            The blocking HID function to call (e.g.
            ``self._device.set_key_image``).
        *args
            Positional arguments forwarded to *func*.

        Raises
        ------
        HidWriteTimeout
            If the call does not complete within
            :data:`_HID_WRITE_TIMEOUT` seconds.
        """
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(get_executor(), func, *args),
                timeout=_HID_WRITE_TIMEOUT,
            )
        except TimeoutError:
            logger.error(
                "HID write timed out after %.1fs — device may be disconnected",
                _HID_WRITE_TIMEOUT,
            )
            raise HidWriteTimeout(
                f"HID write to {func!r} timed out after {_HID_WRITE_TIMEOUT}s"
            ) from None

    @property
    def device_path(self) -> str | None:
        """HID device path, or ``None`` if not opened."""
        if self._device is None:
            return None
        return cast("str | None", self._device.id())

    @property
    def is_connected(self) -> bool:
        """Whether the device is currently connected and operational."""
        return self._device is not None and self._running

    @property
    def capabilities(self) -> DeviceCapabilities:
        """The device capabilities for the connected device.

        Raises
        ------
        DeckError
            If the device is not opened.
        """
        if self._caps is None:
            raise DeckError("Device not opened")
        return self._caps

    @property
    def metrics(self) -> RenderMetrics:
        """Rendering metrics for the connected device.

        Raises
        ------
        DeckError
            If the device is not opened.
        """
        if self._metrics is None:
            raise DeckError("Device not opened")
        return self._metrics

    @property
    def info(self) -> DeviceInfo:
        """Get device information."""
        if not self._device:
            raise DeckError("Device not opened")
        caps = self.capabilities
        return DeviceInfo(
            deck_type=caps.deck_type,
            serial=self._device.get_serial_number(),
            firmware=self._device.get_firmware_version(),
            key_count=caps.key_count,
            key_layout=(caps.key_cols, caps.key_rows),
            encoder_count=caps.dial_count,
            key_pixel_size=caps.key_size,
            touchscreen_size=(caps.touchscreen_width, caps.touchscreen_height),
            key_image_format=caps.key_image_format,
        )

    @property
    def brightness(self) -> int:
        """Current brightness level (0-100)."""
        return self._brightness

    @property
    def theme(self) -> Theme | None:
        """Per-deck theme override, or ``None`` to inherit the system theme.

        When set, this theme is used for all screens on this deck
        unless a screen has its own :attr:`~deux.Screen.theme`
        override.  Set to ``None`` to fall back to the system-wide
        theme.
        """
        return self._theme

    @theme.setter
    def theme(self, value: Theme | None) -> None:
        self._theme = value

    def _resolve_stylesheet(self) -> str:
        """Resolve the effective CSS stylesheet for the active screen.

        The cascade is: screen theme > deck theme > system theme.

        Returns
        -------
        str
            CSS stylesheet string from the most specific theme.
        """
        from ..render.theme import get_active_theme

        screen = self._active_screen
        if screen is not None and screen.theme is not None:
            return screen.theme.css
        if self._theme is not None:
            return self._theme.css
        return get_active_theme().css

    async def set_brightness(self, percent: int) -> None:
        """Set screen brightness.

        Pushes the value to the hardware (if connected) and emits
        :attr:`on_brightness_changed` with the clamped result.  If the
        clamped value equals the current brightness, no event fires —
        observers see only confirmed transitions.

        Parameters
        ----------
        percent
            Brightness level (0-100).  Values outside the range are
            clamped.
        """
        clamped = max(0, min(100, percent))
        if clamped == self._brightness:
            return
        if self._device is not None:
            async with self._device_lock:
                await self._exec_device_io(self._device.set_brightness, clamped)
        self._brightness = clamped
        await self.on_brightness_changed.emit(clamped)

    def screen(self, name: str) -> Screen:
        """Get or create a screen by name.

        Parameters
        ----------
        name
            Screen name.

        Returns
        -------
        Screen
            The Screen instance.

        Raises
        ------
        DeckError
            If the device is not opened — capabilities are required to
            size the screen, and they are only known after :meth:`start`.
        """
        from ..ui.screen import Screen

        if self._caps is None:
            raise DeckError("Device not opened")

        if name not in self._screens:
            self._screens[name] = Screen(name, self._caps)
        return self._screens[name]

    async def set_screen(self, name: str) -> None:
        """Switch to a named screen, rendering all keys and cards.

        Wires up refresh callbacks on every key and card so that any
        handler or background task can call ``request_refresh()`` to
        trigger a re-render without needing a direct reference to the
        deck.  After the new screen has finished rendering, fires
        :attr:`on_screen_changed` with the new name.  No event fires
        if the requested screen is already active.

        Parameters
        ----------
        name
            Screen name (must already exist via ``deck.screen(name)``).

        Raises
        ------
        DeckError
            If *name* does not match a previously-created screen.
        """
        if name not in self._screens:
            raise DeckError(f"Screen '{name}' does not exist")

        target = self._screens[name]
        if target is self._active_screen:
            return

        self._active_screen = target
        logger.info("Switching to screen: %s", name)

        # Apply the resolved theme cascade for this screen.
        from ..render.svg_rasterize import set_svg_stylesheet

        set_svg_stylesheet(self._resolve_stylesheet())

        self._wire_refresh_callbacks()

        await self._render_all_keys()
        if self._active_screen.touch_strip is not None:
            await self._render_touchscreen()
        if self._active_screen.info_screen is not None:
            await self._render_info_screen()

        await self.on_screen_changed.emit(name, self._screens)

    def _wire_refresh_callbacks(self) -> None:
        """Register ``self.refresh`` on every key and card of the active screen.

        Called by :meth:`set_screen`.  Allows handlers and background
        tasks to call :meth:`KeySlot.request_refresh` /
        :meth:`Card.request_refresh` to trigger re-renders without
        needing a direct deck reference.
        """
        screen = self._active_screen
        if screen is None:
            return
        for key_slot in screen.keys.values():
            key_slot.set_refresh_callback(self.refresh)
        if screen.touch_strip is not None:
            for card in screen.touch_strip.cards:
                card.set_refresh_callback(self.refresh)

    @property
    def active_screen(self) -> Screen | None:
        """The currently displayed screen, or ``None`` if no screen is set."""
        return self._active_screen

    def _current_screen(self) -> Screen | None:
        return self._active_screen

    async def _render_all_keys(self) -> None:
        """Render and push all key images for the active screen."""
        screen = self._current_screen()
        if not self._device or not screen:
            return

        caps = self._caps
        if caps is None:
            return

        metrics = self._metrics

        if metrics is None:
            return

        for key_index in range(caps.key_count):
            key_slot = screen.keys.get(key_index)
            if key_slot and self._is_dui_key(key_slot):
                await self._render_dui_key(key_slot, key_index)
            else:
                bg_image = screen.key_bg_image
                if bg_image is not None:
                    image_bytes = bg_image
                else:
                    image_bytes = render_blank_key(
                        key_size=metrics.key_size,
                        image_format=caps.key_image_format,
                    )
                async with self._device_lock:
                    await self._exec_device_io(
                        self._device.set_key_image,
                        key_index,
                        image_bytes,
                    )

    @staticmethod
    def _is_dui_key(key_slot: KeySlot) -> bool:
        """Check whether a key slot is a DuiKey."""
        return getattr(key_slot, "has_dui_content", False)

    @staticmethod
    def _is_animating(obj: Any) -> bool:
        """Check whether a card or key has an active spinner animation."""
        return getattr(obj, "is_animating", False)

    async def _render_dui_key(self, key_slot: KeySlot, key_index: int) -> None:
        """Render a DuiKey and push to the device.

        Parameters
        ----------
        key_slot
            The DuiKey to render.
        key_index
            The screen slot the key is currently installed at.  This is
            authoritative for routing (a single DuiKey may live on
            multiple screens at different slots), so the spinner
            ``push_fn`` is rewired on every render to capture the active
            slot.
        """
        if not self._device:
            return

        dui_key = cast("DuiKey", key_slot)

        # Skip rendering if a spinner animation is active
        if self._is_animating(dui_key):
            return

        # Re-wire push_fn every render so a DuiKey reused across screens
        # always animates at the slot of the currently active screen.
        async def _push_key_frame(frame_bytes: bytes) -> None:
            async with self._device_lock:
                await self._exec_device_io(
                    self._device.set_key_image,
                    key_index,
                    frame_bytes,
                )

        if self._caps is None:
            return

        dui_key.set_push_fn(_push_key_frame, key_size=self._caps.key_size)

        image_bytes = dui_key.render_image(
            key_size=self._caps.key_size,
            image_format=self._caps.key_image_format,
        )
        dui_key.set_rendered_image(image_bytes)

        async with self._device_lock:
            await self._exec_device_io(
                self._device.set_key_image,
                key_index,
                image_bytes,
            )

    async def _render_touchscreen(self) -> None:
        """Render and push each card panel individually to the device.

        Uses the SVG-native pipeline for DuiCards: background
        compositing happens at the SVG level, and each panel is
        rasterised directly to device-ready bytes and pushed as a
        per-panel update.

        Non-DUI cards fall back to the legacy Pillow compositing path.
        """
        screen = self._current_screen()
        if not self._device or not screen or not self._metrics:
            return

        if screen.touch_strip is None:
            return

        metrics = self._metrics
        touch_strip = screen.touch_strip

        from ..dui.card import DuiCard

        bg_svg_root = touch_strip.bg_svg_root

        for card_idx, card in enumerate(screen.cards):
            x_pos = card_idx * metrics.panel_width
            y_pos = 0

            if isinstance(card, DuiCard):
                # Set up background layer for SVG-level compositing
                bg_tile = touch_strip.bg_tile(card_idx)
                card.set_bg_tile(bg_tile)

                if bg_svg_root is not None:
                    card.set_background_layer(
                        bg_svg_root,
                        card_idx,
                        metrics.panel_width,
                        metrics.panel_height,
                    )
                else:
                    card.clear_background_layer()

                # Wire push_fn for spinner animations (per-panel update)
                async def _make_push(
                    x: int,
                    y: int,
                    w: int,
                    h: int,
                    tile: Image.Image | None,
                ) -> PushFn:
                    async def _push_card_frame(frame_bytes: bytes) -> None:
                        if tile is not None:
                            # Decode the frame, composite onto the bg tile, re-encode
                            frame_img = Image.open(io.BytesIO(frame_bytes))
                            out_bytes = compose_card_with_background(
                                frame_img,
                                bg_tile=tile,
                                panel_width=w,
                                panel_height=h,
                                image_format=(
                                    self._caps.touchscreen_image_format
                                    if self._caps
                                    else "JPEG"
                                ),
                            )
                        else:
                            out_bytes = frame_bytes
                        async with self._device_lock:
                            await self._exec_device_io(
                                self._device.set_touchscreen_image,
                                out_bytes,
                                x,
                                y,
                                w,
                                h,
                            )

                    return _push_card_frame

                push_fn = await _make_push(
                    x_pos,
                    y_pos,
                    metrics.panel_width,
                    metrics.panel_height,
                    bg_tile,
                )
                card.set_push_fn(
                    push_fn, panel_size=(metrics.panel_width, metrics.panel_height)
                )

                # Skip re-rendering cards with active spinner animations
                if self._is_animating(card):
                    continue

                await card.prepare_assets()

                # SVG-native pipeline: render directly to device bytes
                image_fmt = (
                    self._caps.touchscreen_image_format if self._caps else "JPEG"
                )
                panel_bytes = card.render_bytes(
                    panel_width=metrics.panel_width,
                    panel_height=metrics.panel_height,
                    image_format=image_fmt,
                    background=touch_strip.background_color,
                )

                # Also render a PIL image for caching (used by screenshot)
                img = card.render()
                card.set_rendered(img)

            else:
                # Non-DUI card: legacy path with Pillow compositing
                await card.prepare_assets()
                rendered = card.render()
                card.set_rendered(rendered)

                bg_tile = touch_strip.bg_tile(card_idx)
                panel_bytes = compose_card_with_background(
                    rendered,
                    bg_tile=bg_tile,
                    background=touch_strip.background_color,
                    panel_width=metrics.panel_width,
                    panel_height=metrics.panel_height,
                    image_format=(
                        self._caps.touchscreen_image_format if self._caps else "JPEG"
                    ),
                )

            # Push per-panel update
            async with self._device_lock:
                await self._exec_device_io(
                    self._device.set_touchscreen_image,
                    panel_bytes,
                    x_pos,
                    y_pos,
                    metrics.panel_width,
                    metrics.panel_height,
                )

    async def _render_info_screen(self) -> None:
        """Render and push the info screen image (e.g. Neo)."""
        screen = self._current_screen()
        if not self._device or not screen:
            return

        info = screen.info_screen
        if info is None:
            return

        image_bytes = info.render_bytes()

        async with self._device_lock:
            await self._exec_device_io(
                self._device.set_screen_image,
                image_bytes,
                0,
                0,
                info.width,
                info.height,
            )
        info.mark_clean()

    async def refresh(self) -> None:
        """Re-render and push all dirty controls on the active screen.

        Call this after changing card values if you need immediate
        updates outside of ``set_screen()``.  Also drains any pending
        callbacks queued by programmatic ``set_value()`` calls on
        range controls.
        """
        screen = self._current_screen()
        if not screen:
            return

        for card in screen.cards:
            await self._drain_card_callbacks(card)

        for key_index, key_slot in screen.keys.items():
            if key_slot.is_dirty and self._is_dui_key(key_slot):
                await self._render_dui_key(key_slot, key_index)

        if screen.key_bg_dirty:
            await self._render_all_keys()
            screen.clear_key_bg_dirty()

        if screen.touch_strip is not None and screen.touch_strip.any_dirty:
            await self._render_touchscreen()

        if screen.info_screen is not None and screen.info_screen.is_dirty:
            await self._render_info_screen()

    async def _check_timeouts(self) -> None:
        """Check all card selection timeouts on the active screen."""
        screen = self._current_screen()
        if not screen:
            return
        any_changed = False
        for card in screen.cards:
            if card.check_selection_timeout():
                any_changed = True
        if any_changed:
            await self.refresh()

    def schedule_timeout_check(self) -> None:
        """Signal that a card timeout needs checking.

        Call this method when a card registers a selection timeout so
        the deck can fire ``_check_timeouts`` without polling.  This is
        a no-op when the timeout loop is already scheduled to wake.
        """
        self._timeout_event.set()

    async def _timeout_loop(self) -> None:
        """Deadline-driven timeout checker.

        Waits until ``schedule_timeout_check`` is called, then performs
        the timeout check.  This eliminates the 500 ms polling wake.
        """
        try:
            while self._running:
                await self._timeout_event.wait()
                self._timeout_event.clear()
                if not self._running:
                    break
                await self._check_timeouts()
        except asyncio.CancelledError:
            pass

    async def _event_loop(self) -> None:
        """Dispatch transport events to the active screen handlers."""
        if not self._transport:
            return

        self._timeout_task = asyncio.create_task(
            self._timeout_loop(), name="deux-timeouts"
        )

        try:
            while self._running:
                event = await self._transport.queue.get()

                if not self._current_screen():
                    continue

                try:
                    await self._dispatch(event)
                except Exception:
                    logger.exception("Error in event handler")

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Event loop crashed")
        finally:
            if self._timeout_task and not self._timeout_task.done():
                self._timeout_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._timeout_task
            self._closed_event.set()

    async def _drain_card_callbacks(self, card: Card) -> None:
        """Drain and await all pending callbacks queued on a card."""
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

    async def _dispatch(self, event: DeckEvent) -> None:
        """Dispatch a single event to the appropriate handler on the active screen."""
        screen = self._current_screen()
        if not screen:
            return

        if isinstance(event, KeyEvent):
            key_slot = screen.keys.get(event.key)
            if key_slot:
                await key_slot.dispatch(event.pressed)
                if key_slot.is_dirty:
                    await self.refresh()

        elif isinstance(event, EncoderTurnEvent):
            encoder = screen.encoders.get(event.encoder)
            if encoder:
                await encoder.dispatch_turn(event.direction)
            if screen.touch_strip is not None:
                card = screen.touch_strip.card(event.encoder)
                await card.dispatch_encoder_turn(event.direction)
                await self._drain_card_callbacks(card)
                if card.is_dirty:
                    await self.refresh()

        elif isinstance(event, EncoderPressEvent):
            encoder = screen.encoders.get(event.encoder)
            if encoder:
                await encoder.dispatch_press(event.pressed)
            if screen.touch_strip is not None:
                card = screen.touch_strip.card(event.encoder)
                if event.pressed:
                    await card.dispatch_encoder_press()
                else:
                    await card.dispatch_encoder_release()
                await self._drain_card_callbacks(card)
                if card.is_dirty:
                    await self.refresh()

        elif isinstance(event, TouchEvent):
            if screen.touch_strip is not None and self._metrics is not None:
                zone = event.compute_zone(self._metrics)
                card = screen.touch_strip.card(zone)
                await card.dispatch_touch(event)
