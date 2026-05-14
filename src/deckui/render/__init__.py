"""Rendering helpers for deckui keys, cards, and touchscreen."""

from __future__ import annotations

from .image_fetch import ImageFetchError, fetch_image
from .image_fetch import clear_cache as clear_image_cache
from .key_renderer import render_blank_key, render_key_image
from .metrics import RenderMetrics
from .screen_renderer import render_info_screen
from .svg_rasterize import (
    RasterizeError,
    SvgRasterizer,
    get_svg_backend,
    get_svg_stylesheet,
    list_svg_backends,
    register_svg_backend,
    set_svg_backend,
    set_svg_stylesheet,
)
from .touch_renderer import (
    compose_touchstrip,
    render_blank_touchscreen,
)

__all__ = [
    "ImageFetchError",
    "RasterizeError",
    "RenderMetrics",
    "SvgRasterizer",
    "clear_image_cache",
    "compose_touchstrip",
    "fetch_image",
    "get_svg_backend",
    "get_svg_stylesheet",
    "list_svg_backends",
    "register_svg_backend",
    "render_blank_key",
    "render_blank_touchscreen",
    "render_info_screen",
    "render_key_image",
    "set_svg_backend",
    "set_svg_stylesheet",
]
