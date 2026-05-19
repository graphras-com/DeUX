"""DeckEventRouter: extracted event dispatch logic for Stream Deck devices.

Routes transport events (key presses, encoder turns/presses, touch
events) to the appropriate screen handlers, separated from the
lifecycle and rendering responsibilities of
:class:`~deux.runtime.deck.Deck`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .events import (
    DeckEvent,
    EncoderPressEvent,
    EncoderTurnEvent,
    KeyEvent,
    TouchEvent,
)

if TYPE_CHECKING:
    from .deck import Deck

logger = logging.getLogger(__name__)


class DeckEventRouter:
    """Routes transport events to the active screen's handlers.

    This class owns the event dispatch logic that was previously
    embedded in ``Deck._dispatch``.  It operates on the deck's active
    screen, metrics, and refresh/drain helpers via a back-reference to
    the parent ``Deck`` instance.

    Parameters
    ----------
    deck : Deck
        The parent deck instance whose state is used for routing.
    """

    def __init__(self, deck: Deck) -> None:
        self._deck = deck

    async def dispatch(self, event: DeckEvent) -> None:
        """Dispatch a single event to the appropriate handler on the active screen.

        Parameters
        ----------
        event : DeckEvent
            The transport event to route.  Supported types are
            :class:`KeyEvent`, :class:`EncoderTurnEvent`,
            :class:`EncoderPressEvent`, and :class:`TouchEvent`.
        """
        deck = self._deck
        screen = deck._current_screen()
        if not screen:
            return

        if isinstance(event, KeyEvent):
            await self._dispatch_key(screen, event)
        elif isinstance(event, EncoderTurnEvent):
            await self._dispatch_encoder_turn(screen, event)
        elif isinstance(event, EncoderPressEvent):
            await self._dispatch_encoder_press(screen, event)
        elif isinstance(event, TouchEvent):
            await self._dispatch_touch(screen, event)

    async def _dispatch_key(self, screen: Any, event: KeyEvent) -> None:
        """Dispatch a key press/release event.

        Parameters
        ----------
        screen : Screen
            The currently active screen.
        event : KeyEvent
            The key event to dispatch.
        """
        key_slot = screen.keys.get(event.key)
        if key_slot:
            await key_slot.dispatch(event.pressed)
            if key_slot.is_dirty:
                await self._deck.refresh()

    async def _dispatch_encoder_turn(
        self, screen: Any, event: EncoderTurnEvent
    ) -> None:
        """Dispatch an encoder turn event.

        Parameters
        ----------
        screen : Screen
            The currently active screen.
        event : EncoderTurnEvent
            The encoder turn event to dispatch.
        """
        encoder = screen.encoders.get(event.encoder)
        if encoder:
            await encoder.dispatch_turn(event.direction)
        if screen.touch_strip is not None:
            card = screen.touch_strip.card(event.encoder)
            await card.dispatch_encoder_turn(event.direction)
            await self._deck._drain_card_callbacks(card)
            if card.is_dirty:
                await self._deck.refresh()

    async def _dispatch_encoder_press(
        self, screen: Any, event: EncoderPressEvent
    ) -> None:
        """Dispatch an encoder press/release event.

        Parameters
        ----------
        screen : Screen
            The currently active screen.
        event : EncoderPressEvent
            The encoder press event to dispatch.
        """
        encoder = screen.encoders.get(event.encoder)
        if encoder:
            await encoder.dispatch_press(event.pressed)
        if screen.touch_strip is not None:
            card = screen.touch_strip.card(event.encoder)
            if event.pressed:
                await card.dispatch_encoder_press()
            else:
                await card.dispatch_encoder_release()
            await self._deck._drain_card_callbacks(card)
            if card.is_dirty:
                await self._deck.refresh()

    async def _dispatch_touch(self, screen: Any, event: TouchEvent) -> None:
        """Dispatch a touchscreen event.

        Parameters
        ----------
        screen : Screen
            The currently active screen.
        event : TouchEvent
            The touch event to dispatch.
        """
        if screen.touch_strip is not None and self._deck._metrics is not None:
            zone = event.compute_zone(self._deck._metrics)
            card = screen.touch_strip.card(zone)
            await card.dispatch_touch(event)
