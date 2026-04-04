"""Tests for deckboard.ui.elements.metrics — LargeDualValue, SmallDualValue."""

from __future__ import annotations

from PIL import Image

from deckboard.render.metrics import PANEL_HEIGHT, PANEL_WIDTH
from deckboard.ui.elements.metrics import (
    LargeDualValue,
    SmallDualValue,
    _truncate_value,
)
from deckboard.ui.cards.stack import StackCard


# ── _truncate_value helper ───────────────────────────────────────────────


class TestTruncateValue:
    def test_short_text_unchanged(self):
        from PIL import ImageDraw

        from deckboard.render.fonts import get_font

        img = Image.new("RGB", (200, 50))
        draw = ImageDraw.Draw(img)
        font = get_font()
        result = _truncate_value("Hi", font, 200, draw)
        assert result == "Hi"

    def test_long_text_gets_ellipsis(self):
        from PIL import ImageDraw

        from deckboard.render.fonts import get_font

        img = Image.new("RGB", (200, 50))
        draw = ImageDraw.Draw(img)
        font = get_font()
        long_text = "A" * 200
        result = _truncate_value(long_text, font, 50, draw)
        assert result.endswith("\u2026")
        assert len(result) < len(long_text)

    def test_empty_text(self):
        from PIL import ImageDraw

        from deckboard.render.fonts import get_font

        img = Image.new("RGB", (200, 50))
        draw = ImageDraw.Draw(img)
        font = get_font()
        result = _truncate_value("", font, 50, draw)
        assert result == ""

    def test_zero_width_returns_ellipsis(self):
        from PIL import ImageDraw

        from deckboard.render.fonts import get_font

        img = Image.new("RGB", (200, 50))
        draw = ImageDraw.Draw(img)
        font = get_font()
        result = _truncate_value("Hello World", font, 0, draw)
        assert result == "\u2026"


# ── LargeDualValue ──────────────────────────────────────────────────────


class TestLargeDualValueInit:
    def test_defaults(self):
        dv = LargeDualValue()
        assert dv.left_value == ""
        assert dv.right_value == ""
        assert dv.left_icon is None
        assert dv.right_icon is None
        assert dv.color == "white"
        assert dv.selectable is False

    def test_custom_values(self):
        dv = LargeDualValue("22°C", "45%")
        assert dv.left_value == "22°C"
        assert dv.right_value == "45%"

    def test_custom_icons(self):
        left = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        right = Image.new("RGBA", (24, 24), (0, 255, 0, 255))
        dv = LargeDualValue(left_icon=left, right_icon=right)
        assert dv.left_icon is left
        assert dv.right_icon is right

    def test_custom_color(self):
        dv = LargeDualValue(color="#ff0000")
        assert dv.color == "#ff0000"

    def test_not_selectable(self):
        dv = LargeDualValue("X", "Y")
        assert dv.selectable is False


class TestLargeDualValueSetLeftValue:
    def test_sets_value(self):
        dv = LargeDualValue("old", "other")
        dv.set_left_value("new")
        assert dv.left_value == "new"

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = LargeDualValue("old", "other")
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        dv.set_left_value("new")
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = LargeDualValue("old", "other")
        dv.set_left_value("new")
        assert dv.left_value == "new"


class TestLargeDualValueSetRightValue:
    def test_sets_value(self):
        dv = LargeDualValue("left", "old")
        dv.set_right_value("new")
        assert dv.right_value == "new"

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = LargeDualValue("left", "old")
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        dv.set_right_value("new")
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = LargeDualValue("left", "old")
        dv.set_right_value("new")
        assert dv.right_value == "new"


class TestLargeDualValueSetLeftIcon:
    def test_sets_icon(self):
        dv = LargeDualValue()
        icon = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        dv.set_left_icon(icon)
        assert dv.left_icon is icon

    def test_sets_icon_to_none(self):
        icon = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        dv = LargeDualValue(left_icon=icon)
        dv.set_left_icon(None)
        assert dv.left_icon is None

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = LargeDualValue()
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        icon = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        dv.set_left_icon(icon)
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = LargeDualValue()
        icon = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        dv.set_left_icon(icon)
        assert dv.left_icon is icon


