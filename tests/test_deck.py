"""Tests for deckboard.deck — Deck class."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deckboard.deck import Deck, DeckError, _KEY_COUNT
from deckboard.icon import IconManager
from deckboard.page import Page
from deckboard.types import (
    DialPressEvent,
    DialTurnEvent,
    EventType,
    KeyEvent,
    TouchEvent,
)


@pytest.fixture
def deck(tmp_path):
    """A Deck instance with a temporary icon cache."""
    return Deck(icon_cache_dir=tmp_path / "icons")


# ── Deck.__init__ ───────────────────────────────────────────────────────


class TestDeckInit:
    def test_defaults(self, deck):
        assert deck._device_type == "Stream Deck +"
        assert deck._device_index == 0
        assert deck._brightness == 80
        assert deck._device is None
        assert deck._transport is None
        assert deck._running is False
        assert deck._active_page is None
        assert deck._pages == {}

    def test_custom_params(self, tmp_path):
        d = Deck(
            device_type="Stream Deck Mini",
            device_index=1,
            brightness=50,
            icon_cache_dir=tmp_path / "custom",
        )
        assert d._device_type == "Stream Deck Mini"
        assert d._device_index == 1
        assert d._brightness == 50

    def test_has_icon_manager(self, deck):
        assert isinstance(deck.icons, IconManager)


# ── Deck.page ───────────────────────────────────────────────────────────


class TestDeckPage:
    def test_creates_page(self, deck):
        p = deck.page("main")
        assert isinstance(p, Page)
        assert p.name == "main"

    def test_same_instance(self, deck):
        a = deck.page("main")
        b = deck.page("main")
        assert a is b

    def test_different_pages(self, deck):
        a = deck.page("main")
        b = deck.page("settings")
        assert a is not b
        assert a.name == "main"
        assert b.name == "settings"


# ── Deck.brightness ─────────────────────────────────────────────────────


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


# ── Deck.set_page ───────────────────────────────────────────────────────


class TestDeckSetPage:
    async def test_nonexistent_page_raises(self, deck):
        with pytest.raises(DeckError, match="Page 'missing' does not exist"):
            await deck.set_page("missing")

    async def test_sets_active_page(self, deck):
        deck.page("main")
        # Patch rendering methods since no device
        deck._render_all_buttons = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        await deck.set_page("main")
        assert deck.active_page is not None
        assert deck.active_page.name == "main"

    async def test_calls_render(self, deck):
        deck.page("main")
        deck._render_all_buttons = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        await deck.set_page("main")
        deck._render_all_buttons.assert_awaited_once()
        deck._render_touchscreen.assert_awaited_once()


# ── Deck.active_page ────────────────────────────────────────────────────


class TestDeckActivePage:
    def test_initially_none(self, deck):
        assert deck.active_page is None


# ── Deck.refresh ────────────────────────────────────────────────────────


class TestDeckRefresh:
    async def test_no_active_page(self, deck):
        """refresh() is a no-op when no active page."""
        await deck.refresh()  # Should not raise

    async def test_renders_dirty_buttons(self, deck):
        p = deck.page("main")
        p.button(0).set_icon("mdi:home")

        deck._active_page = p
        deck._render_button = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        await deck.refresh()
        deck._render_button.assert_awaited_once()

    async def test_renders_dirty_touchscreen(self, deck):
        p = deck.page("main")
        p.widget(0).set_label("test")

        deck._active_page = p
        deck._render_button = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        await deck.refresh()
        deck._render_touchscreen.assert_awaited_once()

    async def test_skips_clean_buttons(self, deck):
        p = deck.page("main")
        b = p.button(0)
        b.set_icon("mdi:home")
        b.mark_clean()  # Make it clean

        deck._active_page = p
        deck._render_button = AsyncMock()
        deck._render_touchscreen = AsyncMock()
        # Mark all widgets clean
        for w in p.widgets:
            w.mark_clean()

        await deck.refresh()
        deck._render_button.assert_not_awaited()

    async def test_skips_clean_touchscreen(self, deck):
        p = deck.page("main")
        for w in p.widgets:
            w.mark_clean()

        deck._active_page = p
        deck._render_button = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        await deck.refresh()
        deck._render_touchscreen.assert_not_awaited()


# ── Deck._dispatch ──────────────────────────────────────────────────────


class TestDeckDispatch:
    async def test_no_active_page(self, deck):
        """_dispatch is a no-op with no active page."""
        event = KeyEvent(key=0, pressed=True)
        await deck._dispatch(event)  # Should not raise

    async def test_key_press_dispatches(self, deck):
        p = deck.page("main")
        handler = AsyncMock()
        p.button(0).on_press(handler)
        deck._active_page = p

        await deck._dispatch(KeyEvent(key=0, pressed=True))
        handler.assert_awaited_once()

    async def test_key_release_dispatches(self, deck):
        p = deck.page("main")
        handler = AsyncMock()
        p.button(0).on_release(handler)
        deck._active_page = p

        await deck._dispatch(KeyEvent(key=0, pressed=False))
        handler.assert_awaited_once()

    async def test_key_press_no_handler(self, deck):
        """No error when button has no handler."""
        p = deck.page("main")
        p.button(0)  # No handler registered
        deck._active_page = p

        await deck._dispatch(KeyEvent(key=0, pressed=True))  # Should not raise

    async def test_key_event_unknown_button(self, deck):
        """No error when event targets a button that doesn't exist on the page."""
        p = deck.page("main")
        deck._active_page = p

        await deck._dispatch(KeyEvent(key=7, pressed=True))  # No button 7

    async def test_dial_turn_dispatches(self, deck):
        p = deck.page("main")
        handler = AsyncMock()
        p.dial(1).on_turn(handler)
        deck._active_page = p

        await deck._dispatch(DialTurnEvent(dial=1, direction=3))
        handler.assert_awaited_once_with(3)

    async def test_dial_turn_no_handler(self, deck):
        p = deck.page("main")
        p.dial(1)
        deck._active_page = p

        await deck._dispatch(DialTurnEvent(dial=1, direction=1))

    async def test_dial_turn_unknown_dial(self, deck):
        p = deck.page("main")
        deck._active_page = p

        await deck._dispatch(DialTurnEvent(dial=2, direction=1))

    async def test_dial_turn_updates_widget_slider(self, deck):
        """Dial turn forwards to widget sliders and triggers refresh."""
        from deckboard.widgets.volume import VolumeSlider
        from deckboard.widgets.slider_widget import SliderWidget

        p = deck.page("main")
        sw = SliderWidget(1)
        slider = VolumeSlider()
        sw.add_slider(slider)
        p.set_widget(1, sw)
        deck._active_page = p

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._dispatch(DialTurnEvent(dial=1, direction=5))
            mock_refresh.assert_awaited_once()
        assert slider.value == 5  # default 0 + 5

    async def test_dial_press_dispatches(self, deck):
        p = deck.page("main")
        handler = AsyncMock()
        p.dial(0).on_press(handler)
        deck._active_page = p

        await deck._dispatch(DialPressEvent(dial=0, pressed=True))
        handler.assert_awaited_once()

    async def test_dial_release_dispatches(self, deck):
        p = deck.page("main")
        handler = AsyncMock()
        p.dial(0).on_release(handler)
        deck._active_page = p

        await deck._dispatch(DialPressEvent(dial=0, pressed=False))
        handler.assert_awaited_once()

    async def test_dial_press_no_handler(self, deck):
        p = deck.page("main")
        p.dial(0)
        deck._active_page = p

        await deck._dispatch(DialPressEvent(dial=0, pressed=True))

    async def test_dial_press_unknown_dial(self, deck):
        p = deck.page("main")
        deck._active_page = p

        await deck._dispatch(DialPressEvent(dial=3, pressed=True))

    async def test_dial_press_cycles_widget_slider(self, deck):
        """Dial press cycles active slider on the widget and triggers refresh."""
        from deckboard.widgets.volume import VolumeSlider
        from deckboard.widgets.brightness import BrightnessSlider
        from deckboard.widgets.slider_widget import SliderWidget

        p = deck.page("main")
        sw = SliderWidget(0)
        sw.add_slider(VolumeSlider())
        sw.add_slider(BrightnessSlider())
        p.set_widget(0, sw)
        deck._active_page = p

        assert sw._active_slider_index == 0
        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._dispatch(DialPressEvent(dial=0, pressed=True))
            mock_refresh.assert_awaited_once()
        assert sw._active_slider_index == 1

    async def test_touch_short_dispatches(self, deck):
        p = deck.page("main")
        handler = AsyncMock()
        p.widget(0).on_tap(handler)
        deck._active_page = p

        await deck._dispatch(TouchEvent(event_type=EventType.TOUCH_SHORT, x=50, y=50))
        handler.assert_awaited_once()

    async def test_touch_long_dispatches(self, deck):
        p = deck.page("main")
        handler = AsyncMock()
        p.widget(1).on_long_press(handler)
        deck._active_page = p

        await deck._dispatch(TouchEvent(event_type=EventType.TOUCH_LONG, x=300, y=50))
        handler.assert_awaited_once()

    async def test_touch_drag_dispatches(self, deck):
        p = deck.page("main")
        handler = AsyncMock()
        p.widget(2).on_drag(handler)
        deck._active_page = p

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
        p = deck.page("main")
        deck._active_page = p

        await deck._dispatch(TouchEvent(event_type=EventType.TOUCH_SHORT, x=50, y=50))

    async def test_touch_zone_calculation(self, deck):
        """Touch at x=600 should dispatch to widget zone 3."""
        p = deck.page("main")
        handler = AsyncMock()
        p.widget(3).on_tap(handler)
        deck._active_page = p

        await deck._dispatch(TouchEvent(event_type=EventType.TOUCH_SHORT, x=700, y=50))
        handler.assert_awaited_once()


