"""Tests for deux.dui.card — DuiCard class."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from PIL import Image

from deux.dui.card import DuiCard
from deux.dui.schema import (
    EventMapping,
    PackageSpec,
    PackageType,
    RangeBinding,
    Region,
    TextBinding,
    ToggleBinding,
)
from deux.runtime.capabilities import STREAM_DECK_PLUS
from deux.runtime.events import EventType, TouchEvent
from deux.ui.cards.base import Card
from deux.ui.screen import Screen

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


class TestDuiCardIsCard:
    def test_is_card_subclass(self, card_package_spec):
        card = DuiCard(card_package_spec)
        assert isinstance(card, Card)

    def test_set_card_installs_at_slot(self, card_package_spec):
        """set_card stores the card in the strip's slot list.

        The card itself carries no slot identity -- the strip's slot
        list is the authoritative source of truth.
        """
        card = DuiCard(card_package_spec)
        screen = Screen("test", STREAM_DECK_PLUS)
        screen.set_card(2, card)
        assert screen.touch_strip is not None
        assert screen.touch_strip.cards[2] is card

    def test_has_spec(self, card_package_spec):
        card = DuiCard(card_package_spec)
        assert card.spec is card_package_spec


class TestDuiCardDataBinding:
    def test_set_marks_dirty(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="")}
        )
        card = DuiCard(spec)
        card.mark_clean()
        assert card.is_dirty is False

        card.set("title", "New Title")
        assert card.is_dirty is True

    def test_set_same_value_not_dirty(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Same")}
        )
        card = DuiCard(spec)
        card.mark_clean()
        card.set("title", "Same")
        assert card.is_dirty is False

    def test_set_returns_self(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="")}
        )
        card = DuiCard(spec)
        result = card.set("title", "Test")
        assert result is card

    def test_set_many(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="")}
        )
        card = DuiCard(spec)
        card.mark_clean()
        result = card.set_many(title="New")
        assert result is card
        assert card.is_dirty is True

    def test_set_many_no_change(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Same")}
        )
        card = DuiCard(spec)
        card.mark_clean()
        card.set_many(title="Same")
        assert card.is_dirty is False

    def test_get_value(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Init")}
        )
        card = DuiCard(spec)
        assert card.get("title") == "Init"
        card.set("title", "Changed")
        assert card.get("title") == "Changed"

    def test_set_unknown_raises(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        with pytest.raises(KeyError):
            card.set("nonexistent", "val")

    def test_get_unknown_raises(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        with pytest.raises(KeyError):
            card.get("nonexistent")

    def test_set_range_marks_dirty(self):
        spec = _make_card_spec(
            bindings={"level": RangeBinding(node="bar", default=0.0)}
        )
        card = DuiCard(spec)
        card.mark_clean()
        card.set("level", 0.5)
        assert card.is_dirty is True

    def test_set_range_same_value_not_dirty(self):
        spec = _make_card_spec(
            bindings={"level": RangeBinding(node="bar", default=0.5)}
        )
        card = DuiCard(spec)
        card.mark_clean()
        card.set("level", 0.5)
        assert card.is_dirty is False

    def test_get_range_value(self):
        spec = _make_card_spec(
            bindings={"level": RangeBinding(node="bar", default=0.3)}
        )
        card = DuiCard(spec)
        assert card.get("level") == 0.3
        card.set("level", 0.8)
        assert card.get("level") == 0.8


class TestDuiCardRangeHelpers:
    """Tests for set_range, adjust_range, and get_range helpers."""

    def _make_range_card(self, default: float = 0.0) -> DuiCard:
        spec = _make_card_spec(
            bindings={"level": RangeBinding(node="bar", default=default)}
        )
        return DuiCard(spec)


    def test_set_range_normalises(self):
        card = self._make_range_card()
        card.set_range("level", 50, min_val=0, max_val=100)
        assert card.get("level") == pytest.approx(0.5)

    def test_set_range_clamps_high(self):
        card = self._make_range_card()
        card.set_range("level", 200, min_val=0, max_val=100)
        assert card.get("level") == pytest.approx(1.0)

    def test_set_range_clamps_low(self):
        card = self._make_range_card()
        card.set_range("level", -10, min_val=0, max_val=100)
        assert card.get("level") == pytest.approx(0.0)

    def test_set_range_returns_self(self):
        card = self._make_range_card()
        result = card.set_range("level", 50, min_val=0, max_val=100)
        assert result is card

    def test_set_range_marks_dirty(self):
        card = self._make_range_card()
        card.mark_clean()
        card.set_range("level", 50, min_val=0, max_val=100)
        assert card.is_dirty is True

    def test_set_range_equal_min_max_raises(self):
        card = self._make_range_card()
        with pytest.raises(ValueError, match="must not be equal"):
            card.set_range("level", 5, min_val=5, max_val=5)

    def test_set_range_unknown_binding_raises(self):
        card = self._make_range_card()
        with pytest.raises(KeyError):
            card.set_range("nonexistent", 50, min_val=0, max_val=100)

    def test_set_range_custom_domain(self):
        card = self._make_range_card()
        card.set_range("level", 4000, min_val=2000, max_val=6000)
        assert card.get("level") == pytest.approx(0.5)


    def test_adjust_range_increment(self):
        card = self._make_range_card(default=0.5)
        new_val = card.adjust_range("level", 10, min_val=0, max_val=100)
        assert new_val == pytest.approx(60.0)
        assert card.get("level") == pytest.approx(0.6)

    def test_adjust_range_decrement(self):
        card = self._make_range_card(default=0.5)
        new_val = card.adjust_range("level", -20, min_val=0, max_val=100)
        assert new_val == pytest.approx(30.0)
        assert card.get("level") == pytest.approx(0.3)

    def test_adjust_range_clamps_at_max(self):
        card = self._make_range_card(default=0.9)
        new_val = card.adjust_range("level", 20, min_val=0, max_val=100)
        assert new_val == pytest.approx(100.0)
        assert card.get("level") == pytest.approx(1.0)

    def test_adjust_range_clamps_at_min(self):
        card = self._make_range_card(default=0.1)
        new_val = card.adjust_range("level", -20, min_val=0, max_val=100)
        assert new_val == pytest.approx(0.0)
        assert card.get("level") == pytest.approx(0.0)

    def test_adjust_range_marks_dirty(self):
        card = self._make_range_card(default=0.5)
        card.mark_clean()
        card.adjust_range("level", 5, min_val=0, max_val=100)
        assert card.is_dirty is True

    def test_adjust_range_equal_min_max_raises(self):
        card = self._make_range_card()
        with pytest.raises(ValueError, match="must not be equal"):
            card.adjust_range("level", 5, min_val=5, max_val=5)


    def test_get_range_denormalises(self):
        card = self._make_range_card(default=0.75)
        val = card.get_range("level", min_val=0, max_val=100)
        assert val == pytest.approx(75.0)

    def test_get_range_custom_domain(self):
        card = self._make_range_card(default=0.5)
        val = card.get_range("level", min_val=2000, max_val=6000)
        assert val == pytest.approx(4000.0)

    def test_get_range_equal_min_max_raises(self):
        card = self._make_range_card()
        with pytest.raises(ValueError, match="must not be equal"):
            card.get_range("level", min_val=5, max_val=5)

    def test_get_range_unknown_binding_raises(self):
        card = self._make_range_card()
        with pytest.raises(KeyError):
            card.get_range("nonexistent", min_val=0, max_val=100)


class TestDuiCardToggleBinding:
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
        card = DuiCard(spec)
        card.mark_clean()
        card.set("lights", True)
        assert card.is_dirty is True

    def test_set_toggle_same_value_not_dirty(self):
        spec = self._make_toggle_spec()
        card = DuiCard(spec)
        card.mark_clean()
        card.set("lights", False)
        assert card.is_dirty is False

    def test_get_toggle_value(self):
        spec = self._make_toggle_spec()
        card = DuiCard(spec)
        assert card.get("lights") is False
        card.set("lights", True)
        assert card.get("lights") is True

    def test_toggle_renders_differently(self):
        spec = self._make_toggle_spec()
        card = DuiCard(spec)
        img_off = card.render()

        card.set("lights", True)
        img_on = card.render()

        assert img_off.tobytes() != img_on.tobytes()


class TestDuiCardRender:
    def test_render_returns_image(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Hello")}
        )
        card = DuiCard(spec)
        img = card.render()
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        assert img.size == (197, 98)

    def test_render_with_changed_binding(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="Hello")}
        )
        card = DuiCard(spec)
        img1 = card.render()
        card.set("title", "World")
        img2 = card.render()
        assert img1.tobytes() != img2.tobytes()


class TestDuiCardBgTile:
    """Tests for DuiCard background tile support."""

    def test_set_bg_tile(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        tile = Image.new("RGB", (200, 100), (255, 0, 0))
        card.set_bg_tile(tile)
        assert card._bg_tile is tile

    def test_set_bg_tile_none(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        tile = Image.new("RGB", (200, 100), (255, 0, 0))
        card.set_bg_tile(tile)
        card.set_bg_tile(None)
        assert card._bg_tile is None

    def test_bg_tile_initially_none(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        assert card._bg_tile is None


class TestDuiCardPrepareAssets:
    async def test_prepare_assets_is_noop(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        await card.prepare_assets()


class TestDuiCardEvents:
    def test_on_decorator(self):
        spec = _make_card_spec(
            events=(EventMapping(name="play", source="encoder_press"),),
        )
        card = DuiCard(spec)

        @card.on("play")
        async def handler():
            pass

        assert handler is not None

    def test_bind_event(self):
        spec = _make_card_spec(
            events=(EventMapping(name="play", source="encoder_press"),),
        )
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("play", handler)
        card.handle_encoder_press()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1
        # The registered callable wraps the user's handler so any
        # state changes auto-trigger a refresh; the original handler
        # is preserved on the wrapper for introspection.
        assert callbacks[0][0].__wrapped__ is handler

    def test_encoder_turn_routes_to_handler(self):
        spec = _make_card_spec(
            events=(
                EventMapping(name="next", source="encoder_turn", direction="right"),
            ),
        )
        card = DuiCard(spec)
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
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("next", handler)

        card.handle_encoder_turn(-1)
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 0

    def test_encoder_press_routes(self):
        spec = _make_card_spec(
            events=(EventMapping(name="press", source="encoder_press"),),
        )
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("press", handler)

        card.handle_encoder_press()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1

    def test_encoder_release_routes(self):
        spec = _make_card_spec(
            events=(EventMapping(name="release", source="encoder_release"),),
        )
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("release", handler)

        card.handle_encoder_press()
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
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("card_tap", handler)

        event = TouchEvent(event_type=EventType.TOUCH_SHORT, x=50, y=50)
        await card.dispatch_touch(event)
        handler.assert_awaited_once()

    async def test_dispatch_touch_falls_back_to_base(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
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
        card = DuiCard(spec)
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
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("press", handler)

        await card.dispatch_encoder_press()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1

    async def test_dispatch_encoder_release_via_base_card(self):
        spec = _make_card_spec(
            events=(EventMapping(name="release", source="encoder_release"),),
        )
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("release", handler)

        await card.dispatch_encoder_press()
        card.drain_pending_callbacks()
        await card.dispatch_encoder_release()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1


class TestDuiCardDirtyTracking:
    def test_starts_dirty(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        assert card.is_dirty is True

    def test_mark_clean_and_dirty(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        card.mark_clean()
        assert card.is_dirty is False
        card.mark_dirty()
        assert card.is_dirty is True

    def test_set_rendered_clears_dirty(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        img = Image.new("RGB", (197, 98))
        card.set_rendered(img)
        assert card.is_dirty is False
        assert card.rendered is img


class TestDuiCardHandlerAutoRefresh:
    """Registered handlers that mutate state must auto-trigger a refresh.

    Regression tests for the bug where accumulator-driven and hold-timer
    handlers fired from detached asyncio tasks, mutating bindings without
    ever causing a render.
    """

    @pytest.fixture
    def card(self):
        spec = _make_card_spec(
            bindings={"title": TextBinding(node="title", default="")},
            events=(
                EventMapping(
                    name="bump",
                    source="encoder_turn",
                    direction="right",
                    accumulate=True,
                ),
                EventMapping(name="press", source="encoder_press"),
                EventMapping(name="hold", source="encoder_hold", hold_ms=50),
            ),
        )
        return DuiCard(spec)

    async def test_handler_dirties_card_triggers_refresh(self, card):
        """Wrapper calls request_refresh when handler leaves card dirty."""
        refreshed = 0

        async def _refresh() -> None:
            nonlocal refreshed
            refreshed += 1
            card.mark_clean()

        card.set_refresh_callback(_refresh)
        card.mark_clean()

        @card.on("press")
        async def _press():
            card.set("title", "changed")

        # Invoke the wrapped handler directly (mirrors what
        # accumulator/hold tasks do once they fire).
        card.handle_encoder_press()
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

        assert refreshed == 1

    async def test_clean_handler_no_extra_refresh(self, card):
        """Wrapper is a no-op when the handler doesn't dirty the card."""
        refreshed = 0

        async def _refresh() -> None:
            nonlocal refreshed
            refreshed += 1
            card.mark_clean()

        card.set_refresh_callback(_refresh)
        card.mark_clean()

        @card.on("press")
        async def _press():
            pass  # no state change

        card.handle_encoder_press()
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

        assert refreshed == 0

    async def test_explicit_request_refresh_not_doubled(self, card):
        """A handler that calls request_refresh itself doesn't trigger a 2nd refresh.

        After the handler's explicit refresh, the deck (here, the stub)
        marks the card clean.  The wrapper's post-call dirty check then
        finds nothing to do, so we get exactly one refresh -- not two.
        """
        refreshed = 0

        async def _refresh() -> None:
            nonlocal refreshed
            refreshed += 1
            card.mark_clean()

        card.set_refresh_callback(_refresh)
        card.mark_clean()

        @card.on("press")
        async def _press():
            card.set("title", "changed")
            await card.request_refresh()

        card.handle_encoder_press()
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

        assert refreshed == 1

    async def test_accumulator_flush_triggers_refresh(self, card):
        """The whole point: accumulated turns refresh after the debounce.

        Before this fix, the flush task fired the user's callback in a
        detached coroutine that never re-entered the dispatcher, so a
        rapid encoder spin could leave the display stale.
        """
        import asyncio

        refreshed = 0

        async def _refresh() -> None:
            nonlocal refreshed
            refreshed += 1
            card.mark_clean()

        card.set_refresh_callback(_refresh)
        card.mark_clean()

        @card.on("bump")
        async def _bump(_steps: int):
            card.set("title", "changed")

        # Simulate a burst of 5 ticks; the accumulator collapses them
        # into one debounced call to the wrapped handler.
        for _ in range(5):
            card.handle_encoder_turn(1)
        # Wait for the default 0.25s debounce window to elapse plus
        # a tiny buffer for the flush task to run.
        await asyncio.sleep(0.4)

        assert refreshed == 1
        assert card.get("title") == "changed"
