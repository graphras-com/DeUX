"""Tests for deckboard.tools.preview — SVG preview CLI tool."""

from __future__ import annotations

import argparse
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from deckboard.render.metrics import (
    ICON_PADDING,
    ICON_SIZE,
    KEY_SIZE,
    MARGIN_LEFT,
    MARGIN_TOP,
    PANEL_COUNT,
    PANEL_GAP,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    TOUCHSCREEN_HEIGHT,
    TOUCHSCREEN_WIDTH,
)
from deckboard.render.icons import IconError
from deckboard.tools.preview import (
    _KEY_COUNT,
    _svg_to_png_fit,
    build_parser,
    compose_card_image,
    compose_key_image,
    compose_touchstrip,
    load_svg,
    main,
    parse_args,
    render_preview,
)


# -- Fixtures ----------------------------------------------------------------


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


# -- load_svg ----------------------------------------------------------------


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


# -- compose_key_image -------------------------------------------------------


class TestComposeKeyImage:
    def test_returns_jpeg_bytes(self):
        svg_img = Image.new("RGBA", (80, 80), (255, 0, 0, 255))
        result = compose_key_image(svg_img)
        assert isinstance(result, bytes)
        # Verify it's valid JPEG
        decoded = Image.open(io.BytesIO(result))
        assert decoded.format == "JPEG"
        assert decoded.size == KEY_SIZE

    def test_centres_icon_in_key(self):
        """A small image should be centred in the icon area."""
        svg_img = Image.new("RGBA", (40, 40), (255, 0, 0, 255))
        result = compose_key_image(svg_img)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == KEY_SIZE

    def test_rgb_image_no_alpha(self):
        """An RGB image (no alpha) should compose without error."""
        svg_img = Image.new("RGB", (60, 60), (0, 255, 0))
        result = compose_key_image(svg_img)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == KEY_SIZE

    def test_full_size_icon(self):
        """An 80x80 icon should be placed at (ICON_PADDING, ICON_PADDING)."""
        svg_img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (255, 0, 0, 255))
        result = compose_key_image(svg_img)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == KEY_SIZE


# -- compose_card_image ------------------------------------------------------


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
        # The non-black centre should contain the image
        centre_pixel = result.getpixel((PANEL_WIDTH // 2, PANEL_HEIGHT // 2))
        assert centre_pixel != (0, 0, 0)

    def test_rgb_image_no_alpha(self):
        svg_img = Image.new("RGB", (50, 30), (0, 255, 0))
        result = compose_card_image(svg_img)
        assert result.size == (PANEL_WIDTH, PANEL_HEIGHT)


# -- compose_touchstrip ------------------------------------------------------


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
        # Should be mostly black (JPEG compression may introduce slight noise)
        px = decoded.getpixel((0, 0))
        assert all(c < 10 for c in px)

    def test_single_card_placed_correctly(self):
        red_card = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), (255, 0, 0))
        cards: list[Image.Image | None] = [red_card, None, None, None]
        result = compose_touchstrip(cards)
        decoded = Image.open(io.BytesIO(result)).convert("RGB")
        # Card 0 should be at x=MARGIN_LEFT
        px = decoded.getpixel((MARGIN_LEFT + 5, MARGIN_TOP + 5))
        assert px[0] > 200  # red channel high

    def test_excess_cards_ignored(self):
        """More than PANEL_COUNT cards should be silently truncated."""
        cards: list[Image.Image | None] = [
            Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), (255, 0, 0)) for _ in range(6)
        ]
        result = compose_touchstrip(cards)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.size == (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)


# -- build_parser / parse_args -----------------------------------------------


class TestParser:
    def test_no_args(self):
        args = parse_args([])
        for i in range(_KEY_COUNT):
            assert getattr(args, f"key{i}") is None
        for i in range(PANEL_COUNT):
            assert getattr(args, f"card{i}") is None

    def test_key_arg(self, tmp_path: Path):
        args = parse_args([f"--key0", str(tmp_path / "k.svg")])
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


# -- render_preview ----------------------------------------------------------


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


# -- main / push_to_device ---------------------------------------------------


