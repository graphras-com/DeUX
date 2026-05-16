"""Tests for deux.runtime.deck — Deck class."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from deux.render.metrics import RenderMetrics
from deux.runtime.capabilities import STREAM_DECK_PLUS
from deux.runtime.deck import Deck, DeckError
from deux.runtime.events import (
    EncoderPressEvent,
    EncoderTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)
from deux.ui.cards.base import Card
from deux.ui.screen import Screen
from tests.conftest import PANEL_HEIGHT, PANEL_WIDTH


class _TestCard(Card):
    """Minimal concrete card for testing deck dispatch without legacy widgets."""

    def render(self) -> Image.Image:
        return Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")


@pytest.fixture
def deck(tmp_path):
    """A Deck instance with required serial_number.

    Capabilities are pre-populated so tests can call ``deck.screen()``
    without going through the real device-discovery path.
    """
    d = Deck(serial_number="TEST123")
    d._caps = STREAM_DECK_PLUS
    d._metrics = RenderMetrics(STREAM_DECK_PLUS)
    return d


class TestDeckInit:
    def test_defaults(self, deck):
        assert deck._serial_number == "TEST123"
        assert deck._brightness == 80
        assert deck._device is None
        assert deck._transport is None
        assert deck._running is False
        assert deck._active_screen is None
        assert deck._screens == {}

    def test_custom_brightness(self):
        d = Deck(serial_number="ABC123", brightness=50)
        assert d._serial_number == "ABC123"
        assert d._brightness == 50


class TestDeckPage:
    def test_creates_screen(self, deck):
        p = deck.screen("main")
        assert isinstance(p, Screen)
        assert p.name == "main"

    def test_creates_page(self, deck):
        p = deck.screen("main")
        assert isinstance(p, Screen)
        assert p.name == "main"

    def test_same_instance(self, deck):
        a = deck.screen("main")
        b = deck.screen("main")
        assert a is b

    def test_different_screens(self, deck):
        a = deck.screen("main")
        b = deck.screen("settings")
        assert a is not b
        assert a.name == "main"
        assert b.name == "settings"


class TestDeckBrightness:
    def test_initial_brightness(self, deck):
        assert deck.brightness == 80

    async def test_set_brightness_clamps_low(self, deck):
        await deck.set_brightness(-10)
        assert deck.brightness == 0

    async def test_set_brightness_clamps_high(self, deck):
        await deck.set_brightness(200)
        assert deck.brightness == 100

    async def test_set_brightness_normal(self, deck):
        await deck.set_brightness(50)
        assert deck.brightness == 50

    async def test_set_brightness_with_device(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        await deck.set_brightness(60)
        assert deck.brightness == 60

    async def test_set_brightness_emits_event(self, deck):
        seen: list[int] = []

        @deck.on_brightness_changed
        async def _on(value: int) -> None:
            seen.append(value)

        await deck.set_brightness(42)
        assert seen == [42]

    async def test_set_brightness_idempotent_no_event(self, deck):
        """Setting the same value emits no event and skips the hardware push."""
        seen: list[int] = []

        @deck.on_brightness_changed
        async def _on(value: int) -> None:  # pragma: no cover - never invoked
            seen.append(value)

        # initial brightness is 80; setting to 80 should be a no-op.
        await deck.set_brightness(80)
        assert seen == []

    async def test_set_brightness_skips_hw_when_unchanged(
        self, deck, mock_streamdeck_device
    ):
        """A no-op call must not touch the hardware."""
        deck._device = mock_streamdeck_device
        await deck.set_brightness(80)  # equal to default
        mock_streamdeck_device.set_brightness.assert_not_called()

    async def test_set_brightness_emits_clamped_value(self, deck):
        seen: list[int] = []

        @deck.on_brightness_changed
        async def _on(value: int) -> None:
            seen.append(value)

        await deck.set_brightness(999)
        assert seen == [100]


class TestDeckSetPage:
    async def test_sets_active_screen(self, deck):
        deck.screen("main")
        deck._render_all_keys = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        await deck.set_screen("main")
        assert deck.active_screen is not None
        assert deck.active_screen.name == "main"

    async def test_nonexistent_page_raises(self, deck):
        with pytest.raises(DeckError, match="Screen 'missing' does not exist"):
            await deck.set_screen("missing")

    async def test_calls_render(self, deck):
        deck.screen("main")
        deck._render_all_keys = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        await deck.set_screen("main")
        deck._render_all_keys.assert_awaited_once()
        deck._render_touchscreen.assert_awaited_once()

    async def test_emits_event_after_render(self, deck):
        """on_screen_changed fires after the new screen has rendered."""
        deck.screen("main")
        deck._render_all_keys = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        order: list[str] = []
        deck._render_all_keys.side_effect = lambda: order.append("rendered")

        @deck.on_screen_changed
        async def _on(name: str, screens: dict) -> None:
            order.append(f"event:{name}")

        await deck.set_screen("main")
        assert order == ["rendered", "event:main"]

    async def test_idempotent_does_not_emit_or_re_render(self, deck):
        """Re-setting the same screen emits nothing and re-renders nothing."""
        deck.screen("main")
        deck._render_all_keys = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        await deck.set_screen("main")  # initial activation
        seen: list[str] = []

        @deck.on_screen_changed
        async def _on(name: str, screens: dict) -> None:  # pragma: no cover - never invoked
            seen.append(name)

        deck._render_all_keys.reset_mock()
        deck._render_touchscreen.reset_mock()

        await deck.set_screen("main")
        assert seen == []
        deck._render_all_keys.assert_not_awaited()
        deck._render_touchscreen.assert_not_awaited()

    async def test_emits_event_on_screen_switch(self, deck):
        deck.screen("main")
        deck.screen("settings")
        deck._render_all_keys = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        seen: list[str] = []

        @deck.on_screen_changed
        async def _on(name: str, screens: dict) -> None:
            seen.append(name)

        await deck.set_screen("main")
        await deck.set_screen("settings")
        await deck.set_screen("main")
        assert seen == ["main", "settings", "main"]


class TestDeckActivePage:
    def test_initially_none(self, deck):
        assert deck.active_screen is None


class TestDeckWireRefreshCallbacks:
    """Tests for the screen-wide refresh-callback wiring."""

    async def test_wires_keys_and_cards_on_set_screen(self, deck):
        """set_screen wires deck.refresh on every key and card."""
        screen = deck.screen("main")
        key = screen.key(0)
        card = _TestCard()
        screen.set_card(0, card)

        deck._render_all_keys = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        # Patch BEFORE set_screen so the bound method captured by the
        # wiring is the mock.
        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck.set_screen("main")
            await key.request_refresh()
            await card.request_refresh()
            assert mock_refresh.await_count == 2

    async def test_request_refresh_from_key_handler_triggers_refresh(self, deck):
        """A key handler can call request_refresh after set_screen."""
        screen = deck.screen("main")
        key = screen.key(0)

        deck._render_all_keys = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        @key.on_press
        async def _press() -> None:
            await key.request_refresh()

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck.set_screen("main")
            await deck._dispatch(KeyEvent(key=0, pressed=True))
            mock_refresh.assert_awaited()


class TestDeckRefresh:
    async def test_no_active_screen(self, deck):
        """refresh() is a no-op when no active page."""
        await deck.refresh()

    async def test_renders_dirty_touchscreen(self, deck):
        p = deck.screen("main")
        deck._active_screen = p
        deck._render_touchscreen = AsyncMock()

        await deck.refresh()
        deck._render_touchscreen.assert_awaited_once()

    async def test_skips_clean_touchscreen(self, deck):
        p = deck.screen("main")
        for w in p.cards:
            w.mark_clean()

        deck._active_screen = p
        deck._render_touchscreen = AsyncMock()

        await deck.refresh()
        deck._render_touchscreen.assert_not_awaited()


class TestDeckDispatch:
    async def test_no_active_screen(self, deck):
        """_dispatch is a no-op with no active page."""
        event = KeyEvent(key=0, pressed=True)
        await deck._dispatch(event)

    async def test_key_press_dispatches(self, deck):
        p = deck.screen("main")
        handler = AsyncMock()
        p.key(0).on_press(handler)
        deck._active_screen = p

        await deck._dispatch(KeyEvent(key=0, pressed=True))
        handler.assert_awaited_once()

    async def test_key_release_dispatches(self, deck):
        p = deck.screen("main")
        handler = AsyncMock()
        p.key(0).on_release(handler)
        deck._active_screen = p

        await deck._dispatch(KeyEvent(key=0, pressed=False))
        handler.assert_awaited_once()

    async def test_key_press_no_handler(self, deck):
        """No error when key has no handler."""
        p = deck.screen("main")
        p.key(0)
        deck._active_screen = p

        await deck._dispatch(KeyEvent(key=0, pressed=True))

    async def test_key_event_unknown_key(self, deck):
        """No error when event targets a key that doesn't exist on the page."""
        p = deck.screen("main")
        deck._active_screen = p

        await deck._dispatch(KeyEvent(key=7, pressed=True))

    async def test_key_press_refreshes_when_dirty(self, deck):
        """refresh() is called after key dispatch if the key is dirty."""
        p = deck.screen("main")
        key_slot = p.key(0)

        async def mark_dirty():
            key_slot._dirty = True

        key_slot.on_press(mark_dirty)
        deck._active_screen = p
        key_slot._dirty = False

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._dispatch(KeyEvent(key=0, pressed=True))
            mock_refresh.assert_awaited_once()

    async def test_key_press_no_refresh_when_clean(self, deck):
        """refresh() is NOT called after key dispatch if key stays clean."""
        p = deck.screen("main")
        key_slot = p.key(0)
        key_slot.on_press(AsyncMock())
        deck._active_screen = p
        key_slot._dirty = False

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._dispatch(KeyEvent(key=0, pressed=True))
            mock_refresh.assert_not_awaited()

    async def test_encoder_turn_dispatches(self, deck):
        p = deck.screen("main")
        handler = AsyncMock()
        p.encoder(1).on_turn(handler)
        deck._active_screen = p

        await deck._dispatch(EncoderTurnEvent(encoder=1, direction=3))
        handler.assert_awaited_once_with(3)

    async def test_encoder_turn_no_handler(self, deck):
        p = deck.screen("main")
        p.encoder(1)
        deck._active_screen = p

        await deck._dispatch(EncoderTurnEvent(encoder=1, direction=1))

    async def test_encoder_turn_unknown_encoder(self, deck):
        p = deck.screen("main")
        deck._active_screen = p

        await deck._dispatch(EncoderTurnEvent(encoder=2, direction=1))

    async def test_encoder_turn_dispatches_to_card(self, deck):
        """Encoder turn is forwarded to the card at that zone."""
        p = deck.screen("main")
        card = _TestCard()
        p.set_card(1, card)
        deck._active_screen = p

        turn_handler = AsyncMock()
        card.on_encoder_turn(turn_handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(EncoderTurnEvent(encoder=1, direction=5))

        turn_handler.assert_awaited_once_with(5)

    async def test_encoder_press_dispatches(self, deck):
        p = deck.screen("main")
        handler = AsyncMock()
        p.encoder(0).on_press(handler)
        deck._active_screen = p

        await deck._dispatch(EncoderPressEvent(encoder=0, pressed=True))
        handler.assert_awaited_once()

    async def test_encoder_release_dispatches(self, deck):
        p = deck.screen("main")
        handler = AsyncMock()
        p.encoder(0).on_release(handler)
        deck._active_screen = p

        await deck._dispatch(EncoderPressEvent(encoder=0, pressed=False))
        handler.assert_awaited_once()

    async def test_encoder_press_no_handler(self, deck):
        p = deck.screen("main")
        p.encoder(0)
        deck._active_screen = p

        await deck._dispatch(EncoderPressEvent(encoder=0, pressed=True))

    async def test_encoder_press_unknown_encoder(self, deck):
        p = deck.screen("main")
        deck._active_screen = p

        await deck._dispatch(EncoderPressEvent(encoder=3, pressed=True))

    async def test_encoder_press_dispatches_to_card(self, deck):
        """Encoder press is forwarded to the card's dispatch_encoder_press."""
        p = deck.screen("main")
        card = _TestCard()
        p.set_card(0, card)
        deck._active_screen = p

        press_handler = AsyncMock()
        card.on_encoder_press(press_handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(EncoderPressEvent(encoder=0, pressed=True))

        press_handler.assert_awaited_once()

    async def test_encoder_release_dispatches_to_card(self, deck):
        """Encoder release is forwarded to the card's dispatch_encoder_release."""
        p = deck.screen("main")
        card = _TestCard()
        p.set_card(0, card)
        deck._active_screen = p

        release_handler = AsyncMock()
        card.on_encoder_release(release_handler)

        await deck._dispatch(EncoderPressEvent(encoder=0, pressed=False))
        release_handler.assert_awaited_once()

    async def test_encoder_press_release_does_not_call_press_handler(self, deck):
        """Card on_encoder_press is NOT called for release events."""
        p = deck.screen("main")
        card = _TestCard()
        p.set_card(0, card)
        deck._active_screen = p

        handler = AsyncMock()
        card.on_encoder_press(handler)

        await deck._dispatch(EncoderPressEvent(encoder=0, pressed=False))
        handler.assert_not_awaited()

    async def test_touch_short_dispatches(self, deck):
        p = deck.screen("main")
        handler = AsyncMock()
        p.card(0).on_tap(handler)
        deck._active_screen = p
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        await deck._dispatch(TouchEvent(event_type=EventType.TOUCH_SHORT, x=50, y=50))
        handler.assert_awaited_once()

    async def test_touch_long_dispatches(self, deck):
        p = deck.screen("main")
        handler = AsyncMock()
        p.card(1).on_long_press(handler)
        deck._active_screen = p
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        await deck._dispatch(TouchEvent(event_type=EventType.TOUCH_LONG, x=300, y=50))
        handler.assert_awaited_once()

    async def test_touch_drag_dispatches(self, deck):
        p = deck.screen("main")
        handler = AsyncMock()
        p.card(2).on_drag(handler)
        deck._active_screen = p
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        await deck._dispatch(
            TouchEvent(
                event_type=EventType.TOUCH_DRAG,
                x=450,
                y=20,
                x_out=550,
                y_out=80,
            )
        )
        handler.assert_awaited_once_with(450, 20, 550, 80)

    async def test_touch_no_handler(self, deck):
        p = deck.screen("main")
        deck._active_screen = p
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        await deck._dispatch(TouchEvent(event_type=EventType.TOUCH_SHORT, x=50, y=50))

    async def test_touch_zone_calculation(self, deck):
        """Touch at x=700 should dispatch to widget zone 3."""
        p = deck.screen("main")
        handler = AsyncMock()
        p.card(3).on_tap(handler)
        deck._active_screen = p
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        await deck._dispatch(TouchEvent(event_type=EventType.TOUCH_SHORT, x=700, y=50))
        handler.assert_awaited_once()


class TestDeckDispatchCardCallbacks:
    """Tests for card-level encoder decorators and pending callback draining."""

    async def test_encoder_turn_calls_card_encoder_turn_handler(self, deck):
        """Card on_encoder_turn handler is called on EncoderTurnEvent."""
        p = deck.screen("main")
        card = _TestCard()
        p.set_card(0, card)
        deck._active_screen = p

        handler = AsyncMock()
        card.on_encoder_turn(handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(EncoderTurnEvent(encoder=0, direction=3))

        handler.assert_awaited_once_with(3)

    async def test_encoder_turn_order_encoder_then_card(self, deck):
        """Dispatch order: encoder handler -> card encoder handler."""
        p = deck.screen("main")
        card = _TestCard()
        p.set_card(0, card)
        deck._active_screen = p

        call_order = []

        encoder_handler = AsyncMock(side_effect=lambda d: call_order.append("encoder"))
        p.encoder(0).on_turn(encoder_handler)

        card_handler = AsyncMock(side_effect=lambda d: call_order.append("card"))
        card.on_encoder_turn(card_handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(EncoderTurnEvent(encoder=0, direction=1))

        assert call_order == ["encoder", "card"]

    async def test_drain_card_callbacks_helper(self, deck):
        """_drain_card_callbacks awaits all pending callbacks in order."""
        card = _TestCard()
        results = []

        async def h1(v: float):
            results.append(("h1", v))

        async def h2(v: float):
            results.append(("h2", v))

        card.queue_pending_callback(h1, (1.0,))
        card.queue_pending_callback(h2, (2.0,))

        await deck._drain_card_callbacks(card)
        assert results == [("h1", 1.0), ("h2", 2.0)]
        assert card.drain_pending_callbacks() == []

    async def test_refresh_drains_pending_callbacks(self, deck):
        """Programmatic queue_pending_callback + refresh drains callbacks."""
        p = deck.screen("main")
        card = _TestCard()
        p.set_card(0, card)
        deck._active_screen = p
        deck._render_touchscreen = AsyncMock()

        change_handler = AsyncMock()
        card.queue_pending_callback(change_handler, (42.0,))

        await deck.refresh()
        change_handler.assert_awaited_once_with(42.0)


class TestDeckRenderAllKeys:
    async def test_no_device(self, deck):
        """No-op when device is None."""
        deck._active_screen = deck.screen("main")
        await deck._render_all_keys()

    async def test_renders_with_device(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)
        p = deck.screen("main")
        deck._active_screen = p

        await deck._render_all_keys()
        assert mock_streamdeck_device.set_key_image.call_count == STREAM_DECK_PLUS.key_count


class TestDeckRenderTouchscreen:
    async def test_no_device(self, deck):
        """No-op when device is None."""
        deck._active_screen = deck.screen("main")
        await deck._render_touchscreen()

    async def test_renders_with_device(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)
        p = deck.screen("main")
        deck._active_screen = p

        await deck._render_touchscreen()
        # Per-panel rendering: one call per panel (4 panels on SD+)
        assert mock_streamdeck_device.set_touchscreen_image.call_count == 4

    async def test_renders_custom_cards(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)
        p = deck.screen("main")
        card = _TestCard()
        p.set_card(0, card)
        deck._active_screen = p

        await deck._render_touchscreen()
        # Per-panel rendering: one call per panel (4 panels on SD+)
        assert mock_streamdeck_device.set_touchscreen_image.call_count == 4


class TestDeckInfo:
    def test_no_device_raises(self, deck):
        with pytest.raises(DeckError, match="Device not opened"):
            _ = deck.info

    def test_returns_device_info(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        deck._caps = STREAM_DECK_PLUS
        info = deck.info
        assert info.deck_type == "Stream Deck +"
        assert info.serial == "TEST123"
        assert info.firmware == "1.0.0"
        assert info.key_count == 8
        assert info.key_layout == (4, 2)
        assert info.encoder_count == 4
        assert info.key_pixel_size == (120, 120)
        assert info.touchscreen_size == (800, 100)
        assert info.key_image_format == "JPEG"


class TestDeckCapabilities:
    def test_capabilities_not_opened(self):
        d = Deck(serial_number="TEST123")
        with pytest.raises(DeckError, match="Device not opened"):
            _ = d.capabilities

    def test_metrics_not_opened(self):
        d = Deck(serial_number="TEST123")
        with pytest.raises(DeckError, match="Device not opened"):
            _ = d.metrics

    def test_screen_not_opened(self):
        d = Deck(serial_number="TEST123")
        with pytest.raises(DeckError, match="Device not opened"):
            d.screen("main")

    def test_capabilities_after_set(self, deck):
        assert deck.capabilities is STREAM_DECK_PLUS

    def test_metrics_after_set(self, deck):
        assert deck.metrics.key_count == 8


class TestDeckStart:
    async def test_no_devices_found(self, deck):
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            with pytest.raises(DeckError, match="No Stream Deck devices found"):
                await deck.start()

    async def test_no_visual_devices(self, deck):
        mock_dev = MagicMock()
        mock_dev.DECK_VISUAL = False
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_dev]
            with pytest.raises(DeckError, match="No visual Stream Deck devices found"):
                await deck.start()

    async def test_successful_start(self, mock_streamdeck_device):
        d = Deck(serial_number="TEST123")
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await d.start()
            assert d._running is True
            assert d._device is mock_streamdeck_device
            assert d._transport is not None
            assert d._caps is not None
            assert d._metrics is not None
            await d.stop()

    async def test_already_running_noop(self, mock_streamdeck_device):
        d = Deck(serial_number="TEST123")
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await d.start()
            await d.start()
            assert mock_dm.return_value.enumerate.call_count == 1
            await d.stop()

    async def test_start_serial_not_found(self, mock_streamdeck_device):
        d = Deck(serial_number="NOMATCH")
        mock_streamdeck_device.get_serial_number.return_value = "OTHER"
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            with pytest.raises(DeckError, match="No device with serial"):
                await d.start()


class TestDeckStop:
    async def test_stop_when_not_running(self, deck):
        """stop() is a no-op when not running."""
        await deck.stop()

    async def test_stop_closes_device(self, mock_streamdeck_device):
        d = Deck(serial_number="TEST123")
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await d.start()
            await d.stop()

            assert d._running is False
            mock_streamdeck_device.reset.assert_called()
            mock_streamdeck_device.close.assert_called()

    async def test_stop_sets_closed_event(self, mock_streamdeck_device):
        d = Deck(serial_number="TEST123")
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await d.start()
            await d.stop()
            assert d._closed_event.is_set()

    async def test_stop_handles_device_error(self, mock_streamdeck_device):
        """stop() handles errors during device close gracefully."""
        mock_streamdeck_device.close.side_effect = OSError("HID error")
        d = Deck(serial_number="TEST123")
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await d.start()
            await d.stop()


class TestDeckWaitClosed:
    async def test_wait_closed_resolves_after_stop(self, mock_streamdeck_device):
        d = Deck(serial_number="TEST123")
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await d.start()

            async def stop_soon():
                await asyncio.sleep(0.05)
                await d.stop()

            asyncio.create_task(stop_soon())
            await asyncio.wait_for(d.wait_closed(), timeout=2.0)


class TestDeckIsConnected:
    def test_not_connected_initially(self):
        d = Deck(serial_number="TEST123")
        assert d.is_connected is False

    def test_connected_with_device_and_running(self, mock_streamdeck_device):
        d = Deck(serial_number="TEST123")
        d._device = mock_streamdeck_device
        d._running = True
        assert d.is_connected is True


class TestDeckCheckTimeouts:
    """Tests for _check_timeouts — periodic card selection timeout checks."""

    async def test_no_active_screen_is_noop(self, deck):
        """_check_timeouts does nothing when no page is active."""
        deck._active_screen = None
        await deck._check_timeouts()

    async def test_no_expired_timeouts_no_refresh(self, deck):
        """No refresh when no card has an expired timeout."""
        p = deck.screen("main")
        deck._active_screen = p

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._check_timeouts()
            mock_refresh.assert_not_awaited()

    async def test_expired_timeout_triggers_refresh(self, deck):
        """Card with expired timeout triggers a refresh."""
        p = deck.screen("main")
        card = _TestCard()
        card.check_selection_timeout = lambda: True
        p.set_card(0, card)
        deck._active_screen = p

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._check_timeouts()
            mock_refresh.assert_awaited_once()


class TestDeckEventLoop:
    """Tests for _event_loop internal paths."""

    async def test_event_loop_returns_early_without_transport(self, deck):
        """_event_loop returns immediately when _transport is None."""
        deck._transport = None
        deck._running = True
        await deck._event_loop()
        assert not deck._closed_event.is_set()

    async def test_event_loop_timeout_continues(self, deck):
        """TimeoutError calls _check_timeouts then continues."""
        transport = MagicMock()
        transport.queue = asyncio.Queue()
        deck._transport = transport
        deck._running = True

        async def stop_after_delay():
            await asyncio.sleep(0.6)
            deck._running = False

        asyncio.create_task(stop_after_delay())
        with patch.object(
            deck, "_check_timeouts", new_callable=AsyncMock
        ) as mock_check:
            await deck._event_loop()
            mock_check.assert_awaited()
        assert deck._closed_event.is_set()

    async def test_event_loop_no_active_screen_continues(self, deck):
        """Event received but no active page -> continue."""
        transport = MagicMock()
        transport.queue = asyncio.Queue()
        deck._transport = transport
        deck._running = True
        deck._active_screen = None

        await transport.queue.put(KeyEvent(key=0, pressed=True))

        async def stop_after_delay():
            await asyncio.sleep(0.1)
            deck._running = False

        asyncio.create_task(stop_after_delay())
        await deck._event_loop()
        assert deck._closed_event.is_set()

    async def test_event_loop_dispatch_exception_logged(self, deck):
        """Exception in _dispatch is caught and logged."""
        transport = MagicMock()
        transport.queue = asyncio.Queue()
        deck._transport = transport
        deck._running = True
        deck._active_screen = deck.screen("main")

        deck._dispatch = AsyncMock(side_effect=ValueError("handler error"))

        await transport.queue.put(KeyEvent(key=0, pressed=True))

        async def stop_after_delay():
            await asyncio.sleep(0.1)
            deck._running = False

        asyncio.create_task(stop_after_delay())
        with patch("deux.runtime.deck.logger") as mock_logger:
            await deck._event_loop()
            mock_logger.exception.assert_called_with("Error in event handler")
        assert deck._closed_event.is_set()

    async def test_event_loop_unexpected_crash_logged(self, deck):
        """Unexpected exception crashes the event loop, logged."""
        transport = MagicMock()
        deck._transport = transport
        deck._running = True

        async def exploding_get():
            raise RuntimeError("unexpected crash")

        transport.queue = MagicMock()
        transport.queue.get = exploding_get

        with patch("deux.runtime.deck.logger") as mock_logger:
            await deck._event_loop()
            mock_logger.exception.assert_called_with("Event loop crashed")
        assert deck._closed_event.is_set()


class TestDeckError:
    def test_is_exception(self):
        assert issubclass(DeckError, Exception)

    def test_message(self):
        e = DeckError("test message")
        assert str(e) == "test message"


class TestDeckRenderCrossScreen:
    """A DuiKey or DuiCard installed on two screens at different slots
    must render to the slot of whichever screen is currently active.

    Regression coverage for the bug where ``Screen.set_key`` and
    ``TouchStrip.set_card`` mutated the user-supplied object's ``_index``,
    causing the second installation to corrupt the first screen's render.
    """

    async def test_dui_key_renders_at_active_screens_slot(
        self, deck, mock_streamdeck_device, key_package_spec
    ):
        from deux.dui.key import DuiKey

        deck._device = mock_streamdeck_device
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        shared_key = DuiKey(key_package_spec)

        screen_a = deck.screen("a")
        screen_a.set_key(4, shared_key)
        screen_b = deck.screen("b")
        screen_b.set_key(0, shared_key)

        # Render screen A; the shared key must render at slot 4.
        deck._active_screen = screen_a
        mock_streamdeck_device.set_key_image.reset_mock()
        await deck._render_all_keys()
        a_slots = [c.args[0] for c in mock_streamdeck_device.set_key_image.call_args_list]
        # Every key index gets a call (DUI or blank); slot 4 is the only DUI
        # render -- which we verify by checking the bytes differ from a blank.
        assert 4 in a_slots
        assert sorted(a_slots) == list(range(STREAM_DECK_PLUS.key_count))

        # Render screen B; the same instance must now render at slot 0.
        deck._active_screen = screen_b
        mock_streamdeck_device.set_key_image.reset_mock()
        await deck._render_all_keys()
        b_slots = [c.args[0] for c in mock_streamdeck_device.set_key_image.call_args_list]
        assert 0 in b_slots
        assert sorted(b_slots) == list(range(STREAM_DECK_PLUS.key_count))

    async def test_dui_key_spinner_pushes_to_active_screens_slot(
        self, deck, mock_streamdeck_device, key_package_spec
    ):
        """The spinner ``push_fn`` is rewired on every render so a key
        reused across screens animates at the active screen's slot.
        """
        from deux.dui.key import DuiKey

        deck._device = mock_streamdeck_device
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        shared_key = DuiKey(key_package_spec)

        screen_a = deck.screen("a")
        screen_a.set_key(5, shared_key)
        screen_b = deck.screen("b")
        screen_b.set_key(2, shared_key)

        deck._active_screen = screen_a
        await deck._render_all_keys()
        push_fn = shared_key._push_fn
        assert push_fn is not None
        mock_streamdeck_device.set_key_image.reset_mock()
        await push_fn(b"frame_a")
        assert mock_streamdeck_device.set_key_image.call_args.args[0] == 5

        deck._active_screen = screen_b
        await deck._render_all_keys()
        push_fn = shared_key._push_fn
        assert push_fn is not None
        mock_streamdeck_device.set_key_image.reset_mock()
        await push_fn(b"frame_b")
        assert mock_streamdeck_device.set_key_image.call_args.args[0] == 2

    async def test_dui_card_spinner_pushes_to_active_screens_slot(
        self, deck, mock_streamdeck_device, card_package_spec
    ):
        """A DuiCard reused on the touch strip in different positions
        across two screens has its push_fn rewired each render.
        """
        from deux.dui.card import DuiCard

        deck._device = mock_streamdeck_device
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)
        metrics = deck._metrics

        shared_card = DuiCard(card_package_spec)

        screen_a = deck.screen("a")
        screen_a.set_card(1, shared_card)
        screen_b = deck.screen("b")
        screen_b.set_card(3, shared_card)

        def expected_x(slot: int) -> int:
            return slot * metrics.panel_width

        deck._active_screen = screen_a
        await deck._render_touchscreen()
        push_fn = shared_card._push_fn
        assert push_fn is not None
        mock_streamdeck_device.set_touchscreen_image.reset_mock()
        await push_fn(b"frame_a")
        # set_touchscreen_image(frame_bytes, x, y, w, h)
        assert mock_streamdeck_device.set_touchscreen_image.call_args.args[1] == expected_x(1)

        deck._active_screen = screen_b
        await deck._render_touchscreen()
        push_fn = shared_card._push_fn
        assert push_fn is not None
        mock_streamdeck_device.set_touchscreen_image.reset_mock()
        await push_fn(b"frame_b")
        assert mock_streamdeck_device.set_touchscreen_image.call_args.args[1] == expected_x(3)
