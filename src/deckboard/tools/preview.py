"""Preview SVG designs on a physical Stream Deck+ device.

Run with::

    python -m deckboard.tools.preview \\
        --card0 my_card.svg --key0 my_key.svg

Only the specified slots are updated; unspecified keys and cards are
left blank (black).  SVGs are scaled to fit the target area while
preserving aspect ratio and centred on a black background.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import logging
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path

from PIL import Image

from deckboard.render.icons import IconError
from deckboard.render.key_renderer import _encode_jpeg
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

logger = logging.getLogger(__name__)

_KEY_COUNT = 8


# -- SVG loading -------------------------------------------------------------


def _svg_to_png_fit(svg_data: bytes, max_width: int, max_height: int) -> bytes:
    """Rasterise SVG bytes to PNG, fitting within a bounding box.

    Unlike ``icons._svg_to_png`` (which forces exact dimensions), this
    function preserves the SVG's intrinsic aspect ratio by only
    constraining the output width, then scaling down if the height
    exceeds *max_height*.
    """
    try:
        if platform.system() == "Darwin":
            brew_lib = Path("/opt/homebrew/lib")
            if brew_lib.exists():
                os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", str(brew_lib))

        import cairosvg  # noqa: delayed import

        # First pass: constrain by width to get natural aspect ratio.
        png_bytes = cairosvg.svg2png(
            bytestring=svg_data,
            output_width=max_width,
        )
        img = Image.open(io.BytesIO(png_bytes))
        if img.height > max_height:
            # Width-constrained result is too tall; constrain by height.
            png_bytes = cairosvg.svg2png(
                bytestring=svg_data,
                output_height=max_height,
            )
        return png_bytes
    except (OSError, ImportError) as exc:
        logger.debug("cairosvg unavailable (%s), trying rsvg-convert", exc)

    try:
        result = subprocess.run(
            [
                "rsvg-convert",
                "--keep-aspect-ratio",
                "--width",
                str(max_width),
                "--height",
                str(max_height),
                "--format",
                "png",
            ],
            input=svg_data,
            capture_output=True,
            check=True,
            timeout=10,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        logger.debug("rsvg-convert unavailable (%s)", exc)

    raise IconError(
        "No SVG renderer available. Install one of:\n"
        "  - System library: brew install cairo  (macOS) or apt install libcairo2 (Linux)\n"
        "  - CLI tool: apt install librsvg2-bin\n"
        "  - Python package: pip install cairosvg"
    )


def load_svg(path: Path, max_width: int, max_height: int) -> Image.Image:
    """Load an SVG file and return a PIL Image fitted to *max_width* x *max_height*.

    The SVG is rasterised at a size that preserves its intrinsic aspect
    ratio.  The result is guaranteed to be at most *max_width* wide and
    *max_height* tall.
    """
    svg_data = path.read_bytes()
    png_bytes = _svg_to_png_fit(svg_data, max_width, max_height)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    # Final safety net — thumbnail never upscales, only shrinks.
    img.thumbnail((max_width, max_height), Image.LANCZOS)
    return img


# -- Image composition -------------------------------------------------------


def compose_key_image(svg_img: Image.Image) -> bytes:
    """Place *svg_img* centred on a 120x120 black key canvas.

    The image is fitted inside the icon area (80x80 by default) using
    ``ICON_PADDING`` as the margin on each side.
    """
    canvas = Image.new("RGB", KEY_SIZE, "black")
    x = ICON_PADDING + (ICON_SIZE - svg_img.width) // 2
    y = ICON_PADDING + (ICON_SIZE - svg_img.height) // 2
    if svg_img.mode == "RGBA":
        canvas.paste(svg_img, (x, y), svg_img)
    else:
        canvas.paste(svg_img, (x, y))
    return _encode_jpeg(canvas)


def compose_card_image(svg_img: Image.Image) -> Image.Image:
    """Place *svg_img* centred on a panel-sized black card canvas."""
    canvas = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
    x = (PANEL_WIDTH - svg_img.width) // 2
    y = (PANEL_HEIGHT - svg_img.height) // 2
    if svg_img.mode == "RGBA":
        canvas.paste(svg_img, (x, y), svg_img)
    else:
        canvas.paste(svg_img, (x, y))
    return canvas


def compose_touchstrip(card_images: list[Image.Image | None]) -> bytes:
    """Compose up to 4 card images into a single 800x100 touchscreen JPEG."""
    img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")
    for index, card_image in enumerate(card_images):
        if index >= PANEL_COUNT:
            break
        if card_image is not None:
            x = MARGIN_LEFT + index * (PANEL_WIDTH + PANEL_GAP)
            img.paste(card_image, (x, MARGIN_TOP))
    return _encode_jpeg(img)


# -- CLI argument parsing -----------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the ``argparse`` parser for the preview tool."""
    parser = argparse.ArgumentParser(
        prog="python -m deckboard.tools.preview",
        description="Preview SVG designs on a Stream Deck+ device.",
    )
    for i in range(_KEY_COUNT):
        parser.add_argument(
            f"--key{i}",
            type=Path,
            default=None,
            metavar="SVG",
            help=f"SVG file for key slot {i}",
        )
    for i in range(PANEL_COUNT):
        parser.add_argument(
            f"--card{i}",
            type=Path,
            default=None,
            metavar="SVG",
            help=f"SVG file for card slot {i}",
        )
    parser.add_argument(
        "-b",
        "--brightness",
        type=int,
        default=80,
        metavar="PCT",
        help="Screen brightness 0-100 (default: 80)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    return build_parser().parse_args(argv)


# -- Device interaction -------------------------------------------------------


def _find_and_open_device() -> object:
    """Discover, open, and return the first Stream Deck+ device.

    Prints an error and exits if no device is found.
    """
    from StreamDeck.DeviceManager import DeviceManager  # type: ignore[import-untyped]

    devices = DeviceManager().enumerate()
    if not devices:
        print("ERROR: No Stream Deck devices found", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    deck = devices[0]
    deck.open()
    logger.debug("Opened device: %s", deck.deck_type())
    return deck


async def push_to_device(
    key_images: dict[int, bytes],
    touchstrip_bytes: bytes,
    brightness: int = 80,
) -> None:
    """Push rendered images to the physical Stream Deck+.

    *key_images* maps key indices to JPEG bytes.  *touchstrip_bytes* is
    the full 800x100 touchscreen JPEG.  *brightness* sets the screen
    brightness (0-100).
    """
    loop = asyncio.get_running_loop()
    deck = await loop.run_in_executor(None, _find_and_open_device)

    try:
        brightness = max(0, min(100, brightness))
        await loop.run_in_executor(
            None,
            deck.set_brightness,
            brightness,  # type: ignore[union-attr]
        )

        for key_index in range(_KEY_COUNT):
            jpeg = key_images.get(key_index)
            if jpeg is not None:
                await loop.run_in_executor(
                    None,
                    deck.set_key_image,
                    key_index,
                    jpeg,  # type: ignore[union-attr]
                )

        await loop.run_in_executor(
            None,
            deck.set_touchscreen_image,  # type: ignore[union-attr]
            touchstrip_bytes,
            0,
            0,
            TOUCHSCREEN_WIDTH,
            TOUCHSCREEN_HEIGHT,
        )

        print("Preview pushed — press Ctrl+C to exit", file=sys.stderr)  # noqa: T201
        await _wait_for_interrupt()
    finally:
        await loop.run_in_executor(None, deck.reset)  # type: ignore[union-attr]
        await loop.run_in_executor(None, deck.close)  # type: ignore[union-attr]


async def _wait_for_interrupt() -> None:
    """Wait until the process receives SIGINT (Ctrl+C).

    Uses an :class:`asyncio.Event` set by a signal handler so the event
    loop stays responsive and shuts down cleanly on the first Ctrl+C.
    """
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    loop.add_signal_handler(signal.SIGINT, stop.set)
    try:
        await stop.wait()
    finally:
        loop.remove_signal_handler(signal.SIGINT)


# -- Orchestration ------------------------------------------------------------


def render_preview(
    args: argparse.Namespace,
) -> tuple[dict[int, bytes], bytes]:
    """Render all specified SVGs and return key images + touchstrip JPEG.

    Returns a ``(key_images, touchstrip_bytes)`` tuple.
    """
    key_images: dict[int, bytes] = {}
    card_images: list[Image.Image | None] = [None] * PANEL_COUNT

    for i in range(_KEY_COUNT):
        svg_path: Path | None = getattr(args, f"key{i}", None)
        if svg_path is not None:
            if not svg_path.exists():
                print(f"ERROR: Key SVG not found: {svg_path}", file=sys.stderr)  # noqa: T201
                sys.exit(1)
            img = load_svg(svg_path, ICON_SIZE, ICON_SIZE)
            key_images[i] = compose_key_image(img)
            logger.info(
                "Rendered key %d from %s (%dx%d)", i, svg_path, img.width, img.height
            )

    for i in range(PANEL_COUNT):
        svg_path = getattr(args, f"card{i}", None)
        if svg_path is not None:
            if not svg_path.exists():
                print(f"ERROR: Card SVG not found: {svg_path}", file=sys.stderr)  # noqa: T201
                sys.exit(1)
            img = load_svg(svg_path, PANEL_WIDTH, PANEL_HEIGHT)
            card_images[i] = compose_card_image(img)
            logger.info(
                "Rendered card %d from %s (%dx%d)", i, svg_path, img.width, img.height
            )

    touchstrip_bytes = compose_touchstrip(card_images)
    return key_images, touchstrip_bytes


def main(argv: list[str] | None = None) -> None:
    """Entry point for the preview tool."""
    args = parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    key_images, touchstrip_bytes = render_preview(args)
    asyncio.run(push_to_device(key_images, touchstrip_bytes, args.brightness))


if __name__ == "__main__":  # pragma: no cover
    main()
