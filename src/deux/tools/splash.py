"""Push a full-screen splash image to a connected Stream Deck.

Uploads a single image covering the entire back-panel LCD via HID
command ``0x08`` (Update Full Screen Image).  Intended as a quick
way to test the splash pipeline against real hardware without writing
any Python.

Examples
--------
::

    # Push an image, fitting with cover (default), to the first deck:
    python -m deux.tools.splash --image boot.png

    # Letterbox with a coloured background:
    python -m deux.tools.splash --image logo.svg --fit contain --background "#1a1a2e"

    # Clear the screen to solid black:
    python -m deux.tools.splash --clear

Notes
-----
The full-screen image is a *one-shot* whole-LCD blit.  Any subsequent
key or window update (including by another running deux process) will
paint over it.  See :class:`deux.runtime.deck.Deck.show_full_screen_image`
for details.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deux.runtime.hid.device import HidDevice

logger = logging.getLogger(__name__)


def _parse_color(value: str) -> tuple[int, int, int]:
    """Parse ``#rrggbb`` or ``r,g,b`` into an RGB tuple.

    Parameters
    ----------
    value : str
        Either a hex CSS-style colour (``"#1a2b3c"``) or three
        comma-separated 0-255 integers (``"26,43,60"``).

    Returns
    -------
    tuple[int, int, int]
        ``(r, g, b)`` clamped to ``[0, 255]``.

    Raises
    ------
    argparse.ArgumentTypeError
        If *value* cannot be parsed.
    """
    text = value.strip()
    if text.startswith("#"):
        hex_part = text[1:]
        if len(hex_part) != 6:
            raise argparse.ArgumentTypeError(
                f"Hex colour must be 6 hex digits, got {value!r}"
            )
        try:
            r = int(hex_part[0:2], 16)
            g = int(hex_part[2:4], 16)
            b = int(hex_part[4:6], 16)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid hex colour: {value!r}"
            ) from exc
        return (r, g, b)

    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"Expected '#rrggbb' or 'r,g,b', got {value!r}"
        )
    try:
        r, g, b = (max(0, min(255, int(p))) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"RGB components must be integers, got {value!r}"
        ) from exc
    return (r, g, b)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the ``argparse`` parser for the splash CLI."""
    parser = argparse.ArgumentParser(
        prog="deux.tools.splash",
        description="Push a full-screen splash image to a connected Stream Deck.",
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Path to image (PNG, JPEG, SVG, ...).  Mutually exclusive with --clear.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the LCD to a solid colour (defaults to black).",
    )
    parser.add_argument(
        "--fit",
        choices=("cover", "contain", "stretch"),
        default="cover",
        help="Resize strategy (default: cover).",
    )
    parser.add_argument(
        "--background",
        type=_parse_color,
        default=(0, 0, 0),
        help="Letterbox/clear colour as '#rrggbb' or 'r,g,b' (default: black).",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=90,
        help="JPEG quality 1-95 (default: 90).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def _find_first_device() -> HidDevice:
    """Enumerate and open the first connected Stream Deck.

    Returns
    -------
    HidDevice
        An opened :class:`~deux.runtime.hid.device.HidDevice`.

    Raises
    ------
    SystemExit
        If no device is found (exit code 1).
    """
    # Inline import: keep the heavy HID stack out of import path until
    # the user actually runs the tool.
    from deux.runtime.hid.discovery import enumerate_devices  # noqa: PLC0415

    devices = enumerate_devices()
    if not devices:
        print("ERROR: No Stream Deck devices found", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    device = devices[0]
    device.open()
    return device


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m deux.tools.splash``.

    Parameters
    ----------
    argv : list[str] or None, optional
        Argument vector (excluding the program name).  Defaults to
        :data:`sys.argv` when ``None``.

    Returns
    -------
    int
        Process exit code.  ``0`` on success, ``1`` on bad arguments
        or no device, ``2`` on image preparation / HID error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.image is None and not args.clear:
        parser.error("Either --image or --clear is required")
    if args.image is not None and args.clear:
        parser.error("--image and --clear are mutually exclusive")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # Lazy imports: avoid pulling resvg / Pillow / HID into module load.
    from deux.runtime.splash import (  # noqa: PLC0415
        SplashError,
        prepare_full_screen_jpeg,
        prepare_solid_color_jpeg,
    )

    device = _find_first_device()
    logical_size = device.logical_lcd_size
    if logical_size == (0, 0):
        print(  # noqa: T201
            f"ERROR: Device PID 0x{device.product_id:04X} ({device.family}) "
            "has no known LCD size for the full-screen image path.",
            file=sys.stderr,
        )
        device.close()
        return 2

    try:
        if args.clear:
            print(  # noqa: T201
                f"Clearing {device.family} ({logical_size[0]}x{logical_size[1]}) "
                f"to RGB{args.background}",
                file=sys.stderr,
            )
            jpeg = prepare_solid_color_jpeg(
                args.background,
                logical_size=logical_size,
                rotation=device.rotation,
                jpeg_quality=args.quality,
            )
        else:
            print(  # noqa: T201
                f"Pushing {args.image} to {device.family} "
                f"({logical_size[0]}x{logical_size[1]}, fit={args.fit})",
                file=sys.stderr,
            )
            jpeg = prepare_full_screen_jpeg(
                args.image,
                logical_size=logical_size,
                rotation=device.rotation,
                fit=args.fit,
                background=args.background,
                jpeg_quality=args.quality,
            )

        device.set_full_screen_image(jpeg)
    except SplashError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)  # noqa: T201
        device.close()
        return 2
    except Exception as exc:  # noqa: BLE001 — final user-facing barrier
        print(f"ERROR: {exc}", file=sys.stderr)  # noqa: T201
        device.close()
        return 2

    device.close()
    print("Done.", file=sys.stderr)  # noqa: T201
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised by `python -m`
    raise SystemExit(main())
