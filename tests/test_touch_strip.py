"""Tests for deckui.ui — Card (abstract), BlankCard, and TouchStrip."""

from __future__ import annotations

import pytest
from PIL import Image

from deckui.ui.cards.base import Card
from deckui.ui.cards.blank import BlankCard
from deckui.ui.touch_strip import TouchStrip
from tests.conftest import PANEL_HEIGHT, PANEL_WIDTH


class _ConcreteWidget(Card):
    """Minimal concrete subclass for testing the abstract base."""

    def render(self) -> Image.Image:
        return Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")


class TestWidgetAbstractBase:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            Card()

    def test_initially_dirty(self):
        w = _ConcreteWidget()
        assert w.is_dirty is True

    def test_mark_clean(self):
        w = _ConcreteWidget()
        w.mark_clean()
        assert w.is_dirty is False

    def test_mark_dirty(self):
        w = _ConcreteWidget()
        w.mark_clean()
        w.mark_dirty()
        assert w.is_dirty is True

    def test_rendered_initially_none(self):
        w = _ConcreteWidget()
        assert w.rendered is None

    def test_set_rendered(self):
        w = _ConcreteWidget()
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT))
        w.set_rendered(img)
        assert w.rendered is img
        assert w.is_dirty is False

    def test_set_rendered_none(self):
        w = _ConcreteWidget()
        w.set_rendered(None)
        assert w.rendered is None
        assert w.is_dirty is False

    def test_on_tap(self):
        w = _ConcreteWidget()

        @w.on_tap
        async def handler():
            pass

        assert w._tap_handler is handler

    def test_on_long_press(self):
        w = _ConcreteWidget()

        @w.on_long_press
        async def handler():
            pass

        assert w._long_press_handler is handler

    def test_on_drag(self):
        w = _ConcreteWidget()

        @w.on_drag
        async def handler(x, y, x_out, y_out):
            pass

        assert w._drag_handler is handler

    def test_on_tap_returns_handler(self):
        w = _ConcreteWidget()

        async def handler():
            pass

        result = w.on_tap(handler)
        assert result is handler

    def test_on_long_press_returns_handler(self):
        w = _ConcreteWidget()

        async def handler():
            pass

        result = w.on_long_press(handler)
        assert result is handler

    def test_on_drag_returns_handler(self):
        w = _ConcreteWidget()

        async def handler(x, y, x_out, y_out):
            pass

        result = w.on_drag(handler)
        assert result is handler

    def test_handle_encoder_turn_noop(self):
        w = _ConcreteWidget()
        w.handle_encoder_turn(1)

    def test_handle_encoder_press_noop(self):
        w = _ConcreteWidget()
        w.handle_encoder_press()

    def test_handle_encoder_release_noop(self):
        w = _ConcreteWidget()
        w.handle_encoder_release()

    def test_check_selection_timeout_returns_false(self):
        w = _ConcreteWidget()
        assert w.check_selection_timeout() is False

    def test_render_returns_image(self):
        w = _ConcreteWidget()
        img = w.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)


class TestWidgetEncoderDecorators:
    def test_on_encoder_turn(self):
        w = _ConcreteWidget()

        @w.on_encoder_turn
        async def handler(direction: int):
            pass

        assert w._encoder_turn_handler is handler

    def test_on_encoder_turn_returns_handler(self):
        w = _ConcreteWidget()

        async def handler(direction: int):
            pass

        result = w.on_encoder_turn(handler)
        assert result is handler

    def test_on_encoder_press(self):
        w = _ConcreteWidget()

        @w.on_encoder_press
        async def handler():
            pass

        assert w._encoder_press_handler is handler

    def test_on_encoder_press_returns_handler(self):
        w = _ConcreteWidget()

        async def handler():
            pass

        result = w.on_encoder_press(handler)
        assert result is handler

    def test_on_encoder_release(self):
        w = _ConcreteWidget()

        @w.on_encoder_release
        async def handler():
            pass

        assert w._encoder_release_handler is handler

    def test_on_encoder_release_returns_handler(self):
        w = _ConcreteWidget()

        async def handler():
            pass

        result = w.on_encoder_release(handler)
        assert result is handler

    def test_encoder_handlers_initially_none(self):
        w = _ConcreteWidget()
        assert w._encoder_turn_handler is None
        assert w._encoder_press_handler is None
        assert w._encoder_release_handler is None


