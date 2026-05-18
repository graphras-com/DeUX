"""Tests for the reactive bind/bind_range/bind_many/forward methods on DuiCard and DuiKey."""

from __future__ import annotations

import pytest

from deux.dui.card import DuiCard
from deux.dui.key import DuiKey
from deux.dui.schema import (
    CssClassBinding,
    EventMapping,
    PackageSpec,
    PackageType,
    RangeBinding,
    TextBinding,
    ToggleBinding,
)
from deux.runtime.async_event import AsyncEvent

_CARD_SVG = (
    '<svg id="C" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<rect id="bg" width="197" height="98" fill="#1c1c1c"/>'
    '<text id="title" x="4" y="40" font-size="14">x</text>'
    '<text id="artist" x="4" y="60" font-size="14">x</text>'
    '<rect id="bar" x="4" y="86" width="189" height="4" fill="#0f0"/>'
    '<rect id="on_node" x="0" y="0" width="10" height="10" fill="#0f0"/>'
    '<rect id="off_node" x="0" y="0" width="10" height="10" fill="#f00"/>'
    '<g id="styled"/>'
    "</svg>"
)

_KEY_SVG = (
    '<svg id="K" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
    '<text id="label" x="60" y="100" font-size="14">x</text>'
    '<rect id="bar" x="4" y="110" width="112" height="4" fill="#0f0"/>'
    "</svg>"
)


def _card_spec(
    bindings: dict | None = None, events: tuple | None = None
) -> PackageSpec:
    return PackageSpec(
        name="C",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_CARD_SVG,
        bindings=bindings or {},
        events=events or (),
    )


def _key_spec(
    bindings: dict | None = None, events: tuple | None = None
) -> PackageSpec:
    return PackageSpec(
        name="K",
        type=PackageType.KEY,
        version=1,
        svg_source=_KEY_SVG,
        bindings=bindings or {},
        events=events or (),
    )


class _RefreshTracker:
    """Tiny helper that mirrors the deck's "mark clean after refresh" contract."""

    def __init__(self, target: DuiCard | DuiKey) -> None:
        self.count = 0
        self._target = target

    async def __call__(self) -> None:
        self.count += 1
        self._target.mark_clean()


# =====================================================================
# DuiCard.bind
# =====================================================================


class TestDuiCardBind:
    def _card(self) -> DuiCard:
        return DuiCard(
            _card_spec(
                bindings={"title": TextBinding(node="title", default="")}
            )
        )

    def test_returns_self_for_chaining(self):
        card = self._card()
        event = AsyncEvent()
        assert card.bind("title", event) is card

    def test_subscribes_to_event(self):
        card = self._card()
        event = AsyncEvent()
        card.bind("title", event)
        assert event.subscriber_count == 1

    async def test_event_emit_writes_binding(self):
        card = self._card()
        event = AsyncEvent()
        card.bind("title", event)
        await event.emit("Hello")
        assert card.get("title") == "Hello"

    async def test_event_emit_triggers_refresh(self):
        card = self._card()
        refresh = _RefreshTracker(card)
        card.set_refresh_callback(refresh)
        card.mark_clean()

        event = AsyncEvent()
        card.bind("title", event)
        await event.emit("Hello")

        assert refresh.count == 1

    async def test_idempotent_emit_skips_refresh(self):
        """Re-emitting the same value leaves the card clean and avoids a refresh."""
        card = DuiCard(
            _card_spec(
                bindings={"title": TextBinding(node="title", default="Same")}
            )
        )
        refresh = _RefreshTracker(card)
        card.set_refresh_callback(refresh)
        card.mark_clean()

        event = AsyncEvent()
        card.bind("title", event)
        await event.emit("Same")

        assert refresh.count == 0

    async def test_transform_maps_args_to_value(self):
        card = self._card()
        event = AsyncEvent()
        card.bind("title", event, transform=lambda v: f"[{v}]")
        await event.emit("loud")
        assert card.get("title") == "[loud]"

    async def test_transform_consumes_multi_arg_event(self):
        card = self._card()
        event = AsyncEvent()
        card.bind(
            "title",
            event,
            transform=lambda first, second: f"{first}-{second}",
        )
        await event.emit("a", "b")
        assert card.get("title") == "a-b"

    async def test_transform_sees_mutated_outer_state(self):
        """Transform reads at emit time, not at bind time."""
        card = self._card()
        event = AsyncEvent()
        ctx = {"prefix": "v1"}
        card.bind("title", event, transform=lambda v: f"{ctx['prefix']}:{v}")
        ctx["prefix"] = "v2"
        await event.emit("x")
        assert card.get("title") == "v2:x"

    async def test_unknown_binding_raises_at_emit(self):
        card = self._card()
        event = AsyncEvent()
        card.bind("nonexistent", event)
        with pytest.raises(KeyError):
            await event.emit("x")


