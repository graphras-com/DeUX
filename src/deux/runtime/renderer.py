"""DeckRenderer: extracted rendering logic for Stream Deck devices.

Handles key, touchscreen, and info-screen rendering pipelines,
separated from the lifecycle and event-dispatch responsibilities
of :class:`~deux.runtime.deck.Deck`.
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING, Any, cast

from PIL import Image

from ..dui.key import DuiKey
from ..render.key_renderer import render_blank_key
from ..render.touch_renderer import compose_card_with_background

if TYPE_CHECKING:
    from ..dui.animator import PushFn
    from ..render.context import RenderingContext
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

    def __init__(self, deck: Deck) -> None:
        self._deck = deck

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

        The cascade is: screen theme > deck theme > system theme.

        Returns
        -------
        str
            CSS stylesheet string from the most specific theme.
        """
        from ..render.theme import get_active_theme

        screen = self._deck._active_screen
        if screen is not None and screen.theme is not None:
            return screen.theme.css
        if self._deck._theme is not None:
            return self._deck._theme.css
        return get_active_theme().css

    # ------------------------------------------------------------------
    # Key rendering
    # ------------------------------------------------------------------

    async def render_all_keys(self) -> None:
        """Render and push all key images for the active screen."""
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

        for key_index in range(caps.key_count):
            key_slot = screen.keys.get(key_index)
            if key_slot and self.is_dui_key(key_slot):
                await self.render_dui_key(key_slot, key_index)
            else:
                bg_image = screen.key_bg_image
                if bg_image is not None:
                    image_bytes = bg_image
                else:
                    image_bytes = render_blank_key(
                        key_size=metrics.key_size,
                        image_format=caps.key_image_format,
                    )
                async with deck._device_lock:
                    await deck._exec_device_io(
                        deck._device.set_key_image,
                        key_index,
                        image_bytes,
                    )

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

        # Re-wire push_fn every render so a DuiKey reused across screens
        # always animates at the slot of the currently active screen.
        async def _push_key_frame(frame_bytes: bytes) -> None:
            async with deck._device_lock:
                await deck._exec_device_io(
                    deck._device.set_key_image,
                    key_index,
                    frame_bytes,
                )

        if deck._caps is None:
            return

        dui_key.set_push_fn(_push_key_frame, key_size=deck._caps.key_size)

        image_bytes = dui_key.render_image(
            key_size=deck._caps.key_size,
            image_format=deck._caps.key_image_format,
        )
        dui_key.set_rendered_image(image_bytes)

        async with deck._device_lock:
            await deck._exec_device_io(
                deck._device.set_key_image,
                key_index,
                image_bytes,
            )

    # ------------------------------------------------------------------
    # Touchscreen rendering
    # ------------------------------------------------------------------

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

        from ..dui.card import DuiCard

        bg_svg_root = touch_strip.bg_svg_root

        for card_idx, card in enumerate(screen.cards):
            x_pos = card_idx * metrics.panel_width
            y_pos = 0
            bg_tile = touch_strip.bg_tile(card_idx)

            if isinstance(card, DuiCard):
                # Set up background layer for SVG-level compositing
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
                            # Offload CPU-bound PIL work to a thread to avoid
                            # blocking the event loop.
                            def _compose(fb: bytes = frame_bytes) -> bytes:
                                frame_img = Image.open(io.BytesIO(fb))
                                return compose_card_with_background(
                                    frame_img,
                                    bg_tile=tile,
                                    panel_width=w,
                                    panel_height=h,
                                    image_format=(
                                        deck._caps.touchscreen_image_format
                                        if deck._caps
                                        else "JPEG"
                                    ),
                                )

                            out_bytes = await asyncio.to_thread(_compose)
                        else:
                            out_bytes = frame_bytes
                        async with deck._device_lock:
                            await deck._exec_device_io(
                                deck._device.set_touchscreen_image,
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
                if self.is_animating(card):
                    continue

            await card.prepare_assets()

            image_fmt = (
                deck._caps.touchscreen_image_format if deck._caps else "JPEG"
            )

            # Unified rendering: each card type implements render_panel_bytes
            panel_bytes = await asyncio.to_thread(
                card.render_panel_bytes,
                metrics=metrics,
                card_index=card_idx,
                bg_tile=bg_tile,
                background=touch_strip.background_color,
                image_format=image_fmt,
            )

            # Push per-panel update
            async with deck._device_lock:
                await deck._exec_device_io(
                    deck._device.set_touchscreen_image,
                    panel_bytes,
                    x_pos,
                    y_pos,
                    metrics.panel_width,
                    metrics.panel_height,
                )

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

        async with deck._device_lock:
            await deck._exec_device_io(
                deck._device.set_screen_image,
                image_bytes,
                0,
                0,
                info.width,
                info.height,
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

    def apply_theme(self) -> None:
        """Apply the resolved theme cascade to all renderers on the active screen.

        Instead of mutating the module-level global stylesheet (which
        races when multiple decks render concurrently), this builds an
        explicit :class:`~deux.render.context.RenderingContext` and
        pushes it to every :class:`~deux.dui.svg_renderer.SvgRenderer`
        on the active screen's cards and keys.

        The global stylesheet is also updated for backward compatibility
        with code that reads it directly.
        """
        from ..render.context import RenderingContext
        from ..render.svg_rasterize import set_svg_stylesheet

        css = self._resolve_stylesheet()

        # Update global for backward compatibility / simple usage.
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
        from ..dui.card import DuiCard
        from ..dui.key import DuiKey

        screen = self._deck._active_screen
        if screen is None:
            return

        # Keys
        for key_slot in screen.keys.values():
            if isinstance(key_slot, DuiKey):
                key_slot._renderer.set_rendering_context(ctx)

        # Touchscreen cards
        if screen.touch_strip is not None:
            for card in screen.touch_strip.cards:
                if isinstance(card, DuiCard):
                    card._renderer.set_rendering_context(ctx)
