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

from deckui.render.metrics import (
    KEY_MARGIN_LEFT,
    KEY_MARGIN_TOP,
    KEY_SIZE,
    KEY_USABLE_HEIGHT,
    KEY_USABLE_WIDTH,
    MARGIN_LEFT,
    MARGIN_TOP,
    PANEL_COUNT,
    PANEL_GAP,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
)
from deckui.render.svg_rasterize import RasterizeError

if TYPE_CHECKING:
    from pathlib import Path
from deckui.tools.preview import (
    _KEY_COUNT,
    _svg_to_png_fit,
    _watch_and_reload,
    build_parser,
    collect_svg_paths,
    compose_card_image,
    compose_key_image,
    compose_touchstrip,
    get_mtimes,
    load_svg,
    main,
    parse_args,
    parse_hex_color,
    render_preview,
)


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
        """An 80x80 SVG scaled to 80x80 should remain 80x80."""
        img = load_svg(square_svg, 80, 80)
        assert img.size == (80, 80)

    def test_wide_image_constrained_by_width(self, wide_svg: Path):
        """A 200x50 SVG fitted to 197x98 keeps width as the constraint."""
        img = load_svg(wide_svg, PANEL_WIDTH, PANEL_HEIGHT)
        assert img.width <= PANEL_WIDTH
        assert img.height <= PANEL_HEIGHT


class TestComposeKeyImage:
    def test_returns_jpeg_bytes(self):
        svg_img = Image.new("RGBA", (80, 80), (255, 0, 0, 255))
        result = compose_key_image(svg_img)
        assert isinstance(result, bytes)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.format == "JPEG"
        assert decoded.size == KEY_SIZE

    def test_centres_within_usable_area(self):
        """A small image should be centred within the margin-bounded usable area."""
        svg_img = Image.new("RGBA", (40, 40), (255, 0, 0, 255))
        result = compose_key_image(svg_img)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        assert decoded.size == KEY_SIZE

        cx = KEY_MARGIN_LEFT + KEY_USABLE_WIDTH // 2
        cy = KEY_MARGIN_TOP + KEY_USABLE_HEIGHT // 2
        r, g, b = decoded.getpixel((cx, cy))
        assert r > 200, f"Centre of usable area should be red, got ({r}, {g}, {b})"

    def test_left_margin_is_clear(self):
        """Outer edge of left margin should remain black (no content)."""
        svg_img = Image.new(
            "RGBA",
            (KEY_USABLE_WIDTH, KEY_USABLE_HEIGHT),
            (255, 0, 0, 255),
        )
        result = compose_key_image(svg_img)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        mid_y = KEY_SIZE[1] // 2
        r, g, b = decoded.getpixel((0, mid_y))
        assert r < 20, f"Left margin edge pixel (0, {mid_y}) not black: ({r},{g},{b})"

    def test_right_margin_is_clear(self):
        """Outer edge of right margin should remain black (no content)."""
        svg_img = Image.new(
            "RGBA",
            (KEY_USABLE_WIDTH, KEY_USABLE_HEIGHT),
            (255, 0, 0, 255),
        )
        result = compose_key_image(svg_img)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        mid_y = KEY_SIZE[1] // 2
        last_x = KEY_SIZE[0] - 1
        r, g, b = decoded.getpixel((last_x, mid_y))
        assert r < 20, (
            f"Right margin edge pixel ({last_x}, {mid_y}) not black: ({r},{g},{b})"
        )

    def test_rgb_image_no_alpha(self):
        """An RGB image (no alpha) should compose without error."""
        svg_img = Image.new("RGB", (60, 60), (0, 255, 0))
        result = compose_key_image(svg_img)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == KEY_SIZE

    def test_usable_size_image_fills_usable_area(self):
        """A 106x106 image should fill exactly the usable area."""
        svg_img = Image.new(
            "RGBA",
            (KEY_USABLE_WIDTH, KEY_USABLE_HEIGHT),
            (255, 0, 0, 255),
        )
        result = compose_key_image(svg_img)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        assert decoded.size == KEY_SIZE
        cx = KEY_MARGIN_LEFT + KEY_USABLE_WIDTH // 2
        cy = KEY_MARGIN_TOP + KEY_USABLE_HEIGHT // 2
        r, _, _ = decoded.getpixel((cx, cy))
        assert r > 200


