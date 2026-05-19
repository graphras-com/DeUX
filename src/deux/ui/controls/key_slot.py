"""KeySlot class: wraps a physical key on the Stream Deck."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...runtime.events import AsyncHandler

logger = logging.getLogger(__name__)


class KeySlot:
    """Represents a single physical key on the Stream Deck.

    Examples
    --------
    Use decorators to register event handlers::

        @key.on_press
        async def handle():
            print("pressed!")
    """

    def __init__(self) -> None:
        self._press_handler: AsyncHandler | None = None
        self._release_handler: AsyncHandler | None = None
        self._image_bytes: bytes | None = None
        self._dirty = True
        self._refresh_callbacks: list[AsyncHandler] = []

    def set_refresh_callback(self, callback: AsyncHandler) -> None:
        """Register an async callback the key can invoke to request a refresh.

        Multiple callbacks may be registered (e.g. when the same key is
        installed on screens belonging to different decks).  Each call
        adds *callback* to the list — duplicates are silently ignored so
        that re-wiring the same deck does not accumulate entries.

        This is set automatically by :class:`~deux.runtime.deck.Deck`
        when a screen is activated, so any code path (key handler,
        background task, external state change) can call
        :meth:`request_refresh` to trigger a re-render.

        Parameters
        ----------
        callback
            Async callable that triggers a deck refresh.
        """
        if callback not in self._refresh_callbacks:
            self._refresh_callbacks.append(callback)

    def remove_refresh_callback(self, callback: AsyncHandler) -> None:
        """Remove a previously registered refresh callback.

        No-op if *callback* is not in the list.

        Parameters
        ----------
        callback
            The callback to remove.
        """
        with contextlib.suppress(ValueError):
            self._refresh_callbacks.remove(callback)

    async def request_refresh(self) -> None:
        """Ask all registered decks to re-render the active screen.

        No-op if no refresh callbacks have been registered.
        """
        for cb in list(self._refresh_callbacks):
            await cb()

    def on_press(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for key press events.

        Examples
        --------
        ::

            @key.on_press
            async def handle():
                ...
        """
        self._press_handler = handler
        return handler

    def on_release(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for key release events.

        Examples
        --------
        ::

            @key.on_release
            async def handle():
                ...
        """
        self._release_handler = handler
        return handler

    async def dispatch(self, pressed: bool) -> None:
        """Dispatch a press or release event through the internal hook.

        Subclasses should override :meth:`_dispatch_event` to customise
        event handling without replacing the public entry point.
        """
        await self._dispatch_event(pressed)

    async def _dispatch_event(self, pressed: bool) -> None:
        """Internal dispatch hook — override in subclasses.

        The default implementation calls the registered press/release handler.

        Parameters
        ----------
        pressed : bool
            ``True`` for a press event, ``False`` for a release event.
        """
        handler = self._press_handler if pressed else self._release_handler
        if handler is not None:
            await handler()

    @property
    def is_dirty(self) -> bool:
        """Whether the key image needs re-rendering."""
        return self._dirty

    def mark_dirty(self) -> None:
        """Flag this key for re-rendering on the next refresh."""
        self._dirty = True

    def mark_clean(self) -> None:
        """Clear the dirty flag after the key image has been flushed."""
        self._dirty = False

    def set_rendered_image(self, image_bytes: bytes) -> None:
        """Store pre-rendered JPEG bytes (set by Deck during render)."""
        self._image_bytes = image_bytes
        self._dirty = False

    @property
    def image_bytes(self) -> bytes | None:
        """The pre-rendered image bytes, or ``None`` if not yet rendered."""
        return self._image_bytes
