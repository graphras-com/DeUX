"""DuiKey: a physical key backed by a .dui package."""

from __future__ import annotations

import asyncio
import builtins
import logging
from typing import TYPE_CHECKING, Any

from ..ui.controls.key_slot import KeySlot
from .animator import PushFn, SpinnerAnimator
from .binding_mixin import BindingMixin
from .event_map import EventMap
from .schema import PackageSpec
from .spinner import SpinnerFrames
from .svg_renderer import SvgRenderer

if TYPE_CHECKING:
    from ..render.context import RenderingContext
    from ..runtime.async_event import AsyncEvent
    from ..runtime.events import AsyncHandler

logger = logging.getLogger(__name__)


class DuiKey(BindingMixin, KeySlot):
    """A physical key whose layout and events are defined by a .dui package.

    ``DuiKey`` extends :class:`~deux.ui.controls.key_slot.KeySlot`
    so that it is accepted wherever a ``KeySlot`` is expected.  It
    replaces the icon + label rendering with SVG-based rendering from
    a ``.dui`` package.

    Examples
    --------
    ::

        from deux import DuiKey

        # Resolve by name from the DUI repository
        key = DuiKey("IconKey")
        key.set("label", "Shutdown")

        @key.on("activate")
        async def handle():
            ...

    You can also pass a pre-loaded :class:`~deux.dui.schema.PackageSpec`
    directly::

        from deux.dui import load_package, DuiKey

        spec = load_package("./PowerKey.dui")
        key = DuiKey(spec)

    The key index is assigned automatically when you install the key
    on a screen with :meth:`~deux.ui.screen.Screen.set_key`.

    Parameters
    ----------
    spec : PackageSpec or str
        A validated :class:`~deux.dui.schema.PackageSpec`, or a
        package name (e.g. ``"IconKey"``) to resolve from the DUI
        repository.
    """

    def __init__(self, spec: PackageSpec | str) -> None:
        if isinstance(spec, str):
            # Inline import: keeps the lookup go through repository.resolve_dui
            # at call time so monkeypatching that symbol in tests works.
            from .repository import resolve_dui  # noqa: PLC0415

            spec = resolve_dui(spec)
        super().__init__()
        self._spec = spec
        self._renderer = SvgRenderer(spec)
        self._events = EventMap(spec.events)
        self._subscriptions: list[tuple[AsyncEvent, AsyncHandler]] = []
        self._dirty = True
        self._busy = False
        self._animator: SpinnerAnimator | None = None
        self._spinner_frames: SpinnerFrames | None = None
        self._push_fn: PushFn | None = None
        self._key_size: tuple[int, int] | None = None

    @property
    def spec(self) -> PackageSpec:
        """The package specification backing this key."""
        return self._spec

    @property
    def is_busy(self) -> bool:
        """Whether a busy-guarded handler is currently executing."""
        return self._busy

    @property
    def is_animating(self) -> bool:
        """Whether a spinner animation is currently running."""
        return self._animator is not None and self._animator.is_running

    def set_push_fn(self, push_fn: PushFn, key_size: tuple[int, int]) -> None:
        """Set the async function used to push animation frames to the device.

        Parameters
        ----------
        push_fn
            Async callable ``(frame_bytes) -> None``.
        key_size
            ``(width, height)`` of the device's key — used to size
            spinner frames.
        """
        self._push_fn = push_fn
        self._key_size = key_size

    def set(self, name: str, value: Any) -> DuiKey:
        """Set a binding value.  Marks the key dirty if changed.

        Parameters
        ----------
        name
            Binding name as defined in the manifest.
        value
            New value (type depends on binding kind).

        Returns
        -------
        DuiKey
            self, for method chaining.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        """
        if self._renderer.set(name, value):
            self._dirty = True
        return self

    def set_many(self, **kwargs: Any) -> DuiKey:
        """Set multiple binding values at once.

        Returns
        -------
        DuiKey
            self, for method chaining.
        """
        if self._renderer.set_many(**kwargs):
            self._dirty = True
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
        """Return all Iconify icon identifiers needed by this key.

        Returns
        -------
        set[str]
            A set of ``"prefix:icon"`` strings referenced by the key's
            bindings (defaults and current values).
        """
        return self._renderer.collect_icon_names()

    def set_rendering_context(self, ctx: RenderingContext | None) -> None:
        """Set the explicit rendering context for this key.

        Parameters
        ----------
        ctx : RenderingContext or None
            The rendering context to apply, or ``None`` to revert to
            module-level defaults.
        """
        self._renderer.set_rendering_context(ctx)

    def set_range(
        self, name: str, value: float, *, min_val: float = 0, max_val: float = 1
    ) -> DuiKey:
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
        DuiKey
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

    def render_image(
        self,
        key_size: tuple[int, int],
        image_format: str = "JPEG",
    ) -> bytes:
        """Render the SVG layout to image bytes for the key.

        Uses the SVG-native pipeline: the SVG is rasterised at
        *key_size* directly (vector scaling via ``viewBox``) with a
        black background injected at the SVG level.  No Pillow resize
        or compositing is needed.

        Falls back to the legacy Pillow path for BMP format.

        Parameters
        ----------
        key_size
            Target key dimensions ``(width, height)`` in pixels.
        image_format
            Image encoding format (``"JPEG"`` or ``"BMP"``).

        Returns
        -------
        bytes
            Encoded image bytes.
        """
        self._renderer.set_target_size(*key_size)
        fmt = image_format.upper()
        out_fmt = "jpeg" if fmt == "JPEG" else "bmp"
        return self._renderer.render_bytes(
            output_format=out_fmt,
            background="black",
        )

    async def _dispatch_event(self, pressed: bool) -> None:
        """Dispatch a key press/release through the event map.

        All matching handlers (simple and compound) are called.
        Falls back to the base KeySlot handlers if the event map
        returns no matches.
        """
        handlers = (
            self._events.handle_key_press()
            if pressed
            else self._events.handle_key_release()
        )

        if handlers:
            for handler in handlers:
                await handler()
        else:
            await super()._dispatch_event(pressed)

    async def start_busy(self) -> None:
        """Enter the busy state and start the spinner animation.

        While busy, the key suppresses further ``start_busy()`` calls.
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

        If the key is not currently busy this is a no-op.
        """
        if not self._busy:
            return
        await self._stop_spinner()
        self._busy = False
        self._dirty = True

    async def _start_spinner(self) -> None:
        """Start the spinner animation if configured."""
        if (
            self._spec.spinner is None
            or self._push_fn is None
            or self._key_size is None
        ):
            return

        width, height = self._key_size
        rendered_svg = self._renderer.render_svg()
        spinner_frames = SpinnerFrames(
            self._spec,
            width=width,
            height=height,
            rendered_svg=rendered_svg,
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