# =====================================================================
# DuiCard.bind_range
# =====================================================================


class TestDuiCardBindRange:
    def _card(self, default: float = 0.0) -> DuiCard:
        return DuiCard(
            _card_spec(
                bindings={"level": RangeBinding(node="bar", default=default)}
            )
        )

    def test_returns_self_for_chaining(self):
        card = self._card()
        event = AsyncEvent()
        assert card.bind_range("level", event, min_val=0, max_val=100) is card

    def test_equal_min_max_raises_at_bind_time(self):
        """Validation surfaces at registration, not at first emit."""
        card = self._card()
        event = AsyncEvent()
        with pytest.raises(ValueError, match="must not be equal"):
            card.bind_range("level", event, min_val=5, max_val=5)
        # Subscriber should NOT have been added.
        assert event.subscriber_count == 0

    async def test_event_emit_normalises_to_unit_range(self):
        card = self._card()
        event = AsyncEvent()
        card.bind_range("level", event, min_val=0, max_val=100)
        await event.emit(50)
        assert card.get("level") == pytest.approx(0.5)

    async def test_event_emit_clamps_high(self):
        card = self._card()
        event = AsyncEvent()
        card.bind_range("level", event, min_val=0, max_val=100)
        await event.emit(250)
        assert card.get("level") == pytest.approx(1.0)

    async def test_event_emit_clamps_low(self):
        card = self._card()
        event = AsyncEvent()
        card.bind_range("level", event, min_val=0, max_val=100)
        await event.emit(-10)
        assert card.get("level") == pytest.approx(0.0)

    async def test_transform_returns_domain_value(self):
        card = self._card()
        event = AsyncEvent()
        # Event emits a Celsius temperature; transform turns it into Kelvin
        # which the slider treats as 2000–6000.
        card.bind_range(
            "level",
            event,
            min_val=2000,
            max_val=6000,
            transform=lambda c: 2000 + c * 10,
        )
        await event.emit(200)  # → 4000 K
        assert card.get("level") == pytest.approx(0.5)

    async def test_event_emit_triggers_refresh_only_when_changed(self):
        card = self._card(default=0.5)
        refresh = _RefreshTracker(card)
        card.set_refresh_callback(refresh)
        card.mark_clean()

        event = AsyncEvent()
        card.bind_range("level", event, min_val=0, max_val=100)

        await event.emit(50)  # already 0.5, no change
        assert refresh.count == 0

        await event.emit(80)
        assert refresh.count == 1


# =====================================================================
# DuiCard.bind_many
# =====================================================================


class TestDuiCardBindMany:
    def _card(self) -> DuiCard:
        return DuiCard(
            _card_spec(
                bindings={
                    "title": TextBinding(node="title", default=""),
                    "artist": TextBinding(node="artist", default=""),
                }
            )
        )

    def test_returns_self_for_chaining(self):
        card = self._card()
        event = AsyncEvent()
        assert card.bind_many(event, transform=lambda **_: {}) is card

    async def test_emit_sets_multiple_bindings(self):
        card = self._card()
        event = AsyncEvent()
        card.bind_many(
            event,
            transform=lambda track: {
                "title": track["title"],
                "artist": track["artist"],
            },
        )
        await event.emit({"title": "Hot", "artist": "Walker"})
        assert card.get("title") == "Hot"
        assert card.get("artist") == "Walker"

    async def test_emit_triggers_single_refresh(self):
        card = self._card()
        refresh = _RefreshTracker(card)
        card.set_refresh_callback(refresh)
        card.mark_clean()

        event = AsyncEvent()
        card.bind_many(
            event,
            transform=lambda track: {
                "title": track["title"],
                "artist": track["artist"],
            },
        )
        await event.emit({"title": "Hot", "artist": "Walker"})

        assert refresh.count == 1

    async def test_idempotent_emit_skips_refresh(self):
        card = self._card()
        card.set_many(title="Hot", artist="Walker")
        refresh = _RefreshTracker(card)
        card.set_refresh_callback(refresh)
        card.mark_clean()

        event = AsyncEvent()
        card.bind_many(
            event,
            transform=lambda track: {
                "title": track["title"],
                "artist": track["artist"],
            },
        )
        await event.emit({"title": "Hot", "artist": "Walker"})

        assert refresh.count == 0


# =====================================================================
# DuiCard.forward
# =====================================================================


