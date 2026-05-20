"""Tests for deux.runtime.manager — DeckManager class."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from deux.runtime.hid.protocol import ImageRotation
from deux.runtime.manager import DeckManager


def _make_raw_device(
    deck_type: str = "Stream Deck +",
    serial: str = "MGR_DEV1",
) -> MagicMock:
    """Create a mock HidDevice for enumeration.

    Parameters
    ----------
    deck_type : str
        Device family name.
    serial : str
        Device serial number.

    Returns
    -------
    MagicMock
        A mock matching the HidDevice interface.
    """
    d = MagicMock()
    d.family = deck_type
    d.serial_number = serial
    d.firmware_version = "1.0.0"
    d.key_count = 8
    d.key_layout = (4, 2)
    d.encoder_count = 4
    d.key_size = (120, 120)
    d.window_size = (800, 100)
    d.lcd_size = (800, 480)
    d.has_touch = True
    d.has_window = True
    d.sensor_count = 0
    d.vendor_id = 0x0FD9
    d.product_id = 0x0084
    d.rotation = ImageRotation.NONE
    d.path = f"/dev/hid/{serial}".encode()
    d.is_open = False

    d.open.return_value = None
    d.close.return_value = None
    d.show_logo.return_value = None
    d.set_brightness.return_value = None
    d.set_key_image.return_value = None
    d.set_partial_window_image.return_value = None
    return d


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

        assert handler in m._disconnect_handlers

    def test_multiple_connect_handlers(self):
        m = DeckManager()

        @m.on_connect(deck_type="Stream Deck +")
        async def plus_handler(deck):
            pass

        @m.on_connect(deck_type="Stream Deck Mini")
        async def mini_handler(deck):
            pass

        assert len(m._connect_handlers) == 2


class TestDeckManagerLifecycle:
    async def test_start_stop(self):
        m = DeckManager(poll_interval=0.05)

        @m.on_connect()
        async def handler(deck):
            pass

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = []
            await m.start()
            assert m._running is True
            await asyncio.sleep(0.1)
            await m.stop()
            assert m._running is False
            assert m._closed_event.is_set()

    async def test_start_already_running(self):
        m = DeckManager(poll_interval=0.05)

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = []
            await m.start()
            await m.start()
            await m.stop()

    async def test_stop_when_not_running(self):
        m = DeckManager()
        await m.stop()

    async def test_context_manager(self):
        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = []
            async with DeckManager(poll_interval=0.05) as m:
                assert m._running is True
            assert m._running is False


class TestDeckManagerScanOnce:
    async def test_scan_detects_new_device(self):
        m = DeckManager(poll_interval=10.0)
        connected_decks = []

        @m.on_connect()
        async def handler(deck):
            connected_decks.append(deck)

        dev = _make_raw_device(serial="SCAN1")

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = [dev]
            with patch("deux.runtime.deck.enumerate_devices") as deck_dm:
                deck_dm.return_value = [dev]
                await m._scan_once()

        assert len(connected_decks) == 1
        assert "SCAN1" in m._decks

        for d in m._decks.values():
            await d.stop()

    async def test_scan_detects_disconnect(self):
        m = DeckManager(poll_interval=10.0)
        disconnected = []

        @m.on_disconnect
        async def handler(info):
            disconnected.append(info)

        mock_deck = MagicMock()
        mock_deck.stop = AsyncMock()
        mock_deck.info = MagicMock()
        mock_deck.info.serial = "GONE1"
        mock_deck.device_path = "/dev/hid/GONE1"
        m._decks["GONE1"] = mock_deck

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = []
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

        mock_existing = MagicMock()
        mock_existing.device_path = "/dev/hid/EXISTING"
        m._decks["EXISTING"] = mock_existing

        dev = _make_raw_device(serial="EXISTING")

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = [dev]
            await m._scan_once()

        assert connect_count == 0

    async def test_scan_filters_by_deck_type(self):
        m = DeckManager(poll_interval=10.0)
        connected_types = []

        @m.on_connect(deck_type="Stream Deck +")
        async def plus_handler(deck):
            connected_types.append("plus")

        dev_mini = _make_raw_device(deck_type="Stream Deck Mini", serial="MINI1")

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = [dev_mini]
            await m._scan_once()

        assert connected_types == []

    async def test_scan_filters_by_serial(self):
        m = DeckManager(poll_interval=10.0)
        connected_serials = []

        @m.on_connect(serial="WANTED")
        async def handler(deck):
            connected_serials.append("WANTED")

        dev = _make_raw_device(serial="UNWANTED")

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = [dev]
            await m._scan_once()

        assert connected_serials == []

    async def test_scan_enumeration_failure(self):
        m = DeckManager(poll_interval=10.0)

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.side_effect = OSError("HID error")
            await m._scan_once()

    async def test_scan_device_open_error_skipped(self):
        m = DeckManager(poll_interval=10.0)

        @m.on_connect()
        async def handler(deck):
            pass

        dev = _make_raw_device(serial="BAD_OPEN")
        dev.open.side_effect = OSError("HID error")

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = [dev]
            await m._scan_once()

        assert m._decks == {}

    async def test_scan_device_open_error_logs_info_then_debug(self, caplog):
        """Permission / probe errors are logged at info (first) then debug (subsequent).

        Verifies acceptance criteria from issue #196: device probe failures
        are logged at ``info`` level for the first occurrence and ``debug``
        for subsequent ones, with exception info attached.
        """
        m = DeckManager(poll_interval=10.0)

        @m.on_connect()
        async def handler(deck):
            pass

        dev = _make_raw_device(serial="PERM_ERR")
        dev.open.side_effect = PermissionError("Permission denied")

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = [dev]

            # First scan — should log at INFO level
            with caplog.at_level(logging.DEBUG, logger="deux.runtime.manager"):
                caplog.clear()
                await m._scan_once()

            info_records = [
                r
                for r in caplog.records
                if r.levelno == logging.INFO and "Failed to probe new device" in r.message
            ]
            assert len(info_records) == 1
            assert info_records[0].exc_info is not None
            assert info_records[0].exc_info[0] is PermissionError

            # Second scan — same path, should log at DEBUG level
            with caplog.at_level(logging.DEBUG, logger="deux.runtime.manager"):
                caplog.clear()
                await m._scan_once()

            debug_records = [
                r
                for r in caplog.records
                if r.levelno == logging.DEBUG and "Failed to probe device" in r.message
            ]
            assert len(debug_records) == 1
            assert debug_records[0].exc_info is not None


class TestDeckManagerDecks:
    def test_decks_returns_copy(self):
        m = DeckManager()
        m._decks["X"] = MagicMock()
        d = m.decks
        assert "X" in d
        d.pop("X")
        assert "X" in m._decks


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

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = []
            await m._scan_once()

        assert len(disconnected) == 1
        assert disconnected[0].serial == "FALLBACK1"
        assert disconnected[0].deck_type == "unknown"


class TestDeckManagerConnectHandlerError:
    async def test_connect_handler_error_logged(self):
        """Error in connect handler is caught, doesn't crash manager."""
        m = DeckManager(poll_interval=10.0)

        @m.on_connect()
        async def handler(deck):
            raise ValueError("handler error")

        dev = _make_raw_device(serial="ERR1")

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = [dev]
            with patch("deux.runtime.deck.enumerate_devices") as deck_dm:
                deck_dm.return_value = [dev]
                await m._scan_once()

        assert "ERR1" in m._decks
        for d in m._decks.values():
            await d.stop()


