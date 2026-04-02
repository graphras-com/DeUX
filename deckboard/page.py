"""Page class: a named layout of buttons, dials, and widgets that can be swapped."""

from __future__ import annotations

import logging

from .button import Button
from .dial import Dial
from .touchscreen import TouchScreen, Widget

logger = logging.getLogger(__name__)

# Stream Deck+ constants
_KEY_COUNT = 8
_DIAL_COUNT = 4
_WIDGET_COUNT = 4


class Page:
    """A named layout containing buttons, dials, and touchscreen widgets.

    Pages allow you to define multiple layouts and switch between them.
    When a page is activated, all key images, touchscreen widgets, and
    event handlers swap atomically.

    Usage::

        main = deck.page("main")
        main.button(0).set_icon("mdi:home")

        @main.button(0).on_press
        async def handle():
            await deck.set_page("settings")
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._buttons: dict[int, Button] = {}
        self._dials: dict[int, Dial] = {}
        self._touchscreen = TouchScreen()

    @property
    def name(self) -> str:
        return self._name

    def button(self, index: int) -> Button:
        """Get or create a button by index (0-7 for Stream Deck+).

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

    def dial(self, index: int) -> Dial:
        """Get or create a dial by index (0-3 for Stream Deck+).

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

    def widget(self, index: int) -> Widget:
        """Get a touchscreen widget zone by index (0-3).

        Args:
            index: Widget zone index.

        Returns:
            The Widget instance for this zone on this page.
        """
        return self._touchscreen.widget(index)

    @property
    def buttons(self) -> dict[int, Button]:
        return self._buttons

    @property
    def dials(self) -> dict[int, Dial]:
        return self._dials

    @property
    def touchscreen(self) -> TouchScreen:
        return self._touchscreen

    @property
    def widgets(self) -> list[Widget]:
        return self._touchscreen.widgets
