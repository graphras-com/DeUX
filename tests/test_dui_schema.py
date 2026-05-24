"""Tests for deux.dui.schema — data model classes."""

from __future__ import annotations

import pytest

from deux.dui.schema import (
    HOLD_SOURCES,
    VALID_DIRECTIONS,
    VALID_REGION_EVENTS,
    VALID_SOURCES,
    BindingType,
    ColorBinding,
    CssClassBinding,
    EventMapping,
    IconifyBinding,
    ImageBinding,
    ImageFit,
    ListBinding,
    OverflowMode,
    PackageSpec,
    PackageType,
    RangeBinding,
    RangeDirection,
    Region,
    SliderBinding,
    TextBinding,
    ToggleBinding,
    VisibilityBinding,
)


class TestPackageType:
    def test_touch_strip_card(self):
        assert PackageType("TouchStripCard") == PackageType.TOUCH_STRIP_CARD

    def test_key(self):
        assert PackageType("Key") == PackageType.KEY

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            PackageType("Invalid")


class TestBindingType:
    def test_all_types(self):
        assert BindingType("text") == BindingType.TEXT
        assert BindingType("image") == BindingType.IMAGE
        assert BindingType("visibility") == BindingType.VISIBILITY
        assert BindingType("color") == BindingType.COLOR
        assert BindingType("range") == BindingType.RANGE
        assert BindingType("slider") == BindingType.SLIDER
        assert BindingType("toggle") == BindingType.TOGGLE
        assert BindingType("iconify") == BindingType.ICONIFY
        assert BindingType("list") == BindingType.LIST


class TestOverflowMode:
    def test_modes(self):
        assert OverflowMode("ellipsis") == OverflowMode.ELLIPSIS
        assert OverflowMode("clip") == OverflowMode.CLIP


class TestImageFit:
    def test_modes(self):
        assert ImageFit("cover") == ImageFit.COVER
        assert ImageFit("contain") == ImageFit.CONTAIN
        assert ImageFit("fill") == ImageFit.FILL


class TestTextBinding:
    def test_defaults(self):
        b = TextBinding(node="title")
        assert b.node == "title"
        assert b.default == ""
        assert b.max_width is None
        assert b.overflow == OverflowMode.ELLIPSIS
        assert b.wrap is False
        assert b.max_height is None
        assert b.line_height is None

    def test_custom(self):
        b = TextBinding(
            node="artist", default="Unknown", max_width=90, overflow=OverflowMode.CLIP
        )
        assert b.default == "Unknown"
        assert b.max_width == 90
        assert b.overflow == OverflowMode.CLIP

    def test_frozen(self):
        b = TextBinding(node="title")
        with pytest.raises(AttributeError):
            b.node = "other"  # type: ignore[misc]

    def test_wrap_fields(self):
        b = TextBinding(
            node="label",
            max_width=90,
            wrap=True,
            max_height=60,
            line_height=18.0,
        )
        assert b.wrap is True
        assert b.max_height == 60
        assert b.line_height == 18.0

    def test_wrap_defaults_false(self):
        b = TextBinding(node="label", max_width=90)
        assert b.wrap is False
        assert b.max_height is None
        assert b.line_height is None


class TestImageBinding:
    def test_defaults(self):
        b = ImageBinding(node="cover")
        assert b.fit == ImageFit.COVER
        assert b.placeholder_node is None

    def test_with_placeholder(self):
        b = ImageBinding(node="cover", placeholder_node="cover_placeholder")
        assert b.placeholder_node == "cover_placeholder"


class TestVisibilityBinding:
    def test_default_visible(self):
        b = VisibilityBinding(node="overlay")
        assert b.default is True

    def test_default_hidden(self):
        b = VisibilityBinding(node="overlay", default=False)
        assert b.default is False


class TestToggleBinding:
    def test_defaults(self):
        b = ToggleBinding(node_on="icon_on", node_off="icon_off")
        assert b.node_on == "icon_on"
        assert b.node_off == "icon_off"
        assert b.default is False

    def test_default_true(self):
        b = ToggleBinding(node_on="icon_on", node_off="icon_off", default=True)
        assert b.default is True

    def test_frozen(self):
        b = ToggleBinding(node_on="icon_on", node_off="icon_off")
        with pytest.raises(AttributeError):
            b.node_on = "other"  # type: ignore[misc]


class TestIconifyBinding:
    def test_defaults(self):
        b = IconifyBinding(node="icon", size=55)
        assert b.node == "icon"
        assert b.size == 55
        assert b.default == ""

    def test_custom(self):
        b = IconifyBinding(node="icon", size=32, default="line-md:home")
        assert b.size == 32
        assert b.default == "line-md:home"

    def test_frozen(self):
        b = IconifyBinding(node="icon", size=55)
        with pytest.raises(AttributeError):
            b.size = 32  # type: ignore[misc]


