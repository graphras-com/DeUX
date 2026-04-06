"""Status card with the standard icon, label, and value layout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from ...render.touch_renderer import render_status_card_image
from .base import Card

if TYPE_CHECKING:
    from ...render.icons import IconManager


class StatusCard(Card):
    """A card displaying an icon, label, and value in the classic layout.

    Layout (197x98):
      - Left side: 55x55 icon (centered vertically, 8px from left)
      - Right side: label on top, value below

    Usage::

        card.set_icon("mdi:volume-high")
        card.set_label("Volume")
        card.set_value("75%")
    """

    def __init__(self, index: int) -> None:
        super().__init__(index)
        self._icon_name: str | None = None
        self._icon_color: str = "white"
        self._label: str | None = None
        self._value: str | None = None
        self._icon_image: Image.Image | None = None

    # -- Configuration methods (return self for chaining) ------------------

    def set_icon(self, name: str, color: str = "white") -> StatusCard:
        """Set the icon by Iconify name.

        Args:
            name: Icon name in ``prefix:name`` format.
            color: Icon color. Defaults to white.
        """
        self._icon_name = name
        self._icon_color = color
        self._dirty = True
        return self

    def set_label(self, label: str | None) -> StatusCard:
        """Set the primary text label."""
        self._label = label
        self._dirty = True
        return self

    def set_value(self, value: str | None) -> StatusCard:
        """Set the secondary value text."""
        self._value = value
        self._dirty = True
        return self

    def clear(self) -> StatusCard:
        """Clear all content from this card zone."""
        self._icon_name = None
        self._label = None
        self._value = None
        self._icon_image = None
        self._rendered = None
        self._dirty = True
        return self

    # -- Properties --------------------------------------------------------

    @property
    def icon_name(self) -> str | None:
        return self._icon_name

    @property
    def icon_color(self) -> str:
        return self._icon_color

    @property
    def label(self) -> str | None:
        return self._label

    @property
    def value(self) -> str | None:
        return self._value

    # -- Icon image (set externally by the render pipeline) ----------------

    def set_icon_image(self, img: Image.Image | None) -> None:
        """Set the pre-fetched icon image for rendering.

        Called by the render pipeline after fetching the icon from the
        :class:`~deckboard.render.icons.IconManager`.
        """
        self._icon_image = img

    async def prepare_assets(self, icons: IconManager) -> None:
        """Pre-fetch the icon needed for this card before rendering."""
        if self._icon_name is None:
            self._icon_image = None
            return
        self._icon_image = await icons.get(self._icon_name, color=self._icon_color)

    # -- Rendering ---------------------------------------------------------

    def render(self) -> Image.Image:
        """Render this card using the classic icon/label/value layout.

        Returns:
            A PANEL_WIDTH x PANEL_HEIGHT RGB :class:`~PIL.Image.Image`.
        """
        return render_status_card_image(
            icon=self._icon_image,
            label=self._label,
            value=self._value,
        )
