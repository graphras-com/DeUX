"""SVG-to-image rasterisation using the resvg pure-Rust backend.

An application-wide CSS stylesheet can be set via
:func:`set_svg_stylesheet`.  It is applied to every SVG before
rasterisation by injecting a ``<style>`` element.

SVG document manipulation helpers are provided for the SVG-native
render pipeline: :func:`set_svg_dimensions`, :func:`inject_background_rect`,
:func:`compose_svg_layers`, and :func:`slice_background_viewbox`.  These
allow sizing, background injection, and multi-layer compositing to happen
entirely at the SVG (vector) level before a single rasterisation pass.
"""

from __future__ import annotations

import copy
import io
import logging
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from .._errors import DeuxError
from .._xml import safe_fromstring
from .context import RenderingContext

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)
_perf_logger = logging.getLogger("deux.render.profiler")


class RasterizeError(DeuxError):
    """Raised when SVG rasterisation fails."""


# ---------------------------------------------------------------------------
# Resvg rasteriser
# ---------------------------------------------------------------------------

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"


def _resvg_rasterize(svg_data: bytes, width: int, height: int) -> bytes:
    """Rasterise SVG bytes to PNG via the ``resvg`` Rust binding.

    To control output dimensions, the SVG ``width`` and ``height``
    attributes are set to the requested size before parsing.  A
    ``viewBox`` is added (preserving the original design dimensions) if
    one is not already present, so the resvg engine performs
    vector-level scaling.

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
        PNG image bytes.

    Raises
    ------
    RasterizeError
        If ``resvg`` is not installed or SVG parsing/rendering fails.
    """
    try:
        from resvg import render as _resvg_render
        from resvg import usvg

        root = safe_fromstring(svg_data)
        if "viewBox" not in root.attrib:
            orig_w = root.get("width", str(width))
            orig_h = root.get("height", str(height))
            # Strip non-numeric units (e.g. "100px" -> "100")
            orig_w = "".join(c for c in orig_w if c.isdigit() or c == ".")
            orig_h = "".join(c for c in orig_h if c.isdigit() or c == ".")
            root.set("viewBox", f"0 0 {orig_w} {orig_h}")
        root.set("width", str(width))
        root.set("height", str(height))

        ET.register_namespace("", _SVG_NS)
        ET.register_namespace("xlink", _XLINK_NS)
        svg_text = ET.tostring(root, encoding="unicode", xml_declaration=False)

        opts = usvg.Options.default()
        opts.load_system_fonts()
        tree = usvg.Tree.from_str(svg_text, opts)

        png_bytes: bytes = _resvg_render(tree, (1.0, 0.0, 0.0, 0.0, 1.0, 0.0))
        return png_bytes
    except ImportError as exc:
        raise RasterizeError(f"resvg unavailable: {exc}") from exc
    except Exception as exc:
        raise RasterizeError(f"resvg rasterisation failed: {exc}") from exc


