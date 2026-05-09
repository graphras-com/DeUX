"""SVG-to-PNG rasterisation with a pluggable backend registry.

Built-in backends: ``cairo`` (CairoSVG), ``pyvips``, and ``rsvg-cli``
(subprocess).  Third-party backends can be registered at runtime via
:func:`register_svg_backend`.

Examples
--------
Select a specific backend::

    from deckui import set_svg_backend
    set_svg_backend("pyvips")

Register a custom backend::

    from deckui import SvgRasterizer, register_svg_backend, set_svg_backend

    class MyRasterizer:
        def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
            ...

    register_svg_backend("custom", MyRasterizer())
    set_svg_backend("custom")
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

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


class RasterizeError(Exception):
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

    def rasterize(self, svg_data: bytes, width: int, height: int) -> bytes:
        """Rasterise *svg_data* to PNG via ``pyvips``.

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
            If pyvips is not installed or SVG loading fails.
        """
        try:
            _ensure_macos_lib_path()
            import pyvips

            # Suppress noisy libvips GLib messages (e.g. "threadpool completed")
            # by raising the pyvips logger threshold to WARNING.
            logging.getLogger("pyvips").setLevel(logging.WARNING)

            image = pyvips.Image.svgload_buffer(svg_data)
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
# Auto-fallback ordering
# ---------------------------------------------------------------------------

_AUTO_ORDER: tuple[str, ...] = ("pyvips", "cairo", "rsvg-cli")


def _svg_to_png(svg_data: bytes, width: int, height: int) -> bytes:
    """Convert SVG bytes to PNG bytes using the active backend.

    When the backend is ``"auto"`` (the default), tries each registered
    backend in order: cairo -> pyvips -> rsvg-cli.

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

    if backend_name != "auto":
        return _registry[backend_name].rasterize(svg_data, width, height)

    # Auto mode: try backends in order, collecting errors.
    errors: list[str] = []
    for name in _AUTO_ORDER:
        backend = _registry.get(name)
        if backend is None:
            continue
        try:
            return backend.rasterize(svg_data, width, height)
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
# Register built-in backends at import time
# ---------------------------------------------------------------------------

register_svg_backend("cairo", CairoRasterizer())
register_svg_backend("pyvips", PyvipsRasterizer())
register_svg_backend("rsvg-cli", RsvgCliRasterizer())
