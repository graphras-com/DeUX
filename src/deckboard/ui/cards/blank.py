"""BlankCard: a minimal card that renders an empty black panel."""

from __future__ import annotations

from PIL import Image

from ...render.metrics import PANEL_HEIGHT, PANEL_WIDTH
from .base import Card


class BlankCard(Card):
    """A card that renders a plain black rectangle.

    Used as the default placeholder in :class:`~deckboard.ui.touch_strip.TouchStrip`
    before the user assigns real cards.
    """

    def render(self) -> Image.Image:
        return Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
