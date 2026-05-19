"""Tests for :class:`deux.runtime.async_event.AsyncEvent`."""

from __future__ import annotations

import pytest

from deux.runtime import AsyncEvent
from deux.runtime.async_event import AsyncEvent as AsyncEventInternal


class TestSubscription:
    def test_decorator_returns_handler_unchanged(self) -> None:
        evt: AsyncEvent = AsyncEvent()

        async def handler() -> None:  # pragma: no cover - never invoked
            pass

        assert evt(handler) is handler
        assert evt.subscribe(handler) is handler  # idempotent return value

    def test_subscriber_count_tracks_subscriptions(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        assert evt.subscriber_count == 0

        async def a() -> None:  # pragma: no cover - never invoked
            pass

        async def b() -> None:  # pragma: no cover - never invoked
            pass

        evt.subscribe(a)
        evt.subscribe(b)
        assert evt.subscriber_count == 2

        evt.unsubscribe(a)
        assert evt.subscriber_count == 1

    def test_unsubscribe_unknown_handler_raises(self) -> None:
        evt: AsyncEvent = AsyncEvent()

        async def handler() -> None:  # pragma: no cover - never invoked
            pass

        with pytest.raises(ValueError):
            evt.unsubscribe(handler)


class TestEmit:
    async def test_no_subscribers_is_noop(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        await evt.emit(1, 2, three=3)  # must not raise

    async def test_invokes_every_subscriber_with_args(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        seen: list[tuple[int, str]] = []

        @evt
        async def first(value: int, label: str) -> None:
            seen.append((value, label))

        @evt
        async def second(value: int, label: str) -> None:
            seen.append((value * 2, label.upper()))

        await evt.emit(7, "hi")
        assert seen == [(7, "hi"), (14, "HI")]

    async def test_dispatch_order_is_registration_order(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        order: list[str] = []

        @evt
        async def a() -> None:
            order.append("a")

        @evt
        async def b() -> None:
            order.append("b")

        @evt
        async def c() -> None:
            order.append("c")

        await evt.emit()
        assert order == ["a", "b", "c"]

    async def test_subscribe_during_emit_does_not_fire_in_same_emission(
        self,
    ) -> None:
        """Snapshotting handlers prevents reentrant subscribe storms."""
        evt: AsyncEvent = AsyncEvent()
        late_called = False

        async def late() -> None:
            nonlocal late_called
            late_called = True

        @evt
        async def first() -> None:
            evt.subscribe(late)

        await evt.emit()
        assert late_called is False
        # But it does fire on the next emission.
        await evt.emit()
        assert late_called is True

    async def test_unsubscribe_during_emit_is_safe(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        calls: list[str] = []

        async def b() -> None:
            calls.append("b")

        unsubscribed = False

        @evt
        async def a() -> None:
            nonlocal unsubscribed
            calls.append("a")
            if not unsubscribed:
                evt.unsubscribe(b)
                unsubscribed = True

        evt.subscribe(b)
        await evt.emit()
        # Snapshot semantics: b still ran in this emission.
        assert calls == ["a", "b"]
        # Next emission only has a.
        calls.clear()
        await evt.emit()
        assert calls == ["a"]

    async def test_handler_exception_propagates(self) -> None:
        evt: AsyncEvent = AsyncEvent()

        @evt
        async def boom() -> None:
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError, match="nope"):
            await evt.emit()


class TestLastValue:
    def test_has_value_false_before_emit(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        assert evt.has_value is False

    def test_last_args_raises_before_emit(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        with pytest.raises(LookupError):
            _ = evt.last_args

    def test_last_kwargs_raises_before_emit(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        with pytest.raises(LookupError):
            _ = evt.last_kwargs

    async def test_has_value_true_after_emit(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        await evt.emit(42)
        assert evt.has_value is True

    async def test_last_args_captures_positional(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        await evt.emit(1, "two")
        assert evt.last_args == (1, "two")

    async def test_last_kwargs_captures_keywords(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        await evt.emit(x=10, y=20)
        assert evt.last_kwargs == {"x": 10, "y": 20}

    async def test_last_value_updates_on_each_emit(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        await evt.emit("first")
        await evt.emit("second")
        assert evt.last_args == ("second",)

    async def test_last_value_stored_even_with_no_subscribers(self) -> None:
        evt: AsyncEvent = AsyncEvent()
        await evt.emit(99)
        assert evt.last_args == (99,)


def test_top_level_export_matches_internal() -> None:
    """Public re-export from ``deux`` is the same class."""
    assert AsyncEvent is AsyncEventInternal
