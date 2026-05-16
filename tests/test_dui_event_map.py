"""Tests for deux.dui.event_map — event routing and gesture detection."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from deux.dui.event_map import EventMap
from deux.dui.schema import EventMapping, Region
from deux.runtime.events import EventType


def _make_events(*specs: tuple) -> tuple[EventMapping, ...]:
    """Shorthand to create event mappings from (name, source, kwargs) tuples."""
    result = []
    for spec in specs:
        if len(spec) == 2:
            name, source = spec
            result.append(EventMapping(name=name, source=source))
        else:
            name, source, kwargs = spec
            result.append(EventMapping(name=name, source=source, **kwargs))
    return tuple(result)


def _handlers(results: list) -> list:
    """Return the list of handlers as-is (identity helper for readability)."""
    return results


def _handler(result):
    """Return the handler as-is (identity helper for readability)."""
    return result


class TestEncoderTurn:
    def test_turn_right(self):
        events = _make_events(
            ("next", "encoder_turn", {"direction": "right"}),
            ("prev", "encoder_turn", {"direction": "left"}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("next", handler)
        result = em.handle_encoder_turn(1)
        assert _handler(result) is handler

    def test_turn_left(self):
        events = _make_events(
            ("next", "encoder_turn", {"direction": "right"}),
            ("prev", "encoder_turn", {"direction": "left"}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("prev", handler)
        result = em.handle_encoder_turn(-1)
        assert _handler(result) is handler

    def test_turn_no_direction_filter(self):
        events = _make_events(("scroll", "encoder_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("scroll", handler)
        assert _handler(em.handle_encoder_turn(1)) is handler
        assert _handler(em.handle_encoder_turn(-1)) is handler

    def test_turn_no_match(self):
        events = _make_events(("next", "encoder_turn", {"direction": "right"}))
        em = EventMap(events)
        assert em.handle_encoder_turn(1) is None

    def test_turn_wrong_direction(self):
        events = _make_events(("next", "encoder_turn", {"direction": "right"}))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("next", handler)
        assert (
            em.handle_encoder_turn(-1) is None
        )

    def test_turn_suppressed_while_pressed_when_no_press_turn_declared(self):
        """encoder_turn must not fire while the encoder is pressed."""
        events = _make_events(("scroll", "encoder_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("scroll", handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert result is None
        handler.assert_not_called()

    def test_turn_resumes_after_release(self):
        """encoder_turn fires again once the encoder is released.

        Uses ``release_turn_grace_ms=0`` so the post-release suppression
        window (covered separately in :class:`TestPostReleaseTurnGrace`)
        does not interfere with this assertion.
        """
        events = _make_events(("scroll", "encoder_turn"))
        em = EventMap(events, release_turn_grace_ms=0)
        handler = AsyncMock()
        em.on("scroll", handler)

        em.handle_encoder_press()
        assert em.handle_encoder_turn(1) is None
        em.handle_encoder_release()

        result = em.handle_encoder_turn(1)
        assert _handler(result) is handler

    async def test_accumulator_tick_not_delivered_while_pressed(self):
        """Accumulated encoder_turn ticks are dropped while the encoder is pressed."""
        events = _make_events(
            ("scroll", "encoder_turn", {"accumulate": True, "accumulate_delay": 0.02}),
        )
        em = EventMap(events, release_turn_grace_ms=0)
        handler = AsyncMock()
        em.on("scroll", handler)

        em.handle_encoder_press()
        em.handle_encoder_turn(1)
        em.handle_encoder_turn(1)
        em.handle_encoder_turn(-1)

        await asyncio.sleep(0.1)
        handler.assert_not_called()

        em.handle_encoder_release()
        em.handle_encoder_turn(1)
        em.handle_encoder_turn(1)

        await asyncio.sleep(0.1)
        handler.assert_awaited_once_with(2)


class TestEncoderPressRelease:
    def test_simple_press(self):
        events = _make_events(("press", "encoder_press"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("press", handler)
        assert em.handle_encoder_press() == [handler]

    def test_simple_release(self):
        events = _make_events(("release", "encoder_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("release", handler)
        em.handle_encoder_press()
        assert _handlers(em.handle_encoder_release()) == [handler]

    def test_press_release_gesture_within_duration(self):
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 500}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("toggle", handler)

        em.handle_encoder_press()
        result = em.handle_encoder_release()
        assert handler in _handlers(result)

    def test_press_release_gesture_exceeded_duration(self):
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 1}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("toggle", handler)

        em.handle_encoder_press()
        time.sleep(0.01)
        result = em.handle_encoder_release()
        assert handler not in _handlers(result)

    def test_press_release_no_max_duration(self):
        events = _make_events(("toggle", "encoder_press_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("toggle", handler)

        em.handle_encoder_press()
        time.sleep(0.01)
        result = em.handle_encoder_release()
        assert handler in _handlers(result)

    def test_release_without_press(self):
        events = _make_events(("release", "encoder_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("release", handler)
        result = em.handle_encoder_release()
        assert _handlers(result) == [handler]

    def test_release_always_fires_alongside_press_release(self):
        """encoder_release fires even when encoder_press_release also fires."""
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 500}),
            ("up", "encoder_release"),
        )
        em = EventMap(events)
        toggle_handler = AsyncMock()
        release_handler = AsyncMock()
        em.on("toggle", toggle_handler)
        em.on("up", release_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_release()
        assert toggle_handler in _handlers(result)
        assert release_handler in _handlers(result)


class TestEncoderPressTurn:
    def test_press_turn_while_pressed(self):
        events = _make_events(("seek", "encoder_press_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("seek", handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert _handler(result) is handler

    def test_press_turn_not_pressed(self):
        events = _make_events(("seek", "encoder_press_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("seek", handler)

        result = em.handle_encoder_turn(1)
        assert result is None

    def test_press_turn_after_release(self):
        events = _make_events(("seek", "encoder_press_turn"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("seek", handler)

        em.handle_encoder_press()
        em.handle_encoder_release()
        result = em.handle_encoder_turn(1)
        assert result is None

    def test_press_turn_direction_right(self):
        events = _make_events(
            ("seek_fwd", "encoder_press_turn", {"direction": "right"}),
            ("seek_bwd", "encoder_press_turn", {"direction": "left"}),
        )
        em = EventMap(events)
        fwd_handler = AsyncMock()
        bwd_handler = AsyncMock()
        em.on("seek_fwd", fwd_handler)
        em.on("seek_bwd", bwd_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert _handler(result) is fwd_handler

    def test_press_turn_direction_left(self):
        events = _make_events(
            ("seek_fwd", "encoder_press_turn", {"direction": "right"}),
            ("seek_bwd", "encoder_press_turn", {"direction": "left"}),
        )
        em = EventMap(events)
        fwd_handler = AsyncMock()
        bwd_handler = AsyncMock()
        em.on("seek_fwd", fwd_handler)
        em.on("seek_bwd", bwd_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(-1)
        assert _handler(result) is bwd_handler

    def test_press_turn_direction_no_match(self):
        events = _make_events(
            ("seek_fwd", "encoder_press_turn", {"direction": "right"}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("seek_fwd", handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(-1)
        assert result is None

    def test_press_turn_takes_priority_over_regular_turn(self):
        """encoder_press_turn is checked before encoder_turn when pressed."""
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("seek", "encoder_press_turn"),
        )
        em = EventMap(events)
        scroll_handler = AsyncMock()
        seek_handler = AsyncMock()
        em.on("scroll", scroll_handler)
        em.on("seek", seek_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert _handler(result) is seek_handler

    def test_press_turn_direction_mismatch_does_not_fall_back(self):
        """When pressed, a direction-mismatched press_turn does NOT fall back to encoder_turn."""
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("seek_fwd", "encoder_press_turn", {"direction": "right"}),
        )
        em = EventMap(events)
        scroll_handler = AsyncMock()
        seek_handler = AsyncMock()
        em.on("scroll", scroll_handler)
        em.on("seek_fwd", seek_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(-1)
        assert result is None
        scroll_handler.assert_not_called()
        seek_handler.assert_not_called()


class TestPostReleaseTurnGrace:
    """Suppression of encoder_turn for a short window after a press+turn cycle.

    Mirrors the real ergonomic problem: a finger lifting off a rotary encoder
    after a press_turn gesture often produces a stray tick, which would
    spuriously fire the unrelated encoder_turn handler (e.g. brightness on
    DashboardCard) without this grace window.
    """

    async def test_turn_after_release_with_intervening_turn_is_suppressed(self):
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("seek", "encoder_press_turn"),
        )
        em = EventMap(events, release_turn_grace_ms=80)
        scroll_handler = AsyncMock()
        seek_handler = AsyncMock()
        em.on("scroll", scroll_handler)
        em.on("seek", seek_handler)

        em.handle_encoder_press()
        em.handle_encoder_turn(1)
        em.handle_encoder_release()

        result = em.handle_encoder_turn(1)
        assert result is None
        scroll_handler.assert_not_called()

    async def test_turn_after_release_without_intervening_turn_fires(self):
        """A clean press-release with no turn must NOT open a suppression window."""
        events = _make_events(("scroll", "encoder_turn"))
        em = EventMap(events, release_turn_grace_ms=80)
        handler = AsyncMock()
        em.on("scroll", handler)

        em.handle_encoder_press()
        em.handle_encoder_release()

        result = em.handle_encoder_turn(1)
        assert _handler(result) is handler

    async def test_grace_window_expires(self):
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("seek", "encoder_press_turn"),
        )
        em = EventMap(events, release_turn_grace_ms=30)
        scroll_handler = AsyncMock()
        em.on("scroll", scroll_handler)
        em.on("seek", AsyncMock())

        em.handle_encoder_press()
        em.handle_encoder_turn(1)
        em.handle_encoder_release()

        await asyncio.sleep(0.06)

        result = em.handle_encoder_turn(1)
        assert _handler(result) is scroll_handler

    async def test_grace_triggered_even_when_turn_was_silent(self):
        """A silent turn-while-pressed (no press_turn declared) still opens the window."""
        events = _make_events(("scroll", "encoder_turn"))
        em = EventMap(events, release_turn_grace_ms=80)
        handler = AsyncMock()
        em.on("scroll", handler)

        em.handle_encoder_press()
        em.handle_encoder_turn(1)  # silent — no press_turn declared
        em.handle_encoder_release()

        result = em.handle_encoder_turn(1)
        assert result is None
        handler.assert_not_called()

    async def test_press_turn_during_grace_is_not_suppressed(self):
        """Suppression only blocks plain encoder_turn, not encoder_press_turn."""
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("seek", "encoder_press_turn"),
        )
        em = EventMap(events, release_turn_grace_ms=80)
        seek_handler = AsyncMock()
        em.on("scroll", AsyncMock())
        em.on("seek", seek_handler)

        em.handle_encoder_press()
        em.handle_encoder_turn(1)
        em.handle_encoder_release()

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert _handler(result) is seek_handler

    async def test_default_grace_window_is_active(self):
        """The default grace window (DEFAULT_RELEASE_TURN_GRACE_MS) is non-zero."""
        events = _make_events(("scroll", "encoder_turn"))
        em = EventMap(events)  # default grace
        handler = AsyncMock()
        em.on("scroll", handler)

        em.handle_encoder_press()
        em.handle_encoder_turn(1)
        em.handle_encoder_release()

        result = em.handle_encoder_turn(1)
        assert result is None
        handler.assert_not_called()

    async def test_grace_zero_disables_suppression(self):
        events = _make_events(("scroll", "encoder_turn"))
        em = EventMap(events, release_turn_grace_ms=0)
        handler = AsyncMock()
        em.on("scroll", handler)

        em.handle_encoder_press()
        em.handle_encoder_turn(1)
        em.handle_encoder_release()

        result = em.handle_encoder_turn(1)
        assert _handler(result) is handler


class TestKeyEvents:
    def test_key_press(self):
        events = _make_events(("hold", "key_press"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("hold", handler)
        assert _handlers(em.handle_key_press()) == [handler]

    def test_key_release(self):
        events = _make_events(("up", "key_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("up", handler)
        em.handle_key_press()
        assert _handlers(em.handle_key_release()) == [handler]

    def test_key_press_release_within_duration(self):
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 500}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("activate", handler)

        em.handle_key_press()
        result = em.handle_key_release()
        assert handler in _handlers(result)

    def test_key_press_release_exceeded(self):
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 1}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("activate", handler)

        em.handle_key_press()
        time.sleep(0.01)
        result = em.handle_key_release()
        assert handler not in _handlers(result)

    def test_key_release_without_press(self):
        events = _make_events(("up", "key_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("up", handler)
        result = em.handle_key_release()
        assert _handlers(result) == [handler]

    def test_key_press_release_no_max(self):
        events = _make_events(("tap", "key_press_release"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("tap", handler)
        em.handle_key_press()
        time.sleep(0.01)
        assert handler in _handlers(em.handle_key_release())

    def test_release_always_fires_alongside_press_release(self):
        """key_release fires even when key_press_release also fires."""
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 500}),
            ("up", "key_release"),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        release_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("up", release_handler)

        em.handle_key_press()
        result = em.handle_key_release()
        assert tap_handler in _handlers(result)
        assert release_handler in _handlers(result)

    def test_press_always_fires_with_hold_configured(self):
        """key_press fires even when key_hold is also configured."""
        events = _make_events(
            ("down", "key_press"),
            ("long_hold", "key_hold", {"hold_ms": 500}),
        )
        em = EventMap(events)
        press_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("down", press_handler)
        em.on("long_hold", hold_handler)

        result = em.handle_key_press()
        assert press_handler in _handlers(result)

    def test_no_key_press_mapping_returns_empty(self):
        """handle_key_press returns empty list when no key_press mapping."""
        events = _make_events(("up", "key_release"))
        em = EventMap(events)
        result = em.handle_key_press()
        assert result == []

    def test_no_key_release_mapping_returns_empty(self):
        """handle_key_release returns empty list when no key_release mapping."""
        events = _make_events(("down", "key_press"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("down", handler)
        em.handle_key_press()
        result = em.handle_key_release()
        assert result == []


class TestKeyHold:
    async def test_hold_fires_after_delay(self):
        """key_hold handler fires after hold_ms while key is still held."""
        events = _make_events(
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("long_hold", handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)
        handler.assert_awaited_once()

    async def test_hold_cancelled_on_early_release(self):
        """key_hold does NOT fire if released before hold_ms."""
        events = _make_events(
            ("long_hold", "key_hold", {"hold_ms": 5000}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("long_hold", handler)

        em.handle_key_press()
        em.handle_key_release()
        await asyncio.sleep(0.01)
        handler.assert_not_awaited()

    async def test_hold_suppresses_press_release(self):
        """After key_hold fires, key_press_release is suppressed on release."""
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 5000}),
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_key_release()
        assert tap_handler not in _handlers(result)
        tap_handler.assert_not_awaited()

    async def test_hold_does_not_suppress_key_release(self):
        """After key_hold fires, key_release still fires."""
        events = _make_events(
            ("up", "key_release"),
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        release_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("up", release_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_key_release()
        assert release_handler in _handlers(result)

    async def test_short_tap_still_works_with_hold(self):
        """Quick release fires press_release, not the hold."""
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 300}),
            ("long_hold", "key_hold", {"hold_ms": 500}),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        result = em.handle_key_release()
        assert tap_handler in _handlers(result)
        hold_handler.assert_not_awaited()

    async def test_hold_no_handler_registered(self):
        """If no handler is registered, no timer starts."""
        events = _make_events(
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)

        em.handle_key_press()
        await asyncio.sleep(0.05)
        assert em._hold_task is None

    async def test_hold_reset_between_presses(self):
        """hold_fired is reset on each new press."""
        events = _make_events(
            ("activate", "key_press_release"),
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()
        em.handle_key_release()

        em.handle_key_press()
        result = em.handle_key_release()
        assert tap_handler in _handlers(result)

    async def test_hold_suppresses_press_release_but_not_release(self):
        """After key_hold fires, key_press_release is suppressed but key_release still fires."""
        events = _make_events(
            ("activate", "key_press_release", {"max_duration_ms": 5000}),
            ("up", "key_release"),
            ("long_hold", "key_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        tap_handler = AsyncMock()
        release_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("activate", tap_handler)
        em.on("up", release_handler)
        em.on("long_hold", hold_handler)

        em.handle_key_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_key_release()
        assert tap_handler not in _handlers(result)
        assert release_handler in _handlers(result)


class TestEncoderHold:
    async def test_encoder_hold_fires_after_delay(self):
        events = _make_events(
            ("enc_hold", "encoder_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("enc_hold", handler)

        em.handle_encoder_press()
        await asyncio.sleep(0.05)
        handler.assert_awaited_once()

    async def test_encoder_hold_cancelled_on_early_release(self):
        events = _make_events(
            ("enc_hold", "encoder_hold", {"hold_ms": 5000}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("enc_hold", handler)

        em.handle_encoder_press()
        em.handle_encoder_release()
        await asyncio.sleep(0.01)
        handler.assert_not_awaited()

    async def test_encoder_hold_suppresses_press_release(self):
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 5000}),
            ("enc_hold", "encoder_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        toggle_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("toggle", toggle_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_encoder_release()
        assert toggle_handler not in _handlers(result)
        toggle_handler.assert_not_awaited()

    async def test_encoder_short_tap_still_works_with_hold(self):
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 300}),
            ("enc_hold", "encoder_hold", {"hold_ms": 500}),
        )
        em = EventMap(events)
        toggle_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("toggle", toggle_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_release()
        assert toggle_handler in _handlers(result)
        hold_handler.assert_not_awaited()

    async def test_encoder_release_fires_alongside_press_release(self):
        """encoder_release fires even when encoder_press_release also fires."""
        events = _make_events(
            ("toggle", "encoder_press_release", {"max_duration_ms": 500}),
            ("up", "encoder_release"),
            ("enc_hold", "encoder_hold", {"hold_ms": 500}),
        )
        em = EventMap(events)
        toggle_handler = AsyncMock()
        release_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("toggle", toggle_handler)
        em.on("up", release_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_release()
        assert toggle_handler in _handlers(result)
        assert release_handler in _handlers(result)

    async def test_encoder_hold_cancelled_by_turn_before_hold_ms(self):
        """encoder_hold does NOT fire if a turn occurs before hold_ms expires."""
        events = _make_events(
            ("seek", "encoder_press_turn"),
            ("enc_hold", "encoder_hold", {"hold_ms": 50}),
        )
        em = EventMap(events)
        seek_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("seek", seek_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert _handler(result) is seek_handler

        await asyncio.sleep(0.1)
        hold_handler.assert_not_awaited()

    async def test_encoder_hold_cancelled_by_turn_without_press_turn_mapping(self):
        """encoder_hold is cancelled by turn even without encoder_press_turn mapping.

        With no ``encoder_press_turn`` declared, the turn itself is silent — the
        ``encoder_turn`` handler must not fire while the encoder is pressed —
        but the physical motion still cancels the pending hold timer.
        """
        events = _make_events(
            ("scroll", "encoder_turn"),
            ("enc_hold", "encoder_hold", {"hold_ms": 50}),
        )
        em = EventMap(events)
        scroll_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("scroll", scroll_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        result = em.handle_encoder_turn(1)
        assert result is None
        scroll_handler.assert_not_called()

        await asyncio.sleep(0.1)
        hold_handler.assert_not_awaited()

    async def test_encoder_hold_does_not_suppress_release(self):
        """After encoder_hold fires, encoder_release still fires."""
        events = _make_events(
            ("up", "encoder_release"),
            ("enc_hold", "encoder_hold", {"hold_ms": 10}),
        )
        em = EventMap(events)
        release_handler = AsyncMock()
        hold_handler = AsyncMock()
        em.on("up", release_handler)
        em.on("enc_hold", hold_handler)

        em.handle_encoder_press()
        await asyncio.sleep(0.05)
        hold_handler.assert_awaited_once()

        result = em.handle_encoder_release()
        assert release_handler in _handlers(result)


class TestTouchEvents:
    def test_tap_in_region(self):
        events = _make_events(("card_tap", "tap"))
        regions = (
            Region(name="card", x=0, y=0, width=197, height=98, events=("tap",)),
        )
        em = EventMap(events, regions)
        handler = AsyncMock()
        em.on("card_tap", handler)

        result = em.handle_touch(EventType.TOUCH_SHORT, 50, 50)
        assert _handler(result) is handler

    def test_tap_outside_region(self):
        events = _make_events(("card_tap", "tap"))
        regions = (Region(name="card", x=0, y=0, width=50, height=50, events=("tap",)),)
        em = EventMap(events, regions)
        handler = AsyncMock()
        em.on("card_tap", handler)

        result = em.handle_touch(EventType.TOUCH_SHORT, 100, 50)
        assert _handler(result) is handler

    def test_long_press_in_region(self):
        events = _make_events(("menu", "long_press"))
        regions = (
            Region(name="card", x=0, y=0, width=197, height=98, events=("long_press",)),
        )
        em = EventMap(events, regions)
        handler = AsyncMock()
        em.on("menu", handler)

        result = em.handle_touch(EventType.TOUCH_LONG, 50, 50)
        assert _handler(result) is handler

    def test_drag_not_handled(self):
        events = _make_events(("card_tap", "tap"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("card_tap", handler)
        result = em.handle_touch(EventType.TOUCH_DRAG, 50, 50)
        assert result is None

    def test_no_regions_still_matches_top_level(self):
        events = _make_events(("card_tap", "tap"))
        em = EventMap(events)
        handler = AsyncMock()
        em.on("card_tap", handler)
        result = em.handle_touch(EventType.TOUCH_SHORT, 50, 50)
        assert _handler(result) is handler

    def test_region_event_mismatch(self):
        """Region only accepts 'tap' but we send long_press."""
        events = _make_events(("menu", "long_press"))
        regions = (
            Region(name="card", x=0, y=0, width=197, height=98, events=("tap",)),
        )
        em = EventMap(events, regions)
        handler = AsyncMock()
        em.on("menu", handler)
        result = em.handle_touch(EventType.TOUCH_LONG, 50, 50)
        assert _handler(result) is handler


class TestEventMapRegistration:
    def test_on_unknown_event_raises(self):
        events = _make_events(("play", "encoder_press"))
        em = EventMap(events)
        with pytest.raises(KeyError, match="Unknown event"):
            em.on("nonexistent", AsyncMock())

    def test_event_names_property(self):
        events = _make_events(("play", "encoder_press"), ("stop", "encoder_release"))
        em = EventMap(events)
        assert em.event_names == ["play", "stop"]

    def test_unregistered_handler_returns_empty(self):
        events = _make_events(("play", "encoder_press"))
        em = EventMap(events)
        assert em.handle_encoder_press() == []


class TestAccumulatedTurns:
    async def test_accumulated_turn_debounces(self):
        """Multiple ticks flush as a single call with net steps."""
        events = _make_events(
            ("vol_up", "encoder_turn", {
                "direction": "right", "accumulate": True, "accumulate_delay": 0.05,
            }),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("vol_up", handler)

        assert em.handle_encoder_turn(1) is None
        assert em.handle_encoder_turn(1) is None
        assert em.handle_encoder_turn(1) is None

        await asyncio.sleep(0.1)
        handler.assert_awaited_once_with(3)

    async def test_accumulated_turn_respects_max_steps(self):
        events = _make_events(
            ("vol_up", "encoder_turn", {
                "direction": "right", "accumulate": True,
                "accumulate_delay": 0.05, "accumulate_max_steps": 2,
            }),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("vol_up", handler)

        for _ in range(5):
            em.handle_encoder_turn(1)

        await asyncio.sleep(0.1)
        handler.assert_awaited_once_with(2)

    async def test_accumulated_turn_custom_delay(self):
        events = _make_events(
            ("vol", "encoder_turn", {
                "accumulate": True, "accumulate_delay": 0.05,
            }),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("vol", handler)

        em.handle_encoder_turn(1)
        await asyncio.sleep(0.02)
        handler.assert_not_awaited()

        await asyncio.sleep(0.05)
        handler.assert_awaited_once_with(1)

    async def test_accumulated_press_turn(self):
        events = _make_events(
            ("kelvin", "encoder_press_turn", {
                "direction": "right", "accumulate": True, "accumulate_delay": 0.05,
            }),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("kelvin", handler)

        em.handle_encoder_press()
        assert em.handle_encoder_turn(1) is None
        assert em.handle_encoder_turn(1) is None

        await asyncio.sleep(0.1)
        handler.assert_awaited_once_with(2)

    async def test_accumulated_press_turn_not_pressed(self):
        """Accumulated press_turn doesn't fire when not pressed."""
        events = _make_events(
            ("kelvin", "encoder_press_turn", {
                "accumulate": True, "accumulate_delay": 0.05,
            }),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("kelvin", handler)

        assert em.handle_encoder_turn(1) is None

        await asyncio.sleep(0.1)
        handler.assert_not_awaited()

    async def test_cancel_accumulators(self):
        events = _make_events(
            ("vol_up", "encoder_turn", {
                "direction": "right", "accumulate": True, "accumulate_delay": 0.05,
            }),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("vol_up", handler)

        em.handle_encoder_turn(1)
        em.cancel_accumulators()

        await asyncio.sleep(0.1)
        handler.assert_not_awaited()

    async def test_non_accumulated_turn_unchanged(self):
        """Non-accumulated turns still return handler directly."""
        events = _make_events(
            ("vol_up", "encoder_turn", {"direction": "right"}),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("vol_up", handler)

        result = em.handle_encoder_turn(1)
        assert result is handler

    async def test_accumulated_direction_filtering(self):
        """Accumulated left turn only captures left ticks."""
        events = _make_events(
            ("vol_down", "encoder_turn", {
                "direction": "left", "accumulate": True, "accumulate_delay": 0.05,
            }),
        )
        em = EventMap(events)
        handler = AsyncMock()
        em.on("vol_down", handler)

        # Right tick should not match
        assert em.handle_encoder_turn(1) is None
        await asyncio.sleep(0.1)
        handler.assert_not_awaited()

        # Left tick should match
        em.handle_encoder_turn(-1)
        await asyncio.sleep(0.1)
        handler.assert_awaited_once_with(-1)
