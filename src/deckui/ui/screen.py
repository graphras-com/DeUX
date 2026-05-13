"""Screen layout class for deckui navigation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .controls.encoder_slot import EncoderSlot
from .controls.key_slot import KeySlot
from .info_screen import InfoScreen
from .touch_strip import TouchStrip

if TYPE_CHECKING:
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
    :class:`~deckui.runtime.deck.DeckError`.

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

    @property
    def name(self) -> str:
        """The screen name."""
        return self._name

    @property
    def capabilities(self) -> DeviceCapabilities:
        """The device capabilities this screen is configured for."""
        return self._caps

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

        The same ``KeySlot`` (or :class:`~deckui.dui.DuiKey`) instance may
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
    def keys(self) -> dict[int, KeySlot]:
        """Mapping of key index to :class:`KeySlot` for all configured keys."""
        return self._keys

    @property
    def encoders(self) -> dict[int, EncoderSlot]:
        """Mapping of encoder index to :class:`EncoderSlot` for all configured encoders."""
        return self._encoders

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
        if self._touch_strip is not None:
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
        """All touch-strip cards, or an empty list if the device has no touchscreen."""
        if self._touch_strip is None:
            return []
        return self._touch_strip.cards
