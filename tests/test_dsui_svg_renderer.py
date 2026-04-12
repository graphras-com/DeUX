"""Tests for deckboard.dsui.svg_renderer — SVG rendering engine."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from deckboard.dsui.schema import (
    ColorBinding,
    ImageBinding,
    ImageFit,
    OverflowMode,
    PackageSpec,
    PackageType,
    RangeBinding,
    RangeDirection,
    SliderBinding,
    TextBinding,
    ToggleBinding,
    VisibilityBinding,
)
from deckboard.dsui.svg_renderer import (
    SvgRenderer,
    _fit_image,
    _image_to_data_uri,
    _truncate_text,
)


# -- Helper SVGs -----------------------------------------------------------

_BASIC_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect id="bg" width="100" height="50" fill="#000000"/>'
    '<text id="label" x="10" y="30" font-size="12" fill="#ffffff">Hello</text>'
    "</svg>"
)

_IMAGE_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect id="bg" width="100" height="50" fill="#000000"/>'
    '<rect id="placeholder" x="0" y="0" width="40" height="40" fill="#ff0000"/>'
    '<image id="pic" x="0" y="0" width="40" height="40" href=""/>'
    "</svg>"
)

_VISIBILITY_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect id="bg" width="100" height="50" fill="#000000"/>'
    '<rect id="panel" x="10" y="10" width="80" height="30" fill="#ff0000"/>'
    "</svg>"
)

_TOGGLE_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect id="bg" width="100" height="50" fill="#000000"/>'
    '<path id="icon_on" d="M10 10 L50 10 L50 40 L10 40 Z" fill="#00ff00"/>'
    '<path id="icon_off" d="M60 10 L90 10 L90 40 L60 40 Z" fill="#ff0000"/>'
    "</svg>"
)

_COLOR_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect id="accent" width="100" height="50" fill="#ff0000"/>'
    "</svg>"
)

_RANGE_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect id="bg" width="100" height="50" fill="#000000"/>'
    '<rect id="bar" x="5" y="20" width="80" height="10" fill="#00ff00"/>'
    "</svg>"
)

_RANGE_VERTICAL_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="50" height="100">'
    '<rect id="bg" width="50" height="100" fill="#000000"/>'
    '<rect id="vbar" x="20" y="5" width="10" height="80" fill="#00ff00"/>'
    "</svg>"
)


def _make_spec(
    svg: str, bindings: dict | None = None, assets: dict | None = None
) -> PackageSpec:
    """Create a minimal PackageSpec for testing."""
    return PackageSpec(
        name="Test",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=svg,
        bindings=bindings or {},
        assets=assets or {},
    )


class TestTextTruncation:
    def test_short_text_unchanged(self):
        assert _truncate_text("Hi", 90, OverflowMode.ELLIPSIS) == "Hi"

    def test_long_text_truncated(self):
        long_text = "A" * 100
        result = _truncate_text(long_text, 70, OverflowMode.ELLIPSIS)
        assert result.endswith("\u2026")
        assert len(result) < len(long_text)

    def test_clip_mode_unchanged(self):
        long_text = "A" * 100
        assert _truncate_text(long_text, 70, OverflowMode.CLIP) == long_text

    def test_very_small_max_width(self):
        result = _truncate_text("Hello World", 7, OverflowMode.ELLIPSIS)
        assert len(result) <= 2  # 1 char + ellipsis


class TestImageFit:
    def test_fill(self):
        img = Image.new("RGB", (200, 100))
        result = _fit_image(img, 50, 50, ImageFit.FILL)
        assert result.size == (50, 50)

    def test_contain(self):
        img = Image.new("RGB", (200, 100))
        result = _fit_image(img, 50, 50, ImageFit.CONTAIN)
        assert result.size == (50, 50)
        # The actual image should be letterboxed

    def test_cover(self):
        img = Image.new("RGB", (200, 100))
        result = _fit_image(img, 50, 50, ImageFit.COVER)
        assert result.size == (50, 50)

    def test_zero_target(self):
        img = Image.new("RGB", (50, 50))
        result = _fit_image(img, 0, 50, ImageFit.FILL)
        assert result.size == (50, 50)  # unchanged

    def test_contain_portrait(self):
        img = Image.new("RGB", (100, 200))
        result = _fit_image(img, 50, 50, ImageFit.CONTAIN)
        assert result.size == (50, 50)


class TestImageToDataUri:
    def test_png_format(self):
        img = Image.new("RGB", (10, 10), "red")
        uri = _image_to_data_uri(img, "PNG")
        assert uri.startswith("data:image/png;base64,")

    def test_jpeg_format(self):
        img = Image.new("RGB", (10, 10), "red")
        uri = _image_to_data_uri(img, "JPEG")
        assert uri.startswith("data:image/jpeg;base64,")


class TestSvgRendererSet:
    def test_set_text_binding(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={"label": TextBinding(node="label", default="Hello")},
        )
        renderer = SvgRenderer(spec)
        changed = renderer.set("label", "World")
        assert changed is True
        assert renderer.get("label") == "World"

    def test_set_same_value_returns_false(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={"label": TextBinding(node="label", default="Hello")},
        )
        renderer = SvgRenderer(spec)
        assert renderer.set("label", "Hello") is False

    def test_set_image_always_returns_true(self):
        spec = _make_spec(
            _IMAGE_SVG,
            bindings={"pic": ImageBinding(node="pic")},
        )
        renderer = SvgRenderer(spec)
        img = Image.new("RGB", (10, 10))
        assert renderer.set("pic", img) is True
        # Set same image again — still True (identity unreliable)
        assert renderer.set("pic", img) is True

    def test_set_unknown_raises(self):
        spec = _make_spec(_BASIC_SVG, bindings={})
        renderer = SvgRenderer(spec)
        with pytest.raises(KeyError, match="Unknown binding"):
            renderer.set("nonexistent", "val")

    def test_get_unknown_raises(self):
        spec = _make_spec(_BASIC_SVG, bindings={})
        renderer = SvgRenderer(spec)
        with pytest.raises(KeyError, match="Unknown binding"):
            renderer.get("nonexistent")

    def test_set_many(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={
                "label": TextBinding(node="label", default="Hello"),
            },
        )
        renderer = SvgRenderer(spec)
        changed = renderer.set_many(label="New")
        assert changed is True
        assert renderer.get("label") == "New"

    def test_set_many_no_change(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={"label": TextBinding(node="label", default="Hello")},
        )
        renderer = SvgRenderer(spec)
        changed = renderer.set_many(label="Hello")
        assert changed is False


class TestSvgRendererDefaults:
    def test_text_default(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={"label": TextBinding(node="label", default="DefaultVal")},
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("label") == "DefaultVal"

    def test_visibility_default_true(self):
        spec = _make_spec(
            _VISIBILITY_SVG,
            bindings={"panel": VisibilityBinding(node="panel", default=True)},
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("panel") is True

    def test_visibility_default_false(self):
        spec = _make_spec(
            _VISIBILITY_SVG,
            bindings={"panel": VisibilityBinding(node="panel", default=False)},
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("panel") is False

    def test_color_default(self):
        spec = _make_spec(
            _COLOR_SVG,
            bindings={"accent": ColorBinding(node="accent", default="#00ff00")},
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("accent") == "#00ff00"

    def test_image_default_none(self):
        spec = _make_spec(
            _IMAGE_SVG,
            bindings={"pic": ImageBinding(node="pic")},
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("pic") is None


class TestSvgRendererRender:
    def test_renders_to_rgb_image(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={"label": TextBinding(node="label", default="Hi")},
        )
        renderer = SvgRenderer(spec)
        img = renderer.render()
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.size == (100, 50)

    def test_text_binding_applied(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={"label": TextBinding(node="label", default="Original")},
        )
        renderer = SvgRenderer(spec)
        img_before = renderer.render()

        renderer.set("label", "Changed")
        img_after = renderer.render()

        # Images should differ (different text)
        assert img_before.tobytes() != img_after.tobytes()

    def test_visibility_binding(self):
        spec = _make_spec(
            _VISIBILITY_SVG,
            bindings={"panel": VisibilityBinding(node="panel", default=True)},
        )
        renderer = SvgRenderer(spec)
        img_visible = renderer.render()

        renderer.set("panel", False)
        img_hidden = renderer.render()

        assert img_visible.tobytes() != img_hidden.tobytes()

    def test_color_binding(self):
        spec = _make_spec(
            _COLOR_SVG,
            bindings={"accent": ColorBinding(node="accent", default="#ff0000")},
        )
        renderer = SvgRenderer(spec)
        img_red = renderer.render()

        renderer.set("accent", "#0000ff")
        img_blue = renderer.render()

        assert img_red.tobytes() != img_blue.tobytes()

    def test_image_binding_with_pil(self):
        spec = _make_spec(
            _IMAGE_SVG,
            bindings={
                "pic": ImageBinding(
                    node="pic",
                    placeholder_node="placeholder",
                ),
            },
        )
        renderer = SvgRenderer(spec)

        # No image — placeholder should be visible
        img_no_pic = renderer.render()

        # Set an image
        cover = Image.new("RGB", (40, 40), (0, 255, 0))
        renderer.set("pic", cover)
        img_with_pic = renderer.render()

        assert img_no_pic.tobytes() != img_with_pic.tobytes()

    def test_image_binding_with_bytes(self):
        spec = _make_spec(
            _IMAGE_SVG,
            bindings={"pic": ImageBinding(node="pic")},
        )
        renderer = SvgRenderer(spec)

        img = Image.new("RGB", (40, 40), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        renderer.set("pic", buf.getvalue())
        result = renderer.render()
        assert result.size == (100, 50)

    def test_image_binding_none_hides(self):
        spec = _make_spec(
            _IMAGE_SVG,
            bindings={
                "pic": ImageBinding(
                    node="pic",
                    placeholder_node="placeholder",
                ),
            },
        )
        renderer = SvgRenderer(spec)
        # Initially None
        img = renderer.render()
        assert img.size == (100, 50)

    def test_text_truncation_applied(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={
                "label": TextBinding(
                    node="label",
                    default="",
                    max_width=35,
                    overflow=OverflowMode.ELLIPSIS,
                ),
            },
        )
        renderer = SvgRenderer(spec)
        renderer.set("label", "A very long piece of text that should be truncated")
        # Should not raise
        img = renderer.render()
        assert img.size == (100, 50)

    def test_render_does_not_mutate_base(self):
        spec = _make_spec(
            _BASIC_SVG,
            bindings={"label": TextBinding(node="label", default="Original")},
        )
        renderer = SvgRenderer(spec)
        renderer.set("label", "Modified")
        renderer.render()

        # Reset to default and render again — should work
        renderer.set("label", "Original")
        img = renderer.render()
        assert img.size == (100, 50)

    def test_image_binding_unsupported_type_logs_warning(self, caplog):
        spec = _make_spec(
            _IMAGE_SVG,
            bindings={"pic": ImageBinding(node="pic")},
        )
        renderer = SvgRenderer(spec)
        renderer.set("pic", 12345)  # unsupported type
        import logging

        with caplog.at_level(logging.WARNING):
            renderer.render()
        assert "unsupported value type" in caplog.text

    def test_missing_node_logs_warning(self, caplog):
        """Binding references a node that somehow isn't in the parsed tree."""
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"/>'
        spec = PackageSpec(
            name="Test",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={"ghost": TextBinding(node="ghost_node", default="x")},
        )
        renderer = SvgRenderer(spec)
        import logging

        with caplog.at_level(logging.WARNING):
            renderer.render()
        assert "not found in SVG" in caplog.text


