"""Tests for the shared executor module (issue #190).

Verifies that a single shared executor is used across Deck, DeckManager,
and discovery, and that shutdown uses ``wait=True`` for clean termination.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from deux.runtime._executor import get_executor, shutdown_executor
from deux.runtime.deck import Deck
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
        with patch("deux.runtime.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
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

        with patch("deux.runtime.manager.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
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
            dev.DECK_VISUAL = True
            dev.DECK_TOUCH = True
            dev.DECK_TYPE = "Stream Deck +"
            dev.KEY_PIXEL_WIDTH = 120
            dev.KEY_PIXEL_HEIGHT = 120
            dev.KEY_IMAGE_FORMAT = "JPEG"
            dev.KEY_FLIP = [False, False]
            dev.KEY_ROTATION = 0
            dev.TOUCHSCREEN_PIXEL_WIDTH = 800
            dev.TOUCHSCREEN_PIXEL_HEIGHT = 100
            dev.TOUCHSCREEN_IMAGE_FORMAT = "JPEG"
            dev.TOUCHSCREEN_FLIP = [False, False]
            dev.TOUCHSCREEN_ROTATION = 0
            dev.SCREEN_PIXEL_WIDTH = 0
            dev.SCREEN_PIXEL_HEIGHT = 0
            dev.SCREEN_IMAGE_FORMAT = ""
            dev.SCREEN_FLIP = [False, False]
            dev.SCREEN_ROTATION = 0
            dev.TOUCH_KEY_COUNT = 0
            serial = f"LEAK_TEST_{i}"
            dev.get_serial_number.return_value = serial
            dev.get_firmware_version.return_value = "1.0.0"
            dev.deck_type.return_value = "Stream Deck +"
            dev.key_count.return_value = 8
            dev.key_layout.return_value = (4, 2)
            dev.dial_count.return_value = 4
            dev.id.return_value = f"/dev/hid/{serial}"

            d = Deck(serial_number=serial)
            with patch("deux.runtime.deck.DeviceManager") as dm:
                dm.return_value.enumerate.return_value = [dev]
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
