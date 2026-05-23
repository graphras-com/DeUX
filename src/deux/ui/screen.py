"""Screen layout class for deux navigation."""

from __future__ import annotations

import io
import logging
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from ..render.background_layer import BackgroundLayer
from .controls.encoder_slot import EncoderSlot
from .controls.key_slot import KeySlot
from .info_screen import InfoScreen
from .touch_strip import TouchStrip

if TYPE_CHECKING:
    from ..render.theme import Theme
    from ..runtime.capabilities import DeviceCapabilities
    from .cards.base import Card

logger = logging.getLogger(__name__)


class Screen:
    """A named layout containing keys, encoders, and touch-strip cards.

    Screens allow you to define multiple layouts and switch between them.
    When a screen is activated, all key images, touch-strip cards, and
    event handlers swap atomically.

    The number of available keys, encoders, and card zones is determined
    by the device capabilities.  For devices without encoders or a
    touchscreen, those features are unavailable and accessing them raises
    :class:`~deux.runtime.deck.DeckError`.

    Examples
    --------
    ::

        main = deck.screen("main")

        @main.key(0).on_press
        async def handle():
            await deck.set_screen("settings")
    """

    def __init__(self, name: str, caps: DeviceCapabilities) -> None:
        self._name = name
        self._caps = caps
        self._keys: dict[int, KeySlot] = {}
        self._encoders: dict[int, EncoderSlot] = {}
        self._theme: Theme | None = None
        self._key_bg_layer = BackgroundLayer(
            "key",
            key_size=self._caps.key_size,
            key_image_format=self._caps.key_image_format,
        )
        self._key_bg_dirty: bool = False

        if self._caps.has_touchscreen and self._caps.dial_count > 0:
            from ..render.metrics import RenderMetrics

            metrics = RenderMetrics(self._caps)
            self._touch_strip: TouchStrip | None = TouchStrip(
                panel_count=metrics.panel_count,
                panel_width=metrics.panel_width,
                panel_height=metrics.panel_height,
            )
        else:
            self._touch_strip = None

        if self._caps.has_info_screen:
            self._info_screen: InfoScreen | None = InfoScreen(
                width=self._caps.screen_width,
                height=self._caps.screen_height,
                image_format=self._caps.screen_image_format,
            )
        else:
            self._info_screen = None

        self._apply_default_backgrounds()

    @property
    def name(self) -> str:
        """The screen name."""
        return self._name

    def _apply_default_backgrounds(self) -> None:
        """Load and apply bundled default background SVGs for this device.

        Looks up the device's VID:PID in the bundled manifest and sets
        the touchscreen background SVG if one is available and no
        background has been explicitly configured.  Failures are logged
        but never raised — defaults are best-effort.
        """
        import xml.etree.ElementTree as ET

        from ..render.defaults import get_default_backgrounds
        from ..render.svg_rasterize import RasterizeError

        try:
            backgrounds = get_default_backgrounds(
                self._caps.vendor_id, self._caps.product_id
            )
        except Exception:
            logger.warning("Could not load default backgrounds", exc_info=True)
            return

        if "touchscreen" in backgrounds and self._touch_strip is not None:
            try:
                svg_data = backgrounds["touchscreen"]
                self._touch_strip.bg_layer.set_svg(svg_data, trusted=True)
            except (ET.ParseError, RasterizeError, OSError):
                logger.warning(
                    "Failed to apply default touchscreen background", exc_info=True
                )

        if "key" in backgrounds:
            try:
                svg_data = backgrounds["key"]
                self._key_bg_layer.set_svg(svg_data, trusted=True)
            except (ET.ParseError, RasterizeError, OSError):
                logger.warning(
                    "Failed to apply default key background", exc_info=True
                )

    def _rasterize_key_background(self) -> None:
        """Re-rasterize the key background via the BackgroundLayer.

        If no key background SVG is set, this is a no-op.
        """
        self._key_bg_layer.invalidate()

    @property
    def key_bg_image(self) -> bytes | None:
        """Pre-rendered default key background image, or ``None``.

        Returns
        -------
        bytes or None
            Encoded image bytes ready to push to the device, or ``None``
            if no default key background is configured.
        """
        return self._key_bg_layer.key_image

    @property
    def key_bg_dirty(self) -> bool:
        """Whether the key background needs re-rendering on all blank keys."""
        return self._key_bg_dirty

    def clear_key_bg_dirty(self) -> None:
        """Reset the key-background dirty flag after a full key render."""
        self._key_bg_dirty = False

    @property
    def capabilities(self) -> DeviceCapabilities:
        """The device capabilities this screen is configured for."""
        return self._caps

    @property
    def theme(self) -> Theme | None:
        """Per-screen theme override, or ``None`` to inherit.

        When set, this theme takes precedence over both the deck-level
        and system-wide theme for this screen.  Set to ``None`` to fall
        back to the deck or system theme.
        """
        return self._theme

    @theme.setter
    def theme(self, value: Theme | None) -> None:
        self._theme = value

    def key(self, index: int) -> KeySlot:
        """Get or create a key slot by index.

        Parameters
        ----------
        index
            Key index (0 to key_count-1).

        Returns
        -------
        KeySlot
            The KeySlot instance for this key on this screen.
        """
        key_count = self._caps.key_count
        if not 0 <= index < key_count:
            raise IndexError(
                f"Key index must be 0-{key_count - 1}, got {index}"
            )

        if index not in self._keys:
            self._keys[index] = KeySlot()
        return self._keys[index]

    def set_key(self, index: int, key: KeySlot) -> None:
        """Replace the key slot at *index* with a custom key.

        The same ``KeySlot`` (or :class:`~deux.dui.DuiKey`) instance may
        be installed on multiple screens at different slot indices — the
        screen's slot map is the single source of truth for routing, so
        no state is mutated on *key* itself.

        Parameters
        ----------
        index
            Key index.
        key
            The key slot to install.
        """
        key_count = self._caps.key_count
        if not 0 <= index < key_count:
            raise IndexError(
                f"Key index must be 0-{key_count - 1}, got {index}"
            )
        if not isinstance(key, KeySlot):
            raise TypeError(f"Expected KeySlot, got {type(key).__name__}")
        self._keys[index] = key

    def encoder(self, index: int) -> EncoderSlot:
        """Get or create an encoder slot by index.

        Parameters
        ----------
        index
            Encoder index (0 to dial_count-1).

        Returns
        -------
        EncoderSlot
            The EncoderSlot instance for this encoder on this screen.

        Raises
        ------
        IndexError
            If index is out of range or device has no encoders.
        """
        dial_count = self._caps.dial_count
        if dial_count == 0:
            raise IndexError("This device has no encoders")
        if not 0 <= index < dial_count:
            raise IndexError(
                f"Encoder index must be 0-{dial_count - 1}, got {index}"
            )

        if index not in self._encoders:
            self._encoders[index] = EncoderSlot()
        return self._encoders[index]

    def card(self, index: int) -> Card:
        """Get a touch-strip card zone by index."""
        if self._touch_strip is None:
            raise IndexError("This device has no touchscreen")
        return self._touch_strip.card(index)

    def set_card(self, index: int, card: Card) -> None:
        """Replace the card at *index* with a custom card."""
        if self._touch_strip is None:
            raise IndexError("This device has no touchscreen")
        self._touch_strip.set_card(index, card)

    @property
    def keys(self) -> Mapping[int, KeySlot]:
        """Mapping of key index to :class:`KeySlot` for all configured keys.

        Returns a read-only view; external code cannot mutate internal state.
        """
        return MappingProxyType(self._keys)

    @property
    def encoders(self) -> Mapping[int, EncoderSlot]:
        """Mapping of encoder index to :class:`EncoderSlot` for all configured encoders.

        Returns a read-only view; external code cannot mutate internal state.
        """
        return MappingProxyType(self._encoders)

    @property
    def touch_strip(self) -> TouchStrip | None:
        """The touch strip, or ``None`` if the device has no touchscreen."""
        return self._touch_strip

    @property
    def info_screen(self) -> InfoScreen | None:
        """The info screen, or ``None`` if the device has no info display."""
        return self._info_screen

    @property
    def touchstrip_background(self) -> str:
        """The fill colour for the touchscreen canvas behind cards."""
        if self._touch_strip is None:
            return "black"
        return self._touch_strip.background_color

    @touchstrip_background.setter
    def touchstrip_background(self, value: str) -> None:
        """Set the fill colour for the touchscreen canvas behind cards.

        Parameters
        ----------
        value : str
            CSS colour string for the background.

        Raises
        ------
        IndexError
            If the device has no touchscreen.
        """
        if self._touch_strip is None:
            raise IndexError("This device has no touchscreen")
        self._touch_strip.background_color = value

    def set_touchstrip_background_svg(self, svg_data: bytes) -> None:
        """Set a background SVG for the touchstrip.

        The SVG is rasterized once, sliced into per-panel tiles, and
        cached.  Cards with transparent areas will show the background
        through.  When no background SVG is set, the solid
        :attr:`touchstrip_background` colour is used instead.

        Parameters
        ----------
        svg_data
            Raw SVG content as UTF-8 bytes.

        Raises
        ------
        IndexError
            If the device has no touchscreen.
        """
        if self._touch_strip is None:
            raise IndexError("This device has no touchscreen")
        self._touch_strip.set_background_svg(svg_data)

    def set_touchstrip_background_svg_from_file(self, path: str | Path) -> None:
        """Load a touchstrip background SVG from a file path.

        Convenience wrapper around :meth:`set_touchstrip_background_svg`.

        Parameters
        ----------
        path
            Path to an SVG file.

        Raises
        ------
        IndexError
            If the device has no touchscreen.
        FileNotFoundError
            If *path* does not exist.
        """
        if self._touch_strip is None:
            raise IndexError("This device has no touchscreen")
        self._touch_strip.set_background_svg_from_file(path)

    def clear_touchstrip_background_svg(self) -> None:
        """Remove the touchstrip background SVG.

        Reverts to the solid :attr:`touchstrip_background` colour.

        Raises
        ------
        IndexError
            If the device has no touchscreen.
        """
        if self._touch_strip is None:
            raise IndexError("This device has no touchscreen")
        self._touch_strip.clear_background_svg()

    @property
    def cards(self) -> list[Card]:
        """All touch-strip cards, or an empty list if the device has no touchscreen.

        Returns a shallow copy; external code cannot mutate internal state.
        """
        if self._touch_strip is None:
            return []
        return list(self._touch_strip.cards)

    def mark_all_dirty(self) -> None:
        """Flag every control on this screen for re-rendering.

        Marks all configured keys, touch-strip cards, and the info
        screen (if present) as dirty so the next refresh cycle
        re-renders the entire screen.  If the touch strip has a
        background SVG it is re-rasterized so that stylesheet changes
        are reflected.  Useful when a global property such as the
        active stylesheet changes.
        """
        for key_slot in self._keys.values():
            key_slot.mark_dirty()
        if self._key_bg_layer.has_svg:
            self._key_bg_layer.invalidate()
            self._key_bg_dirty = True
        if self._touch_strip is not None:
            self._touch_strip.invalidate_background()
        for card in self.cards:
            card.mark_dirty()
        if self._info_screen is not None:
            self._info_screen.mark_dirty()

    def collect_all_icons(self) -> set[str]:
        """Collect all Iconify icon identifiers needed by this screen.

        Iterates all DuiKey and DuiCard instances on this screen and
        aggregates their :meth:`~deux.dui.svg_renderer.SvgRenderer.collect_icon_names`
        results.

        Returns
        -------
        set[str]
            A set of ``"prefix:icon"`` strings used across all
            keys and cards on this screen.
        """
        from ..dui.card import DuiCard
        from ..dui.key import DuiKey

        icons: set[str] = set()
        for key_slot in self._keys.values():
            if isinstance(key_slot, DuiKey):
                icons.update(key_slot.collect_icon_names())
        if self._touch_strip is not None:
            for card in self._touch_strip.cards:
                if isinstance(card, DuiCard):
                    icons.update(card.collect_icon_names())
        return icons

    def screenshot(self, directory: str | Path) -> list[Path]:
        """Save the current screen state as individual PNG files.

        Writes one file per key that has been rendered, one file per
        touch-strip card that has been rendered, and one file for the
        info screen (if it has content).  Blank or unrendered controls
        are skipped.

        PNG is used instead of JPEG to avoid additional compression
        artifacts on the already-small device images.

        Parameters
        ----------
        directory : str or Path
            Target directory for the screenshot files.  Created
            (including parents) if it does not already exist.

        Returns
        -------
        list[Path]
            Paths of all files written, in the order they were saved.

        Examples
        --------
        ::

            paths = screen.screenshot("/tmp/deck_screenshot")
            # [PosixPath('/tmp/deck_screenshot/key_0.png'),
            #  PosixPath('/tmp/deck_screenshot/card_1.png')]
        """
        from PIL import Image

        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        # Keys — decode device JPEG/BMP bytes back to PIL, re-encode as PNG.
        for index, key_slot in self._keys.items():
            if key_slot.image_bytes is None:
                continue
            img = Image.open(io.BytesIO(key_slot.image_bytes))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            path = out_dir / f"key_{index}.png"
            path.write_bytes(buf.getvalue())
            written.append(path)

        # Touch-strip cards
        if self._touch_strip is not None:
            for index, card in enumerate(self._touch_strip.cards):
                # Render on demand; fall back to the last cached image
                # when the card does not support on-demand rendering.
                card_img = card.render() or card.rendered
                if card_img is None:
                    continue
                buf = io.BytesIO()
                rgb = card_img.convert("RGB") if card_img.mode != "RGB" else card_img
                rgb.save(buf, format="PNG")
                path = out_dir / f"card_{index}.png"
                path.write_bytes(buf.getvalue())
                written.append(path)

        # Info screen
        if self._info_screen is not None and self._info_screen.image is not None:
            info_img: Image.Image = self._info_screen.image
            if info_img.mode != "RGB":
                info_img = info_img.convert("RGB")
            buf = io.BytesIO()
            info_img.save(buf, format="PNG")
            path = out_dir / "info_screen.png"
            path.write_bytes(buf.getvalue())
            written.append(path)

        return written