class TestColorBinding:
    def test_defaults(self):
        b = ColorBinding(node="bg")
        assert b.attribute == "fill"
        assert b.default == "#ffffff"

    def test_stroke(self):
        b = ColorBinding(node="border", attribute="stroke", default="#000000")
        assert b.attribute == "stroke"

    def test_color(self):
        b = ColorBinding(node="group", attribute="color", default="#00ff00")
        assert b.attribute == "color"

    def test_invalid_attribute_raises(self):
        with pytest.raises(ValueError, match="Invalid color attribute"):
            ColorBinding(node="bg", attribute="opacity")


class TestCssClassBinding:
    def test_defaults(self):
        b = CssClassBinding(node="card")
        assert b.node == "card"
        assert b.default == ""

    def test_custom_default(self):
        b = CssClassBinding(node="card", default="active")
        assert b.default == "active"

    def test_frozen(self):
        b = CssClassBinding(node="card")
        with pytest.raises(AttributeError):
            b.node = "other"  # type: ignore[misc]


class TestRangeDirection:
    def test_modes(self):
        assert RangeDirection("horizontal") == RangeDirection.HORIZONTAL
        assert RangeDirection("vertical") == RangeDirection.VERTICAL

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            RangeDirection("diagonal")


class TestRangeBinding:
    def test_defaults(self):
        b = RangeBinding(node="bar")
        assert b.node == "bar"
        assert b.default == 0.0
        assert b.direction == RangeDirection.HORIZONTAL

    def test_custom(self):
        b = RangeBinding(node="meter", default=0.5, direction=RangeDirection.VERTICAL)
        assert b.default == 0.5
        assert b.direction == RangeDirection.VERTICAL

    def test_frozen(self):
        b = RangeBinding(node="bar")
        with pytest.raises(AttributeError):
            b.node = "other"  # type: ignore[misc]


class TestSliderBinding:
    def test_defaults(self):
        b = SliderBinding(node="indicator")
        assert b.node == "indicator"
        assert b.default == 0.0
        assert b.direction == RangeDirection.HORIZONTAL
        assert b.min_pos == 0.0
        assert b.max_pos == 0.0

    def test_custom(self):
        b = SliderBinding(
            node="knob",
            default=0.5,
            direction=RangeDirection.VERTICAL,
            min_pos=1.5,
            max_pos=183.5,
        )
        assert b.default == 0.5
        assert b.direction == RangeDirection.VERTICAL
        assert b.min_pos == 1.5
        assert b.max_pos == 183.5

    def test_frozen(self):
        b = SliderBinding(node="indicator")
        with pytest.raises(AttributeError):
            b.node = "other"  # type: ignore[misc]


class TestEventMapping:
    def test_simple(self):
        e = EventMapping(name="play", source="encoder_press")
        assert e.direction is None
        assert e.max_duration_ms is None

    def test_with_direction(self):
        e = EventMapping(name="next", source="encoder_turn", direction="right")
        assert e.direction == "right"

    def test_with_duration(self):
        e = EventMapping(
            name="toggle", source="encoder_press_release", max_duration_ms=250
        )
        assert e.max_duration_ms == 250

    def test_with_hold_ms(self):
        e = EventMapping(name="hold", source="key_hold", hold_ms=500)
        assert e.hold_ms == 500

    def test_hold_ms_default_none(self):
        e = EventMapping(name="play", source="encoder_press")
        assert e.hold_ms is None

    def test_frozen(self):
        e = EventMapping(name="play", source="encoder_press")
        with pytest.raises(AttributeError):
            e.name = "other"  # type: ignore[misc]


class TestRegion:
    def test_basic(self):
        r = Region(
            name="card", x=0, y=0, width=197, height=98, events=("tap", "long_press")
        )
        assert r.name == "card"
        assert r.events == ("tap", "long_press")

    def test_empty_events(self):
        r = Region(name="bg", x=0, y=0, width=100, height=50)
        assert r.events == ()


class TestPackageSpec:
    def test_minimal(self):
        spec = PackageSpec(
            name="Test",
            type=PackageType.TOUCH_STRIP_CARD,
            version=1,
            svg_source="<svg></svg>",
        )
        assert spec.name == "Test"
        assert spec.bindings == {}
        assert spec.events == ()
        assert spec.regions == ()
        assert spec.assets == {}

    def test_frozen(self):
        spec = PackageSpec(
            name="Test",
            type=PackageType.KEY,
            version=1,
            svg_source="<svg></svg>",
        )
        with pytest.raises(AttributeError):
            spec.name = "other"  # type: ignore[misc]


class TestValidSets:
    def test_valid_sources(self):
        assert "encoder_press" in VALID_SOURCES
        assert "encoder_release" in VALID_SOURCES
        assert "encoder_press_release" in VALID_SOURCES
        assert "encoder_turn" in VALID_SOURCES
        assert "encoder_press_turn" in VALID_SOURCES
        assert "encoder_hold" in VALID_SOURCES
        assert "key_press" in VALID_SOURCES
        assert "key_release" in VALID_SOURCES
        assert "key_press_release" in VALID_SOURCES
        assert "key_hold" in VALID_SOURCES
        assert "tap" in VALID_SOURCES
        assert "long_press" in VALID_SOURCES

    def test_hold_sources(self):
        assert frozenset({"key_hold", "encoder_hold"}) == HOLD_SOURCES

    def test_valid_directions(self):
        assert frozenset({"left", "right"}) == VALID_DIRECTIONS

    def test_valid_region_events(self):
        assert frozenset({"tap", "long_press"}) == VALID_REGION_EVENTS


