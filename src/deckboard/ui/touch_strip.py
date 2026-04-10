"""Touch-strip container managing the 4 card zones on the Stream Deck+ LCD strip."""

from __future__ import annotations

from ..render.metrics import PANEL_COUNT
from .cards.base import Card
from .cards.blank import BlankCard


class TouchStrip:
    """Manage the 4 card zones on the Stream Deck+ touch strip.

    The *background_color* fills the entire 800x100 canvas — including
    the margin and gap areas outside card panels.  Each :class:`Screen`
    owns its own ``TouchStrip``, so different screens can use different
    background colours.
    """

    def __init__(self, background_color: str = "black") -> None:
        self._cards: list[Card] = [BlankCard(i) for i in range(PANEL_COUNT)]
        self._background_color = background_color

    @property
    def background_color(self) -> str:
        """The fill colour for the touchscreen canvas (margins and gaps)."""
        return self._background_color

    @background_color.setter
    def background_color(self, value: str) -> None:
        if self._background_color != value:
            self._background_color = value
            for card in self._cards:
                card.mark_dirty()

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
