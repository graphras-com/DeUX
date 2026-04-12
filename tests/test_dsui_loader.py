"""Tests for deckboard.dsui.loader — package loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from deckboard.dsui.loader import PackageError, load_all_packages, load_package
from deckboard.dsui.schema import (
    ColorBinding,
    ImageBinding,
    ImageFit,
    OverflowMode,
    PackageType,
    RangeBinding,
    RangeDirection,
    SliderBinding,
    TextBinding,
    VisibilityBinding,
)


class TestLoadPackageValid:
    """Test loading valid .dsui packages."""

    def test_loads_card_package(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        assert spec.name == "TestCard"
        assert spec.type == PackageType.TOUCH_STRIP_CARD
        assert spec.version == 1
        assert "<svg" in spec.svg_source

    def test_loads_key_package(self, key_dsui_path):
        spec = load_package(key_dsui_path)
        assert spec.name == "TestKey"
        assert spec.type == PackageType.KEY
        assert spec.version == 1

    def test_text_binding_parsed(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        b = spec.bindings["title"]
        assert isinstance(b, TextBinding)
        assert b.node == "title"
        assert b.default == "Default Title"
        assert b.max_width == 90
        assert b.overflow == OverflowMode.ELLIPSIS

    def test_text_binding_no_max_width(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        b = spec.bindings["artist"]
        assert isinstance(b, TextBinding)
        assert b.max_width is None

    def test_image_binding_parsed(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        b = spec.bindings["cover"]
        assert isinstance(b, ImageBinding)
        assert b.node == "cover"
        assert b.fit == ImageFit.COVER
        assert b.placeholder_node == "cover_placeholder"

    def test_visibility_binding_parsed(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        b = spec.bindings["overlay_visible"]
        assert isinstance(b, VisibilityBinding)
        assert b.default is True

    def test_color_binding_parsed(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        b = spec.bindings["accent_color"]
        assert isinstance(b, ColorBinding)
        assert b.attribute == "fill"
        assert b.default == "#ff0000"

    def test_range_binding_parsed(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        b = spec.bindings["progress"]
        assert isinstance(b, RangeBinding)
        assert b.node == "accent"
        assert b.default == 0.5
        assert b.direction == RangeDirection.HORIZONTAL

    def test_range_binding_vertical(self, tmp_path):
        pkg = tmp_path / "R.dsui"
        pkg.mkdir()
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar" height="80"/></svg>'
        )
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: R\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  level:\n    type: range\n    node: bar\n    direction: vertical\n    default: 1.0",
            encoding="utf-8",
        )
        spec = load_package(pkg)
        b = spec.bindings["level"]
        assert isinstance(b, RangeBinding)
        assert b.direction == RangeDirection.VERTICAL
        assert b.default == 1.0

    def test_slider_binding_parsed(self, tmp_path):
        pkg = tmp_path / "S.dsui"
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
        pkg = tmp_path / "SV.dsui"
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
        pkg = tmp_path / "SP.dsui"
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

    def test_events_parsed(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        names = [e.name for e in spec.events]
        assert "toggle_play" in names
        assert "next" in names
        assert "previous" in names
        assert "seek_forward" in names
        assert "seek_backward" in names

    def test_event_direction(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        next_evt = next(e for e in spec.events if e.name == "next")
        assert next_evt.direction == "right"

    def test_event_press_turn_direction(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        seek_fwd = next(e for e in spec.events if e.name == "seek_forward")
        seek_bwd = next(e for e in spec.events if e.name == "seek_backward")
        assert seek_fwd.source == "encoder_press_turn"
        assert seek_fwd.direction == "right"
        assert seek_bwd.source == "encoder_press_turn"
        assert seek_bwd.direction == "left"

    def test_event_duration(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        toggle = next(e for e in spec.events if e.name == "toggle_play")
        assert toggle.max_duration_ms == 250

    def test_regions_parsed(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        assert len(spec.regions) == 1
        r = spec.regions[0]
        assert r.name == "card"
        assert r.x == 0
        assert r.width == 197
        assert "tap" in r.events

    def test_assets_loaded(self, card_dsui_path):
        spec = load_package(card_dsui_path)
        assert "test_icon.png" in spec.assets
        assert len(spec.assets["test_icon.png"]) > 0

    def test_accepts_string_path(self, card_dsui_path):
        spec = load_package(str(card_dsui_path))
        assert spec.name == "TestCard"

    def test_key_events_parsed(self, key_dsui_path):
        spec = load_package(key_dsui_path)
        names = [e.name for e in spec.events]
        assert "activate" in names
        assert "hold" in names


class TestLoadPackageInvalid:
    """Test error handling for invalid packages."""

    def test_not_a_directory(self, tmp_path):
        fake = tmp_path / "notexist.dsui"
        with pytest.raises(PackageError, match="not a directory"):
            load_package(fake)

    def test_missing_manifest(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        with pytest.raises(PackageError, match="Missing manifest.yaml"):
            load_package(pkg)

    def test_invalid_yaml(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(": [\ninvalid", encoding="utf-8")
        with pytest.raises(PackageError, match="Invalid YAML"):
            load_package(pkg)

    def test_manifest_not_mapping(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text("- list_item", encoding="utf-8")
        with pytest.raises(PackageError, match="must be a YAML mapping"):
            load_package(pkg)

    def test_missing_name(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "type: Key\nversion: 1\nlayout: l.svg", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="missing or invalid 'name'"):
            load_package(pkg)

    def test_missing_type(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\nversion: 1\nlayout: l.svg", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="missing 'type'"):
            load_package(pkg)

    def test_invalid_type(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Widget\nversion: 1\nlayout: l.svg",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="Invalid package type"):
            load_package(pkg)

    def test_missing_version(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nlayout: l.svg", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="missing 'version'"):
            load_package(pkg)

    def test_invalid_version(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 0\nlayout: l.svg", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="positive integer"):
            load_package(pkg)

    def test_missing_layout(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1", encoding="utf-8"
        )
        with pytest.raises(PackageError, match="missing or invalid 'layout'"):
            load_package(pkg)

    def test_layout_file_not_found(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: missing.svg",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="Layout file not found"):
            load_package(pkg)

    def test_invalid_svg(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text("not xml at all {{{", encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="Invalid SVG"):
            load_package(pkg)

    def test_binding_missing_type(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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

    def test_image_placeholder_not_in_svg(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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

    def test_event_invalid_duration(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
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

    def test_event_hold_ms_required_for_key_hold(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: key_hold",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="hold_ms is required"):
            load_package(pkg)

    def test_event_hold_ms_required_for_encoder_hold(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "events:\n  - name: x\n    source: encoder_hold",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="hold_ms is required"):
            load_package(pkg)

    def test_event_hold_ms_invalid(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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

    def test_region_missing_field(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "regions:\n  r:\n    x: 0\n    y: 0\n    width: 100\n    height: 50\n    events: [swipe]",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="invalid event 'swipe'"):
            load_package(pkg)

    def test_bindings_not_mapping(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n    min_pos: left\n    max_pos: 100",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="min_pos must be a number"):
            load_package(pkg)

    def test_slider_binding_max_pos_not_number(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect id="bar"/></svg>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  bar:\n    type: slider\n    node: bar\n    min_pos: 0\n    max_pos: right",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="max_pos must be a number"):
            load_package(pkg)

    def test_slider_binding_min_greater_than_max(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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
        pkg = tmp_path / "Bad.dsui"
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

    def test_version_string_invalid(self, tmp_path):
        pkg = tmp_path / "Bad.dsui"
        pkg.mkdir()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
        (pkg / "layout.svg").write_text(svg, encoding="utf-8")
        (pkg / "manifest.yaml").write_text(
            "name: Bad\ntype: Key\nversion: abc\nlayout: layout.svg",
            encoding="utf-8",
        )
        with pytest.raises(PackageError, match="positive integer"):
            load_package(pkg)


class TestLoadAllPackages:
    def test_loads_multiple(self, dsui_packages_dir):
        packages = load_all_packages(dsui_packages_dir)
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

    def test_skips_non_dsui(self, tmp_path):
        (tmp_path / "regular_dir").mkdir()
        (tmp_path / "file.txt").write_text("hello")
        packages = load_all_packages(tmp_path)
        assert packages == {}


class TestLoadPackageNoBindingsOrEvents:
    """Test that a minimal package with no bindings, events, or regions loads."""

    def test_minimal_package(self, tmp_path):
        pkg = tmp_path / "Minimal.dsui"
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
