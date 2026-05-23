"""Tests for the batched-render gate on :class:`deux.runtime.deck.Deck`.

The gate suppresses partial per-key writes during operations that end
in a full :meth:`DeckRenderer.render_screen_complete` call (initial
screen load, screen switch, theme change).  Any
:meth:`Card.request_refresh` or :meth:`KeySlot.request_refresh` call
issued while the gate is closed is folded into a single drain
refresh fired once the batched operation completes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from deux.render.theme import Theme
from deux.runtime.capabilities import STREAM_DECK_PLUS
from deux.runtime.deck import Deck


@pytest.fixture
def deck():
    """A :class:`Deck` pre-seeded with capabilities and a mocked renderer.

    ``render_screen_complete`` is replaced with an :class:`AsyncMock`
    so the tests can drive the gate without invoking the real render
    pipeline.
    """
    d = Deck.for_testing(STREAM_DECK_PLUS, serial_number="GATE")
    d._renderer.render_screen_complete = AsyncMock()  # type: ignore[method-assign]
    d._renderer.apply_theme = lambda: None  # type: ignore[method-assign]
    return d


class TestRefreshGate:
    """Direct exercises of :meth:`Deck.refresh` under the gate."""

    async def test_refresh_runs_normally_when_gate_open(self, deck):
        """With ``_batch_render_depth == 0``, refresh executes its body."""
        deck.screen("main")
        await deck.set_screen("main")  # opens the gate after initial render

        # Sanity: gate is open after set_screen returns.
        assert deck._batch_render_depth == 0

        # No active dirty content -> refresh is a no-op but reaches the body.
        await deck.refresh()
        assert deck._refresh_pending is False

    async def test_refresh_is_suppressed_inside_batched_render(self, deck):
        """Calls to refresh inside the gate set _refresh_pending and return early."""
        deck.screen("main")

        async with deck._batched_render():
            assert deck._batch_render_depth == 1
            await deck.refresh()
            assert deck._refresh_pending is True

        # Exiting the gate fires the drained refresh, which clears the flag.
        assert deck._refresh_pending is False

    async def test_drain_fires_once_for_many_suppressed_calls(self, deck):
        """N suppressed refresh calls collapse into exactly one drain refresh."""
        deck.screen("main")
        await deck.set_screen("main")
        deck._renderer.render_screen_complete.reset_mock()

        # Patch refresh AFTER set_screen so the drain path uses the mock.
        with pytest.MonkeyPatch.context() as mp:
            drain_mock = AsyncMock()
            mp.setattr(deck, "refresh", drain_mock)

            async with deck._batched_render():
                # The mocked refresh does not respect the gate (it
                # replaces the method entirely), so trip the pending
                # flag directly via the attribute the context manager
                # checks on exit.
                deck._refresh_pending = True
                deck._refresh_pending = True
                deck._refresh_pending = True

            drain_mock.assert_awaited_once()


class TestSetScreenGate:
    """Verifies :meth:`Deck.set_screen` wraps its body in the gate."""

    async def test_set_screen_closes_then_reopens_gate(self, deck):
        """During set_screen the gate is closed; after, it is open."""
        deck.screen("main")
        observed_depths: list[int] = []

        original = deck._renderer.render_screen_complete

        async def _capture():
            observed_depths.append(deck._batch_render_depth)
            await original()

        deck._renderer.render_screen_complete = _capture  # type: ignore[method-assign]
        await deck.set_screen("main")

        assert observed_depths == [1]
        assert deck._batch_render_depth == 0

    async def test_refresh_called_during_set_screen_is_deferred(self, deck):
        """A handler that calls refresh during on_screen_changed is gated."""
        deck.screen("main")
        observed: dict[str, int] = {"during": -1}

        @deck.on_screen_changed
        async def _handler(name: str, screens: dict) -> None:
            await deck.refresh()
            observed["during"] = deck._batch_render_depth

        await deck.set_screen("main")

        # Inside the handler, the gate was closed.
        assert observed["during"] == 1
        # After set_screen returns, the pending flag has been drained.
        assert deck._refresh_pending is False
        assert deck._batch_render_depth == 0

    async def test_subsequent_screen_switch_keeps_gate_consistent(self, deck):
        """Two successive screen switches leave depth at 0 and pending False."""
        deck.screen("a")
        deck.screen("b")

        await deck.set_screen("a")
        await deck.set_screen("b")

        assert deck._batch_render_depth == 0
        assert deck._refresh_pending is False


class TestSetThemeGate:
    """Verifies :meth:`Deck.set_theme` wraps its body in the gate."""

    async def test_set_theme_closes_gate_during_render(self, deck):
        """During set_theme the gate is closed; after, it is open."""
        deck.screen("main")
        await deck.set_screen("main")

        observed_depths: list[int] = []
        original = deck._renderer.render_screen_complete

        async def _capture():
            observed_depths.append(deck._batch_render_depth)
            await original()

        deck._renderer.render_screen_complete = _capture  # type: ignore[method-assign]

        await deck.set_theme(Theme(primary=(120, 120, 120)))

        assert observed_depths == [1]
        assert deck._batch_render_depth == 0

    async def test_set_theme_without_active_screen_does_not_render(self, deck):
        """set_theme returns early if no active screen, leaving gate untouched."""
        await deck.set_theme(Theme(primary=(120, 120, 120)))
        assert deck._batch_render_depth == 0
        deck._renderer.render_screen_complete.assert_not_awaited()


class TestNestedBatchedRender:
    """The depth counter must handle re-entrant batched operations."""

    async def test_nested_contexts_only_drain_on_outermost_exit(self, deck):
        """A nested _batched_render does not fire the drain prematurely."""
        deck.screen("main")
        await deck.set_screen("main")

        with pytest.MonkeyPatch.context() as mp:
            drain_mock = AsyncMock()
            mp.setattr(deck, "refresh", drain_mock)

            async with deck._batched_render():
                async with deck._batched_render():
                    deck._refresh_pending = True
                    assert deck._batch_render_depth == 2
                # Inner exit: depth now 1 -> drain must NOT fire yet.
                assert deck._batch_render_depth == 1
                drain_mock.assert_not_awaited()
            # Outer exit: depth 0 -> drain fires once.
            drain_mock.assert_awaited_once()

    async def test_nested_set_screen_from_on_screen_changed_handler(self, deck):
        """A handler that calls set_screen recursively still terminates."""
        deck.screen("a")
        deck.screen("b")

        called: list[str] = []
        invocations = {"n": 0}

        @deck.on_screen_changed
        async def _handler(name: str, screens: dict) -> None:
            called.append(name)
            invocations["n"] += 1
            if invocations["n"] == 1:
                # Switch again from inside the first handler.
                await deck.set_screen("b")

        await deck.set_screen("a")

        # Both switches completed exactly once each.
        assert called == ["a", "b"]
        assert deck._batch_render_depth == 0
        assert deck._refresh_pending is False


class TestStopResetsGate:
    """:meth:`Deck.stop` must reset the gate so reconnects start clean."""

    async def test_stop_resets_depth_and_pending(self, deck):
        """Manually corrupt the gate state then verify stop clears it."""
        deck._batch_render_depth = 5
        deck._refresh_pending = True

        # stop() short-circuits when _running is False, so simulate a
        # running deck without a real device by setting the flag and
        # routing the device-close path around the absent device.
        deck._running = True
        await deck.stop()

        assert deck._batch_render_depth == 0
        assert deck._refresh_pending is False
