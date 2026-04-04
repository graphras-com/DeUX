"""Dual-value sub-elements for touchscreen widget zones.

The hierarchy is::

    LargeDualValue  (two icon+value pairs side by side, same height as LargeSlider)
    SmallDualValue  (two icon+value pairs side by side, same height as SmallSlider)

Each element is divided into two equal sections (left and right).  Every
section displays a small icon followed by a left-aligned value string.
There is no visible divider, no frame, and no label.

Dual-value elements are non-selectable: they render inside a
:class:`StackCard` alongside sliders but are skipped when the encoder
cycles through active elements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from ...render.fonts import get_large_font, get_small_font
from .base import Element

if TYPE_CHECKING:
    from ..cards.base import Card

# ── Layout constants ─────────────────────────────────────────────────────

# Large dual-value — same slot height as LargeSlider (PANEL_HEIGHT // 2)
_LARGE_ICON_SIZE = 26
_LARGE_ICON_MARGIN_LEFT = 4
_LARGE_ICON_GAP = 4  # gap between icon column and value text

# Small dual-value — same slot height as SmallSlider (PANEL_HEIGHT // 4)
_SMALL_ICON_SIZE = 13
_SMALL_ICON_MARGIN_LEFT = 4
_SMALL_ICON_GAP = 3  # gap between icon column and value text


def _truncate_value(
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


class LargeDualValue(Element):
    """Two icon + value pairs displayed side by side, same height as a LargeSlider.

    The element is split into two equal halves.  Each half shows a small
    icon on the left and a left-aligned value string to its right.  The
    icon occupies a fixed-width column so values stay aligned when
    multiple ``LargeDualValue`` elements are stacked vertically.

    Args:
        left_icon: PIL Image for the left section icon (or ``None``).
        left_value: Display string for the left section.
        right_icon: PIL Image for the right section icon (or ``None``).
        right_value: Display string for the right section.
        color: Text colour for both values.  Defaults to ``"white"``.
    """

    def __init__(
        self,
        left_value: str = "",
        right_value: str = "",
        *,
        left_icon: Image.Image | None = None,
        right_icon: Image.Image | None = None,
        color: str = "white",
    ) -> None:
        super().__init__()
        self._left_icon = left_icon
        self._left_value = left_value
        self._right_icon = right_icon
        self._right_value = right_value
        self._color = color

    # -- Properties --------------------------------------------------------

    @property
    def left_icon(self) -> Image.Image | None:
        return self._left_icon

    @property
    def left_value(self) -> str:
        return self._left_value

    @property
    def right_icon(self) -> Image.Image | None:
        return self._right_icon

    @property
    def right_value(self) -> str:
        return self._right_value

    @property
    def color(self) -> str:
        return self._color

    # -- Mutators ----------------------------------------------------------

    def set_left_icon(self, icon: Image.Image | None) -> None:
        """Update the left section icon.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._left_icon = icon
        if self._card is not None:
            self._card.mark_dirty()

    def set_left_value(self, value: str) -> None:
        """Update the left section value text.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._left_value = value
        if self._card is not None:
            self._card.mark_dirty()

    def set_right_icon(self, icon: Image.Image | None) -> None:
        """Update the right section icon.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._right_icon = icon
        if self._card is not None:
            self._card.mark_dirty()

    def set_right_value(self, value: str) -> None:
        """Update the right section value text.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._right_value = value
        if self._card is not None:
            self._card.mark_dirty()

    def set_color(self, color: str) -> None:
        """Update the text colour for both values.

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
        """Draw both icon+value sections onto *img* within the given rectangle.

        Args:
            img: Target image (modified in-place).
            x: Left edge.
            y: Top edge.
            width: Available width.
            height: Available height.
            active: Ignored — dual-value elements are never active.
        """
        draw = ImageDraw.Draw(img)
        font = get_large_font()

        half_w = width // 2
        icon_size = _LARGE_ICON_SIZE
        icon_ml = _LARGE_ICON_MARGIN_LEFT
        icon_gap = _LARGE_ICON_GAP

        # Fixed icon column width: margin + icon + gap
        icon_col_w = icon_ml + icon_size + icon_gap

        # Left section
        self._render_section(
            draw,
            img,
            font,
            x,
            y,
            half_w,
            height,
            icon_size,
            icon_ml,
            icon_col_w,
            self._left_icon,
            self._left_value,
        )

        # Right section
        self._render_section(
            draw,
            img,
            font,
            x + half_w,
            y,
            width - half_w,
            height,
            icon_size,
            icon_ml,
            icon_col_w,
            self._right_icon,
            self._right_value,
        )

    def _render_section(
        self,
        draw: ImageDraw.ImageDraw,
        img: Image.Image,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        sx: int,
        sy: int,
        sw: int,
        sh: int,
        icon_size: int,
        icon_ml: int,
        icon_col_w: int,
        icon: Image.Image | None,
        value: str,
    ) -> None:
        """Render a single icon+value section."""
        # Icon — centred vertically within the icon column
        if icon is not None:
            sized = icon.resize((icon_size, icon_size), Image.LANCZOS)
            icon_x = sx + icon_ml
            icon_y = sy + (sh - icon_size) // 2
            if sized.mode == "RGBA":
                img.paste(sized, (icon_x, icon_y), sized)
            else:
                img.paste(sized, (icon_x, icon_y))

        # Value — left-aligned after the icon column, vertically centred
        text_x = sx + icon_col_w
        available_w = sw - icon_col_w
        display = _truncate_value(value, font, max(available_w, 0), draw)

        bbox = draw.textbbox((0, 0), display, font=font)
        text_h = bbox[3] - bbox[1]
        text_y = sy + (sh - text_h) // 2

        draw.text((text_x, text_y), display, fill=self._color, font=font)