class TestWidgetPendingCallbacks:
    def test_initially_empty(self):
        w = _ConcreteWidget()
        assert w.drain_pending_callbacks() == []

    def test_queue_and_drain(self):
        w = _ConcreteWidget()

        async def handler(value: float):
            pass

        w.queue_pending_callback(handler, (42.0,))
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 1
        assert callbacks[0] == (handler, (42.0,))

    def test_drain_clears_queue(self):
        w = _ConcreteWidget()

        async def handler(value: float):
            pass

        w.queue_pending_callback(handler, (1.0,))
        w.drain_pending_callbacks()
        assert w.drain_pending_callbacks() == []

    def test_multiple_callbacks_preserved_in_order(self):
        w = _ConcreteWidget()

        async def h1(value: float):
            pass

        async def h2(value: float):
            pass

        w.queue_pending_callback(h1, (10.0,))
        w.queue_pending_callback(h2, (20.0,))
        callbacks = w.drain_pending_callbacks()
        assert len(callbacks) == 2
        assert callbacks[0] == (h1, (10.0,))
        assert callbacks[1] == (h2, (20.0,))


class TestWidgetDispatch:
    async def test_dispatch_encoder_turn_with_handler(self):
        w = _ConcreteWidget()
        called_with = []

        @w.on_encoder_turn
        async def handler(direction: int):
            called_with.append(direction)

        await w.dispatch_encoder_turn(3)
        assert called_with == [3]

    async def test_dispatch_encoder_turn_no_handler(self):
        w = _ConcreteWidget()
        await w.dispatch_encoder_turn(1)

    async def test_dispatch_encoder_press_with_handler(self):
        w = _ConcreteWidget()
        called = []

        @w.on_encoder_press
        async def handler():
            called.append(True)

        await w.dispatch_encoder_press()
        assert called == [True]

    async def test_dispatch_encoder_release_with_handler(self):
        w = _ConcreteWidget()
        called = []

        @w.on_encoder_release
        async def handler():
            called.append(True)

        await w.dispatch_encoder_release()
        assert called == [True]

    async def test_dispatch_touch_tap(self):
        from deckui.runtime.events import EventType, TouchEvent

        w = _ConcreteWidget()
        called = []

        @w.on_tap
        async def handler():
            called.append("tap")

        await w.dispatch_touch(TouchEvent(event_type=EventType.TOUCH_SHORT, x=10, y=10))
        assert called == ["tap"]

    async def test_dispatch_touch_long_press(self):
        from deckui.runtime.events import EventType, TouchEvent

        w = _ConcreteWidget()
        called = []

        @w.on_long_press
        async def handler():
            called.append("long")

        await w.dispatch_touch(TouchEvent(event_type=EventType.TOUCH_LONG, x=10, y=10))
        assert called == ["long"]

    async def test_dispatch_touch_drag(self):
        from deckui.runtime.events import EventType, TouchEvent

        w = _ConcreteWidget()
        called = []

        @w.on_drag
        async def handler(x, y, x_out, y_out):
            called.append((x, y, x_out, y_out))

        await w.dispatch_touch(
            TouchEvent(event_type=EventType.TOUCH_DRAG, x=10, y=20, x_out=30, y_out=40)
        )
        assert called == [(10, 20, 30, 40)]

    async def test_dispatch_touch_no_handler(self):
        from deckui.runtime.events import EventType, TouchEvent

        w = _ConcreteWidget()
        await w.dispatch_touch(TouchEvent(event_type=EventType.TOUCH_SHORT, x=10, y=10))


class TestWidgetRefreshCallback:
    async def test_set_and_request_refresh(self):
        w = _ConcreteWidget()
        called = []

        async def refresh():
            called.append(True)

        w.set_refresh_callback(refresh)
        await w.request_refresh()
        assert called == [True]

    async def test_request_refresh_no_callback(self):
        w = _ConcreteWidget()
        await w.request_refresh()

    async def test_prepare_assets_noop(self):
        w = _ConcreteWidget()
        await w.prepare_assets()


class TestBlankCard:
    def test_is_card(self):
        b = BlankCard()
        assert isinstance(b, Card)

    def test_render_returns_none(self):
        b = BlankCard()
        assert b.render() is None

    def test_initially_dirty(self):
        b = BlankCard()
        assert b.is_dirty is True


class TestTouchStripInit:
    def test_creates_four_cards(self, touchscreen: TouchStrip):
        assert len(touchscreen.cards) == 4

    def test_default_cards_are_blank(self, touchscreen: TouchStrip):
        for w in touchscreen.cards:
            assert isinstance(w, BlankCard)


