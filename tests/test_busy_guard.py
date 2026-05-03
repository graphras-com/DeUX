"""Tests for app-controlled busy state on DuiCard and DuiKey, plus spinner manifest validation."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from deckui.dui.card import DuiCard
from deckui.dui.key import DuiKey
from deckui.dui.loader import PackageError, _parse_spinner, load_package
from deckui.dui.schema import (
    Binding,
    EventMapping,
    PackageSpec,
    PackageType,
    SpinnerSpec,
    SpinnerType,
    TextBinding,
)

_CARD_SVG = (
    '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<rect id="bg" width="197" height="98" fill="#1c1c1c"/>'
    '<text id="title" x="4" y="40" font-size="14" fill="#ffffff">Default</text>'
    '<rect id="spinner" x="80" y="30" width="30" height="30" display="none" fill="#fff"/>'
    "</svg>"
)

_KEY_SVG = (
    '<svg id="TestKey" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
    '<text id="label" x="60" y="100" font-size="14" fill="#fff" text-anchor="middle">Key</text>'
    '<rect id="spinner" x="80" y="30" width="30" height="30" display="none" fill="#fff"/>'
    "</svg>"
)


def _fake_png(width: int = 120, height: int = 120) -> bytes:
    img = Image.new("RGB", (width, height), "black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_card_spec(
    spinner: SpinnerSpec | None = None,
    bindings: dict[str, Binding] | None = None,
) -> PackageSpec:
    events = (
        EventMapping(name="action", source="encoder_press"),
    )
    return PackageSpec(
        name="TestCard",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_CARD_SVG,
        bindings=bindings or {},
        events=events,
        spinner=spinner,
    )


def _make_key_spec(
    spinner: SpinnerSpec | None = None,
    bindings: dict[str, Binding] | None = None,
) -> PackageSpec:
    events = (
        EventMapping(name="activate", source="key_press"),
    )
    return PackageSpec(
        name="TestKey",
        type=PackageType.KEY,
        version=1,
        svg_source=_KEY_SVG,
        bindings=bindings or {},
        events=events,
        spinner=spinner,
    )


# ── Card busy state ──────────────────────────────────────────────────


class TestCardBusyState:
    def test_card_not_busy_by_default(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        assert card.is_busy is False

    async def test_card_start_busy_sets_flag(self):
        spec = _make_card_spec()
        card = DuiCard(spec)

        await card.start_busy()
        assert card.is_busy is True

    async def test_card_start_busy_suppresses_duplicate(self):
        """Second start_busy() while already busy is a no-op."""
        spec = _make_card_spec()
        card = DuiCard(spec)

        await card.start_busy()
        await card.start_busy()  # no-op
        assert card.is_busy is True

    async def test_card_finish_busy_clears_flag(self):
        spec = _make_card_spec()
        card = DuiCard(spec)

        await card.start_busy()
        await card.finish_busy()
        assert card.is_busy is False

    async def test_card_finish_busy_marks_dirty(self):
        spec = _make_card_spec()
        card = DuiCard(spec)

        await card.start_busy()
        card.mark_clean()
        await card.finish_busy()
        assert card.is_dirty is True

    async def test_card_finish_busy_noop_when_not_busy(self):
        spec = _make_card_spec()
        card = DuiCard(spec)
        card.mark_clean()
        await card.finish_busy()
        assert card.is_busy is False
        assert card.is_dirty is False

    @patch(
        "deckui.render.svg_rasterize._svg_to_png",
        side_effect=lambda b, w, h: _fake_png(w, h),
    )
    async def test_card_spinner_starts_and_stops(self, mock_raster):
        spinner = SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=4)
        spec = _make_card_spec(spinner=spinner)
        card = DuiCard(spec)

        push_fn = AsyncMock()
        card.set_push_fn(push_fn, panel_size=(200, 100))

        await card.start_busy()
        assert card.is_animating is True

        await card.finish_busy()
        assert card.is_animating is False

    @patch(
        "deckui.render.svg_rasterize._svg_to_png",
        side_effect=lambda b, w, h: _fake_png(w, h),
    )
    async def test_card_spinner_uses_rendered_svg(self, mock_raster):
        """Spinner frames should include current binding values."""
        bindings: dict[str, Binding] = {
            "title": TextBinding(node="title", default="Default"),
        }
        spinner = SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=2)
        spec = _make_card_spec(spinner=spinner, bindings=bindings)
        card = DuiCard(spec)
        card.set("title", "Updated")

        push_fn = AsyncMock()
        card.set_push_fn(push_fn, panel_size=(200, 100))

        await card.start_busy()

        # Inspect what was rasterised — SVG bytes should contain "Updated"
        assert mock_raster.call_count >= 2
        first_svg_bytes: bytes = mock_raster.call_args_list[0][0][0]
        assert b"Updated" in first_svg_bytes

        await card.finish_busy()

    async def test_card_events_dispatch_without_busy(self):
        """Events dispatch normally — no automatic busy wrapping."""
        spec = _make_card_spec()
        card = DuiCard(spec)
        handler = AsyncMock()
        card.bind_event("action", handler)

        card.handle_encoder_press()
        callbacks = card.drain_pending_callbacks()
        assert len(callbacks) == 1
        await callbacks[0][0](*callbacks[0][1])
        handler.assert_awaited_once()
        assert card.is_busy is False


# ── Key busy state ───────────────────────────────────────────────────


class TestKeyBusyState:
    def test_key_not_busy_by_default(self):
        spec = _make_key_spec()
        key = DuiKey(spec)
        assert key.is_busy is False

    async def test_key_start_busy_sets_flag(self):
        spec = _make_key_spec()
        key = DuiKey(spec)

        await key.start_busy()
        assert key.is_busy is True

    async def test_key_start_busy_suppresses_duplicate(self):
        spec = _make_key_spec()
        key = DuiKey(spec)

        await key.start_busy()
        await key.start_busy()  # no-op
        assert key.is_busy is True

    async def test_key_finish_busy_clears_flag(self):
        spec = _make_key_spec()
        key = DuiKey(spec)

        await key.start_busy()
        await key.finish_busy()
        assert key.is_busy is False

    async def test_key_finish_busy_marks_dirty(self):
        spec = _make_key_spec()
        key = DuiKey(spec)

        await key.start_busy()
        key._dirty = False
        await key.finish_busy()
        assert key._dirty is True

    async def test_key_finish_busy_noop_when_not_busy(self):
        spec = _make_key_spec()
        key = DuiKey(spec)
        key._dirty = False
        await key.finish_busy()
        assert key._dirty is False

    @patch(
        "deckui.render.svg_rasterize._svg_to_png",
        side_effect=lambda b, w, h: _fake_png(w, h),
    )
    async def test_key_spinner_starts_and_stops(self, mock_raster):
        spinner = SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=4)
        spec = _make_key_spec(spinner=spinner)
        key = DuiKey(spec)

        push_fn = AsyncMock()
        key.set_push_fn(push_fn, key_size=(120, 120))

        await key.start_busy()
        assert key.is_animating is True

        await key.finish_busy()
        assert key.is_animating is False

    @patch(
        "deckui.render.svg_rasterize._svg_to_png",
        side_effect=lambda b, w, h: _fake_png(w, h),
    )
    async def test_key_spinner_uses_rendered_svg(self, mock_raster):
        """Spinner frames should include current binding values."""
        bindings: dict[str, Binding] = {
            "label": TextBinding(node="label", default="Key"),
        }
        spinner = SpinnerSpec(type=SpinnerType.ROTATION, node="spinner", frames=2)
        spec = _make_key_spec(spinner=spinner, bindings=bindings)
        key = DuiKey(spec)
        key.set("label", "Playing")

        push_fn = AsyncMock()
        key.set_push_fn(push_fn, key_size=(120, 120))

        await key.start_busy()

        assert mock_raster.call_count >= 2
        first_svg_bytes: bytes = mock_raster.call_args_list[0][0][0]
        assert b"Playing" in first_svg_bytes

        await key.finish_busy()

    async def test_key_events_dispatch_without_busy(self):
        """Events dispatch normally — no automatic busy wrapping."""
        spec = _make_key_spec()
        key = DuiKey(spec)
        handler = AsyncMock()
        key.bind_event("activate", handler)

        await key.dispatch(True)
        handler.assert_awaited_once()
        assert key.is_busy is False


# ── Spinner manifest validation ───────────────────────────────────────


class TestSpinnerManifestValidation:
    def test_invalid_spinner_type(self):
        with pytest.raises(PackageError, match="Invalid spinner type"):
            _parse_spinner({"type": "wobble"})

    def test_frames_less_than_2(self):
        with pytest.raises(PackageError, match="frames.*must be an integer >= 2"):
            _parse_spinner({"type": "rotation", "node": "spinner", "frames": 1})

    def test_interval_ms_less_than_10(self):
        with pytest.raises(PackageError, match="interval_ms.*must be an integer >= 10"):
            _parse_spinner({"type": "rotation", "node": "spinner", "interval_ms": 5})

    def test_rotation_without_node_raises(self):
        with pytest.raises(PackageError, match="requires a 'node'"):
            _parse_spinner({"type": "rotation"})

    def test_pulse_without_node_raises(self):
        with pytest.raises(PackageError, match="requires a 'node'"):
            _parse_spinner({"type": "pulse"})

    def test_custom_without_frames_raises(self, tmp_path):
        """Custom spinner with no asset frames should fail."""
        pkg_dir = tmp_path / "Test.dui"
        pkg_dir.mkdir()
        (pkg_dir / "layout.svg").write_text(_CARD_SVG, encoding="utf-8")
        manifest = (
            "name: Test\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "spinner:\n  type: custom\n"
        )
        (pkg_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")

        with pytest.raises(PackageError, match="custom.*requires"):
            load_package(pkg_dir)

    def test_spinner_node_not_in_svg_raises(self, tmp_path):
        """Spinner referencing a node not present in SVG should fail."""
        pkg_dir = tmp_path / "Test.dui"
        pkg_dir.mkdir()
        (pkg_dir / "layout.svg").write_text(_CARD_SVG, encoding="utf-8")
        manifest = (
            "name: Test\ntype: TouchStripCard\nversion: 1\nlayout: layout.svg\n"
            "spinner:\n  type: rotation\n  node: nonexistent\n"
        )
        (pkg_dir / "manifest.yaml").write_text(manifest, encoding="utf-8")

        with pytest.raises(PackageError, match="does not exist in the SVG"):
            load_package(pkg_dir)
