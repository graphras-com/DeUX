"""SVG-to-PIL rendering engine for .dui packages."""

from __future__ import annotations

import base64
import copy
import functools
import io
import logging
import math
import xml.etree.ElementTree as ET
from contextlib import suppress
from typing import Any

from PIL import Image, ImageFont

from .iconify import IconifyError, fetch_icon
from .schema import (
    Binding,
    ColorBinding,
    IconifyBinding,
    ImageBinding,
    ImageFit,
    OverflowMode,
    PackageSpec,
    RangeBinding,
    RangeDirection,
    SliderBinding,
    TextBinding,
    ToggleBinding,
    VisibilityBinding,
)

logger = logging.getLogger(__name__)

# SVG namespace — ElementTree requires explicit namespace handling
_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK_NS = "http://www.w3.org/1999/xlink"

# Register namespaces so output uses short prefixes
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

    # ImageFit.COVER — scale up so image covers target, then center-crop
    ratio = max(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * ratio))
    new_h = max(1, int(src_h * ratio))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _truncate_text(text: str, max_width: int, overflow: OverflowMode) -> str:
    """Truncate text to approximate a pixel max_width.

    Uses a simple character-width heuristic (0.6 * font-size per char)
    since we cannot measure the exact rendered width before CairoSVG
    rasterises.  The SVG font-size is not available here, so we use
    the max_width as a rough character limit with an average ratio.
    """
    if overflow == OverflowMode.CLIP:
        return text

    # Rough estimate: assume average char width ~ 0.55 * font-size.
    # Since we don't know font-size here, treat max_width as a
    # generous pixel budget.  For typical 10-20px fonts on a 197px
    # panel, max_width=90 ≈ ~12-15 chars.  We use a conservative
    # 7px average char width for the estimation.
    avg_char_width = 7
    max_chars = max(1, max_width // avg_char_width)

    if len(text) <= max_chars:
        return text

    return text[: max(1, max_chars - 1)] + "\u2026"  # ellipsis character


# ---------------------------------------------------------------------------
# Font resolution and text wrapping
# ---------------------------------------------------------------------------

_DEFAULT_FONT_FAMILY = "sans-serif"
_DEFAULT_FONT_SIZE = 16.0
_DEFAULT_LINE_HEIGHT_RATIO = 1.2


def _resolve_font_attrs(root: ET.Element, elem: ET.Element) -> tuple[str, float]:
    """Resolve font-family and font-size from an SVG element and its ancestors.

    Walks from *elem* up through the SVG tree to find ``font-family``
    and ``font-size`` attributes.  Falls back to sensible defaults if
    neither the element nor any ancestor declares them.

    Returns:
        A ``(font_family, font_size)`` tuple.
    """
    family: str | None = None
    size: float | None = None

    # Build a parent map so we can walk upward
    parent_map: dict[ET.Element, ET.Element] = {}
    for parent in root.iter():
        for child in parent:
            parent_map[child] = parent

    # Walk from elem upward
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
        family or _DEFAULT_FONT_FAMILY,
        size or _DEFAULT_FONT_SIZE,
    )


