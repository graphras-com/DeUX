"""Tests for ``deux.dui.spinner`` — library-owned spinner frame generation."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest
from PIL import Image

from deux.dui.spinner import (
    SPINNER_FRAME_COUNT,
    SPINNER_INTERVAL_MS,
    _bg_signature,
    _build_spinner_fragment,
    clear_cache,
    get_frames,
)

_SPINNER_SVG = (
    '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" '
    'width="120" height="120">'
    '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
    '<g id="spinner" transform="translate(60 60)"/>'
    "</svg>"
)


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


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


class TestGetFrames:
    """Behaviour of the ``get_frames`` entry point."""

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_returns_eight_frames(self, mock_raster):
        frames = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=120,
            height=120,
        )
        assert len(frames) == SPINNER_FRAME_COUNT == 8
        assert all(isinstance(f, bytes) and f for f in frames)

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_constants(self, mock_raster):
        assert SPINNER_FRAME_COUNT == 8
        assert SPINNER_INTERVAL_MS == 100

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_each_frame_has_distinct_rotation(self, mock_raster):
        get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=120,
            height=120,
        )
        assert mock_raster.call_count == SPINNER_FRAME_COUNT
        rotations: list[str] = []
        for call in mock_raster.call_args_list:
            svg_bytes: bytes = call.args[0]
            root = ET.fromstring(svg_bytes)  # noqa: S314
            target = root.find('.//{http://www.w3.org/2000/svg}g[@id="spinner"]')
            assert target is not None
            rotor = target.find('.//{http://www.w3.org/2000/svg}g[@class="deux-spinner-rotor"]')
            assert rotor is not None
            transform = rotor.get("transform", "")
            rotations.append(transform)
        assert len(set(rotations)) == SPINNER_FRAME_COUNT

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_spinner_is_made_visible_in_frames(self, mock_raster):
        svg_with_hidden = _SPINNER_SVG.replace(
            '<g id="spinner" transform="translate(60 60)"/>',
            '<g id="spinner" transform="translate(60 60)" display="none"/>',
        )
        get_frames(
            rendered_svg=svg_with_hidden,
            spinner_node_id="spinner",
            width=120,
            height=120,
        )
        for call in mock_raster.call_args_list:
            svg_bytes: bytes = call.args[0]
            root = ET.fromstring(svg_bytes)  # noqa: S314
            target = root.find('.//{http://www.w3.org/2000/svg}g[@id="spinner"]')
            assert target is not None
            assert target.get("display") is None

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_missing_node_returns_blank_frames(self, mock_raster):
        frames = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="nonexistent",
            width=120,
            height=120,
        )
        assert len(frames) == SPINNER_FRAME_COUNT
        # All blank frames are identical
        assert len(set(frames)) == 1
        # Rasteriser is not called when placeholder is missing
        mock_raster.assert_not_called()

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_canonical_geometry_is_injected(self, mock_raster):
        get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=120,
            height=120,
        )
        first_svg: bytes = mock_raster.call_args_list[0].args[0]
        # Background rect (from library canonical template)
        assert b'fill-opacity="0.8"' in first_svg
        # 8 rotation bars
        root = ET.fromstring(first_svg)  # noqa: S314
        bars = root.findall(
            './/{http://www.w3.org/2000/svg}g[@id="spinner"]'
            "//{http://www.w3.org/2000/svg}rect"
        )
        # 1 background + 8 bars in the canonical template
        assert len(bars) >= 8

    @patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
    def test_blank_frames_use_bg_tile_when_provided(self, mock_raster):
        tile = Image.new("RGB", (120, 120), (50, 50, 50))
        buf = io.BytesIO()
        tile.save(buf, format="PNG")

        frames = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="missing",
            width=120,
            height=120,
            bg_tile=buf.getvalue(),
        )
        assert len(frames) == SPINNER_FRAME_COUNT
        assert all(f == frames[0] for f in frames)


class TestBuildSpinnerFragment:
    def test_fragment_parses_with_angle(self):
        elem = _build_spinner_fragment(45.0)
        assert elem.tag == "{http://www.w3.org/2000/svg}g"
        rotor = elem.find('.//{http://www.w3.org/2000/svg}g[@class="deux-spinner-rotor"]')
        assert rotor is not None
        assert "rotate(45.0)" in (rotor.get("transform") or "")


class TestBgSignature:
    def test_none_returns_constant(self):
        assert _bg_signature(None) == "none"

    def test_bytes_returns_digest(self):
        sig = _bg_signature(b"abc")
        assert sig != "none"
        assert _bg_signature(b"abc") == sig

    def test_image_returns_digest(self):
        img = Image.new("RGB", (5, 5), (1, 2, 3))
        sig = _bg_signature(img)
        assert sig != "none"
        # Same image bytes → same signature
        img2 = Image.new("RGB", (5, 5), (1, 2, 3))
        assert _bg_signature(img2) == sig
