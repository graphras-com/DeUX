"""Rendering helpers for deux keys, cards, and touchscreen."""

from __future__ import annotations

from .context import RenderingContext
from .defaults import (
    SurfaceBackgrounds,
    get_default_backgrounds,
    list_supported_devices,
)
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
    load_svg_stylesheet,
    register_svg_backend,
    set_svg_backend,
    set_svg_stylesheet,
)
from .theme import (
    Theme,
    _apply_default_theme,
    get_active_theme,
    get_default_font_family,
    set_active_theme,
)
from .touch_renderer import (
    compose_touchstrip,
    render_blank_touchscreen,
)

# Apply the default theme so a baseline CSS stylesheet is always active.
_apply_default_theme()

__all__ = [
    "RenderingContext",
    "SurfaceBackgrounds",
    "Theme",
    "ImageFetchError",
    "RasterizeError",
    "RenderMetrics",
    "SvgRasterizer",
    "clear_image_cache",
    "compose_touchstrip",
    "fetch_image",
    "get_active_theme",
    "get_default_backgrounds",
    "get_default_font_family",
    "get_svg_backend",
    "get_svg_stylesheet",
    "list_supported_devices",
    "list_svg_backends",
    "load_svg_stylesheet",
    "register_svg_backend",
    "render_blank_key",
    "render_blank_touchscreen",
    "render_info_screen",
    "render_key_image",
    "set_active_theme",
    "set_svg_backend",
    "set_svg_stylesheet",
]
