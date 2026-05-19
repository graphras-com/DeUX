"""Touch-strip container managing card zones on the Stream Deck LCD strip."""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from ..render.background_layer import BackgroundLayer
from .cards.base import Card
from .cards.blank import BlankCard

logger = logging.getLogger(__name__)


class TouchStrip:
    """Manage card zones on the Stream Deck touch strip.

    The number of card zones is determined by the device's dial count
    (typically 4 for Stream Deck+).

    The *background_color* fills the entire touchscreen canvas — including
    the margin and gap areas outside card panels.  Each :class:`Screen`
    owns its own ``TouchStrip``, so different screens can use different
    background colours.

    An optional background SVG (covering the full touchscreen, e.g.
    800x100 on Stream Deck+) can be set via :meth:`set_background_svg`.
    When set, the SVG is rasterized once, sliced into per-panel tiles,
    and cached.  Cards render with transparent backgrounds and are
    composited onto their tile at render time.

    Parameters
    ----------
    panel_count
        Number of card zones.
    panel_width
        Width of each card panel in pixels.
    panel_height
        Height of each card panel in pixels.
    background_color
        Initial background colour.
    """

    def __init__(
        self,
        panel_count: int = 4,
        panel_width: int = 200,
        panel_height: int = 100,
        background_color: str = "black",
    ) -> None:
        self._panel_count = panel_count
        self._panel_width = panel_width
        self._panel_height = panel_height
        self._cards: list[Card] = [BlankCard() for _ in range(panel_count)]
        self._background_color = background_color
        self._bg_layer = BackgroundLayer(
            "touchstrip",
            panel_count=panel_count,
            panel_width=panel_width,
            panel_height=panel_height,
        )

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

        The same ``Card`` instance may be installed on multiple screens
        (and, on a single screen, in different slots across screens) —
        the strip's slot list is the single source of truth for routing,
        so no state is mutated on *card* itself.

        Parameters
        ----------
        index
            Card zone index.
        card
            A :class:`Card` subclass instance.

        Raises
        ------
        IndexError
            If *index* is out of range.
        TypeError
            If *card* is not a :class:`Card` instance.
        """
        if not 0 <= index < self._panel_count:
            raise IndexError(
                f"Card index must be 0-{self._panel_count - 1}, got {index}"
            )
        if not isinstance(card, Card):
            msg = f"Expected a Card instance, got {type(card).__name__}"
            raise TypeError(msg)
        self._cards[index] = card

    @property
    def cards(self) -> list[Card]:
        """All card zones on this touch strip.

        Returns a shallow copy; external code cannot mutate internal state.
        """
        return list(self._cards)

    @property
    def panel_width(self) -> int:
        """Width of each card panel in pixels."""
        return self._panel_width

    @property
    def panel_height(self) -> int:
        """Height of each card panel in pixels."""
        return self._panel_height

    @property
    def bg_tiles(self) -> list[Image.Image] | None:
        """Pre-sliced background tiles, or ``None`` if no background SVG is set.

        Returns a shallow copy when tiles exist; external code cannot mutate internal state.
        """
        return self._bg_layer.tiles

    def bg_tile(self, index: int) -> Image.Image | None:
        """Return the cached background tile for panel *index*, or ``None``.

        Parameters
        ----------
        index
            Panel index (0 to panel_count-1).

        Returns
        -------
        Image.Image or None
            The RGB tile image, or ``None`` if no background SVG is set.
        """
        return self._bg_layer.tile(index)

    @property
    def bg_svg_root(self) -> ET.Element | None:
        """The parsed background SVG root element, or ``None``.

        Used by the SVG-native pipeline to compose background layers
        with card SVGs at the vector level before rasterisation.
        """
        return self._bg_layer.svg_root

    @property
    def bg_layer(self) -> BackgroundLayer:
        """The background layer managing SVG, tiles, and rasterisation."""
        return self._bg_layer

    def set_background_svg(self, svg_data: bytes) -> None:
        """Set a background SVG for the entire touchstrip.

        The SVG is parsed and cached as an XML element tree for
        SVG-level composition.  For backward compatibility, the SVG
        is also rasterized and sliced into per-panel PIL tiles.

        All cards are marked dirty so they re-render with the new
        background.

        Parameters
        ----------
        svg_data
            Raw SVG content as UTF-8 bytes.
        """
        self._bg_layer.set_svg(svg_data)
        for card in self._cards:
            card.mark_dirty()

    def set_background_svg_from_file(self, path: str | Path) -> None:
        """Load a background SVG from a file path.

        Convenience wrapper around :meth:`set_background_svg`.

        Parameters
        ----------
        path
            Path to an SVG file.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist.
        """
        svg_data = Path(path).read_bytes()
        self.set_background_svg(svg_data)

    def clear_background_svg(self) -> None:
        """Remove the background SVG and revert to solid-colour background.

        All cards are marked dirty so they re-render without the
        background tiles.
        """
        self._bg_layer.clear()
        for card in self._cards:
            card.mark_dirty()

    def invalidate_background(self) -> None:
        """Re-rasterize the cached background SVG tiles.

        Call this when a global property that affects SVG rendering
        (such as the active stylesheet) has changed.  If no background
        SVG is set this is a no-op.
        """
        if self._bg_layer.has_svg:
            self._bg_layer.invalidate()

    async def set_background_svg_async(self, svg_data: bytes) -> None:
        """Async variant of :meth:`set_background_svg`.

        Offloads the CPU-bound SVG rasterisation to a worker thread
        so the event loop stays responsive.

        Parameters
        ----------
        svg_data
            Raw SVG content as UTF-8 bytes.
        """
        self._bg_layer.set_svg_deferred(svg_data)
        await asyncio.to_thread(self._bg_layer.rasterize)
        for card in self._cards:
            card.mark_dirty()

    async def invalidate_background_async(self) -> None:
        """Async variant of :meth:`invalidate_background`.

        Offloads the CPU-bound SVG rasterisation to a worker thread
        so the event loop stays responsive.
        """
        if self._bg_layer.has_svg:
            await asyncio.to_thread(self._bg_layer.rasterize)

    @property
    def any_dirty(self) -> bool:
        """Whether any card zone needs re-rendering."""
        return any(card.is_dirty for card in self._cards)
