"""DeckRenderer: extracted rendering logic for Stream Deck devices.

Handles key, touchscreen, and info-screen rendering pipelines,
separated from the lifecycle and event-dispatch responsibilities
of :class:`~deux.runtime.deck.Deck`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, cast

from ..dui.animator import DeviceUnavailable
from ..dui.key import DuiKey
from ..render.context import RenderingContext
from ..render.key_renderer import render_blank_key
from ..render.profiler import RenderProfiler
from ..render.svg_rasterize import set_svg_stylesheet
from ..render.touch_renderer import composite_frame_on_tile
from .hid._ctypes_hidapi import HidApiError

if TYPE_CHECKING:
    from ..dui.animator import PushFn
    from ..render.metrics import RenderMetrics
    from ..ui.cards.base import Card
    from ..ui.controls.key_slot import KeySlot
    from .capabilities import DeviceCapabilities
    from .deck import Deck

logger = logging.getLogger(__name__)


class DeckRenderer:
    """Encapsulates all rendering pipelines for a single :class:`Deck`.

    This class owns the key, touchscreen, and info-screen render methods
    that were previously embedded in ``Deck``.  It operates on the deck's
    device, capabilities, metrics, and active screen via a back-reference
    to the parent ``Deck`` instance.

    Parameters
    ----------
    deck : Deck
        The parent deck instance whose device and state are used for
        rendering.
    """

    #: Minimum interval between touchscreen renders in seconds (~60 fps).
    _MIN_TOUCH_INTERVAL: float = 1.0 / 60.0

    def __init__(self, deck: Deck) -> None:
        self._deck = deck
        self._last_touch_render: float = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_dui_key(key_slot: KeySlot) -> bool:
        """Check whether a key slot is a DuiKey.

        Parameters
        ----------
        key_slot : KeySlot
            The key slot to inspect.

        Returns
        -------
        bool
            ``True`` if *key_slot* is a :class:`DuiKey`.
        """
        return isinstance(key_slot, DuiKey)

    @staticmethod
    def is_animating(obj: Any) -> bool:
        """Check whether a card or key has an active spinner animation.

        Parameters
        ----------
        obj : Any
            Object to inspect (typically a :class:`DuiKey` or
            :class:`Card`).

        Returns
        -------
        bool
            ``True`` if *obj* has ``is_animating`` set to ``True``.
        """
        return getattr(obj, "is_animating", False)

    def _resolve_stylesheet(self) -> str:
        """Resolve the effective CSS stylesheet for the active screen.

        .. deprecated::
            Use :meth:`Deck.resolve_stylesheet` instead.  This method is
            retained as a thin pass-through to avoid breaking downstream
            callers and is scheduled for removal in a future release.

        Returns
        -------
        str
            CSS stylesheet string from the most specific theme.
        """
        return self._deck.resolve_stylesheet()

    # ------------------------------------------------------------------
    # Key rendering
    # ------------------------------------------------------------------

    async def render_all_keys(self) -> None:
        """Render and push all key images for the active screen.

        Key images are rendered concurrently (CPU-bound work offloaded
        to threads), then pushed to the device sequentially to avoid
        visible one-by-one delays.
        """
        deck = self._deck
        screen = deck._current_screen()
        if not deck._device or not screen:
            return

        caps: DeviceCapabilities | None = deck._caps
        if caps is None:
            return

        metrics: RenderMetrics | None = deck._metrics
        if metrics is None:
            return

        # Phase 1: render all key images concurrently
        key_images: dict[int, bytes] = {}
        render_tasks: list[asyncio.Task[tuple[int, bytes]]] = []
        prof = RenderProfiler("render_all_keys")

        for key_index in range(caps.key_count):
            key_slot = screen.keys.get(key_index)
            if key_slot and self.is_dui_key(key_slot):
                dui_key = cast("DuiKey", key_slot)

                # Skip keys with active spinner animation
                if self.is_animating(dui_key):
                    continue

                # Wire push_fn for animations (needs to happen on main thread)
                async def _push_key_frame(
                    frame_bytes: bytes, idx: int = key_index
                ) -> None:
                    device = deck._device
                    if device is None:
                        raise DeviceUnavailable(
                            f"deck {deck!r} device is None"
                        )
                    async with deck._device_lock:
                        device = deck._device
                        if device is None:
                            raise DeviceUnavailable(
                                f"deck {deck!r} device closed"
                            )
                        try:
                            await deck._exec_device_io(
                                device.set_key_image, idx, frame_bytes
                            )
                        except HidApiError as exc:
                            raise DeviceUnavailable(str(exc)) from exc

                dui_key.set_push_fn(_push_key_frame, key_size=caps.key_size)

                async def _render_key(
                    dk: DuiKey = dui_key, idx: int = key_index
                ) -> tuple[int, bytes]:
                    img = await asyncio.to_thread(
                        dk.render_image,
                        key_size=caps.key_size,
                        image_format=caps.key_image_format,
                    )
                    dk.set_rendered_image(img)
                    return (idx, img)

                render_tasks.append(asyncio.ensure_future(_render_key()))
            else:
                bg_image = screen.key_bg_image
                if bg_image is not None:
                    key_images[key_index] = bg_image
                else:
                    key_images[key_index] = render_blank_key(
                        key_size=metrics.key_size,
                        image_format=caps.key_image_format,
                    )

        # Await all concurrent renders
        if render_tasks:
            with prof.step("render_phase"):
                results = await asyncio.gather(*render_tasks)
            for idx, img in results:
                key_images[idx] = img

        # Phase 2: push all key images to device under a single lock
        with prof.step("push_phase"):
            await deck._consume_splash_push_deadline()
            async with deck._device_lock:
                for key_index in sorted(key_images):
                    await deck._exec_device_io(
                        deck._device.set_key_image,
                        key_index,
                        key_images[key_index],
                    )

        prof.finish()
        prof.log()

    async def render_dui_key(self, key_slot: KeySlot, key_index: int) -> None:
        """Render a DuiKey and push to the device.

        Parameters
        ----------
        key_slot : KeySlot
            The DuiKey to render.
        key_index : int
            The screen slot the key is currently installed at.  This is
            authoritative for routing (a single DuiKey may live on
            multiple screens at different slots), so the spinner
            ``push_fn`` is rewired on every render to capture the active
            slot.
        """
        deck = self._deck
        if not deck._device:
            return

        dui_key = cast("DuiKey", key_slot)

        # Skip rendering if a spinner animation is active
        if self.is_animating(dui_key):
            return

        # Skip rendering if the key content has not changed
        if not dui_key.is_dirty:
            return

        # Re-wire push_fn every render so a DuiKey reused across screens
        # always animates at the slot of the currently active screen.
        async def _push_key_frame(frame_bytes: bytes) -> None:
            device = deck._device
            if device is None:
                raise DeviceUnavailable(f"deck {deck!r} device is None")
            async with deck._device_lock:
                device = deck._device
                if device is None:
                    raise DeviceUnavailable(f"deck {deck!r} device closed")
                try:
                    await deck._exec_device_io(
                        device.set_key_image,
                        key_index,
                        frame_bytes,
                    )
                except HidApiError as exc:
                    raise DeviceUnavailable(str(exc)) from exc

        if deck._caps is None:
            return

        dui_key.set_push_fn(_push_key_frame, key_size=deck._caps.key_size)

        prof = RenderProfiler("render_dui_key")
        with prof.step("render_image"):
            image_bytes = await asyncio.to_thread(
                dui_key.render_image,
                key_size=deck._caps.key_size,
                image_format=deck._caps.key_image_format,
            )
        dui_key.set_rendered_image(image_bytes)

        with prof.step("push_to_device"):
            async with deck._device_lock:
                await deck._exec_device_io(
                    deck._device.set_key_image,
                    key_index,
                    image_bytes,
                )
        prof.finish()
        prof.log()

    # ------------------------------------------------------------------
    # Touchscreen rendering
    # ------------------------------------------------------------------

    def _touchscreen_image_format(self) -> str:
        """Return the touchscreen image format for the active device.

        Returns
        -------
        str
            Image format string (e.g. ``"JPEG"``) from device
            capabilities, defaulting to ``"JPEG"`` if unavailable.
        """
        caps = self._deck._caps
        return caps.touchscreen_image_format if caps else "JPEG"

    def _make_card_push_fn(
        self,
        card_idx: int,
        panel_width: int,
        panel_height: int,
        bg_tile: bytes | None,
    ) -> PushFn:
        """Build a ``push_fn`` that delivers a single panel frame to the device.

        Used to wire spinner animations into per-panel updates.  The
        returned coroutine optionally composites the frame onto the
        provided background tile before pushing it to the device under
        the deck's I/O lock.

        Parameters
        ----------
        card_idx : int
            Index of the card on the touch strip (0-based).
        panel_width, panel_height : int
            Panel dimensions in pixels.
        bg_tile : bytes | None
            Optional encoded background tile for compositing.

        Returns
        -------
        PushFn
            Async callable accepting raw frame bytes for the panel.
        """
        deck = self._deck
        x_pos = card_idx * panel_width
        y_pos = 0
        image_fmt = self._touchscreen_image_format()

        async def _push_card_frame(frame_bytes: bytes) -> None:
            if bg_tile is not None:
                out_bytes = await asyncio.to_thread(
                    composite_frame_on_tile,
                    frame_bytes,
                    bg_tile_bytes=bg_tile,
                    panel_width=panel_width,
                    panel_height=panel_height,
                    image_format=image_fmt,
                )
            else:
                out_bytes = frame_bytes
            device = deck._device
            if device is None:
                raise DeviceUnavailable(f"deck {deck!r} device is None")
            async with deck._device_lock:
                device = deck._device
                if device is None:
                    raise DeviceUnavailable(f"deck {deck!r} device closed")
                try:
                    await deck._exec_device_io(
                        device.set_partial_window_image,
                        x_pos,
                        y_pos,
                        panel_width,
                        panel_height,
                        out_bytes,
                    )
                except HidApiError as exc:
                    raise DeviceUnavailable(str(exc)) from exc

        return _push_card_frame

    async def _setup_card(
        self,
        card_idx: int,
        card: Card,
        bg_tile: bytes | None,
        bg_svg_root: Any,
        panel_width: int,
        panel_height: int,
    ) -> bool:
        """Configure a card's background layer and animation push hook.

        For :class:`DuiCard` instances, this installs the background
        tile, wires (or clears) the SVG background layer, and registers
        a ``push_fn`` for spinner animations.

        Parameters
        ----------
        card_idx : int
            Index of the card on the touch strip.
        card : Card
            The card to set up.
        bg_tile : bytes | None
            Encoded background tile for this card slot, if any.
        bg_svg_root : Any
            Touch strip's root SVG element for background compositing,
            or ``None`` if no background is configured.
        panel_width, panel_height : int
            Panel dimensions in pixels.

        Returns
        -------
        bool
            ``True`` if the card should be rendered this cycle (i.e. it
             is dirty and not currently animating); ``False`` otherwise.
        """
        # Inline import: dui.card transitively imports runtime.events, which
        # triggers runtime package init while this module is still loading.
        from ..dui.card import DuiCard  # noqa: PLC0415

        if isinstance(card, DuiCard):
            card.set_bg_tile(bg_tile)

            if bg_svg_root is not None:
                card.set_background_layer(
                    bg_svg_root,
                    card_idx,
                    panel_width,
                    panel_height,
                )
            else:
                card.clear_background_layer()

            push_fn = self._make_card_push_fn(
                card_idx, panel_width, panel_height, bg_tile
            )
            card.set_push_fn(push_fn, panel_size=(panel_width, panel_height))

            if self.is_animating(card):
                return False

        return card.is_dirty

    async def _push_card(
        self, card_idx: int, panel_bytes: bytes, panel_width: int, panel_height: int
    ) -> None:
        """Push a rendered panel to the touchscreen at the given slot.

        The caller is responsible for holding the deck's device lock.

        Parameters
        ----------
        card_idx : int
            Index of the card on the touch strip (0-based).
        panel_bytes : bytes
            Encoded panel image to send to the device.
        panel_width, panel_height : int
            Panel dimensions in pixels.
        """
        deck = self._deck
        x_pos = card_idx * panel_width
        y_pos = 0
        await deck._exec_device_io(
            deck._device.set_partial_window_image,  # type: ignore[union-attr]
            x_pos,
            y_pos,
            panel_width,
            panel_height,
            panel_bytes,
        )

    async def render_touchscreen(self) -> None:
        """Render and push each card panel individually to the device.

        Delegates panel rendering to the card's
        :meth:`~deux.ui.cards.base.Card.render_panel_bytes` method,
        which is overridden by :class:`~deux.dui.card.DuiCard` to use
        the SVG-native pipeline.  Non-DUI cards fall back to the
        legacy Pillow compositing path (with a deprecation warning).
        """
        deck = self._deck
        screen = deck._current_screen()
        if not deck._device or not screen or not deck._metrics:
            return

        if screen.touch_strip is None:
            return

        metrics = deck._metrics
        touch_strip = screen.touch_strip
        bg_svg_root = touch_strip.bg_svg_root

        # Phase 1: set up cards (push_fn wiring, background layers)
        cards_to_render: list[tuple[int, Card, bytes | None]] = []
        for card_idx, card in enumerate(screen.cards):
            bg_tile = touch_strip.bg_tile(card_idx)
            should_render = await self._setup_card(
                card_idx,
                card,
                bg_tile,
                bg_svg_root,
                metrics.panel_width,
                metrics.panel_height,
            )
            if should_render:
                cards_to_render.append((card_idx, card, bg_tile))

        # Phase 2: frame budget.  push_fn wiring above must still run on
        # every call so that spinner animations target the correct slot,
        # but actual render/push is throttled.
        now = time.perf_counter()
        if now - self._last_touch_render < self._MIN_TOUCH_INTERVAL:
            return
        self._last_touch_render = now

        if not cards_to_render:
            return

        image_fmt = self._touchscreen_image_format()

        async def _render_card(
            cidx: int, crd: Card, tile: bytes | None
        ) -> tuple[int, bytes]:
            await crd.prepare_assets()
            panel_bytes = await asyncio.to_thread(
                crd.render_panel_bytes,
                metrics=metrics,
                card_index=cidx,
                bg_tile=tile,
                background=touch_strip.background_color,
                image_format=image_fmt,
            )
            return (cidx, panel_bytes)

        # Phase 3: render all dirty cards concurrently, then push under a
        # single device lock.  A single card still benefits from this
        # path: asyncio.gather of one task adds negligible overhead.
        prof = RenderProfiler("render_touchscreen")
        with prof.step("render_cards"):
            results = await asyncio.gather(
                *[_render_card(cidx, crd, tile) for cidx, crd, tile in cards_to_render]
            )

        with prof.step("push_to_device"):
            await deck._consume_splash_push_deadline()
            async with deck._device_lock:
                for cidx, panel_bytes in sorted(results, key=lambda r: r[0]):
                    await self._push_card(
                        cidx, panel_bytes, metrics.panel_width, metrics.panel_height
                    )
        prof.finish()
        prof.log()

    # ------------------------------------------------------------------
    # Info-screen rendering
    # ------------------------------------------------------------------

    async def render_info_screen(self) -> None:
        """Render and push the info screen image (e.g. Neo)."""
        deck = self._deck
        screen = deck._current_screen()
        if not deck._device or not screen:
            return

        info = screen.info_screen
        if info is None:
            return

        image_bytes = info.render_bytes()

        await deck._consume_splash_push_deadline()
        async with deck._device_lock:
            await deck._exec_device_io(
                deck._device.set_partial_window_image,
                0,
                0,
                info.width,
                info.height,
                image_bytes,
            )
        info.mark_clean()

    # ------------------------------------------------------------------
    # Card callback drain
    # ------------------------------------------------------------------

    @staticmethod
    async def drain_card_callbacks(card: Card) -> None:
        """Drain and await all pending callbacks queued on a card.

        Parameters
        ----------
        card : Card
            The card whose pending callbacks should be drained.
        """
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

    # ------------------------------------------------------------------
    # Theme application
    # ------------------------------------------------------------------

    async def render_screen_complete(self) -> None:
        """Prefetch icons, render all controls, then push to device.

        This is the single entry point for full-screen renders: initial
        screen load, screen switch, and theme change.  It ensures the
        complete screen (keys, cards, info screen) is rendered before
        any images are sent to the device, avoiding partial displays.

        The sequence is:

        1. Prefetch all Iconify icons needed by the active screen.
        2. Render all keys, cards, and the info screen concurrently.
        3. Push all rendered images to the device.
        """
        deck = self._deck
        screen = deck._current_screen()
        if not screen or not deck._device:
            return

        prof = RenderProfiler("render_screen_complete")
        t0 = time.perf_counter()

        # 1. Prefetch icons
        icons = screen.collect_all_icons()
        if icons:
            # Inline import: tests patch ``deux.dui.iconify.prefetch_icons``;
            # importing it lazily keeps that patching point effective.
            from ..dui.iconify import prefetch_icons  # noqa: PLC0415

            with prof.step("prefetch_icons"):
                await prefetch_icons(icons)

        # 2–3. Render and push all controls
        with prof.step("render_all_keys"):
            await self.render_all_keys()
        if screen.touch_strip is not None:
            with prof.step("render_touchscreen"):
                await self.render_touchscreen()
        if screen.info_screen is not None:
            with prof.step("render_info_screen"):
                await self.render_info_screen()

        prof.finish((time.perf_counter() - t0) * 1000.0)
        prof.log()

    def apply_theme(self) -> None:
        """Apply the resolved theme cascade to all renderers on the active screen.

        Builds an explicit :class:`~deux.render.context.RenderingContext`
        and pushes it to every :class:`~deux.dui.svg_renderer.SvgRenderer`
        on the active screen's cards and keys.  The module-level global
        stylesheet is also updated so that renderers without an explicit
        context pick up the correct CSS.
        """
        css = self._deck.resolve_stylesheet()

        # Update global stylesheet for renderers without an explicit context.
        set_svg_stylesheet(css)

        # Build per-deck context and push to all renderers.
        ctx = RenderingContext(stylesheet=css)
        self._apply_context_to_screen(ctx)

    def _apply_context_to_screen(self, ctx: RenderingContext) -> None:
        """Push a rendering context to every renderer on the active screen.

        Parameters
        ----------
        ctx : RenderingContext
            The context to propagate.
        """
        # Inline import: dui.card transitively imports runtime.events, which
        # triggers runtime package init while this module is still loading.
        from ..dui.card import DuiCard  # noqa: PLC0415

        screen = self._deck.active_screen
        if screen is None:
            return

        # Keys
        for key_slot in screen.keys.values():
            if isinstance(key_slot, DuiKey):
                key_slot.set_rendering_context(ctx)

        # Touchscreen cards
        if screen.touch_strip is not None:
            for card in screen.touch_strip.cards:
                if isinstance(card, DuiCard):
                    card.set_rendering_context(ctx)
