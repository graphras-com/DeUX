"""Tests for deux.dui.spinner — SpinnerFrames class."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest
from PIL import Image

from deux.dui.schema import (
    PackageSpec,
    PackageType,
    SpinnerSpec,
    SpinnerType,
)
from deux.dui.spinner import SpinnerFrames

_SPINNER_SVG = (
    '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" '
    'width="120" height="120">'
    '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
    '<rect id="spinner_background" x="0" y="0" width="55" height="55" '
    'display="none" fill="#333"/>'
    '<rect id="spinner" x="80" y="30" width="30" height="30" '
    'display="none" fill="#fff"/>'
    '<circle id="spinner_circle" cx="60" cy="60" r="20" '
    'display="none" fill="#fff"/>'
    "</svg>"
)


def _fake_png(width: int = 120, height: int = 120) -> bytes:
    """Return a minimal valid PNG."""
    img = Image.new("RGB", (width, height), "black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fake_image(
    svg_data: bytes,
    width: int = 120,
    height: int = 120,
    *,
    mode: str = "RGBA",
    ctx: object = None,
) -> Image.Image:
    """Return a minimal valid PIL Image for mocking ``_svg_to_image``."""
    return Image.new(mode, (width, height), "black")


def _make_spec(
    spinner: SpinnerSpec | None = None,
    assets: dict[str, bytes] | None = None,
    svg: str = _SPINNER_SVG,
) -> PackageSpec:
    return PackageSpec(
        name="TestSpinner",
        type=PackageType.KEY,
        version=1,
        svg_source=svg,
        spinner=spinner,
        assets=assets or {},
    )


class TestRotation:
    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_rotation_generates_correct_frame_count(self, mock_raster):
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=8)
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        assert len(sf.frames) == 8

    def test_element_centre_calculation_rect(self):
        """Rect at x=80,y=30,w=30,h=30 → centre (95, 45)."""
        elem = ET.fromstring(
            '<rect xmlns="http://www.w3.org/2000/svg" '
            'x="80" y="30" width="30" height="30"/>'
        )
        cx, cy = SpinnerFrames._element_centre(elem)
        assert cx == pytest.approx(95.0)
        assert cy == pytest.approx(45.0)

    def test_element_centre_calculation_circle(self):
        """Circle with cx=60, cy=60 → centre (60, 60)."""
        elem = ET.fromstring(
            '<circle xmlns="http://www.w3.org/2000/svg" cx="60" cy="60" r="20"/>'
        )
        cx, cy = SpinnerFrames._element_centre(elem)
        assert cx == pytest.approx(60.0)
        assert cy == pytest.approx(60.0)


class TestPulse:
    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_pulse_generates_correct_frame_count(self, mock_raster):
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.PULSE, node="spinner", frames=6)
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        assert len(sf.frames) == 6


class TestCustom:
    def test_custom_from_png_files(self):
        """Custom spinner loads numbered PNGs from assets."""
        assets = {}
        for i in range(4):
            assets[f"spinner/frame_{i:02d}.png"] = _fake_png(120, 120)

        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.CUSTOM, frames=4),
            assets=assets,
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        frames = sf.frames
        assert len(frames) == 4
        for f in frames:
            assert isinstance(f, bytes)
            assert len(f) > 0

    def test_custom_from_animated_gif(self):
        """Custom spinner loads frames from an animated GIF."""
        # Create a 3-frame animated GIF
        imgs = [Image.new("RGB", (120, 120), color) for color in ["red", "green", "blue"]]
        buf = io.BytesIO()
        imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:], loop=0)
        gif_bytes = buf.getvalue()

        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.CUSTOM, frames=3),
            assets={"spinner.gif": gif_bytes},
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        frames = sf.frames
        assert len(frames) == 3


class TestCaching:
    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_frames_are_cached_after_first_access(self, mock_raster):
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=4)
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        first = sf.frames
        second = sf.frames
        assert first is second
        # _generate called only once
        assert mock_raster.call_count == 4  # once per frame, not 8


class TestRenderedSvg:
    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_rotation_uses_rendered_svg_when_provided(self, mock_raster):
        """When rendered_svg is passed, spinner frames use it instead of raw svg_source."""
        rendered = (
            '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" '
            'width="120" height="120">'
            '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
            '<text id="title">Updated Title</text>'
            '<rect id="spinner" x="80" y="30" width="30" height="30" '
            'display="none" fill="#fff"/>'
            "</svg>"
        )
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=2)
        )
        sf = SpinnerFrames(spec, width=120, height=120, rendered_svg=rendered)
        assert len(sf.frames) == 2

        # Verify the rendered SVG was used — it should contain "Updated Title"
        first_call_svg: bytes = mock_raster.call_args_list[0][0][0]
        assert b"Updated Title" in first_call_svg

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_pulse_uses_rendered_svg_when_provided(self, mock_raster):
        rendered = (
            '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" '
            'width="120" height="120">'
            '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
            '<text id="title">Rendered Content</text>'
            '<rect id="spinner" x="80" y="30" width="30" height="30" '
            'display="none" fill="#fff"/>'
            "</svg>"
        )
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.PULSE, node="spinner", frames=2)
        )
        sf = SpinnerFrames(spec, width=120, height=120, rendered_svg=rendered)
        assert len(sf.frames) == 2

        first_call_svg: bytes = mock_raster.call_args_list[0][0][0]
        assert b"Rendered Content" in first_call_svg

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_falls_back_to_svg_source_without_rendered(self, mock_raster):
        """Without rendered_svg, spinner uses the raw svg_source."""
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=2)
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        assert len(sf.frames) == 2
        # Raw SVG should NOT contain "Updated Title"
        first_call_svg: bytes = mock_raster.call_args_list[0][0][0]
        assert b"Updated Title" not in first_call_svg


class TestErrors:
    def test_no_spinner_spec_raises(self):
        spec = _make_spec(spinner=None)
        with pytest.raises(ValueError, match="no spinner configuration"):
            SpinnerFrames(spec, width=120, height=120)

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_blank_frames_fallback_for_missing_node(self, mock_raster):
        """When the spinner node ID doesn't exist in the SVG, return blank frames."""
        spec = _make_spec(
            spinner=SpinnerSpec(
                type=SpinnerType.ROTATION, node="nonexistent", frames=4
            )
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        frames = sf.frames
        assert len(frames) == 4
        # All frames should be identical (blank)
        assert all(f == frames[0] for f in frames)


class TestBackgroundNode:
    """Background node is shown (not animated) during spinner frames."""

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_rotation_shows_background_node(self, mock_raster):
        """Rotation frames should unhide the background_node."""
        spec = _make_spec(
            spinner=SpinnerSpec(
                type=SpinnerType.ROTATION,
                node="spinner",
                frames=2,
                background_node="spinner_background",
            )
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        assert len(sf.frames) == 2

        # Inspect the SVG passed to rasteriser — background should be visible
        first_svg: bytes = mock_raster.call_args_list[0][0][0]
        assert b'id="spinner_background"' in first_svg
        # display="none" should have been removed from the background node
        root = ET.fromstring(first_svg)  # noqa: S314
        bg = root.find('.//{http://www.w3.org/2000/svg}rect[@id="spinner_background"]')
        if bg is None:
            bg = root.find('.//rect[@id="spinner_background"]')
        assert bg is not None
        assert bg.get("display") is None

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_rotation_background_node_not_rotated(self, mock_raster):
        """Background node must not receive a rotation transform."""
        spec = _make_spec(
            spinner=SpinnerSpec(
                type=SpinnerType.ROTATION,
                node="spinner",
                frames=4,
                background_node="spinner_background",
            )
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        assert len(sf.frames) == 4

        # Check last frame (non-zero rotation) — background should have no transform
        last_svg: bytes = mock_raster.call_args_list[3][0][0]
        root = ET.fromstring(last_svg)  # noqa: S314
        bg = root.find('.//{http://www.w3.org/2000/svg}rect[@id="spinner_background"]')
        if bg is None:
            bg = root.find('.//rect[@id="spinner_background"]')
        assert bg is not None
        assert "rotate" not in (bg.get("transform") or "")

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_pulse_shows_background_node(self, mock_raster):
        """Pulse frames should unhide the background_node."""
        spec = _make_spec(
            spinner=SpinnerSpec(
                type=SpinnerType.PULSE,
                node="spinner",
                frames=2,
                background_node="spinner_background",
            )
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        assert len(sf.frames) == 2

        first_svg: bytes = mock_raster.call_args_list[0][0][0]
        root = ET.fromstring(first_svg)  # noqa: S314
        bg = root.find('.//{http://www.w3.org/2000/svg}rect[@id="spinner_background"]')
        if bg is None:
            bg = root.find('.//rect[@id="spinner_background"]')
        assert bg is not None
        assert bg.get("display") is None
        # Background should not have opacity set
        assert bg.get("opacity") is None

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_missing_background_node_no_error(self, mock_raster):
        """If background_node references a missing element, no crash occurs."""
        spec = _make_spec(
            spinner=SpinnerSpec(
                type=SpinnerType.ROTATION,
                node="spinner",
                frames=2,
                background_node="nonexistent_bg",
            )
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        assert len(sf.frames) == 2

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_no_background_node_works(self, mock_raster):
        """Spinner without background_node still works normally."""
        spec = _make_spec(
            spinner=SpinnerSpec(
                type=SpinnerType.ROTATION, node="spinner", frames=2
            )
        )
        sf = SpinnerFrames(spec, width=120, height=120)
        assert len(sf.frames) == 2


class TestSpinnerWithBgTile:
    """Spinner frames composited onto a background tile."""

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_rotation_with_bg_tile(self, mock_raster):
        tile = Image.new("RGB", (120, 120), (255, 0, 0))
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=4)
        )
        sf = SpinnerFrames(spec, width=120, height=120, bg_tile=tile)
        assert len(sf.frames) == 4
        for frame_bytes in sf.frames:
            img = Image.open(io.BytesIO(frame_bytes))
            assert img.size == (120, 120)

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_pulse_with_bg_tile(self, mock_raster):
        tile = Image.new("RGB", (120, 120), (0, 255, 0))
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.PULSE, node="spinner", frames=4)
        )
        sf = SpinnerFrames(spec, width=120, height=120, bg_tile=tile)
        assert len(sf.frames) == 4

    def test_blank_frames_with_bg_tile(self):
        """Blank fallback frames use the background tile instead of black."""
        tile = Image.new("RGB", (120, 120), (0, 0, 255))
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.ROTATION, node="nonexistent", frames=2)
        )
        sf = SpinnerFrames(spec, width=120, height=120, bg_tile=tile)
        for frame_bytes in sf.frames:
            img = Image.open(io.BytesIO(frame_bytes))
            r, g, b = img.getpixel((60, 60))
            assert b > 200
            assert r < 50

    def test_custom_frames_with_bg_tile(self):
        """Custom PNG frames are composited onto the background tile."""
        tile = Image.new("RGB", (120, 120), (255, 0, 0))
        frame_img = Image.new("RGBA", (120, 120), (0, 255, 0, 128))
        buf = io.BytesIO()
        frame_img.save(buf, format="PNG")
        frame_png = buf.getvalue()
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.CUSTOM, frames=1),
            assets={"spinner/frame_00.png": frame_png},
        )
        sf = SpinnerFrames(spec, width=120, height=120, bg_tile=tile)
        assert len(sf.frames) == 1

    def test_gif_frames_with_bg_tile(self):
        """GIF frames are composited onto the background tile."""
        tile = Image.new("RGB", (120, 120), (255, 0, 0))
        f1 = Image.new("RGB", (120, 120), (0, 255, 0))
        f2 = Image.new("RGB", (120, 120), (0, 0, 255))
        buf = io.BytesIO()
        f1.save(buf, format="GIF", save_all=True, append_images=[f2], loop=0)
        gif_data = buf.getvalue()
        spec = _make_spec(
            spinner=SpinnerSpec(type=SpinnerType.CUSTOM, frames=2),
            assets={"spinner.gif": gif_data},
        )
        sf = SpinnerFrames(spec, width=120, height=120, bg_tile=tile)
        assert len(sf.frames) == 2
