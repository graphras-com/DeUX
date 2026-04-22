"""Tests for deckboard.runtime.manager — DeckManager class."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deckboard.runtime.manager import DeckManager


def _make_raw_device(
    deck_type: str = "Stream Deck +",
    serial: str = "MGR_DEV1",
    visual: bool = True,
) -> MagicMock:
    """Create a mock raw device for enumeration."""
    d = MagicMock()
    d.DECK_TYPE = deck_type
    d.DECK_VISUAL = visual
    d.DECK_TOUCH = True
    d.KEY_PIXEL_WIDTH = 120
    d.KEY_PIXEL_HEIGHT = 120
    d.KEY_IMAGE_FORMAT = "JPEG"
    d.KEY_FLIP = [False, False]
    d.KEY_ROTATION = 0
    d.TOUCHSCREEN_PIXEL_WIDTH = 800
    d.TOUCHSCREEN_PIXEL_HEIGHT = 100
    d.TOUCHSCREEN_IMAGE_FORMAT = "JPEG"
    d.TOUCHSCREEN_FLIP = [False, False]
    d.TOUCHSCREEN_ROTATION = 0
    d.SCREEN_PIXEL_WIDTH = 0
    d.SCREEN_PIXEL_HEIGHT = 0
    d.SCREEN_IMAGE_FORMAT = ""
    d.SCREEN_FLIP = [False, False]
    d.SCREEN_ROTATION = 0
    d.TOUCH_KEY_COUNT = 0

    d.deck_type.return_value = deck_type
    d.get_serial_number.return_value = serial
    d.get_firmware_version.return_value = "1.0.0"
    d.key_count.return_value = 8
    d.key_layout.return_value = (4, 2)
    d.dial_count.return_value = 4

    d.id.return_value = f"/dev/hid/{serial}"
    d.open.return_value = None
    d.close.return_value = None
    d.reset.return_value = None
    d.set_brightness.return_value = None
    d.set_key_image.return_value = None
    d.set_touchscreen_image.return_value = None
    d.set_screen_image.return_value = None
    d.set_key_callback.return_value = None
    d.set_dial_callback.return_value = None
    d.set_touchscreen_callback.return_value = None
    return d


# ── DeckManager.__init__ ─────────────────────────────────────────────────


class TestDeckManagerInit:
    def test_defaults(self):
        m = DeckManager()
        assert m._poll_interval == 2.0
        assert m._brightness == 80
        assert m._auto_reconnect is True
        assert m._running is False
        assert m._decks == {}

    def test_custom_params(self):
        m = DeckManager(poll_interval=5.0, brightness=50, auto_reconnect=True)
        assert m._poll_interval == 5.0
        assert m._brightness == 50
        assert m._auto_reconnect is True


# ── DeckManager.on_connect / on_disconnect ───────────────────────────────


class TestDeckManagerHandlers:
    def test_on_connect_decorator(self):
        m = DeckManager()

        @m.on_connect(deck_type="Stream Deck +")
        async def handler(deck):
            pass

        assert len(m._connect_handlers) == 1
        filters, h = m._connect_handlers[0]
        assert filters["deck_type"] == "Stream Deck +"
        assert filters["serial"] is None
        assert h is handler

    def test_on_connect_serial_filter(self):
        m = DeckManager()

        @m.on_connect(serial="ABC123")
        async def handler(deck):
            pass

        filters, _ = m._connect_handlers[0]
        assert filters["serial"] == "ABC123"

    def test_on_disconnect_decorator(self):
        m = DeckManager()

        @m.on_disconnect
        async def handler(info):
            pass

        assert m._disconnect_handler is handler

    def test_multiple_connect_handlers(self):
        m = DeckManager()

        @m.on_connect(deck_type="Stream Deck +")
        async def plus_handler(deck):
            pass

        @m.on_connect(deck_type="Stream Deck Mini")
        async def mini_handler(deck):
            pass

        assert len(m._connect_handlers) == 2


# ── DeckManager lifecycle ────────────────────────────────────────────────


class TestDeckManagerLifecycle:
    async def test_start_stop(self):
        m = DeckManager(poll_interval=0.05)

        # Register a dummy handler so scan works
        @m.on_connect()
        async def handler(deck):
            pass

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            await m.start()
            assert m._running is True
            await asyncio.sleep(0.1)
            await m.stop()
            assert m._running is False
            assert m._closed_event.is_set()

    async def test_start_already_running(self):
        m = DeckManager(poll_interval=0.05)

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            await m.start()
            await m.start()  # no-op
            await m.stop()

    async def test_stop_when_not_running(self):
        m = DeckManager()
        await m.stop()  # no-op, should not raise

    async def test_context_manager(self):
        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            async with DeckManager(poll_interval=0.05) as m:
                assert m._running is True
            assert m._running is False


# ── DeckManager._scan_once ───────────────────────────────────────────────


class TestDeckManagerScanOnce:
    async def test_scan_detects_new_device(self):
        m = DeckManager(poll_interval=10.0)
        connected_decks = []

        @m.on_connect()
        async def handler(deck):
            connected_decks.append(deck)

        dev = _make_raw_device(serial="SCAN1")

        # Patch both the manager's enumeration and the Deck's enumeration
        with patch("deckboard.runtime.manager.DeviceManager") as mgr_dm:
            mgr_dm.return_value.enumerate.return_value = [dev]
            with patch("deckboard.runtime.deck.DeviceManager") as deck_dm:
                deck_dm.return_value.enumerate.return_value = [dev]
                await m._scan_once()

        assert len(connected_decks) == 1
        assert "SCAN1" in m._decks

        # Clean up
        for d in m._decks.values():
            await d.stop()

    async def test_scan_detects_disconnect(self):
        m = DeckManager(poll_interval=10.0)
        disconnected = []

        @m.on_disconnect
        async def handler(info):
            disconnected.append(info)

        # Pre-populate a managed deck
        mock_deck = MagicMock()
        mock_deck.stop = AsyncMock()
        mock_deck.info = MagicMock()
        mock_deck.info.serial = "GONE1"
        mock_deck.device_path = "/dev/hid/GONE1"
        m._decks["GONE1"] = mock_deck

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            await m._scan_once()

        assert "GONE1" not in m._decks
        assert len(disconnected) == 1
        mock_deck.stop.assert_awaited_once()

    async def test_scan_ignores_already_managed(self):
        m = DeckManager(poll_interval=10.0)
        connect_count = 0

        @m.on_connect()
        async def handler(deck):
            nonlocal connect_count
            connect_count += 1

        # Pre-populate
        mock_existing = MagicMock()
        mock_existing.device_path = "/dev/hid/EXISTING"
        m._decks["EXISTING"] = mock_existing

        dev = _make_raw_device(serial="EXISTING")

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            await m._scan_once()

        assert connect_count == 0

    async def test_scan_filters_by_deck_type(self):
        m = DeckManager(poll_interval=10.0)
        connected_types = []

        @m.on_connect(deck_type="Stream Deck +")
        async def plus_handler(deck):
            connected_types.append("plus")

        dev_mini = _make_raw_device(deck_type="Stream Deck Mini", serial="MINI1")

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev_mini]
            await m._scan_once()

        assert connected_types == []  # Mini doesn't match Plus filter

    async def test_scan_filters_by_serial(self):
        m = DeckManager(poll_interval=10.0)
        connected_serials = []

        @m.on_connect(serial="WANTED")
        async def handler(deck):
            connected_serials.append("WANTED")

        dev = _make_raw_device(serial="UNWANTED")

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            await m._scan_once()

        assert connected_serials == []

    async def test_scan_enumeration_failure(self):
        m = DeckManager(poll_interval=10.0)

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.side_effect = OSError("HID error")
            await m._scan_once()  # Should not raise

    async def test_scan_device_open_error_skipped(self):
        m = DeckManager(poll_interval=10.0)

        @m.on_connect()
        async def handler(deck):
            pass

        dev = _make_raw_device(serial="BAD_OPEN")
        dev.open.side_effect = OSError("HID error")

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [dev]
            await m._scan_once()

        assert m._decks == {}


# ── DeckManager.decks property ──────────────────────────────────────────


class TestDeckManagerDecks:
    def test_decks_returns_copy(self):
        m = DeckManager()
        m._decks["X"] = MagicMock()
        d = m.decks
        assert "X" in d
        # Modifying the copy should not affect internal state
        d.pop("X")
        assert "X" in m._decks


# ── DeckManager disconnect with info error ──────────────────────────────


class TestDeckManagerDisconnectInfoError:
    async def test_disconnect_info_error_fallback(self):
        """When deck.info raises, a fallback DeviceInfo is used."""
        m = DeckManager(poll_interval=10.0)
        disconnected = []

        @m.on_disconnect
        async def handler(info):
            disconnected.append(info)

        mock_deck = MagicMock()
        mock_deck.stop = AsyncMock()
        type(mock_deck).info = property(lambda self: (_ for _ in ()).throw(Exception("no device")))
        mock_deck.device_path = "/dev/hid/FALLBACK1"
        m._decks["FALLBACK1"] = mock_deck

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            await m._scan_once()

        assert len(disconnected) == 1
        assert disconnected[0].serial == "FALLBACK1"
        assert disconnected[0].deck_type == "unknown"


# ── DeckManager connect handler error ────────────────────────────────────


class TestDeckManagerConnectHandlerError:
    async def test_connect_handler_error_logged(self):
        """Error in connect handler is caught, doesn't crash manager."""
        m = DeckManager(poll_interval=10.0)

        @m.on_connect()
        async def handler(deck):
            raise ValueError("handler error")

        dev = _make_raw_device(serial="ERR1")

        with patch("deckboard.runtime.manager.DeviceManager") as mgr_dm:
            mgr_dm.return_value.enumerate.return_value = [dev]
            with patch("deckboard.runtime.deck.DeviceManager") as deck_dm:
                deck_dm.return_value.enumerate.return_value = [dev]
                await m._scan_once()

        # Deck was still added despite handler error
        assert "ERR1" in m._decks
        for d in m._decks.values():
            await d.stop()


