"""Tests for deux.dui.loader — package loading and validation."""

from __future__ import annotations

import logging

import pytest

from deux.dui.loader import PackageError, load_all_packages, load_package
from deux.dui.schema import (
    ColorBinding,
    CssClassBinding,
    IconifyBinding,
    ImageBinding,
    ImageFit,
    ListBinding,
    OverflowMode,
    PackageType,
    RangeBinding,
    RangeDirection,
    SliderBinding,
    TextBinding,
    ToggleBinding,
    VisibilityBinding,
)


class TestLoadPackageValid:
    """Test loading valid .dui packages."""

    def test_loads_card_package(self, card_dui_path):
        spec = load_package(card_dui_path)
        assert spec.name == "TestCard"
        assert spec.type == PackageType.TOUCH_STRIP_CARD
        assert spec.version == 1
        assert "<svg" in spec.svg_source
        assert spec.description == "A test card for audio playback"
        assert spec.author == "Test Author <test@example.com>"
        assert spec.category == "media"
        assert spec.tags == ("music", "test")

    def test_loads_key_package(self, key_dui_path):
        spec = load_package(key_dui_path)
        assert spec.name == "TestKey"
        assert spec.type == PackageType.KEY
        assert spec.version == 1

    def test_text_binding_parsed(self, card_dui_path):
        spec = load_package(card_dui_path)
        b = spec.bindings["title"]
        assert isinstance(b, TextBinding)
        assert b.node == "title"
        assert b.default == "Default Title"
        assert b.max_width == 90
        assert b.overflow == OverflowMode.ELLIPSIS

    def test_text_binding_no_max_width(self, card_dui_path):
        spec = load_package(card_dui_path)
        b = spec.bindings["artist"]
        assert isinstance(b, TextBinding)
        assert b.max_width is None

    def test_text_binding_wrap_default_false(self, card_dui_path):
        spec = load_package(card_dui_path)
        b = spec.bindings["title"]
        assert isinstance(b, TextBinding)
        assert b.wrap is False
        assert b.max_height is None
        assert b.line_height is None

    def test_text_binding_wrap_true(self, tmp_path):
        pkg = tmp_path / "Wrap.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Wrap\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  label:\n    type: text\n    node: t\n"
            "    max_width: 90\n    wrap: true\n    max_height: 60\n"
            "    line_height: 18.0",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["label"]
        assert isinstance(b, TextBinding)
        assert b.wrap is True
        assert b.max_width == 90
        assert b.max_height == 60
        assert b.line_height == 18.0

    def test_text_binding_wrap_without_max_height(self, tmp_path):
        """wrap=true without max_height is valid (unlimited vertical space)."""
        pkg = tmp_path / "WrapNoH.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: WrapNoH\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  label:\n    type: text\n    node: t\n"
            "    max_width: 90\n    wrap: true",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["label"]
        assert isinstance(b, TextBinding)
        assert b.wrap is True
        assert b.max_height is None
        assert b.line_height is None

    def test_image_binding_parsed(self, card_dui_path):
        spec = load_package(card_dui_path)
        b = spec.bindings["cover"]
        assert isinstance(b, ImageBinding)
        assert b.node == "cover"
        assert b.fit == ImageFit.COVER
        assert b.placeholder_node == "cover_placeholder"

    def test_visibility_binding_parsed(self, card_dui_path):
        spec = load_package(card_dui_path)
        b = spec.bindings["overlay_visible"]
        assert isinstance(b, VisibilityBinding)
        assert b.default is True

    def test_color_binding_parsed(self, card_dui_path):
        spec = load_package(card_dui_path)
        b = spec.bindings["accent_color"]
        assert isinstance(b, ColorBinding)
        assert b.attribute == "fill"
        assert b.default == "#ff0000"

    def test_css_class_binding_parsed(self, tmp_path):
        pkg = tmp_path / "CC.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="card"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: CC\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  style:\n    type: css_class\n    node: card\n"
            "    default: active",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["style"]
        assert isinstance(b, CssClassBinding)
        assert b.node == "card"
        assert b.default == "active"

    def test_css_class_binding_default_empty(self, tmp_path):
        pkg = tmp_path / "CC2.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="card"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: CC2\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  style:\n    type: css_class\n    node: card",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["style"]
        assert isinstance(b, CssClassBinding)
        assert b.default == ""

    def test_range_binding_parsed(self, card_dui_path):
        spec = load_package(card_dui_path)
        b = spec.bindings["progress"]
        assert isinstance(b, RangeBinding)
        assert b.node == "accent"
        assert b.default == 0.5
        assert b.direction == RangeDirection.HORIZONTAL

    def test_range_binding_vertical(self, tmp_path):
        pkg = tmp_path / "R.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar" height="80"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: R\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  level:\n    type: range\n    node: bar\n"
            "    direction: vertical\n    default: 1.0",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["level"]
        assert isinstance(b, RangeBinding)
        assert b.direction == RangeDirection.VERTICAL
        assert b.default == 1.0

    def test_toggle_binding_parsed(self, tmp_path):
        pkg = tmp_path / "T.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path id="icon_on" d="M0 0"/><path id="icon_off" d="M0 0"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: T\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  lights:\n    type: toggle\n    node_on: icon_on\n"
            "    node_off: icon_off\n    default: true",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["lights"]
        assert isinstance(b, ToggleBinding)
        assert b.node_on == "icon_on"
        assert b.node_off == "icon_off"
        assert b.default is True

    def test_toggle_binding_default_false(self, tmp_path):
        pkg = tmp_path / "TF.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path id="icon_on" d="M0 0"/><path id="icon_off" d="M0 0"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: TF\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  state:\n    type: toggle\n    node_on: icon_on\n    node_off: icon_off",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["state"]
        assert isinstance(b, ToggleBinding)
        assert b.default is False

    def test_iconify_binding_parsed(self, tmp_path):
        pkg = tmp_path / "I.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: I\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    node: icon\n"
            '    size: 55\n    default: "line-md:home"',
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["icon"]
        assert isinstance(b, IconifyBinding)
        assert b.node == "icon"
        assert b.size == 55
        assert b.default == "line-md:home"

    def test_iconify_binding_default_empty(self, tmp_path):
        pkg = tmp_path / "IE.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: IE\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    node: icon\n    size: 24",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["icon"]
        assert isinstance(b, IconifyBinding)
        assert b.size == 24
        assert b.default == ""

    def test_slider_binding_parsed(self, tmp_path):
        pkg = tmp_path / "S.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect id="knob" x="5" y="10" width="4" height="11"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: S\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  brightness:\n    type: slider\n    node: knob\n"
            "    default: 0.5\n    direction: horizontal\n    min_pos: 1.5\n    max_pos: 183.5",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["brightness"]
        assert isinstance(b, SliderBinding)
        assert b.node == "knob"
        assert b.default == 0.5
        assert b.direction == RangeDirection.HORIZONTAL
        assert b.min_pos == 1.5
        assert b.max_pos == 183.5

    def test_slider_binding_vertical(self, tmp_path):
        pkg = tmp_path / "SV.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect id="knob" x="5" y="10" width="4" height="11"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: SV\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  level:\n    type: slider\n    node: knob\n"
            "    direction: vertical\n    min_pos: 5.0\n    max_pos: 80.0",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["level"]
        assert isinstance(b, SliderBinding)
        assert b.direction == RangeDirection.VERTICAL
        assert b.min_pos == 5.0
        assert b.max_pos == 80.0

    def test_slider_binding_equal_min_max(self, tmp_path):
        """min_pos == max_pos is valid (indicator is pinned to one position)."""
        pkg = tmp_path / "SP.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect id="dot" x="50" y="10" width="4" height="4"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: SP\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  pin:\n    type: slider\n    node: dot\n"
            "    min_pos: 50.0\n    max_pos: 50.0",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["pin"]
        assert isinstance(b, SliderBinding)
        assert b.min_pos == b.max_pos == 50.0

    def test_events_parsed(self, card_dui_path):
        spec = load_package(card_dui_path)
        names = [e.name for e in spec.events]
        assert "toggle_play" in names
        assert "next" in names
        assert "previous" in names
        assert "seek_forward" in names
        assert "seek_backward" in names

    def test_event_direction(self, card_dui_path):
        spec = load_package(card_dui_path)
        next_evt = next(e for e in spec.events if e.name == "next")
        assert next_evt.direction == "right"

    def test_event_press_turn_direction(self, card_dui_path):
        spec = load_package(card_dui_path)
        seek_fwd = next(e for e in spec.events if e.name == "seek_forward")
        seek_bwd = next(e for e in spec.events if e.name == "seek_backward")
        assert seek_fwd.source == "encoder_press_turn"
        assert seek_fwd.direction == "right"
        assert seek_bwd.source == "encoder_press_turn"
        assert seek_bwd.direction == "left"

    def test_event_duration(self, card_dui_path):
        spec = load_package(card_dui_path)
        toggle = next(e for e in spec.events if e.name == "toggle_play")
        assert toggle.max_duration_ms == 250

    def test_regions_parsed(self, card_dui_path):
        spec = load_package(card_dui_path)
        assert len(spec.regions) == 1
        r = spec.regions[0]
        assert r.name == "card"
        assert r.x == 0
        assert r.width == 197
        assert "tap" in r.events

    def test_assets_loaded(self, card_dui_path):
        spec = load_package(card_dui_path)
        assert "test_icon.png" in spec.assets
        assert len(spec.assets["test_icon.png"]) > 0

    def test_accepts_string_path(self, card_dui_path):
        spec = load_package(str(card_dui_path))
        assert spec.name == "TestCard"

    def test_key_events_parsed(self, key_dui_path):
        spec = load_package(key_dui_path)
        names = [e.name for e in spec.events]
        assert "activate" in names
        assert "hold" in names


