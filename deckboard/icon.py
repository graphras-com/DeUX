"""Icon manager: fetch icons from Iconify API, convert SVG to PNG, cache locally."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

# Default cache directory
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "deckboard" / "icons"

# Iconify API base URL
_ICONIFY_API = "https://api.iconify.design"


class IconError(Exception):
    """Raised when an icon cannot be fetched or converted."""


def _svg_to_png(svg_data: bytes, width: int, height: int) -> bytes:
    """Convert SVG bytes to PNG bytes.

    Tries cairosvg first (fast, high quality). If the cairo system library
    is not found, falls back to Pillow's built-in SVG support or rsvg-convert.
    """
    # Attempt 1: cairosvg (needs libcairo system library)
    try:
        # On macOS with Homebrew, cairocffi may not find the library
        # unless we help it by pre-loading or setting the path.
        if platform.system() == "Darwin":
            brew_lib = Path("/opt/homebrew/lib")
            if brew_lib.exists():
                os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", str(brew_lib))

        import cairosvg  # noqa: delayed import

        return cairosvg.svg2png(
            bytestring=svg_data,
            output_width=width,
            output_height=height,
        )
    except (OSError, ImportError) as e:
        logger.debug("cairosvg unavailable (%s), trying fallback", e)

    # Attempt 2: rsvg-convert CLI (available on many Linux systems)
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
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        logger.debug("rsvg-convert unavailable (%s), trying Pillow", e)

    # Attempt 3: Pillow — render SVG text as an image (limited quality)
    # This won't render SVG paths, but gives a meaningful error.
    raise IconError(
        "No SVG renderer available. Install one of:\n"
        "  - System library: brew install cairo  (macOS) or apt install libcairo2 (Linux)\n"
        "  - CLI tool: apt install librsvg2-bin\n"
        "  - Python package: pip install cairosvg"
    )


class IconManager:
    """Fetches icons from Iconify by name, converts SVG to PNG, and caches locally.

    Icon names use the format ``prefix:name``, e.g. ``mdi:home``,
    ``mdi-light:arrow-up-circle``, ``lucide:settings``.
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, Image.Image] = {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _cache_key(self, name: str, size: int, color: str) -> str:
        """Generate a deterministic cache key for an icon variant."""
        # Normalize color: strip '#' for filename safety
        color_safe = color.lstrip("#")
        # prefix:name -> prefix--name
        name_safe = name.replace(":", "--").replace("/", "--")
        return f"{name_safe}--{size}--{color_safe}"

    def _cache_path(self, cache_key: str) -> Path:
        return self._cache_dir / f"{cache_key}.png"

    def _parse_icon_name(self, name: str) -> tuple[str, str]:
        """Parse 'prefix:name' into (prefix, icon_name).

        Also accepts 'prefix/name' format.
        """
        if ":" in name:
            prefix, icon_name = name.split(":", 1)
        elif "/" in name:
            prefix, icon_name = name.split("/", 1)
        else:
            raise IconError(
                f"Invalid icon name '{name}'. Expected format: 'prefix:name' (e.g. 'mdi:home')"
            )
        return prefix, icon_name

    def _build_url(self, prefix: str, icon_name: str, color: str) -> str:
        """Build Iconify API URL for an SVG icon."""
        # Color needs to be URL-encoded: '#' -> '%23'
        encoded_color = color.replace("#", "%23")
        return f"{_ICONIFY_API}/{prefix}/{icon_name}.svg?color={encoded_color}"

    async def get(
        self,
        name: str,
        size: int = 80,
        color: str = "white",
    ) -> Image.Image:
        """Fetch an icon as a PIL Image (RGBA).

        Args:
            name: Icon name in ``prefix:name`` format (e.g. ``mdi:home``).
            size: Target size in pixels (square). Defaults to 80.
            color: Icon color. Defaults to white.

        Returns:
            PIL Image in RGBA mode, sized to ``size x size``.
        """
        cache_key = self._cache_key(name, size, color)

        # 1. Check memory cache
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        # 2. Check disk cache
        disk_path = self._cache_path(cache_key)
        if disk_path.exists():
            img = Image.open(disk_path).convert("RGBA")
            self._memory_cache[cache_key] = img
            logger.debug("Icon cache hit (disk): %s", name)
            return img

        # 3. Fetch from Iconify API
        logger.info("Fetching icon from Iconify: %s", name)
        prefix, icon_name = self._parse_icon_name(name)
        url = self._build_url(prefix, icon_name, color)

        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise IconError(f"Failed to fetch icon '{name}' from {url}: {e}") from e

        svg_data = resp.content

        if not svg_data or b"<svg" not in svg_data:
            raise IconError(f"Invalid SVG response for icon '{name}'")

        # 4. Convert SVG to PNG
        try:
            png_data = _svg_to_png(svg_data, size, size)
        except Exception as e:
            raise IconError(
                f"Failed to convert SVG to PNG for icon '{name}': {e}"
            ) from e

        # 5. Load as PIL Image
        img = Image.open(BytesIO(png_data)).convert("RGBA")

        # 6. Cache to disk and memory
        img.save(disk_path, "PNG")
        self._memory_cache[cache_key] = img
        logger.debug("Icon cached: %s -> %s", name, disk_path)

        return img

    def get_cached(
        self, name: str, size: int = 80, color: str = "white"
    ) -> Image.Image | None:
        """Synchronously retrieve an icon if it's already cached (memory or disk).

        Returns None if the icon is not cached.
        """
        cache_key = self._cache_key(name, size, color)

        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        disk_path = self._cache_path(cache_key)
        if disk_path.exists():
            img = Image.open(disk_path).convert("RGBA")
            self._memory_cache[cache_key] = img
            return img

        return None

    def clear_cache(self) -> None:
        """Clear the in-memory icon cache."""
        self._memory_cache.clear()

    def clear_disk_cache(self) -> None:
        """Remove all cached icon files from disk."""
        if self._cache_dir.exists():
            for f in self._cache_dir.glob("*.png"):
                f.unlink()
        self._memory_cache.clear()
