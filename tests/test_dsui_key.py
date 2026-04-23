"""Tests for deckui.dsui.key — DsuiKey class."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from PIL import Image

from deckui.dsui.key import DsuiKey
from deckui.dsui.schema import (
    EventMapping,
    PackageSpec,
    PackageType,
    RangeBinding,
    TextBinding,
    ToggleBinding,
)
from deckui.ui.controls.key_slot import KeySlot
from deckui.ui.screen import Screen

_KEY_SVG = (
    '<svg id="TestKey" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
    '<text id="label" x="60" y="100" font-size="14" fill="#ffffff">Key</text>'
    "</svg>"
)


def _make_key_spec(
    bindings: dict | None = None,
    events: tuple | None = None,
) -> PackageSpec:
    return PackageSpec(
        name="TestKey",
        type=PackageType.KEY,
        version=1,
        svg_source=_KEY_SVG,
        bindings=bindings or {},
        events=events or (),
    )


class TestDsuiKeyIsKeySlot:
    def test_is_key_slot_subclass(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        assert isinstance(key, KeySlot)

    def test_has_index_after_set_key(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        screen = Screen("test")
        screen.set_key(3, key)
        assert key.index == 3

    def test_has_spec(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        assert key.spec is spec

    def test_has_dsui_content(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        assert key.has_dsui_content is True


class TestDsuiKeyDataBinding:
    def test_set_marks_dirty(self):
        spec = _make_key_spec(bindings={"label": TextBinding(node="label", default="")})
        key = DsuiKey(spec)
        key.mark_clean()
        key.set("label", "Hello")
        assert key.is_dirty is True

    def test_set_same_not_dirty(self):
        spec = _make_key_spec(
            bindings={"label": TextBinding(node="label", default="Same")}
        )
        key = DsuiKey(spec)
        key.mark_clean()
        key.set("label", "Same")
        assert key.is_dirty is False

    def test_set_returns_self(self):
        spec = _make_key_spec(bindings={"label": TextBinding(node="label", default="")})
        key = DsuiKey(spec)
        assert key.set("label", "Test") is key

    def test_set_many(self):
        spec = _make_key_spec(bindings={"label": TextBinding(node="label", default="")})
        key = DsuiKey(spec)
        key.mark_clean()
        result = key.set_many(label="New")
        assert result is key
        assert key.is_dirty is True

    def test_set_many_no_change(self):
        spec = _make_key_spec(
            bindings={"label": TextBinding(node="label", default="Same")}
        )
        key = DsuiKey(spec)
        key.mark_clean()
        key.set_many(label="Same")
        assert key.is_dirty is False

    def test_get(self):
        spec = _make_key_spec(
            bindings={"label": TextBinding(node="label", default="Init")}
        )
        key = DsuiKey(spec)
        assert key.get("label") == "Init"

    def test_set_unknown_raises(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        with pytest.raises(KeyError):
            key.set("nope", "val")

    def test_get_unknown_raises(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        with pytest.raises(KeyError):
            key.get("nope")


class TestDsuiKeyRender:
    def test_render_image_returns_bytes(self):
        spec = _make_key_spec(
            bindings={"label": TextBinding(node="label", default="Test")}
        )
        key = DsuiKey(spec)
        data = key.render_image()
        assert isinstance(data, bytes)
        assert len(data) > 0
        assert data[:2] == b"\xff\xd8"

    def test_render_image_is_120x120(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        data = key.render_image()
        import io

        img = Image.open(io.BytesIO(data))
        assert img.size == (120, 120)

    def test_render_with_non_key_size_svg(self):
        """SVG is 197x98 (card size) but DsuiKey should resize to 120x120."""
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
            '<rect id="bg" width="197" height="98" fill="#333"/>'
            '<text id="label" x="10" y="50" fill="white">Test</text>'
            "</svg>"
        )
        spec = PackageSpec(
            name="WideKey",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={"label": TextBinding(node="label", default="Hi")},
        )
        key = DsuiKey(spec)
        data = key.render_image()
        import io

        img = Image.open(io.BytesIO(data))
        assert img.size == (120, 120)


class TestDsuiKeyToggleBinding:
    _TOGGLE_KEY_SVG = (
        '<svg id="TK" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
        '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
        '<path id="on_icon" d="M20 20 L60 20 L60 60 L20 60 Z" fill="#00ff00"/>'
        '<path id="off_icon" d="M20 20 L60 20 L60 60 L20 60 Z" fill="#ff0000"/>'
        "</svg>"
    )

    def _make_toggle_spec(self):
        return PackageSpec(
            name="ToggleKey",
            type=PackageType.KEY,
            version=1,
            svg_source=self._TOGGLE_KEY_SVG,
            bindings={
                "state": ToggleBinding(
                    node_on="on_icon", node_off="off_icon", default=False
                ),
            },
        )

    def test_set_toggle_marks_dirty(self):
        spec = self._make_toggle_spec()
        key = DsuiKey(spec)
        key.mark_clean()
        key.set("state", True)
        assert key.is_dirty is True

    def test_set_toggle_same_value_not_dirty(self):
        spec = self._make_toggle_spec()
        key = DsuiKey(spec)
        key.mark_clean()
        key.set("state", False)
        assert key.is_dirty is False

    def test_get_toggle_value(self):
        spec = self._make_toggle_spec()
        key = DsuiKey(spec)
        assert key.get("state") is False
        key.set("state", True)
        assert key.get("state") is True

    def test_toggle_renders_different_images(self):
        spec = self._make_toggle_spec()
        key = DsuiKey(spec)
        data_off = key.render_image()

        key.set("state", True)
        data_on = key.render_image()

        assert data_off != data_on


class TestDsuiKeyEvents:
    def test_on_event_decorator(self):
        spec = _make_key_spec(
            events=(EventMapping(name="activate", source="key_press"),),
        )
        key = DsuiKey(spec)

        @key.on_event("activate")
        async def handler():
            pass

        assert handler is not None

    def test_bind_event(self):
        spec = _make_key_spec(
            events=(EventMapping(name="activate", source="key_press"),),
        )
        key = DsuiKey(spec)
        handler = AsyncMock()
        key.bind_event("activate", handler)

    async def test_dispatch_press_routes_to_event_map(self):
        spec = _make_key_spec(
            events=(EventMapping(name="activate", source="key_press"),),
        )
        key = DsuiKey(spec)
        handler = AsyncMock()
        key.bind_event("activate", handler)

        await key.dispatch(True)
        handler.assert_awaited_once()

    async def test_dispatch_release_routes_to_event_map(self):
        spec = _make_key_spec(
            events=(EventMapping(name="up", source="key_release"),),
        )
        key = DsuiKey(spec)
        handler = AsyncMock()
        key.bind_event("up", handler)

        await key.dispatch(True)
        await key.dispatch(False)
        handler.assert_awaited_once()

    async def test_dispatch_falls_back_to_base(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        base_handler = AsyncMock()
        key.on_press(base_handler)

        await key.dispatch(True)
        base_handler.assert_awaited_once()

    async def test_dispatch_release_falls_back(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        base_handler = AsyncMock()
        key.on_release(base_handler)

        await key.dispatch(False)
        base_handler.assert_awaited_once()

    async def test_key_press_release_gesture(self):
        spec = _make_key_spec(
            events=(
                EventMapping(
                    name="tap", source="key_press_release", max_duration_ms=500
                ),
            ),
        )
        key = DsuiKey(spec)
        handler = AsyncMock()
        key.bind_event("tap", handler)

        await key.dispatch(True)
        await key.dispatch(False)
        handler.assert_awaited_once()


class TestDsuiKeyDirtyTracking:
    def test_starts_dirty(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        assert key.is_dirty is True

    def test_set_rendered_image_clears_dirty(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        key.set_rendered_image(b"\xff\xd8fake_jpeg")
        assert key.is_dirty is False

    def test_mark_clean(self):
        spec = _make_key_spec()
        key = DsuiKey(spec)
        key.mark_clean()
        assert key.is_dirty is False


_KEY_BAR_SVG = (
    '<svg id="TestKey" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<rect id="bg" width="120" height="120" fill="#1c1c1c"/>'
    '<rect id="bar" x="4" y="100" width="112" height="4" fill="#00ff00"/>'
    "</svg>"
)


class TestDsuiKeyRangeHelpers:
    """Tests for set_range, adjust_range, and get_range on DsuiKey."""

    def _make_range_key(self, default: float = 0.0) -> DsuiKey:
        spec = PackageSpec(
            name="TestKey",
            type=PackageType.KEY,
            version=1,
            svg_source=_KEY_BAR_SVG,
            bindings={"level": RangeBinding(node="bar", default=default)},
            events=(),
        )
        return DsuiKey(spec)

    def test_set_range_normalises(self):
        key = self._make_range_key()
        key.set_range("level", 50, min_val=0, max_val=100)
        assert key.get("level") == pytest.approx(0.5)

    def test_set_range_returns_self(self):
        key = self._make_range_key()
        result = key.set_range("level", 50, min_val=0, max_val=100)
        assert result is key

    def test_set_range_clamps(self):
        key = self._make_range_key()
        key.set_range("level", 200, min_val=0, max_val=100)
        assert key.get("level") == pytest.approx(1.0)

    def test_adjust_range(self):
        key = self._make_range_key(default=0.5)
        new_val = key.adjust_range("level", 10, min_val=0, max_val=100)
        assert new_val == pytest.approx(60.0)

    def test_get_range(self):
        key = self._make_range_key(default=0.75)
        val = key.get_range("level", min_val=0, max_val=100)
        assert val == pytest.approx(75.0)

    def test_equal_min_max_raises(self):
        key = self._make_range_key()
        with pytest.raises(ValueError):
            key.set_range("level", 5, min_val=5, max_val=5)
        with pytest.raises(ValueError):
            key.adjust_range("level", 1, min_val=5, max_val=5)
        with pytest.raises(ValueError):
            key.get_range("level", min_val=5, max_val=5)
