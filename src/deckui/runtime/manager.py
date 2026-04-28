"""DeckManager: the sole entry point for managing Stream Deck devices."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from StreamDeck.DeviceManager import DeviceManager

from .deck import Deck, DeckError
from .device_info import DeviceInfo

if TYPE_CHECKING:
    from .events import AsyncHandler

logger = logging.getLogger(__name__)

ConnectHandler = Callable[["Deck"], Any]


class DeckManager:
    """The main entry point for the deckui library.

    Manages one or more Stream Deck devices with automatic discovery,
    hot-plug detection, and reconnection.  Register ``on_connect`` and
    ``on_disconnect`` handlers, then start the manager.

    Examples
    --------
    ::

        manager = DeckManager()

        @manager.on_connect(deck_type="Stream Deck +")
        async def handle(deck: Deck):
            screen = deck.screen("main")

            @screen.key(0).on_press
            async def on_home():
                print("Home pressed!")

            await deck.set_screen("main")

        @manager.on_disconnect
        async def lost(info: DeviceInfo):
            print(f"Lost: {info.serial}")

        async with manager:
            await manager.wait_closed()

    Parameters
    ----------
    poll_interval
        Seconds between device scans (default 2.0).
    brightness
        Default brightness for new Deck instances (0-100).
    auto_reconnect
        If ``True`` (default), automatically reconnect
        devices that disconnect.  The ``on_connect`` handler is
        called again on reconnection.
    """

    def __init__(
        self,
        poll_interval: float = 2.0,
        brightness: int = 80,
        auto_reconnect: bool = True,
    ) -> None:
        self._poll_interval = poll_interval
        self._brightness = brightness
        self._auto_reconnect = auto_reconnect
        self._running = False
        self._closed_event = asyncio.Event()
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._scan_task: asyncio.Task[None] | None = None

        self._decks: dict[str, Deck] = {}

        self._connect_handlers: list[tuple[dict[str, str | None], AsyncHandler]] = []
        self._disconnect_handler: AsyncHandler | None = None

    async def __aenter__(self) -> DeckManager:
        """Start the manager and return it for use as an async context manager."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the manager when exiting the async context."""
        await self.stop()

    async def start(self) -> None:
        """Start the device scanning loop."""
        if self._running:
            return
        self._running = True
        self._closed_event.clear()
        self._scan_task = asyncio.create_task(
            self._scan_loop(), name="deckmanager-scan"
        )
        logger.info("DeckManager started (poll_interval=%.1fs)", self._poll_interval)

    async def stop(self) -> None:
        """Stop scanning and close all managed decks."""
        if not self._running:
            return
        self._running = False

        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._scan_task

        for serial, deck in list(self._decks.items()):
            try:
                await deck.stop()
            except Exception:
                logger.warning("Error stopping deck %s", serial)
        self._decks.clear()

        self._closed_event.set()
        self._executor.shutdown(wait=False)
        logger.info("DeckManager stopped")

    async def wait_closed(self) -> None:
        """Block until the manager is stopped."""
        await self._closed_event.wait()

    def on_connect(
        self,
        *,
        serial: str | None = None,
        deck_type: str | None = None,
    ) -> Callable[[AsyncHandler], AsyncHandler]:
        """Register a callback for when a matching device connects.

        The handler is also called on reconnection when
        ``auto_reconnect`` is enabled.

        Examples
        --------
        ::

            @manager.on_connect(deck_type="Stream Deck +")
            async def handle(deck: Deck):
                ...

        Parameters
        ----------
        serial
            Only match this serial number.
        deck_type
            Only match this device type.

        Returns
        -------
        Callable
            Decorator that registers the handler.
        """
        filters = {"serial": serial, "deck_type": deck_type}

        def decorator(handler: AsyncHandler) -> AsyncHandler:
            self._connect_handlers.append((filters, handler))
            return handler

        return decorator

    @property
    def on_disconnect(self) -> Callable[[AsyncHandler], AsyncHandler]:
        """Register a callback for when a device disconnects.

        Examples
        --------
        ::

            @manager.on_disconnect
            async def handle(info: DeviceInfo):
                ...
        """

        def decorator(handler: AsyncHandler) -> AsyncHandler:
            self._disconnect_handler = handler
            return handler

        return decorator

    @property
    def decks(self) -> dict[str, Deck]:
        """Currently managed decks, keyed by serial number."""
        return dict(self._decks)

    async def _scan_loop(self) -> None:
        """Periodically enumerate devices and manage connections.

        Runs an initial scan immediately, then polls at the configured
        ``poll_interval`` until the manager is stopped or cancelled.
        Sets the closed event on exit so that ``wait_closed()`` unblocks.
        """
        await self._scan_once()

        try:
            while self._running:
                await asyncio.sleep(self._poll_interval)
                if not self._running:
                    break
                await self._scan_once()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Scan loop crashed")
        finally:
            self._closed_event.set()

    async def _scan_once(self) -> None:
        """Execute a single device scan cycle.

        Enumerates all connected Stream Deck devices, detects new
        connections and disconnections, and invokes the appropriate
        registered handlers.  Devices that fail to open are silently
        skipped.
        """
        loop = asyncio.get_running_loop()

        try:
            devices = await loop.run_in_executor(
                self._executor, DeviceManager().enumerate
            )
        except Exception:
            logger.debug("Device enumeration failed")
            return

        visual = [d for d in devices if d.DECK_VISUAL]

        managed_paths: dict[str, str] = {}
        for serial, deck in self._decks.items():
            path = deck.device_path
            if path is not None:
                managed_paths[path] = serial

        connected_serials: set[str] = set()
        device_by_serial: dict[str, Any] = {}

        for d in visual:
            dev_path = d.id()
            if dev_path in managed_paths:
                connected_serials.add(managed_paths[dev_path])
                continue
            try:
                await loop.run_in_executor(self._executor, d.open)
                serial = d.get_serial_number()
                connected_serials.add(serial)
                device_by_serial[serial] = d
                await loop.run_in_executor(self._executor, d.close)
            except Exception:
                continue

        for serial in list(self._decks):
            if serial not in connected_serials:
                deck = self._decks.pop(serial)
                logger.info("Device disconnected: %s", serial)
                try:
                    info = deck.info
                except Exception:
                    info = DeviceInfo(
                        deck_type="unknown",
                        serial=serial,
                        firmware="",
                        key_count=0,
                        key_layout=(0, 0),
                        encoder_count=0,
                        key_pixel_size=(0, 0),
                        touchscreen_size=(0, 0),
                        key_image_format="",
                    )
                with suppress(Exception):
                    await deck.stop()
                if self._disconnect_handler:
                    try:
                        await self._disconnect_handler(info)
                    except Exception:
                        logger.exception("Error in disconnect handler")

        for serial in connected_serials:
            if serial in self._decks:
                continue

            raw_device = device_by_serial.get(serial)
            if raw_device is None:
                continue
            device_type = raw_device.DECK_TYPE

            for filters, handler in self._connect_handlers:
                if filters["serial"] is not None and filters["serial"] != serial:
                    continue
                if (
                    filters["deck_type"] is not None
                    and filters["deck_type"] != device_type
                ):
                    continue

                try:
                    deck = Deck(
                        serial_number=serial,
                        brightness=self._brightness,
                    )
                    await deck.start()
                    self._decks[serial] = deck
                    logger.info("Device connected: %s (%s)", serial, device_type)

                    try:
                        await handler(deck)
                    except Exception:
                        logger.exception("Error in connect handler for %s", serial)
                except DeckError:
                    logger.debug("Failed to start deck for %s", serial)
                except Exception:
                    logger.exception("Unexpected error starting deck %s", serial)
                break
