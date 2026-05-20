"""Unified background-layer abstraction for Stream Deck surfaces.

Consolidates background SVG parsing, rasterisation, and tile slicing
that was previously scattered across :class:`~deux.ui.touch_strip.TouchStrip`,
:class:`~deux.ui.screen.Screen`, :class:`~deux.dui.svg_renderer.SvgRenderer`,
and :class:`~deux.runtime.renderer.DeckRenderer`.
"""

from __future__ import annotations

import io
import logging
import xml.etree.ElementTree as ET
from typing import Literal

from PIL import Image

from .._xml import safe_fromstring

logger = logging.getLogger(__name__)


class BackgroundLayer:
    """Own the SVG source, parsed XML root, and rasterised outputs for a background.

    A single ``BackgroundLayer`` encapsulates one background SVG and its
    derived artefacts: the parsed element tree, rasterised full image,
    and (for touchstrip backgrounds) per-panel tiles.  Two *kinds* are
    supported:

    ``"touchstrip"``
        A full-width SVG that is rasterised and sliced into per-panel
        tiles.  Requires *panel_count*, *panel_width*, and
        *panel_height*.

    ``"key"``
        A single-key SVG that is rasterised and encoded to device image
        bytes.  Requires *key_size* and *key_image_format*.

    Parameters
    ----------
    kind : ``"touchstrip"`` or ``"key"``
        Which surface this background belongs to.
    panel_count : int, optional
        Number of panels (touchstrip only).
    panel_width : int, optional
        Width of each panel in pixels (touchstrip only).
    panel_height : int, optional
        Height of each panel in pixels (touchstrip only).
    key_size : tuple[int, int], optional
        ``(width, height)`` of a key (key only).
    key_image_format : str, optional
        Device image format for key encoding (key only).
    """

    def __init__(
        self,
        kind: Literal["touchstrip", "key"],
        *,
        panel_count: int = 0,
        panel_width: int = 0,
        panel_height: int = 0,
        key_size: tuple[int, int] = (0, 0),
        key_image_format: str = "JPEG",
    ) -> None:
        self._kind = kind
        self._svg: bytes | None = None
        self._svg_root: ET.Element | None = None

        # Touchstrip state
        self._panel_count = panel_count
        self._panel_width = panel_width
        self._panel_height = panel_height
        self._tiles: list[bytes] | None = None

        # Key state
        self._key_size = key_size
        self._key_image_format = key_image_format
        self._key_image: bytes | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def kind(self) -> Literal["touchstrip", "key"]:
        """The surface kind this layer targets."""
        return self._kind

    @property
    def svg(self) -> bytes | None:
        """Raw SVG source bytes, or ``None`` if unset."""
        return self._svg

    @property
    def svg_root(self) -> ET.Element | None:
        """Parsed SVG root element, or ``None`` if unset."""
        return self._svg_root

    @property
    def tiles(self) -> list[bytes] | None:
        """Pre-sliced touchstrip tiles as PNG bytes (shallow copy), or ``None``.

        Only meaningful for ``kind="touchstrip"``.
        """
        if self._tiles is None:
            return None
        return list(self._tiles)

    def tile(self, index: int) -> bytes | None:
        """Return the cached background tile for panel *index*, or ``None``.

        Parameters
        ----------
        index : int
            Panel index (0-based).

        Returns
        -------
        bytes or None
            PNG-encoded tile bytes, or ``None`` if no background SVG is set
            or *index* is out of range.
        """
        if self._tiles is None or not 0 <= index < len(self._tiles):
            return None
        return self._tiles[index]

    @property
    def key_image(self) -> bytes | None:
        """Pre-rendered key background image bytes, or ``None``.

        Only meaningful for ``kind="key"``.
        """
        return self._key_image

    @property
    def has_svg(self) -> bool:
        """Whether a background SVG is currently set."""
        return self._svg is not None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def set_svg(self, svg_data: bytes, *, trusted: bool = False) -> None:
        """Set the background SVG and rasterise immediately.

        Parameters
        ----------
        svg_data : bytes
            Raw SVG content as UTF-8 bytes.
        trusted : bool, default=False
            When ``True``, uses stdlib ``ET.fromstring`` (suitable for
            bundled/trusted SVGs).  When ``False``, uses the safe parser
            that strips potentially dangerous elements.
        """
        self._svg = svg_data
        if trusted:
            self._svg_root = ET.fromstring(svg_data)  # noqa: S314 — trusted
        else:
            self._svg_root = safe_fromstring(svg_data)
        self._rasterize()

    def set_svg_deferred(self, svg_data: bytes, *, trusted: bool = False) -> None:
        """Parse the SVG without rasterising (for async workflows).

        Call :meth:`rasterize` separately (e.g. via ``asyncio.to_thread``)
        to perform the CPU-bound rasterisation step.

        Parameters
        ----------
        svg_data : bytes
            Raw SVG content as UTF-8 bytes.
        trusted : bool, default=False
            When ``True``, uses stdlib ``ET.fromstring``.
        """
        self._svg = svg_data
        if trusted:
            self._svg_root = ET.fromstring(svg_data)  # noqa: S314 — trusted
        else:
            self._svg_root = safe_fromstring(svg_data)

    def rasterize(self) -> None:
        """Public entry point for rasterisation.

        Useful for offloading to a thread via ``asyncio.to_thread``.
        No-op if no SVG is set.
        """
        self._rasterize()

    def clear(self) -> None:
        """Remove the background SVG and all derived artefacts."""
        self._svg = None
        self._svg_root = None
        self._tiles = None
        self._key_image = None

    def invalidate(self) -> None:
        """Re-rasterize the current SVG (e.g. after stylesheet changes).

        No-op if no SVG is set.
        """
        if self._svg is not None:
            self._rasterize()

    # ------------------------------------------------------------------
    # Internal rasterisation
    # ------------------------------------------------------------------

    def _rasterize(self) -> None:
        """Rasterize the SVG according to the layer's *kind*.

        For ``"touchstrip"``, produces a full-width image and slices it
        into per-panel tiles.  For ``"key"``, produces an encoded key
        image ready to push to the device.
        """
        if self._svg is None:
            self._tiles = None
            self._key_image = None
            return

        if self._kind == "touchstrip":
            self._rasterize_touchstrip()
        else:
            self._rasterize_key()

    def _rasterize_touchstrip(self) -> None:
        """Rasterize and slice a touchstrip background SVG using Pillow."""
        from .svg_rasterize import _svg_to_png

        assert self._svg is not None  # noqa: S101 — invariant

        total_width = self._panel_width * self._panel_count
        total_height = self._panel_height

        png_data = _svg_to_png(self._svg, total_width, total_height)

        full_img = Image.open(io.BytesIO(png_data)).convert("RGB")

        tiles: list[bytes] = []
        for i in range(self._panel_count):
            x0 = i * self._panel_width
            tile = full_img.crop((x0, 0, x0 + self._panel_width, total_height))
            buf = io.BytesIO()
            tile.save(buf, format="PNG")
            tiles.append(buf.getvalue())

        self._tiles = tiles
        logger.debug(
            "Background SVG rasterized: %dx%d -> %d tiles of %dx%d",
            total_width,
            total_height,
            self._panel_count,
            self._panel_width,
            self._panel_height,
        )

    def _rasterize_key(self) -> None:
        """Rasterize a key background SVG to encoded device bytes."""
        from .svg_rasterize import _rasterize_svg

        assert self._svg is not None  # noqa: S101 — invariant

        key_w, key_h = self._key_size
        fmt = "jpeg" if self._key_image_format.upper() == "JPEG" else "bmp"
        self._key_image = _rasterize_svg(
            self._svg, key_w, key_h, output_format=fmt
        )
        logger.debug("Key background SVG rasterized: %dx%d", key_w, key_h)