class TestSvgRendererInlineAssets:
    def test_inline_asset_by_path(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">'
            '<image id="icon" href="assets/test.png" width="20" height="20"/>'
            "</svg>"
        )
        # Create a test PNG
        img = Image.new("RGB", (20, 20), "red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        spec = _make_spec(svg, assets={"test.png": buf.getvalue()})
        renderer = SvgRenderer(spec)
        result = renderer.render()
        assert result.size == (50, 50)

    def test_inline_asset_by_name(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">'
            '<image id="icon" href="icon.png" width="20" height="20"/>'
            "</svg>"
        )
        img = Image.new("RGB", (20, 20), "blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        spec = _make_spec(svg, assets={"icon.png": buf.getvalue()})
        renderer = SvgRenderer(spec)
        result = renderer.render()
        assert result.size == (50, 50)


class TestSvgRendererRange:
    def test_set_range_returns_true_on_change(self):
        spec = _make_spec(
            _RANGE_SVG,
            bindings={"bar": RangeBinding(node="bar", default=0.0)},
        )
        renderer = SvgRenderer(spec)
        assert renderer.set("bar", 0.5) is True

    def test_set_range_same_value_returns_false(self):
        spec = _make_spec(
            _RANGE_SVG,
            bindings={"bar": RangeBinding(node="bar", default=0.5)},
        )
        renderer = SvgRenderer(spec)
        assert renderer.set("bar", 0.5) is False

    def test_range_default(self):
        spec = _make_spec(
            _RANGE_SVG,
            bindings={"bar": RangeBinding(node="bar", default=0.75)},
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("bar") == 0.75

    def test_range_extent_cached_horizontal(self):
        spec = _make_spec(
            _RANGE_SVG,
            bindings={"bar": RangeBinding(node="bar", default=0.0)},
        )
        renderer = SvgRenderer(spec)
        assert renderer._range_extents["bar"] == 80.0

    def test_range_extent_cached_vertical(self):
        spec = _make_spec(
            _RANGE_VERTICAL_SVG,
            bindings={
                "vbar": RangeBinding(
                    node="vbar", default=0.0, direction=RangeDirection.VERTICAL
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer._range_extents["vbar"] == 80.0

    def test_range_renders_differently(self):
        spec = _make_spec(
            _RANGE_SVG,
            bindings={"bar": RangeBinding(node="bar", default=0.0)},
        )
        renderer = SvgRenderer(spec)
        img_empty = renderer.render()

        renderer.set("bar", 1.0)
        img_full = renderer.render()

        assert img_empty.tobytes() != img_full.tobytes()

    def test_range_half_differs_from_full(self):
        spec = _make_spec(
            _RANGE_SVG,
            bindings={"bar": RangeBinding(node="bar", default=1.0)},
        )
        renderer = SvgRenderer(spec)
        img_full = renderer.render()

        renderer.set("bar", 0.5)
        img_half = renderer.render()

        assert img_full.tobytes() != img_half.tobytes()

    def test_range_vertical_renders(self):
        spec = _make_spec(
            _RANGE_VERTICAL_SVG,
            bindings={
                "vbar": RangeBinding(
                    node="vbar", default=1.0, direction=RangeDirection.VERTICAL
                ),
            },
        )
        renderer = SvgRenderer(spec)
        img_full = renderer.render()

        renderer.set("vbar", 0.0)
        img_empty = renderer.render()

        assert img_full.tobytes() != img_empty.tobytes()

    def test_range_clamped_above_one(self):
        spec = _make_spec(
            _RANGE_SVG,
            bindings={"bar": RangeBinding(node="bar", default=0.0)},
        )
        renderer = SvgRenderer(spec)
        renderer.set("bar", 1.0)
        img_one = renderer.render()

        renderer.set("bar", 5.0)
        img_over = renderer.render()

        # Both should produce the same output (clamped to 1.0)
        assert img_one.tobytes() == img_over.tobytes()

    def test_range_clamped_below_zero(self):
        spec = _make_spec(
            _RANGE_SVG,
            bindings={"bar": RangeBinding(node="bar", default=0.0)},
        )
        renderer = SvgRenderer(spec)
        img_zero = renderer.render()

        renderer.set("bar", -0.5)
        img_neg = renderer.render()

        # Both should produce the same output (clamped to 0.0)
        assert img_zero.tobytes() == img_neg.tobytes()

    def test_range_missing_node_logs_warning(self, caplog):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"/>'
        spec = PackageSpec(
            name="Test",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={"ghost": RangeBinding(node="ghost_node", default=0.5)},
        )
        renderer = SvgRenderer(spec)
        import logging

        with caplog.at_level(logging.WARNING):
            renderer.render()
        assert "not found in SVG" in caplog.text


# -- Slider SVGs ---------------------------------------------------------------

_SLIDER_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="200" height="50">'
    '<rect id="bg" width="200" height="50" fill="#000000"/>'
    '<rect id="track" x="5" y="20" width="190" height="10" fill="#333333"/>'
    '<rect id="knob" x="5" y="18" width="4" height="14" fill="#ffffff"/>'
    "</svg>"
)

_SLIDER_VERTICAL_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="50" height="200">'
    '<rect id="bg" width="50" height="200" fill="#000000"/>'
    '<rect id="track" x="20" y="5" width="10" height="190" fill="#333333"/>'
    '<rect id="vknob" x="18" y="5" width="14" height="4" fill="#ffffff"/>'
    "</svg>"
)


class TestSvgRendererSlider:
    def test_set_slider_returns_true_on_change(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.0, min_pos=5.0, max_pos=191.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.set("pos", 0.5) is True

    def test_set_slider_same_value_returns_false(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.5, min_pos=5.0, max_pos=191.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.set("pos", 0.5) is False

    def test_slider_default(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.75, min_pos=5.0, max_pos=191.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("pos") == 0.75

    def test_slider_horizontal_renders_differently(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.0, min_pos=5.0, max_pos=191.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        img_min = renderer.render()

        renderer.set("pos", 1.0)
        img_max = renderer.render()

        assert img_min.tobytes() != img_max.tobytes()

    def test_slider_half_differs_from_full(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=1.0, min_pos=5.0, max_pos=191.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        img_full = renderer.render()

        renderer.set("pos", 0.5)
        img_half = renderer.render()

        assert img_full.tobytes() != img_half.tobytes()

    def test_slider_vertical_renders(self):
        spec = _make_spec(
            _SLIDER_VERTICAL_SVG,
            bindings={
                "vpos": SliderBinding(
                    node="vknob",
                    default=1.0,
                    direction=RangeDirection.VERTICAL,
                    min_pos=5.0,
                    max_pos=191.0,
                ),
            },
        )
        renderer = SvgRenderer(spec)
        img_full = renderer.render()

        renderer.set("vpos", 0.0)
        img_empty = renderer.render()

        assert img_full.tobytes() != img_empty.tobytes()

    def test_slider_clamped_above_one(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.0, min_pos=5.0, max_pos=191.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        renderer.set("pos", 1.0)
        img_one = renderer.render()

        renderer.set("pos", 5.0)
        img_over = renderer.render()

        # Both should produce the same output (clamped to 1.0)
        assert img_one.tobytes() == img_over.tobytes()

    def test_slider_clamped_below_zero(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.0, min_pos=5.0, max_pos=191.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        img_zero = renderer.render()

        renderer.set("pos", -0.5)
        img_neg = renderer.render()

        # Both should produce the same output (clamped to 0.0)
        assert img_zero.tobytes() == img_neg.tobytes()

    def test_slider_midpoint_position(self):
        """Value 0.5 should place the element at the midpoint between min and max."""
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.0, min_pos=10.0, max_pos=190.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        renderer.set("pos", 0.5)
        # Check the calculated position via internal rendering
        # midpoint = 10.0 + 0.5 * (190.0 - 10.0) = 100.0
        import copy
        import xml.etree.ElementTree as ET

        root = copy.deepcopy(renderer._base_root)
        from deckboard.dsui.svg_renderer import _find_element_by_id

        binding = spec.bindings["pos"]
        renderer._apply_slider(_find_element_by_id(root, "knob"), binding, 0.5)
        elem = _find_element_by_id(root, "knob")
        assert elem.get("x") == "100.0"

    def test_slider_at_zero_uses_min_pos(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.0, min_pos=10.0, max_pos=190.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        import copy
        import xml.etree.ElementTree as ET

        root = copy.deepcopy(renderer._base_root)
        from deckboard.dsui.svg_renderer import _find_element_by_id

        binding = spec.bindings["pos"]
        renderer._apply_slider(_find_element_by_id(root, "knob"), binding, 0.0)
        elem = _find_element_by_id(root, "knob")
        assert elem.get("x") == "10.0"

    def test_slider_at_one_uses_max_pos(self):
        spec = _make_spec(
            _SLIDER_SVG,
            bindings={
                "pos": SliderBinding(
                    node="knob", default=0.0, min_pos=10.0, max_pos=190.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        import copy
        import xml.etree.ElementTree as ET

        root = copy.deepcopy(renderer._base_root)
        from deckboard.dsui.svg_renderer import _find_element_by_id

        binding = spec.bindings["pos"]
        renderer._apply_slider(_find_element_by_id(root, "knob"), binding, 1.0)
        elem = _find_element_by_id(root, "knob")
        assert elem.get("x") == "190.0"

    def test_slider_vertical_sets_y(self):
        spec = _make_spec(
            _SLIDER_VERTICAL_SVG,
            bindings={
                "vpos": SliderBinding(
                    node="vknob",
                    default=0.0,
                    direction=RangeDirection.VERTICAL,
                    min_pos=5.0,
                    max_pos=191.0,
                ),
            },
        )
        renderer = SvgRenderer(spec)
        import copy

        root = copy.deepcopy(renderer._base_root)
        from deckboard.dsui.svg_renderer import _find_element_by_id

        binding = spec.bindings["vpos"]
        renderer._apply_slider(_find_element_by_id(root, "vknob"), binding, 0.5)
        elem = _find_element_by_id(root, "vknob")
        assert elem.get("y") == "98.0"

    def test_slider_missing_node_logs_warning(self, caplog):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"/>'
        spec = PackageSpec(
            name="Test",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={
                "ghost": SliderBinding(
                    node="ghost_node", default=0.5, min_pos=0.0, max_pos=100.0
                ),
            },
        )
        renderer = SvgRenderer(spec)
        import logging

        with caplog.at_level(logging.WARNING):
            renderer.render()
        assert "not found in SVG" in caplog.text


# -- Toggle tests -------------------------------------------------------------


class TestSvgRendererToggleSet:
    def test_set_toggle_returns_true_on_change(self):
        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=False
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.set("lights", True) is True

    def test_set_toggle_same_value_returns_false(self):
        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=False
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.set("lights", False) is False

    def test_toggle_default_false(self):
        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=False
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("lights") is False

    def test_toggle_default_true(self):
        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=True
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.get("lights") is True


class TestSvgRendererToggleRender:
    def test_toggle_true_differs_from_false(self):
        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=False
                ),
            },
        )
        renderer = SvgRenderer(spec)
        img_off = renderer.render()

        renderer.set("lights", True)
        img_on = renderer.render()

        assert img_off.tobytes() != img_on.tobytes()

    def test_toggle_true_shows_on_hides_off(self):
        """Verify SVG DOM manipulation: True → node_on visible, node_off hidden."""
        import copy
        import xml.etree.ElementTree as ET

        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=True
                ),
            },
        )
        renderer = SvgRenderer(spec)
        root = copy.deepcopy(renderer._base_root)
        binding = spec.bindings["lights"]
        from deckboard.dsui.svg_renderer import _find_element_by_id

        elem_on = _find_element_by_id(root, "icon_on")
        elem_off = _find_element_by_id(root, "icon_off")
        renderer._apply_toggle(elem_on, elem_off, True)

        assert elem_on.get("display") is None  # visible
        assert elem_off.get("display") == "none"  # hidden

    def test_toggle_false_shows_off_hides_on(self):
        """Verify SVG DOM manipulation: False → node_off visible, node_on hidden."""
        import copy

        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=False
                ),
            },
        )
        renderer = SvgRenderer(spec)
        root = copy.deepcopy(renderer._base_root)
        from deckboard.dsui.svg_renderer import _find_element_by_id

        elem_on = _find_element_by_id(root, "icon_on")
        elem_off = _find_element_by_id(root, "icon_off")
        renderer._apply_toggle(elem_on, elem_off, False)

        assert elem_on.get("display") == "none"  # hidden
        assert elem_off.get("display") is None  # visible

    def test_toggle_switch_from_true_to_false(self):
        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=True
                ),
            },
        )
        renderer = SvgRenderer(spec)
        img_on = renderer.render()

        renderer.set("lights", False)
        img_off = renderer.render()

        assert img_on.tobytes() != img_off.tobytes()

    def test_toggle_renders_rgb_image(self):
        spec = _make_spec(
            _TOGGLE_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="icon_off", default=False
                ),
            },
        )
        renderer = SvgRenderer(spec)
        img = renderer.render()
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.size == (100, 50)

    def test_toggle_missing_node_on_logs_warning(self, caplog):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">'
            '<path id="icon_off" d="M0 0"/></svg>'
        )
        spec = PackageSpec(
            name="Test",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={
                "lights": ToggleBinding(
                    node_on="ghost_on", node_off="icon_off", default=False
                ),
            },
        )
        renderer = SvgRenderer(spec)
        import logging

        with caplog.at_level(logging.WARNING):
            renderer.render()
        assert "node_on 'ghost_on' not found" in caplog.text

    def test_toggle_missing_node_off_logs_warning(self, caplog):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">'
            '<path id="icon_on" d="M0 0"/></svg>'
        )
        spec = PackageSpec(
            name="Test",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={
                "lights": ToggleBinding(
                    node_on="icon_on", node_off="ghost_off", default=False
                ),
            },
        )
        renderer = SvgRenderer(spec)
        import logging

        with caplog.at_level(logging.WARNING):
            renderer.render()
        assert "node_off 'ghost_off' not found" in caplog.text

    def test_toggle_missing_both_nodes_logs_warnings(self, caplog):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"/>'
        spec = PackageSpec(
            name="Test",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={
                "lights": ToggleBinding(
                    node_on="ghost_on", node_off="ghost_off", default=True
                ),
            },
        )
        renderer = SvgRenderer(spec)
        import logging

        with caplog.at_level(logging.WARNING):
            renderer.render()
        assert "node_on 'ghost_on' not found" in caplog.text
        assert "node_off 'ghost_off' not found" in caplog.text
