"""Tests for deckboard.ui.elements.text — LargeText, SmallText."""

from __future__ import annotations

from PIL import Image

from deckboard.render.fonts import get_large_font
from deckboard.render.metrics import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.ui.elements.text import LargeText, SmallText, _truncate_text
from deckboard.ui.cards.stack import StackCard


# ── _truncate_text helper ────────────────────────────────────────────────


class TestTruncateText:
    def test_short_text_unchanged(self):
        from PIL import ImageDraw

        img = Image.new("RGB", (200, 50))
        draw = ImageDraw.Draw(img)
        from deckboard.render.fonts import get_font

        font = get_font()
        result = _truncate_text("Hi", font, 200, draw)
        assert result == "Hi"

    def test_long_text_gets_ellipsis(self):
        from PIL import ImageDraw

        img = Image.new("RGB", (200, 50))
        draw = ImageDraw.Draw(img)
        from deckboard.render.fonts import get_font

        font = get_font()
        long_text = "A" * 200
        result = _truncate_text(long_text, font, 50, draw)
        assert result.endswith("\u2026")
        assert len(result) < len(long_text)

    def test_empty_text(self):
        from PIL import ImageDraw

        img = Image.new("RGB", (200, 50))
        draw = ImageDraw.Draw(img)
        from deckboard.render.fonts import get_font

        font = get_font()
        result = _truncate_text("", font, 50, draw)
        assert result == ""

    def test_zero_width_returns_ellipsis(self):
        from PIL import ImageDraw

        img = Image.new("RGB", (200, 50))
        draw = ImageDraw.Draw(img)
        from deckboard.render.fonts import get_font

        font = get_font()
        result = _truncate_text("Hello World", font, 0, draw)
        assert result == "\u2026"


# ── LargeText ────────────────────────────────────────────────────────────


class TestLargeTextInit:
    def test_defaults(self):
        t = LargeText()
        assert t.text == ""
        assert t.color == "white"
        assert t.selectable is False

    def test_custom_text(self):
        t = LargeText("Hello")
        assert t.text == "Hello"

    def test_custom_color(self):
        t = LargeText("Hi", color="#ff0000")
        assert t.color == "#ff0000"

    def test_not_selectable(self):
        t = LargeText("X")
        assert t.selectable is False


class TestLargeTextSetText:
    def test_sets_text(self):
        t = LargeText("old")
        t.set_text("new")
        assert t.text == "new"

    def test_marks_widget_dirty(self):
        panel = StackCard(0)
        t = LargeText("old")
        panel.add_element(t)
        panel.mark_clean()
        assert panel.is_dirty is False
        t.set_text("new")
        assert panel.is_dirty is True

    def test_without_widget_does_not_raise(self):
        t = LargeText("old")
        t.set_text("new")
        assert t.text == "new"


class TestLargeTextSetColor:
    def test_sets_color(self):
        t = LargeText("Hi")
        t.set_color("#00ff00")
        assert t.color == "#00ff00"

    def test_marks_widget_dirty(self):
        panel = StackCard(0)
        t = LargeText("Hi")
        panel.add_element(t)
        panel.mark_clean()
        assert panel.is_dirty is False
        t.set_color("red")
        assert panel.is_dirty is True

    def test_without_widget_does_not_raise(self):
        t = LargeText("Hi")
        t.set_color("red")
        assert t.color == "red"


class TestLargeTextRender:
    def test_renders_onto_image(self):
        t = LargeText("Volume: 75%")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_empty_text(self):
        t = LargeText("")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_long_text_truncated(self):
        t = LargeText("A" * 200)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_active_ignored(self):
        t = LargeText("Test")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        # active=True should not cause errors; it's ignored for text
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2, active=True)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_custom_color(self):
        t = LargeText("Red Text", color="#ff0000")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)


# ── SmallText ────────────────────────────────────────────────────────────


class TestSmallTextInit:
    def test_defaults(self):
        t = SmallText()
        assert t.text == ""
        assert t.color == "white"
        assert t.selectable is False

    def test_custom_text(self):
        t = SmallText("Online")
        assert t.text == "Online"

    def test_custom_color(self):
        t = SmallText("Y", color="#00ff00")
        assert t.color == "#00ff00"

    def test_not_selectable(self):
        t = SmallText("X")
        assert t.selectable is False


class TestSmallTextSetText:
    def test_sets_text(self):
        t = SmallText("old")
        t.set_text("new")
        assert t.text == "new"

    def test_marks_widget_dirty(self):
        panel = StackCard(0)
        t = SmallText("old")
        panel.add_element(t)
        panel.mark_clean()
        assert panel.is_dirty is False
        t.set_text("new")
        assert panel.is_dirty is True

    def test_without_widget_does_not_raise(self):
        t = SmallText("old")
        t.set_text("new")
        assert t.text == "new"


class TestSmallTextSetColor:
    def test_sets_color(self):
        t = SmallText()
        t.set_color("#ff00ff")
        assert t.color == "#ff00ff"

    def test_marks_widget_dirty(self):
        panel = StackCard(0)
        t = SmallText()
        panel.add_element(t)
        panel.mark_clean()
        assert panel.is_dirty is False
        t.set_color("red")
        assert panel.is_dirty is True

    def test_without_widget_does_not_raise(self):
        t = SmallText()
        t.set_color("red")
        assert t.color == "red"


class TestSmallTextRender:
    def test_renders_onto_image(self):
        t = SmallText("Online")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_empty_text(self):
        t = SmallText("")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_long_text_truncated(self):
        t = SmallText("A" * 200)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_active_ignored(self):
        t = SmallText("Value")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4, active=True)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_custom_color(self):
        t = SmallText("Green", color="#00ff00")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        t.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)


# ── get_large_font ───────────────────────────────────────────────────────


class TestGetLargeFont:
    def test_returns_font(self):
        font = get_large_font()
        assert font is not None

    def test_cached(self):
        f1 = get_large_font()
        f2 = get_large_font()
        assert f1 is f2