class TestLargeDualValueSetRightIcon:
    def test_sets_icon(self):
        dv = LargeDualValue()
        icon = Image.new("RGBA", (24, 24), (0, 255, 0, 255))
        dv.set_right_icon(icon)
        assert dv.right_icon is icon

    def test_sets_icon_to_none(self):
        icon = Image.new("RGBA", (24, 24), (0, 255, 0, 255))
        dv = LargeDualValue(right_icon=icon)
        dv.set_right_icon(None)
        assert dv.right_icon is None

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = LargeDualValue()
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        icon = Image.new("RGBA", (24, 24), (0, 255, 0, 255))
        dv.set_right_icon(icon)
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = LargeDualValue()
        icon = Image.new("RGBA", (24, 24), (0, 255, 0, 255))
        dv.set_right_icon(icon)
        assert dv.right_icon is icon


class TestLargeDualValueSetColor:
    def test_sets_color(self):
        dv = LargeDualValue()
        dv.set_color("#00ff00")
        assert dv.color == "#00ff00"

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = LargeDualValue()
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        dv.set_color("red")
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = LargeDualValue()
        dv.set_color("red")
        assert dv.color == "red"


class TestLargeDualValueRender:
    def test_renders_onto_image(self):
        dv = LargeDualValue("22°C", "45%")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_empty_values(self):
        dv = LargeDualValue()
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_long_text_truncated(self):
        dv = LargeDualValue("A" * 200, "B" * 200)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_active_ignored(self):
        dv = LargeDualValue("22°C", "45%")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2, active=True)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_custom_color(self):
        dv = LargeDualValue("22°C", "45%", color="#ff0000")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_rgba_icons(self):
        left = Image.new("RGBA", (48, 48), (255, 0, 0, 255))
        right = Image.new("RGBA", (48, 48), (0, 255, 0, 255))
        dv = LargeDualValue("22°C", "45%", left_icon=left, right_icon=right)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_rgb_icons(self):
        left = Image.new("RGB", (48, 48), (255, 0, 0))
        right = Image.new("RGB", (48, 48), (0, 255, 0))
        dv = LargeDualValue("22°C", "45%", left_icon=left, right_icon=right)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_left_icon_only(self):
        left = Image.new("RGBA", (48, 48), (255, 0, 0, 255))
        dv = LargeDualValue("22°C", "45%", left_icon=left)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_right_icon_only(self):
        right = Image.new("RGBA", (48, 48), (0, 255, 0, 255))
        dv = LargeDualValue("22°C", "45%", right_icon=right)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_at_offset(self):
        dv = LargeDualValue("22°C", "45%")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 10, 20, PANEL_WIDTH - 10, PANEL_HEIGHT // 2)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)


# ── SmallDualValue ──────────────────────────────────────────────────────


class TestSmallDualValueInit:
    def test_defaults(self):
        dv = SmallDualValue()
        assert dv.left_value == ""
        assert dv.right_value == ""
        assert dv.left_icon is None
        assert dv.right_icon is None
        assert dv.color == "white"
        assert dv.selectable is False

    def test_custom_values(self):
        dv = SmallDualValue("95 Mb", "48 Mb")
        assert dv.left_value == "95 Mb"
        assert dv.right_value == "48 Mb"

    def test_custom_icons(self):
        left = Image.new("RGBA", (12, 12), (255, 0, 0, 255))
        right = Image.new("RGBA", (12, 12), (0, 255, 0, 255))
        dv = SmallDualValue(left_icon=left, right_icon=right)
        assert dv.left_icon is left
        assert dv.right_icon is right

    def test_custom_color(self):
        dv = SmallDualValue(color="#00ff00")
        assert dv.color == "#00ff00"

    def test_not_selectable(self):
        dv = SmallDualValue("X", "Y")
        assert dv.selectable is False