class TestDeckManagerReconnect:
    async def test_reconnect_calls_on_connect_again(self):
        """When a device disconnects and reappears, on_connect is called again."""
        m = DeckManager(poll_interval=10.0, auto_reconnect=True)
        connected_serials = []

        @m.on_connect()
        async def handler(deck):
            connected_serials.append(deck._serial_number)

        dev = _make_raw_device(serial="RECON1")

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = [dev]
            with patch("deux.runtime.deck.enumerate_devices") as deck_dm:
                deck_dm.return_value = [dev]
                await m._scan_once()

        assert connected_serials == ["RECON1"]

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = []
            await m._scan_once()

        assert "RECON1" not in m._decks

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = [dev]
            with patch("deux.runtime.deck.enumerate_devices") as deck_dm:
                deck_dm.return_value = [dev]
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

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = [dev]
            with patch("deux.runtime.deck.enumerate_devices") as deck_dm:
                deck_dm.return_value = [dev]
                await m._scan_once()

        assert "NOREC1" in m._decks

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = []
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

        with patch("deux.runtime.manager.enumerate_devices") as mock_dm:
            mock_dm.return_value = []
            await m._scan_once()

        assert "DISC_ERR" not in m._decks


class TestPathSerialCache:
    """Tests for path-to-serial caching in _scan_once."""

    async def test_cache_avoids_repeated_open_close(self):
        """Second scan uses cached serial, no additional open/close for probe."""
        m = DeckManager(poll_interval=10.0)
        # No connect handler — device won't become managed, so we can
        # isolate the probe open/close behavior.

        dev = _make_raw_device(serial="CACHE1")

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = [dev]
            await m._scan_once()

        assert dev.open.call_count == 1
        assert dev.close.call_count == 1
        assert m._path_serial_cache["/dev/hid/CACHE1"] == "CACHE1"

        # Reset and scan again — should use cache, no open/close
        dev.open.reset_mock()
        dev.close.reset_mock()

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = [dev]
            await m._scan_once()

        assert dev.open.call_count == 0
        assert dev.close.call_count == 0

    async def test_cache_invalidated_on_disconnect(self):
        """Cache entry removed when device path disappears."""
        m = DeckManager(poll_interval=10.0)
        m._path_serial_cache["/dev/hid/GONE"] = "GONE_SERIAL"

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = []
            await m._scan_once()

        assert "/dev/hid/GONE" not in m._path_serial_cache

    async def test_cache_not_populated_on_probe_failure(self):
        """Failed probe does not add entry to cache."""
        m = DeckManager(poll_interval=10.0)

        dev = _make_raw_device(serial="FAIL1")
        dev.open.side_effect = OSError("USB busy")

        with patch("deux.runtime.manager.enumerate_devices") as mgr_dm:
            mgr_dm.return_value = [dev]
            await m._scan_once()

        assert "/dev/hid/FAIL1" not in m._path_serial_cache