class TestTouchStripCard:
    def test_get_by_index(self, touchscreen: TouchStrip):
        for i in range(4):
            w = touchscreen.card(i)
            assert isinstance(w, Card)
            assert touchscreen.cards[i] is w

    def test_same_instance(self, touchscreen: TouchStrip):
        """card(i) returns the same object each time."""
        a = touchscreen.card(0)
        b = touchscreen.card(0)
        assert a is b

    def test_index_too_low(self, touchscreen: TouchStrip):
        with pytest.raises(IndexError, match="Card index must be 0-3"):
            touchscreen.card(-1)

    def test_index_too_high(self, touchscreen: TouchStrip):
        with pytest.raises(IndexError, match="Card index must be 0-3"):
            touchscreen.card(4)


class TestTouchStripSetCard:
    def test_replace_with_custom_card(self, touchscreen: TouchStrip):
        cw = _ConcreteWidget()
        touchscreen.set_card(2, cw)
        assert touchscreen.card(2) is cw

    def test_replace_with_blank(self, touchscreen: TouchStrip):
        cw = _ConcreteWidget()
        touchscreen.set_card(0, cw)
        blank = BlankCard()
        touchscreen.set_card(0, blank)
        assert touchscreen.card(0) is blank

    def test_index_too_low(self, touchscreen: TouchStrip):
        with pytest.raises(IndexError, match="Card index must be 0-3"):
            touchscreen.set_card(-1, _ConcreteWidget())

    def test_index_too_high(self, touchscreen: TouchStrip):
        with pytest.raises(IndexError, match="Card index must be 0-3"):
            touchscreen.set_card(4, _ConcreteWidget())

    def test_rejects_non_card(self, touchscreen: TouchStrip):
        with pytest.raises(TypeError, match="Expected a Card instance"):
            touchscreen.set_card(0, "not a card")


class TestTouchStripBackgroundColor:
    def test_default_is_black(self, touchscreen: TouchStrip):
        assert touchscreen.background_color == "black"

    def test_constructor_accepts_background_color(self):
        ts = TouchStrip(background_color="#1a1a2e")
        assert ts.background_color == "#1a1a2e"

    def test_setter_updates_value(self, touchscreen: TouchStrip):
        touchscreen.background_color = "#ff0000"
        assert touchscreen.background_color == "#ff0000"

    def test_setter_marks_all_cards_dirty(self, touchscreen: TouchStrip):
        for card in touchscreen.cards:
            card.mark_clean()
        assert touchscreen.any_dirty is False
        touchscreen.background_color = "#00ff00"
        assert touchscreen.any_dirty is True
        for card in touchscreen.cards:
            assert card.is_dirty is True

    def test_setter_same_value_does_not_mark_dirty(self, touchscreen: TouchStrip):
        for card in touchscreen.cards:
            card.mark_clean()
        touchscreen.background_color = "black"
        assert touchscreen.any_dirty is False


class TestTouchStripAnyDirty:
    def test_initially_dirty(self, touchscreen: TouchStrip):
        assert touchscreen.any_dirty is True

    def test_all_clean(self, touchscreen: TouchStrip):
        for w in touchscreen.cards:
            w.mark_clean()
        assert touchscreen.any_dirty is False

    def test_one_dirty(self, touchscreen: TouchStrip):
        for w in touchscreen.cards:
            w.mark_clean()
        touchscreen.card(2).mark_dirty()
        assert touchscreen.any_dirty is True


class TestTouchStripPanelDimensions:
    """Panel width and height are stored and exposed."""

    def test_defaults(self):
        ts = TouchStrip(panel_count=4)
        assert ts.panel_width == 200
        assert ts.panel_height == 100

    def test_custom_dimensions(self):
        ts = TouchStrip(panel_count=2, panel_width=400, panel_height=50)
        assert ts.panel_width == 400
        assert ts.panel_height == 50