class TestComposeCardImage:
    def test_returns_pil_image(self):
        svg_img = Image.new("RGBA", (100, 50), (0, 0, 255, 255))
        result = compose_card_image(svg_img)
        assert isinstance(result, Image.Image)
        assert result.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_centres_image(self):
        """A 100x50 image on a 197x98 canvas should be centred."""
        svg_img = Image.new("RGBA", (100, 50), (255, 0, 0, 255))
        result = compose_card_image(svg_img)
        assert result.size == (PANEL_WIDTH, PANEL_HEIGHT)
        centre_pixel = result.getpixel((PANEL_WIDTH // 2, PANEL_HEIGHT // 2))
        assert centre_pixel != (0, 0, 0)

    def test_rgb_image_no_alpha(self):
        svg_img = Image.new("RGB", (50, 30), (0, 255, 0))
        result = compose_card_image(svg_img)
        assert result.size == (PANEL_WIDTH, PANEL_HEIGHT)

    def test_custom_background_colour(self):
        """A card with no SVG coverage should show the custom background."""
        svg_img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        result = compose_card_image(svg_img, background="#ff0000")
        px = result.getpixel((0, 0))
        assert px == (255, 0, 0)

    def test_default_background_is_black(self):
        svg_img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        result = compose_card_image(svg_img)
        px = result.getpixel((0, 0))
        assert px == (0, 0, 0)


class TestComposeTouchstrip:
    def test_returns_jpeg_bytes(self):
        cards: list[Image.Image | None] = [None] * PANEL_COUNT
        result = compose_touchstrip(cards)
        assert isinstance(result, bytes)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_all_none_produces_black(self):
        cards: list[Image.Image | None] = [None] * PANEL_COUNT
        result = compose_touchstrip(cards)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert all(c < 10 for c in px)

    def test_single_card_placed_correctly(self):
        red_card = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), (255, 0, 0))
        cards: list[Image.Image | None] = [red_card, None, None, None]
        result = compose_touchstrip(cards)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        px = decoded.getpixel((MARGIN_LEFT + 5, MARGIN_TOP + 5))
        assert px[0] > 200

    def test_excess_cards_ignored(self):
        """More than PANEL_COUNT cards should be silently truncated."""
        cards: list[Image.Image | None] = [
            Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), (255, 0, 0)) for _ in range(6)
        ]
        result = compose_touchstrip(cards)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_custom_background_fills_margins(self):
        """The background colour should fill areas outside card panels."""
        cards: list[Image.Image | None] = [None] * PANEL_COUNT
        result = compose_touchstrip(cards, background="#00ff00")
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert px[1] > 200
        assert px[0] < 30
        assert px[2] < 30

    def test_custom_background_between_panels(self):
        """The background colour should fill the gap between card panels."""
        cards: list[Image.Image | None] = [None, None, None, None]
        result = compose_touchstrip(cards, background="#0000ff")
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        gap_x = MARGIN_LEFT + PANEL_WIDTH + PANEL_GAP // 2
        px = decoded.getpixel((gap_x, TOUCHSCREEN_HEIGHT // 2))
        assert px[2] > 200

    def test_default_background_is_black(self):
        cards: list[Image.Image | None] = [None] * PANEL_COUNT
        result = compose_touchstrip(cards)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert all(c < 10 for c in px)


class TestParser:
    def test_no_args(self):
        args = parse_args([])
        for i in range(_KEY_COUNT):
            assert getattr(args, f"key{i}") is None
        for i in range(PANEL_COUNT):
            assert getattr(args, f"card{i}") is None

    def test_key_arg(self, tmp_path: Path):
        args = parse_args(["--key0", str(tmp_path / "k.svg")])
        assert args.key0 == tmp_path / "k.svg"

    def test_card_arg(self, tmp_path: Path):
        args = parse_args(["--card2", str(tmp_path / "c.svg")])
        assert args.card2 == tmp_path / "c.svg"

    def test_all_keys_and_cards(self, tmp_path: Path):
        argv = []
        for i in range(_KEY_COUNT):
            argv.extend([f"--key{i}", str(tmp_path / f"k{i}.svg")])
        for i in range(PANEL_COUNT):
            argv.extend([f"--card{i}", str(tmp_path / f"c{i}.svg")])
        args = parse_args(argv)
        for i in range(_KEY_COUNT):
            assert getattr(args, f"key{i}") == tmp_path / f"k{i}.svg"
        for i in range(PANEL_COUNT):
            assert getattr(args, f"card{i}") == tmp_path / f"c{i}.svg"

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
        key_images, touchstrip = render_preview(args)
        assert key_images == {}
        assert isinstance(touchstrip, bytes)

    def test_with_key_svg(self, square_svg: Path):
        args = parse_args(["--key0", str(square_svg)])
        key_images, touchstrip = render_preview(args)
        assert 0 in key_images
        decoded = Image.open(io.BytesIO(key_images[0]))
        assert decoded.size == KEY_SIZE

    def test_with_card_svg(self, wide_svg: Path):
        args = parse_args(["--card1", str(wide_svg)])
        key_images, touchstrip = render_preview(args)
        assert key_images == {}
        decoded = Image.open(io.BytesIO(touchstrip))
        assert decoded.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

    def test_with_both(self, square_svg: Path, wide_svg: Path):
        args = parse_args(
            [
                "--key3",
                str(square_svg),
                "--card0",
                str(wide_svg),
            ]
        )
        key_images, touchstrip = render_preview(args)
        assert 3 in key_images
        assert isinstance(touchstrip, bytes)

    def test_missing_key_svg_exits(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        args = parse_args(["--key0", str(tmp_path / "nonexistent.svg")])
        with pytest.raises(SystemExit):
            render_preview(args)
        assert "Key SVG not found" in capsys.readouterr().err

    def test_missing_card_svg_exits(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        args = parse_args(["--card0", str(tmp_path / "nonexistent.svg")])
        with pytest.raises(SystemExit):
            render_preview(args)
        assert "Card SVG not found" in capsys.readouterr().err

    def test_background_applies_to_touchstrip(self, wide_svg: Path):
        """When --background is given, the touchstrip uses that colour."""
        args = parse_args(["--card0", str(wide_svg), "--background", "#00ff00"])
        _, touchstrip = render_preview(args)
        decoded = Image.open(io.BytesIO(touchstrip)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert px[1] > 200

    def test_no_background_defaults_black(self):
        args = parse_args([])
        _, touchstrip = render_preview(args)
        decoded = Image.open(io.BytesIO(touchstrip)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert all(c < 10 for c in px)


class TestMain:
    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_calls_push(self, mock_push: AsyncMock, square_svg: Path):
        main(["--key0", str(square_svg)])
        mock_push.assert_awaited_once()
        kwargs = mock_push.call_args
        key_images, touchstrip, brightness = kwargs[0]
        assert 0 in key_images
        assert isinstance(touchstrip, bytes)
        assert brightness == 80
        assert kwargs[1]["watch_args"] is None

    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_default_brightness(self, mock_push: AsyncMock):
        main([])
        _, _, brightness = mock_push.call_args[0]
        assert brightness == 80

    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_custom_brightness(self, mock_push: AsyncMock):
        main(["--brightness", "40"])
        _, _, brightness = mock_push.call_args[0]
        assert brightness == 40

    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_verbose(self, mock_push: AsyncMock):
        main(["-v"])
        mock_push.assert_awaited_once()

    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_with_background(self, mock_push: AsyncMock):
        main(["--background", "#aabbcc"])
        mock_push.assert_awaited_once()
        _, touchstrip, _ = mock_push.call_args[0]
        decoded = Image.open(io.BytesIO(touchstrip)).convert("RGB")
        px = decoded.getpixel((0, 0))
        assert px[0] > 150
        assert px[1] > 160
        assert px[2] > 180

    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_watch_passes_args(self, mock_push: AsyncMock, square_svg: Path):
        main(["--key0", str(square_svg), "--watch"])
        kwargs = mock_push.call_args
        assert kwargs[1]["watch_args"] is not None
        assert kwargs[1]["watch_args"].watch is True

    @patch("deckui.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_poll_interval(self, mock_push: AsyncMock):
        main(["--watch", "--poll-interval", "1.5"])
        kwargs = mock_push.call_args
        assert kwargs[1]["poll_interval"] == 1.5


class TestPushToDevice:
    async def test_push_opens_and_pushes(self, mock_streamdeck_device: MagicMock):
        from deckui.tools.preview import push_to_device

        blank_key = Image.new("RGB", KEY_SIZE, "black")
        buf = io.BytesIO()
        blank_key.save(buf, format="JPEG")
        key_jpeg = buf.getvalue()

        blank_ts = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        buf2 = io.BytesIO()
        blank_ts.save(buf2, format="JPEG")
        ts_jpeg = buf2.getvalue()

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
            await push_to_device({0: key_jpeg}, ts_jpeg, brightness=60)

        mock_streamdeck_device.set_brightness.assert_called_once_with(60)
        mock_streamdeck_device.set_key_image.assert_called_once_with(0, key_jpeg)
        mock_streamdeck_device.set_touchscreen_image.assert_called_once_with(
            ts_jpeg,
            0,
            0,
            TOUCHSCREEN_WIDTH,
            TOUCHSCREEN_HEIGHT,
        )
        mock_streamdeck_device.reset.assert_called_once()
        mock_streamdeck_device.close.assert_called_once()

    async def test_brightness_clamped(self, mock_streamdeck_device: MagicMock):
        """Values outside 0-100 are clamped."""
        from deckui.tools.preview import push_to_device

        blank_ts = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        buf = io.BytesIO()
        blank_ts.save(buf, format="JPEG")
        ts_jpeg = buf.getvalue()

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
            await push_to_device({}, ts_jpeg, brightness=150)

        mock_streamdeck_device.set_brightness.assert_called_once_with(100)


class TestWaitForInterrupt:
    async def test_returns_on_sigint(self):
        """The coroutine completes when SIGINT is delivered."""
        import signal

        from deckui.tools.preview import _wait_for_interrupt

        loop = asyncio.get_running_loop()

        loop.call_later(0.05, os.kill, os.getpid(), signal.SIGINT)
        await asyncio.wait_for(_wait_for_interrupt(), timeout=1.0)

    async def test_signal_handler_removed_after_return(self):
        """The SIGINT handler is cleaned up after _wait_for_interrupt returns."""
        import signal

        from deckui.tools.preview import _wait_for_interrupt

        loop = asyncio.get_running_loop()
        loop.call_later(0.05, os.kill, os.getpid(), signal.SIGINT)
        await asyncio.wait_for(_wait_for_interrupt(), timeout=1.0)

        assert loop.remove_signal_handler(signal.SIGINT) is False


class TestSvgToPngFit:
    def test_tall_svg_constrained_by_height(self, tmp_path: Path):
        """An SVG taller than max_height triggers the height-constrained path."""
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="200">'
            b'<rect width="20" height="200" fill="red"/>'
            b"</svg>"
        )
        png_bytes = _svg_to_png_fit(svg, 80, 80)
        img = Image.open(io.BytesIO(png_bytes))
        assert img.height <= 80

    def test_cairosvg_fallback_to_rsvg(self):
        """When cairosvg is unavailable, fall back to rsvg-convert."""
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            b'<rect width="10" height="10" fill="red"/>'
            b"</svg>"
        )
        fake_png = Image.new("RGB", (10, 10), "red")
        buf = io.BytesIO()
        fake_png.save(buf, format="PNG")
        fake_png_bytes = buf.getvalue()

        with (
            patch.dict("sys.modules", {"cairosvg": None}),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout=fake_png_bytes)
            result = _svg_to_png_fit(svg, 80, 80)
            assert result == fake_png_bytes
            mock_run.assert_called_once()

    def test_no_renderer_raises(self):
        """When both cairosvg and rsvg-convert fail, raise RasterizeError."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'

        with patch.dict("sys.modules", {"cairosvg": None}), patch(
            "subprocess.run",
            side_effect=FileNotFoundError("no rsvg"),
        ), pytest.raises(RasterizeError, match="No SVG renderer"):
            _svg_to_png_fit(svg, 80, 80)


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
        """Importing __main__ should call main()."""
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
        """When an SVG file mtime changes, _watch_and_reload re-pushes."""
        args = parse_args(["--key0", str(square_svg), "--watch"])

        call_count = 0

        def counting_set_key(key: int, image: bytes) -> None:
            nonlocal call_count
            call_count += 1

        mock_streamdeck_device.set_key_image.side_effect = counting_set_key

        loop = asyncio.get_running_loop()
        # Schedule: touch file after 0.1s, then SIGINT after 0.8s
        loop.call_later(0.1, square_svg.write_bytes, square_svg.read_bytes())
        loop.call_later(1.0, os.kill, os.getpid(), signal.SIGINT)

        await asyncio.wait_for(
            _watch_and_reload(args, mock_streamdeck_device, poll_interval=0.2),
            timeout=3.0,
        )
        assert call_count >= 1

    async def test_exits_on_sigint(self, mock_streamdeck_device: MagicMock):
        """_watch_and_reload exits cleanly on SIGINT."""
        args = parse_args(["--watch"])

        loop = asyncio.get_running_loop()
        loop.call_later(0.1, os.kill, os.getpid(), signal.SIGINT)

        await asyncio.wait_for(
            _watch_and_reload(args, mock_streamdeck_device, poll_interval=0.2),
            timeout=2.0,
        )

    async def test_render_error_continues(
        self, square_svg: Path, mock_streamdeck_device: MagicMock
    ):
        """A render error during watch should not crash the watcher."""
        args = parse_args(["--key0", str(square_svg), "--watch"])

        loop = asyncio.get_running_loop()
        # Write invalid SVG to trigger render error, then SIGINT
        loop.call_later(0.1, square_svg.write_bytes, b"not valid svg")
        loop.call_later(1.0, os.kill, os.getpid(), signal.SIGINT)

        # Should not raise
        await asyncio.wait_for(
            _watch_and_reload(args, mock_streamdeck_device, poll_interval=0.2),
            timeout=3.0,
        )


class TestPushToDeviceWatch:
    async def test_push_with_watch_calls_watch_and_reload(
        self, mock_streamdeck_device: MagicMock, square_svg: Path
    ):
        """When watch_args is provided, push_to_device enters watch mode."""
        from deckui.tools.preview import push_to_device

        blank_ts = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        buf = io.BytesIO()
        blank_ts.save(buf, format="JPEG")
        ts_jpeg = buf.getvalue()

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
            await push_to_device(
                {}, ts_jpeg, brightness=80, watch_args=args, poll_interval=0.5
            )

        mock_watch.assert_awaited_once_with(args, mock_streamdeck_device, 0.5)