class TestSmallDualValueSetLeftValue:
    def test_sets_value(self):
        dv = SmallDualValue("old", "other")
        dv.set_left_value("new")
        assert dv.left_value == "new"

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = SmallDualValue("old", "other")
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        dv.set_left_value("new")
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = SmallDualValue("old", "other")
        dv.set_left_value("new")
        assert dv.left_value == "new"


class TestSmallDualValueSetRightValue:
    def test_sets_value(self):
        dv = SmallDualValue("left", "old")
        dv.set_right_value("new")
        assert dv.right_value == "new"

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = SmallDualValue("left", "old")
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        dv.set_right_value("new")
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = SmallDualValue("left", "old")
        dv.set_right_value("new")
        assert dv.right_value == "new"


class TestSmallDualValueSetLeftIcon:
    def test_sets_icon(self):
        dv = SmallDualValue()
        icon = Image.new("RGBA", (12, 12), (255, 0, 0, 255))
        dv.set_left_icon(icon)
        assert dv.left_icon is icon

    def test_sets_icon_to_none(self):
        icon = Image.new("RGBA", (12, 12), (255, 0, 0, 255))
        dv = SmallDualValue(left_icon=icon)
        dv.set_left_icon(None)
        assert dv.left_icon is None

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = SmallDualValue()
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        icon = Image.new("RGBA", (12, 12), (255, 0, 0, 255))
        dv.set_left_icon(icon)
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = SmallDualValue()
        icon = Image.new("RGBA", (12, 12), (255, 0, 0, 255))
        dv.set_left_icon(icon)
        assert dv.left_icon is icon


class TestSmallDualValueSetRightIcon:
    def test_sets_icon(self):
        dv = SmallDualValue()
        icon = Image.new("RGBA", (12, 12), (0, 255, 0, 255))
        dv.set_right_icon(icon)
        assert dv.right_icon is icon

    def test_sets_icon_to_none(self):
        icon = Image.new("RGBA", (12, 12), (0, 255, 0, 255))
        dv = SmallDualValue(right_icon=icon)
        dv.set_right_icon(None)
        assert dv.right_icon is None

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = SmallDualValue()
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        icon = Image.new("RGBA", (12, 12), (0, 255, 0, 255))
        dv.set_right_icon(icon)
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = SmallDualValue()
        icon = Image.new("RGBA", (12, 12), (0, 255, 0, 255))
        dv.set_right_icon(icon)
        assert dv.right_icon is icon


class TestSmallDualValueSetColor:
    def test_sets_color(self):
        dv = SmallDualValue()
        dv.set_color("#ff00ff")
        assert dv.color == "#ff00ff"

    def test_marks_card_dirty(self):
        panel = StackCard(0)
        dv = SmallDualValue()
        panel.add_element(dv)
        panel.mark_clean()
        assert panel.is_dirty is False
        dv.set_color("red")
        assert panel.is_dirty is True

    def test_without_card_does_not_raise(self):
        dv = SmallDualValue()
        dv.set_color("red")
        assert dv.color == "red"


class TestSmallDualValueRender:
    def test_renders_onto_image(self):
        dv = SmallDualValue("95 Mb", "48 Mb")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_empty_values(self):
        dv = SmallDualValue()
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_long_text_truncated(self):
        dv = SmallDualValue("A" * 200, "B" * 200)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_active_ignored(self):
        dv = SmallDualValue("95 Mb", "48 Mb")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4, active=True)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_custom_color(self):
        dv = SmallDualValue("95 Mb", "48 Mb", color="#00ff00")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_rgba_icons(self):
        left = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        right = Image.new("RGBA", (24, 24), (0, 255, 0, 255))
        dv = SmallDualValue("95 Mb", "48 Mb", left_icon=left, right_icon=right)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_rgb_icons(self):
        left = Image.new("RGB", (24, 24), (255, 0, 0))
        right = Image.new("RGB", (24, 24), (0, 255, 0))
        dv = SmallDualValue("95 Mb", "48 Mb", left_icon=left, right_icon=right)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_left_icon_only(self):
        left = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        dv = SmallDualValue("95 Mb", "48 Mb", left_icon=left)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_with_right_icon_only(self):
        right = Image.new("RGBA", (24, 24), (0, 255, 0, 255))
        dv = SmallDualValue("95 Mb", "48 Mb", right_icon=right)
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 0, 0, PANEL_WIDTH, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_renders_at_offset(self):
        dv = SmallDualValue("95 Mb", "48 Mb")
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        dv.render_onto(img, 10, 20, PANEL_WIDTH - 10, PANEL_HEIGHT // 4)
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)


