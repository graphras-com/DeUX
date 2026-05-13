"""Tests for deckui.tools.preview — SVG preview CLI tool."""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import signal
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from deckui.render.svg_rasterize import RasterizeError
from deckui.runtime.capabilities import STREAM_DECK_PLUS

if TYPE_CHECKING:
    from pathlib import Path
from deckui.tools.preview import (
    _MAX_CARD_SLOTS,
    _MAX_KEY_SLOTS,
    _svg_to_png_fit,
    _watch_and_reload,
    build_parser,
    collect_svg_paths,
    compose_card_image,
    compose_full_touchstrip,
    compose_key_image,
    compose_touchstrip,
    get_mtimes,
    load_svg,
    main,
    parse_args,
    parse_hex_color,
    render_preview,
)

KEY_SIZE = STREAM_DECK_PLUS.key_size
TOUCHSCREEN_SIZE = (STREAM_DECK_PLUS.touchscreen_width, STREAM_DECK_PLUS.touchscreen_height)
PANEL_COUNT = STREAM_DECK_PLUS.panel_count
PANEL_WIDTH = STREAM_DECK_PLUS.touchscreen_width // STREAM_DECK_PLUS.panel_count
PANEL_HEIGHT = STREAM_DECK_PLUS.touchscreen_height
PANEL_SIZE = (PANEL_WIDTH, PANEL_HEIGHT)


@pytest.fixture
def tiny_svg(tmp_path: Path) -> Path:
    """Write a minimal valid SVG and return its path."""
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
        b'<rect width="40" height="20" fill="red"/>'
        b"</svg>"
    )
    p = tmp_path / "icon.svg"
    p.write_bytes(svg)
    return p


@pytest.fixture
def square_svg(tmp_path: Path) -> Path:
    """Write a square SVG for key tests."""
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80">'
        b'<rect width="80" height="80" fill="blue"/>'
        b"</svg>"
    )
    p = tmp_path / "square.svg"
    p.write_bytes(svg)
    return p


@pytest.fixture
def wide_svg(tmp_path: Path) -> Path:
    """Write a wide SVG for card tests."""
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="50">'
        b'<rect width="200" height="50" fill="green"/>'
        b"</svg>"
    )
    p = tmp_path / "wide.svg"
    p.write_bytes(svg)
    return p


@pytest.fixture
def touchstrip_svg(tmp_path: Path) -> Path:
    """Write an 800x100 SVG for full touchstrip tests."""
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="100">'
        b'<rect width="800" height="100" fill="cyan"/>'
        b"</svg>"
    )
    p = tmp_path / "touchstrip.svg"
    p.write_bytes(svg)
    return p


class TestParseHexColor:
    def test_hash_prefix(self):
        assert parse_hex_color("#1a2b3c") == "#1a2b3c"

    def test_no_hash_prefix(self):
        assert parse_hex_color("ff00aa") == "#ff00aa"

    def test_uppercase_normalised(self):
        assert parse_hex_color("#AABBCC") == "#aabbcc"

    def test_mixed_case(self):
        assert parse_hex_color("AaBbCc") == "#aabbcc"

    def test_all_zeros(self):
        assert parse_hex_color("000000") == "#000000"

    def test_all_f(self):
        assert parse_hex_color("FFFFFF") == "#ffffff"

    def test_invalid_too_short(self):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid hex colour"):
            parse_hex_color("#abc")

    def test_invalid_too_long(self):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid hex colour"):
            parse_hex_color("#1234567")

    def test_invalid_chars(self):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid hex colour"):
            parse_hex_color("#gghhii")

    def test_empty_string(self):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid hex colour"):
            parse_hex_color("")

    def test_hash_only(self):
        with pytest.raises(argparse.ArgumentTypeError, match="invalid hex colour"):
            parse_hex_color("#")