class TestTouchStripBackgroundSvg:
    """Background SVG rasterization, slicing, and clearing."""

    @staticmethod
    def _make_svg(width: int = 800, height: int = 100, fill: str = "red") -> bytes:
        """Create a minimal solid-fill SVG for testing."""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<rect width="{width}" height="{height}" fill="{fill}"/>'
            f"</svg>"
        ).encode()

    def test_set_background_svg_creates_tiles(self):
        ts = TouchStrip(panel_count=4, panel_width=200, panel_height=100)
        ts.set_background_svg(self._make_svg())
        assert ts.bg_tiles is not None
        assert len(ts.bg_tiles) == 4
        for tile in ts.bg_tiles:
            assert tile.size == (200, 100)
            assert tile.mode == "RGB"

    def test_set_background_svg_marks_all_dirty(self):
        ts = TouchStrip(panel_count=4, panel_width=200, panel_height=100)
        for card in ts.cards:
            card.mark_clean()
        assert ts.any_dirty is False
        ts.set_background_svg(self._make_svg())
        assert ts.any_dirty is True
        for card in ts.cards:
            assert card.is_dirty is True

    def test_bg_tile_returns_tile(self):
        ts = TouchStrip(panel_count=4, panel_width=200, panel_height=100)
        ts.set_background_svg(self._make_svg())
        tile = ts.bg_tile(0)
        assert tile is not None
        assert tile.size == (200, 100)

    def test_bg_tile_returns_none_without_svg(self):
        ts = TouchStrip(panel_count=4, panel_width=200, panel_height=100)
        assert ts.bg_tile(0) is None

    def test_bg_tile_out_of_range_returns_none(self):
        ts = TouchStrip(panel_count=4, panel_width=200, panel_height=100)
        ts.set_background_svg(self._make_svg())
        assert ts.bg_tile(10) is None
        assert ts.bg_tile(-1) is None

    def test_clear_background_svg(self):
        ts = TouchStrip(panel_count=4, panel_width=200, panel_height=100)
        ts.set_background_svg(self._make_svg())
        assert ts.bg_tiles is not None
        for card in ts.cards:
            card.mark_clean()
        ts.clear_background_svg()
        assert ts.bg_tiles is None
        assert ts.any_dirty is True

    def test_set_background_svg_from_file(self, tmp_path):
        svg_file = tmp_path / "bg.svg"
        svg_file.write_bytes(self._make_svg())
        ts = TouchStrip(panel_count=4, panel_width=200, panel_height=100)
        ts.set_background_svg_from_file(svg_file)
        assert ts.bg_tiles is not None
        assert len(ts.bg_tiles) == 4

    def test_set_background_svg_from_file_not_found(self):
        ts = TouchStrip(panel_count=4, panel_width=200, panel_height=100)
        with pytest.raises(FileNotFoundError):
            ts.set_background_svg_from_file("/nonexistent/bg.svg")

    def test_tiles_reflect_svg_content(self):
        """Tiles from a red SVG should have red pixels."""
        ts = TouchStrip(panel_count=2, panel_width=100, panel_height=50)
        ts.set_background_svg(self._make_svg(width=200, height=50, fill="red"))
        tile = ts.bg_tile(0)
        assert tile is not None
        r, g, b = tile.getpixel((50, 25))
        assert r > 200
        assert g < 50
        assert b < 50

    def test_two_panel_slicing(self):
        """Each panel tile covers its portion of the background."""
        # Left half red, right half blue
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="50">'
            b'<rect x="0" y="0" width="100" height="50" fill="red"/>'
            b'<rect x="100" y="0" width="100" height="50" fill="blue"/>'
            b"</svg>"
        )
        ts = TouchStrip(panel_count=2, panel_width=100, panel_height=50)
        ts.set_background_svg(svg)

        tile0 = ts.bg_tile(0)
        tile1 = ts.bg_tile(1)
        assert tile0 is not None and tile1 is not None

        # Tile 0 should be red
        r, g, b = tile0.getpixel((50, 25))
        assert r > 200 and g < 50 and b < 50

        # Tile 1 should be blue
        r, g, b = tile1.getpixel((50, 25))
        assert r < 50 and g < 50 and b > 200


class TestTouchStripInvalidateBackground:
    """Tests for TouchStrip.invalidate_background."""

    @staticmethod
    def _make_svg(width: int = 800, height: int = 100, fill: str = "red") -> bytes:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<rect width="{width}" height="{height}" fill="{fill}"/>'
            f"</svg>"
        ).encode()

    def test_rerasterizes_when_bg_svg_set(self):
        """invalidate_background re-slices the cached SVG."""
        ts = TouchStrip(panel_count=2, panel_width=100, panel_height=50)
        ts.set_background_svg(self._make_svg(width=200, height=50))
        old_tiles = ts.bg_tiles
        assert old_tiles is not None
        ts.invalidate_background()
        # Tiles should be freshly created (new list object)
        assert ts.bg_tiles is not None
        assert ts.bg_tiles is not old_tiles

    def test_noop_without_bg_svg(self):
        """invalidate_background is a no-op when no background SVG is set."""
        ts = TouchStrip(panel_count=2, panel_width=100, panel_height=50)
        ts.invalidate_background()
        assert ts.bg_tiles is None
