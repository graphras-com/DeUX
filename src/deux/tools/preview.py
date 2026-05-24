"""Preview SVG designs on a physical Stream Deck device.

Examples
--------
::

    python -m deux.tools.preview \\
        --card0 my_card.svg --key0 my_key.svg \\
        --background "#1a2b3c"

    # Auto-reload when SVG files change:
    python -m deux.tools.preview \\
        --card0 my_card.svg --key0 my_key.svg --watch

Only the specified slots are updated; unspecified keys and cards are
left blank (black unless ``--background`` is given).  SVGs are scaled
edge-to-edge to the connected device's native key/panel size — the tool
does not impose any margins, padding, or gaps.

Use ``--touchstrip`` to push a single full-width SVG across the entire
touchstrip instead of specifying individual ``--cardN`` panels.  The
``--touchstrip`` flag is mutually exclusive with ``--cardN`` flags.

The tool auto-detects the first connected visual Stream Deck device and
adapts key/card counts and dimensions to the hardware.

With ``--watch``, the tool monitors all specified SVG files and
automatically re-renders and re-pushes images when any file changes.
The poll interval can be tuned with ``--poll-interval`` (default 0.5s).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from deux.runtime.hid.device import HidDevice

from PIL import Image

from deux.render.key_renderer import _encode_image_bytes
from deux.render.svg_rasterize import _svg_to_image, _svg_to_png
from deux.runtime.capabilities import DeviceCapabilities
from deux.runtime.deck import _HID_WRITE_TIMEOUT

from .._xml import safe_fromstring

logger = logging.getLogger(__name__)

# CLI output convention
# ---------------------
# User-facing messages and errors are written to stderr via
# ``print(..., file=sys.stderr)`` (annotated with a ruff T201 ignore
# directive at each call site). This is the deliberate CLI convention:
# such output should always reach the user regardless of the configured
# logging level. The ``logger`` is reserved for diagnostic / status
# output (``debug`` and ``info``) that respects the ``--verbose`` flag.

# Regex used to strip unit suffixes (``"px"``, ``"pt"``, ...) from SVG
# width / height attributes.
_DIM_RE = re.compile(r"([\d.]+)")

# Upper-bound slot counts used only to generate ``--keyN`` / ``--cardN``
# CLI flags. The tool ignores flags that don't correspond to an actual
# slot on the connected device, so generous bounds are harmless.
_MAX_KEY_SLOTS = 32
_MAX_CARD_SLOTS = 8

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


class PreviewDeckDevice(Protocol):
    """Protocol for the low-level Stream Deck device used by the preview tool."""

    def open(self) -> None: ...
    def close(self) -> None: ...
    def show_logo(self) -> None: ...
    @property
    def family(self) -> str: ...
    def set_brightness(self, value: int) -> None: ...
    def set_key_image(self, key: int, image: bytes) -> None: ...
    def set_partial_window_image(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        image: bytes,
    ) -> None: ...


def parse_hex_color(value: str) -> str:
    """Validate and normalise a hex colour string to ``#RRGGBB``.

    Accepts ``RRGGBB`` or ``#RRGGBB`` (case-insensitive).  Raises
    :class:`argparse.ArgumentTypeError` for invalid values so that
    ``argparse`` can produce a user-friendly error message.
    """
    m = _HEX_RE.match(value)
    if m is None:
        raise argparse.ArgumentTypeError(
            f"invalid hex colour: {value!r} (expected '#RRGGBB' or 'RRGGBB')"
        )
    return f"#{m.group(1).lower()}"



def _compute_fit_dims(
    svg_data: bytes, max_width: int, max_height: int
) -> tuple[int, int]:
    """Compute output dimensions that fit *svg_data* into a bounding box.

    Parses the SVG's intrinsic ``width`` / ``height`` attributes and
    returns ``(out_w, out_h)`` preserving aspect ratio within
    *max_width* x *max_height*. Falls back to ``(max_width, max_height)``
    if the SVG omits or has unparseable dimensions.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content (UTF-8).
    max_width : int
        Maximum output width in pixels.
    max_height : int
        Maximum output height in pixels.

    Returns
    -------
    tuple[int, int]
        ``(out_w, out_h)`` — both ``>= 1``.
    """
    try:
        root = safe_fromstring(svg_data)  # untrusted: user-supplied SVG
        w_match = _DIM_RE.match(root.get("width", ""))
        h_match = _DIM_RE.match(root.get("height", ""))
        if w_match and h_match:
            svg_w = float(w_match.group(1))
            svg_h = float(h_match.group(1))
            if svg_w > 0 and svg_h > 0:
                scale = min(max_width / svg_w, max_height / svg_h)
                return max(1, int(svg_w * scale)), max(1, int(svg_h * scale))
    except Exception:
        logger.debug(
            "Failed to parse SVG intrinsic dimensions; using fallback raster size %dx%d.",
            max_width,
            max_height,
        )
    return max_width, max_height


def _svg_to_png_fit(svg_data: bytes, max_width: int, max_height: int) -> bytes:
    """Rasterise SVG bytes to PNG, fitting within a bounding box.

    Parses the SVG's intrinsic dimensions to compute the correct output
    size that preserves aspect ratio within *max_width* x *max_height*,
    then delegates to the active SVG backend.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content.
    max_width : int
        Maximum output width in pixels.
    max_height : int
        Maximum output height in pixels.

    Returns
    -------
    bytes
        PNG image bytes fitting within the bounding box.

    Raises
    ------
    RasterizeError
        If no SVG renderer backend is available.
    """
    out_w, out_h = _compute_fit_dims(svg_data, max_width, max_height)
    return _svg_to_png(svg_data, out_w, out_h)


def _svg_to_image_fit(
    svg_data: bytes, max_width: int, max_height: int
) -> Image.Image:
    """Rasterise SVG bytes to a PIL RGBA Image fitted within a bounding box.

    Preserves the SVG's intrinsic aspect ratio. Uses the raw-RGBA path
    to avoid a PNG encode/decode round-trip.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content (UTF-8).
    max_width : int
        Maximum width of the output image.
    max_height : int
        Maximum height of the output image.

    Returns
    -------
    Image.Image
        An RGBA PIL Image fitted within the bounding box.

    Raises
    ------
    RasterizeError
        If no SVG renderer backend is available.
    """
    out_w, out_h = _compute_fit_dims(svg_data, max_width, max_height)
    return _svg_to_image(svg_data, out_w, out_h, mode="RGBA")


def load_svg(path: Path, max_width: int, max_height: int) -> Image.Image:
    """Load an SVG file and return a PIL Image fitted to *max_width* x *max_height*.

    The SVG is rasterised at a size that preserves its intrinsic aspect
    ratio.  The result is guaranteed to be at most *max_width* wide and
    *max_height* tall.
    """
    svg_data = path.read_bytes()
    img = _svg_to_image_fit(svg_data, max_width, max_height)
    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return img


def _center_on_canvas(
    svg_img: Image.Image,
    size: tuple[int, int],
    background: str,
) -> Image.Image:
    """Centre *svg_img* on an RGB canvas of *size* filled with *background*.

    Pastes using *svg_img*'s alpha channel as the mask when present.

    Parameters
    ----------
    svg_img : Image.Image
        Image to composite onto the canvas.
    size : tuple[int, int]
        ``(width, height)`` of the target canvas.
    background : str
        Canvas fill colour (any PIL-compatible colour string).

    Returns
    -------
    Image.Image
        New RGB canvas with *svg_img* centred.
    """
    canvas = Image.new("RGB", size, background)
    x = (size[0] - svg_img.width) // 2
    y = (size[1] - svg_img.height) // 2
    if svg_img.mode == "RGBA":
        canvas.paste(svg_img, (x, y), svg_img)
    else:
        canvas.paste(svg_img, (x, y))
    return canvas


def compose_key_image(
    svg_img: Image.Image,
    key_size: tuple[int, int],
    background: str = "black",
) -> bytes:
    """Place *svg_img* edge-to-edge on a key-sized canvas.

    The image is centred only when its intrinsic aspect ratio differs
    from the key — there are no margins or padding around it.

    Parameters
    ----------
    svg_img
        Pre-rasterised SVG image to composite onto the key canvas.
    key_size
        ``(width, height)`` of the target key canvas.
    background
        Canvas fill colour (any PIL-compatible colour string).

    Returns
    -------
    bytes
        JPEG-encoded image bytes ready for ``set_key_image``.
    """
    return _encode_image_bytes(_center_on_canvas(svg_img, key_size, background))


def compose_card_image(
    svg_img: Image.Image,
    panel_size: tuple[int, int],
    background: str = "black",
) -> Image.Image:
    """Place *svg_img* edge-to-edge on a panel-sized card canvas.

    Parameters
    ----------
    svg_img
        Pre-rasterised SVG image to composite onto the card canvas.
    panel_size
        ``(width, height)`` of the target panel.
    background
        Canvas fill colour (any PIL-compatible colour string).

    Returns
    -------
    Image.Image
        Composited card image at *panel_size*.
    """
    return _center_on_canvas(svg_img, panel_size, background)


def compose_touchstrip(
    card_images: list[Image.Image | None],
    *,
    touchscreen_width: int,
    touchscreen_height: int,
    panel_count: int,
    panel_width: int,
    background: str = "black",
) -> bytes:
    """Compose card images into a single touchscreen JPEG.

    Cards are tiled edge-to-edge starting at ``(i * panel_width, 0)``.
    The *background* colour shows wherever a slot is ``None`` or a
    card image leaves pixels uncovered.
    """
    img = Image.new("RGB", (touchscreen_width, touchscreen_height), background)
    for index, card_image in enumerate(card_images):
        if index >= panel_count:
            break
        if card_image is not None:
            img.paste(card_image, (index * panel_width, 0))
    return _encode_image_bytes(img)


def compose_full_touchstrip(
    svg_img: Image.Image,
    touchscreen_size: tuple[int, int],
    background: str = "black",
) -> bytes:
    """Place *svg_img* edge-to-edge on a full touchstrip canvas.

    Unlike :func:`compose_touchstrip`, which tiles individual card
    images, this function composites a single SVG image covering the
    entire touchstrip area.

    Parameters
    ----------
    svg_img : Image.Image
        Pre-rasterised SVG image to composite onto the touchstrip canvas.
    touchscreen_size : tuple[int, int]
        ``(width, height)`` of the target touchstrip canvas.
    background : str, default="black"
        Canvas fill colour (any PIL-compatible colour string).

    Returns
    -------
    bytes
        JPEG-encoded image bytes ready for ``set_touchscreen_image``.
    """
    return _encode_image_bytes(
        _center_on_canvas(svg_img, touchscreen_size, background)
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the ``argparse`` parser for the preview tool.

    The parser declares ``--keyN`` / ``--cardN`` flags up to a generous
    upper bound; flags that don't correspond to an actual slot on the
    connected device are ignored at render time.
    """
    parser = argparse.ArgumentParser(
        prog="python -m deux.tools.preview",
        description="Preview SVG designs on a Stream Deck device.",
    )
    for i in range(_MAX_KEY_SLOTS):
        parser.add_argument(
            f"--key{i}",
            type=Path,
            default=None,
            metavar="SVG",
            help=argparse.SUPPRESS if i >= 8 else f"SVG file for key slot {i}",
        )
    for i in range(_MAX_CARD_SLOTS):
        parser.add_argument(
            f"--card{i}",
            type=Path,
            default=None,
            metavar="SVG",
            help=argparse.SUPPRESS if i >= 4 else f"SVG file for card slot {i}",
        )
    parser.add_argument(
        "--touchstrip",
        type=Path,
        default=None,
        metavar="SVG",
        help="SVG file for the full touchstrip (mutually exclusive with --cardN)",
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
        "--background",
        type=parse_hex_color,
        default=None,
        metavar="HEX",
        help="Background colour for the touchstrip in hex (e.g. '#1a2b3c' or '1a2b3c')",
    )
    parser.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="Watch SVG files for changes and auto-reload",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        metavar="SECS",
        help="File poll interval in seconds when --watch is active (default: 0.5)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Parameters
    ----------
    argv : list[str] | None, optional
        Argument list to parse.  Defaults to ``sys.argv[1:]``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with key/card paths, brightness, background, etc.
    """
    args = build_parser().parse_args(argv)

    # --touchstrip is mutually exclusive with --cardN flags.
    if args.touchstrip is not None:
        card_flags = [
            f"card{i}"
            for i in range(_MAX_CARD_SLOTS)
            if getattr(args, f"card{i}") is not None
        ]
        if card_flags:
            build_parser().error(
                f"--touchstrip cannot be used together with --{card_flags[0]}"
            )

    return args




def _find_and_open_device() -> PreviewDeckDevice:
    """Discover, open, and return the first visual Stream Deck device.

    Prints an error and exits if no device is found.
    """
    # Inline import: tests patch ``deux.runtime.hid.discovery.enumerate_devices``;
    # importing it lazily keeps that patching point effective.
    from deux.runtime.hid.discovery import enumerate_devices  # noqa: PLC0415

    devices = enumerate_devices()
    if not devices:
        print("ERROR: No Stream Deck devices found", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    deck = cast("PreviewDeckDevice", devices[0])
    deck.open()
    logger.debug("Opened device: %s", deck.family)
    return deck


async def push_to_device(
    args: argparse.Namespace,
    *,
    poll_interval: float = 0.5,
) -> None:
    """Open the deck, render images for *args*, and push them.

    Sized to the connected device's capabilities — key images are
    rendered at ``caps.key_size`` and the touchstrip at
    ``caps.touchscreen_width × caps.touchscreen_height``.

    When ``args.watch`` is true the tool polls the referenced SVG files
    and re-pushes on change.  *poll_interval* controls how often files
    are polled (in seconds).
    """
    loop = asyncio.get_running_loop()
    deck = await loop.run_in_executor(None, _find_and_open_device)

    try:
        caps = DeviceCapabilities.from_device(cast("HidDevice", deck))
        panel_width = (
            caps.touchscreen_width // caps.panel_count if caps.panel_count > 0 else 0
        )

        brightness = max(0, min(100, args.brightness))
        await asyncio.wait_for(
            loop.run_in_executor(
                None,
                deck.set_brightness,
                brightness,
            ),
            timeout=_HID_WRITE_TIMEOUT,
        )

        key_images, touchstrip_bytes = render_preview(args, caps)

        for key_index in range(caps.key_count):
            jpeg = key_images.get(key_index)
            if jpeg is not None:
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        deck.set_key_image,
                        key_index,
                        jpeg,
                    ),
                    timeout=_HID_WRITE_TIMEOUT,
                )

        if caps.has_touchscreen:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    deck.set_partial_window_image,
                    0,
                    0,
                    caps.touchscreen_width,
                    caps.touchscreen_height,
                    touchstrip_bytes,
                ),
                timeout=_HID_WRITE_TIMEOUT,
            )

        if args.watch:
            print(  # noqa: T201
                "Preview pushed — watching for changes (Ctrl+C to exit)",
                file=sys.stderr,
            )
            await _watch_and_reload(args, deck, caps, panel_width, poll_interval)
        else:
            print("Preview pushed — press Ctrl+C to exit", file=sys.stderr)  # noqa: T201
            await _wait_for_interrupt()
    finally:
        await asyncio.wait_for(
            loop.run_in_executor(None, deck.show_logo), timeout=_HID_WRITE_TIMEOUT
        )
        await asyncio.wait_for(
            loop.run_in_executor(None, deck.close), timeout=_HID_WRITE_TIMEOUT
        )


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


def collect_svg_paths(args: argparse.Namespace) -> list[Path]:
    """Return the list of SVG file paths specified in *args*.

    Returns
    -------
    list[Path]
        Ordered list of SVG paths (keys first, then cards).
    """
    paths: list[Path] = []
    for i in range(_MAX_KEY_SLOTS):
        p: Path | None = getattr(args, f"key{i}", None)
        if p is not None:
            paths.append(p)
    for i in range(_MAX_CARD_SLOTS):
        p = getattr(args, f"card{i}", None)
        if p is not None:
            paths.append(p)
    ts: Path | None = getattr(args, "touchstrip", None)
    if ts is not None:
        paths.append(ts)
    return paths


def get_mtimes(paths: list[Path]) -> dict[Path, float]:
    """Return a mapping of *paths* to their modification times.

    Missing files are silently assigned mtime ``0.0``.
    """
    mtimes: dict[Path, float] = {}
    for p in paths:
        try:
            mtimes[p] = p.stat().st_mtime
        except OSError:
            mtimes[p] = 0.0
    return mtimes


async def _watch_and_reload(
    args: argparse.Namespace,
    deck: PreviewDeckDevice,
    caps: DeviceCapabilities,
    panel_width: int,
    poll_interval: float,
) -> None:
    """Poll SVG files for changes and re-push to *deck* on modification.

    Runs until SIGINT (Ctrl+C) is received.
    """
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    loop.add_signal_handler(signal.SIGINT, stop.set)

    svg_paths = collect_svg_paths(args)
    last_mtimes = get_mtimes(svg_paths)

    try:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
                break  # stop was set
            except TimeoutError:
                pass  # poll interval elapsed, check files

            current_mtimes = get_mtimes(svg_paths)
            if current_mtimes != last_mtimes:
                changed = [
                    p for p in svg_paths if current_mtimes[p] != last_mtimes.get(p, 0.0)
                ]
                logger.info("Detected changes: %s", [str(p) for p in changed])
                print(  # noqa: T201
                    f"Reloading {len(changed)} changed file(s)...",
                    file=sys.stderr,
                )
                last_mtimes = current_mtimes
                try:
                    key_images, touchstrip_bytes = render_preview(args, caps)
                except Exception as exc:
                    print(f"Render error: {exc}", file=sys.stderr)  # noqa: T201
                    continue

                for key_index in range(caps.key_count):
                    jpeg = key_images.get(key_index)
                    if jpeg is not None:
                        await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                deck.set_key_image,
                                key_index,
                                jpeg,
                            ),
                            timeout=_HID_WRITE_TIMEOUT,
                        )

                if caps.has_touchscreen:
                    await asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            deck.set_partial_window_image,
                            0,
                            0,
                            caps.touchscreen_width,
                            caps.touchscreen_height,
                            touchstrip_bytes,
                        ),
                        timeout=_HID_WRITE_TIMEOUT,
                    )
                _ = panel_width  # carried for symmetry; geometry comes from caps
                print("Preview updated", file=sys.stderr)  # noqa: T201
    finally:
        loop.remove_signal_handler(signal.SIGINT)




def render_preview(
    args: argparse.Namespace,
    caps: DeviceCapabilities,
) -> tuple[dict[int, bytes], bytes]:
    """Render all specified SVGs at *caps* sizes.

    Parameters
    ----------
    args
        Parsed CLI arguments.
    caps
        Capabilities of the connected device — drives key and panel sizing.

    Returns
    -------
    tuple[dict[int, bytes], bytes]
        ``(key_images, touchstrip_bytes)`` where *key_images* maps key
        index → JPEG bytes. *touchstrip_bytes* is empty when the device
        has no touchscreen.
    """
    background: str = getattr(args, "background", None) or "black"
    key_images: dict[int, bytes] = {}

    key_size = (caps.key_pixel_width, caps.key_pixel_height)
    for i in range(caps.key_count):
        svg_path: Path | None = getattr(args, f"key{i}", None)
        if svg_path is not None:
            if not svg_path.exists():
                print(f"ERROR: Key SVG not found: {svg_path}", file=sys.stderr)  # noqa: T201
                sys.exit(1)
            img = load_svg(svg_path, *key_size)
            key_images[i] = compose_key_image(img, key_size, background=background)
            logger.info(
                "Rendered key %d from %s (%dx%d)", i, svg_path, img.width, img.height
            )

    if not caps.has_touchscreen or caps.panel_count == 0:
        return key_images, b""

    touchstrip_svg: Path | None = getattr(args, "touchstrip", None)
    if touchstrip_svg is not None:
        if not touchstrip_svg.exists():
            print(f"ERROR: Touchstrip SVG not found: {touchstrip_svg}", file=sys.stderr)  # noqa: T201
            sys.exit(1)
        ts_size = (caps.touchscreen_width, caps.touchscreen_height)
        img = load_svg(touchstrip_svg, *ts_size)
        touchstrip_bytes = compose_full_touchstrip(img, ts_size, background=background)
        logger.info(
            "Rendered full touchstrip from %s (%dx%d)",
            touchstrip_svg,
            img.width,
            img.height,
        )
        return key_images, touchstrip_bytes

    panel_width = caps.touchscreen_width // caps.panel_count
    panel_size = (panel_width, caps.touchscreen_height)
    card_images: list[Image.Image | None] = [None] * caps.panel_count

    for i in range(caps.panel_count):
        svg_path = getattr(args, f"card{i}", None)
        if svg_path is not None:
            if not svg_path.exists():
                print(f"ERROR: Card SVG not found: {svg_path}", file=sys.stderr)  # noqa: T201
                sys.exit(1)
            img = load_svg(svg_path, *panel_size)
            card_images[i] = compose_card_image(img, panel_size, background=background)
            logger.info(
                "Rendered card %d from %s (%dx%d)", i, svg_path, img.width, img.height
            )

    touchstrip_bytes = compose_touchstrip(
        card_images,
        touchscreen_width=caps.touchscreen_width,
        touchscreen_height=caps.touchscreen_height,
        panel_count=caps.panel_count,
        panel_width=panel_width,
        background=background,
    )
    return key_images, touchstrip_bytes


def main(argv: list[str] | None = None) -> None:
    """Entry point for the preview tool.

    Parameters
    ----------
    argv : list[str] | None, optional
        Argument list to parse.  Defaults to ``sys.argv[1:]``.
    """
    args = parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    asyncio.run(push_to_device(args, poll_interval=args.poll_interval))


if __name__ == "__main__":  # pragma: no cover
    main()