class TestLoadSvg:
    def test_returns_rgba_image(self, tiny_svg: Path):
        img = load_svg(tiny_svg, 80, 80)
        assert img.mode == "RGBA"

    def test_fits_within_bounds(self, tiny_svg: Path):
        img = load_svg(tiny_svg, 80, 80)
        assert img.width <= 80
        assert img.height <= 80

    def test_preserves_aspect_ratio(self, tiny_svg: Path):
        """A 40x20 SVG scaled to 80x80 should be 80x40 (2:1 ratio)."""
        img = load_svg(tiny_svg, 80, 80)
        assert img.width == 80
        assert img.height == 40

    def test_exact_fit(self, square_svg: Path):
        img = load_svg(square_svg, 80, 80)
        assert img.size == (80, 80)

    def test_wide_image_constrained(self, wide_svg: Path):
        img = load_svg(wide_svg, PANEL_WIDTH, PANEL_HEIGHT)
        assert img.width <= PANEL_WIDTH
        assert img.height <= PANEL_HEIGHT


class TestComposeKeyImage:
    def test_returns_jpeg_bytes(self):
        svg_img = Image.new("RGBA", (80, 80), (255, 0, 0, 255))
        result = compose_key_image(svg_img, KEY_SIZE)
        assert isinstance(result, bytes)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.format == "JPEG"
        assert decoded.size == KEY_SIZE

    def test_centres_within_canvas(self):
        """A small image should be centred on the key canvas."""
        svg_img = Image.new("RGBA", (40, 40), (255, 0, 0, 255))
        result = compose_key_image(svg_img, KEY_SIZE)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        assert decoded.size == KEY_SIZE
        cx = KEY_SIZE[0] // 2
        cy = KEY_SIZE[1] // 2
        r, _, _ = decoded.getpixel((cx, cy))
        assert r > 200, "Centre of key should be red"

    def test_full_size_image_fills_edge_to_edge(self):
        """A key-sized image fills the canvas — no margin."""
        svg_img = Image.new("RGBA", KEY_SIZE, (255, 0, 0, 255))
        result = compose_key_image(svg_img, KEY_SIZE)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        # Top-left corner: SVG paints all the way to (0, 0).
        r, _, _ = decoded.getpixel((0, 0))
        assert r > 200

    def test_rgb_image_no_alpha(self):
        svg_img = Image.new("RGB", (60, 60), (0, 255, 0))
        result = compose_key_image(svg_img, KEY_SIZE)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == KEY_SIZE

    def test_custom_background(self):
        """Background colour shows where the SVG doesn't cover."""
        svg_img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        result = compose_key_image(svg_img, KEY_SIZE, background="#0000ff")
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        r, g, b = decoded.getpixel((0, 0))
        assert b > 200 and r < 30


