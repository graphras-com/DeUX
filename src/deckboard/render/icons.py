"""Icon fetching, conversion, and caching for rendered deckboard UI."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "deckboard" / "icons"
_ICONIFY_API = "https://api.iconify.design"


class IconError(Exception):
    """Raised when an icon cannot be fetched or converted."""


def _svg_to_png(svg_data: bytes, width: int, height: int) -> bytes:
    """Convert SVG bytes to PNG bytes."""
    try:
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

    raise IconError(
        "No SVG renderer available. Install one of:\n"
        "  - System library: brew install cairo  (macOS) or apt install libcairo2 (Linux)\n"
        "  - CLI tool: apt install librsvg2-bin\n"
        "  - Python package: pip install cairosvg"
    )


class IconManager:
    """Fetch icons from Iconify and cache them as RGBA images."""

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
        color_safe = color.lstrip("#")
        name_safe = name.replace(":", "--").replace("/", "--")
        return f"{name_safe}--{size}--{color_safe}"

    def _cache_path(self, cache_key: str) -> Path:
        return self._cache_dir / f"{cache_key}.png"

    def _parse_icon_name(self, name: str) -> tuple[str, str]:
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
        encoded_color = color.replace("#", "%23")
        return f"{_ICONIFY_API}/{prefix}/{icon_name}.svg?color={encoded_color}"

    async def get(
        self,
        name: str,
        size: int = 80,
        color: str = "white",
    ) -> Image.Image:
        """Fetch an icon as a PIL image."""
        cache_key = self._cache_key(name, size, color)

        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        disk_path = self._cache_path(cache_key)
        if disk_path.exists():
            img = Image.open(disk_path).convert("RGBA")
            self._memory_cache[cache_key] = img
            logger.debug("Icon cache hit (disk): %s", name)
            return img

        logger.info("Fetching icon from Iconify: %s", name)
        prefix, icon_name = self._parse_icon_name(name)
        url = self._build_url(prefix, icon_name, color)

        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise IconError(f"Failed to fetch icon '{name}' from {url}: {exc}") from exc

        svg_data = resp.content
        if not svg_data or b"<svg" not in svg_data:
            raise IconError(f"Invalid SVG response for icon '{name}'")

        try:
            png_data = _svg_to_png(svg_data, size, size)
        except Exception as exc:
            raise IconError(
                f"Failed to convert SVG to PNG for icon '{name}': {exc}"
            ) from exc

        img = Image.open(BytesIO(png_data)).convert("RGBA")
        img.save(disk_path, "PNG")
        self._memory_cache[cache_key] = img
        logger.debug("Icon cached: %s -> %s", name, disk_path)
        return img

    def get_cached(
        self, name: str, size: int = 80, color: str = "white"
    ) -> Image.Image | None:
        """Synchronously retrieve an icon if it is already cached."""
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
            for file in self._cache_dir.glob("*.png"):
                file.unlink()
        self._memory_cache.clear()
