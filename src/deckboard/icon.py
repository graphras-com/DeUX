"""Compatibility exports for icon fetching and caching helpers."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from .render import icons as _icons

IconError = _icons.IconError
_svg_to_png = _icons._svg_to_png
subprocess = _icons.subprocess


class IconManager(_icons.IconManager):
    """Backward-compatible icon manager that preserves old patch points."""

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
            _icons.logger.debug("Icon cache hit (disk): %s", name)
            return img

        _icons.logger.info("Fetching icon from Iconify: %s", name)
        prefix, icon_name = self._parse_icon_name(name)
        url = self._build_url(prefix, icon_name, color)

        client = await self._get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except _icons.httpx.HTTPError as exc:
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
        _icons.logger.debug("Icon cached: %s -> %s", name, disk_path)
        return img


__all__ = ["IconError", "IconManager", "_svg_to_png"]