class TestComposeCardImage:
    def test_returns_pil_image(self):
        svg_img = Image.new("RGBA", (100, 50), (0, 0, 255, 255))
        result = compose_card_image(svg_img, PANEL_SIZE)
        assert isinstance(result, Image.Image)
        assert result.size == PANEL_SIZE

    def test_centres_image(self):
        svg_img = Image.new("RGBA", (100, 50), (255, 0, 0, 255))
        result = compose_card_image(svg_img, PANEL_SIZE)
        assert result.size == PANEL_SIZE
        centre_pixel = result.getpixel((PANEL_WIDTH // 2, PANEL_HEIGHT // 2))
        assert centre_pixel != (0, 0, 0)

    def test_rgb_image_no_alpha(self):
        svg_img = Image.new("RGB", (50, 30), (0, 255, 0))
        result = compose_card_image(svg_img, PANEL_SIZE)
        assert result.size == PANEL_SIZE

    def test_custom_background_colour(self):
        svg_img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        result = compose_card_image(svg_img, PANEL_SIZE, background="#ff0000")
        px = result.getpixel((0, 0))
        assert px == (255, 0, 0)

    def test_default_background_is_black(self):
        svg_img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        result = compose_card_image(svg_img, PANEL_SIZE)
        px = result.getpixel((0, 0))
        assert px == (0, 0, 0)


class TestComposeTouchstrip:
    def _kwargs(self):
        return {
            "touchscreen_width": TOUCHSCREEN_SIZE[0],
            "touchscreen_height": TOUCHSCREEN_SIZE[1],
            "panel_count": PANEL_COUNT,
            "panel_width": PANEL_WIDTH,
        }

    def test_returns_jpeg_bytes(self):
        cards: list[Image.Image | None] = [None] * PANEL_COUNT
        result = compose_touchstrip(cards, **self._kwargs())
        assert isinstance(result, bytes)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == TOUCHSCREEN_SIZE

    def test_all_none_produces_black(self):
        cards: list[Image.Image | None] = [None] * PANEL_COUNT
        result = compose_touchstrip(cards, **self._kwargs())
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert all(c < 10 for c in px)

    def test_single_card_placed_at_panel_origin(self):
        red_card = Image.new("RGB", PANEL_SIZE, (255, 0, 0))
        cards: list[Image.Image | None] = [red_card, None, None, None]
        result = compose_touchstrip(cards, **self._kwargs())
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        px = decoded.getpixel((5, 5))
        assert px[0] > 200

    def test_excess_cards_ignored(self):
        cards: list[Image.Image | None] = [
            Image.new("RGB", PANEL_SIZE, (255, 0, 0)) for _ in range(6)
        ]
        result = compose_touchstrip(cards, **self._kwargs())
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == TOUCHSCREEN_SIZE

    def test_cards_tile_edge_to_edge(self):
        """Cards span the full touchscreen width — no gap between them."""
        red = Image.new("RGB", PANEL_SIZE, (255, 0, 0))
        green = Image.new("RGB", PANEL_SIZE, (0, 255, 0))
        cards: list[Image.Image | None] = [red, green, None, None]
        result = compose_touchstrip(cards, **self._kwargs())
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        # Pixels inside each panel, away from JPEG block boundaries.
        r0, _, _ = decoded.getpixel((PANEL_WIDTH - 16, PANEL_HEIGHT // 2))
        _, g1, _ = decoded.getpixel((PANEL_WIDTH + 16, PANEL_HEIGHT // 2))
        assert r0 > 200
        assert g1 > 200

    def test_default_background_is_black(self):
        cards: list[Image.Image | None] = [None] * PANEL_COUNT
        result = compose_touchstrip(cards, **self._kwargs())
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert all(c < 10 for c in px)

    def test_custom_background(self):
        cards: list[Image.Image | None] = [None] * PANEL_COUNT
        result = compose_touchstrip(cards, background="#00ff00", **self._kwargs())
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert px[1] > 200


class TestParser:
    def test_no_args(self):
        args = parse_args([])
        for i in range(_MAX_KEY_SLOTS):
            assert getattr(args, f"key{i}") is None
        for i in range(_MAX_CARD_SLOTS):
            assert getattr(args, f"card{i}") is None

    def test_key_arg(self, tmp_path: Path):
        args = parse_args(["--key0", str(tmp_path / "k.svg")])
        assert args.key0 == tmp_path / "k.svg"

    def test_card_arg(self, tmp_path: Path):
        args = parse_args(["--card2", str(tmp_path / "c.svg")])
        assert args.card2 == tmp_path / "c.svg"

    def test_brightness_default(self):
        args = parse_args([])
        assert args.brightness == 80

    def test_brightness_custom(self):
        args = parse_args(["--brightness", "50"])
        assert args.brightness == 50

    def test_brightness_short(self):
        args = parse_args(["-b", "30"])
        assert args.brightness == 30

    def test_verbose_flag(self):
        args = parse_args(["-v"])
        assert args.verbose is True

    def test_verbose_long(self):
        args = parse_args(["--verbose"])
        assert args.verbose is True

    def test_renderer_default_auto(self):
        args = parse_args([])
        assert args.renderer == "auto"

    def test_renderer_short_flag(self):
        args = parse_args(["-r", "cairo"])
        assert args.renderer == "cairo"

    def test_renderer_long_flag(self):
        args = parse_args(["--renderer", "pyvips"])
        assert args.renderer == "pyvips"

    def test_build_parser_returns_parser(self):
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_background_default_none(self):
        args = parse_args([])
        assert args.background is None

    def test_background_with_hash(self):
        args = parse_args(["--background", "#1a2b3c"])
        assert args.background == "#1a2b3c"

    def test_background_without_hash(self):
        args = parse_args(["--background", "ff00aa"])
        assert args.background == "#ff00aa"

    def test_background_invalid_exits(self):
        with pytest.raises(SystemExit):
            parse_args(["--background", "nope"])


class TestRenderPreview:
    def test_no_files(self):
        args = parse_args([])
        key_images, touchstrip = render_preview(args, STREAM_DECK_PLUS)
        assert key_images == {}
        assert isinstance(touchstrip, bytes)

    def test_with_key_svg(self, square_svg: Path):
        args = parse_args(["--key0", str(square_svg)])
        key_images, _ = render_preview(args, STREAM_DECK_PLUS)
        assert 0 in key_images
        decoded = Image.open(io.BytesIO(key_images[0]))
        assert decoded.size == KEY_SIZE

    def test_with_card_svg(self, wide_svg: Path):
        args = parse_args(["--card1", str(wide_svg)])
        key_images, touchstrip = render_preview(args, STREAM_DECK_PLUS)
        assert key_images == {}
        decoded = Image.open(io.BytesIO(touchstrip))
        assert decoded.size == TOUCHSCREEN_SIZE

    def test_with_both(self, square_svg: Path, wide_svg: Path):
        args = parse_args(
            [
                "--key3",
                str(square_svg),
                "--card0",
                str(wide_svg),
            ]
        )
        key_images, touchstrip = render_preview(args, STREAM_DECK_PLUS)
        assert 3 in key_images
        assert isinstance(touchstrip, bytes)

    def test_missing_key_svg_exits(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        args = parse_args(["--key0", str(tmp_path / "nonexistent.svg")])
        with pytest.raises(SystemExit):
            render_preview(args, STREAM_DECK_PLUS)
        assert "Key SVG not found" in capsys.readouterr().err

    def test_missing_card_svg_exits(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        args = parse_args(["--card0", str(tmp_path / "nonexistent.svg")])
        with pytest.raises(SystemExit):
            render_preview(args, STREAM_DECK_PLUS)
        assert "Card SVG not found" in capsys.readouterr().err

    def test_background_applies_to_touchstrip(self, wide_svg: Path):
        args = parse_args(["--card0", str(wide_svg), "--background", "#00ff00"])
        _, touchstrip = render_preview(args, STREAM_DECK_PLUS)
        decoded = Image.open(io.BytesIO(touchstrip)).convert("RGB")
        # Pixel near the right edge of the touchscreen — outside card0,
        # so the background colour shows through.
        px = decoded.getpixel((TOUCHSCREEN_SIZE[0] - 5, TOUCHSCREEN_SIZE[1] // 2))
        assert px[1] > 200

    def test_no_background_defaults_black(self):
        args = parse_args([])
        _, touchstrip = render_preview(args, STREAM_DECK_PLUS)
        decoded = Image.open(io.BytesIO(touchstrip)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert all(c < 10 for c in px)

    def test_no_touchscreen_returns_empty_bytes(self, square_svg: Path):
        """A device without a touchscreen produces empty touchstrip bytes."""
        from tests.conftest import STREAM_DECK_MINI

        args = parse_args(["--key0", str(square_svg)])
        key_images, touchstrip = render_preview(args, STREAM_DECK_MINI)
        assert 0 in key_images
        assert touchstrip == b""

    def test_key_size_matches_caps(self, square_svg: Path):
        """Key images render at caps.key_size, not a fixed default."""
        from tests.conftest import STREAM_DECK_MINI

        args = parse_args(["--key0", str(square_svg)])
        key_images, _ = render_preview(args, STREAM_DECK_MINI)
        decoded = Image.open(io.BytesIO(key_images[0]))
        assert decoded.size == STREAM_DECK_MINI.key_size


class TestPushToDevice:
    async def test_push_renders_and_pushes(
        self, mock_streamdeck_device: MagicMock, square_svg: Path
    ):
        from deckui.tools.preview import push_to_device

        # The device protocol-cast accepts the StreamDeck mock
        mock_streamdeck_device.DECK_VISUAL = True

        args = parse_args(["--key0", str(square_svg), "--brightness", "60"])

        with (
            patch(
                "deckui.tools.preview._find_and_open_device",
                return_value=mock_streamdeck_device,
            ),
            patch(
                "deckui.tools.preview._wait_for_interrupt",
                new_callable=AsyncMock,
            ),
        ):
            await push_to_device(args)

        mock_streamdeck_device.set_brightness.assert_called_once_with(60)
        # Key 0 was pushed
        key_calls = [
            c for c in mock_streamdeck_device.set_key_image.call_args_list
            if c.args[0] == 0
        ]
        assert len(key_calls) == 1
        # Touchstrip pushed once (Stream Deck+ has touchscreen)
        mock_streamdeck_device.set_touchscreen_image.assert_called_once()
        mock_streamdeck_device.reset.assert_called_once()
        mock_streamdeck_device.close.assert_called_once()

    async def test_brightness_clamped(self, mock_streamdeck_device: MagicMock):
        from deckui.tools.preview import push_to_device

        mock_streamdeck_device.DECK_VISUAL = True
        args = parse_args(["--brightness", "150"])

        with (
            patch(
                "deckui.tools.preview._find_and_open_device",
                return_value=mock_streamdeck_device,
            ),
            patch(
                "deckui.tools.preview._wait_for_interrupt",
                new_callable=AsyncMock,
            ),
        ):
            await push_to_device(args)

        mock_streamdeck_device.set_brightness.assert_called_once_with(100)

    async def test_no_touchscreen_skips_touchstrip_push(
        self, mock_mini_device: MagicMock
    ):
        """A device without a touchscreen does not call set_touchscreen_image."""
        from deckui.tools.preview import push_to_device

        mock_mini_device.DECK_VISUAL = True
        args = parse_args([])

        with (
            patch(
                "deckui.tools.preview._find_and_open_device",
                return_value=mock_mini_device,
            ),
            patch(
                "deckui.tools.preview._wait_for_interrupt",
                new_callable=AsyncMock,
            ),
        ):
            await push_to_device(args)

        mock_mini_device.set_touchscreen_image.assert_not_called()


class TestMain:
    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_calls_push(self, mock_push: AsyncMock, square_svg: Path):
        main(["--key0", str(square_svg)])
        mock_push.assert_awaited_once()
        args = mock_push.call_args.args[0]
        assert args.key0 == square_svg

    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_passes_poll_interval(self, mock_push: AsyncMock):
        main(["--poll-interval", "1.5"])
        kwargs = mock_push.call_args.kwargs
        assert kwargs["poll_interval"] == 1.5

    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_verbose(self, mock_push: AsyncMock):
        main(["-v"])
        mock_push.assert_awaited_once()


class TestWaitForInterrupt:
    async def test_returns_on_sigint(self):
        from deckui.tools.preview import _wait_for_interrupt

        loop = asyncio.get_running_loop()
        loop.call_later(0.05, os.kill, os.getpid(), signal.SIGINT)
        await asyncio.wait_for(_wait_for_interrupt(), timeout=1.0)

    async def test_signal_handler_removed_after_return(self):
        from deckui.tools.preview import _wait_for_interrupt

        loop = asyncio.get_running_loop()
        loop.call_later(0.05, os.kill, os.getpid(), signal.SIGINT)
        await asyncio.wait_for(_wait_for_interrupt(), timeout=1.0)
        assert loop.remove_signal_handler(signal.SIGINT) is False


class TestSvgToPngFit:
    def test_tall_svg_constrained_by_height(self, tmp_path: Path):
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="200">'
            b'<rect width="20" height="200" fill="red"/>'
            b"</svg>"
        )
        png_bytes = _svg_to_png_fit(svg, 80, 80)
        img = Image.open(io.BytesIO(png_bytes))
        assert img.height <= 80

    def test_cairosvg_fallback_to_rsvg(self):
        """When the first backend fails, auto mode falls through to the next."""
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            b'<rect width="10" height="10" fill="red"/>'
            b"</svg>"
        )
        fake_png = Image.new("RGB", (10, 10), "red")
        buf = io.BytesIO()
        fake_png.save(buf, format="PNG")
        fake_png_bytes = buf.getvalue()

        import deckui.render.svg_rasterize as svg_mod

        class FailBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                raise RasterizeError("fail")

        class SuccessBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                return fake_png_bytes

        old_registry = svg_mod._registry.copy()
        old_active = svg_mod._active_backend
        try:
            svg_mod._registry["cairo"] = FailBackend()  # type: ignore[assignment]
            svg_mod._registry["pyvips"] = SuccessBackend()  # type: ignore[assignment]
            svg_mod._active_backend = None  # auto mode
            result = _svg_to_png_fit(svg, 80, 80)
            assert result == fake_png_bytes
        finally:
            svg_mod._registry = old_registry
            svg_mod._active_backend = old_active

    def test_no_renderer_raises(self):
        """When all backends fail in auto mode, RasterizeError is raised."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'

        import deckui.render.svg_rasterize as svg_mod

        class FailBackend:
            def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
                raise RasterizeError("fail")

        old_registry = svg_mod._registry.copy()
        old_active = svg_mod._active_backend
        try:
            for name in list(svg_mod._registry):
                svg_mod._registry[name] = FailBackend()  # type: ignore[assignment]
            svg_mod._active_backend = None  # auto mode
            with pytest.raises(RasterizeError):
                _svg_to_png_fit(svg, 80, 80)
        finally:
            svg_mod._registry = old_registry
            svg_mod._active_backend = old_active


class TestFindAndOpenDevice:
    def test_no_devices_exits(self, capsys: pytest.CaptureFixture[str]):
        from deckui.tools.preview import _find_and_open_device

        mock_dm = MagicMock()
        mock_dm.return_value.enumerate.return_value = []
        with patch(
            "StreamDeck.DeviceManager.DeviceManager",
            mock_dm,
        ), pytest.raises(SystemExit):
            _find_and_open_device()
        assert "No Stream Deck devices found" in capsys.readouterr().err

    def test_no_visual_devices_exits(self, capsys: pytest.CaptureFixture[str]):
        from deckui.tools.preview import _find_and_open_device

        device = MagicMock()
        device.DECK_VISUAL = False
        mock_dm = MagicMock()
        mock_dm.return_value.enumerate.return_value = [device]
        with patch(
            "StreamDeck.DeviceManager.DeviceManager",
            mock_dm,
        ), pytest.raises(SystemExit):
            _find_and_open_device()
        assert "No visual Stream Deck devices found" in capsys.readouterr().err

    def test_opens_first_visual_device(self):
        from deckui.tools.preview import _find_and_open_device

        device = MagicMock()
        device.DECK_VISUAL = True
        mock_dm = MagicMock()
        mock_dm.return_value.enumerate.return_value = [device]
        with patch(
            "StreamDeck.DeviceManager.DeviceManager",
            mock_dm,
        ):
            result = _find_and_open_device()
        device.open.assert_called_once()
        assert result is device


class TestMainModule:
    @patch("deckui.tools.preview.main")
    def test_main_module(self, mock_main: MagicMock):
        import importlib

        import deckui.tools.__main__

        importlib.reload(deckui.tools.__main__)
        mock_main.assert_called()


class TestCollectSvgPaths:
    def test_empty_args(self):
        args = parse_args([])
        assert collect_svg_paths(args) == []

    def test_collects_keys_and_cards(self, tmp_path: Path):
        k = tmp_path / "k.svg"
        c = tmp_path / "c.svg"
        args = parse_args(["--key0", str(k), "--card2", str(c)])
        paths = collect_svg_paths(args)
        assert k in paths
        assert c in paths
        assert len(paths) == 2

    def test_order_keys_before_cards(self, tmp_path: Path):
        k = tmp_path / "k.svg"
        c = tmp_path / "c.svg"
        args = parse_args(["--card0", str(c), "--key0", str(k)])
        paths = collect_svg_paths(args)
        assert paths[0] == k
        assert paths[1] == c


class TestGetMtimes:
    def test_existing_file(self, tiny_svg: Path):
        mtimes = get_mtimes([tiny_svg])
        assert tiny_svg in mtimes
        assert mtimes[tiny_svg] > 0

    def test_missing_file(self, tmp_path: Path):
        missing = tmp_path / "gone.svg"
        mtimes = get_mtimes([missing])
        assert mtimes[missing] == 0.0

    def test_empty_list(self):
        assert get_mtimes([]) == {}


class TestParserWatch:
    def test_watch_default_false(self):
        args = parse_args([])
        assert args.watch is False

    def test_watch_flag(self):
        args = parse_args(["--watch"])
        assert args.watch is True

    def test_watch_short(self):
        args = parse_args(["-w"])
        assert args.watch is True

    def test_poll_interval_default(self):
        args = parse_args([])
        assert args.poll_interval == 0.5

    def test_poll_interval_custom(self):
        args = parse_args(["--poll-interval", "2.0"])
        assert args.poll_interval == 2.0


class TestWatchAndReload:
    async def test_detects_change_and_reloads(
        self, square_svg: Path, mock_streamdeck_device: MagicMock
    ):
        args = parse_args(["--key0", str(square_svg), "--watch"])

        call_count = 0

        def counting_set_key(key: int, image: bytes) -> None:
            nonlocal call_count
            call_count += 1

        mock_streamdeck_device.set_key_image.side_effect = counting_set_key

        loop = asyncio.get_running_loop()
        loop.call_later(0.1, square_svg.write_bytes, square_svg.read_bytes())
        loop.call_later(1.0, os.kill, os.getpid(), signal.SIGINT)

        await asyncio.wait_for(
            _watch_and_reload(
                args,
                mock_streamdeck_device,
                STREAM_DECK_PLUS,
                PANEL_WIDTH,
                poll_interval=0.2,
            ),
            timeout=3.0,
        )
        assert call_count >= 1

    async def test_exits_on_sigint(self, mock_streamdeck_device: MagicMock):
        args = parse_args(["--watch"])

        loop = asyncio.get_running_loop()
        loop.call_later(0.1, os.kill, os.getpid(), signal.SIGINT)

        await asyncio.wait_for(
            _watch_and_reload(
                args,
                mock_streamdeck_device,
                STREAM_DECK_PLUS,
                PANEL_WIDTH,
                poll_interval=0.2,
            ),
            timeout=2.0,
        )

    async def test_render_error_continues(
        self, square_svg: Path, mock_streamdeck_device: MagicMock
    ):
        args = parse_args(["--key0", str(square_svg), "--watch"])

        loop = asyncio.get_running_loop()
        loop.call_later(0.1, square_svg.write_bytes, b"not valid svg")
        loop.call_later(1.0, os.kill, os.getpid(), signal.SIGINT)

        await asyncio.wait_for(
            _watch_and_reload(
                args,
                mock_streamdeck_device,
                STREAM_DECK_PLUS,
                PANEL_WIDTH,
                poll_interval=0.2,
            ),
            timeout=3.0,
        )


class TestPushToDeviceWatch:
    async def test_push_with_watch_invokes_watch(
        self, mock_streamdeck_device: MagicMock, square_svg: Path
    ):
        from deckui.tools.preview import push_to_device

        mock_streamdeck_device.DECK_VISUAL = True
        args = parse_args(["--key0", str(square_svg), "--watch"])

        with (
            patch(
                "deckui.tools.preview._find_and_open_device",
                return_value=mock_streamdeck_device,
            ),
            patch(
                "deckui.tools.preview._watch_and_reload",
                new_callable=AsyncMock,
            ) as mock_watch,
        ):
            await push_to_device(args, poll_interval=0.5)

        mock_watch.assert_awaited_once()


class TestMainRendererFlag:
    """Tests that ``main()`` applies the ``--renderer`` flag."""

    def test_main_sets_renderer(self):
        """``--renderer`` flag calls ``set_svg_backend`` before running."""
        with (
            patch("deckui.tools.preview.set_svg_backend") as mock_set,
            patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock),
        ):
            main(["--renderer", "cairo"])
            mock_set.assert_called_once_with("cairo")

    def test_main_auto_skips_set(self):
        """``--renderer auto`` (default) does not call ``set_svg_backend``."""
        with (
            patch("deckui.tools.preview.set_svg_backend") as mock_set,
            patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock),
        ):
            main([])
            mock_set.assert_not_called()


class TestComposeFullTouchstrip:
    """Tests for ``compose_full_touchstrip``."""

    def test_returns_jpeg_bytes(self):
        svg_img = Image.new("RGBA", TOUCHSCREEN_SIZE, (0, 255, 255, 255))
        result = compose_full_touchstrip(svg_img, TOUCHSCREEN_SIZE)
        assert isinstance(result, bytes)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.format == "JPEG"
        assert decoded.size == TOUCHSCREEN_SIZE

    def test_centres_smaller_image(self):
        """A smaller image is centred on the touchstrip canvas."""
        svg_img = Image.new("RGBA", (400, 50), (255, 0, 0, 255))
        result = compose_full_touchstrip(svg_img, TOUCHSCREEN_SIZE)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        cx, cy = TOUCHSCREEN_SIZE[0] // 2, TOUCHSCREEN_SIZE[1] // 2
        r, _, _ = decoded.getpixel((cx, cy))
        assert r > 200

    def test_full_size_fills_edge_to_edge(self):
        svg_img = Image.new("RGBA", TOUCHSCREEN_SIZE, (0, 255, 0, 255))
        result = compose_full_touchstrip(svg_img, TOUCHSCREEN_SIZE)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        _, g, _ = decoded.getpixel((0, 0))
        assert g > 200

    def test_rgb_image_no_alpha(self):
        svg_img = Image.new("RGB", TOUCHSCREEN_SIZE, (0, 0, 255))
        result = compose_full_touchstrip(svg_img, TOUCHSCREEN_SIZE)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == TOUCHSCREEN_SIZE

    def test_custom_background(self):
        svg_img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        result = compose_full_touchstrip(svg_img, TOUCHSCREEN_SIZE, background="#ff0000")
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        r, _, _ = decoded.getpixel((0, 0))
        assert r > 200


class TestParserTouchstrip:
    """Tests for the ``--touchstrip`` CLI flag."""

    def test_touchstrip_default_none(self):
        args = parse_args([])
        assert args.touchstrip is None

    def test_touchstrip_accepts_path(self, tmp_path: Path):
        p = tmp_path / "ts.svg"
        args = parse_args(["--touchstrip", str(p)])
        assert args.touchstrip == p

    def test_touchstrip_conflicts_with_card(self, tmp_path: Path):
        ts = tmp_path / "ts.svg"
        card = tmp_path / "c.svg"
        with pytest.raises(SystemExit):
            parse_args(["--touchstrip", str(ts), "--card0", str(card)])

    def test_touchstrip_conflicts_with_any_card(self, tmp_path: Path):
        ts = tmp_path / "ts.svg"
        card = tmp_path / "c.svg"
        with pytest.raises(SystemExit):
            parse_args(["--touchstrip", str(ts), "--card3", str(card)])


class TestRenderPreviewTouchstrip:
    """Tests for render_preview with --touchstrip."""

    def test_touchstrip_flag_renders_full(self, touchstrip_svg: Path):
        args = parse_args(["--touchstrip", str(touchstrip_svg)])
        key_images, touchstrip = render_preview(args, STREAM_DECK_PLUS)
        assert key_images == {}
        decoded = Image.open(io.BytesIO(touchstrip))
        assert decoded.size == TOUCHSCREEN_SIZE

    def test_touchstrip_with_keys(self, touchstrip_svg: Path, square_svg: Path):
        args = parse_args([
            "--touchstrip", str(touchstrip_svg),
            "--key0", str(square_svg),
        ])
        key_images, touchstrip = render_preview(args, STREAM_DECK_PLUS)
        assert 0 in key_images
        decoded = Image.open(io.BytesIO(touchstrip))
        assert decoded.size == TOUCHSCREEN_SIZE

    def test_touchstrip_missing_svg_exits(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        args = parse_args(["--touchstrip", str(tmp_path / "nonexistent.svg")])
        with pytest.raises(SystemExit):
            render_preview(args, STREAM_DECK_PLUS)
        assert "Touchstrip SVG not found" in capsys.readouterr().err

    def test_touchstrip_background(self, touchstrip_svg: Path):
        args = parse_args([
            "--touchstrip", str(touchstrip_svg),
            "--background", "#ff0000",
        ])
        _, touchstrip = render_preview(args, STREAM_DECK_PLUS)
        assert isinstance(touchstrip, bytes)
        decoded = Image.open(io.BytesIO(touchstrip))
        assert decoded.size == TOUCHSCREEN_SIZE


class TestCollectSvgPathsTouchstrip:
    """Tests for collect_svg_paths with --touchstrip."""

    def test_includes_touchstrip_path(self, tmp_path: Path):
        ts = tmp_path / "ts.svg"
        args = parse_args(["--touchstrip", str(ts)])
        paths = collect_svg_paths(args)
        assert ts in paths

    def test_touchstrip_after_keys(self, tmp_path: Path):
        k = tmp_path / "k.svg"
        ts = tmp_path / "ts.svg"
        args = parse_args(["--touchstrip", str(ts), "--key0", str(k)])
        paths = collect_svg_paths(args)
        assert paths[0] == k
        assert paths[-1] == ts
