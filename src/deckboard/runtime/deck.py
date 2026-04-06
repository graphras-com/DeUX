"""Deck class: main entry point for the deckboard library."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from StreamDeck.DeviceManager import DeviceManager

from ..render.icons import IconManager
from ..render.key_renderer import render_blank_key, render_key_image
from ..render.metrics import TOUCHSCREEN_HEIGHT, TOUCHSCREEN_WIDTH
from ..render.touch_renderer import compose_touchstrip
from .device_info import DeviceInfo
from .events import (
    DeckEvent,
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from .transport import AsyncTransport

if TYPE_CHECKING:
    from ..ui.cards.base import Card
    from ..ui.controls.key_slot import KeySlot
    from ..ui.screen import Screen

logger = logging.getLogger(__name__)

# Stream Deck+ constants
_KEY_COUNT = 8
_ENCODER_COUNT = 4


class DeckError(Exception):
    """Raised for deck-level errors."""


class Deck:
    """High-level, asyncio-native interface to an Elgato Stream Deck+.

    Usage::

        async with Deck() as deck:
            main = deck.screen("main")
            main.key(0).set_icon("mdi:home")

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
        device_type: str = "Stream Deck +",
        device_index: int = 0,
        brightness: int = 80,
        icon_cache_dir: str | Path | None = None,
    ) -> None:
        """
        Args:
            device_type: Stream Deck model to search for.
            device_index: If multiple decks match, which one to use.
            brightness: Initial brightness (0-100).
            icon_cache_dir: Override the default icon cache directory.
        """
        # Lazy import to avoid circular dependency at module level
        from ..ui.screen import Screen

        self._device_type = device_type
        self._device_index = device_index
        self._brightness = brightness
        self._device: Any = None  # low-level StreamDeck object
        self._transport: AsyncTransport | None = None
        self._event_task: asyncio.Task | None = None
        self._closed_event = asyncio.Event()
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=2)

        # Icon manager
        self.icons = IconManager(cache_dir=icon_cache_dir)

        # Debug grid overlay
        self._debug_grid = False

        # Screens
        self._screens: dict[str, Screen] = {}
        self._active_screen: Screen | None = None
        self._pages = self._screens
        self._active_page: Screen | None = None

    # -- Async context manager ---------------------------------------------

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

        # Filter for target device type
        matching = [d for d in devices if d.DECK_TYPE == self._device_type]
        if not matching:
            available = [d.DECK_TYPE for d in devices]
            raise DeckError(f"No '{self._device_type}' found. Available: {available}")

        if self._device_index >= len(matching):
            raise DeckError(
                f"Device index {self._device_index} out of range "
                f"(found {len(matching)} matching devices)"
            )

        self._device = matching[self._device_index]

        # Open device (blocking)
        await loop.run_in_executor(self._executor, self._device.open)
        await loop.run_in_executor(self._executor, self._device.reset)
        await loop.run_in_executor(
            self._executor, self._device.set_brightness, self._brightness
        )

        logger.info(
            "Opened %s (serial: %s, firmware: %s)",
            self._device.deck_type(),
            self._device.get_serial_number(),
            self._device.get_firmware_version(),
        )

        # Set up async transport bridge
        self._transport = AsyncTransport(self._device, loop)
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

        # Close icon HTTP client
        await self.icons.close()

        self._closed_event.set()
        self._executor.shutdown(wait=False)
        logger.info("Deck stopped")

    async def wait_closed(self) -> None:
        """Block until the deck is closed (e.g. by stop() or disconnect)."""
        await self._closed_event.wait()

    # -- Device info -------------------------------------------------------

    @property
    def info(self) -> DeviceInfo:
        """Get device information."""
        if not self._device:
            raise DeckError("Device not opened")
        return DeviceInfo(
            deck_type=self._device.deck_type(),
            serial=self._device.get_serial_number(),
            firmware=self._device.get_firmware_version(),
            key_count=self._device.key_count(),
            key_layout=self._device.key_layout(),
            encoder_count=self._device.dial_count(),
            key_pixel_size=(
                self._device.KEY_PIXEL_WIDTH,
                self._device.KEY_PIXEL_HEIGHT,
            ),
            touchscreen_size=(
                self._device.TOUCHSCREEN_PIXEL_WIDTH,
                self._device.TOUCHSCREEN_PIXEL_HEIGHT,
            ),
            key_image_format=self._device.KEY_IMAGE_FORMAT,
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
            await loop.run_in_executor(
                self._executor, self._device.set_brightness, self._brightness
            )

    # -- Debug grid --------------------------------------------------------

    @property
    def debug_grid(self) -> bool:
        """Whether a debug alignment grid is drawn over rendered images."""
        return self._debug_grid

    @debug_grid.setter
    def debug_grid(self, value: bool) -> None:
        self._debug_grid = value

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
            self._screens[name] = Screen(name)
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
        await self._render_touchscreen()

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

        loop = asyncio.get_running_loop()

        for key_index in range(_KEY_COUNT):
            key_slot = screen.keys.get(key_index)
            if key_slot and (key_slot.icon_name or key_slot.label):
                await self._render_key(key_slot)
            else:
                # Blank key
                image_bytes = render_blank_key(debug_grid=self._debug_grid)
                await loop.run_in_executor(
                    self._executor,
                    self._device.set_key_image,
                    key_index,
                    image_bytes,
                )

    async def _render_key(self, key_slot: KeySlot) -> None:
        """Render a single key and push to the device."""
        if not self._device:
            return

        icon_img = None
        if key_slot.icon_name:
            icon_img = await self.icons.get(
                key_slot.icon_name, color=key_slot.icon_color
            )

        image_bytes = render_key_image(
            icon=icon_img,
            label=key_slot.label,
            debug_grid=self._debug_grid,
        )
        key_slot.set_rendered_image(image_bytes)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            self._device.set_key_image,
            key_slot.index,
            image_bytes,
        )

    async def _render_touchscreen(self) -> None:
        """Render and push the full touch-strip image for the active screen."""
        screen = self._current_screen()
        if not self._device or not screen:
            return

        card_images = []
        for card in screen.cards:
            await card.prepare_assets(self.icons)
            img = card.render()
            card.set_rendered(img)
            card_images.append(img)

        touchstrip_bytes = compose_touchstrip(card_images, debug_grid=self._debug_grid)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            self._device.set_touchscreen_image,
            touchstrip_bytes,
            0,
            0,
            TOUCHSCREEN_WIDTH,
            TOUCHSCREEN_HEIGHT,
        )

    async def refresh(self) -> None:
        """Re-render and push all dirty controls on the active screen.

        Call this after changing key icons/labels or card values
        if you need immediate updates outside of ``set_screen()``.
        Also drains any pending callbacks queued by programmatic
        ``set_value()`` calls on range controls.
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
                await self._render_key(key_slot)

        # Render the touch strip if any card is dirty
        if screen.touch_strip.any_dirty:
            await self._render_touchscreen()

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
        finally:
            self._closed_event.set()

    async def _drain_card_callbacks(self, card: Card) -> None:
        """Drain and await all pending callbacks queued on a card.

        Callbacks are enqueued by child elements (e.g. range controls) when
        their value changes synchronously.  This method pops them all
        and awaits each in order.
        """
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

    async def _drain_widget_callbacks(self, card: Card) -> None:
        """Backward-compatible private helper used by existing tests."""
        await self._drain_card_callbacks(card)

    async def _dispatch(self, event: DeckEvent) -> None:
        """Dispatch a single event to the appropriate handler on the active screen."""
        screen = self._current_screen()
        if not screen:
            return

        if isinstance(event, KeyEvent):
            key_slot = screen.keys.get(event.key)
            if key_slot:
                await key_slot.dispatch(event.pressed)

        elif isinstance(event, EncoderTurnEvent):
            encoder = screen.encoders.get(event.encoder)
            if encoder:
                await encoder.dispatch_turn(event.direction)
            card = screen.touch_strip.card(event.encoder)
            await card.dispatch_encoder_turn(event.direction)
            await self._drain_card_callbacks(card)
            if card.is_dirty:
                await self.refresh()

        elif isinstance(event, EncoderPressEvent):
            encoder = screen.encoders.get(event.encoder)
            if encoder:
                await encoder.dispatch_press(event.pressed)
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
            zone = event.zone
            card = screen.touch_strip.card(zone)
            await card.dispatch_touch(event)
