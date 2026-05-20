"""Tests for icon preloading, collect_icon_names, and batch screen rendering."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deux.dui import iconify as iconify_mod
from deux.dui.iconify import (
    clear_cache,
    fetch_icon,
    prefetch_icons,
)
from deux.dui.schema import (
    IconifyBinding,
    ListBinding,
    PackageSpec,
    PackageType,
    TextBinding,
)
from deux.dui.svg_renderer import SvgRenderer
from deux.render.metrics import RenderMetrics
from deux.runtime.capabilities import STREAM_DECK_PLUS
from deux.runtime.deck import Deck
from deux.ui.screen import Screen

_SAMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" '
    'viewBox="0 0 24 24"><path fill="currentColor" d="M0 0"/></svg>'
)

_BASIC_SVG = (
    '<svg id="test" xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect id="bg" width="100" height="50" fill="#000000"/>'
    '<text id="label" x="10" y="30" font-size="12" fill="#fff">Hi</text>'
    '<g id="icon_group"></g>'
    "</svg>"
)


@pytest.fixture(autouse=True)
def _isolate_iconify_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reset the iconify cache and redirect disk cache to tmp_path."""
    clear_cache(persistent=True)
    fake_dir = tmp_path / "iconify"
    fake_dir.mkdir()

    def _fake_get_dir() -> Path:
        fake_dir.mkdir(parents=True, exist_ok=True)
        return fake_dir

    monkeypatch.setattr(iconify_mod, "_get_disk_cache_dir", _fake_get_dir)
    monkeypatch.setattr(iconify_mod, "_disk_cache_dir", fake_dir)
    yield
    clear_cache(persistent=True)


@pytest.fixture(autouse=True)
def _bypass_ssrf():
    """Bypass SSRF checks."""
    with patch("deux.dui.iconify.check_url"):
        yield


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


# -----------------------------------------------------------------------
# prefetch_icons
# -----------------------------------------------------------------------


class TestPrefetchIcons:
    """Tests for :func:`deux.dui.iconify.prefetch_icons`."""

    async def test_prefetch_warms_cache(self):
        """Prefetched icons are served from cache on subsequent fetch_icon calls."""
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG) as mock:
            result = await prefetch_icons(["mdi:home", "mdi:settings"])

        assert result["mdi:home"] == _SAMPLE_SVG
        assert result["mdi:settings"] == _SAMPLE_SVG
        assert mock.call_count == 2

        # Now fetch_icon should hit cache
        with patch.object(iconify_mod, "_http_get") as mock2:
            svg = fetch_icon("mdi:home")
        mock2.assert_not_called()
        assert svg == _SAMPLE_SVG

    async def test_prefetch_deduplicates(self):
        """Duplicate icon names are fetched only once."""
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG) as mock:
            result = await prefetch_icons(["mdi:home", "mdi:home", "mdi:home"])

        assert mock.call_count == 1
        assert len(result) == 1

    async def test_prefetch_empty_iterable(self):
        """Empty input returns empty dict without errors."""
        result = await prefetch_icons([])
        assert result == {}

    async def test_prefetch_handles_failures_gracefully(self):
        """Failed icons return None without raising."""

        def _side_effect(url: str) -> str:
            if "missing" in url:
                return "404"
            return _SAMPLE_SVG

        with patch.object(iconify_mod, "_http_get", side_effect=_side_effect):
            result = await prefetch_icons(["mdi:home", "mdi:missing"])

        assert result["mdi:home"] == _SAMPLE_SVG
        assert result["mdi:missing"] is None


# -----------------------------------------------------------------------
# SvgRenderer.collect_icon_names
# -----------------------------------------------------------------------