@functools.lru_cache(maxsize=32)
def _load_font(family: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font by family name and size, with fallbacks.

    Tries several name variations.  If all fail, logs a warning and
    returns Pillow's built-in default font.  Results are cached.

    Args:
        family: Font family name (e.g. ``"ArialMT"``).
        size: Font size in pixels (integer for cache-key hashability).
    """
    # Build candidate names: original, stripped suffixes, lowercase
    candidates: list[str] = [family]
    for suffix in ("MT", "Bold", "Italic", "-Regular", "-Bold"):
        if family.endswith(suffix):
            candidates.append(family[: -len(suffix)])
    candidates.append(family.lower())
    # Deduplicate while preserving order
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

    Args:
        text: The text string to wrap.
        max_width: Maximum line width in pixels.
        font: A Pillow font object for measurement.
        overflow: How to handle text that doesn't fit.
        max_height: Optional vertical pixel budget.
        line_height: Vertical spacing between lines in pixels.

    Returns:
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

    # Apply max_height constraint
    if max_height is not None and line_height > 0:
        max_lines = max(1, math.floor(max_height / line_height))
        if len(lines) > max_lines:
            # Truncate to max_lines; handle last-line overflow
            lines = lines[:max_lines]
            if overflow == OverflowMode.ELLIPSIS:
                last = lines[-1]
                # Re-join remaining text that was cut off is implicit
                # — we just need to mark the last line with ellipsis
                ellipsis = "\u2026"
                if font.getlength(last + ellipsis) > max_width:
                    # Trim characters until it fits
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

    Args:
        spec: The validated package specification.
    """

    def __init__(self, spec: PackageSpec) -> None:
        self._spec = spec
        self._values: dict[str, Any] = {}
        self._base_root: ET.Element = ET.fromstring(spec.svg_source)  # noqa: S314
        self._range_extents: dict[str, float] = {}

        # Initialise defaults from bindings
        for name, binding in spec.bindings.items():
            if isinstance(binding, (TextBinding, VisibilityBinding, ColorBinding)):
                self._values[name] = binding.default
            elif isinstance(binding, RangeBinding):
                self._values[name] = binding.default
                # Cache the original extent from the SVG template
                elem = _find_element_by_id(self._base_root, binding.node)
                if elem is not None:
                    attr = (
                        "width"
                        if binding.direction == RangeDirection.HORIZONTAL
                        else "height"
                    )
                    self._range_extents[name] = float(elem.get(attr, "0"))
            elif isinstance(binding, (SliderBinding, ToggleBinding, IconifyBinding)):
                self._values[name] = binding.default
            # ImageBinding defaults to None (no image)

    def set(self, name: str, value: Any) -> bool:
        """Set a binding value.

        Args:
            name: Binding name as defined in the manifest.
            value: The new value.  Type depends on the binding:
                   text → ``str``, image → ``PIL.Image.Image`` or ``bytes``,
                   visibility → ``bool``, color → ``str``.

        Returns:
            ``True`` if the value actually changed (triggers dirty flag).

        Raises:
            KeyError: If *name* is not a known binding.
        """
        if name not in self._spec.bindings:
            raise KeyError(
                f"Unknown binding '{name}'. Available: {sorted(self._spec.bindings)}"
            )

        old = self._values.get(name)
        # For images, always consider it changed (identity comparison is unreliable)
        binding = self._spec.bindings[name]
        if isinstance(binding, ImageBinding):
            self._values[name] = value
            return True

        if old == value:
            return False

        self._values[name] = value
        return True

    def set_many(self, **kwargs: Any) -> bool:
        """Set multiple binding values at once.

        Returns:
            ``True`` if any value changed.
        """
        changed = False
        for name, value in kwargs.items():
            if self.set(name, value):
                changed = True
        return changed

    def get(self, name: str) -> Any:
        """Get the current value of a binding.

        Raises:
            KeyError: If *name* is not a known binding.
        """
        if name not in self._spec.bindings:
            raise KeyError(
                f"Unknown binding '{name}'. Available: {sorted(self._spec.bindings)}"
            )
        return self._values.get(name)

    def render(self) -> Image.Image:
        """Rasterise the SVG with current binding values to a PIL Image.

        Returns:
            An RGB :class:`~PIL.Image.Image` at the SVG's native dimensions.
        """
        root = copy.deepcopy(self._base_root)

        for name, binding in self._spec.bindings.items():
            value = self._values.get(name)
            self._apply_binding(root, name, binding, value)

        # Inline any asset references that use relative paths
        self._inline_assets(root)

        # Serialise and rasterise
        svg_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
        return self._rasterise(svg_bytes.encode("utf-8"))

    def _apply_binding(
        self,
        root: ET.Element,
        name: str,
        binding: Binding,
        value: Any,
    ) -> None:
        """Apply a single binding to the SVG tree."""
        # Toggle bindings address two nodes instead of one.
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

        if isinstance(binding, TextBinding):
            self._apply_text(root, elem, binding, value)
        elif isinstance(binding, ImageBinding):
            self._apply_image(root, elem, binding, value)
        elif isinstance(binding, VisibilityBinding):
            self._apply_visibility(elem, value)
        elif isinstance(binding, ColorBinding):
            self._apply_color(elem, binding, value)
        elif isinstance(binding, RangeBinding):
            self._apply_range(elem, name, binding, value)
        elif isinstance(binding, SliderBinding):
            self._apply_slider(elem, binding, value)
        elif isinstance(binding, IconifyBinding):
            self._apply_iconify(elem, binding, value)

    def _apply_text(
        self,
        root: ET.Element,
        elem: ET.Element,
        binding: TextBinding,
        value: Any,
    ) -> None:
        """Set text content, applying wrapping or truncation if configured."""
        text = str(value) if value is not None else binding.default

        if binding.wrap and binding.max_width is not None:
            self._apply_wrapped_text(root, elem, binding, text)
            return

        if binding.max_width is not None:
            text = _truncate_text(text, binding.max_width, binding.overflow)
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
        # Resolve font from the SVG tree
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

        # Clear existing content and children
        elem.text = None
        for child in list(elem):
            elem.remove(child)

        # Inherit x from the parent <text> so text-anchor is respected
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
        """Set an image element's href to a data URI."""
        if value is None:
            # No image — hide this element, show placeholder if configured
            elem.set("href", "")
            elem.set("display", "none")
            if binding.placeholder_node:
                placeholder = _find_element_by_id(root, binding.placeholder_node)
                if placeholder is not None:
                    placeholder.attrib.pop("display", None)
            return

        # We have an image — show it, hide placeholder
        elem.attrib.pop("display", None)
        if binding.placeholder_node:
            placeholder = _find_element_by_id(root, binding.placeholder_node)
            if placeholder is not None:
                placeholder.set("display", "none")

        # Get target dimensions from the SVG element
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
        # Also set xlink:href for compatibility
        elem.set(f"{{{_XLINK_NS}}}href", data_uri)

    def _apply_visibility(self, elem: ET.Element, value: Any) -> None:
        """Toggle element visibility via the display attribute."""
        if value:
            elem.attrib.pop("display", None)
        else:
            elem.set("display", "none")

    def _apply_toggle(
        self,
        elem_on: ET.Element | None,
        elem_off: ET.Element | None,
        value: Any,
    ) -> None:
        """Toggle visibility between two elements based on a boolean value."""
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
        """Set an element's fill, stroke, or color attribute."""
        color_val = str(value) if value is not None else binding.default
        elem.set(binding.attribute, color_val)

    def _apply_range(
        self,
        elem: ET.Element,
        name: str,
        binding: RangeBinding,
        value: Any,
    ) -> None:
        """Scale an element's width or height proportional to a 0–1 value."""
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
        """Translate an element's x or y between min_pos and max_pos."""
        ratio = max(
            0.0, min(1.0, float(value if value is not None else binding.default))
        )
        pos = binding.min_pos + ratio * (binding.max_pos - binding.min_pos)
        attr = "x" if binding.direction == RangeDirection.HORIZONTAL else "y"
        elem.set(attr, str(pos))

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
        # Always clear existing content — either we replace it with the
        # new icon, or we leave the group empty.
        elem.text = None
        for child in list(elem):
            elem.remove(child)

        # ``None`` and empty string both clear the group.  The binding's
        # default is applied at construction time via ``_values`` and is
        # not re-used here so users can explicitly unset the icon.
        if value is None or value == "":
            return
        name = str(value)

        try:
            svg_source = fetch_icon(str(name))
        except IconifyError as exc:
            logger.warning("Iconify binding '%s': %s", binding.node, exc)
            return

        try:
            icon_root = ET.fromstring(svg_source)  # noqa: S314 — trusted API
        except ET.ParseError as exc:
            logger.warning(
                "Iconify binding '%s': failed to parse icon SVG: %s",
                binding.node,
                exc,
            )
            return

        # Force the embedded icon to our requested pixel size.  The
        # original viewBox is preserved, so the icon scales uniformly.
        size = str(binding.size)
        icon_root.set("width", size)
        icon_root.set("height", size)

        elem.append(icon_root)

    def _inline_assets(self, root: ET.Element) -> None:
        """Replace relative asset href references with data URIs."""
        if not self._spec.assets:
            return

        for elem in root.iter():
            href = elem.get("href") or elem.get(f"{{{_XLINK_NS}}}href")
            if not href:
                continue

            # Check if href matches an asset path like "assets/foo.png"
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
        """Rasterise SVG bytes to a PIL Image via CairoSVG."""
        from ..render.svg_rasterize import _svg_to_png

        # Read target dimensions from the SVG root
        width = int(float(self._base_root.get("width", "197")))
        height = int(float(self._base_root.get("height", "98")))

        png_data = _svg_to_png(svg_data, width, height)
        return Image.open(io.BytesIO(png_data)).convert("RGB")
