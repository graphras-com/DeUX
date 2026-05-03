"""Tests for CardController and KeyController base classes."""

from __future__ import annotations

from unittest.mock import MagicMock

from deckui.dui.card import DuiCard
from deckui.dui.key import DuiKey
from deckui.dui.schema import (
    PackageSpec,
    PackageType,
    TextBinding,
)
from deckui.ui.controller import CardController, KeyController

_CARD_SVG = (
    '<svg id="C" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<text id="title" x="4" y="40">x</text>'
    "</svg>"
)
_KEY_SVG = (
    '<svg id="K" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<text id="label" x="60" y="60">x</text>'
    "</svg>"
)


def _card_spec() -> PackageSpec:
    return PackageSpec(
        name="C",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_CARD_SVG,
        bindings={"title": TextBinding(node="title", default="")},
    )


def _key_spec() -> PackageSpec:
    return PackageSpec(
        name="K",
        type=PackageType.KEY,
        version=1,
        svg_source=_KEY_SVG,
        bindings={"label": TextBinding(node="label", default="")},
    )


class TestCardController:
    async def test_default_on_attach_is_noop(self):
        controller = CardController()
        controller.card = DuiCard(_card_spec())
        # Default on_attach should not raise.
        await controller.on_attach(MagicMock())

    async def test_default_on_detach_is_noop(self):
        controller = CardController()
        controller.card = DuiCard(_card_spec())
        await controller.on_detach()

    async def test_subclass_can_override_lifecycle(self):
        attached: list[object] = []
        detached: list[bool] = []

        class _Mine(CardController):
            def __init__(self) -> None:
                self.card = DuiCard(_card_spec())

            async def on_attach(self, deck: object) -> None:
                attached.append(deck)

            async def on_detach(self) -> None:
                detached.append(True)

        controller = _Mine()
        deck = MagicMock()

        await controller.on_attach(deck)
        await controller.on_detach()

        assert attached == [deck]
        assert detached == [True]

    def test_card_attribute_holds_subclass_card(self):
        class _Mine(CardController):
            def __init__(self) -> None:
                self.card = DuiCard(_card_spec())

        controller = _Mine()
        assert isinstance(controller.card, DuiCard)


class TestKeyController:
    async def test_default_on_attach_is_noop(self):
        controller = KeyController()
        controller.key = DuiKey(_key_spec())
        await controller.on_attach(MagicMock())

    async def test_default_on_detach_is_noop(self):
        controller = KeyController()
        controller.key = DuiKey(_key_spec())
        await controller.on_detach()

    async def test_subclass_can_override_lifecycle(self):
        attached: list[object] = []
        detached: list[bool] = []

        class _Mine(KeyController):
            def __init__(self) -> None:
                self.key = DuiKey(_key_spec())

            async def on_attach(self, deck: object) -> None:
                attached.append(deck)

            async def on_detach(self) -> None:
                detached.append(True)

        controller = _Mine()
        deck = MagicMock()

        await controller.on_attach(deck)
        await controller.on_detach()

        assert attached == [deck]
        assert detached == [True]

    def test_key_attribute_holds_subclass_key(self):
        class _Mine(KeyController):
            def __init__(self) -> None:
                self.key = DuiKey(_key_spec())

        controller = _Mine()
        assert isinstance(controller.key, DuiKey)


class TestExports:
    """Both classes should be importable from deckui top-level."""

    def test_card_controller_importable_from_deckui(self):
        from deckui import CardController as TopLevel
        from deckui.ui.controller import CardController as Internal

        assert TopLevel is Internal

    def test_key_controller_importable_from_deckui(self):
        from deckui import KeyController as TopLevel
        from deckui.ui.controller import KeyController as Internal

        assert TopLevel is Internal