class TestCollectIconNames:
    """Tests for :meth:`SvgRenderer.collect_icon_names`."""

    def test_collects_iconify_defaults(self):
        """IconifyBinding defaults are collected."""
        spec = _make_spec(
            _BASIC_SVG,
            bindings={
                "play_icon": IconifyBinding(
                    node="icon_group", size=24, default="mdi:play"
                ),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.collect_icon_names() == {"mdi:play"}

    def test_collects_current_iconify_value(self):
        """Changed iconify value is also collected."""
        spec = _make_spec(
            _BASIC_SVG,
            bindings={
                "play_icon": IconifyBinding(
                    node="icon_group", size=24, default="mdi:play"
                ),
            },
        )
        renderer = SvgRenderer(spec)
        renderer.set("play_icon", "mdi:pause")
        icons = renderer.collect_icon_names()
        assert "mdi:play" in icons
        assert "mdi:pause" in icons

    def test_collects_list_icon_items(self):
        """ListBinding items with 'icon:' prefix are collected."""
        spec = _make_spec(
            _BASIC_SVG,
            bindings={
                "menu": ListBinding(
                    node="icon_group",
                    child_tag="tspan",
                    default_items=["icon:mdi:home", "Text", "icon:mdi:cog"],
                ),
            },
        )
        renderer = SvgRenderer(spec)
        icons = renderer.collect_icon_names()
        assert "mdi:home" in icons
        assert "mdi:cog" in icons
        assert len(icons) == 2

    def test_empty_when_no_icon_bindings(self):
        """Spec with only text bindings returns empty set."""
        spec = _make_spec(
            _BASIC_SVG,
            bindings={
                "label": TextBinding(node="label", default="Hello"),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.collect_icon_names() == set()

    def test_collects_list_icon_from_current_value(self):
        """ListBinding current value items with 'icon:' prefix are collected."""
        spec = _make_spec(
            _BASIC_SVG,
            bindings={
                "menu": ListBinding(
                    node="icon_group",
                    child_tag="tspan",
                    default_items=["icon:mdi:home"],
                ),
            },
        )
        renderer = SvgRenderer(spec)
        renderer.set("menu", {"items": ["icon:mdi:star", "Text"], "index": 0})
        icons = renderer.collect_icon_names()
        assert "mdi:home" in icons
        assert "mdi:star" in icons

    def test_iconify_empty_default_skipped(self):
        """IconifyBinding with empty default does not add empty string."""
        spec = _make_spec(
            _BASIC_SVG,
            bindings={
                "icon": IconifyBinding(node="icon_group", size=24, default=""),
            },
        )
        renderer = SvgRenderer(spec)
        assert renderer.collect_icon_names() == set()


# -----------------------------------------------------------------------
# Screen.collect_all_icons
# -----------------------------------------------------------------------


class TestScreenCollectAllIcons:
    """Tests for :meth:`Screen.collect_all_icons`."""

    def test_collects_from_dui_keys(self, key_dui_path: Path):
        """Icons from DuiKey bindings are collected."""
        from deux.dui.key import DuiKey

        screen = Screen("test", STREAM_DECK_PLUS)

        # Create a DuiKey with iconify bindings by modifying the manifest
        svg = (
            '<svg id="TestKey" xmlns="http://www.w3.org/2000/svg" '
            'width="120" height="120">'
            '<g id="icon_g"></g></svg>'
        )
        spec = PackageSpec(
            name="IconKey",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={
                "icon": IconifyBinding(node="icon_g", size=24, default="mdi:power"),
            },
        )
        key = DuiKey(spec)
        screen.set_key(0, key)

        icons = screen.collect_all_icons()
        assert "mdi:power" in icons

    def test_collects_from_dui_cards(self):
        """Icons from DuiCard bindings are collected."""
        from deux.dui.card import DuiCard

        screen = Screen("test", STREAM_DECK_PLUS)

        svg = (
            '<svg id="TestCard" xmlns="http://www.w3.org/2000/svg" '
            'width="197" height="98">'
            '<g id="icon_g"></g></svg>'
        )
        spec = PackageSpec(
            name="IconCard",
            type=PackageType.TOUCH_STRIP_CARD,
            version=1,
            svg_source=svg,
            bindings={
                "icon": IconifyBinding(node="icon_g", size=24, default="mdi:music"),
            },
        )
        card = DuiCard(spec)
        screen.set_card(0, card)

        icons = screen.collect_all_icons()
        assert "mdi:music" in icons

    def test_empty_for_plain_keys(self):
        """Screen with only plain KeySlots returns empty set."""
        screen = Screen("test", STREAM_DECK_PLUS)
        screen.key(0)
        assert screen.collect_all_icons() == set()


# -----------------------------------------------------------------------
# DeckRenderer.render_screen_complete
# -----------------------------------------------------------------------


class TestRenderScreenComplete:
    """Tests for :meth:`DeckRenderer.render_screen_complete`."""

    def _make_deck_with_screen(self) -> Deck:
        """Create a Deck with a mock device and active screen."""
        deck = Deck(serial_number="TEST123")
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)
        deck._device = MagicMock()
        deck._device.set_key_image.return_value = None
        deck._device.set_partial_window_image.return_value = None
        return deck

    async def test_render_screen_complete_calls_prefetch(self):
        """render_screen_complete prefetches icons before rendering."""
        deck = self._make_deck_with_screen()
        screen = deck.screen("main")
        deck._active_screen = screen

        with patch(
            "deux.runtime.renderer.DeckRenderer.render_all_keys",
            new_callable=AsyncMock,
        ) as mock_keys, patch(
            "deux.runtime.renderer.DeckRenderer.render_touchscreen",
            new_callable=AsyncMock,
        ), patch(
            "deux.dui.iconify.prefetch_icons",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_prefetch:
            # Add a DuiKey with an icon to the screen
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
                '<g id="icon_g"></g></svg>'
            )
            from deux.dui.key import DuiKey

            spec = PackageSpec(
                name="IK",
                type=PackageType.KEY,
                version=1,
                svg_source=svg,
                bindings={
                    "icon": IconifyBinding(
                        node="icon_g", size=24, default="mdi:play"
                    ),
                },
            )
            screen.set_key(0, DuiKey(spec))

            await deck._renderer.render_screen_complete()

            mock_prefetch.assert_awaited_once_with({"mdi:play"})
            mock_keys.assert_awaited_once()

    async def test_render_screen_complete_skips_when_no_screen(self):
        """render_screen_complete is a no-op when no screen is active."""
        deck = self._make_deck_with_screen()
        # No active screen
        await deck._renderer.render_screen_complete()
        # Should not raise


# -----------------------------------------------------------------------
# Deck.set_screen uses render_screen_complete
# -----------------------------------------------------------------------


class TestDeckSetScreenIntegration:
    """Tests for Deck.set_screen using render_screen_complete."""

    async def test_set_screen_calls_render_screen_complete(self):
        """set_screen delegates to render_screen_complete."""
        deck = Deck(serial_number="TEST123")
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)
        deck._device = MagicMock()
        deck._device.set_key_image.return_value = None
        deck._device.set_partial_window_image.return_value = None
        deck.screen("main")

        with patch.object(
            deck._renderer,
            "render_screen_complete",
            new_callable=AsyncMock,
        ) as mock_complete:
            await deck.set_screen("main")
            mock_complete.assert_awaited_once()


# -----------------------------------------------------------------------
# Deck.set_theme
# -----------------------------------------------------------------------


class TestDeckSetTheme:
    """Tests for :meth:`Deck.set_theme`."""

    async def test_set_theme_triggers_full_render(self):
        """set_theme applies theme and re-renders the entire screen."""
        deck = Deck(serial_number="TEST123")
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)
        deck._device = MagicMock()
        deck._device.set_key_image.return_value = None
        deck._device.set_partial_window_image.return_value = None

        deck.screen("main")
        deck._active_screen = deck._screens["main"]

        with patch.object(
            deck._renderer,
            "render_screen_complete",
            new_callable=AsyncMock,
        ) as mock_complete, patch.object(
            deck._renderer, "apply_theme"
        ) as mock_apply:
            from deux.render.theme import Theme

            theme = Theme(primary=(0, 0, 0))
            await deck.set_theme(theme)

            mock_apply.assert_called_once()
            mock_complete.assert_awaited_once()
            assert deck._theme is theme

    async def test_set_theme_noop_when_no_screen(self):
        """set_theme without an active screen only sets the property."""
        deck = Deck(serial_number="TEST123")
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        from deux.render.theme import Theme

        theme = Theme(primary=(0, 0, 0))
        await deck.set_theme(theme)

        assert deck._theme is theme

    async def test_set_theme_none_clears(self):
        """Setting theme to None clears the deck theme."""
        deck = Deck(serial_number="TEST123")
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        from deux.render.theme import Theme

        deck._theme = Theme(primary=(0, 0, 0))
        await deck.set_theme(None)
        assert deck._theme is None


# -----------------------------------------------------------------------
# Deck.preload_icons
# -----------------------------------------------------------------------


class TestDeckPreloadIcons:
    """Tests for :meth:`Deck.preload_icons`."""

    async def test_preload_icons_collects_all_screens(self):
        """preload_icons aggregates icons from all registered screens."""
        deck = Deck(serial_number="TEST123")
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)

        from deux.dui.key import DuiKey

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
            '<g id="icon_g"></g></svg>'
        )

        # Screen 1 with one icon
        s1 = deck.screen("main")
        spec1 = PackageSpec(
            name="K1",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={
                "icon": IconifyBinding(node="icon_g", size=24, default="mdi:home"),
            },
        )
        s1.set_key(0, DuiKey(spec1))

        # Screen 2 with a different icon
        s2 = deck.screen("settings")
        spec2 = PackageSpec(
            name="K2",
            type=PackageType.KEY,
            version=1,
            svg_source=svg,
            bindings={
                "icon": IconifyBinding(node="icon_g", size=24, default="mdi:cog"),
            },
        )
        s2.set_key(0, DuiKey(spec2))

        with patch(
            "deux.dui.iconify.prefetch_icons",
            new_callable=AsyncMock,
            return_value={},
        ) as mock_prefetch:
            await deck.preload_icons()

            called_icons = mock_prefetch.call_args[0][0]
            assert "mdi:home" in called_icons
            assert "mdi:cog" in called_icons

    async def test_preload_icons_noop_when_no_icons(self):
        """preload_icons does not call prefetch when no icons exist."""
        deck = Deck(serial_number="TEST123")
        deck._caps = STREAM_DECK_PLUS
        deck._metrics = RenderMetrics(STREAM_DECK_PLUS)
        deck.screen("empty")

        with patch(
            "deux.dui.iconify.prefetch_icons",
            new_callable=AsyncMock,
        ) as mock_prefetch:
            await deck.preload_icons()
            mock_prefetch.assert_not_awaited()
