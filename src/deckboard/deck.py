"""Deck class: main entry point for the deckboard library."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from StreamDeck.DeviceManager import DeviceManager

from .runtime.transport import AsyncTransport
from .button import Button
from .icon import IconManager
from .render.metrics import TOUCHSCREEN_HEIGHT, TOUCHSCREEN_WIDTH
from .render.touch_renderer import compose_touchstrip
from .image import (
    render_blank_key,
    render_key_image,
)
from .page import Page, Screen
from .touchscreen import Widget
from .types import (
    DeckEvent,
    DeviceInfo,
    DialPressEvent,
    DialTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)

logger = logging.getLogger(__name__)

# Stream Deck+ constants
_KEY_COUNT = 8
_DIAL_COUNT = 4


class DeckError(Exception):
    """Raised for deck-level errors."""


class Deck:
    """High-level, asyncio-native interface to an Elgato Stream Deck+.

    Usage::

        async with Deck() as deck:
            main = deck.page("main")
            main.button(0).set_icon("mdi:home")

            @main.button(0).on_press
            async def on_home():
                print("Home pressed!")

            await deck.set_page("main")
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
        self._pages: dict[str, Page] = {}
        self._active_page: Page | None = None
        self._screens = self._pages
        self._active_screen: Screen | None = None

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
            dial_count=self._device.dial_count(),
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
        if name not in self._pages:
            self._pages[name] = Screen(name)
        return self._pages[name]

    def page(self, name: str) -> Page:
        """Compatibility alias for :meth:`screen`."""
        return self.screen(name)

    async def set_screen(self, name: str) -> None:
        """Switch to a named screen, rendering all keys and cards.

        Args:
            name: Screen name (must already exist via ``deck.screen(name)``).
        """
        if name not in self._pages:
            raise DeckError(f"Screen '{name}' does not exist")

        self._active_page = self._pages[name]
        self._active_screen = self._active_page
        logger.info("Switching to screen: %s", name)

        # Render all keys and cards for this screen
        await self._render_all_buttons()
        await self._render_touchscreen()

    async def set_page(self, name: str) -> None:
        """Compatibility alias for :meth:`set_screen`."""
        try:
            await self.set_screen(name)
        except DeckError as exc:
            message = str(exc).replace("Screen", "Page").replace("screen", "page")
            raise DeckError(message) from exc

    @property
    def active_screen(self) -> Screen | None:
        return self._active_screen

    @property
    def active_page(self) -> Page | None:
        return self._active_page

    # -- Rendering ---------------------------------------------------------

    async def _render_all_buttons(self) -> None:
        """Render and push all button images for the active page."""
        if not self._device or not self._active_page:
            return

        loop = asyncio.get_running_loop()

        for key_index in range(_KEY_COUNT):
            button = self._active_page.keys.get(key_index)
            if button and (button.icon_name or button.label):
                await self._render_button(button)
            else:
                # Blank key
                image_bytes = render_blank_key(debug_grid=self._debug_grid)
                await loop.run_in_executor(
                    self._executor,
                    self._device.set_key_image,
                    key_index,
                    image_bytes,
                )

    async def _render_button(self, button: Button) -> None:
        """Render a single button and push to the device."""
        if not self._device:
            return

        icon_img = None
        if button.icon_name:
            icon_img = await self.icons.get(button.icon_name, color=button.icon_color)

        image_bytes = render_key_image(
            icon=icon_img,
            label=button.label,
            debug_grid=self._debug_grid,
        )
        button.set_rendered_image(image_bytes)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            self._device.set_key_image,
            button.index,
            image_bytes,
        )

    async def _render_touchscreen(self) -> None:
        """Render and push the full touchscreen image for the active page."""
        if not self._device or not self._active_page:
            return

        card_images = []
        for card in self._active_page.cards:
            await card.prepare_assets(self.icons)
            img = card.render()
            card.set_rendered(img)
            card_images.append(img)

        touchscreen_bytes = compose_touchstrip(card_images, debug_grid=self._debug_grid)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            self._device.set_touchscreen_image,
            touchscreen_bytes,
            0,
            0,
            TOUCHSCREEN_WIDTH,
            TOUCHSCREEN_HEIGHT,
        )

    async def refresh(self) -> None:
        """Re-render and push all dirty buttons and widgets on the active page.

        Call this after changing button icons/labels or widget values
        if you need immediate updates outside of ``set_page()``.
        Also drains any pending callbacks queued by programmatic
        ``set_value()`` calls on sliders.
        """
        if not self._active_page:
            return

        # Drain pending callbacks from all cards (programmatic set_value)
        for card in self._active_page.cards:
            await self._drain_widget_callbacks(card)

        # Render dirty keys
        for button in self._active_page.keys.values():
            if button.is_dirty:
                await self._render_button(button)

        # Render the touch strip if any card is dirty
        if self._active_page.touch_strip.any_dirty:
            await self._render_touchscreen()

    # -- Event dispatch loop -----------------------------------------------

    async def _check_timeouts(self) -> None:
        """Check all widget selection timeouts on the active page.

        If any widget's active slider reverts to its default because the
        timeout elapsed, a refresh is triggered so the display updates.
        """
        page = self._active_page
        if not page:
            return
        any_changed = False
        for card in page.cards:
            if card.check_selection_timeout():
                any_changed = True
        if any_changed:
            await self.refresh()

    async def _event_loop(self) -> None:
        """Main event dispatch loop: reads events from the transport queue
        and dispatches them to the active page's handlers."""
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

                if not self._active_page:
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

    async def _drain_widget_callbacks(self, widget: Widget) -> None:
        """Drain and await all pending callbacks queued on a widget.

        Callbacks are enqueued by child elements (e.g. sliders) when
        their value changes synchronously.  This method pops them all
        and awaits each in order.
        """
        for handler, args in widget.drain_pending_callbacks():
            await handler(*args)

    async def _dispatch(self, event: DeckEvent) -> None:
        """Dispatch a single event to the appropriate handler on the active page."""
        page = self._active_page
        if not page:
            return

        if isinstance(event, KeyEvent):
            button = page.keys.get(event.key)
            if button:
                await button.dispatch(event.pressed)

        elif isinstance(event, DialTurnEvent):
            dial = page.encoders.get(event.dial)
            if dial:
                await dial.dispatch_turn(event.direction)
            card = page.touch_strip.card(event.dial)
            await card.dispatch_dial_turn(event.direction)
            await self._drain_widget_callbacks(card)
            if card.is_dirty:
                await self.refresh()

        elif isinstance(event, DialPressEvent):
            dial = page.encoders.get(event.dial)
            if dial:
                await dial.dispatch_press(event.pressed)
            if event.pressed:
                card = page.touch_strip.card(event.dial)
                await card.dispatch_dial_press()
                await self._drain_widget_callbacks(card)
                if card.is_dirty:
                    await self.refresh()

        elif isinstance(event, TouchEvent):
            zone = event.zone
            card = page.touch_strip.card(zone)
            await card.dispatch_touch(event)
