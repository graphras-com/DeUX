"""Tests for deckboard.dsui.card — DsuiCard class."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from deckboard.dsui.card import DsuiCard
from deckboard.dsui.schema import (
    EventMapping,
    PackageSpec,
    PackageType,
    RangeBinding,
    Region,
    TextBinding,
    ToggleBinding,
)
from deckboard.runtime.events import EventType, TouchEvent
from deckboard.ui.cards.base import Card


# -- Helpers ---------------------------------------------------------------

_CARD_SVG = (
    '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<rect id="bg" width="197" height="98" fill="#1c1c1c"/>'
    '<text id="title" x="4" y="40" font-size="14" fill="#ffffff">Default</text>'
    '<rect id="bar" x="4" y="86" width="189" height="4" fill="#00ff00"/>'
    "</svg>"
)


def _make_card_spec(
    bindings: dict | None = None,
    events: tuple | None = None,
    regions: tuple | None = None,
) -> PackageSpec:
    return PackageSpec(
        name="TestCard",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_CARD_SVG,
        bindings=bindings or {},
        events=events or (),
        regions=regions or (),
    )


class TestDsuiCardIsCard:
    def test_is_card_subclass(self, card_package_spec):
        card = DsuiCard(0, card_package_spec)
        assert isinstance(card, Card)

    def test_has_index(self, card_package_spec):
        card = DsuiCard(2, card_package_spec)
        assert card.index == 2

    def test_has_spec(self, card_package_spec):
        card = DsuiCard(0, card_package_spec)
        assert card.spec is card_package_spec


class TestDsuiCardDataBinding:
    def test_set_marks_dirty(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="")}
        )
        card = DsuiCard(0, spec)
        card.mark_clean()
        assert card.is_dirty is False

        card.set("title", "New Title")
        assert card.is_dirty is True

    def test_set_same_value_not_dirty(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Same")}
        )
        card = DsuiCard(0, spec)
        card.mark_clean()
        card.set("title", "Same")
        assert card.is_dirty is False

    def test_set_returns_self(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="")}
        )
        card = DsuiCard(0, spec)
        result = card.set("title", "Test")
        assert result is card

    def test_set_many(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="")}
        )
        card = DsuiCard(0, spec)
        card.mark_clean()
        result = card.set_many(title="New")
        assert result is card
        assert card.is_dirty is True

    def test_set_many_no_change(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Same")}
        )
        card = DsuiCard(0, spec)
        card.mark_clean()
        card.set_many(title="Same")
        assert card.is_dirty is False

    def test_get_value(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Init")}
        )
        card = DsuiCard(0, spec)
        assert card.get("title") == "Init"
        card.set("title", "Changed")
        assert card.get("title") == "Changed"

    def test_set_unknown_raises(self):
        spec = _make_card_spec()
        card = DsuiCard(0, spec)
        with pytest.raises(KeyError):
            card.set("nonexistent", "val")

    def test_get_unknown_raises(self):
        spec = _make_card_spec()
        card = DsuiCard(0, spec)
        with pytest.raises(KeyError):
            card.get("nonexistent")

    def test_set_range_marks_dirty(self):
        spec = _make_card_spec(
            bindings={"level": RangeBinding(node="bar", default=0.0)}
        )
        card = DsuiCard(0, spec)
        card.mark_clean()
        card.set("level", 0.5)
        assert card.is_dirty is True

    def test_set_range_same_value_not_dirty(self):
        spec = _make_card_spec(
            bindings={"level": RangeBinding(node="bar", default=0.5)}
        )
        card = DsuiCard(0, spec)
        card.mark_clean()
        card.set("level", 0.5)
        assert card.is_dirty is False

    def test_get_range_value(self):
        spec = _make_card_spec(
            bindings={"level": RangeBinding(node="bar", default=0.3)}
        )
        card = DsuiCard(0, spec)
        assert card.get("level") == 0.3
        card.set("level", 0.8)
        assert card.get("level") == 0.8


class TestDsuiCardToggleBinding:
    _TOGGLE_CARD_SVG = (
        '<svg id="TC" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
        '<rect id="bg" width="197" height="98" fill="#1c1c1c"/>'
        '<path id="icon_on" d="M10 10 L50 10 L50 40 L10 40 Z" fill="#00ff00"/>'
        '<path id="icon_off" d="M60 10 L90 10 L90 40 L60 40 Z" fill="#ff0000"/>'
        "</svg>"
    )

    def _make_toggle_spec(self):
        return PackageSpec(
            name="ToggleCard",
            type=PackageType.TOUCH_STRIP_CARD,
            version=1,
            svg_source=self._TOGGLE_CARD_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=False
                ),
            },
        )

    def test_set_toggle_marks_dirty(self):
        spec = self._make_toggle_spec()
        card = DsuiCard(0, spec)
        card.mark_clean()
        card.set("lights", True)
        assert card.is_dirty is True

    def test_set_toggle_same_value_not_dirty(self):
        spec = self._make_toggle_spec()
        card = DsuiCard(0, spec)
        card.mark_clean()
        card.set("lights", False)  # same as default
        assert card.is_dirty is False

    def test_get_toggle_value(self):
        spec = self._make_toggle_spec()
        card = DsuiCard(0, spec)
        assert card.get("lights") is False
        card.set("lights", True)
        assert card.get("lights") is True

    def test_toggle_renders_differently(self):
        spec = self._make_toggle_spec()
        card = DsuiCard(0, spec)
        img_off = card.render()

        card.set("lights", True)
        img_on = card.render()

        assert img_off.tobytes() != img_on.tobytes()


class TestDsuiCardRender:
    def test_render_returns_image(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Hello")}
        )
        card = DsuiCard(0, spec)
        img = card.render()
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.size == (197, 98)

    def test_render_with_changed_binding(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Hello")}
        )
        card = DsuiCard(0, spec)
        img1 = card.render()
        card.set("title", "World")
        img2 = card.render()
        assert img1.tobytes() != img2.tobytes()


class TestDsuiCardPrepareAssets:
    async def test_prepare_assets_is_noop(self):
        spec = _make_card_spec()
        card = DsuiCard(0, spec)
        await card.prepare_assets()
        # Should not raise or call anything


class TestDsuiCardEvents:
    def test_on_decorator(self):
        spec = _make_card_spec(
            events=(EventMapping(name="play", source="encoder_press"),),
        )
        card = DsuiCard(0, spec)

        @card.on("play")
        async def handler():
            pass

        assert handler is not None

    def test_bind_event(self):
        spec = _make_card_spec(
            events=(EventMapping(name="play", source="encoder_press"),),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("play", handler)
        # Event should be routed
        card.handle_encoder_press()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0][0] is handler

    def test_encoder_turn_routes_to_handler(self):
        spec = _make_card_spec(
            events=(
                EventMapping(name="next", source="encoder_turn", direction="right"),
            ),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("next", handler)

        card.handle_encoder_turn(1)
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1

    def test_encoder_turn_no_match_no_callback(self):
        spec = _make_card_spec(
            events=(
                EventMapping(name="next", source="encoder_turn", direction="right"),
            ),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("next", handler)

        card.handle_encoder_turn(-1)  # left, not right
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_encoder_press_routes(self):
        spec = _make_card_spec(
            events=(EventMapping(name="press", source="encoder_press"),),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("press", handler)

        card.handle_encoder_press()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1

    def test_encoder_release_routes(self):
        spec = _make_card_spec(
            events=(EventMapping(name="release", source="encoder_release"),),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("release", handler)

        card.handle_encoder_press()  # set state
        card.handle_encoder_release()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1

    async def test_dispatch_touch_via_event_map(self):
        spec = _make_card_spec(
            events=(EventMapping(name="card_tap", source="tap"),),
            regions=(
                Region(name="card", x=0, y=0, width=197, height=98, events=("tap",)),
            ),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("card_tap", handler)

        event = TouchEvent(event_type=EventType.TOUCH_SHORT, x=50, y=50)
        await card.dispatch_touch(event)
        handler.assert_awaited_once()

    async def test_dispatch_touch_falls_back_to_base(self):
        spec = _make_card_spec()  # no events
        card = DsuiCard(0, spec)
        base_handler = AsyncMock()
        card.on_tap(base_handler)

        event = TouchEvent(event_type=EventType.TOUCH_SHORT, x=50, y=50)
        await card.dispatch_touch(event)
        base_handler.assert_awaited_once()

    async def test_dispatch_encoder_turn_via_base_card(self):
        """Verify the full dispatch chain through Card.dispatch_encoder_turn."""
        spec = _make_card_spec(
            events=(
                EventMapping(name="next", source="encoder_turn", direction="right"),
            ),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("next", handler)

        await card.dispatch_encoder_turn(1)
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1
        await callbacks[0][0](*callbacks[0][1])
        handler.assert_awaited_once()

    async def test_dispatch_encoder_press_via_base_card(self):
        spec = _make_card_spec(
            events=(EventMapping(name="press", source="encoder_press"),),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("press", handler)

        await card.dispatch_encoder_press()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1

    async def test_dispatch_encoder_release_via_base_card(self):
        spec = _make_card_spec(
            events=(EventMapping(name="release", source="encoder_release"),),
        )
        card = DsuiCard(0, spec)
        handler = AsyncMock()
        card.bind_event("release", handler)

        # Must press first to set state
        await card.dispatch_encoder_press()
        card.drain_pending_callbacks()  # clear press callbacks
        await card.dispatch_encoder_release()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1


class TestDsuiCardDirtyTracking:
    def test_starts_dirty(self):
        spec = _make_card_spec()
        card = DsuiCard(0, spec)
        assert card.is_dirty is True

    def test_mark_clean_and_dirty(self):
        spec = _make_card_spec()
        card = DsuiCard(0, spec)
        card.mark_clean()
        assert card.is_dirty is False
        card.mark_dirty()
        assert card.is_dirty is True

    def test_set_rendered_clears_dirty(self):
        spec = _make_card_spec()
        card = DsuiCard(0, spec)
        img = Image.new("RGB", (197, 98))
        card.set_rendered(img)
        assert card.is_dirty is False
        assert card.rendered is img
