"""SVG-to-image rasterisation with a pluggable backend registry.

Built-in backends: ``cairo`` (CairoSVG), ``pyvips``, and ``rsvg-cli``
(subprocess).  Third-party backends can be registered at runtime via
:func:`register_svg_backend`.

An application-wide CSS stylesheet can be set via
:func:`set_svg_stylesheet`.  It is applied to every SVG before
rasterisation — natively for pyvips, or by injecting a ``<style>``
element for other backends.

SVG document manipulation helpers are provided for the SVG-native
render pipeline: :func:`set_svg_dimensions`, :func:`inject_background_rect`,
:func:`compose_svg_layers`, and :func:`slice_background_viewbox`.  These
allow sizing, background injection, and multi-layer compositing to happen
entirely at the SVG (vector) level before a single rasterisation pass.

Examples
--------
Select a specific backend::

    from deux import set_svg_backend
    set_svg_backend("pyvips")

Set a global CSS stylesheet::

    from deux import set_svg_stylesheet
    set_svg_stylesheet(\"\"\".text-primary { color: #ff0000; }\"\"\")

Register a custom backend::

    from deux import SvgRasterizer, register_svg_backend, set_svg_backend

    class MyRasterizer:
        def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
            ...

    register_svg_backend("custom", MyRasterizer())
    set_svg_backend("custom")
"""

from __future__ import annotations

import copy
import io
import logging
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Protocol, runtime_checkable

from .._errors import DeuxError
from .._xml import safe_fromstring

logger = logging.getLogger(__name__)

def _ensure_macos_lib_path() -> None:
    """Set ``DYLD_FALLBACK_LIBRARY_PATH`` on macOS if Homebrew libs exist.

    macOS SIP strips ``DYLD_*`` variables from child processes, so
    Homebrew-installed C libraries (libcairo, libvips, etc.) are not
    found by default.  This sets the fallback path once so that
    ``cffi``/``ctypes`` can locate them.
    """
    if platform.system() == "Darwin":
        brew_lib = Path("/opt/homebrew/lib")
        if brew_lib.exists():
            os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", str(brew_lib))


class RasterizeError(DeuxError):
    """Raised when SVG rasterisation fails."""


@runtime_checkable
class SvgRasterizer(Protocol):
    """Protocol for SVG-to-PNG rasterisation backends.

    Any object that implements :meth:`rasterize` with the correct
    signature can be used as a backend.
    """

    def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
        """Convert raw SVG bytes to PNG bytes.

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
            If rasterisation fails.
        """
        pass  # pragma: no cover


# ---------------------------------------------------------------------------
# Built-in backend implementations
# ---------------------------------------------------------------------------


class CairoRasterizer:
    """SVG rasteriser using CairoSVG.

    The ``cairosvg`` package is imported lazily on first call so that the
    module can be imported even when CairoSVG is not installed.
    """

    def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
        """Rasterise *svg_data* to PNG via ``cairosvg.svg2png``.

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
            If CairoSVG is not installed or the underlying C library
            cannot be loaded.
        """
        try:
            _ensure_macos_lib_path()

            import cairosvg

            result: bytes = cairosvg.svg2png(
                bytestring=svg_data,
                output_width=width,
                output_height=height,
            )
            return result
        except (OSError, ImportError) as exc:
            raise RasterizeError(f"cairosvg unavailable: {exc}") from exc
        except Exception as exc:
            raise RasterizeError(f"cairosvg rasterisation failed: {exc}") from exc


class PyvipsRasterizer:
    """SVG rasteriser using pyvips.

    The ``pyvips`` package is imported lazily on first call so that the
    module can be imported even when pyvips is not installed.
    """

    def rasterize(
        self,
        svg_data: bytes,
        width: int,
        height: int,
        *,
        stylesheet: str | None = None,
    ) -> bytes:
        """Rasterise *svg_data* to PNG via ``pyvips``.

        Parameters
        ----------
        svg_data : bytes
            Raw SVG content.
        width : int
            Desired output width in pixels.
        height : int
            Desired output height in pixels.
        stylesheet : str or None, optional
            CSS stylesheet text to apply during rasterisation.  Passed
            to ``pyvips.Image.svgload_buffer`` as the ``stylesheet``
            parameter (requires librsvg >= 2.48).

        Returns
        -------
        bytes
            PNG image bytes.

        Raises
        ------
        RasterizeError
            If pyvips is not installed or SVG loading fails.
        """
        try:
            _ensure_macos_lib_path()
            import pyvips

            # Suppress noisy libvips GLib messages (e.g. "threadpool completed")
            # by raising the pyvips logger threshold to WARNING.
            logging.getLogger("pyvips").setLevel(logging.WARNING)

            load_kwargs: dict[str, str] = {}
            if stylesheet is not None:
                load_kwargs["stylesheet"] = stylesheet

            image = pyvips.Image.svgload_buffer(svg_data, **load_kwargs)
            # Scale to fit the requested dimensions.
            h_scale = width / image.width
            v_scale = height / image.height
            image = image.resize(h_scale, vscale=v_scale)
            png_bytes: bytes = image.write_to_buffer(".png")
            return png_bytes
        except (OSError, ImportError) as exc:
            raise RasterizeError(f"pyvips unavailable: {exc}") from exc
        except Exception as exc:
            raise RasterizeError(f"pyvips rasterisation failed: {exc}") from exc