def _resvg_rasterize_rgba(
    svg_data: bytes, width: int, height: int
) -> tuple[bytes, int, int]:
    """Rasterise SVG bytes to raw RGBA pixels via the ``resvg`` Rust binding.

    Uses :func:`resvg.render_rgba` to obtain the pixel buffer directly,
    avoiding the PNG encode/decode round-trip incurred by
    :func:`_resvg_rasterize`.

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
    tuple[bytes, int, int]
        A ``(rgba_bytes, width, height)`` tuple where *rgba_bytes*
        contains ``width * height * 4`` pre-multiplied RGBA bytes.

    Raises
    ------
    RasterizeError
        If ``resvg`` is not installed or SVG parsing/rendering fails.
    """
    try:
        from resvg import render_rgba as _resvg_render_rgba
        from resvg import usvg

        root = safe_fromstring(svg_data)
        if "viewBox" not in root.attrib:
            orig_w = root.get("width", str(width))
            orig_h = root.get("height", str(height))
            orig_w = "".join(c for c in orig_w if c.isdigit() or c == ".")
            orig_h = "".join(c for c in orig_h if c.isdigit() or c == ".")
            root.set("viewBox", f"0 0 {orig_w} {orig_h}")
        root.set("width", str(width))
        root.set("height", str(height))

        ET.register_namespace("", _SVG_NS)
        ET.register_namespace("xlink", _XLINK_NS)
        svg_text = ET.tostring(root, encoding="unicode", xml_declaration=False)

        opts = usvg.Options.default()
        opts.load_system_fonts()
        tree = usvg.Tree.from_str(svg_text, opts)

        rgba_bytes, w, h = _resvg_render_rgba(tree, (1.0, 0.0, 0.0, 0.0, 1.0, 0.0))
        return bytes(rgba_bytes), w, h
    except ImportError as exc:
        raise RasterizeError(f"resvg unavailable: {exc}") from exc
    except Exception as exc:
        raise RasterizeError(f"resvg rasterisation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Application-wide CSS stylesheet
# ---------------------------------------------------------------------------

_active_stylesheet: str | None = None


def set_svg_stylesheet(css: str | None) -> None:
    """Set an application-wide CSS stylesheet for SVG rasterisation.

    The stylesheet is applied to every SVG before rasterisation by
    injecting a ``<style>`` element **before** any existing ``<style>``
    elements in the SVG, so that per-package styles can override the
    application defaults.

    Pass ``None`` to clear the stylesheet.

    Parameters
    ----------
    css : str or None
        Raw CSS text, or ``None`` to remove a previously set stylesheet.

    Examples
    --------
    ::

        from deux import set_svg_stylesheet

        set_svg_stylesheet(\"\"\".text-primary { color: #ff0000; }\"\"\")
    """
    global _active_stylesheet  # noqa: PLW0603
    _active_stylesheet = css
    logger.debug(
        "SVG stylesheet %s",
        "cleared" if css is None else f"set ({len(css)} chars)",
    )


def get_svg_stylesheet() -> str | None:
    """Return the currently active application-wide CSS stylesheet.

    Returns
    -------
    str or None
        The CSS text set via :func:`set_svg_stylesheet`, or ``None``
        if no stylesheet is active.
    """
    return _active_stylesheet


def load_svg_stylesheet(path: str | Path) -> None:
    """Load a CSS stylesheet from a file and set it as the active stylesheet.

    This is a convenience wrapper around :func:`set_svg_stylesheet` that
    reads the CSS text from *path* and applies it application-wide.

    Parameters
    ----------
    path : str or Path
        Path to a CSS file (UTF-8 encoded).

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    IsADirectoryError
        If *path* is a directory.

    Examples
    --------
    ::

        from deux import load_svg_stylesheet

        load_svg_stylesheet("assets/theme.css")
    """
    css = Path(path).read_text(encoding="utf-8")
    set_svg_stylesheet(css)


def _inject_stylesheet(svg_data: bytes, css: str) -> bytes:
    """Inject a ``<style>`` element into SVG bytes as the first child.

    The ``<style>`` element is inserted as the **first child** of the
    root ``<svg>`` element, before any existing ``<style>`` or ``<defs>``
    elements.  This ensures that per-package styles (defined later in
    the document) take precedence in the CSS cascade.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content (UTF-8).
    css : str
        CSS text to inject.

    Returns
    -------
    bytes
        Modified SVG content with the stylesheet injected.
    """
    # Register the SVG namespace so ET doesn't emit ns0: prefixes.
    ET.register_namespace("", _SVG_NS)
    ET.register_namespace("xlink", _XLINK_NS)

    root = safe_fromstring(svg_data)  # untrusted: may contain user SVG

    style_elem = ET.Element(f"{{{_SVG_NS}}}style")
    style_elem.set("type", "text/css")
    style_elem.text = css

    # Insert as first child so existing <style> elements override it.
    root.insert(0, style_elem)

    return ET.tostring(root, encoding="unicode", xml_declaration=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Public rasterisation entry points
# ---------------------------------------------------------------------------


def _svg_to_png(
    svg_data: bytes,
    width: int,
    height: int,
    *,
    ctx: RenderingContext | None = None,
) -> bytes:
    """Convert SVG bytes to PNG bytes using resvg.

    If an application-wide stylesheet has been set via
    :func:`set_svg_stylesheet`, it is injected as a ``<style>`` element
    before rasterisation.

    When *ctx* is provided, its stylesheet overrides the module-level
    global, allowing concurrent renders with different themes.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content.
    width : int
        Desired output width in pixels.
    height : int
        Desired output height in pixels.
    ctx : RenderingContext or None, optional
        Explicit rendering context.  When ``None``, falls back to
        module-level globals.

    Returns
    -------
    bytes
        Rasterised PNG image bytes.

    Raises
    ------
    RasterizeError
        If resvg is not available or rasterisation fails.
    """
    css = ctx.resolve_stylesheet() if ctx is not None else _active_stylesheet

    t0 = time.perf_counter()
    if css is not None:
        svg_data = _inject_stylesheet(svg_data, css)

    result = _resvg_rasterize(svg_data, width, height)
    elapsed = (time.perf_counter() - t0) * 1000.0
    _perf_logger.debug("_svg_to_png %dx%d %.1fms", width, height, elapsed)
    return result


def _svg_to_image(
    svg_data: bytes,
    width: int,
    height: int,
    *,
    mode: str = "RGBA",
    ctx: RenderingContext | None = None,
) -> Image.Image:
    """Convert SVG bytes to a PIL :class:`~PIL.Image.Image` without a PNG round-trip.

    Uses :func:`_resvg_rasterize_rgba` to obtain raw RGBA pixels and
    constructs a PIL Image via :func:`Image.frombuffer`, bypassing the
    PNG encode/decode cycle that :func:`_svg_to_png` requires.

    If an application-wide stylesheet has been set via
    :func:`set_svg_stylesheet`, it is injected before rasterisation.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content.
    width : int
        Desired output width in pixels.
    height : int
        Desired output height in pixels.
    mode : str, default="RGBA"
        PIL image mode for the result (e.g. ``"RGBA"`` or ``"RGB"``).
    ctx : RenderingContext or None, optional
        Explicit rendering context.  When ``None``, falls back to
        module-level globals.

    Returns
    -------
    Image.Image
        Rasterised image as a PIL Image in the requested *mode*.

    Raises
    ------
    RasterizeError
        If resvg is not available or rasterisation fails.
    """
    from PIL import Image

    css = ctx.resolve_stylesheet() if ctx is not None else _active_stylesheet

    t0 = time.perf_counter()
    if css is not None:
        svg_data = _inject_stylesheet(svg_data, css)

    rgba_bytes, w, h = _resvg_rasterize_rgba(svg_data, width, height)
    img = Image.frombuffer("RGBA", (w, h), rgba_bytes, "raw", "RGBA", 0, 1)
    if mode != "RGBA":
        img = img.convert(mode)
    elapsed = (time.perf_counter() - t0) * 1000.0
    _perf_logger.debug("_svg_to_image %dx%d mode=%s %.1fms", width, height, mode, elapsed)
    return img


def _rasterize_svg(
    svg_data: bytes,
    width: int,
    height: int,
    *,
    output_format: str = "png",
    quality: int = 90,
    ctx: RenderingContext | None = None,
) -> bytes:
    """Rasterise SVG bytes directly to the requested image format.

    For PNG output, rasterises via resvg and returns the encoded PNG
    bytes directly.  For JPEG and BMP, rasterises to raw RGBA pixels
    (bypassing a PNG round-trip), converts to a PIL Image, and
    re-encodes in the target format.

    When *ctx* is provided, its stylesheet overrides the module-level
    global, allowing concurrent renders with different themes.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content (UTF-8).
    width : int
        Desired output width in pixels.
    height : int
        Desired output height in pixels.
    output_format : str, default="png"
        Target image format: ``"png"``, ``"jpeg"``, or ``"bmp"``.
    quality : int, default=90
        JPEG quality (ignored for other formats).
    ctx : RenderingContext or None, optional
        Explicit rendering context.  When ``None``, falls back to
        module-level globals.

    Returns
    -------
    bytes
        Rasterised image bytes in the requested format.

    Raises
    ------
    RasterizeError
        If resvg is not available or rasterisation fails.
    ValueError
        If *output_format* is not one of ``"png"``, ``"jpeg"``, ``"bmp"``.
    """
    fmt = output_format.lower()
    if fmt not in ("png", "jpeg", "bmp"):
        raise ValueError(f"Unsupported output format: {output_format!r}")

    t0 = time.perf_counter()

    if fmt == "png":
        result = _svg_to_png(svg_data, width, height, ctx=ctx)
    else:
        img = _svg_to_image(svg_data, width, height, mode="RGB", ctx=ctx)
        buf = io.BytesIO()
        if fmt == "jpeg":
            img.save(buf, format="JPEG", quality=quality)
        else:
            img.save(buf, format="BMP")
        result = buf.getvalue()

    elapsed = (time.perf_counter() - t0) * 1000.0
    _perf_logger.debug("_rasterize_svg %dx%d fmt=%s %.1fms", width, height, fmt, elapsed)
    return result


# ---------------------------------------------------------------------------
# SVG document manipulation helpers
# ---------------------------------------------------------------------------


def set_svg_dimensions(root: ET.Element, width: int, height: int) -> None:
    """Set ``width`` and ``height`` attributes on an SVG root element.

    The ``viewBox`` is left unchanged so that the SVG engine performs
    vector-level scaling from the design canvas to the target device
    dimensions.

    Parameters
    ----------
    root : ET.Element
        The ``<svg>`` root element (mutated in place).
    width : int
        Target width in pixels.
    height : int
        Target height in pixels.
    """
    root.set("width", str(width))
    root.set("height", str(height))


def inject_background_rect(root: ET.Element, color: str) -> None:
    """Insert a solid-colour background ``<rect>`` as the first child.

    The rectangle fills 100% of the SVG viewport so the rasterised
    output is fully opaque.  This eliminates the need for Pillow-level
    canvas creation and alpha compositing.

    Parameters
    ----------
    root : ET.Element
        The ``<svg>`` root element (mutated in place).
    color : str
        CSS colour value (e.g. ``"black"``, ``"#1a1a2e"``).
    """
    rect = ET.Element(f"{{{_SVG_NS}}}rect")
    rect.set("width", "100%")
    rect.set("height", "100%")
    rect.set("fill", color)
    root.insert(0, rect)


def slice_background_viewbox(
    bg_root: ET.Element,
    card_index: int,
    panel_width: int,
    panel_height: int,
) -> ET.Element:
    """Clone a background SVG and set its viewBox to a panel-sized slice.

    The returned element is a deep copy with its ``viewBox`` adjusted
    to window into the region corresponding to *card_index*.  The
    ``width`` and ``height`` attributes are set to ``panel_width`` and
    ``panel_height`` so the slice fills the target panel exactly.

    Parameters
    ----------
    bg_root : ET.Element
        The full-width background ``<svg>`` root element.
    card_index : int
        Zero-based panel index (determines the x-offset of the slice).
    panel_width : int
        Width of a single panel in pixels.
    panel_height : int
        Height of a single panel in pixels.

    Returns
    -------
    ET.Element
        A cloned ``<svg>`` element with the sliced ``viewBox``.
    """
    sliced = copy.deepcopy(bg_root)
    x_offset = card_index * panel_width
    sliced.set("viewBox", f"{x_offset} 0 {panel_width} {panel_height}")
    sliced.set("width", str(panel_width))
    sliced.set("height", str(panel_height))
    return sliced


def compose_svg_layers(
    width: int,
    height: int,
    layers: list[ET.Element],
) -> ET.Element:
    """Create a wrapper SVG containing multiple nested ``<svg>`` layers.

    Each layer is embedded as a nested ``<svg>`` element positioned at
    the origin.  Layers are drawn in order (first = bottom, last = top)
    following the SVG painter's model.

    Parameters
    ----------
    width : int
        Output width in pixels.
    height : int
        Output height in pixels.
    layers : list[ET.Element]
        SVG elements to embed as layers.  Each should have its own
        ``viewBox``, ``width``, and ``height`` attributes.

    Returns
    -------
    ET.Element
        A wrapper ``<svg>`` root element containing all layers.
    """
    ET.register_namespace("", _SVG_NS)
    ET.register_namespace("xlink", _XLINK_NS)

    wrapper = ET.Element(f"{{{_SVG_NS}}}svg")
    wrapper.set("width", str(width))
    wrapper.set("height", str(height))
    wrapper.set("viewBox", f"0 0 {width} {height}")

    for layer in layers:
        # Ensure each layer has position attributes
        layer.set("x", "0")
        layer.set("y", "0")
        wrapper.append(layer)

    return wrapper
