"""Tests for deckboard.dsui.schema — data model classes."""

from __future__ import annotations

import pytest

from deckboard.dsui.schema import (
    BindingType,
    ColorBinding,
    EventMapping,
    HOLD_SOURCES,
    ImageBinding,
    ImageFit,
    OverflowMode,
    PackageSpec,
    PackageType,
    Region,
    TextBinding,
    VALID_DIRECTIONS,
    VALID_REGION_EVENTS,
    VALID_SOURCES,
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


class TestColorBinding:
    def test_defaults(self):
        b = ColorBinding(node="bg")
        assert b.attribute == "fill"
        assert b.default == "#ffffff"

    def test_stroke(self):
        b = ColorBinding(node="border", attribute="stroke", default="#000000")
        assert b.attribute == "stroke"


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
        assert HOLD_SOURCES == frozenset({"key_hold", "encoder_hold"})

    def test_valid_directions(self):
        assert VALID_DIRECTIONS == frozenset({"left", "right"})

    def test_valid_region_events(self):
        assert VALID_REGION_EVENTS == frozenset({"tap", "long_press"})
