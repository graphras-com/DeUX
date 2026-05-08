"""Tests for the transform binding (rotate)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from deckui.dui.loader import PackageError, load_package
from deckui.dui.schema import (
    RotateTransform,
    TransformBinding,
    TransformKind,
)
from deckui.dui.svg_renderer import SvgRenderer


# ─── Fixtures ────────────────────────────────────────────────────────────────

_TRANSFORM_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
  <rect id="needle" x="90" y="10" width="20" height="80"/>
</svg>
"""

_TRANSFORM_SVG_NO_DIMS = """\
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
  <polyline id="arrow" points="0,0 5,-5 0,-100 -5,-5"/>
</svg>
"""


def _make_transform_package(
    tmp_path: Path,
    transforms: list[dict[str, Any]],
    default: float = 0.0,
    svg: str = _TRANSFORM_SVG,
    node: str = "needle",
) -> Path:
    """Create a minimal .dui package with a transform binding."""
    pkg = tmp_path / "Transform.dui"
    pkg.mkdir()
    (pkg / "layout.svg").write_text(svg, encoding="utf-8")

    import yaml

    manifest = {
        "name": "Transform",
        "type": "TouchStripCard",
        "version": 1,
        "layout": "layout.svg",
        "bindings": {
            "gauge": {
                "type": "transform",
                "node": node,
                "default": default,
                "transforms": transforms,
            }
        },
    }
    (pkg / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")
    return pkg


# ─── Schema tests ────────────────────────────────────────────────────────────


class TestTransformSchema:
    """Tests for transform binding dataclasses."""

    def test_rotate_transform_defaults(self):
        """RotateTransform has sensible defaults."""
        rt = RotateTransform()
        assert rt.from_angle == 0.0
        assert rt.to_angle == 360.0
        assert rt.origin == "center"

    def test_transform_binding_construction(self):
        """TransformBinding can be constructed with transforms."""
        rt = RotateTransform(from_angle=-50, to_angle=50, origin="100 100")
        tb = TransformBinding(node="needle", default=0.5, transforms=(rt,))
        assert tb.node == "needle"
        assert tb.default == 0.5
        assert len(tb.transforms) == 1
        assert tb.transforms[0].from_angle == -50

    def test_transform_kind_enum(self):
        """TransformKind has rotate value."""
        assert TransformKind.ROTATE.value == "rotate"


# ─── Loader tests ────────────────────────────────────────────────────────────


class TestTransformLoader:
    """Tests for transform binding parsing from manifest."""

    def test_load_valid_rotate(self, tmp_path: Path):
        """Valid rotate transform loads correctly."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[{"kind": "rotate", "from": 0, "to": 270, "origin": "center"}],
            default=0.4,
        )
        spec = load_package(pkg_path)
        binding = spec.bindings["gauge"]
        assert isinstance(binding, TransformBinding)
        assert binding.default == 0.4
        assert len(binding.transforms) == 1
        assert isinstance(binding.transforms[0], RotateTransform)
        assert binding.transforms[0].from_angle == 0.0
        assert binding.transforms[0].to_angle == 270.0
        assert binding.transforms[0].origin == "center"

    def test_load_rotate_defaults(self, tmp_path: Path):
        """Rotate transform uses defaults for from/to/origin."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[{"kind": "rotate"}],
        )
        spec = load_package(pkg_path)
        binding = spec.bindings["gauge"]
        assert isinstance(binding, TransformBinding)
        rt = binding.transforms[0]
        assert rt.from_angle == 0.0
        assert rt.to_angle == 360.0
        assert rt.origin == "center"

    def test_load_missing_transforms(self, tmp_path: Path):
        """Missing transforms key raises PackageError."""
        pkg = tmp_path / "Bad.dui"
        pkg.mkdir()
        (pkg / "layout.svg").write_text(_TRANSFORM_SVG, encoding="utf-8")
        manifest = (
            "name: Bad\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "bindings:\n  gauge:\n    type: transform\n    node: needle\n"
        )
        (pkg / "manifest.yaml").write_text(manifest, encoding="utf-8")
        with pytest.raises(PackageError, match="missing 'transforms'"):
            load_package(pkg)

    def test_load_empty_transforms(self, tmp_path: Path):
        """Empty transforms list raises PackageError."""
        pkg_path = _make_transform_package(tmp_path, transforms=[])
        with pytest.raises(PackageError, match="non-empty list"):
            load_package(pkg_path)

    def test_load_invalid_kind(self, tmp_path: Path):
        """Invalid transform kind raises PackageError."""
        pkg_path = _make_transform_package(
            tmp_path, transforms=[{"kind": "skew"}]
        )
        with pytest.raises(PackageError, match="invalid kind 'skew'"):
            load_package(pkg_path)

    def test_load_invalid_default(self, tmp_path: Path):
        """Default outside 0-1 raises PackageError."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[{"kind": "rotate"}],
            default=1.5,
        )
        with pytest.raises(PackageError, match="between 0.0 and 1.0"):
            load_package(pkg_path)

    def test_load_invalid_from(self, tmp_path: Path):
        """Non-numeric 'from' raises PackageError."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[{"kind": "rotate", "from": "abc"}],
        )
        with pytest.raises(PackageError, match="'from' must be a number"):
            load_package(pkg_path)

    def test_load_invalid_to(self, tmp_path: Path):
        """Non-numeric 'to' raises PackageError."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[{"kind": "rotate", "to": "abc"}],
        )
        with pytest.raises(PackageError, match="'to' must be a number"):
            load_package(pkg_path)

    def test_load_invalid_origin(self, tmp_path: Path):
        """Non-string origin raises PackageError."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[{"kind": "rotate", "origin": 123}],
        )
        with pytest.raises(PackageError, match="'origin' must be a string"):
            load_package(pkg_path)

    def test_load_node_not_in_svg(self, tmp_path: Path):
        """Node not in SVG raises PackageError."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[{"kind": "rotate"}],
            node="nonexistent",
        )
        with pytest.raises(PackageError, match="does not exist in the SVG"):
            load_package(pkg_path)

    def test_load_multiple_transforms(self, tmp_path: Path):
        """Multiple transforms in a single binding load correctly."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[
                {"kind": "rotate", "from": 0, "to": 180},
                {"kind": "rotate", "from": 0, "to": 90, "origin": "50 50"},
            ],
        )
        spec = load_package(pkg_path)
        binding = spec.bindings["gauge"]
        assert isinstance(binding, TransformBinding)
        assert len(binding.transforms) == 2
        assert binding.transforms[1].origin == "50 50"


