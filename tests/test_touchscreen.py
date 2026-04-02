"""Tests for deckboard.touchscreen — Widget and TouchScreen classes."""

from __future__ import annotations

import pytest
from PIL import Image

from deckboard.touchscreen import TouchScreen, Widget


# ── Widget ──────────────────────────────────────────────────────────────


class TestWidgetInit:
    def test_index(self, widget: Widget):
        assert widget.index == 0

    def test_defaults(self, widget: Widget):
        assert widget.icon_name is None
        assert widget.icon_color == "white"
        assert widget.label is None
        assert widget.value is None
        assert widget.rendered is None
        assert widget.is_dirty is True

    def test_custom_index(self):
        w = Widget(3)
        assert w.index == 3


class TestWidgetSetIcon:
    def test_sets_icon_name(self, widget: Widget):
        widget.set_icon("mdi:volume-high")
        assert widget.icon_name == "mdi:volume-high"

    def test_sets_color(self, widget: Widget):
        widget.set_icon("mdi:x", color="#ff0000")
        assert widget.icon_color == "#ff0000"

    def test_default_color(self, widget: Widget):
        widget.set_icon("mdi:x")
        assert widget.icon_color == "white"

    def test_marks_dirty(self, widget: Widget):
        widget.mark_clean()
        widget.set_icon("mdi:x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: Widget):
        assert widget.set_icon("mdi:x") is widget


class TestWidgetSetLabel:
    def test_sets_label(self, widget: Widget):
        widget.set_label("Volume")
        assert widget.label == "Volume"

    def test_none_removes(self, widget: Widget):
        widget.set_label("x")
        widget.set_label(None)
        assert widget.label is None

    def test_marks_dirty(self, widget: Widget):
        widget.mark_clean()
        widget.set_label("x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: Widget):
        assert widget.set_label("x") is widget


class TestWidgetSetValue:
    def test_sets_value(self, widget: Widget):
        widget.set_value("75%")
        assert widget.value == "75%"

    def test_none_removes(self, widget: Widget):
        widget.set_value("x")
        widget.set_value(None)
        assert widget.value is None

    def test_marks_dirty(self, widget: Widget):
        widget.mark_clean()
        widget.set_value("x")
        assert widget.is_dirty is True

    def test_returns_self(self, widget: Widget):
        assert widget.set_value("x") is widget


class TestWidgetClear:
    def test_clears_all(self, widget: Widget):
        widget.set_icon("mdi:x")
        widget.set_label("L")
        widget.set_value("V")
        widget.set_rendered(Image.new("RGB", (200, 100)))
        widget.clear()
        assert widget.icon_name is None
        assert widget.label is None
        assert widget.value is None
        assert widget.rendered is None
        assert widget.is_dirty is True

    def test_returns_self(self, widget: Widget):
        assert widget.clear() is widget


class TestWidgetChaining:
    def test_chained_calls(self):
        w = Widget(0)
        result = w.set_icon("mdi:x").set_label("L").set_value("V")
        assert result is w
        assert w.icon_name == "mdi:x"
        assert w.label == "L"
        assert w.value == "V"


class TestWidgetEventHandlers:
    def test_on_tap(self, widget: Widget):
        @widget.on_tap
        async def handler():
            pass

        assert widget._tap_handler is handler

    def test_on_long_press(self, widget: Widget):
        @widget.on_long_press
        async def handler():
            pass

        assert widget._long_press_handler is handler

    def test_on_drag(self, widget: Widget):
        @widget.on_drag
        async def handler(x, y, x_out, y_out):
            pass

        assert widget._drag_handler is handler

    def test_on_tap_returns_handler(self, widget: Widget):
        async def handler():
            pass

        result = widget.on_tap(handler)
        assert result is handler

    def test_on_long_press_returns_handler(self, widget: Widget):
        async def handler():
            pass

        result = widget.on_long_press(handler)
        assert result is handler

    def test_on_drag_returns_handler(self, widget: Widget):
        async def handler(x, y, x_out, y_out):
            pass

        result = widget.on_drag(handler)
        assert result is handler


class TestWidgetRendering:
    def test_set_rendered(self, widget: Widget):
        img = Image.new("RGB", (200, 100))
        widget.set_rendered(img)
        assert widget.rendered is img
        assert widget.is_dirty is False

    def test_mark_clean(self, widget: Widget):
        assert widget.is_dirty is True
        widget.mark_clean()
        assert widget.is_dirty is False


# ── TouchScreen ─────────────────────────────────────────────────────────


class TestTouchScreenInit:
    def test_creates_four_widgets(self, touchscreen: TouchScreen):
        assert len(touchscreen.widgets) == 4

    def test_widget_indices(self, touchscreen: TouchScreen):
        for i in range(4):
            assert touchscreen.widgets[i].index == i


class TestTouchScreenWidget:
    def test_get_by_index(self, touchscreen: TouchScreen):
        for i in range(4):
            w = touchscreen.widget(i)
            assert isinstance(w, Widget)
            assert w.index == i

    def test_same_instance(self, touchscreen: TouchScreen):
        """widget(i) returns the same object each time."""
        a = touchscreen.widget(0)
        b = touchscreen.widget(0)
        assert a is b

    def test_index_too_low(self, touchscreen: TouchScreen):
        with pytest.raises(IndexError, match="Widget index must be 0-3"):
            touchscreen.widget(-1)

    def test_index_too_high(self, touchscreen: TouchScreen):
        with pytest.raises(IndexError, match="Widget index must be 0-3"):
            touchscreen.widget(4)


class TestTouchScreenAnyDirty:
    def test_initially_dirty(self, touchscreen: TouchScreen):
        assert touchscreen.any_dirty is True

    def test_all_clean(self, touchscreen: TouchScreen):
        for w in touchscreen.widgets:
            w.mark_clean()
        assert touchscreen.any_dirty is False

    def test_one_dirty(self, touchscreen: TouchScreen):
        for w in touchscreen.widgets:
            w.mark_clean()
        touchscreen.widget(2).set_label("changed")
        assert touchscreen.any_dirty is True
