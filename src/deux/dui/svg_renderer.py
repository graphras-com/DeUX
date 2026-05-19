"""SVG-to-PIL rendering engine for .dui packages."""

from __future__ import annotations

import base64
import copy
import functools
import io
import logging
import math
import os
import platform
import xml.etree.ElementTree as ET
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, ClassVar

from PIL import Image, ImageFont

from .._xml import safe_fromstring
from ..render.context import RenderingContext
from .iconify import IconifyError, fetch_icon
from .schema import (
    Binding,
    ColorBinding,
    CssClassBinding,
    IconifyBinding,
    ImageBinding,
    ImageFit,
    ListBinding,
    OverflowMode,
    PackageSpec,
    RangeBinding,
    RangeDirection,
    RotateTransform,
    SliderBinding,
    TextBinding,
    ToggleBinding,
    TransformBinding,
    VisibilityBinding,
)

logger = logging.getLogger(__name__)

_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", _SVG_NS)
ET.register_namespace("xlink", _XLINK_NS)


def _find_element_by_id(root: ET.Element, element_id: str) -> ET.Element | None:
    """Find an element by its id attribute, searching all namespaces."""
    for elem in root.iter():
        if elem.get("id") == element_id:
            return elem
    return None


def _image_to_data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    """Encode a PIL Image as a base64 data URI."""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png" if fmt == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _fit_image(
    img: Image.Image, target_w: int, target_h: int, fit: ImageFit
) -> Image.Image:
    """Scale an image to fit within target dimensions using the specified mode."""
    if target_w <= 0 or target_h <= 0:
        return img

    src_w, src_h = img.size

    if fit == ImageFit.FILL:
        return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    if fit == ImageFit.CONTAIN:
        ratio = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * ratio))
        new_h = max(1, int(src_h * ratio))
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        paste_x = (target_w - new_w) // 2
        paste_y = (target_h - new_h) // 2
        canvas.paste(resized, (paste_x, paste_y))
        return canvas

    ratio = max(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * ratio))
    new_h = max(1, int(src_h * ratio))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _truncate_text(
    text: str,
    max_width: int,
    overflow: OverflowMode,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None,
) -> str:
    """Truncate single-line text so it fits within *max_width* pixels.

    When a Pillow *font* is provided, pixel-accurate measurement via
    :meth:`~PIL.ImageFont.ImageFont.getlength` is used.  Otherwise
    falls back to a simple character-width heuristic (7 px per char).

    Parameters
    ----------
    text : str
        The text string to truncate.
    max_width : int
        Maximum allowed width in pixels.
    overflow : OverflowMode
        How to handle overflow (``ELLIPSIS`` appends ``…``, ``CLIP``
        returns the original text unchanged).
    font : ImageFont.FreeTypeFont | ImageFont.ImageFont | None, optional
        Pillow font used for pixel-accurate measurement.  When *None*,
        a character-width heuristic is used as a fallback.

    Returns
    -------
    str
        The (possibly truncated) text.
    """
    if overflow == OverflowMode.CLIP:
        return text

    ellipsis = "\u2026"

    if font is not None:
        if font.getlength(text) <= max_width:
            return text
        # Binary-search for the longest prefix that fits with ellipsis.
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if font.getlength(text[:mid] + ellipsis) <= max_width:
                lo = mid
            else:
                hi = mid - 1
        return text[: max(1, lo)].rstrip() + ellipsis

    # Fallback: character-width heuristic (no font available).
    avg_char_width = 7
    max_chars = max(1, max_width // avg_char_width)

    if len(text) <= max_chars:
        return text

    return text[: max(1, max_chars - 1)] + ellipsis


_DEFAULT_FONT_FAMILY = "Inter"
_DEFAULT_FONT_SIZE = 16.0
_DEFAULT_LINE_HEIGHT_RATIO = 1.2


def _get_default_font_family() -> str:
    """Return the default font family from the active theme.

    Falls back to the module-level ``_DEFAULT_FONT_FAMILY`` if
    the theme system is not yet initialised (e.g. during import).

    Returns
    -------
    str
        The default font family name.
    """
    try:
        from ..render.theme import get_default_font_family

        return get_default_font_family()
    except Exception:
        return _DEFAULT_FONT_FAMILY


def _resolve_font_attrs(root: ET.Element, elem: ET.Element) -> tuple[str, float]:
    """Resolve font-family and font-size from an SVG element and its ancestors.

    Walks from *elem* up through the SVG tree to find ``font-family``
    and ``font-size`` attributes.  Falls back to sensible defaults if
    neither the element nor any ancestor declares them.

    Returns
    -------
    tuple[str, float]
        A ``(font_family, font_size)`` tuple.
    """
    family: str | None = None
    size: float | None = None

    parent_map: dict[ET.Element, ET.Element] = {}
    for parent in root.iter():
        for child in parent:
            parent_map[child] = parent

    current: ET.Element | None = elem
    while current is not None:
        if family is None:
            raw_family = current.get("font-family")
            if raw_family:
                family = raw_family.split(",")[0].strip().strip("'\"")
        if size is None:
            raw_size = current.get("font-size")
            if raw_size:
                with suppress(ValueError):
                    size = float(raw_size.rstrip("px"))
        if family is not None and size is not None:
            break
        current = parent_map.get(current)

    return (
        family or _get_default_font_family(),
        size or _DEFAULT_FONT_SIZE,
    )


def _system_font_dirs() -> list[Path]:
    """Return platform-specific system font directories.

    Returns
    -------
    list[Path]
        Directories that may contain ``.ttf`` / ``.otf`` font files.
    """
    dirs: list[Path] = []
    system = platform.system()
    if system == "Darwin":
        dirs.append(Path.home() / "Library" / "Fonts")
        dirs.append(Path("/Library/Fonts"))
        dirs.append(Path("/System/Library/Fonts"))
        dirs.append(Path("/System/Library/Fonts/Supplemental"))
    elif system == "Linux":
        dirs.append(Path.home() / ".local" / "share" / "fonts")
        dirs.append(Path.home() / ".fonts")
        dirs.append(Path("/usr/share/fonts"))
        dirs.append(Path("/usr/local/share/fonts"))
    elif system == "Windows":  # pragma: no cover
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        dirs.append(windir / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    return [d for d in dirs if d.is_dir()]


@functools.lru_cache(maxsize=1)
def _font_file_index() -> dict[str, Path]:
    """Build a lowercase-name-to-path index of system font files.

    Scans platform font directories once and caches the result.

    Returns
    -------
    dict[str, Path]
        Mapping of lowercased font stem names to their file paths.
    """
    index: dict[str, Path] = {}
    for font_dir in _system_font_dirs():
        try:
            for entry in font_dir.iterdir():
                if entry.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                    index[entry.stem.lower()] = entry
        except PermissionError:
            continue
    return index


def _find_font_file(family: str) -> Path | None:
    """Search system font directories for a font matching *family*.

    Generates candidate file-stem names from the family string and
    checks them against the cached font file index.

    Parameters
    ----------
    family : str
        Font family name (e.g. ``"Frutiger Linotype"``).

    Returns
    -------
    Path or None
        Path to a matching font file, or ``None`` if not found.
    """
    index = _font_file_index()
    # Build candidate stems: original, without spaces, hyphenated, etc.
    base = family.lower()
    candidates = [
        base,
        base.replace(" ", ""),
        base.replace(" ", "-"),
        base.replace(" ", "_"),
    ]
    # Try individual words (e.g. "Frutiger Linotype" -> "frutiger")
    words = base.split()
    if len(words) > 1:
        candidates.extend(words)
    # Also try without common suffixes
    for suffix in ("mt", "bold", "italic", "-regular", "-bold"):
        if base.endswith(suffix):
            stripped = base[: -len(suffix)].rstrip(" -_")
            candidates.append(stripped)
    for stem in dict.fromkeys(candidates):  # deduplicate, preserve order
        if stem in index:
            return index[stem]
    # Prefix match for variable font filenames (e.g. "inter" -> "inter-variablefont_...")
    for stem in dict.fromkeys(candidates):
        for key, path in index.items():
            if key.startswith(stem):
                return path
    return None


@functools.lru_cache(maxsize=32)
def _load_font(family: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font by family name and size, with fallbacks.

    First tries Pillow's built-in font name resolution (which works
    when the OS font API recognises the name).  If that fails, scans
    platform-specific font directories for a matching ``.ttf`` /
    ``.otf`` file.

    Parameters
    ----------
    family
        Font family name (e.g. ``"ArialMT"``, ``"Frutiger Linotype"``).
    size
        Font size in pixels (integer for cache-key hashability).
    """
    # 1. Try Pillow's built-in resolution with name variations.
    candidates: list[str] = [family]
    for suffix in ("MT", "Bold", "Italic", "-Regular", "-Bold"):
        if family.endswith(suffix):
            candidates.append(family[: -len(suffix)])
    candidates.append(family.lower())
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    for name in unique:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue

    # 2. Scan system font directories for a matching file.
    font_path = _find_font_file(family)
    if font_path is not None:
        try:
            return ImageFont.truetype(str(font_path), size)
        except OSError:
            pass

    logger.warning(
        "Could not load font '%s' at size %d; using Pillow default font. "
        "Text wrapping measurements may be inaccurate.",
        family,
        size,
    )
    return ImageFont.load_default()


def _wrap_text(
    text: str,
    max_width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    overflow: OverflowMode,
    max_height: int | None = None,
    line_height: float = 18.0,
) -> list[str]:
    """Word-wrap *text* into lines that fit within *max_width* pixels.

    Uses *font* for pixel-accurate text measurement via
    :meth:`~PIL.ImageFont.ImageFont.getlength`.

    If *max_height* is set, the number of visible lines is capped at
    ``floor(max_height / line_height)``.  When there are more lines
    than fit, the last visible line is truncated with an ellipsis
    character (if *overflow* is :attr:`~OverflowMode.ELLIPSIS`).

    Parameters
    ----------
    text
        The text string to wrap.
    max_width
        Maximum line width in pixels.
    font
        A Pillow font object for measurement.
    overflow
        How to handle text that doesn't fit.
    max_height
        Optional vertical pixel budget.
    line_height
        Vertical spacing between lines in pixels.

    Returns
    -------
    list[str]
        A list of line strings, one per wrapped line.
    """
    if not text or not text.strip():
        return []

    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current_line = words[0]

    for word in words[1:]:
        test_line = current_line + " " + word
        if font.getlength(test_line) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)

    if max_height is not None and line_height > 0:
        max_lines = max(1, math.floor(max_height / line_height))
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            if overflow == OverflowMode.ELLIPSIS:
                last = lines[-1]
                ellipsis = "\u2026"
                if font.getlength(last + ellipsis) > max_width:
                    while len(last) > 1 and font.getlength(last + ellipsis) > max_width:
                        last = last[:-1]
                    lines[-1] = last.rstrip() + ellipsis
                else:
                    lines[-1] = last + ellipsis

    return lines


class SvgRenderer:
    """Render a .dui SVG layout with live data bindings.

    The renderer holds a parsed copy of the SVG template.  Each call
    to :meth:`render` clones the template, applies current binding
    values, inlines image assets, and rasterises to a PIL Image via
    CairoSVG.

    Parameters
    ----------
    spec
        The validated package specification.
    """

    def __init__(self, spec: PackageSpec) -> None:
        self._spec = spec
        self._values: dict[str, Any] = {}
        self._base_root: ET.Element = safe_fromstring(spec.svg_source)  # untrusted: .dui pkg
        self._original_root: ET.Element = copy.deepcopy(self._base_root)
        self._range_extents: dict[str, float] = {}
        self._target_width: int | None = None
        self._target_height: int | None = None
        self._rendering_ctx: RenderingContext | None = None

        for name, binding in spec.bindings.items():
            if isinstance(binding, (TextBinding, VisibilityBinding, ColorBinding, CssClassBinding)):
                self._values[name] = binding.default
            elif isinstance(binding, RangeBinding):
                self._values[name] = binding.default
                elem = _find_element_by_id(self._base_root, binding.node)
                if elem is not None:
                    attr = (
                        "width"
                        if binding.direction == RangeDirection.HORIZONTAL
                        else "height"
                    )
                    self._range_extents[name] = float(elem.get(attr, "0"))
            elif isinstance(
                binding, (SliderBinding, ToggleBinding, IconifyBinding, TransformBinding)
            ):
                self._values[name] = binding.default
            elif isinstance(binding, ListBinding):
                self._values[name] = {
                    "items": list(binding.default_items),
                    "index": binding.default_index,
                }

    def set(self, name: str, value: Any) -> bool:
        """Set a binding value.

        Parameters
        ----------
        name
            Binding name as defined in the manifest.
        value
            The new value.  Type depends on the binding:
            text → ``str``, image → ``PIL.Image.Image`` or ``bytes``,
            visibility → ``bool``, color → ``str``.

        Returns
        -------
        bool
            ``True`` if the value actually changed (triggers dirty flag).

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        """
        if name not in self._spec.bindings:
            raise KeyError(
                f"Unknown binding '{name}'. Available: {sorted(self._spec.bindings)}"
            )

        old = self._values.get(name)
        binding = self._spec.bindings[name]
        if isinstance(binding, ImageBinding):
            self._values[name] = value
            return True

        if isinstance(binding, ListBinding) and isinstance(value, dict):
            current = self._values.get(name, {"items": [], "index": None})
            merged = dict(current)
            if "items" in value:
                merged["items"] = list(value["items"])
            if "index" in value:
                merged["index"] = value["index"]
            # Clamp index when items changed but index wasn't explicitly set.
            if "items" in value and "index" not in value:
                items = merged["items"]
                idx = merged["index"]
                if idx is not None and idx != -1 and items and idx >= len(items):
                    merged["index"] = len(items) - 1
                elif not items:
                    merged["index"] = None
            # Normalise -1 → None.
            if merged.get("index") == -1:
                merged["index"] = None
            if old == merged:
                return False
            self._values[name] = merged
            return True

        if old == value:
            return False

        self._values[name] = value
        return True

    def set_many(self, **kwargs: Any) -> bool:
        """Set multiple binding values at once.

        Returns
        -------
        bool
            ``True`` if any value changed.
        """
        changed = False
        for name, value in kwargs.items():
            if self.set(name, value):
                changed = True
        return changed

    def get(self, name: str) -> Any:
        """Get the current value of a binding.

        Raises
        ------
        KeyError
            If *name* is not a known binding.
        """
        if name not in self._spec.bindings:
            raise KeyError(
                f"Unknown binding '{name}'. Available: {sorted(self._spec.bindings)}"
            )
        return self._values.get(name)

    def set_target_size(self, width: int, height: int) -> None:
        """Set the target rasterisation dimensions.

        When set, the SVG ``width`` and ``height`` attributes are
        overridden to these values before rasterisation, enabling
        vector-level scaling from the ``viewBox`` design canvas to the
        device's native pixel dimensions.

        Parameters
        ----------
        width : int
            Target width in pixels.
        height : int
            Target height in pixels.
        """
        self._target_width = width
        self._target_height = height

    @property
    def rendering_context(self) -> RenderingContext | None:
        """The explicit rendering context, or ``None`` for global defaults.

        Returns
        -------
        RenderingContext or None
            The context set via :meth:`set_rendering_context`.
        """
        return self._rendering_ctx

    def set_rendering_context(self, ctx: RenderingContext | None) -> None:
        """Set an explicit rendering context for this renderer.

        When set, the context's stylesheet and backend override the
        module-level globals during rasterisation.  Pass ``None`` to
        revert to the global defaults.

        Parameters
        ----------
        ctx : RenderingContext or None
            The rendering context to use, or ``None`` for defaults.
        """
        self._rendering_ctx = ctx

    def set_base_layer(
        self,
        bg_root: ET.Element,
        card_index: int,
        panel_width: int,
        panel_height: int,
    ) -> None:
        """Set a background SVG layer underneath the card content.

        The background SVG's ``viewBox`` is sliced to the region
        corresponding to *card_index*, then composed as a layer beneath
        the card's own SVG template.  The composed tree replaces
        ``_base_root`` so that subsequent :meth:`render` calls produce
        a single SVG document with both layers.

        Call this when the background SVG or the card's slot assignment
        changes — not on every render.

        Parameters
        ----------
        bg_root : ET.Element
            The full-width background ``<svg>`` root element.
        card_index : int
            Zero-based panel index.
        panel_width : int
            Width of a single panel in pixels.
        panel_height : int
            Height of a single panel in pixels.
        """
        from ..render.svg_rasterize import compose_svg_layers, slice_background_viewbox

        bg_slice = slice_background_viewbox(bg_root, card_index, panel_width, panel_height)
        card_layer = copy.deepcopy(self._original_root)
        card_layer.set("width", str(panel_width))
        card_layer.set("height", str(panel_height))

        composed = compose_svg_layers(panel_width, panel_height, [bg_slice, card_layer])
        self._base_root = composed

    def clear_base_layer(self) -> None:
        """Remove the background layer and revert to the original SVG template.

        After calling this, :meth:`render` will produce output from the
        card's own SVG only, without any background layer.
        """
        self._base_root = copy.deepcopy(self._original_root)

    def render(self) -> Image.Image:
        """Rasterise the SVG with current binding values to a PIL Image.

        Returns
        -------
        Image.Image
            An RGBA :class:`~PIL.Image.Image`.  When target dimensions
            are set via :meth:`set_target_size` the image is rasterised
            at those dimensions (vector scaling); otherwise at the SVG's
            native dimensions.
        """
        root = copy.deepcopy(self._base_root)

        for name, binding in self._spec.bindings.items():
            value = self._values.get(name)
            self._apply_binding(root, name, binding, value)

        self._inline_assets(root)
        self._hide_spinner_node(root)

        svg_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
        logger.debug("Rendered SVG before rasterisation:\n%s", svg_bytes)
        return self._rasterise(svg_bytes.encode("utf-8"))

    def render_bytes(
        self,
        *,
        output_format: str = "jpeg",
        background: str | None = None,
        quality: int = 90,
    ) -> bytes:
        """Rasterise the SVG directly to encoded image bytes.

        This is the SVG-native pipeline entry point.  It applies
        bindings, optionally injects a background colour, sets the
        target dimensions, and rasterises to the requested format in
        a single pass — no intermediate PIL Image.

        Parameters
        ----------
        output_format : str, default="jpeg"
            Target image format: ``"jpeg"``, ``"bmp"``, or ``"png"``.
        background : str or None, optional
            CSS colour for a solid background rect injected under all
            content.  When ``None``, no background is injected (the
            SVG's own background or transparency is preserved).
        quality : int, default=90
            JPEG quality (ignored for other formats).

        Returns
        -------
        bytes
            Encoded image bytes ready to send to the device.
        """
        from ..render.svg_rasterize import (
            _rasterize_svg,
            inject_background_rect,
            set_svg_dimensions,
        )

        root = copy.deepcopy(self._base_root)

        for name, binding in self._spec.bindings.items():
            value = self._values.get(name)
            self._apply_binding(root, name, binding, value)

        self._inline_assets(root)
        self._hide_spinner_node(root)

        if background is not None:
            inject_background_rect(root, background)

        # Determine rasterisation dimensions.
        if self._target_width is not None and self._target_height is not None:
            width = self._target_width
            height = self._target_height
        else:
            width = int(float(root.get("width", "197")))
            height = int(float(root.get("height", "98")))

        set_svg_dimensions(root, width, height)

        svg_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
        return _rasterize_svg(
            svg_bytes.encode("utf-8"),
            width,
            height,
            output_format=output_format,
            quality=quality,
            ctx=self._rendering_ctx,
        )

    def render_svg(self) -> str:
        """Return the SVG source with current bindings applied (not rasterised).

        This is used by the spinner system to generate frames that
        reflect the current binding state rather than the raw template.

        Returns
        -------
        str
            SVG markup as a Unicode string.
        """
        root = copy.deepcopy(self._base_root)

        for name, binding in self._spec.bindings.items():
            value = self._values.get(name)
            self._apply_binding(root, name, binding, value)

        self._inline_assets(root)
        self._hide_spinner_node(root)

        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def _hide_spinner_node(self, root: ET.Element) -> None:
        """Hide the spinner and its background node so they are invisible at rest.

        DUI package authors may not set ``display="none"`` on the spinner
        element or its background, which would make them visible in every
        non-busy render.  This method forces both nodes hidden; the spinner
        frame generators remove ``display="none"`` when producing animation
        frames.

        Parameters
        ----------
        root
            The parsed SVG element tree (will be mutated in place).
        """
        spinner = self._spec.spinner
        if spinner is not None and spinner.node is not None:
            elem = _find_element_by_id(root, spinner.node)
            if elem is not None:
                elem.set("display", "none")
        if spinner is not None and spinner.background_node is not None:
            bg_elem = _find_element_by_id(root, spinner.background_node)
            if bg_elem is not None:
                bg_elem.set("display", "none")

    #: Dispatch table mapping binding types to handler methods.
    #: Each handler is called with (root, elem, name, binding, value).
    #: To support a new binding type, register it here without modifying
    #: ``_apply_binding`` itself.
    _BINDING_HANDLERS: ClassVar[
        dict[type[Binding], Callable[[SvgRenderer, ET.Element, ET.Element, str, Any, Any], None]]
    ] = {}

    @staticmethod
    def _register_binding_handler(
        binding_type: type[Binding],
    ) -> Callable[
        [Callable[[SvgRenderer, ET.Element, ET.Element, str, Any, Any], None]],
        Callable[[SvgRenderer, ET.Element, ET.Element, str, Any, Any], None],
    ]:
        """Decorator to register a binding handler in the dispatch table.

        Parameters
        ----------
        binding_type : type[Binding]
            The binding class this handler processes.

        Returns
        -------
        Callable
            The decorator that registers the handler.
        """

        def decorator(
            func: Callable[[SvgRenderer, ET.Element, ET.Element, str, Any, Any], None],
        ) -> Callable[[SvgRenderer, ET.Element, ET.Element, str, Any, Any], None]:
            SvgRenderer._BINDING_HANDLERS[binding_type] = func
            return func

        return decorator

    def _apply_binding(
        self,
        root: ET.Element,
        name: str,
        binding: Binding,
        value: Any,
    ) -> None:
        """Apply a single binding to the SVG tree.

        Uses a dispatch table to route each binding type to its handler,
        allowing new binding types to be added without modifying this method.
        """
        if isinstance(binding, ToggleBinding):
            elem_on = _find_element_by_id(root, binding.node_on)
            elem_off = _find_element_by_id(root, binding.node_off)
            if elem_on is None:
                logger.warning(
                    "Binding '%s': node_on '%s' not found in SVG",
                    name,
                    binding.node_on,
                )
            if elem_off is None:
                logger.warning(
                    "Binding '%s': node_off '%s' not found in SVG",
                    name,
                    binding.node_off,
                )
            self._apply_toggle(elem_on, elem_off, value)
            return

        elem = _find_element_by_id(root, binding.node)
        if elem is None:
            logger.warning(
                "Binding '%s': node '%s' not found in SVG", name, binding.node
            )
            return

        handler = self._BINDING_HANDLERS.get(type(binding))
        if handler is not None:
            handler(self, root, elem, name, binding, value)
        else:
            logger.warning(
                "Binding '%s': no handler registered for type '%s'",
                name,
                type(binding).__name__,
            )

    def _apply_text(
        self,
        root: ET.Element,
        elem: ET.Element,
        binding: TextBinding,
        value: Any,
    ) -> None:
        """Set text content, applying wrapping or truncation if configured.

        Parameters
        ----------
        root : ET.Element
            The SVG document root (needed for font resolution during wrapping).
        elem : ET.Element
            The ``<text>`` element whose content is being set.
        binding : TextBinding
            The text binding definition from the manifest.
        value : Any
            The text value to render; coerced to ``str``.
        """
        text = str(value) if value is not None else binding.default

        if binding.wrap and binding.max_width is not None:
            self._apply_wrapped_text(root, elem, binding, text)
            return

        if binding.max_width is not None:
            family, size_f = _resolve_font_attrs(root, elem)
            font = _load_font(family, int(size_f))
            text = _truncate_text(text, binding.max_width, binding.overflow, font=font)
        elem.text = text

    def _apply_wrapped_text(
        self,
        root: ET.Element,
        elem: ET.Element,
        binding: TextBinding,
        text: str,
    ) -> None:
        """Word-wrap text into ``<tspan>`` children of *elem*.

        Each ``<tspan>`` carries the parent ``<text>`` element's ``x``
        attribute so that ``text-anchor`` alignment is respected on
        every line.
        """
        family, size_f = _resolve_font_attrs(root, elem)
        font = _load_font(family, int(size_f))

        line_height = binding.line_height or (size_f * _DEFAULT_LINE_HEIGHT_RATIO)

        lines = _wrap_text(
            text,
            binding.max_width,  # type: ignore[arg-type]  # validated non-None
            font,
            binding.overflow,
            max_height=binding.max_height,
            line_height=line_height,
        )

        elem.text = None
        for child in list(elem):
            elem.remove(child)

        x_attr = elem.get("x", "0")

        for i, line in enumerate(lines):
            tspan = ET.SubElement(elem, f"{{{_SVG_NS}}}tspan")
            tspan.set("x", x_attr)
            tspan.set("dy", "0" if i == 0 else str(line_height))
            tspan.text = line

    def _apply_image(
        self,
        root: ET.Element,
        elem: ET.Element,
        binding: ImageBinding,
        value: Any,
    ) -> None:
        """Set an image element's href to a data URI.

        Parameters
        ----------
        root : ET.Element
            The SVG document root (used to locate placeholder nodes).
        elem : ET.Element
            The ``<image>`` element to update.
        binding : ImageBinding
            The image binding definition from the manifest.
        value : Any
            A ``PIL.Image.Image``, ``bytes``, or ``None`` to clear the image.
        """
        if value is None:
            elem.set("href", "")
            elem.set("display", "none")
            if binding.placeholder_node:
                placeholder = _find_element_by_id(root, binding.placeholder_node)
                if placeholder is not None:
                    placeholder.attrib.pop("display", None)
            return

        elem.attrib.pop("display", None)
        if binding.placeholder_node:
            placeholder = _find_element_by_id(root, binding.placeholder_node)
            if placeholder is not None:
                placeholder.set("display", "none")

        target_w = int(float(elem.get("width", "0")))
        target_h = int(float(elem.get("height", "0")))

        if isinstance(value, Image.Image):
            img = value
        elif isinstance(value, bytes):
            img = Image.open(io.BytesIO(value))
        else:
            logger.warning("Image binding: unsupported value type %s", type(value))
            return

        if img.mode != "RGBA":
            img = img.convert("RGBA")

        if target_w > 0 and target_h > 0:
            img = _fit_image(img, target_w, target_h, binding.fit)

        data_uri = _image_to_data_uri(img)
        elem.set("href", data_uri)
        elem.set(f"{{{_XLINK_NS}}}href", data_uri)

    def _apply_visibility(self, elem: ET.Element, value: Any) -> None:
        """Toggle element visibility via the ``display`` attribute.

        Parameters
        ----------
        elem : ET.Element
            The SVG element to show or hide.
        value : Any
            Truthy to show, falsy to hide (sets ``display="none"``).
        """
        if value:
            elem.attrib.pop("display", None)
        else:
            elem.set("display", "none")

    def _apply_css_class(self, elem: ET.Element, value: Any) -> None:
        """Set or remove the ``class`` attribute on an SVG element.

        Parameters
        ----------
        elem : ET.Element
            The SVG element to update.
        value : Any
            A string class value.  Non-empty strings are set as the
            ``class`` attribute; empty or ``None`` removes it.
        """
        class_str = str(value) if value else ""
        if class_str:
            elem.set("class", class_str)
        else:
            elem.attrib.pop("class", None)

    def _apply_toggle(
        self,
        elem_on: ET.Element | None,
        elem_off: ET.Element | None,
        value: Any,
    ) -> None:
        """Toggle visibility between two elements based on a boolean value.

        Parameters
        ----------
        elem_on : ET.Element | None
            The element shown when *value* is truthy.
        elem_off : ET.Element | None
            The element shown when *value* is falsy.
        value : Any
            Boolean-like value controlling which element is visible.
        """
        if value:
            if elem_on is not None:
                elem_on.attrib.pop("display", None)
            if elem_off is not None:
                elem_off.set("display", "none")
        else:
            if elem_off is not None:
                elem_off.attrib.pop("display", None)
            if elem_on is not None:
                elem_on.set("display", "none")

    def _apply_color(self, elem: ET.Element, binding: ColorBinding, value: Any) -> None:
        """Set an element's fill, stroke, or color attribute.

        Parameters
        ----------
        elem : ET.Element
            The SVG element to modify.
        binding : ColorBinding
            The color binding definition specifying the target attribute.
        value : Any
            CSS color string (e.g. ``"#ff0000"``); falls back to *binding.default*.
        """
        color_val = str(value) if value is not None else binding.default
        elem.set(binding.attribute, color_val)

    def _apply_range(
        self,
        elem: ET.Element,
        name: str,
        binding: RangeBinding,
        value: Any,
    ) -> None:
        """Scale an element's width or height proportional to a 0--1 value.

        Parameters
        ----------
        elem : ET.Element
            The SVG element whose dimension is being scaled.
        name : str
            Binding name, used to look up the cached original extent.
        binding : RangeBinding
            The range binding definition from the manifest.
        value : Any
            A float in ``[0.0, 1.0]``; clamped if out of range.
        """
        ratio = max(
            0.0, min(1.0, float(value if value is not None else binding.default))
        )
        extent = self._range_extents.get(name, 0.0)
        attr = "width" if binding.direction == RangeDirection.HORIZONTAL else "height"
        elem.set(attr, str(ratio * extent))

    def _apply_slider(
        self,
        elem: ET.Element,
        binding: SliderBinding,
        value: Any,
    ) -> None:
        """Translate an element's x or y between *min_pos* and *max_pos*.

        Parameters
        ----------
        elem : ET.Element
            The SVG element to reposition.
        binding : SliderBinding
            The slider binding definition containing position limits.
        value : Any
            A float in ``[0.0, 1.0]`` interpolated between *min_pos* and *max_pos*.
        """
        ratio = max(
            0.0, min(1.0, float(value if value is not None else binding.default))
        )
        pos = binding.min_pos + ratio * (binding.max_pos - binding.min_pos)
        attr = "x" if binding.direction == RangeDirection.HORIZONTAL else "y"
        elem.set(attr, str(pos))

    def _apply_transform(
        self,
        elem: ET.Element,
        binding: TransformBinding,
        value: Any,
    ) -> None:
        """Apply composed SVG transforms to an element proportional to a 0–1 value.

        Parameters
        ----------
        elem : ET.Element
            The SVG element to transform.
        binding : TransformBinding
            The transform binding definition from the manifest.
        value : Any
            A float in ``[0.0, 1.0]``; clamped if out of range.
        """
        ratio = max(
            0.0, min(1.0, float(value if value is not None else binding.default))
        )

        parts: list[str] = []
        for spec in binding.transforms:
            if isinstance(spec, RotateTransform):
                angle = spec.from_angle + (spec.to_angle - spec.from_angle) * ratio
                cx, cy = self._resolve_transform_origin(elem, spec.origin)
                parts.append(f"rotate({angle:.4g},{cx:.4g},{cy:.4g})")

        if parts:
            elem.set("transform", " ".join(parts))

    @staticmethod
    def _resolve_transform_origin(
        elem: ET.Element, origin: str
    ) -> tuple[float, float]:
        """Resolve a transform origin string to x, y coordinates.

        Parameters
        ----------
        elem : ET.Element
            The target SVG element (used for ``"center"`` resolution).
        origin : str
            Either ``"center"`` (computes from element geometry) or an
            explicit ``"x y"`` coordinate pair.

        Returns
        -------
        tuple[float, float]
            The resolved (cx, cy) origin coordinates.
        """
        if origin == "center":
            x = float(elem.get("x", "0"))
            y = float(elem.get("y", "0"))
            w = float(elem.get("width", "0"))
            h = float(elem.get("height", "0"))
            return (x + w / 2.0, y + h / 2.0)

        # Explicit "x y" format.
        parts = origin.split()
        if len(parts) == 2:
            try:
                return (float(parts[0]), float(parts[1]))
            except ValueError:
                pass
        # Fallback to 0,0 if unparseable.
        return (0.0, 0.0)

    def _apply_iconify(
        self,
        elem: ET.Element,
        binding: IconifyBinding,
        value: Any,
    ) -> None:
        """Load an Iconify icon by name and embed it into a ``<g>`` node.

        The existing children of *elem* are replaced by a single
        ``<svg>`` child that contains the icon.  Passing ``None`` or an
        empty string clears the group.
        """
        elem.text = None
        for child in list(elem):
            elem.remove(child)

        if value is None or value == "":
            return
        name = str(value)

        try:
            svg_source = fetch_icon(str(name))
        except IconifyError as exc:
            logger.warning("Iconify binding '%s': %s", binding.node, exc)
            return

        try:
            icon_root = safe_fromstring(svg_source)  # untrusted: network (Iconify)
        except Exception as exc:
            logger.warning(
                "Iconify binding '%s': failed to parse icon SVG: %s",
                binding.node,
                exc,
            )
            return

        size = str(binding.size)
        icon_root.set("width", size)
        icon_root.set("height", size)

        elem.append(icon_root)

    def _apply_list(
        self,
        root: ET.Element,
        elem: ET.Element,
        binding: ListBinding,
        value: Any,
    ) -> None:
        """Render a list of items as repeated child elements.

        Each item becomes a ``<child_tag>`` child of *elem*.  The item
        at *index* receives *active_attrs*; all others receive
        *inactive_attrs*.  An index of ``None`` (or ``-1``, normalised
        earlier) means every item is styled as inactive.

        Items prefixed with ``icon:`` are rendered as inline Iconify
        icons via :meth:`_apply_list_icon`.

        Parameters
        ----------
        root : ET.Element
            The SVG document root (needed for font resolution on icon
            items).
        elem : ET.Element
            The parent SVG element whose children are rebuilt.
        binding : ListBinding
            The list binding definition from the manifest.
        value : Any
            A dict with ``"items"`` (list of str) and ``"index"``
            (int or None).
        """
        if not isinstance(value, dict):
            value = {"items": list(binding.default_items), "index": binding.default_index}

        items: list[str] = value.get("items", [])
        index: int | None = value.get("index")
        if index == -1:
            index = None

        # Clear existing children.
        elem.text = None
        for child in list(elem):
            elem.remove(child)

        for i, item in enumerate(items):
            # Separator between items.
            if binding.separator and i > 0:
                sep = ET.SubElement(elem, f"{{{_SVG_NS}}}{binding.child_tag}")
                sep.text = binding.separator
                for attr_k, attr_v in binding.inactive_attrs.items():
                    sep.set(attr_k, attr_v)

            is_active = index is not None and i == index
            attrs = binding.active_attrs if is_active else binding.inactive_attrs

            if item.startswith("icon:"):
                self._apply_list_icon(elem, binding, item[5:], attrs)
            else:
                child_elem = ET.SubElement(elem, f"{{{_SVG_NS}}}{binding.child_tag}")
                child_elem.text = item
                for attr_k, attr_v in attrs.items():
                    child_elem.set(attr_k, attr_v)

    def _apply_list_icon(
        self,
        parent: ET.Element,
        binding: ListBinding,
        icon_name: str,
        attrs: dict[str, str],
    ) -> None:
        """Render a single Iconify icon as a child of *parent*.

        Fetches the icon SVG via the Iconify API, wraps it in a
        ``<child_tag>`` element, and applies the given attributes.

        Parameters
        ----------
        parent : ET.Element
            The parent SVG element to append the icon child to.
        binding : ListBinding
            The list binding definition (provides ``child_tag`` and
            ``icon_size``).
        icon_name : str
            Iconify icon identifier (e.g. ``"mdi:home"``).
        attrs : dict[str, str]
            SVG attributes to apply to the wrapper element.
        """
        try:
            svg_source = fetch_icon(icon_name)
        except IconifyError as exc:
            logger.warning("List binding icon '%s': %s", icon_name, exc)
            return

        try:
            icon_root = safe_fromstring(svg_source)  # untrusted: network (Iconify)
        except Exception as exc:
            logger.warning(
                "List binding icon '%s': failed to parse SVG: %s", icon_name, exc
            )
            return

        size = str(binding.icon_size)
        icon_root.set("width", size)
        icon_root.set("height", size)

        wrapper = ET.SubElement(parent, f"{{{_SVG_NS}}}{binding.child_tag}")
        for attr_k, attr_v in attrs.items():
            wrapper.set(attr_k, attr_v)
        wrapper.append(icon_root)

    def _inline_assets(self, root: ET.Element) -> None:
        """Replace relative asset ``href`` references with data URIs.

        Parameters
        ----------
        root : ET.Element
            The SVG document root to scan for asset references.
        """
        if not self._spec.assets:
            return

        for elem in root.iter():
            href = elem.get("href") or elem.get(f"{{{_XLINK_NS}}}href")
            if not href:
                continue

            asset_name: str | None = None
            if href.startswith("assets/"):
                asset_name = href[len("assets/") :]
            elif "/" not in href and href in self._spec.assets:
                asset_name = href

            if asset_name and asset_name in self._spec.assets:
                img = Image.open(io.BytesIO(self._spec.assets[asset_name]))
                data_uri = _image_to_data_uri(img)
                elem.set("href", data_uri)
                elem.set(f"{{{_XLINK_NS}}}href", data_uri)

    def _rasterise(self, svg_data: bytes) -> Image.Image:
        """Rasterise SVG bytes to a PIL Image.

        The image is returned in RGBA mode so that transparent regions
        in the SVG are preserved.  This allows compositing onto a
        background tile when a touchstrip background SVG is active.

        When target dimensions have been set via :meth:`set_target_size`,
        the SVG is rasterised at those dimensions (vector scaling by the
        rasteriser backend).  Otherwise the SVG's intrinsic ``width`` and
        ``height`` attributes are used.

        Parameters
        ----------
        svg_data : bytes
            UTF-8 encoded SVG markup.

        Returns
        -------
        Image.Image
            An RGBA :class:`~PIL.Image.Image`.
        """
        from ..render.svg_rasterize import _svg_to_png

        if self._target_width is not None and self._target_height is not None:
            width = self._target_width
            height = self._target_height
        else:
            width = int(float(self._base_root.get("width", "197")))
            height = int(float(self._base_root.get("height", "98")))

        png_data = _svg_to_png(svg_data, width, height, ctx=self._rendering_ctx)
        return Image.open(io.BytesIO(png_data)).convert("RGBA")


# ---------------------------------------------------------------------------
# Binding handler registrations
# ---------------------------------------------------------------------------


@SvgRenderer._register_binding_handler(TextBinding)
def _handle_text(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_text(root, elem, binding, value)


@SvgRenderer._register_binding_handler(ImageBinding)
def _handle_image(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_image(root, elem, binding, value)


@SvgRenderer._register_binding_handler(VisibilityBinding)
def _handle_visibility(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_visibility(elem, value)


@SvgRenderer._register_binding_handler(ColorBinding)
def _handle_color(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_color(elem, binding, value)


@SvgRenderer._register_binding_handler(RangeBinding)
def _handle_range(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_range(elem, name, binding, value)


@SvgRenderer._register_binding_handler(SliderBinding)
def _handle_slider(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_slider(elem, binding, value)


@SvgRenderer._register_binding_handler(IconifyBinding)
def _handle_iconify(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_iconify(elem, binding, value)


@SvgRenderer._register_binding_handler(ListBinding)
def _handle_list(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_list(root, elem, binding, value)


@SvgRenderer._register_binding_handler(TransformBinding)
def _handle_transform(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_transform(elem, binding, value)


@SvgRenderer._register_binding_handler(CssClassBinding)
def _handle_css_class(
    self: SvgRenderer, root: ET.Element, elem: ET.Element, name: str, binding: Any, value: Any
) -> None:
    self._apply_css_class(elem, value)