class TestDuiCardForward:
    def _card(self) -> DuiCard:
        return DuiCard(
            _card_spec(
                bindings={"title": TextBinding(node="title", default="")},
                events=(
                    EventMapping(name="press", source="encoder_press"),
                    EventMapping(
                        name="bump",
                        source="encoder_turn",
                        direction="right",
                    ),
                ),
            )
        )

    def test_returns_self_for_chaining(self):
        card = self._card()

        async def _t() -> None:
            return None

        assert card.forward("press", _t) is card

    async def test_async_target_invoked_on_event(self):
        card = self._card()
        called = 0

        async def _target() -> None:
            nonlocal called
            called += 1

        card.forward("press", _target)
        card.handle_encoder_press()
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

        assert called == 1

    async def test_target_receives_event_args(self):
        card = self._card()
        seen = []

        async def _target(direction: int) -> None:
            seen.append(direction)

        card.forward("bump", _target)
        card.handle_encoder_turn(1)
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

        assert seen == [1]

    async def test_lambda_returning_coroutine_is_supported(self):
        """Common pattern: lambda that calls an async method.

        ``svc.do(...)`` returns a coroutine; the wrapper awaits it.
        """
        card = self._card()
        called = 0

        async def _async_op() -> None:
            nonlocal called
            called += 1

        card.forward("press", lambda: _async_op())
        card.handle_encoder_press()
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

        assert called == 1

    async def test_target_dirty_changes_trigger_refresh(self):
        """forward() goes through _wrap_handler so refresh fires automatically."""
        card = self._card()
        refresh = _RefreshTracker(card)
        card.set_refresh_callback(refresh)
        card.mark_clean()

        async def _target() -> None:
            card.set("title", "changed")

        card.forward("press", _target)
        card.handle_encoder_press()
        for handler, args in card.drain_pending_callbacks():
            await handler(*args)

        assert refresh.count == 1


# =====================================================================
# DuiKey -- mirror coverage
# =====================================================================


class TestDuiKeyBind:
    def _key(self) -> DuiKey:
        return DuiKey(
            _key_spec(
                bindings={"label": TextBinding(node="label", default="")}
            )
        )

    def test_returns_self_for_chaining(self):
        key = self._key()
        event = AsyncEvent()
        assert key.bind("label", event) is key

    async def test_event_emit_writes_binding_and_refreshes(self):
        key = self._key()
        refresh = _RefreshTracker(key)
        key.set_refresh_callback(refresh)
        key.mark_clean()

        event = AsyncEvent()
        key.bind("label", event)
        await event.emit("Hello")

        assert key.get("label") == "Hello"
        assert refresh.count == 1

    async def test_transform_applied(self):
        key = self._key()
        event = AsyncEvent()
        key.bind("label", event, transform=lambda v: v.upper())
        await event.emit("hi")
        assert key.get("label") == "HI"


class TestDuiKeyBindRange:
    def _key(self, default: float = 0.0) -> DuiKey:
        return DuiKey(
            _key_spec(
                bindings={"level": RangeBinding(node="bar", default=default)}
            )
        )

    def test_equal_min_max_raises(self):
        key = self._key()
        event = AsyncEvent()
        with pytest.raises(ValueError, match="must not be equal"):
            key.bind_range("level", event, min_val=5, max_val=5)
        assert event.subscriber_count == 0

    async def test_emit_normalises(self):
        key = self._key()
        event = AsyncEvent()
        key.bind_range("level", event, min_val=0, max_val=100)
        await event.emit(75)
        assert key.get("level") == pytest.approx(0.75)

    async def test_transform_used(self):
        key = self._key()
        event = AsyncEvent()
        key.bind_range(
            "level",
            event,
            min_val=0,
            max_val=10,
            transform=lambda v: v + 1,
        )
        await event.emit(4)
        assert key.get("level") == pytest.approx(0.5)


class TestDuiKeyBindMany:
    def _key(self) -> DuiKey:
        return DuiKey(
            _key_spec(
                bindings={
                    "label": TextBinding(node="label", default=""),
                }
            )
        )

    async def test_emit_sets_multiple_via_transform(self):
        # Single-binding key still exercises the multi-arg → dict path.
        key = self._key()
        event = AsyncEvent()
        key.bind_many(event, transform=lambda v: {"label": v})
        await event.emit("hi")
        assert key.get("label") == "hi"


class TestDuiKeyForward:
    def _key(self) -> DuiKey:
        return DuiKey(
            _key_spec(
                bindings={"label": TextBinding(node="label", default="")},
                events=(
                    EventMapping(
                        name="click",
                        source="key_press_release",
                        max_duration_ms=300,
                    ),
                ),
            )
        )

    async def test_target_invoked_on_event(self):
        key = self._key()
        called = 0

        async def _target() -> None:
            nonlocal called
            called += 1

        key.forward("click", _target)
        # key_press_release fires on release after a press.
        await key.dispatch(pressed=True)
        await key.dispatch(pressed=False)

        assert called == 1


# =====================================================================
# DuiCard.bind with toggle binding (covers boolean fan-out)
# =====================================================================


