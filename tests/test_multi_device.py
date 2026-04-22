"""Tests for multi-device and reconnect features in deckboard.runtime.deck."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deckboard.runtime.deck import Deck, DeckError
from deckboard.runtime.capabilities import STREAM_DECK_PLUS


def _make_mock_device(
    deck_type: str = "Stream Deck +",
    serial: str = "TEST123",
    visual: bool = True,
) -> MagicMock:
    """Create a mock device matching STREAM_DECK_PLUS defaults."""
    device = MagicMock()
    device.DECK_TYPE = deck_type
    device.DECK_VISUAL = visual
    device.DECK_TOUCH = True
    device.KEY_PIXEL_WIDTH = 120
    device.KEY_PIXEL_HEIGHT = 120
    device.KEY_IMAGE_FORMAT = "JPEG"
    device.KEY_FLIP = [False, False]
    device.KEY_ROTATION = 0
    device.TOUCHSCREEN_PIXEL_WIDTH = 800
    device.TOUCHSCREEN_PIXEL_HEIGHT = 100
    device.TOUCHSCREEN_IMAGE_FORMAT = "JPEG"
    device.TOUCHSCREEN_FLIP = [False, False]
    device.TOUCHSCREEN_ROTATION = 0
    device.SCREEN_PIXEL_WIDTH = 0
    device.SCREEN_PIXEL_HEIGHT = 0
    device.SCREEN_IMAGE_FORMAT = ""
    device.SCREEN_FLIP = [False, False]
    device.SCREEN_ROTATION = 0
    device.TOUCH_KEY_COUNT = 0

    device.deck_type.return_value = deck_type
    device.get_serial_number.return_value = serial
    device.get_firmware_version.return_value = "1.0.0"
    device.key_count.return_value = 8
    device.key_layout.return_value = (4, 2)
    device.dial_count.return_value = 4

    device.open.return_value = None
    device.close.return_value = None
    device.reset.return_value = None
    device.set_brightness.return_value = None
    device.set_key_image.return_value = None
    device.set_touchscreen_image.return_value = None
    device.set_screen_image.return_value = None
    device.set_key_callback.return_value = None
    device.set_dial_callback.return_value = None
    device.set_touchscreen_callback.return_value = None
    return device


# ── Deck constructor new params ─────────────────────────────────────────


class TestDeckNewParams:
    def test_deck_type_default(self):
        d = Deck()
        assert d._deck_type is None

    def test_deck_type_set(self):
        d = Deck(deck_type="Stream Deck +")
        assert d._deck_type == "Stream Deck +"

    def test_auto_reconnect_default(self):
        d = Deck()
        assert d._auto_reconnect is False

    def test_auto_reconnect_set(self):
        d = Deck(auto_reconnect=True)
        assert d._auto_reconnect is True

    def test_reconnect_poll_interval_default(self):
        d = Deck()
        assert d._reconnect_poll_interval == 2.0

    def test_reconnect_poll_interval_set(self):
        d = Deck(reconnect_poll_interval=5.0)
        assert d._reconnect_poll_interval == 5.0


# ── Deck.is_connected / is_reconnecting ─────────────────────────────────


class TestDeckConnectionState:
    def test_not_connected_initially(self):
        d = Deck()
        assert d.is_connected is False
        assert d.is_reconnecting is False

    def test_connected_after_start(self, mock_streamdeck_device):
        d = Deck()
        d._device = mock_streamdeck_device
        d._running = True
        d._reconnecting = False
        assert d.is_connected is True

    def test_not_connected_during_reconnect(self, mock_streamdeck_device):
        d = Deck()
        d._device = mock_streamdeck_device
        d._running = True
        d._reconnecting = True
        assert d.is_connected is False
        assert d.is_reconnecting is True


# ── Deck type filter on start ───────────────────────────────────────────


class TestDeckTypeFilter:
    async def test_start_filters_by_deck_type(self):
        d = Deck(deck_type="Stream Deck +")
        plus = _make_mock_device(deck_type="Stream Deck +", serial="PLUS1")
        mini = _make_mock_device(deck_type="Stream Deck Mini", serial="MINI1")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [plus, mini]
            await d.start()
            assert d._device is plus
            await d.stop()

    async def test_start_no_matching_type_raises(self):
        d = Deck(deck_type="Stream Deck XL")
        plus = _make_mock_device(deck_type="Stream Deck +")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [plus]
            with pytest.raises(DeckError, match="No devices of type"):
                await d.start()

    async def test_start_remembers_serial(self):
        """After start(), serial_number is stored for reconnect."""
        d = Deck()
        dev = _make_mock_device(serial="AUTO_SERIAL")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            await d.start()
            assert d._serial_number == "AUTO_SERIAL"
            await d.stop()


# ── on_reconnect / on_disconnect decorators ─────────────────────────────


class TestDeckReconnectDisconnectHandlers:
    def test_on_reconnect_decorator(self):
        d = Deck()

        @d.on_reconnect
        async def handler():
            pass

        assert d._on_reconnect_handler is handler

    def test_on_disconnect_decorator(self):
        d = Deck()

        @d.on_disconnect
        async def handler():
            pass

        assert d._on_disconnect_handler is handler


# ── Deck._handle_disconnect ─────────────────────────────────────────────


class TestDeckHandleDisconnect:
    async def test_handle_disconnect_calls_handler(self):
        d = Deck(auto_reconnect=True, reconnect_poll_interval=0.1)
        d._running = True
        d._serial_number = "TEST123"
        d._device = _make_mock_device()
        d._transport = MagicMock()

        disconnect_called = asyncio.Event()

        @d.on_disconnect
        async def on_disc():
            disconnect_called.set()

        # Make reconnect loop fail immediately by stopping
        async def stop_soon():
            await asyncio.sleep(0.05)
            d._running = False

        asyncio.create_task(stop_soon())
        await d._handle_disconnect()
        assert disconnect_called.is_set()

    async def test_handle_disconnect_cleans_transport(self):
        d = Deck(auto_reconnect=True, reconnect_poll_interval=0.1)
        d._running = True
        d._serial_number = "TEST123"
        d._device = _make_mock_device()
        transport = MagicMock()
        d._transport = transport

        async def stop_soon():
            await asyncio.sleep(0.05)
            d._running = False

        asyncio.create_task(stop_soon())
        await d._handle_disconnect()
        transport.stop.assert_called_once()
        assert d._transport is None


# ── Deck._reconnect_loop ────────────────────────────────────────────────


class TestDeckReconnectLoop:
    async def test_reconnect_finds_device(self):
        d = Deck(auto_reconnect=True, reconnect_poll_interval=0.05)
        d._running = True
        d._serial_number = "RECON1"
        d._executor.__class__ = type(d._executor)  # keep executor alive

        dev = _make_mock_device(serial="RECON1")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            await d._reconnect_loop()

        assert d._device is dev
        assert d._reconnecting is False
        # Clean up
        d._running = False
        if d._transport:
            d._transport.stop()

    async def test_reconnect_exits_when_stopped(self):
        d = Deck(auto_reconnect=True, reconnect_poll_interval=0.05)
        d._running = True
        d._serial_number = "GONE"

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []

            async def stop_soon():
                await asyncio.sleep(0.1)
                d._running = False

            asyncio.create_task(stop_soon())
            await d._reconnect_loop()

        assert d._reconnecting is False

    async def test_reconnect_calls_reconnect_handler(self):
        d = Deck(auto_reconnect=True, reconnect_poll_interval=0.05)
        d._running = True
        d._serial_number = "RECON2"

        reconnect_called = asyncio.Event()

        @d.on_reconnect
        async def on_recon():
            reconnect_called.set()

        dev = _make_mock_device(serial="RECON2")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            await d._reconnect_loop()

        assert reconnect_called.is_set()
        d._running = False
        if d._transport:
            d._transport.stop()

    async def test_reconnect_re_renders_active_screen(self):
        d = Deck(auto_reconnect=True, reconnect_poll_interval=0.05)
        d._running = True
        d._serial_number = "RECON3"

        # Set up an active screen
        screen = d.screen("main")
        d._active_screen = screen
        d._active_page = screen

        dev = _make_mock_device(serial="RECON3")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            with patch.object(
                d, "_render_all_keys", new_callable=AsyncMock
            ) as mock_render:
                with patch.object(
                    d, "_render_touchscreen", new_callable=AsyncMock
                ):
                    await d._reconnect_loop()
                    mock_render.assert_awaited_once()

        d._running = False
        if d._transport:
            d._transport.stop()


# ── Deck.wait_for_device ────────────────────────────────────────────────


class TestDeckWaitForDevice:
    async def test_wait_for_device_immediate(self):
        dev = _make_mock_device(serial="WAIT1")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            deck = await Deck.wait_for_device(poll_interval=0.05)
            assert deck._device is dev
            assert deck._running is True
            await deck.stop()

    async def test_wait_for_device_retries(self):
        dev = _make_mock_device(serial="WAIT2")
        call_count = 0

        def enumerate_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return []
            return [dev]

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.side_effect = enumerate_side_effect
            deck = await asyncio.wait_for(
                Deck.wait_for_device(poll_interval=0.05), timeout=5.0
            )
            assert deck._device is dev
            assert call_count >= 3
            await deck.stop()

    async def test_wait_for_device_with_serial(self):
        dev = _make_mock_device(serial="SPECIFIC")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            deck = await Deck.wait_for_device(
                serial_number="SPECIFIC", poll_interval=0.05
            )
            assert deck._serial_number == "SPECIFIC"
            await deck.stop()

    async def test_wait_for_device_with_deck_type(self):
        dev = _make_mock_device(deck_type="Stream Deck +", serial="TYPED")

        with patch("deckboard.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            deck = await Deck.wait_for_device(
                deck_type="Stream Deck +", poll_interval=0.05
            )
            assert deck._deck_type == "Stream Deck +"
            await deck.stop()


# ── Event loop auto-reconnect trigger ────────────────────────────────────


class TestEventLoopAutoReconnect:
    async def test_event_loop_crash_triggers_reconnect(self):
        """When auto_reconnect is True and event loop crashes, _handle_disconnect is called."""
        d = Deck(auto_reconnect=True, reconnect_poll_interval=0.05)
        d._running = True
        d._serial_number = "CRASH1"

        transport = MagicMock()
        q = MagicMock()

        async def exploding_get():
            raise RuntimeError("HID disconnected")

        q.get = exploding_get
        transport.queue = q
        d._transport = transport

        with patch.object(
            d, "_handle_disconnect", new_callable=AsyncMock
        ) as mock_handle:
            await d._event_loop()
            mock_handle.assert_awaited_once()

    async def test_event_loop_crash_without_reconnect_sets_closed(self):
        """Without auto_reconnect, crash sets closed_event normally."""
        d = Deck(auto_reconnect=False)
        d._running = True

        transport = MagicMock()
        q = MagicMock()

        async def exploding_get():
            raise RuntimeError("HID disconnected")

        q.get = exploding_get
        transport.queue = q
        d._transport = transport

        await d._event_loop()
        assert d._closed_event.is_set()