# ─── Renderer tests ──────────────────────────────────────────────────────────


class TestTransformRenderer:
    """Tests for transform binding SVG rendering."""

    def _make_spec(
        self,
        tmp_path: Path,
        transforms: list[dict[str, Any]],
        default: float = 0.0,
        svg: str = _TRANSFORM_SVG,
    ):
        pkg_path = _make_transform_package(tmp_path, transforms, default, svg)
        return load_package(pkg_path)

    def test_render_at_zero(self, tmp_path: Path):
        """Value 0.0 applies from_angle."""
        spec = self._make_spec(
            tmp_path,
            transforms=[{"kind": "rotate", "from": -50, "to": 50, "origin": "center"}],
            default=0.0,
        )
        renderer = SvgRenderer(spec)
        svg_out = renderer.render_svg()
        # The needle should have rotate(-50,...) 
        assert "rotate(-50" in svg_out

    def test_render_at_one(self, tmp_path: Path):
        """Value 1.0 applies to_angle."""
        spec = self._make_spec(
            tmp_path,
            transforms=[{"kind": "rotate", "from": -50, "to": 50, "origin": "center"}],
        )
        renderer = SvgRenderer(spec)
        renderer.set("gauge", 1.0)
        svg_out = renderer.render_svg()
        assert "rotate(50" in svg_out

    def test_render_at_half(self, tmp_path: Path):
        """Value 0.5 interpolates to midpoint angle."""
        spec = self._make_spec(
            tmp_path,
            transforms=[{"kind": "rotate", "from": 0, "to": 100, "origin": "center"}],
        )
        renderer = SvgRenderer(spec)
        renderer.set("gauge", 0.5)
        svg_out = renderer.render_svg()
        assert "rotate(50" in svg_out

    def test_render_center_origin(self, tmp_path: Path):
        """Origin 'center' resolves from element x, y, width, height."""
        spec = self._make_spec(
            tmp_path,
            transforms=[{"kind": "rotate", "from": 0, "to": 90, "origin": "center"}],
        )
        renderer = SvgRenderer(spec)
        renderer.set("gauge", 1.0)
        svg_out = renderer.render_svg()
        # needle: x=90, y=10, w=20, h=80 → center=(100, 50)
        assert "100" in svg_out
        assert "50" in svg_out

    def test_render_explicit_origin(self, tmp_path: Path):
        """Explicit 'x y' origin is used directly."""
        spec = self._make_spec(
            tmp_path,
            transforms=[{"kind": "rotate", "from": 0, "to": 90, "origin": "200 250"}],
        )
        renderer = SvgRenderer(spec)
        renderer.set("gauge", 1.0)
        svg_out = renderer.render_svg()
        assert "rotate(90,200,250)" in svg_out

    def test_render_clamping_above_one(self, tmp_path: Path):
        """Values above 1.0 are clamped to 1.0."""
        spec = self._make_spec(
            tmp_path,
            transforms=[{"kind": "rotate", "from": 0, "to": 100}],
        )
        renderer = SvgRenderer(spec)
        renderer.set("gauge", 2.5)
        svg_out = renderer.render_svg()
        assert "rotate(100" in svg_out

    def test_render_clamping_below_zero(self, tmp_path: Path):
        """Values below 0.0 are clamped to 0.0."""
        spec = self._make_spec(
            tmp_path,
            transforms=[{"kind": "rotate", "from": 10, "to": 100}],
        )
        renderer = SvgRenderer(spec)
        renderer.set("gauge", -0.5)
        svg_out = renderer.render_svg()
        assert "rotate(10" in svg_out

    def test_render_multiple_transforms(self, tmp_path: Path):
        """Multiple transforms compose in order."""
        spec = self._make_spec(
            tmp_path,
            transforms=[
                {"kind": "rotate", "from": 0, "to": 90, "origin": "0 0"},
                {"kind": "rotate", "from": 0, "to": 180, "origin": "50 50"},
            ],
        )
        renderer = SvgRenderer(spec)
        renderer.set("gauge", 1.0)
        svg_out = renderer.render_svg()
        # Should have both rotations space-separated
        assert "rotate(90,0,0) rotate(180,50,50)" in svg_out

    def test_set_returns_changed(self, tmp_path: Path):
        """set() returns True when value changes, False when same."""
        spec = self._make_spec(
            tmp_path,
            transforms=[{"kind": "rotate", "from": 0, "to": 90}],
            default=0.5,
        )
        renderer = SvgRenderer(spec)
        assert renderer.set("gauge", 0.5) is False
        assert renderer.set("gauge", 0.7) is True
        assert renderer.set("gauge", 0.7) is False

    def test_render_no_dimensions_element(self, tmp_path: Path):
        """Element without width/height (e.g. polyline) gets origin (0, 0) for center."""
        pkg_path = _make_transform_package(
            tmp_path,
            transforms=[{"kind": "rotate", "from": 0, "to": 90, "origin": "center"}],
            svg=_TRANSFORM_SVG_NO_DIMS,
            node="arrow",
        )
        spec = load_package(pkg_path)
        renderer = SvgRenderer(spec)
        renderer.set("gauge", 1.0)
        svg_out = renderer.render_svg()
        # polyline has no x/y/width/height → center = (0,0)
        assert "rotate(90,0,0)" in svg_out
