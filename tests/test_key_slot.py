"""Tests for deux.ui.controls.key_slot — KeySlot class."""

from __future__ import annotations

from unittest.mock import AsyncMock

from deux.ui.controls.key_slot import KeySlot


class TestKeySlotInit:
    def test_defaults(self, key_slot: KeySlot):
        assert key_slot.image_bytes is None
        assert key_slot.is_dirty is True
        assert key_slot._press_handler is None
        assert key_slot._release_handler is None


class TestKeySlotEventHandlers:
    def test_on_press_registers_handler(self, key_slot: KeySlot):
        async def handler():
            pass

        result = key_slot.on_press(handler)
        assert key_slot._press_handler is handler
        assert result is handler

    def test_on_release_registers_handler(self, key_slot: KeySlot):
        async def handler():
            pass

        result = key_slot.on_release(handler)
        assert key_slot._release_handler is handler
        assert result is handler

    def test_on_press_as_decorator(self, key_slot: KeySlot):
        @key_slot.on_press
        async def handler():
            pass

        assert key_slot._press_handler is handler

    def test_on_release_as_decorator(self, key_slot: KeySlot):
        @key_slot.on_release
        async def handler():
            pass

        assert key_slot._release_handler is handler


class TestKeySlotRefreshCallback:
    async def test_request_refresh_no_callback(self, key_slot: KeySlot):
        """request_refresh is a no-op when no callback is registered."""
        await key_slot.request_refresh()

    async def test_set_and_request_refresh(self, key_slot: KeySlot):
        """request_refresh awaits the registered callback."""
        cb = AsyncMock()
        key_slot.set_refresh_callback(cb)
        await key_slot.request_refresh()
        cb.assert_awaited_once()

    async def test_multiple_refresh_callbacks(self, key_slot: KeySlot):
        """Multiple callbacks are all invoked on request_refresh."""
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        key_slot.set_refresh_callback(cb1)
        key_slot.set_refresh_callback(cb2)
        await key_slot.request_refresh()
        cb1.assert_awaited_once()
        cb2.assert_awaited_once()

    async def test_duplicate_callback_not_added_twice(self, key_slot: KeySlot):
        """The same callback registered twice is only called once."""
        cb = AsyncMock()
        key_slot.set_refresh_callback(cb)
        key_slot.set_refresh_callback(cb)
        await key_slot.request_refresh()
        cb.assert_awaited_once()

    async def test_remove_refresh_callback(self, key_slot: KeySlot):
        """Removed callback is no longer invoked."""
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        key_slot.set_refresh_callback(cb1)
        key_slot.set_refresh_callback(cb2)
        key_slot.remove_refresh_callback(cb1)
        await key_slot.request_refresh()
        cb1.assert_not_awaited()
        cb2.assert_awaited_once()

    async def test_remove_nonexistent_callback_noop(self, key_slot: KeySlot):
        """Removing a callback that was never registered is a no-op."""
        key_slot.remove_refresh_callback(AsyncMock())


class TestKeySlotRendering:
    def test_set_rendered_image(self, key_slot: KeySlot):
        key_slot.set_rendered_image(b"jpeg-data")
        assert key_slot.image_bytes == b"jpeg-data"
        assert key_slot.is_dirty is False

    def test_mark_clean(self, key_slot: KeySlot):
        assert key_slot.is_dirty is True
        key_slot.mark_clean()
        assert key_slot.is_dirty is False

    def test_mark_dirty(self, key_slot: KeySlot):
        """mark_dirty re-flags a clean key for rendering."""
        key_slot.mark_clean()
        assert key_slot.is_dirty is False
        key_slot.mark_dirty()
        assert key_slot.is_dirty is True
