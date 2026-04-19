"""Touch-strip container managing card zones on the Stream Deck LCD strip."""

from __future__ import annotations

from .cards.base import Card
from .cards.blank import BlankCard


class TouchStrip:
    """Manage card zones on the Stream Deck touch strip.

    The number of card zones is determined by the device's dial count
    (typically 4 for Stream Deck+).

    The *background_color* fills the entire touchscreen canvas — including
    the margin and gap areas outside card panels.  Each :class:`Screen`
    owns its own ``TouchStrip``, so different screens can use different
    background colours.

    Args:
        panel_count: Number of card zones.
        background_color: Initial background colour.
    """

    def __init__(
        self,
        panel_count: int = 4,
        background_color: str = "black",
    ) -> None:
        self._panel_count = panel_count
        self._cards: list[Card] = [BlankCard(i) for i in range(panel_count)]
        self._background_color = background_color

    @property
    def panel_count(self) -> int:
        """Number of card zones on this touch strip."""
        return self._panel_count

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
        """Get a card zone by index."""
        if not 0 <= index < self._panel_count:
            raise IndexError(
                f"Card index must be 0-{self._panel_count - 1}, got {index}"
            )
        return self._cards[index]

    def set_card(self, index: int, card: Card) -> None:
        """Replace the card at *index* with a custom card.

        Args:
            index: Card zone index.
            card: A :class:`Card` subclass instance.

        Raises:
            IndexError: If *index* is out of range.
            TypeError: If *card* is not a :class:`Card` instance.
        """
        if not 0 <= index < self._panel_count:
            raise IndexError(
                f"Card index must be 0-{self._panel_count - 1}, got {index}"
            )
        if not isinstance(card, Card):
            msg = f"Expected a Card instance, got {type(card).__name__}"
            raise TypeError(msg)
        card._index = index
        self._cards[index] = card

    @property
    def cards(self) -> list[Card]:
        return self._cards

    @property
    def any_dirty(self) -> bool:
        return any(card.is_dirty for card in self._cards)