class TestMain:
    @patch("deckboard.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_calls_push(self, mock_push: AsyncMock, square_svg: Path):
        main(["--key0", str(square_svg)])
        mock_push.assert_awaited_once()
        key_images, touchstrip, brightness = mock_push.call_args[0]
        assert 0 in key_images
        assert isinstance(touchstrip, bytes)
        assert brightness == 80

    @patch("deckboard.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_default_brightness(self, mock_push: AsyncMock):
        main([])
        _, _, brightness = mock_push.call_args[0]
        assert brightness == 80

    @patch("deckboard.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_custom_brightness(self, mock_push: AsyncMock):
        main(["--brightness", "40"])
        _, _, brightness = mock_push.call_args[0]
        assert brightness == 40

    @patch("deckboard.tools.preview.push_to_device", new_callable=AsyncMock)
    def test_main_verbose(self, mock_push: AsyncMock):
        main(["-v"])
        mock_push.assert_awaited_once()


class TestPushToDevice:
    async def test_push_opens_and_pushes(self, mock_streamdeck_device: MagicMock):
        from deckboard.tools.preview import _wait_forever, push_to_device

        # Create minimal key image and touchstrip
        blank_key = Image.new("RGB", KEY_SIZE, "black")
        buf = io.BytesIO()
        blank_key.save(buf, format="JPEG")
        key_jpeg = buf.getvalue()

        blank_ts = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        buf2 = io.BytesIO()
        blank_ts.save(buf2, format="JPEG")
        ts_jpeg = buf2.getvalue()

        with patch(
            "deckboard.tools.preview._find_and_open_device",
            return_value=mock_streamdeck_device,
        ):

            async def mock_executor(executor, fn, *args):
                # Let device calls through, interrupt on _wait_forever
                if fn is _wait_forever:
                    raise KeyboardInterrupt
                return fn(*args)

            with patch("asyncio.get_running_loop") as mock_loop:
                loop_instance = MagicMock()
                loop_instance.run_in_executor = AsyncMock(
                    side_effect=mock_executor,
                )
                mock_loop.return_value = loop_instance

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
        from deckboard.tools.preview import _wait_forever, push_to_device

        blank_ts = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
        buf = io.BytesIO()
        blank_ts.save(buf, format="JPEG")
        ts_jpeg = buf.getvalue()

        with patch(
            "deckboard.tools.preview._find_and_open_device",
            return_value=mock_streamdeck_device,
        ):

            async def mock_executor(executor, fn, *args):
                if fn is _wait_forever:
                    raise KeyboardInterrupt
                return fn(*args)

            with patch("asyncio.get_running_loop") as mock_loop:
                loop_instance = MagicMock()
                loop_instance.run_in_executor = AsyncMock(
                    side_effect=mock_executor,
                )
                mock_loop.return_value = loop_instance

                await push_to_device({}, ts_jpeg, brightness=150)

        mock_streamdeck_device.set_brightness.assert_called_once_with(100)


# -- _svg_to_png_fit ---------------------------------------------------------


class TestSvgToPngFit:
    def test_tall_svg_constrained_by_height(self, tmp_path: Path):
        """An SVG taller than max_height triggers the height-constrained path."""
        # 20x200 SVG → when constrained to width=80, result is 80x800 → too tall
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

        with patch.dict("sys.modules", {"cairosvg": None}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=fake_png_bytes)
                result = _svg_to_png_fit(svg, 80, 80)
                assert result == fake_png_bytes
                mock_run.assert_called_once()

    def test_no_renderer_raises(self):
        """When both cairosvg and rsvg-convert fail, raise IconError."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'

        with patch.dict("sys.modules", {"cairosvg": None}):
            with patch(
                "subprocess.run",
                side_effect=FileNotFoundError("no rsvg"),
            ):
                with pytest.raises(IconError, match="No SVG renderer"):
                    _svg_to_png_fit(svg, 80, 80)


# -- _find_and_open_device ---------------------------------------------------


class TestFindAndOpenDevice:
    def test_no_devices_exits(self, capsys: pytest.CaptureFixture[str]):
        from deckboard.tools.preview import _find_and_open_device

        mock_dm = MagicMock()
        mock_dm.return_value.enumerate.return_value = []
        with patch(
            "StreamDeck.DeviceManager.DeviceManager",
            mock_dm,
        ):
            with pytest.raises(SystemExit):
                _find_and_open_device()
        assert "No Stream Deck devices found" in capsys.readouterr().err

    def test_opens_first_device(self):
        from deckboard.tools.preview import _find_and_open_device

        device = MagicMock()
        mock_dm = MagicMock()
        mock_dm.return_value.enumerate.return_value = [device]
        with patch(
            "StreamDeck.DeviceManager.DeviceManager",
            mock_dm,
        ):
            result = _find_and_open_device()
        device.open.assert_called_once()
        assert result is device


# -- __main__ ----------------------------------------------------------------


class TestMainModule:
    @patch("deckboard.tools.preview.main")
    def test_main_module(self, mock_main: MagicMock):
        """Importing __main__ should call main()."""
        import importlib

        import deckboard.tools.__main__  # noqa: F811

        importlib.reload(deckboard.tools.__main__)
        mock_main.assert_called()