class TestLoadPackageInvalid:
    """Test error handling for invalid packages."""

    def test_not_a_directory(self, tmp_path):
        fake = tmp_path / "notexist.dui"
        with pytest.raises(PackageError, match="not a directory"):
            load_package(fake)

    def test_missing_manifest(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        with pytest.raises(PackageError, match="Missing manifest.yaml"):
            load_package(pkg)

    def test_invalid_yaml(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(": [\ninvalid", encoding="utf-8")
        with pytest.raises(PackageError, match="Invalid YAML"):
            load_package(pkg)

    def test_manifest_not_mapping(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text("- list_item", encoding="utf-8")
        with pytest.raises(PackageError, match="must be a YAML mapping"):
            load_package(pkg)

    def test_missing_name(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "type: Key\nversion: 1\nlayout: l.svg", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="missing or invalid 'name'"):
            load_package(pkg)

    def test_missing_type(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\nversion: 1\nlayout: l.svg", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="missing 'type'"):
            load_package(pkg)

    def test_invalid_type(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Widget\nversion: 1\nlayout: l.svg",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="Invalid package type"):
            load_package(pkg)

    def test_missing_version(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nlayout: l.svg", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="missing 'version'"):
            load_package(pkg)

    def test_invalid_version(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 0\nlayout: l.svg", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="positive integer"):
            load_package(pkg)

    def test_missing_layout(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="missing or invalid 'layout'"):
            load_package(pkg)

    def test_layout_file_not_found(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: missing.svg",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="Layout file not found"):
            load_package(pkg)

    def test_invalid_svg(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text("not xml at all {{{", encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="Invalid SVG"):
            load_package(pkg)

    def test_binding_missing_type(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    node: t",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'type'"):
            load_package(pkg)

    def test_binding_invalid_type(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: animation\n    node: t",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid type 'animation'"):
            load_package(pkg)

    def test_binding_missing_node(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'node'"):
            load_package(pkg)

    def test_binding_node_not_in_svg(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  x:\n    type: text\n    node: missing",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="does not exist in the SVG"):
            load_package(pkg)

    def test_binding_invalid_overflow(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text\n    node: t\n    overflow: wrap",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid overflow"):
            load_package(pkg)

    def test_binding_invalid_fit(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><image id="img"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  img:\n    type: image\n    node: img\n    fit: stretch",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid fit"):
            load_package(pkg)

    def test_css_class_binding_non_string_default(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="card"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  style:\n    type: css_class\n    node: card\n"
            "    default: 42",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="default must be a string"):
            load_package(pkg)

    def test_image_placeholder_not_in_svg(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><image id="img"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  img:\n    type: image\n    node: img\n    placeholder_node: ghost",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="placeholder_node"):
            load_package(pkg)

    def test_event_missing_name(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - source: key_press",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'name'"):
            load_package(pkg)

    def test_event_missing_source(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'source'"):
            load_package(pkg)

    def test_event_invalid_source(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: button_click",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid source"):
            load_package(pkg)

    def test_event_invalid_direction(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_turn\n    direction: up",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid direction"):
            load_package(pkg)

    def test_event_max_duration_ms_defaults_for_press_release(self, tmp_path):
        pkg = tmp_path / "Good.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Good\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: key_press_release",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        ev = next(e for e in spec.events if e.name == "x")
        assert ev.max_duration_ms == 500

    def test_event_invalid_duration(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_press_release\n    max_duration_ms: -1",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="positive integer"):
            load_package(pkg)

    def test_event_hold_ms_defaults_for_key_hold(self, tmp_path):
        pkg = tmp_path / "Good.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Good\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: key_hold",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        ev = next(e for e in spec.events if e.name == "x")
        assert ev.hold_ms == 500

    def test_event_hold_ms_defaults_for_encoder_hold(self, tmp_path):
        pkg = tmp_path / "Good.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Good\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_hold",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        ev = next(e for e in spec.events if e.name == "x")
        assert ev.hold_ms == 500

    def test_event_hold_ms_invalid(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: key_hold\n    hold_ms: -1",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="hold_ms must be a positive integer"):
            load_package(pkg)

    def test_event_hold_ms_zero(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: key_hold\n    hold_ms: 0",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="hold_ms must be a positive integer"):
            load_package(pkg)

    def test_event_hold_ms_not_allowed_on_other_sources(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: key_press\n    hold_ms: 500",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="hold_ms is only valid for"):
            load_package(pkg)

    def test_duplicate_event_name(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: dup\n    source: key_press\n  - name: dup\n    source: key_release",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="Duplicate event name"):
            load_package(pkg)

    def test_event_accumulate_encoder_turn(self, tmp_path):
        pkg = tmp_path / "Good.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Good\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: vol_up\n    source: encoder_turn\n"
            "    direction: right\n    accumulate: true",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        ev = next(e for e in spec.events if e.name == "vol_up")
        assert ev.accumulate is True
        assert ev.accumulate_delay is None
        assert ev.accumulate_max_steps is None

    def test_event_accumulate_encoder_press_turn(self, tmp_path):
        pkg = tmp_path / "Good.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Good\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: seek\n    source: encoder_press_turn\n"
            "    accumulate: true",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        ev = next(e for e in spec.events if e.name == "seek")
        assert ev.accumulate is True

    def test_event_accumulate_with_delay_and_max_steps(self, tmp_path):
        pkg = tmp_path / "Good.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Good\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: vol\n    source: encoder_turn\n"
            "    accumulate: true\n    accumulate_delay: 0.1\n"
            "    accumulate_max_steps: 5",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        ev = next(e for e in spec.events if e.name == "vol")
        assert ev.accumulate is True
        assert ev.accumulate_delay == 0.1
        assert ev.accumulate_max_steps == 5

    def test_event_accumulate_invalid_source(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: key_press\n    accumulate: true",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="accumulate is only valid for"):
            load_package(pkg)

    def test_event_accumulate_delay_without_accumulate(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_turn\n"
            "    accumulate_delay: 0.1",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="accumulate_delay requires accumulate"):
            load_package(pkg)

    def test_event_accumulate_max_steps_without_accumulate(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_turn\n"
            "    accumulate_max_steps: 5",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="accumulate_max_steps requires accumulate"):
            load_package(pkg)

    def test_event_accumulate_delay_not_positive(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_turn\n"
            "    accumulate: true\n    accumulate_delay: -1",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="accumulate_delay must be a positive number"):
            load_package(pkg)

    def test_event_accumulate_max_steps_not_positive(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_turn\n"
            "    accumulate: true\n    accumulate_max_steps: 0",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="accumulate_max_steps must be a positive integer"):
            load_package(pkg)

    def test_event_accumulate_max_steps_boolean_rejected(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_turn\n"
            "    accumulate: true\n    accumulate_max_steps: true",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="accumulate_max_steps must be a positive integer"):
            load_package(pkg)

    def test_region_missing_field(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "regions:\n  r:\n    x: 0\n    y: 0\n    width: 100",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'height'"):
            load_package(pkg)

    def test_region_negative_value(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "regions:\n  r:\n    x: -1\n    y: 0\n    width: 100\n    height: 50",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="non-negative integer"):
            load_package(pkg)

    def test_region_invalid_event(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "regions:\n  r:\n    x: 0\n    y: 0\n    width: 100\n"
            "    height: 50\n    events: [swipe]",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid event 'swipe'"):
            load_package(pkg)

    def test_bindings_not_mapping(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\nbindings: [bad]",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a mapping"):
            load_package(pkg)

    def test_events_not_list(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\nevents: bad",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a list"):
            load_package(pkg)

    def test_event_entry_not_mapping(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - just_a_string",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a mapping"):
            load_package(pkg)

    def test_regions_not_mapping(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\nregions: [bad]",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a mapping"):
            load_package(pkg)

    def test_region_entry_not_mapping(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "regions:\n  r: bad_value",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a mapping"):
            load_package(pkg)

    def test_region_events_not_list(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "regions:\n  r:\n    x: 0\n    y: 0\n    width: 100\n    height: 50\n    events: tap",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a list"):
            load_package(pkg)

    def test_binding_entry_not_mapping(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t: just_a_string",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a mapping"):
            load_package(pkg)

    def test_range_binding_invalid_direction(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: range\n    node: bar\n    direction: diagonal",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid direction"):
            load_package(pkg)

    def test_range_binding_default_out_of_range(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: range\n    node: bar\n    default: 1.5",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="between 0.0 and 1.0"):
            load_package(pkg)

    def test_range_binding_default_negative(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: range\n    node: bar\n    default: -0.1",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="between 0.0 and 1.0"):
            load_package(pkg)

    def test_range_binding_default_not_number(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: range\n    node: bar\n    default: high",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a number"):
            load_package(pkg)

    def test_slider_binding_missing_min_pos(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n    max_pos: 100",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'min_pos'"):
            load_package(pkg)

    def test_slider_binding_missing_max_pos(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n    min_pos: 0",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'max_pos'"):
            load_package(pkg)

    def test_slider_binding_min_pos_not_number(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n"
            "    min_pos: left\n    max_pos: 100",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="min_pos must be a number"):
            load_package(pkg)

    def test_slider_binding_max_pos_not_number(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n"
            "    min_pos: 0\n    max_pos: right",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="max_pos must be a number"):
            load_package(pkg)

    def test_slider_binding_min_greater_than_max(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n    min_pos: 100\n    max_pos: 10",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="min_pos.*must be <= max_pos"):
            load_package(pkg)

    def test_slider_binding_invalid_direction(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n"
            "    direction: diagonal\n    min_pos: 0\n    max_pos: 100",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid direction"):
            load_package(pkg)

    def test_slider_binding_default_out_of_range(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n"
            "    default: 1.5\n    min_pos: 0\n    max_pos: 100",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="between 0.0 and 1.0"):
            load_package(pkg)

    def test_slider_binding_default_not_number(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n"
            "    default: high\n    min_pos: 0\n    max_pos: 100",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="must be a number"):
            load_package(pkg)

    def test_toggle_binding_missing_node_on(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><path id="off" d="M0 0"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: toggle\n    node_off: off",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'node_on'"):
            load_package(pkg)

    def test_toggle_binding_missing_node_off(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path id="icon_on" d="M0 0"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: toggle\n    node_on: icon_on",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'node_off'"):
            load_package(pkg)

    def test_toggle_binding_node_on_not_in_svg(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path id="icon_off" d="M0 0"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: toggle\n    node_on: missing\n    node_off: icon_off",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="node_on 'missing'.*does not exist"):
            load_package(pkg)

    def test_toggle_binding_node_off_not_in_svg(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path id="icon_on" d="M0 0"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: toggle\n    node_on: icon_on\n    node_off: missing",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="node_off 'missing'.*does not exist"):
            load_package(pkg)

    def test_text_binding_wrap_without_max_width(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text\n    node: t\n    wrap: true",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="max_width is required"):
            load_package(pkg)

    def test_text_binding_max_height_invalid(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text\n    node: t\n"
            "    max_width: 90\n    wrap: true\n    max_height: -5",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="max_height must be a positive integer"):
            load_package(pkg)

    def test_text_binding_max_height_zero(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text\n    node: t\n"
            "    max_width: 90\n    wrap: true\n    max_height: 0",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="max_height must be a positive integer"):
            load_package(pkg)

    def test_text_binding_max_height_not_int(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text\n    node: t\n"
            "    max_width: 90\n    wrap: true\n    max_height: big",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="max_height must be a positive integer"):
            load_package(pkg)

    def test_text_binding_line_height_invalid(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text\n    node: t\n"
            "    max_width: 90\n    wrap: true\n    line_height: -1.0",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="line_height must be a positive number"):
            load_package(pkg)

    def test_text_binding_line_height_zero(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text\n    node: t\n"
            "    max_width: 90\n    wrap: true\n    line_height: 0",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="line_height must be a positive number"):
            load_package(pkg)

    def test_text_binding_line_height_not_number(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><text id="t"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  t:\n    type: text\n    node: t\n"
            "    max_width: 90\n    wrap: true\n    line_height: wide",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="line_height must be a positive number"):
            load_package(pkg)

    def test_version_string_invalid(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: abc\nlayout: layout.svg",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="positive integer"):
            load_package(pkg)

    def test_iconify_binding_missing_size(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    node: icon",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'size'"):
            load_package(pkg)

    def test_iconify_binding_size_not_int(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    node: icon\n    size: big",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="size must be a positive integer"):
            load_package(pkg)

    def test_iconify_binding_size_zero(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    node: icon\n    size: 0",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="size must be a positive integer"):
            load_package(pkg)

    def test_iconify_binding_size_negative(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    node: icon\n    size: -10",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="size must be a positive integer"):
            load_package(pkg)

    def test_iconify_binding_size_bool_rejected(self, tmp_path):
        """YAML's ``true`` coerces to int(1) in Python; reject explicitly."""
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    node: icon\n    size: true",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="size must be a positive integer"):
            load_package(pkg)

    def test_iconify_binding_missing_node(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    size: 55",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="missing 'node'"):
            load_package(pkg)

    def test_iconify_binding_node_not_in_svg(self, tmp_path):
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g id="icon"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  icon:\n    type: iconify\n    node: missing\n    size: 55",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="does not exist in the SVG"):
            load_package(pkg)


class TestLoadAllPackages:
    def test_loads_multiple(self, dui_packages_dir):
        packages = load_all_packages(dui_packages_dir)
        assert "TestCard" in packages
        assert "TestKey" in packages
        assert len(packages) == 2

    def test_not_a_directory(self, tmp_path):
        fake = tmp_path / "nope"
        with pytest.raises(PackageError, match="Not a directory"):
            load_all_packages(fake)

    def test_empty_directory(self, tmp_path):
        packages = load_all_packages(tmp_path)
        assert packages == {}

    def test_skips_non_dui(self, tmp_path):
        (tmp_path / "regular_dir").mkdir()
        (tmp_path / "file.txt").write_text("hello")
        packages = load_all_packages(tmp_path)
        assert packages == {}


class TestLoadPackageNoBindingsOrEvents:
    """Test that a minimal package with no bindings, events, or regions loads."""

    def test_minimal_package(self, tmp_path):
        pkg = tmp_path / "Minimal.dui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Minimal\ntype: Key\nversion: 1\nlayout: layout.svg",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        assert spec.name == "Minimal"
        assert spec.bindings == {}
        assert spec.events == ()
        assert spec.regions == ()
        assert spec.assets == {}


class TestLoadPackageMetadata:
    """Test parsing of optional metadata fields."""

    _SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120"/>'
    _BASE = "name: M\ntype: Key\nversion: 1\nlayout: layout.svg\n"

    def _make_pkg(self, tmp_path, extra_yaml: str) -> str:
        pkg = tmp_path / "M.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(self._BASE + extra_yaml, encoding="utf-8")
        return str(pkg)

    def test_metadata_defaults_to_none(self, tmp_path):
        spec = load_package(self._make_pkg(tmp_path, ""))
        assert spec.description is None
        assert spec.author is None
        assert spec.license is None
        assert spec.tags == ()
        assert spec.category is None
        assert spec.url is None
        assert spec.icon is None
        assert spec.min_deux is None
        assert spec.device == ()

    def test_all_metadata_parsed(self, tmp_path):
        extra = (
            'description: "A great package"\n'
            'author: "Jane Doe"\n'
            'license: MIT\n'
            "tags: [media, music]\n"
            "category: media\n"
            'url: "https://example.com"\n'
            'icon: "assets/icon.png"\n'
            'min_deux: "0.5.0"\n'
            "device: [StreamDeckPlus]\n"
        )
        pkg = tmp_path / "M.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(self._BASE + extra, encoding="utf-8")
        assets = pkg / "assets"
        assets.mkdir()
        (assets / "icon.png").write_bytes(b"PNG")
        spec = load_package(pkg)
        assert spec.description == "A great package"
        assert spec.author == "Jane Doe"
        assert spec.license == "MIT"
        assert spec.tags == ("media", "music")
        assert spec.category == "media"
        assert spec.url == "https://example.com"
        assert spec.icon == "assets/icon.png"
        assert spec.min_deux == "0.5.0"
        assert spec.device == ("StreamDeckPlus",)

    def test_invalid_category(self, tmp_path):
        with pytest.raises(PackageError, match="Invalid category"):
            load_package(self._make_pkg(tmp_path, "category: invalid_cat"))

    def test_description_not_string(self, tmp_path):
        with pytest.raises(PackageError, match="'description' must be a string"):
            load_package(self._make_pkg(tmp_path, "description: 123"))

    def test_author_not_string(self, tmp_path):
        with pytest.raises(PackageError, match="'author' must be a string"):
            load_package(self._make_pkg(tmp_path, "author: 123"))

    def test_tags_not_list(self, tmp_path):
        with pytest.raises(PackageError, match="'tags' must be a list"):
            load_package(self._make_pkg(tmp_path, "tags: bad"))

    def test_tags_empty_string(self, tmp_path):
        with pytest.raises(PackageError, match="non-empty string"):
            load_package(self._make_pkg(tmp_path, 'tags: [""]'))

    def test_device_not_list(self, tmp_path):
        with pytest.raises(PackageError, match="'device' must be a list"):
            load_package(self._make_pkg(tmp_path, "device: StreamDeckPlus"))

    def test_device_empty_string(self, tmp_path):
        with pytest.raises(PackageError, match="non-empty string"):
            load_package(self._make_pkg(tmp_path, 'device: [""]'))

    def test_license_not_string(self, tmp_path):
        with pytest.raises(PackageError, match="'license' must be a string"):
            load_package(self._make_pkg(tmp_path, "license: 123"))

    def test_url_not_string(self, tmp_path):
        with pytest.raises(PackageError, match="'url' must be a string"):
            load_package(self._make_pkg(tmp_path, "url: 123"))

    def test_icon_not_string(self, tmp_path):
        with pytest.raises(PackageError, match="'icon' must be a string"):
            load_package(self._make_pkg(tmp_path, "icon: 123"))

    def test_min_deux_not_string(self, tmp_path):
        with pytest.raises(PackageError, match="'min_deux' must be a string"):
            load_package(self._make_pkg(tmp_path, "min_deux: 1"))

    def test_category_not_string(self, tmp_path):
        with pytest.raises(PackageError, match="'category' must be a string"):
            load_package(self._make_pkg(tmp_path, "category: 123"))

    def test_unknown_keys_logged(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING):
            load_package(self._make_pkg(tmp_path, "desciption: typo"))
        assert "unknown manifest keys" in caplog.text


class TestListBindingLoader:
    """Tests for loading the ``list`` binding type."""

    _SVG = '<svg xmlns="http://www.w3.org/2000/svg"><text id="pager" x="50"/></svg>'

    def _make_pkg(self, tmp_path, bindings_yaml: str, *, name: str = "L"):
        pkg = tmp_path / f"{name}.dui"
        pkg.mkdir(exist_ok=True)
        (pkg / "layout.svg").write_text(self._SVG, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            f"name: {name}\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            f"bindings:\n{bindings_yaml}",
            encoding="utf-8",
        )
        return pkg

    def test_valid_full(self, tmp_path):
        spec = load_package(
            self._make_pkg(
                tmp_path,
                "  nav:\n    type: list\n    node: pager\n    child_tag: tspan\n"
                "    default_items:\n      - Main\n      - Settings\n"
                "    default_index: 1\n"
                "    active_attrs:\n      fill: '#ffffff'\n      font-weight: bold\n"
                "    inactive_attrs:\n      fill: '#888888'\n"
                "    separator: ' · '\n    icon_size: 14\n",
            )
        )
        b = spec.bindings["nav"]
        assert isinstance(b, ListBinding)
        assert b.node == "pager"
        assert b.child_tag == "tspan"
        assert b.default_items == ("Main", "Settings")
        assert b.default_index == 1
        assert b.active_attrs == {"fill": "#ffffff", "font-weight": "bold"}
        assert b.inactive_attrs == {"fill": "#888888"}
        assert b.separator == " · "
        assert b.icon_size == 14

    def test_valid_minimal(self, tmp_path):
        spec = load_package(
            self._make_pkg(tmp_path, "  nav:\n    type: list\n    node: pager\n")
        )
        b = spec.bindings["nav"]
        assert isinstance(b, ListBinding)
        assert b.default_items == ()
        assert b.default_index == 0
        assert b.separator == ""
        assert b.icon_size == 16

    def test_default_index_none(self, tmp_path):
        spec = load_package(
            self._make_pkg(
                tmp_path,
                "  nav:\n    type: list\n    node: pager\n    default_index: null\n",
            )
        )
        b = spec.bindings["nav"]
        assert isinstance(b, ListBinding)
        assert b.default_index is None

    def test_default_index_negative_one(self, tmp_path):
        spec = load_package(
            self._make_pkg(
                tmp_path,
                "  nav:\n    type: list\n    node: pager\n    default_index: -1\n",
            )
        )
        b = spec.bindings["nav"]
        assert isinstance(b, ListBinding)
        assert b.default_index == -1

    def test_default_index_out_of_range(self, tmp_path):
        with pytest.raises(PackageError, match="default_index 5 is out of range"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n"
                    "    default_items:\n      - A\n      - B\n"
                    "    default_index: 5\n",
                )
            )

    def test_default_index_not_int(self, tmp_path):
        with pytest.raises(PackageError, match="default_index must be an integer"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n"
                    "    default_index: 'abc'\n",
                )
            )

    def test_default_index_bool_rejected(self, tmp_path):
        with pytest.raises(PackageError, match="default_index must be an integer"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n"
                    "    default_index: true\n",
                )
            )

    def test_child_tag_empty(self, tmp_path):
        with pytest.raises(PackageError, match="child_tag must be a non-empty string"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n    child_tag: ''\n",
                )
            )

    def test_default_items_not_list(self, tmp_path):
        with pytest.raises(PackageError, match="default_items must be a list"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n"
                    "    default_items: notalist\n",
                )
            )

    def test_default_items_non_string_element(self, tmp_path):
        with pytest.raises(PackageError, match="default_items\\[1\\] must be a string"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n"
                    "    default_items:\n      - ok\n      - 123\n",
                )
            )

    def test_active_attrs_not_dict(self, tmp_path):
        with pytest.raises(PackageError, match="active_attrs must be a mapping"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n"
                    "    active_attrs: notadict\n",
                )
            )

    def test_active_attrs_non_string_value(self, tmp_path):
        with pytest.raises(PackageError, match="active_attrs\\['fill'\\] must be a string"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n"
                    "    active_attrs:\n      fill: 123\n",
                )
            )

    def test_icon_size_not_positive(self, tmp_path):
        with pytest.raises(PackageError, match="icon_size must be a positive integer"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n    icon_size: 0\n",
                )
            )

    def test_icon_size_bool_rejected(self, tmp_path):
        with pytest.raises(PackageError, match="icon_size must be a positive integer"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n    icon_size: true\n",
                )
            )

    def test_separator_not_string(self, tmp_path):
        with pytest.raises(PackageError, match="separator must be a string"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: pager\n    separator: 123\n",
                )
            )

    def test_node_not_in_svg(self, tmp_path):
        with pytest.raises(PackageError, match="does not exist in the SVG"):
            load_package(
                self._make_pkg(
                    tmp_path,
                    "  nav:\n    type: list\n    node: missing\n",
                )
            )

    def test_icon_items(self, tmp_path):
        """Items with icon: prefix are valid strings."""
        spec = load_package(
            self._make_pkg(
                tmp_path,
                "  nav:\n    type: list\n    node: pager\n"
                "    default_items:\n      - Main\n      - 'icon:mdi:cog'\n"
                "    default_index: 0\n",
            )
        )
        b = spec.bindings["nav"]
        assert isinstance(b, ListBinding)
        assert b.default_items == ("Main", "icon:mdi:cog")
