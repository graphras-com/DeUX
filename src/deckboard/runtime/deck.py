"""Deck class: main entry point for the deckboard library."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from StreamDeck.DeviceManager import DeviceManager

from ..render.key_renderer import render_blank_key, render_key_image
from ..render.metrics import RenderMetrics
from ..render.touch_renderer import compose_touchstrip
from .capabilities import DeviceCapabilities
from .device_info import DeviceInfo
from .events import (
    AsyncHandler,
    DeckEvent,
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from .transport import AsyncTransport

if TYPE_CHECKING:
    from ..dsui.key import DsuiKey
    from ..ui.cards.base import Card
    from ..ui.controls.key_slot import KeySlot
    from ..ui.screen import Screen

logger = logging.getLogger(__name__)


class DeckError(Exception):
    """Raised for deck-level errors."""


class Deck:
    """High-level, asyncio-native interface to Elgato Stream Deck devices.

    Automatically discovers and connects to the first available visual
    Stream Deck device.  Adapts key count, encoder count, touchscreen
    dimensions, and info screen support to the connected hardware.

    Usage::

        async with Deck() as deck:
            main = deck.screen("main")

            @main.key(0).on_press
            async def on_home():
                print("Home pressed!")

            await deck.set_screen("main")
            await deck.wait_closed()

    Or without context manager::

        deck = Deck()
        await deck.start()
        ...
        await deck.stop()
    """

    def __init__(
        self,
        serial_number: str | None = None,
        device_index: int = 0,
        brightness: int = 80,
        deck_type: str | None = None,
        auto_reconnect: bool = False,
        reconnect_poll_interval: float = 2.0,
    ) -> None:
        """
        Args:
            serial_number: Target a specific device by serial number.
                If ``None``, the first available visual device is used.
            device_index: If multiple visual decks are found and no
                serial_number is given, which one to use (0-based).
            brightness: Initial brightness (0-100).
            deck_type: If set, only connect to devices matching this
                type string (e.g. ``"Stream Deck +"``).
            auto_reconnect: If ``True``, automatically attempt to
                reconnect when the device disconnects.
            reconnect_poll_interval: Seconds between reconnection
                attempts (default 2.0).
        """
        self._serial_number = serial_number
        self._device_index = device_index
        self._brightness = brightness
        self._deck_type = deck_type
        self._auto_reconnect = auto_reconnect
        self._reconnect_poll_interval = reconnect_poll_interval
        self._device: Any = None  # low-level StreamDeck object
        self._caps: DeviceCapabilities | None = None
        self._metrics: RenderMetrics | None = None
        self._transport: AsyncTransport | None = None
        self._event_task: asyncio.Task | None = None
        self._closed_event = asyncio.Event()
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._device_lock = asyncio.Lock()

        # Reconnect state
        self._reconnecting = False
        self._on_reconnect_handler: AsyncHandler | None = None
        self._on_disconnect_handler: AsyncHandler | None = None

        # Screens
        self._screens: dict[str, Screen] = {}
        self._active_screen: Screen | None = None
        self._pages = self._screens
        self._active_page: Screen | None = None

    # -- Async context manager ---------------------------------------------

    @classmethod
    async def wait_for_device(
        cls,
        serial_number: str | None = None,
        deck_type: str | None = None,
        poll_interval: float = 2.0,
        brightness: int = 80,
        auto_reconnect: bool = False,
    ) -> Deck:
        """Wait for a matching device to be connected, then return a started Deck.

        Polls for devices periodically until one matching the given
        criteria is found.

        Args:
            serial_number: Wait for a device with this serial.
            deck_type: Wait for a device of this type.
            poll_interval: Seconds between discovery attempts.
            brightness: Initial brightness (0-100).
            auto_reconnect: Enable auto-reconnect on the returned Deck.

        Returns:
            A started :class:`Deck` instance.
        """
        while True:
            try:
                deck = cls(
                    serial_number=serial_number,
                    deck_type=deck_type,
                    brightness=brightness,
                    auto_reconnect=auto_reconnect,
                )
                await deck.start()
                return deck
            except DeckError:
                logger.debug(
                    "No matching device found, retrying in %.1fs...",
                    poll_interval,
                )
                await asyncio.sleep(poll_interval)

    async def __aenter__(self) -> Deck:
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.stop()

    # -- Lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Discover the device, open it, and start the event loop."""
        if self._running:
            return

        loop = asyncio.get_running_loop()

        # Discover devices (blocking call, run in executor)
        devices = await loop.run_in_executor(self._executor, DeviceManager().enumerate)

        if not devices:
            raise DeckError("No Stream Deck devices found")

        # Filter for visual devices (skip Pedal)
        visual = [d for d in devices if d.DECK_VISUAL]
        if not visual:
            raise DeckError("No visual Stream Deck devices found")

        # Filter by deck type if specified
        if self._deck_type is not None:
            visual = [d for d in visual if d.DECK_TYPE == self._deck_type]
            if not visual:
                raise DeckError(
                    f"No devices of type '{self._deck_type}' found"
                )

        # Select device
        if self._serial_number is not None:
            # Find by serial number — need to open each to read serial
            target = None
            for d in visual:
                try:
                    await loop.run_in_executor(self._executor, d.open)
                    serial = d.get_serial_number()
                    if serial == self._serial_number:
                        target = d
                        break
                    await loop.run_in_executor(self._executor, d.close)
                except Exception:
                    continue
            if target is None:
                raise DeckError(
                    f"No device with serial '{self._serial_number}' found"
                )
            self._device = target
        else:
            if self._device_index >= len(visual):
                raise DeckError(
                    f"Device index {self._device_index} out of range "
                    f"(found {len(visual)} visual devices)"
                )
            self._device = visual[self._device_index]
            await loop.run_in_executor(self._executor, self._device.open)

        await loop.run_in_executor(self._executor, self._device.reset)
        await loop.run_in_executor(
            self._executor, self._device.set_brightness, self._brightness
        )

        # Build capabilities and metrics
        self._caps = DeviceCapabilities.from_device(self._device)
        self._metrics = RenderMetrics(self._caps)

        # Remember serial for reconnection
        if self._serial_number is None:
            self._serial_number = self._device.get_serial_number()

        logger.info(
            "Opened %s (serial: %s, firmware: %s, keys: %d, dials: %d)",
            self._device.deck_type(),
            self._device.get_serial_number(),
            self._device.get_firmware_version(),
            self._caps.key_count,
            self._caps.dial_count,
        )

        # Set up async transport bridge
        self._transport = AsyncTransport(self._device, loop, self._caps)
        self._transport.start()

        self._running = True
        self._closed_event.clear()

        # Start event dispatch loop
        self._event_task = asyncio.create_task(
            self._event_loop(), name="deckboard-events"
        )

    async def stop(self) -> None:
        """Stop the event loop and close the device."""
        if not self._running:
            return

        self._running = False

        # Stop transport
        if self._transport:
            self._transport.stop()

        # Cancel event task
        if self._event_task and not self._event_task.done():
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.CancelledError:
                pass

        # Close device (blocking)
        if self._device:
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(self._executor, self._device.reset)
                await loop.run_in_executor(self._executor, self._device.close)
            except Exception as e:
                logger.warning("Error closing device: %s", e)

        self._closed_event.set()
        self._executor.shutdown(wait=False)
        logger.info("Deck stopped")

    async def wait_closed(self) -> None:
        """Block until the deck is closed (e.g. by stop() or disconnect)."""
        await self._closed_event.wait()

    # -- Reconnect / disconnect callbacks ----------------------------------

    def on_reconnect(self, handler: AsyncHandler) -> AsyncHandler:
        """Register a callback invoked after a successful reconnection.

        Can be used as a decorator::

            @deck.on_reconnect
            async def handle_reconnect():
                await deck.set_screen("main")
        """
        self._on_reconnect_handler = handler
        return handler

    def on_disconnect(self, handler: AsyncHandler) -> AsyncHandler:
        """Register a callback invoked when the device disconnects.

        Can be used as a decorator::

            @deck.on_disconnect
            async def handle_disconnect():
                print("Device lost!")
        """
        self._on_disconnect_handler = handler
        return handler

    async def _reconnect_loop(self) -> None:
        """Poll for the device to reappear and re-open it."""
        logger.info(
            "Reconnect loop started (serial=%s, poll=%.1fs)",
            self._serial_number,
            self._reconnect_poll_interval,
        )
        self._reconnecting = True

        loop = asyncio.get_running_loop()

        while self._running:
            await asyncio.sleep(self._reconnect_poll_interval)
            if not self._running:
                break

            try:
                devices = await loop.run_in_executor(
                    self._executor, DeviceManager().enumerate
                )
                visual = [d for d in devices if d.DECK_VISUAL]

                if self._deck_type is not None:
                    visual = [d for d in visual if d.DECK_TYPE == self._deck_type]

                target = None
                for d in visual:
                    try:
                        await loop.run_in_executor(self._executor, d.open)
                        serial = d.get_serial_number()
                        if serial == self._serial_number:
                            target = d
                            break
                        await loop.run_in_executor(self._executor, d.close)
                    except Exception:
                        continue

                if target is None:
                    continue

                # Re-open successful
                self._device = target
                await loop.run_in_executor(self._executor, self._device.reset)
                await loop.run_in_executor(
                    self._executor, self._device.set_brightness, self._brightness
                )

                self._caps = DeviceCapabilities.from_device(self._device)
                self._metrics = RenderMetrics(self._caps)

                self._transport = AsyncTransport(self._device, loop, self._caps)
                self._transport.start()

                self._reconnecting = False

                logger.info(
                    "Reconnected to %s (serial: %s)",
                    self._device.deck_type(),
                    self._serial_number,
                )

                # Re-render active screen
                if self._active_screen:
                    await self._render_all_keys()
                    if self._active_screen.touch_strip is not None:
                        await self._render_touchscreen()
                    if self._active_screen.info_screen is not None:
                        await self._render_info_screen()

                # Invoke user callback
                if self._on_reconnect_handler:
                    try:
                        await self._on_reconnect_handler()
                    except Exception:
                        logger.exception("Error in reconnect handler")

                return  # Exit reconnect loop, resume event loop

            except Exception:
                logger.debug("Reconnect attempt failed, retrying...")
                continue

        self._reconnecting = False

    # -- Device capabilities -----------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Whether the device is currently connected and operational."""
        return self._device is not None and self._running and not self._reconnecting

    @property
    def is_reconnecting(self) -> bool:
        """Whether the deck is currently attempting to reconnect."""
        return self._reconnecting

    @property
    def capabilities(self) -> DeviceCapabilities:
        """The device capabilities for the connected device.

        Raises:
            DeckError: If the device is not opened.
        """
        if self._caps is None:
            raise DeckError("Device not opened")
        return self._caps

    @property
    def metrics(self) -> RenderMetrics:
        """Rendering metrics for the connected device.

        Raises:
            DeckError: If the device is not opened.
        """
        if self._metrics is None:
            raise DeckError("Device not opened")
        return self._metrics

    # -- Device info -------------------------------------------------------

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

    # -- Brightness --------------------------------------------------------

    @property
    def brightness(self) -> int:
        """Current brightness level (0-100)."""
        return self._brightness

    async def set_brightness(self, percent: int) -> None:
        """Set screen brightness (0-100)."""
        self._brightness = max(0, min(100, percent))
        if self._device:
            loop = asyncio.get_running_loop()
            async with self._device_lock:
                await loop.run_in_executor(
                    self._executor, self._device.set_brightness, self._brightness
                )

    # -- Screen management -------------------------------------------------

    def screen(self, name: str) -> Screen:
        """Get or create a screen by name.

        Args:
            name: Screen name.

        Returns:
            The Screen instance.
        """
        from ..ui.screen import Screen

        if name not in self._screens:
            self._screens[name] = Screen(name, self._caps)
        return self._screens[name]

    async def set_screen(self, name: str) -> None:
        """Switch to a named screen, rendering all keys and cards.

        Args:
            name: Screen name (must already exist via ``deck.screen(name)``).
        """
        if name not in self._screens:
            raise DeckError(f"Screen '{name}' does not exist")

        self._active_screen = self._screens[name]
        self._active_page = self._active_screen
        logger.info("Switching to screen: %s", name)

        # Render all keys and cards for this screen
        await self._render_all_keys()
        if self._active_screen.touch_strip is not None:
            await self._render_touchscreen()
        if self._active_screen.info_screen is not None:
            await self._render_info_screen()

    @property
    def active_screen(self) -> Screen | None:
        return self._active_screen

    def _current_screen(self) -> Screen | None:
        return self._active_screen or self._active_page

    # -- Rendering ---------------------------------------------------------

    async def _render_all_keys(self) -> None:
        """Render and push all key images for the active screen."""
        screen = self._current_screen()
        if not self._device or not screen:
            return

        caps = self._caps
        if caps is None:
            return

        loop = asyncio.get_running_loop()
        metrics = self._metrics

        for key_index in range(caps.key_count):
            key_slot = screen.keys.get(key_index)
            if key_slot and self._is_dsui_key(key_slot):
                await self._render_dsui_key(key_slot)
            else:
                # Blank key
                image_bytes = render_blank_key(
                    key_size=metrics.key_size if metrics else (120, 120),
                    image_format=caps.key_image_format,
                )
                async with self._device_lock:
                    await loop.run_in_executor(
                        self._executor,
                        self._device.set_key_image,
                        key_index,
                        image_bytes,
                    )

    @staticmethod
    def _is_dsui_key(key_slot: KeySlot) -> bool:
        """Check whether a key slot is a DsuiKey."""
        return getattr(key_slot, "has_dsui_content", False)

    async def _render_dsui_key(self, key_slot: KeySlot) -> None:
        """Render a DsuiKey and push to the device."""
        if not self._device:
            return

        from ..dsui.key import DsuiKey

        dsui_key: DsuiKey = key_slot  # type: ignore[assignment]
        image_bytes = dsui_key.render_image(
            key_size=self._caps.key_size if self._caps else (120, 120),
            image_format=self._caps.key_image_format if self._caps else "JPEG",
        )
        dsui_key.set_rendered_image(image_bytes)

        loop = asyncio.get_running_loop()
        async with self._device_lock:
            await loop.run_in_executor(
                self._executor,
                self._device.set_key_image,
                dsui_key.index,
                image_bytes,
            )

    async def _render_touchscreen(self) -> None:
        """Render and push the full touch-strip image for the active screen."""
        screen = self._current_screen()
        if not self._device or not screen or not self._metrics:
            return

        if screen.touch_strip is None:
            return

        card_images = []
        for card in screen.cards:
            await card.prepare_assets()
            img = card.render()
            card.set_rendered(img)
            card_images.append(img)

        metrics = self._metrics
        touchstrip_bytes = compose_touchstrip(
            card_images,
            background=screen.touch_strip.background_color,
            touchscreen_width=metrics.touchscreen_width,
            touchscreen_height=metrics.touchscreen_height,
            panel_count=metrics.panel_count,
            panel_width=metrics.panel_width,
            margin_left=metrics.margin_left,
            margin_top=metrics.margin_top,
            panel_gap=metrics.panel_gap,
            image_format=self._caps.touchscreen_image_format if self._caps else "JPEG",
        )

        loop = asyncio.get_running_loop()
        async with self._device_lock:
            await loop.run_in_executor(
                self._executor,
                self._device.set_touchscreen_image,
                touchstrip_bytes,
                0,
                0,
                metrics.touchscreen_width,
                metrics.touchscreen_height,
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

        loop = asyncio.get_running_loop()
        async with self._device_lock:
            await loop.run_in_executor(
                self._executor,
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

        # Drain pending callbacks from all cards (programmatic set_value)
        for card in screen.cards:
            await self._drain_card_callbacks(card)

        # Render dirty keys
        for key_slot in screen.keys.values():
            if key_slot.is_dirty:
                if self._is_dsui_key(key_slot):
                    await self._render_dsui_key(key_slot)

        # Render the touch strip if any card is dirty
        if screen.touch_strip is not None and screen.touch_strip.any_dirty:
            await self._render_touchscreen()

        # Render info screen if dirty
        if screen.info_screen is not None and screen.info_screen.is_dirty:
            await self._render_info_screen()

    # -- Event dispatch loop -----------------------------------------------

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

    async def _event_loop(self) -> None:
        """Dispatch transport events to the active screen handlers."""
        if not self._transport:
            return

        try:
            while self._running:
                try:
                    event = await asyncio.wait_for(
                        self._transport.queue.get(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    await self._check_timeouts()
                    continue

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
            if self._auto_reconnect and self._running:
                await self._handle_disconnect()
                return
        finally:
            self._closed_event.set()

    async def _handle_disconnect(self) -> None:
        """Handle device disconnection: clean up and optionally reconnect."""
        logger.info("Device disconnected (serial=%s)", self._serial_number)

        # Clean up transport
        if self._transport:
            try:
                self._transport.stop()
            except Exception:
                pass
            self._transport = None

        # Clean up device
        if self._device:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(self._executor, self._device.close)
            except Exception:
                pass
            self._device = None

        # Invoke user disconnect callback
        if self._on_disconnect_handler:
            try:
                await self._on_disconnect_handler()
            except Exception:
                logger.exception("Error in disconnect handler")

        # Attempt reconnection
        await self._reconnect_loop()

        if self._running and not self._reconnecting:
            # Reconnected — restart event loop
            self._closed_event.clear()
            self._event_task = asyncio.create_task(
                self._event_loop(), name="deckboard-events"
            )
        else:
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
                card.set_refresh_callback(self.refresh)
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
