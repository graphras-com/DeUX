"""SVG-to-PNG rasterisation via CairoSVG or rsvg-convert fallback."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import cast

logger = logging.getLogger(__name__)


class RasterizeError(Exception):
    """Raised when SVG rasterisation fails."""


def _svg_to_png(svg_data: bytes, width: int, height: int) -> bytes:
    """Convert SVG bytes to PNG bytes.

    Attempts CairoSVG first, then falls back to ``rsvg-convert``.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content.
    width : int
        Desired output width in pixels.
    height : int
        Desired output height in pixels.

    Returns
    -------
    bytes
        Rasterised PNG image bytes.

    Raises
    ------
    RasterizeError
        If no SVG renderer backend is available.
    """
    try:
        if platform.system() == "Darwin":
            brew_lib = Path("/opt/homebrew/lib")
            if brew_lib.exists():
                os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", str(brew_lib))

        import cairosvg

        return cast(
            "bytes",
            cairosvg.svg2png(
            bytestring=svg_data,
            output_width=width,
            output_height=height,
        )
        )
    except (OSError, ImportError) as exc:
        logger.debug("cairosvg unavailable (%s), trying fallback", exc)

    try:
        result = subprocess.run(
            [
                "rsvg-convert",
                "--width",
                str(width),
                "--height",
                str(height),
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
        logger.debug("rsvg-convert unavailable (%s), trying Pillow", exc)

    raise RasterizeError(
        "No SVG renderer available. Install one of:\n"
        "  - System library: brew install cairo  (macOS) or apt install libcairo2 "
        "(Linux)\n"
        "  - CLI tool: apt install librsvg2-bin\n"
        "  - Python package: pip install cairosvg"
    )