class TestListBinding:
    def test_defaults(self):
        b = ListBinding(node="pager")
        assert b.node == "pager"
        assert b.child_tag == "tspan"
        assert b.default_items == ()
        assert b.default_index == 0
        assert b.active_attrs == {}
        assert b.inactive_attrs == {}
        assert b.separator == ""
        assert b.icon_size == 16

    def test_custom(self):
        b = ListBinding(
            node="nav",
            child_tag="g",
            default_items=("Main", "Settings"),
            default_index=1,
            active_attrs={"fill": "#fff"},
            inactive_attrs={"fill": "#888"},
            separator=" · ",
            icon_size=14,
        )
        assert b.child_tag == "g"
        assert b.default_items == ("Main", "Settings")
        assert b.default_index == 1
        assert b.active_attrs == {"fill": "#fff"}
        assert b.separator == " · "
        assert b.icon_size == 14

    def test_no_active_index(self):
        b = ListBinding(node="pager", default_index=None)
        assert b.default_index is None

    def test_negative_one_index(self):
        b = ListBinding(node="pager", default_index=-1)
        assert b.default_index == -1

    def test_frozen(self):
        b = ListBinding(node="pager")
        with pytest.raises(AttributeError):
            b.node = "other"  # type: ignore[misc]


class TestBindingDefaultValue:
    """Each Binding subclass exposes a ``default_value()`` used by SvgRenderer."""

    def test_text_default_value(self):
        assert TextBinding(node="t", default="hi").default_value() == "hi"

    def test_image_default_value_is_none(self):
        from deux.dui.schema import ImageBinding

        assert ImageBinding(node="i").default_value() is None

    def test_image_is_force_dirty(self):
        from deux.dui.schema import ImageBinding

        assert ImageBinding.force_dirty is True

    def test_visibility_default_value(self):
        from deux.dui.schema import VisibilityBinding

        assert VisibilityBinding(node="v", default=False).default_value() is False

    def test_color_default_value(self):
        assert ColorBinding(node="c", default="#abcdef").default_value() == "#abcdef"

    def test_range_default_value(self):
        from deux.dui.schema import RangeBinding

        assert RangeBinding(node="r", default=0.42).default_value() == 0.42

    def test_slider_default_value(self):
        from deux.dui.schema import SliderBinding

        assert SliderBinding(node="s", default=0.3).default_value() == 0.3

    def test_toggle_default_value(self):
        from deux.dui.schema import ToggleBinding

        assert ToggleBinding(node_on="a", node_off="b", default=True).default_value() is True

    def test_iconify_default_value(self):
        from deux.dui.schema import IconifyBinding

        assert (
            IconifyBinding(node="i", size=16, default="mdi:home").default_value() == "mdi:home"
        )

    def test_transform_default_value(self):
        from deux.dui.schema import TransformBinding

        assert TransformBinding(node="t", default=0.25).default_value() == 0.25

    def test_css_class_default_value(self):
        assert CssClassBinding(node="x", default="cls").default_value() == "cls"

    def test_list_default_value(self):
        b = ListBinding(
            node="pager", default_items=("a", "b", "c"), default_index=1
        )
        assert b.default_value() == {"items": ["a", "b", "c"], "index": 1}


class TestListBindingCoerce:
    """ListBinding.coerce merges partial ``{"items"|"index"}`` payloads."""

    def test_coerce_items_only_preserves_index(self):
        b = ListBinding(node="pager")
        out = b.coerce({"items": ["x", "y"]}, {"items": ["a"], "index": 0})
        assert out == {"items": ["x", "y"], "index": 0}

    def test_coerce_index_only_preserves_items(self):
        b = ListBinding(node="pager")
        out = b.coerce({"index": 1}, {"items": ["a", "b"], "index": 0})
        assert out == {"items": ["a", "b"], "index": 1}

    def test_coerce_negative_one_normalised_to_none(self):
        b = ListBinding(node="pager")
        out = b.coerce({"index": -1}, {"items": ["a"], "index": 0})
        assert out["index"] is None

    def test_coerce_clamps_index_when_items_shrink(self):
        b = ListBinding(node="pager")
        out = b.coerce({"items": ["a"]}, {"items": ["a", "b", "c"], "index": 2})
        assert out == {"items": ["a"], "index": 0}

    def test_coerce_empty_items_clears_index(self):
        b = ListBinding(node="pager")
        out = b.coerce({"items": []}, {"items": ["a"], "index": 0})
        assert out == {"items": [], "index": None}

    def test_coerce_non_dict_returned_as_is(self):
        b = ListBinding(node="pager")
        assert b.coerce("plain", {"items": [], "index": None}) == "plain"
