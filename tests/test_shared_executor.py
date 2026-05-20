"""Tests for the shared executor module (issue #190).

Verifies that a single shared executor is used across Deck, DeckManager,
and discovery, and that shutdown uses ``wait=True`` for clean termination.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from deux.runtime._executor import get_executor, shutdown_executor
from deux.runtime.deck import Deck
from deux.runtime.hid.protocol import ImageRotation
from deux.runtime.manager import DeckManager


class TestSharedExecutor:
    """Shared executor singleton behaviour."""

    def test_get_executor_returns_same_instance(self):
        """Consecutive calls return the same pool."""
        shutdown_executor(wait=True)
        a = get_executor()
        b = get_executor()
        assert a is b
        shutdown_executor(wait=True)

    def test_get_executor_recreates_after_shutdown(self):
        """A new pool is created after shutdown."""
        shutdown_executor(wait=True)
        a = get_executor()
        shutdown_executor(wait=True)
        b = get_executor()
        assert a is not b
        shutdown_executor(wait=True)

    def test_shutdown_executor_is_idempotent(self):
        """Calling shutdown when already shut down does not raise."""
        shutdown_executor(wait=True)
        shutdown_executor(wait=True)


class TestDeckUsesSharedExecutor:
    """Deck no longer creates its own ThreadPoolExecutor."""

    def test_deck_has_no_private_executor(self):
        """Deck instances must not carry a per-instance ``_executor``."""
        d = Deck(serial_number="TEST")
        assert not hasattr(d, "_executor")

    async def test_deck_stop_calls_shutdown_wait_true(self, mock_streamdeck_device):
        """stop() shuts down the shared executor with wait=True."""
        d = Deck(serial_number="TEST123")
        with patch("deux.runtime.deck.enumerate_devices") as mock_enum:
            mock_enum.return_value = [mock_streamdeck_device]
            await d.start()

        with patch("deux.runtime.deck.shutdown_executor") as mock_shutdown:
            await d.stop()
            mock_shutdown.assert_called_once_with(wait=True)


class TestDeckManagerUsesSharedExecutor:
    """DeckManager no longer creates its own ThreadPoolExecutor."""

    def test_manager_has_no_private_executor(self):
        """DeckManager instances must not carry a per-instance ``_executor``."""
        m = DeckManager()
        assert not hasattr(m, "_executor")

    async def test_manager_stop_calls_shutdown_wait_true(self):
        """stop() shuts down the shared executor with wait=True."""
        m = DeckManager(poll_interval=0.05)

        with patch("deux.runtime.manager.enumerate_devices") as mock_enum:
            mock_enum.return_value = []
            await m.start()

        with patch("deux.runtime.manager.shutdown_executor") as mock_shutdown:
            await m.stop()
            mock_shutdown.assert_called_once_with(wait=True)


class TestMultiDeckThreadLeak:
    """Verify no thread leak when multiple decks are started and stopped."""

    async def test_no_thread_leak_on_multi_deck_stop(self, mock_streamdeck_device):
        """Starting and stopping 4 decks must not leak worker threads.

        Before the fix each Deck created its own 2-worker pool, leaving
        abandoned threads on ``stop()``.  Now they all share one pool
        which is cleanly shut down with ``wait=True``.
        """
        baseline = threading.active_count()

        decks: list[Deck] = []
        for i in range(4):
            dev = MagicMock()
            serial = f"LEAK_TEST_{i}"
            dev.family = "Stream Deck +"
            dev.serial_number = serial
            dev.firmware_version = "1.0.0"
            dev.key_count = 8
            dev.key_layout = (4, 2)
            dev.encoder_count = 4
            dev.key_size = (120, 120)
            dev.window_size = (800, 100)
            dev.lcd_size = (800, 480)
            dev.has_touch = True
            dev.has_window = True
            dev.sensor_count = 0
            dev.vendor_id = 0x0FD9
            dev.product_id = 0x0084
            dev.rotation = ImageRotation.NONE
            dev.path = f"/dev/hid/{serial}".encode()
            dev.is_open = False

            d = Deck(serial_number=serial)
            with patch("deux.runtime.deck.enumerate_devices") as dm:
                dm.return_value = [dev]
                await d.start()
            decks.append(d)

        for d in decks:
            await d.stop()

        after = threading.active_count()
        # After stopping all decks the thread count must not exceed
        # the baseline (tolerance of 1 for asyncio internal threads).
        assert after <= baseline + 1, (
            f"Thread leak detected: {after - baseline} extra threads after stopping 4 decks"
        )