class RsvgCliRasterizer:
    """SVG rasteriser using the ``rsvg-convert`` CLI tool."""

    def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
        """Rasterise *svg_data* to PNG via the ``rsvg-convert`` subprocess.

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
            If ``rsvg-convert`` is not found or the subprocess fails.
        """
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
            raise RasterizeError(f"rsvg-convert unavailable: {exc}") from exc


# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------

_registry: dict[str, SvgRasterizer] = {}
_active_backend: str | None = None
_active_stylesheet: str | None = None


def register_svg_backend(name: str, backend: SvgRasterizer) -> None:
    """Register an SVG rasterisation backend.

    Parameters
    ----------
    name : str
        Unique name for the backend (e.g. ``"cairo"``, ``"pyvips"``).
    backend : SvgRasterizer
        An object implementing the :class:`SvgRasterizer` protocol.

    Raises
    ------
    TypeError
        If *backend* does not implement :class:`SvgRasterizer`.
    """
    if not isinstance(backend, SvgRasterizer):
        raise TypeError(
            f"backend must implement SvgRasterizer protocol, got {type(backend).__name__}"
        )
    _registry[name] = backend
    logger.debug("Registered SVG backend %r", name)


def set_svg_backend(name: str, *, verify: bool = True) -> None:
    """Select the active SVG rasterisation backend by name.

    By default, performs a smoke test to verify the backend can
    rasterise a trivial SVG.  Pass ``verify=False`` to skip.

    Parameters
    ----------
    name : str
        Name of a previously registered backend, or ``"auto"`` to use
        automatic fallback ordering.
    verify : bool, default=True
        When *True*, render a tiny SVG to confirm the backend works.
        Raises :class:`RasterizeError` immediately if it does not.

    Raises
    ------
    ValueError
        If *name* is not ``"auto"`` and has not been registered.
    RasterizeError
        If *verify* is True and the backend cannot rasterise.
    """
    global _active_backend  # noqa: PLW0603
    if name != "auto" and name not in _registry:
        raise ValueError(
            f"Unknown SVG backend {name!r}. "
            f"Registered backends: {', '.join(sorted(_registry)) or '(none)'}"
        )
    if verify and name != "auto":
        _test_svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">'
            b'<rect width="1" height="1"/></svg>'
        )
        _registry[name].rasterize(_test_svg, 1, 1)
    _active_backend = name
    logger.debug("Active SVG backend set to %r", name)


def get_svg_backend() -> str:
    """Return the name of the currently active SVG backend.

    Returns
    -------
    str
        ``"auto"`` when no explicit backend has been chosen, otherwise
        the name passed to :func:`set_svg_backend`.
    """
    return _active_backend or "auto"


def list_svg_backends() -> list[str]:
    """Return the names of all registered SVG backends.

    Returns
    -------
    list[str]
        Sorted list of registered backend names.
    """
    return sorted(_registry)


# ---------------------------------------------------------------------------
# Application-wide CSS stylesheet
# ---------------------------------------------------------------------------


