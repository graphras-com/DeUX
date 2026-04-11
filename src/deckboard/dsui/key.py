"""DsuiKey: a physical key backed by a .dsui package."""

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
    """A physical key whose layout and events are defined by a .dsui package.

    ``DsuiKey`` extends :class:`~deckboard.ui.controls.key_slot.KeySlot`
    so that it is accepted wherever a ``KeySlot`` is expected.  It
    replaces the icon + label rendering with SVG-based rendering from
    a ``.dsui`` package.

    Usage::

        from deckboard.dsui import load_package, DsuiKey

        spec = load_package("./PowerKey.dsui")
        key = DsuiKey(0, spec)
        key.set("label", "Shutdown")

        @key.on_event("activate")
        async def handle():
            ...

    Args:
        index: Key index (0-7 for Stream Deck+).
        spec: A validated :class:`~deckboard.dsui.schema.PackageSpec`.
    """

    def __init__(self, index: int, spec: PackageSpec) -> None:
        super().__init__(index)
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

    def render_image(self) -> bytes:
        """Render the SVG layout to JPEG bytes for the key.

        The SVG is rasterised and scaled to KEY_SIZE (120x120),
        then encoded as JPEG.

        Returns:
            JPEG-encoded image bytes.
        """
        img = self._renderer.render()
        if img.size != KEY_SIZE:
            img = img.resize(KEY_SIZE, Image.LANCZOS)
        return self._encode_jpeg(img)

    @property
    def has_dsui_content(self) -> bool:
        """Always ``True`` — this key is backed by a .dsui package."""
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
    def _encode_jpeg(img: Image.Image, quality: int = 90) -> bytes:
        """Encode a PIL image as JPEG bytes."""
        buf = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()
