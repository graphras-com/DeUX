"""Deck class: per-device handle managed by DeckManager."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from typing import TYPE_CHECKING, Any, cast

from StreamDeck.DeviceManager import DeviceManager

from ..render.key_renderer import render_blank_key
from ..render.metrics import RenderMetrics
from ..render.touch_renderer import compose_touchstrip
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
    from ..ui.cards.base import Card
    from ..ui.controls.key_slot import KeySlot
    from ..ui.screen import Screen

logger = logging.getLogger(__name__)


class DeckError(Exception):
    """Raised for deck-level errors."""


class Deck:
    """Per-device handle for an Elgato Stream Deck.

    Instances are created and managed by :class:`DeckManager`.  Do not
    instantiate ``Deck`` directly — use ``DeckManager.on_connect`` to
    receive connected ``Deck`` instances.

    The ``Deck`` object provides the per-device API for screens, keys,
    encoders, touchscreen cards, brightness, and rendering.
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
        self._closed_event = asyncio.Event()
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._device_lock = asyncio.Lock()

        self._screens: dict[str, Screen] = {}
        self._active_screen: Screen | None = None

    async def start(self) -> None:
        """Discover the device by serial, open it, and start the event loop."""
        if self._running:
            return

        loop = asyncio.get_running_loop()

        devices = await loop.run_in_executor(self._executor, DeviceManager().enumerate)

        if not devices:
            raise DeckError("No Stream Deck devices found")

        visual = [d for d in devices if d.DECK_VISUAL]
        if not visual:
            raise DeckError("No visual Stream Deck devices found")

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

        await loop.run_in_executor(self._executor, self._device.reset)
        await loop.run_in_executor(
            self._executor, self._device.set_brightness, self._brightness
        )

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
            self._event_loop(), name="deckui-events"
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

    async def set_brightness(self, percent: int) -> None:
        """Set screen brightness.

        Parameters
        ----------
        percent
            Brightness level (0-100).
        """
        self._brightness = max(0, min(100, percent))
        if self._device:
            loop = asyncio.get_running_loop()
            async with self._device_lock:
                await loop.run_in_executor(
                    self._executor, self._device.set_brightness, self._brightness
                )

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
        """
        from ..ui.screen import Screen

        if name not in self._screens:
            self._screens[name] = Screen(name, self._caps)
        return self._screens[name]

    async def set_screen(self, name: str) -> None:
        """Switch to a named screen, rendering all keys and cards.

        Parameters
        ----------
        name
            Screen name (must already exist via ``deck.screen(name)``).
        """
        if name not in self._screens:
            raise DeckError(f"Screen '{name}' does not exist")

        self._active_screen = self._screens[name]
        logger.info("Switching to screen: %s", name)

        await self._render_all_keys()
        if self._active_screen.touch_strip is not None:
            await self._render_touchscreen()
        if self._active_screen.info_screen is not None:
            await self._render_info_screen()

    @property
    def active_screen(self) -> Screen | None:
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

        loop = asyncio.get_running_loop()
        metrics = self._metrics

        for key_index in range(caps.key_count):
            key_slot = screen.keys.get(key_index)
            if key_slot and self._is_dui_key(key_slot):
                await self._render_dui_key(key_slot)
            else:
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
    def _is_dui_key(key_slot: KeySlot) -> bool:
        """Check whether a key slot is a DuiKey."""
        return getattr(key_slot, "has_dui_content", False)

    @staticmethod
    def _is_animating(obj: Any) -> bool:
        """Check whether a card or key has an active spinner animation."""
        return getattr(obj, "is_animating", False)

    async def _render_dui_key(self, key_slot: KeySlot) -> None:
        """Render a DuiKey and push to the device."""
        if not self._device:
            return

        dui_key = cast("DuiKey", key_slot)

        # Skip rendering if a spinner animation is active
        if self._is_animating(dui_key):
            return

        # Wire up push_fn for spinner animation support
        if not dui_key._push_fn:  # noqa: SLF001
            key_index = dui_key.index

            async def _push_key_frame(frame_bytes: bytes) -> None:
                loop = asyncio.get_running_loop()
                async with self._device_lock:
                    await loop.run_in_executor(
                        self._executor,
                        self._device.set_key_image,
                        key_index,
                        frame_bytes,
                    )

            dui_key.set_push_fn(_push_key_frame)

        image_bytes = dui_key.render_image(
            key_size=self._caps.key_size if self._caps else (120, 120),
            image_format=self._caps.key_image_format if self._caps else "JPEG",
        )
        dui_key.set_rendered_image(image_bytes)

        loop = asyncio.get_running_loop()
        async with self._device_lock:
            await loop.run_in_executor(
                self._executor,
                self._device.set_key_image,
                dui_key.index,
                image_bytes,
            )

    async def _render_touchscreen(self) -> None:
        """Render and push the full touch-strip image for the active screen."""
        screen = self._current_screen()
        if not self._device or not screen or not self._metrics:
            return

        if screen.touch_strip is None:
            return

        metrics = self._metrics

        # Wire up push_fn for each DuiCard that needs spinner support
        for card_idx, card in enumerate(screen.cards):
            from ..dui.card import DuiCard

            if isinstance(card, DuiCard) and card._push_fn is None:  # noqa: SLF001
                x_pos = metrics.margin_left + card_idx * (
                    metrics.panel_width + metrics.panel_gap
                )
                y_pos = metrics.margin_top

                async def _make_push(x: int, y: int, w: int, h: int) -> PushFn:
                    async def _push_card_frame(frame_bytes: bytes) -> None:
                        loop = asyncio.get_running_loop()
                        async with self._device_lock:
                            await loop.run_in_executor(
                                self._executor,
                                self._device.set_touchscreen_image,
                                frame_bytes,
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
                )
                card.set_push_fn(push_fn)

        card_images = []
        for card in screen.cards:
            # Skip re-rendering cards with active spinner animations
            if self._is_animating(card):
                card_images.append(card.rendered)
                continue
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

        for card in screen.cards:
            await self._drain_card_callbacks(card)

        for key_slot in screen.keys.values():
            if key_slot.is_dirty and self._is_dui_key(key_slot):
                await self._render_dui_key(key_slot)

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
                except TimeoutError:
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