# ── StackCard integration ──────────────────────────────────────────────


class TestDualValueTouchPanelIntegration:
    def test_large_dual_value_accepted_by_add_element(self):
        panel = StackCard(0)
        dv = LargeDualValue("22°C", "45%")
        result = panel.add_element(dv)
        assert result is panel
        assert len(panel.elements) == 1
        assert panel.elements[0] is dv

    def test_small_dual_value_accepted_by_add_element(self):
        panel = StackCard(0)
        dv = SmallDualValue("95 Mb", "48 Mb")
        result = panel.add_element(dv)
        assert result is panel
        assert len(panel.elements) == 1
        assert panel.elements[0] is dv

    def test_dual_value_not_in_selectable(self):
        panel = StackCard(0)
        dv = LargeDualValue("22°C", "45%")
        panel.add_element(dv)
        assert panel._selectable_indices() == []

    def test_mixed_with_slider(self):
        from deckboard.ui.controls.volume import VolumeSlider

        panel = StackCard(0)
        dv = LargeDualValue("22°C", "45%")
        vol = VolumeSlider(value=50)
        panel.add_element(dv)
        panel.add_element(vol)
        assert len(panel.elements) == 2
        assert panel.active_control is vol

    def test_panel_render_with_large_dual_value(self):
        panel = StackCard(0)
        dv1 = LargeDualValue("22°C", "45%")
        dv2 = LargeDualValue("1013hPa", "3.2m/s")
        panel.add_element(dv1)
        panel.add_element(dv2)
        img = panel.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_panel_render_with_small_dual_value(self):
        panel = StackCard(0)
        dv1 = SmallDualValue("95 Mb", "48 Mb")
        dv2 = SmallDualValue("-42dBm", "12ms")
        dv3 = SmallDualValue("5 GHz", "WPA3")
        dv4 = SmallDualValue("24 dev", "1.2GB")
        panel.add_element(dv1)
        panel.add_element(dv2)
        panel.add_element(dv3)
        panel.add_element(dv4)
        img = panel.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_panel_render_mixed_dual_value_and_slider(self):
        from deckboard.ui.controls.volume import VolumeSlider

        panel = StackCard(0)
        dv = LargeDualValue("22°C", "45%")
        vol = VolumeSlider(value=65)
        panel.add_element(dv)
        panel.add_element(vol)
        img = panel.render()
        assert img.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_invalid_element_rejected(self):
        import pytest

        panel = StackCard(0)
        with pytest.raises(TypeError, match="got str"):
            panel.add_element("not a valid element")  # type: ignore[arg-type]

    def test_back_reference_set(self):
        panel = StackCard(0)
        dv = LargeDualValue("22°C", "45%")
        panel.add_element(dv)
        assert dv._card is panel

    def test_marks_panel_dirty_on_add(self):
        panel = StackCard(0)
        panel.mark_clean()
        dv = LargeDualValue("22°C", "45%")
        panel.add_element(dv)
        assert panel.is_dirty is True


# ── Public API surface ──────────────────────────────────────────────────


class TestDualValuePublicAPI:
    def test_importable_from_ui(self):
        from deckboard.ui import LargeDualValue, SmallDualValue

        assert LargeDualValue is not None
        assert SmallDualValue is not None

    def test_importable_from_deckboard(self):
        from deckboard import LargeDualValue, SmallDualValue

        assert LargeDualValue is not None
        assert SmallDualValue is not None
