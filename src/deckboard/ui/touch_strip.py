"""Touch-strip container managing the 4 card zones on the Stream Deck+ LCD strip."""

from __future__ import annotations

from ..render.metrics import PANEL_COUNT
from .cards.base import Card


class TouchStrip:
    """Manage the 4 card zones on the Stream Deck+ touch strip."""

    def __init__(self) -> None:
        # Import here to avoid circular imports at module level
        from .cards.status import StatusCard

        self._cards: list[Card] = [StatusCard(i) for i in range(PANEL_COUNT)]

    def card(self, index: int) -> Card:
        """Get a card zone by index (0-3)."""
        if not 0 <= index < PANEL_COUNT:
            raise IndexError(f"Card index must be 0-{PANEL_COUNT - 1}, got {index}")
        return self._cards[index]

    def set_card(self, index: int, card: Card) -> None:
        """Replace the card at *index* with a custom card.

        Args:
            index: Card zone index (0-3).
            card: A :class:`Card` subclass instance.

        Raises:
            IndexError: If *index* is out of range.
            TypeError: If *card* is not a :class:`Card` instance.
        """
        if not 0 <= index < PANEL_COUNT:
            raise IndexError(f"Card index must be 0-{PANEL_COUNT - 1}, got {index}")
        if not isinstance(card, Card):
            msg = f"Expected a Card instance, got {type(card).__name__}"
            raise TypeError(msg)
        self._cards[index] = card

    @property
    def cards(self) -> list[Card]:
        return self._cards

    @property
    def any_dirty(self) -> bool:
        return any(card.is_dirty for card in self._cards)