_TOGGLE_SVG = (
    '<svg id="T" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<rect id="bg" width="197" height="98" fill="#1c1c1c"/>'
    '<rect id="on" x="0" y="0" width="10" height="10" fill="#0f0"/>'
    '<rect id="off" x="0" y="0" width="10" height="10" fill="#f00"/>'
    "</svg>"
)


class TestDuiCardBindToggle:
    """bind() with a toggle binding -- bool emit drives node visibility."""

    def _card(self) -> DuiCard:
        spec = PackageSpec(
            name="T",
            type=PackageType.TOUCH_STRIP_CARD,
            version=1,
            svg_source=_TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="on", node_off="off", default=False
                ),
            },
        )
        return DuiCard(spec)

    async def test_emit_toggles(self):
        card = self._card()
        event = AsyncEvent()
        card.bind("lights", event)
        await event.emit(True)
        assert card.get("lights") is True
        await event.emit(False)
        assert card.get("lights") is False


class TestDuiCardBindCssClass:
    """bind() with a css_class binding -- string emit drives class attribute."""

    def _card(self) -> DuiCard:
        spec = PackageSpec(
            name="CC",
            type=PackageType.TOUCH_STRIP_CARD,
            version=1,
            svg_source=_CARD_SVG,
            bindings={
                "style": CssClassBinding(node="styled", default="idle"),
            },
        )
        return DuiCard(spec)

    async def test_emit_changes_class(self):
        card = self._card()
        event = AsyncEvent()
        card.bind("style", event)
        await event.emit("active")
        assert card.get("style") == "active"

    async def test_emit_clears_class(self):
        card = self._card()
        event = AsyncEvent()
        card.bind("style", event)
        await event.emit("active")
        await event.emit("")
        assert card.get("style") == ""


# ---------------------------------------------------------------------------
# Detach lifecycle tests
# ---------------------------------------------------------------------------


class TestDuiCardDetach:
    """Verify that DuiCard.detach() unsubscribes all handlers."""

    def _card(self) -> DuiCard:
        spec = _card_spec(
            bindings={
                "title": TextBinding(node="title", default=""),
                "bar": RangeBinding(node="bar", default=0.0),
            }
        )
        return DuiCard(spec)

    async def test_detach_removes_bind_handler(self):
        """After detach(), the event's subscriber count drops to zero."""
        card = self._card()
        event = AsyncEvent()
        card.bind("title", event)
        assert event.subscriber_count == 1
        card.detach()
        assert event.subscriber_count == 0

    async def test_detach_removes_bind_range_handler(self):
        """bind_range handlers are also removed by detach()."""
        card = self._card()
        event = AsyncEvent()
        card.bind_range("bar", event, min_val=0, max_val=100)
        assert event.subscriber_count == 1
        card.detach()
        assert event.subscriber_count == 0

    async def test_detach_removes_bind_many_handler(self):
        """bind_many handlers are also removed by detach()."""
        card = self._card()
        event = AsyncEvent()
        card.bind_many(event, lambda v: {"title": v})
        assert event.subscriber_count == 1
        card.detach()
        assert event.subscriber_count == 0

    async def test_detach_idempotent(self):
        """Calling detach() twice does not raise."""
        card = self._card()
        event = AsyncEvent()
        card.bind("title", event)
        card.detach()
        card.detach()  # should not raise
        assert event.subscriber_count == 0

    async def test_handler_count_stable_across_reconnect_cycles(self):
        """Simulates N reconnect cycles; handler count never grows."""
        event = AsyncEvent()
        for _ in range(5):
            card = self._card()
            card.bind("title", event)
            assert event.subscriber_count == 1
            card.detach()
            assert event.subscriber_count == 0


class TestDuiKeyDetach:
    """Verify that DuiKey.detach() unsubscribes all handlers."""

    def _key(self) -> DuiKey:
        spec = _key_spec(
            bindings={
                "label": TextBinding(node="label", default=""),
                "bar": RangeBinding(node="bar", default=0.0),
            }
        )
        return DuiKey(spec)

    async def test_detach_removes_bind_handler(self):
        """After detach(), the event's subscriber count drops to zero."""
        key = self._key()
        event = AsyncEvent()
        key.bind("label", event)
        assert event.subscriber_count == 1
        key.detach()
        assert event.subscriber_count == 0

    async def test_detach_removes_bind_range_handler(self):
        """bind_range handlers are also removed by detach()."""
        key = self._key()
        event = AsyncEvent()
        key.bind_range("bar", event, min_val=0, max_val=100)
        assert event.subscriber_count == 1
        key.detach()
        assert event.subscriber_count == 0

    async def test_handler_count_stable_across_reconnect_cycles(self):
        """Simulates N reconnect cycles; handler count never grows."""
        event = AsyncEvent()
        for _ in range(5):
            key = self._key()
            key.bind("label", event)
            assert event.subscriber_count == 1
            key.detach()
            assert event.subscriber_count == 0