# ── Deck._dispatch — widget event callbacks ─────────────────────────────


class TestDeckDispatchWidgetCallbacks:
    """Tests for widget-level dial decorators and slider on_change callbacks."""

    async def test_dial_turn_calls_widget_dial_turn_handler(self, deck):
        """Widget on_dial_turn handler is called on DialTurnEvent."""
        from deckboard.widgets.slider_widget import SliderWidget

        p = deck.page("main")
        sw = SliderWidget(0)
        p.set_widget(0, sw)
        deck._active_page = p

        handler = AsyncMock()
        sw.on_dial_turn(handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(DialTurnEvent(dial=0, direction=3))

        handler.assert_awaited_once_with(3)

    async def test_dial_press_calls_widget_dial_press_handler(self, deck):
        """Widget on_dial_press handler is called on DialPressEvent."""
        from deckboard.widgets.slider_widget import SliderWidget
        from deckboard.widgets.volume import VolumeSlider

        p = deck.page("main")
        sw = SliderWidget(0)
        sw.add_slider(VolumeSlider())
        sw.add_slider(VolumeSlider())
        p.set_widget(0, sw)
        deck._active_page = p

        handler = AsyncMock()
        sw.on_dial_press(handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(DialPressEvent(dial=0, pressed=True))

        handler.assert_awaited_once()

    async def test_dial_press_release_does_not_call_widget_handler(self, deck):
        """Widget on_dial_press is NOT called for release events."""
        from deckboard.widgets.slider_widget import SliderWidget

        p = deck.page("main")
        sw = SliderWidget(0)
        p.set_widget(0, sw)
        deck._active_page = p

        handler = AsyncMock()
        sw.on_dial_press(handler)

        await deck._dispatch(DialPressEvent(dial=0, pressed=False))
        handler.assert_not_awaited()

    async def test_dial_turn_drains_slider_on_change(self, deck):
        """Slider on_change callback is awaited after dial turn adjusts value."""
        from deckboard.widgets.slider_widget import SliderWidget
        from deckboard.widgets.volume import VolumeSlider

        p = deck.page("main")
        sw = SliderWidget(0)
        vol = VolumeSlider(value=50, step=5)
        sw.add_slider(vol)
        p.set_widget(0, sw)
        deck._active_page = p

        change_handler = AsyncMock()
        vol.on_change(change_handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(DialTurnEvent(dial=0, direction=1))

        change_handler.assert_awaited_once_with(55.0)

    async def test_dial_turn_order_dial_then_widget_then_change(self, deck):
        """Dispatch order: dial handler → widget dial handler → slider on_change."""
        from deckboard.widgets.slider_widget import SliderWidget
        from deckboard.widgets.volume import VolumeSlider

        p = deck.page("main")
        sw = SliderWidget(0)
        vol = VolumeSlider(value=50, step=5)
        sw.add_slider(vol)
        p.set_widget(0, sw)
        deck._active_page = p

        call_order = []

        dial_handler = AsyncMock(side_effect=lambda d: call_order.append("dial"))
        p.dial(0).on_turn(dial_handler)

        widget_handler = AsyncMock(side_effect=lambda d: call_order.append("widget"))
        sw.on_dial_turn(widget_handler)

        change_handler = AsyncMock(side_effect=lambda v: call_order.append("change"))
        vol.on_change(change_handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(DialTurnEvent(dial=0, direction=1))

        assert call_order == ["dial", "widget", "change"]

    async def test_refresh_drains_pending_callbacks(self, deck):
        """Programmatic set_value + refresh drains on_change callbacks."""
        from deckboard.widgets.slider_widget import SliderWidget
        from deckboard.widgets.volume import VolumeSlider

        p = deck.page("main")
        sw = SliderWidget(0)
        vol = VolumeSlider(value=50)
        sw.add_slider(vol)
        p.set_widget(0, sw)
        deck._active_page = p
        deck._render_button = AsyncMock()
        deck._render_touchscreen = AsyncMock()

        change_handler = AsyncMock()
        vol.on_change(change_handler)

        # Programmatic change (not from dial)
        vol.set_value(80)

        await deck.refresh()
        change_handler.assert_awaited_once_with(80.0)

    async def test_no_on_change_when_value_unchanged_via_dial(self, deck):
        """No on_change callback when dial turn doesn't change value (at max)."""
        from deckboard.widgets.slider_widget import SliderWidget
        from deckboard.widgets.volume import VolumeSlider

        p = deck.page("main")
        sw = SliderWidget(0)
        vol = VolumeSlider(value=100, max_value=100, step=5)
        sw.add_slider(vol)
        p.set_widget(0, sw)
        deck._active_page = p

        change_handler = AsyncMock()
        vol.on_change(change_handler)

        with patch.object(deck, "refresh", new_callable=AsyncMock):
            await deck._dispatch(DialTurnEvent(dial=0, direction=1))

        change_handler.assert_not_awaited()

    async def test_drain_widget_callbacks_helper(self, deck):
        """_drain_widget_callbacks awaits all pending callbacks in order."""
        from deckboard.widgets.slider_widget import SliderWidget

        sw = SliderWidget(0)
        results = []

        async def h1(v: float):
            results.append(("h1", v))

        async def h2(v: float):
            results.append(("h2", v))

        sw.queue_pending_callback(h1, (1.0,))
        sw.queue_pending_callback(h2, (2.0,))

        await deck._drain_widget_callbacks(sw)
        assert results == [("h1", 1.0), ("h2", 2.0)]
        # Queue should be empty after drain
        assert sw.drain_pending_callbacks() == []


# ── Deck._render_all_buttons ────────────────────────────────────────────


class TestDeckRenderAllButtons:
    async def test_no_device(self, deck):
        """No-op when device is None."""
        deck._active_page = deck.page("main")
        await deck._render_all_buttons()  # Should not raise

    async def test_renders_with_device(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        p = deck.page("main")
        deck._active_page = p

        await deck._render_all_buttons()
        # Should have called set_key_image for all 8 keys (all blank)
        assert mock_streamdeck_device.set_key_image.call_count == _KEY_COUNT

    async def test_renders_configured_button(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        p = deck.page("main")
        p.button(0).set_icon("mdi:home")
        deck._active_page = p

        # Mock icon fetch
        deck._render_button = AsyncMock()

        await deck._render_all_buttons()
        deck._render_button.assert_awaited_once()


# ── Deck._render_button ─────────────────────────────────────────────────


class TestDeckRenderButton:
    async def test_no_device(self, deck):
        """No-op when device is None."""
        from deckboard.button import Button

        b = Button(0)
        b.set_icon("mdi:home")
        await deck._render_button(b)  # Should not raise

    async def test_renders_button_with_icon(self, deck, mock_streamdeck_device):
        from PIL import Image

        deck._device = mock_streamdeck_device
        from deckboard.button import Button

        b = Button(0)
        b.set_icon("mdi:home")

        # Mock icon manager
        fake_img = Image.new("RGBA", (80, 80))
        deck.icons.get = AsyncMock(return_value=fake_img)

        await deck._render_button(b)
        mock_streamdeck_device.set_key_image.assert_called_once()
        assert b.image_bytes is not None
        assert b.is_dirty is False

    async def test_renders_button_without_icon(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        from deckboard.button import Button

        b = Button(0)
        b.set_label("Test")

        await deck._render_button(b)
        mock_streamdeck_device.set_key_image.assert_called_once()


# ── Deck._render_touchscreen ───────────────────────────────────────────


class TestDeckRenderTouchscreen:
    async def test_no_device(self, deck):
        """No-op when device is None."""
        deck._active_page = deck.page("main")
        await deck._render_touchscreen()  # Should not raise

    async def test_renders_with_device(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        p = deck.page("main")
        deck._active_page = p

        await deck._render_touchscreen()
        mock_streamdeck_device.set_touchscreen_image.assert_called_once()

    async def test_renders_widgets_with_icons(self, deck, mock_streamdeck_device):
        from PIL import Image

        deck._device = mock_streamdeck_device
        p = deck.page("main")
        p.widget(0).set_icon("mdi:volume-high").set_label("Vol").set_value("75%")
        deck._active_page = p

        fake_img = Image.new("RGBA", (80, 80))
        deck.icons.get = AsyncMock(return_value=fake_img)

        await deck._render_touchscreen()
        mock_streamdeck_device.set_touchscreen_image.assert_called_once()


# ── Deck.info ───────────────────────────────────────────────────────────


class TestDeckInfo:
    def test_no_device_raises(self, deck):
        with pytest.raises(DeckError, match="Device not opened"):
            _ = deck.info

    def test_returns_device_info(self, deck, mock_streamdeck_device):
        deck._device = mock_streamdeck_device
        info = deck.info
        assert info.deck_type == "Stream Deck +"
        assert info.serial == "TEST123"
        assert info.firmware == "1.0.0"
        assert info.key_count == 8
        assert info.key_layout == (4, 2)
        assert info.dial_count == 4
        assert info.key_pixel_size == (120, 120)
        assert info.touchscreen_size == (800, 100)
        assert info.key_image_format == "JPEG"


# ── Deck.start ──────────────────────────────────────────────────────────


class TestDeckStart:
    async def test_no_devices_found(self, deck):
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = []
            with pytest.raises(DeckError, match="No Stream Deck devices found"):
                await deck.start()

    async def test_no_matching_type(self, deck):
        mock_dev = MagicMock()
        mock_dev.DECK_TYPE = "Stream Deck Mini"
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_dev]
            with pytest.raises(DeckError, match="No 'Stream Deck \\+' found"):
                await deck.start()

    async def test_device_index_out_of_range(self, deck):
        deck._device_index = 5
        mock_dev = MagicMock()
        mock_dev.DECK_TYPE = "Stream Deck +"
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_dev]
            with pytest.raises(DeckError, match="Device index 5 out of range"):
                await deck.start()

    async def test_successful_start(self, deck, mock_streamdeck_device):
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await deck.start()
            assert deck._running is True
            assert deck._device is mock_streamdeck_device
            assert deck._transport is not None
            # Cleanup
            await deck.stop()

    async def test_already_running_noop(self, deck, mock_streamdeck_device):
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await deck.start()
            # Second call should be no-op
            await deck.start()
            # enumerate only called once
            assert mock_dm.return_value.enumerate.call_count == 1
            await deck.stop()


# ── Deck.stop ───────────────────────────────────────────────────────────


class TestDeckStop:
    async def test_stop_when_not_running(self, deck):
        """stop() is a no-op when not running."""
        await deck.stop()  # Should not raise

    async def test_stop_closes_device(self, deck, mock_streamdeck_device):
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await deck.start()
            await deck.stop()

            assert deck._running is False
            mock_streamdeck_device.reset.assert_called()
            mock_streamdeck_device.close.assert_called()

    async def test_stop_sets_closed_event(self, deck, mock_streamdeck_device):
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await deck.start()
            await deck.stop()
            assert deck._closed_event.is_set()

    async def test_stop_handles_device_error(self, deck, mock_streamdeck_device):
        """stop() handles errors during device close gracefully."""
        mock_streamdeck_device.close.side_effect = OSError("HID error")
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await deck.start()
            await deck.stop()  # Should not raise


# ── Deck context manager ────────────────────────────────────────────────


class TestDeckContextManager:
    async def test_aenter_aexit(self, deck, mock_streamdeck_device):
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            async with deck as d:
                assert d is deck
                assert d._running is True
            assert deck._running is False


# ── Deck.wait_closed ────────────────────────────────────────────────────


class TestDeckWaitClosed:
    async def test_wait_closed_resolves_after_stop(self, deck, mock_streamdeck_device):
        with patch("deckboard.deck.DeviceManager") as mock_dm:
            mock_dm.return_value.enumerate.return_value = [mock_streamdeck_device]
            await deck.start()

            async def stop_soon():
                await asyncio.sleep(0.05)
                await deck.stop()

            asyncio.create_task(stop_soon())
            await asyncio.wait_for(deck.wait_closed(), timeout=2.0)


# ── DeckError ───────────────────────────────────────────────────────────


class TestDeckCheckTimeouts:
    """Tests for _check_timeouts — periodic slider selection timeout checks."""

    async def test_no_active_page_is_noop(self, deck):
        """_check_timeouts does nothing when no page is active."""
        deck._active_page = None
        await deck._check_timeouts()  # Should not raise

    async def test_no_expired_timeouts_no_refresh(self, deck):
        """No refresh when no widget has an expired timeout."""
        from deckboard.widgets.volume import VolumeSlider
        from deckboard.widgets.brightness import BrightnessSlider
        from deckboard.widgets.slider_widget import SliderWidget

        p = deck.page("main")
        sw = SliderWidget(0)
        sw.add_slider(VolumeSlider(), default=True)
        sw.add_slider(BrightnessSlider())
        sw.set_selection_timeout(5)
        p.set_widget(0, sw)
        deck._active_page = p

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._check_timeouts()
            mock_refresh.assert_not_awaited()

    async def test_expired_timeout_triggers_refresh(self, deck):
        """Expired selection timeout reverts slider and triggers refresh."""
        import time
        from deckboard.widgets.volume import VolumeSlider
        from deckboard.widgets.brightness import BrightnessSlider
        from deckboard.widgets.slider_widget import SliderWidget

        p = deck.page("main")
        sw = SliderWidget(0)
        sw.add_slider(VolumeSlider(), default=True)
        sw.add_slider(BrightnessSlider())
        sw.set_selection_timeout(1)
        p.set_widget(0, sw)
        deck._active_page = p

        # Select non-default slider, then simulate timeout expiry
        sw.cycle_active_slider()
        assert sw.active_slider_index == 1
        sw._last_selection_time = time.monotonic() - 2.0

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._check_timeouts()
            mock_refresh.assert_awaited_once()

        # Should have reverted to default
        assert sw.active_slider_index == 0

    async def test_multiple_widgets_only_expired_triggers(self, deck):
        """Only widgets with expired timeouts cause a refresh."""
        import time
        from deckboard.widgets.volume import VolumeSlider
        from deckboard.widgets.brightness import BrightnessSlider
        from deckboard.widgets.slider_widget import SliderWidget

        p = deck.page("main")

        # Widget 0: not expired
        sw0 = SliderWidget(0)
        sw0.add_slider(VolumeSlider(), default=True)
        sw0.add_slider(BrightnessSlider())
        sw0.set_selection_timeout(10)
        sw0.cycle_active_slider()
        p.set_widget(0, sw0)

        # Widget 1: expired
        sw1 = SliderWidget(1)
        sw1.add_slider(VolumeSlider(), default=True)
        sw1.add_slider(BrightnessSlider())
        sw1.set_selection_timeout(1)
        sw1.cycle_active_slider()
        sw1._last_selection_time = time.monotonic() - 2.0
        p.set_widget(1, sw1)

        deck._active_page = p

        with patch.object(deck, "refresh", new_callable=AsyncMock) as mock_refresh:
            await deck._check_timeouts()
            mock_refresh.assert_awaited_once()

        # sw0 unchanged, sw1 reverted
        assert sw0.active_slider_index == 1
        assert sw1.active_slider_index == 0


class TestDeckEventLoop:
    """Tests for _event_loop internal paths (lines 382, 391-399, 403-404)."""

    async def test_event_loop_returns_early_without_transport(self, deck):
        """Line 382: _event_loop returns immediately when _transport is None."""
        deck._transport = None
        deck._running = True
        # Should return immediately without blocking
        await deck._event_loop()
        # _closed_event is NOT set because the finally block is never reached
        # (early return before the try)
        assert not deck._closed_event.is_set()

    async def test_event_loop_timeout_continues(self, deck):
        """TimeoutError calls _check_timeouts then continues."""
        # Set up a real queue that will time out
        transport = MagicMock()
        transport.queue = asyncio.Queue()
        deck._transport = transport
        deck._running = True

        # After a brief period, stop the loop
        async def stop_after_delay():
            await asyncio.sleep(0.6)  # Slightly more than 0.5s timeout
            deck._running = False

        asyncio.create_task(stop_after_delay())
        with patch.object(
            deck, "_check_timeouts", new_callable=AsyncMock
        ) as mock_check:
            await deck._event_loop()
            mock_check.assert_awaited()
        # The loop timed out at least once and then exited
        assert deck._closed_event.is_set()

    async def test_event_loop_no_active_page_continues(self, deck):
        """Lines 393-394: Event received but no active page → continue."""
        transport = MagicMock()
        transport.queue = asyncio.Queue()
        deck._transport = transport
        deck._running = True
        deck._active_page = None

        # Put an event in the queue
        await transport.queue.put(KeyEvent(key=0, pressed=True))

        # Stop after the event is consumed
        async def stop_after_delay():
            await asyncio.sleep(0.1)
            deck._running = False

        asyncio.create_task(stop_after_delay())
        await deck._event_loop()
        assert deck._closed_event.is_set()

    async def test_event_loop_dispatch_exception_logged(self, deck):
        """Lines 396-399: Exception in _dispatch is caught and logged."""
        transport = MagicMock()
        transport.queue = asyncio.Queue()
        deck._transport = transport
        deck._running = True
        deck._active_page = deck.page("main")

        # Make _dispatch raise an exception
        deck._dispatch = AsyncMock(side_effect=ValueError("handler error"))

        await transport.queue.put(KeyEvent(key=0, pressed=True))

        async def stop_after_delay():
            await asyncio.sleep(0.1)
            deck._running = False

        asyncio.create_task(stop_after_delay())
        with patch("deckboard.deck.logger") as mock_logger:
            await deck._event_loop()
            mock_logger.exception.assert_called_with("Error in event handler")
        assert deck._closed_event.is_set()

    async def test_event_loop_unexpected_crash_logged(self, deck):
        """Lines 403-404: Unexpected exception crashes the event loop, logged."""
        transport = MagicMock()
        # Make queue.get() raise a non-asyncio exception
        q = asyncio.Queue()
        deck._transport = transport
        deck._running = True

        # Patch the queue's get to raise a RuntimeError
        async def exploding_get():
            raise RuntimeError("unexpected crash")

        transport.queue = MagicMock()
        transport.queue.get = exploding_get

        with patch("deckboard.deck.logger") as mock_logger:
            await deck._event_loop()
            mock_logger.exception.assert_called_with("Event loop crashed")
        # finally block should still set the closed event
        assert deck._closed_event.is_set()


class TestDeckError:
    def test_is_exception(self):
        assert issubclass(DeckError, Exception)

    def test_message(self):
        e = DeckError("test message")
        assert str(e) == "test message"
