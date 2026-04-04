"""Base interactive control type for touch-strip card composition."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..cards.base import Card


class Control:
    """Base type for interactive controls placed inside a card."""

    selectable: bool = True

    def __init__(self) -> None:
        self._card: Card | None = None

    def bind_to_card(self, card: Card) -> None:
        """Attach this control to a parent card."""
        self._card = card
