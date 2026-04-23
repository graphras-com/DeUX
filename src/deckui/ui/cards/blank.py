"""BlankCard: a transparent placeholder card for empty touch-strip slots."""

from __future__ import annotations

from .base import Card


class BlankCard(Card):
    """A card that renders nothing, letting the touchstrip background show through.

    Used as the default placeholder in :class:`~deckui.ui.touch_strip.TouchStrip`
    before the user assigns real cards.  Returns ``None`` from :meth:`render`
    so the compositor skips the slot and the
    :attr:`~deckui.ui.touch_strip.TouchStrip.background_color` is visible.
    """

    def render(self) -> None:
        return None
