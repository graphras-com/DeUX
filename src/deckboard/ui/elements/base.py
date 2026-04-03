"""Base render-only element type for touch-strip card composition."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...touchscreen import Widget


class Element:
    """Base type for render-only elements placed inside a card."""

    selectable: bool = False

    def __init__(self) -> None:
        self._card: Widget | None = None
        self._widget: Widget | None = None

    def bind_to_card(self, card: Widget) -> None:
        """Attach this element to a parent card."""
        self._card = card
        self._widget = card
