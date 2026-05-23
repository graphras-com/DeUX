"""DuiCard: a touchscreen card backed by a .dui package."""

from __future__ import annotations

import asyncio
import builtins
import logging
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Any

from ..ui.cards.base import Card
from .animator import PushFn, SpinnerAnimator
from .binding_mixin import BindingMixin
from .event_map import EventMap
from .schema import PackageSpec
from .spinner import SpinnerFrames
from .svg_renderer import SvgRenderer

if TYPE_CHECKING:
    from PIL import Image

    from ..render.context import RenderingContext
    from ..render.metrics import RenderMetrics
    from ..runtime.async_event import AsyncEvent
    from ..runtime.events import AsyncHandler, TouchEvent

logger = logging.getLogger(__name__)


class DuiCard(BindingMixin, Card):
    """A touchscreen card whose layout and events are defined by a .dui package.

    Instead of writing a Python class with imperative Pillow rendering,
    you describe the UI in an SVG layout and a YAML manifest.  The card
    loads the package, lets you set binding values, and renders the SVG
    into a PIL Image for the Stream Deck touchscreen.

    Examples
    --------
    ::

        from deux import DuiCard

        # Resolve by name from the DUI repository
        card = DuiCard("AudioCard")
        card.set("artist", "Ash Walker")

        @card.on("toggle_play_pause")
        async def handle():
            ...

    You can also pass a pre-loaded :class:`~deux.dui.schema.PackageSpec`
    directly::

        from deux.dui import load_package, DuiCard

        spec = load_package("./AudioCard.dui")
        card = DuiCard(spec)

    The card index is assigned automatically when you install the card
    on a screen with :meth:`~deux.ui.screen.Screen.set_card`.
    """

    def __init__(self, spec: PackageSpec | str) -> None:
        """Construct a DUI-backed touchscreen card.

        Parameters
        ----------
        spec : PackageSpec or str
            Either a pre-validated
            :class:`~deux.dui.schema.PackageSpec`, or a package name
            (for example ``"DashboardCard"``) to resolve from the DUI
            repository.  String resolution is deferred to
            :func:`~deux.dui.repository.resolve_dui` at call time so
            tests that monkeypatch that symbol behave correctly.

        Raises
        ------
        deux.dui.repository.PackageError
            If *spec* is a string and no matching package is found in
            any registered search path.

        Notes
        -----
        Construction performs no rendering and no device I/O.  The
        underlying :class:`~deux.dui.svg_renderer.SvgRenderer` and
        :class:`~deux.dui.events.EventMap` are built eagerly from
        *spec*; binding values, push callbacks, and background tiles
        are configured later via the corresponding setters.
        """
        if isinstance(spec, str):
            # Inline import: keeps the lookup go through repository.resolve_dui
            # at call time so monkeypatching that symbol in tests works.
            from .repository import resolve_dui  # noqa: PLC0415

            spec = resolve_dui(spec)
        super().__init__()
        self._spec = spec
        self._renderer = SvgRenderer(spec)
        self._events = EventMap(spec.events, spec.regions)
        self._subscriptions: list[tuple[AsyncEvent, AsyncHandler]] = []
        self._busy = False
        self._animator: SpinnerAnimator | None = None
        self._spinner_frames: SpinnerFrames | None = None
        self._push_fn: PushFn | None = None
        self._panel_size: tuple[int, int] | None = None
        self._bg_tile: bytes | None = None
        self._bg_svg_root: ET.Element | None = None
        self._card_index: int | None = None

    @property
    def spec(self) -> PackageSpec:
        """The package specification backing this card."""
        return self._spec

    @property
    def is_busy(self) -> bool:
        """Whether a busy-guarded handler is currently executing."""
        return self._busy

    @property
    def is_animating(self) -> bool:
        """Whether a spinner animation is currently running."""
        return self._animator is not None and self._animator.is_running

    def set_push_fn(self, push_fn: PushFn, panel_size: tuple[int, int]) -> None:
        """Set the async function used to push animation frames to the device.

        This must be called before spinner animations can play.
        Typically set by :class:`~deux.runtime.deck.Deck`.

        Parameters
        ----------
        push_fn
            Async callable ``(frame_bytes) -> None``.
        panel_size
            ``(width, height)`` of the touchscreen panel this card occupies,
            used to size spinner frames.
        """
        self._push_fn = push_fn
        self._panel_size = panel_size

    def set_bg_tile(self, tile: bytes | None) -> None:
        """Set the background tile for compositing spinner frames.

        When a touchstrip background SVG is active, the corresponding
        pre-sliced tile (PNG bytes) is passed here so that spinner
        animations can composite each frame onto the background.

        Parameters
        ----------
        tile
            PNG-encoded background tile bytes, or ``None`` to clear.
        """
        self._bg_tile = tile

    def set_background_layer(
        self,
        bg_root: ET.Element,
        card_index: int,
        panel_width: int,
        panel_height: int,
    ) -> None:
        """Set a background SVG layer underneath the card content.

        The background SVG's ``viewBox`` is sliced to the region for
        *card_index* and composed as a layer beneath the card's own
        SVG.  The composed tree is cached so subsequent renders only
        need to apply bindings and rasterise.

        Parameters
        ----------
        bg_root : ET.Element
            The full-width background ``<svg>`` root element.
        card_index : int
            Zero-based panel index.
        panel_width : int
            Width of a single panel in pixels.
        panel_height : int
            Height of a single panel in pixels.
        """
        self._bg_svg_root = bg_root
        self._card_index = card_index
        self._renderer.set_base_layer(bg_root, card_index, panel_width, panel_height)
        self._renderer.set_target_size(panel_width, panel_height)

    def clear_background_layer(self) -> None:
        """Remove the background layer and revert to the card's own SVG."""
        self._bg_svg_root = None
        self._card_index = None
        self._renderer.clear_base_layer()

    def render_bytes(
        self,
        *,
        panel_width: int,
        panel_height: int,
        image_format: str = "JPEG",
        background: str = "black",
    ) -> bytes:
        """Render the card directly to encoded image bytes.

        Uses the SVG-native pipeline: background compositing happens
        at the SVG level (if a background layer is set), dimensions are
        set for vector scaling, and the output is rasterised directly
        to the requested format.

        Parameters
        ----------
        panel_width : int
            Target panel width in pixels.
        panel_height : int
            Target panel height in pixels.
        image_format : str, default="JPEG"
            Image encoding format (``"JPEG"`` or ``"BMP"``).
        background : str, default="black"
            Fallback background colour (used when no background SVG
            layer is set).

        Returns
        -------
        bytes
            Encoded image bytes ready to send to the device.
        """
        self._renderer.set_target_size(panel_width, panel_height)
        fmt = image_format.upper()
        out_fmt = "jpeg" if fmt == "JPEG" else "bmp"
        # Only inject a solid background if no SVG background layer is set.
        bg = background if self._bg_svg_root is None else None
        return self._renderer.render_bytes(
            output_format=out_fmt,
            background=bg,
        )

    def render_panel_bytes(
        self,
        *,
        metrics: RenderMetrics,
        card_index: int,
        bg_tile: bytes | None,
        background: str = "black",
        image_format: str = "JPEG",
    ) -> bytes:
        """Render the card to encoded image bytes using the SVG-native pipeline.

        Overrides the base :meth:`Card.render_panel_bytes` to use
        SVG-level background compositing and direct rasterisation,
        avoiding the legacy Pillow compositing path entirely.

        Parameters
        ----------
        metrics : RenderMetrics
            Device metrics (panel dimensions, etc.).
        card_index : int
            The zero-based position of this card on the touch strip.
        bg_tile : Image.Image or None
            Cropped background tile for this card's panel, or ``None``.
        background : str, default="black"
            Fallback background colour.
        image_format : str, default="JPEG"
            Image encoding format (``"JPEG"`` or ``"BMP"``).

        Returns
        -------
        bytes
            Encoded image bytes ready to send to the device.
        """
        panel_bytes = self.render_bytes(
            panel_width=metrics.panel_width,
            panel_height=metrics.panel_height,
            image_format=image_format,
            background=background,
        )

        self.mark_clean()

        return panel_bytes

    def set(self, name: str, value: Any) -> DuiCard:
        """Set a binding value.  Marks the card dirty if changed.

        Parameters
        ----------
        name
            Binding name as defined in the manifest.
        value
            New value (type depends on binding kind).

        Returns
        -------
        DuiCard
            self, for method chaining.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        """
        if self._renderer.set(name, value):
            self.mark_dirty()
        return self

    def set_many(self, **kwargs: Any) -> DuiCard:
        """Set multiple binding values at once.

        Returns
        -------
        DuiCard
            self, for method chaining.
        """
        if self._renderer.set_many(**kwargs):
            self.mark_dirty()
        return self

    def get(self, name: str) -> Any:
        """Get the current value of a binding.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        """
        return self._renderer.get(name)

    def collect_icon_names(self) -> builtins.set[str]:
        """Return all Iconify icon identifiers needed by this card.

        Returns
        -------
        set[str]
            A set of ``"prefix:icon"`` strings referenced by the card's
            bindings (defaults and current values).
        """
        return self._renderer.collect_icon_names()

    def set_rendering_context(self, ctx: RenderingContext | None) -> None:
        """Set the explicit rendering context for this card.

        Parameters
        ----------
        ctx : RenderingContext or None
            The rendering context to apply, or ``None`` to revert to
            module-level defaults.
        """
        self._renderer.set_rendering_context(ctx)

    def set_range(
        self, name: str, value: float, *, min_val: float = 0, max_val: float = 1
    ) -> DuiCard:
        """Set a range/slider binding using a domain-scale value.

        Normalises *value* from ``[min_val, max_val]`` to ``[0.0, 1.0]``
        and delegates to :meth:`set`.

        Parameters
        ----------
        name
            Binding name (must be a ``range`` or ``slider`` binding).
        value
            Value in domain units (e.g. 0–100 for a percentage).
        min_val
            Lower bound of the domain range.
        max_val
            Upper bound of the domain range.

        Returns
        -------
        DuiCard
            self, for method chaining.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        ValueError
            If *min_val* equals *max_val*.
        """
        if min_val == max_val:
            raise ValueError("min_val and max_val must not be equal")
        clamped = max(min_val, min(max_val, value))
        normalised = (clamped - min_val) / (max_val - min_val)
        return self.set(name, normalised)

    def adjust_range(
        self, name: str, delta: float, *, min_val: float = 0, max_val: float = 1
    ) -> float:
        """Adjust a range/slider binding by *delta* domain-scale units.

        Reads the current normalised value, denormalises it, adds *delta*,
        clamps, re-normalises, and calls :meth:`set`.

        Parameters
        ----------
        name
            Binding name (must be a ``range`` or ``slider`` binding).
        delta
            Amount to add in domain units (negative to decrease).
        min_val
            Lower bound of the domain range.
        max_val
            Upper bound of the domain range.

        Returns
        -------
        float
            The new value in domain units (clamped to
            ``[min_val, max_val]``), so callers can use it for display
            without back-computing.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        ValueError
            If *min_val* equals *max_val*.
        """
        if min_val == max_val:
            raise ValueError("min_val and max_val must not be equal")
        current_norm = float(self.get(name) or 0.0)
        current_domain = min_val + current_norm * (max_val - min_val)
        new_domain = max(min_val, min(max_val, current_domain + delta))
        normalised = (new_domain - min_val) / (max_val - min_val)
        self.set(name, normalised)
        return new_domain

    def get_range(
        self, name: str, *, min_val: float = 0, max_val: float = 1
    ) -> float:
        """Get a range/slider binding denormalised to domain units.

        Parameters
        ----------
        name
            Binding name.
        min_val
            Lower bound of the domain range.
        max_val
            Upper bound of the domain range.

        Returns
        -------
        float
            The current value in domain units.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        ValueError
            If *min_val* equals *max_val*.
        """
        if min_val == max_val:
            raise ValueError("min_val and max_val must not be equal")
        current_norm = float(self.get(name) or 0.0)
        return min_val + current_norm * (max_val - min_val)


    def render(self) -> Image.Image:
        """Render the SVG layout with current bindings to a PIL Image.

        Returns
        -------
        Image.Image
            A panel-sized RGB :class:`~PIL.Image.Image` (sized from the
            ``.dui`` SVG's intrinsic dimensions).
        """
        return self._renderer.render()

    async def prepare_assets(self) -> None:
        """No-op — .dui cards manage their own assets via the SVG."""

    def handle_encoder_turn(self, direction: int) -> None:
        """Route encoder turn through the event map."""
        handler = self._events.handle_encoder_turn(direction)
        if handler is not None:
            self.queue_pending_callback(handler, (direction,))

    def handle_encoder_press(self) -> None:
        """Route encoder press through the event map."""
        for handler in self._events.handle_encoder_press():
            self.queue_pending_callback(handler, ())

    def handle_encoder_release(self) -> None:
        """Route encoder release through the event map."""
        for handler in self._events.handle_encoder_release():
            self.queue_pending_callback(handler, ())

    async def dispatch_touch(self, event: TouchEvent) -> None:
        """Dispatch touch events through regions and the event map.

        Falls back to the base Card touch handlers (on_tap, etc.)
        if the event map doesn't handle the event.
        """
        handler = self._events.handle_touch(event.event_type, event.x, event.y)
        if handler is not None:
            await handler()
        else:
            await super().dispatch_touch(event)

    async def start_busy(self) -> None:
        """Enter the busy state and start the spinner animation.

        While busy, the card suppresses further ``start_busy()`` calls.
        The spinner keeps running until :meth:`finish_busy` is called.

        If no spinner is configured in the manifest the busy flag is
        still set (suppressing duplicate calls) but no animation plays.
        """
        if self._busy:
            return
        self._busy = True
        await self._start_spinner()

    async def finish_busy(self) -> None:
        """Stop the spinner and exit the busy state.

        Call this from your application code when the asynchronous
        work is truly complete (e.g. after receiving a state update
        from an external system).

        If the card is not currently busy this is a no-op.
        """
        if not self._busy:
            return
        await self._stop_spinner()
        self._busy = False
        self.mark_dirty()

    async def _start_spinner(self) -> None:
        """Start the spinner animation if configured."""
        if (
            self._spec.spinner is None
            or self._push_fn is None
            or self._panel_size is None
        ):
            return

        width, height = self._panel_size
        rendered_svg = self._renderer.render_svg()
        spinner_frames = SpinnerFrames(
            self._spec,
            width=width,
            height=height,
            rendered_svg=rendered_svg,
            bg_tile=self._bg_tile,
        )
        self._spinner_frames = spinner_frames

        self._animator = SpinnerAnimator(
            frames=await asyncio.to_thread(lambda: spinner_frames.frames),
            interval_ms=spinner_frames.interval_ms,
            push_fn=self._push_fn,
        )
        await self._animator.start()

    async def _stop_spinner(self) -> None:
        """Stop the spinner animation."""
        if self._animator is not None:
            await self._animator.stop()
            self._animator = None

    async def cleanup(self) -> None:
        """Cancel pending accumulators and release resources."""
        await self._events.cancel_accumulators()
