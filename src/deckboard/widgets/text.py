"""Text sub-elements for touchscreen widget zones.

The hierarchy is::

    LargeText   (full-width single-line text, same height as LargeSlider)
    SmallText   (compact single-line text, same height as SmallSlider)

Text elements are non-selectable: they render inside a :class:`TouchPanel`
alongside sliders but are skipped when the dial cycles through active
elements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from ..image import get_font, get_large_font, get_small_font
from ..ui.elements.base import Element

if TYPE_CHECKING:
    from ..touchscreen import Widget  # abstract base — any Widget subclass

# ── Layout constants (matching slider.py dimensions) ─────────────────────

# Large text — same slot height as LargeSlider
_LARGE_MARGIN_X = 2

# Small text — same slot height as SmallSlider
_SMALL_MARGIN_X = 4


def _truncate_text(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> str:
    """Truncate *text* with an ellipsis if it exceeds *max_width* pixels."""
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width:
        return text

    ellipsis = "\u2026"
    for end in range(len(text), 0, -1):
        candidate = text[:end] + ellipsis
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return candidate
    return ellipsis


class LargeText(Element):
    """A full-width, single-line text element the same height as a LargeSlider.

    The text is displayed centred within the slot.  If it overflows the
    available width it is truncated with an ellipsis (``\u2026``).

    Args:
        text: Initial display text.
        color: Text colour.  Defaults to ``"white"``.
    """

    def __init__(self, text: str = "", *, color: str = "white") -> None:
        super().__init__()
        self._text = text
        self._color = color

    # -- Properties --------------------------------------------------------

    @property
    def text(self) -> str:
        return self._text

    @property
    def color(self) -> str:
        return self._color

    # -- Mutators ----------------------------------------------------------

    def set_text(self, text: str) -> None:
        """Update the displayed text.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._text = text
        if self._card is not None:
            self._card.mark_dirty()

    def set_color(self, color: str) -> None:
        """Update the text colour.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._color = color
        if self._card is not None:
            self._card.mark_dirty()

    # -- Rendering ---------------------------------------------------------

    def render_onto(
        self,
        img: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        active: bool = False,
    ) -> None:
        """Draw this text element onto *img* within the given rectangle.

        The text is horizontally centred and vertically centred within
        the slot.  Overflow is truncated with an ellipsis.

        Args:
            img: Target image (modified in-place).
            x: Left edge.
            y: Top edge.
            width: Available width.
            height: Available height.
            active: Ignored — text elements are never active.
        """
        draw = ImageDraw.Draw(img)
        font = get_large_font()

        mx = _LARGE_MARGIN_X
        available_w = width - 2 * mx

        display = _truncate_text(self._text, font, available_w, draw)

        bbox = draw.textbbox((0, 0), display, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Centre horizontally and vertically
        text_x = x + mx + (available_w - text_w) // 2
        text_y = y + (height - text_h) // 2

        draw.text((text_x, text_y), display, fill=self._color, font=font)


class SmallText(Element):
    """A compact, single-line text element the same height as a SmallSlider.

    Unlike :class:`SmallSlider`, there is no label column — the text
    occupies the entire width of the slot with a small horizontal margin.
    If the text overflows it is truncated with an ellipsis (``\u2026``).

    Args:
        text: Initial display text.
        color: Text colour.  Defaults to ``"white"``.
    """

    def __init__(self, text: str = "", *, color: str = "white") -> None:
        super().__init__()
        self._text = text
        self._color = color

    # -- Properties --------------------------------------------------------

    @property
    def text(self) -> str:
        return self._text

    @property
    def color(self) -> str:
        return self._color

    # -- Mutators ----------------------------------------------------------

    def set_text(self, text: str) -> None:
        """Update the displayed text.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._text = text
        if self._card is not None:
            self._card.mark_dirty()

    def set_color(self, color: str) -> None:
        """Update the text colour.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._color = color
        if self._card is not None:
            self._card.mark_dirty()

    # -- Rendering ---------------------------------------------------------

    def render_onto(
        self,
        img: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        active: bool = False,
    ) -> None:
        """Draw this text element onto *img* within the given rectangle.

        The text is horizontally centred and vertically centred within
        the slot.  Overflow is truncated with an ellipsis.

        Args:
            img: Target image (modified in-place).
            x: Left edge.
            y: Top edge.
            width: Available width.
            height: Available height.
            active: Ignored — text elements are never active.
        """
        draw = ImageDraw.Draw(img)
        font = get_small_font()

        mx = _SMALL_MARGIN_X
        available_w = width - 2 * mx

        display = _truncate_text(self._text, font, available_w, draw)

        bbox = draw.textbbox((0, 0), display, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Centre horizontally and vertically
        text_x = x + mx + (available_w - text_w) // 2
        text_y = y + (height - text_h) // 2 - 1

        draw.text((text_x, text_y), display, fill=self._color, font=font)
