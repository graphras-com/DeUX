"""Screen layout class for deckboard navigation."""

from __future__ import annotations

import logging

from .cards.base import Card
from .controls.encoder_slot import EncoderSlot
from .controls.key_slot import KeySlot
from .touch_strip import TouchStrip

logger = logging.getLogger(__name__)

# Stream Deck+ constants
_KEY_COUNT = 8
_ENCODER_COUNT = 4


class Screen:
    """A named layout containing keys, encoders, and touch-strip cards.

    Screens allow you to define multiple layouts and switch between them.
    When a screen is activated, all key images, touch-strip cards, and
    event handlers swap atomically.

    Usage::

        main = deck.screen("main")

        @main.key(0).on_press
        async def handle():
            await deck.set_screen("settings")
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._keys: dict[int, KeySlot] = {}
        self._encoders: dict[int, EncoderSlot] = {}
        self._touch_strip = TouchStrip()

    @property
    def name(self) -> str:
        return self._name

    def key(self, index: int) -> KeySlot:
        """Get or create a key slot by index (0-7 for Stream Deck+).

        Args:
            index: Key index.

        Returns:
            The KeySlot instance for this key on this screen.
        """
        if not 0 <= index < _KEY_COUNT:
            raise IndexError(f"Key index must be 0-{_KEY_COUNT - 1}, got {index}")

        if index not in self._keys:
            self._keys[index] = KeySlot(index)
        return self._keys[index]

    def set_key(self, index: int, key: KeySlot) -> None:
        """Replace the key slot at *index* with a custom key.

        This is used to install a :class:`~deckboard.dsui.key.DsuiKey`
        (or any ``KeySlot`` subclass) at a specific position.

        Args:
            index: Key index (0-7).
            key: The key slot to install.
        """
        if not 0 <= index < _KEY_COUNT:
            raise IndexError(f"Key index must be 0-{_KEY_COUNT - 1}, got {index}")
        if not isinstance(key, KeySlot):
            raise TypeError(f"Expected KeySlot, got {type(key).__name__}")
        key._index = index
        self._keys[index] = key

    def encoder(self, index: int) -> EncoderSlot:
        """Get or create an encoder slot by index (0-3 for Stream Deck+).

        Args:
            index: Encoder index.

        Returns:
            The EncoderSlot instance for this encoder on this screen.
        """
        if not 0 <= index < _ENCODER_COUNT:
            raise IndexError(
                f"Encoder index must be 0-{_ENCODER_COUNT - 1}, got {index}"
            )

        if index not in self._encoders:
            self._encoders[index] = EncoderSlot(index)
        return self._encoders[index]

    def card(self, index: int) -> Card:
        """Get a touch-strip card zone by index (0-3)."""
        return self._touch_strip.card(index)

    def set_card(self, index: int, card: Card) -> None:
        """Replace the card at *index* with a custom card."""
        self._touch_strip.set_card(index, card)

    @property
    def keys(self) -> dict[int, KeySlot]:
        return self._keys

    @property
    def encoders(self) -> dict[int, EncoderSlot]:
        return self._encoders

    @property
    def touch_strip(self) -> TouchStrip:
        return self._touch_strip

    @property
    def touchstrip_background(self) -> str:
        """The fill colour for the touchscreen canvas (margins and gaps)."""
        return self._touch_strip.background_color

    @touchstrip_background.setter
    def touchstrip_background(self, value: str) -> None:
        self._touch_strip.background_color = value

    @property
    def cards(self) -> list[Card]:
        return self._touch_strip.cards
