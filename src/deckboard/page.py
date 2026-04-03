"""Screen and Page classes for deckboard navigable layouts."""

from __future__ import annotations

import logging

from .button import Button
from .dial import Dial
from .touchscreen import TouchScreen, Widget

logger = logging.getLogger(__name__)

# Stream Deck+ constants
_KEY_COUNT = 8
_DIAL_COUNT = 4
class Screen:
    """A named layout containing keys, encoders, and touch-strip cards.

    Screens allow you to define multiple layouts and switch between them.
    When a screen is activated, all key images, touch-strip cards, and
    event handlers swap atomically.

    Usage::

        main = deck.screen("main")
        main.key(0).set_icon("mdi:home")

        @main.key(0).on_press
        async def handle():
            await deck.set_screen("settings")
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._buttons: dict[int, Button] = {}
        self._dials: dict[int, Dial] = {}
        self._touchscreen = TouchScreen()

    @property
    def name(self) -> str:
        return self._name

    def key(self, index: int) -> Button:
        """Get or create a key slot by index (0-7 for Stream Deck+).

        Args:
            index: Key index.

        Returns:
            The Button instance for this key on this page.
        """
        if not 0 <= index < _KEY_COUNT:
            raise IndexError(f"Button index must be 0-{_KEY_COUNT - 1}, got {index}")

        if index not in self._buttons:
            self._buttons[index] = Button(index)
        return self._buttons[index]

    def button(self, index: int) -> Button:
        """Compatibility alias for :meth:`key`."""
        return self.key(index)

    def encoder(self, index: int) -> Dial:
        """Get or create an encoder slot by index (0-3 for Stream Deck+).

        Args:
            index: Dial index.

        Returns:
            The Dial instance for this dial on this page.
        """
        if not 0 <= index < _DIAL_COUNT:
            raise IndexError(f"Dial index must be 0-{_DIAL_COUNT - 1}, got {index}")

        if index not in self._dials:
            self._dials[index] = Dial(index)
        return self._dials[index]

    def dial(self, index: int) -> Dial:
        """Compatibility alias for :meth:`encoder`."""
        return self.encoder(index)

    def card(self, index: int) -> Widget:
        """Get a touch-strip card zone by index (0-3)."""
        return self._touchscreen.card(index)

    def widget(self, index: int) -> Widget:
        """Compatibility alias for :meth:`card`."""
        return self.card(index)

    def set_card(self, index: int, card: Widget) -> None:
        """Replace the card at *index* with a custom card."""
        self._touchscreen.set_card(index, card)

    def set_widget(self, index: int, widget: Widget) -> None:
        """Compatibility alias for :meth:`set_card`."""
        self.set_card(index, widget)

    @property
    def buttons(self) -> dict[int, Button]:
        return self._buttons

    @property
    def keys(self) -> dict[int, Button]:
        return self._buttons

    @property
    def dials(self) -> dict[int, Dial]:
        return self._dials

    @property
    def encoders(self) -> dict[int, Dial]:
        return self._dials

    @property
    def touchscreen(self) -> TouchScreen:
        return self._touchscreen

    @property
    def touch_strip(self) -> TouchScreen:
        return self._touchscreen

    @property
    def widgets(self) -> list[Widget]:
        return self._touchscreen.widgets

    @property
    def cards(self) -> list[Widget]:
        return self._touchscreen.cards


Page = Screen