class SmallDualValue(Element):
    """Two icon + value pairs displayed side by side, same height as a SmallSlider.

    Compact version of :class:`LargeDualValue` with a smaller icon and
    font.  Suitable for stacking four rows in a single widget zone.

    Args:
        left_icon: PIL Image for the left section icon (or ``None``).
        left_value: Display string for the left section.
        right_icon: PIL Image for the right section icon (or ``None``).
        right_value: Display string for the right section.
        color: Text colour for both values.  Defaults to ``"white"``.
    """

    def __init__(
        self,
        left_value: str = "",
        right_value: str = "",
        *,
        left_icon: Image.Image | None = None,
        right_icon: Image.Image | None = None,
        color: str = "white",
    ) -> None:
        super().__init__()
        self._left_icon = left_icon
        self._left_value = left_value
        self._right_icon = right_icon
        self._right_value = right_value
        self._color = color

    # -- Properties --------------------------------------------------------

    @property
    def left_icon(self) -> Image.Image | None:
        return self._left_icon

    @property
    def left_value(self) -> str:
        return self._left_value

    @property
    def right_icon(self) -> Image.Image | None:
        return self._right_icon

    @property
    def right_value(self) -> str:
        return self._right_value

    @property
    def color(self) -> str:
        return self._color

    # -- Mutators ----------------------------------------------------------

    def set_left_icon(self, icon: Image.Image | None) -> None:
        """Update the left section icon.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._left_icon = icon
        if self._card is not None:
            self._card.mark_dirty()

    def set_left_value(self, value: str) -> None:
        """Update the left section value text.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._left_value = value
        if self._card is not None:
            self._card.mark_dirty()

    def set_right_icon(self, icon: Image.Image | None) -> None:
        """Update the right section icon.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._right_icon = icon
        if self._card is not None:
            self._card.mark_dirty()

    def set_right_value(self, value: str) -> None:
        """Update the right section value text.

        Marks the parent widget dirty so the change is rendered on the
        next refresh cycle.
        """
        self._right_value = value
        if self._card is not None:
            self._card.mark_dirty()

    def set_color(self, color: str) -> None:
        """Update the text colour for both values.

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
        """Draw both icon+value sections onto *img* within the given rectangle.

        Args:
            img: Target image (modified in-place).
            x: Left edge.
            y: Top edge.
            width: Available width.
            height: Available height.
            active: Ignored — dual-value elements are never active.
        """
        draw = ImageDraw.Draw(img)
        font = get_small_font()

        half_w = width // 2
        icon_size = _SMALL_ICON_SIZE
        icon_ml = _SMALL_ICON_MARGIN_LEFT
        icon_gap = _SMALL_ICON_GAP

        # Fixed icon column width: margin + icon + gap
        icon_col_w = icon_ml + icon_size + icon_gap

        # Left section
        self._render_section(
            draw,
            img,
            font,
            x,
            y,
            half_w,
            height,
            icon_size,
            icon_ml,
            icon_col_w,
            self._left_icon,
            self._left_value,
        )

        # Right section
        self._render_section(
            draw,
            img,
            font,
            x + half_w,
            y,
            width - half_w,
            height,
            icon_size,
            icon_ml,
            icon_col_w,
            self._right_icon,
            self._right_value,
        )

    def _render_section(
        self,
        draw: ImageDraw.ImageDraw,
        img: Image.Image,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        sx: int,
        sy: int,
        sw: int,
        sh: int,
        icon_size: int,
        icon_ml: int,
        icon_col_w: int,
        icon: Image.Image | None,
        value: str,
    ) -> None:
        """Render a single icon+value section."""
        # Icon — centred vertically within the icon column
        if icon is not None:
            sized = icon.resize((icon_size, icon_size), Image.LANCZOS)
            icon_x = sx + icon_ml
            icon_y = sy + (sh - icon_size) // 2
            if sized.mode == "RGBA":
                img.paste(sized, (icon_x, icon_y), sized)
            else:
                img.paste(sized, (icon_x, icon_y))

        # Value — left-aligned after the icon column, vertically centred
        text_x = sx + icon_col_w
        available_w = sw - icon_col_w
        display = _truncate_value(value, font, max(available_w, 0), draw)

        bbox = draw.textbbox((0, 0), display, font=font)
        text_h = bbox[3] - bbox[1]
        text_y = sy + (sh - text_h) // 2 - 1

        draw.text((text_x, text_y), display, fill=self._color, font=font)
