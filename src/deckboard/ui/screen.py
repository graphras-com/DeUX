"""Screen layout class for deckboard navigation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cards.base import Card
from .cards.blank import BlankCard
from .controls.encoder_slot import EncoderSlot
from .controls.key_slot import KeySlot
from .info_screen import InfoScreen
from .touch_strip import TouchStrip

if TYPE_CHECKING:
    from ..runtime.capabilities import DeviceCapabilities

logger = logging.getLogger(__name__)


class Screen:
    """A named layout containing keys, encoders, and touch-strip cards.

    Screens allow you to define multiple layouts and switch between them.
    When a screen is activated, all key images, touch-strip cards, and
    event handlers swap atomically.

    The number of available keys, encoders, and card zones is determined
    by the device capabilities.  For devices without encoders or a
    touchscreen, those features are unavailable and accessing them raises
    :class:`~deckboard.runtime.deck.DeckError`.

    Usage::

        main = deck.screen("main")

        @main.key(0).on_press
        async def handle():
            await deck.set_screen("settings")
    """

    def __init__(self, name: str, caps: DeviceCapabilities | None = None) -> None:
        from ..runtime.capabilities import STREAM_DECK_PLUS

        self._name = name
        self._caps = caps or STREAM_DECK_PLUS
        self._keys: dict[int, KeySlot] = {}
        self._encoders: dict[int, EncoderSlot] = {}

        # Touch strip: only created if the device has encoders + touchscreen
        if self._caps.has_touchscreen and self._caps.dial_count > 0:
            from ..render.metrics import RenderMetrics

            metrics = RenderMetrics(self._caps)
            self._touch_strip: TouchStrip | None = TouchStrip(
                panel_count=metrics.panel_count,
            )
        else:
            self._touch_strip = None

        # Info screen: only for devices with a non-touch screen (Neo)
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
        return self._name

    @property
    def capabilities(self) -> DeviceCapabilities:
        """The device capabilities this screen is configured for."""
        return self._caps

    def key(self, index: int) -> KeySlot:
        """Get or create a key slot by index.

        Args:
            index: Key index (0 to key_count-1).

        Returns:
            The KeySlot instance for this key on this screen.
        """
        key_count = self._caps.key_count
        if not 0 <= index < key_count:
            raise IndexError(
                f"Key index must be 0-{key_count - 1}, got {index}"
            )

        if index not in self._keys:
            self._keys[index] = KeySlot(index)
        return self._keys[index]

    def set_key(self, index: int, key: KeySlot) -> None:
        """Replace the key slot at *index* with a custom key.

        Args:
            index: Key index.
            key: The key slot to install.
        """
        key_count = self._caps.key_count
        if not 0 <= index < key_count:
            raise IndexError(
                f"Key index must be 0-{key_count - 1}, got {index}"
            )
        if not isinstance(key, KeySlot):
            raise TypeError(f"Expected KeySlot, got {type(key).__name__}")
        key._index = index
        self._keys[index] = key

    def encoder(self, index: int) -> EncoderSlot:
        """Get or create an encoder slot by index.

        Args:
            index: Encoder index (0 to dial_count-1).

        Returns:
            The EncoderSlot instance for this encoder on this screen.

        Raises:
            IndexError: If index is out of range or device has no encoders.
        """
        dial_count = self._caps.dial_count
        if dial_count == 0:
            raise IndexError("This device has no encoders")
        if not 0 <= index < dial_count:
            raise IndexError(
                f"Encoder index must be 0-{dial_count - 1}, got {index}"
            )

        if index not in self._encoders:
            self._encoders[index] = EncoderSlot(index)
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
        return self._keys

    @property
    def encoders(self) -> dict[int, EncoderSlot]:
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
        """The fill colour for the touchscreen canvas (margins and gaps)."""
        if self._touch_strip is None:
            return "black"
        return self._touch_strip.background_color

    @touchstrip_background.setter
    def touchstrip_background(self, value: str) -> None:
        if self._touch_strip is not None:
            self._touch_strip.background_color = value

    @property
    def cards(self) -> list[Card]:
        if self._touch_strip is None:
            return []
        return self._touch_strip.cards
