"""Tests for the process-wide spinner frame LRU cache."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from PIL import Image

from deux.dui import spinner as spinner_mod
from deux.dui.spinner import (
    SPINNER_FRAME_COUNT,
    _bg_signature,
    clear_cache,
    get_frames,
)

_SPINNER_SVG = (
    '<svg id="C" xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    '<g id="spinner" transform="translate(50 50)"/>'
    "</svg>"
)

_SPINNER_SVG_ALT = (
    '<svg id="C" xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    '<text id="x">other</text>'
    '<g id="spinner" transform="translate(50 50)"/>'
    "</svg>"
)


def _fake_image(svg_data, width, height, *, mode="RGBA", ctx=None):
    return Image.new(mode, (width, height), "black")


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_cache()
    yield
    clear_cache()


@patch("deux.render.svg_rasterize._svg_to_image", side_effect=_fake_image)
class TestCacheBehaviour:
    """LRU cache identity, eviction, and key composition."""

    def test_repeat_call_reuses_cached_frames(self, mock_raster):
        first = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
        )
        calls = mock_raster.call_count
        second = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
        )
        assert second is first
        assert mock_raster.call_count == calls  # no extra rasterisations

    def test_different_svg_creates_distinct_entry(self, mock_raster):
        a = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
        )
        b = get_frames(
            rendered_svg=_SPINNER_SVG_ALT,
            spinner_node_id="spinner",
            width=64,
            height=64,
        )
        assert b is not a
        assert mock_raster.call_count == 2 * SPINNER_FRAME_COUNT

    def test_different_size_creates_distinct_entry(self, mock_raster):
        a = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
        )
        b = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=128,
            height=128,
        )
        assert b is not a

    def test_different_format_creates_distinct_entry(self, mock_raster):
        a = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
            image_format="JPEG",
        )
        b = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
            image_format="BMP",
        )
        assert b is not a

    def test_different_bg_tile_creates_distinct_entry(self, mock_raster):
        tile1 = Image.new("RGB", (64, 64), (0, 0, 0))
        buf1 = io.BytesIO()
        tile1.save(buf1, format="PNG")
        tile2 = Image.new("RGB", (64, 64), (200, 200, 200))
        buf2 = io.BytesIO()
        tile2.save(buf2, format="PNG")

        a = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
            bg_tile=buf1.getvalue(),
        )
        b = get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
            bg_tile=buf2.getvalue(),
        )
        assert a is not b

    def test_clear_cache_evicts_all(self, mock_raster):
        get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
        )
        clear_cache()
        before = mock_raster.call_count
        get_frames(
            rendered_svg=_SPINNER_SVG,
            spinner_node_id="spinner",
            width=64,
            height=64,
        )
        assert mock_raster.call_count == before + SPINNER_FRAME_COUNT

    def test_lru_eviction(self, mock_raster, monkeypatch):
        monkeypatch.setattr(spinner_mod, "_CACHE_MAX_ENTRIES", 2)

        svgs = [
            _SPINNER_SVG,
            _SPINNER_SVG_ALT,
            _SPINNER_SVG.replace("100", "101"),
        ]
        for svg in svgs:
            get_frames(
                rendered_svg=svg,
                spinner_node_id="spinner",
                width=64,
                height=64,
            )
        assert len(spinner_mod._cache) == 2

        # Oldest (svgs[0]) was evicted → re-fetching forces re-render.
        before = mock_raster.call_count
        get_frames(
            rendered_svg=svgs[0],
            spinner_node_id="spinner",
            width=64,
            height=64,
        )
        assert mock_raster.call_count == before + SPINNER_FRAME_COUNT


class TestBgSignatureStability:
    def test_same_bytes_same_signature(self):
        a = b"\x00\x01\x02"
        assert _bg_signature(a) == _bg_signature(a)

    def test_different_bytes_different_signature(self):
        assert _bg_signature(b"a") != _bg_signature(b"b")