def set_svg_stylesheet(css: str | None) -> None:
    """Set an application-wide CSS stylesheet for SVG rasterisation.

    The stylesheet is applied to every SVG before rasterisation.  When
    the pyvips backend is active, the CSS is passed via the native
    ``stylesheet`` parameter (requires librsvg >= 2.48).  For all other
    backends the CSS is injected as a ``<style>`` element **before** any
    existing ``<style>`` elements in the SVG, so that per-package styles
    can override the application defaults.

    Pass ``None`` to clear the stylesheet.

    Parameters
    ----------
    css : str or None
        Raw CSS text, or ``None`` to remove a previously set stylesheet.

    Examples
    --------
    ::

        from deux import set_svg_stylesheet

        set_svg_stylesheet(\"\"\"
            .text-primary { color: #ff0000; }
        \"\"\")
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


_SVG_NS = "http://www.w3.org/2000/svg"


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
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    root = safe_fromstring(svg_data)  # untrusted: may contain user SVG

    style_elem = ET.Element(f"{{{_SVG_NS}}}style")
    style_elem.set("type", "text/css")
    style_elem.text = css

    # Insert as first child so existing <style> elements override it.
    root.insert(0, style_elem)

    return ET.tostring(root, encoding="unicode", xml_declaration=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Auto-fallback ordering
# ---------------------------------------------------------------------------

_AUTO_ORDER: tuple[str, ...] = ("pyvips", "cairo", "rsvg-cli")


def _svg_to_png(svg_data: bytes, width: int, height: int) -> bytes:
    """Convert SVG bytes to PNG bytes using the active backend.

    When the backend is ``"auto"`` (the default), tries each registered
    backend in order: pyvips -> cairo -> rsvg-cli.

    If an application-wide stylesheet has been set via
    :func:`set_svg_stylesheet`, it is applied before rasterisation.
    For the pyvips backend the stylesheet is passed natively; for all
    other backends it is injected as a ``<style>`` element.

    .. deprecated::
        Use :func:`_rasterize_svg` for new code.  This function is
        retained for backward compatibility.

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
        If no SVG renderer backend is available or the selected backend
        fails.
    """
    backend_name = _active_backend or "auto"
    css = _active_stylesheet
    return _resolve_and_rasterize(backend_name, css, svg_data, width, height)


def _rasterize_with_stylesheet(
    backend: SvgRasterizer,
    name: str,
    svg_data: bytes,
    width: int,
    height: int,
    css: str | None,
) -> bytes:
    """Rasterise SVG data, applying the stylesheet appropriately.

    For the pyvips backend, the stylesheet is passed via the native
    ``stylesheet`` keyword argument.  For all other backends the
    stylesheet is injected as a ``<style>`` element into the SVG data.

    Parameters
    ----------
    backend : SvgRasterizer
        The rasterisation backend instance.
    name : str
        The registered name of the backend.
    svg_data : bytes
        Raw SVG content.
    width : int
        Desired output width in pixels.
    height : int
        Desired output height in pixels.
    css : str or None
        CSS stylesheet text, or ``None`` if no stylesheet is active.

    Returns
    -------
    bytes
        Rasterised PNG image bytes.
    """
    if css is not None and name == "pyvips" and isinstance(backend, PyvipsRasterizer):
        return backend.rasterize(svg_data, width, height, stylesheet=css)

    if css is not None:
        svg_data = _inject_stylesheet(svg_data, css)

    return backend.rasterize(svg_data, width, height)


# ---------------------------------------------------------------------------
# Direct output-format rasterisation
# ---------------------------------------------------------------------------


def _rasterize_svg(
    svg_data: bytes,
    width: int,
    height: int,
    *,
    output_format: str = "png",
    quality: int = 90,
) -> bytes:
    """Rasterise SVG bytes directly to the requested image format.

    This is the preferred entry point for the SVG-native pipeline.
    It bypasses the PNG intermediate when the active backend supports
    direct JPEG output (currently pyvips).  For backends that only
    produce PNG, the PNG bytes are re-encoded via Pillow when a
    different format is requested.

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

    Returns
    -------
    bytes
        Rasterised image bytes in the requested format.

    Raises
    ------
    RasterizeError
        If no SVG renderer backend is available or rasterisation fails.
    ValueError
        If *output_format* is not one of ``"png"``, ``"jpeg"``, ``"bmp"``.
    """
    fmt = output_format.lower()
    if fmt not in ("png", "jpeg", "bmp"):
        raise ValueError(f"Unsupported output format: {output_format!r}")

    backend_name = _active_backend or "auto"
    css = _active_stylesheet

    # Try to get PNG bytes first (the universal intermediate).
    png_bytes = _resolve_and_rasterize(backend_name, css, svg_data, width, height)

    if fmt == "png":
        return png_bytes

    # For JPEG and BMP we need to convert from PNG.
    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    buf = io.BytesIO()
    if fmt == "jpeg":
        img.save(buf, format="JPEG", quality=quality)
    else:  # bmp
        img.save(buf, format="BMP")
    return buf.getvalue()


def _resolve_and_rasterize(
    backend_name: str,
    css: str | None,
    svg_data: bytes,
    width: int,
    height: int,
) -> bytes:
    """Select a backend and rasterise to PNG bytes.

    Extracted from :func:`_svg_to_png` to share logic with
    :func:`_rasterize_svg`.

    Parameters
    ----------
    backend_name : str
        Backend name or ``"auto"``.
    css : str or None
        Active CSS stylesheet text.
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
        If no backend is available.
    """
    if backend_name != "auto":
        backend = _registry[backend_name]
        return _rasterize_with_stylesheet(backend, backend_name, svg_data, width, height, css)

    errors: list[str] = []
    for name in _AUTO_ORDER:
        auto_backend = _registry.get(name)
        if auto_backend is None:
            continue
        try:
            return _rasterize_with_stylesheet(
                auto_backend, name, svg_data, width, height, css
            )
        except RasterizeError as exc:
            logger.debug("Backend %r failed: %s", name, exc)
            errors.append(f"  - {name}: {exc}")

    error_detail = "\n".join(errors) if errors else "  (no backends registered)"
    raise RasterizeError(
        "No SVG renderer available. Install one of:\n"
        "  - System library: brew install cairo  (macOS) or apt install libcairo2 "
        "(Linux)\n"
        "  - CLI tool: apt install librsvg2-bin\n"
        "  - Python package: pip install cairosvg\n"
        "  - Python package: pip install pyvips\n"
        "\nBackend errors:\n" + error_detail
    )


# ---------------------------------------------------------------------------
# SVG document manipulation helpers
# ---------------------------------------------------------------------------

_XLINK_NS = "http://www.w3.org/1999/xlink"


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


# ---------------------------------------------------------------------------
# Register built-in backends at import time
# ---------------------------------------------------------------------------

register_svg_backend("cairo", CairoRasterizer())
register_svg_backend("pyvips", PyvipsRasterizer())
register_svg_backend("rsvg-cli", RsvgCliRasterizer())
