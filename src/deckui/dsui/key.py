"""DsuiKey: a physical key backed by a .dui package."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any, Callable

from PIL import Image

from ..render.metrics import KEY_SIZE
from ..runtime.events import AsyncHandler
from ..ui.controls.key_slot import KeySlot
from .event_map import EventMap
from .svg_renderer import SvgRenderer

if TYPE_CHECKING:
    from .schema import PackageSpec

logger = logging.getLogger(__name__)


class DsuiKey(KeySlot):
    """A physical key whose layout and events are defined by a .dui package.

    ``DsuiKey`` extends :class:`~deckui.ui.controls.key_slot.KeySlot`
    so that it is accepted wherever a ``KeySlot`` is expected.  It
    replaces the icon + label rendering with SVG-based rendering from
    a ``.dui`` package.

    Usage::

        from deckui.dsui import load_package, DsuiKey

        spec = load_package("./PowerKey.dui")
        key = DsuiKey(spec)
        key.set("label", "Shutdown")

        @key.on_event("activate")
        async def handle():
            ...

    The key index is assigned automatically when you install the key
    on a screen with :meth:`~deckui.ui.screen.Screen.set_key`.

    Args:
        spec: A validated :class:`~deckui.dsui.schema.PackageSpec`.
    """

    def __init__(self, spec: PackageSpec) -> None:
        super().__init__(-1)
        self._spec = spec
        self._renderer = SvgRenderer(spec)
        self._events = EventMap(spec.events)
        # Mark dirty so it renders on first screen activation
        self._dirty = True

    @property
    def spec(self) -> PackageSpec:
        """The package specification backing this key."""
        return self._spec

    # -- Data binding API --------------------------------------------------

    def set(self, name: str, value: Any) -> DsuiKey:
        """Set a binding value.  Marks the key dirty if changed.

        Args:
            name: Binding name as defined in the manifest.
            value: New value (type depends on binding kind).

        Returns:
            self, for method chaining.

        Raises:
            KeyError: If *name* is not a known binding.
        """
        if self._renderer.set(name, value):
            self._dirty = True
        return self

    def set_many(self, **kwargs: Any) -> DsuiKey:
        """Set multiple binding values at once.

        Returns:
            self, for method chaining.
        """
        if self._renderer.set_many(**kwargs):
            self._dirty = True
        return self

    def get(self, name: str) -> Any:
        """Get the current value of a binding.

        Raises:
            KeyError: If *name* is not a known binding.
        """
        return self._renderer.get(name)

    # -- Domain-scale range helpers ----------------------------------------

    def set_range(
        self, name: str, value: float, *, min_val: float = 0, max_val: float = 1
    ) -> DsuiKey:
        """Set a range/slider binding using a domain-scale value.

        Normalises *value* from ``[min_val, max_val]`` to ``[0.0, 1.0]``
        and delegates to :meth:`set`.

        Args:
            name: Binding name (must be a ``range`` or ``slider`` binding).
            value: Value in domain units (e.g. 0–100 for a percentage).
            min_val: Lower bound of the domain range.
            max_val: Upper bound of the domain range.

        Returns:
            self, for method chaining.

        Raises:
            KeyError: If *name* is not a known binding.
            ValueError: If *min_val* equals *max_val*.
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

        Args:
            name: Binding name (must be a ``range`` or ``slider`` binding).
            delta: Amount to add in domain units (negative to decrease).
            min_val: Lower bound of the domain range.
            max_val: Upper bound of the domain range.

        Returns:
            The new value in domain units (clamped to
            ``[min_val, max_val]``), so callers can use it for display
            without back-computing.

        Raises:
            KeyError: If *name* is not a known binding.
            ValueError: If *min_val* equals *max_val*.
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

        Args:
            name: Binding name.
            min_val: Lower bound of the domain range.
            max_val: Upper bound of the domain range.

        Returns:
            The current value in domain units.

        Raises:
            KeyError: If *name* is not a known binding.
            ValueError: If *min_val* equals *max_val*.
        """
        if min_val == max_val:
            raise ValueError("min_val and max_val must not be equal")
        current_norm = float(self.get(name) or 0.0)
        return min_val + current_norm * (max_val - min_val)

    # -- Semantic event API ------------------------------------------------

    def on_event(self, event_name: str) -> Callable[[AsyncHandler], AsyncHandler]:
        """Decorator to register a handler for a named semantic event.

        Usage::

            @key.on_event("activate")
            async def handle():
                ...

        Args:
            event_name: Semantic event name from the manifest.

        Returns:
            A decorator that registers the handler and returns it unchanged.
        """

        def decorator(fn: AsyncHandler) -> AsyncHandler:
            self._events.on(event_name, fn)
            return fn

        return decorator

    def bind_event(self, event_name: str, handler: AsyncHandler) -> None:
        """Imperatively register a handler for a named semantic event.

        Args:
            event_name: Semantic event name from the manifest.
            handler: The async callable to invoke.
        """
        self._events.on(event_name, handler)

    # -- Rendering ---------------------------------------------------------

    def render_image(
        self,
        key_size: tuple[int, int] | None = None,
        image_format: str = "JPEG",
    ) -> bytes:
        """Render the SVG layout to image bytes for the key.

        The SVG is rasterised and scaled to the device's key size,
        then encoded in the device's image format.

        Args:
            key_size: Target key dimensions ``(width, height)``.
                Defaults to ``KEY_SIZE`` (120x120 for Stream Deck+).
            image_format: Image encoding format (``"JPEG"`` or ``"BMP"``).

        Returns:
            Encoded image bytes.
        """
        size = key_size or KEY_SIZE
        img = self._renderer.render()
        if img.size != size:
            img = img.resize(size, Image.LANCZOS)
        return self._encode_image(img, image_format)

    @property
    def has_dsui_content(self) -> bool:
        """Always ``True`` — this key is backed by a .dui package."""
        return True

    # -- Override dispatch to use the event map ----------------------------

    async def dispatch(self, pressed: bool) -> None:
        """Dispatch a key press/release through the event map.

        All matching handlers (simple and compound) are called.
        Falls back to the base KeySlot handlers if the event map
        returns no matches.
        """
        if pressed:
            handlers = self._events.handle_key_press()
        else:
            handlers = self._events.handle_key_release()

        if handlers:
            for handler in handlers:
                await handler()
        else:
            # Fall back to base KeySlot on_press/on_release decorators
            await super().dispatch(pressed)

    # -- Private helpers ---------------------------------------------------

    @staticmethod
    def _encode_image(
        img: Image.Image, image_format: str = "JPEG", quality: int = 90
    ) -> bytes:
        """Encode a PIL image in the specified format."""
        buf = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        fmt = image_format.upper()
        if fmt == "BMP":
            img.save(buf, format="BMP")
        else:
            img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()