# ── DeckManager reconnection scenarios ──────────────────────────────────


class TestDeckManagerReconnect:
    async def test_reconnect_calls_on_connect_again(self):
        """When a device disconnects and reappears, on_connect is called again."""
        m = DeckManager(poll_interval=10.0, auto_reconnect=True)
        connected_serials = []

        @m.on_connect()
        async def handler(deck):
            connected_serials.append(deck._serial_number)

        dev = _make_raw_device(serial="RECON1")

        # First scan: device appears
        with patch("deckboard.runtime.manager.DeviceManager") as mgr_dm:
            mgr_dm.return_value.enumerate.return_value = [dev]
            with patch("deckboard.runtime.deck.DeviceManager") as deck_dm:
                deck_dm.return_value.enumerate.return_value = [dev]
                await m._scan_once()

        assert connected_serials == ["RECON1"]

        # Second scan: device disappears
        with patch("deckboard.runtime.manager.DeviceManager") as mgr_dm:
            mgr_dm.return_value.enumerate.return_value = []
            await m._scan_once()

        assert "RECON1" not in m._decks

        # Third scan: device reappears — on_connect should be called again
        with patch("deckboard.runtime.manager.DeviceManager") as mgr_dm:
            mgr_dm.return_value.enumerate.return_value = [dev]
            with patch("deckboard.runtime.deck.DeviceManager") as deck_dm:
                deck_dm.return_value.enumerate.return_value = [dev]
                await m._scan_once()

        assert connected_serials == ["RECON1", "RECON1"]
        assert "RECON1" in m._decks

        for d in m._decks.values():
            await d.stop()

    async def test_no_reconnect_when_disabled(self):
        """With auto_reconnect=False, disconnect handler fires but device stays gone."""
        m = DeckManager(poll_interval=10.0, auto_reconnect=False)
        disconnected = []

        @m.on_connect()
        async def handler(deck):
            pass

        @m.on_disconnect
        async def on_disc(info):
            disconnected.append(info.serial)

        dev = _make_raw_device(serial="NOREC1")

        # Scan 1: connect
        with patch("deckboard.runtime.manager.DeviceManager") as mgr_dm:
            mgr_dm.return_value.enumerate.return_value = [dev]
            with patch("deckboard.runtime.deck.DeviceManager") as deck_dm:
                deck_dm.return_value.enumerate.return_value = [dev]
                await m._scan_once()

        assert "NOREC1" in m._decks

        # Scan 2: disconnect
        with patch("deckboard.runtime.manager.DeviceManager") as mgr_dm:
            mgr_dm.return_value.enumerate.return_value = []
            await m._scan_once()

        assert disconnected == ["NOREC1"]
        assert "NOREC1" not in m._decks

    async def test_disconnect_handler_error_logged(self):
        """Error in disconnect handler is caught, doesn't crash manager."""
        m = DeckManager(poll_interval=10.0)

        @m.on_disconnect
        async def handler(info):
            raise ValueError("disconnect handler error")

        mock_deck = MagicMock()
        mock_deck.stop = AsyncMock()
        mock_deck.info = MagicMock()
        mock_deck.info.serial = "DISC_ERR"
        mock_deck.device_path = "/dev/hid/DISC_ERR"
        m._decks["DISC_ERR"] = mock_deck

        with patch("deckboard.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            await m._scan_once()  # Should not raise

        assert "DISC_ERR" not in m._decks
