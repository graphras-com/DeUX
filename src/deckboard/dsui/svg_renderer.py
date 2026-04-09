"""SVG-to-PIL rendering engine for .dsui packages."""

from __future__ import annotations

import base64
import copy
import io
import logging
import xml.etree.ElementTree as ET
from typing import Any

from PIL import Image

from .schema import (
    Binding,
    ColorBinding,
    ImageBinding,
    ImageFit,
    OverflowMode,
    PackageSpec,
    TextBinding,
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
        return img.resize((target_w, target_h), Image.LANCZOS)

    if fit == ImageFit.CONTAIN:
        ratio = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * ratio))
        new_h = max(1, int(src_h * ratio))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        paste_x = (target_w - new_w) // 2
        paste_y = (target_h - new_h) // 2
        canvas.paste(resized, (paste_x, paste_y))
        return canvas

    # ImageFit.COVER — scale up so image covers target, then center-crop
    ratio = max(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * ratio))
    new_h = max(1, int(src_h * ratio))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
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


class SvgRenderer:
    """Render a .dsui SVG layout with live data bindings.

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

        # Initialise defaults from bindings
        for name, binding in spec.bindings.items():
            if isinstance(binding, TextBinding):
                self._values[name] = binding.default
            elif isinstance(binding, VisibilityBinding):
                self._values[name] = binding.default
            elif isinstance(binding, ColorBinding):
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
        elem = _find_element_by_id(root, binding.node)
        if elem is None:
            logger.warning(
                "Binding '%s': node '%s' not found in SVG", name, binding.node
            )
            return

        if isinstance(binding, TextBinding):
            self._apply_text(elem, binding, value)
        elif isinstance(binding, ImageBinding):
            self._apply_image(root, elem, binding, value)
        elif isinstance(binding, VisibilityBinding):
            self._apply_visibility(elem, value)
        elif isinstance(binding, ColorBinding):
            self._apply_color(elem, binding, value)

    def _apply_text(self, elem: ET.Element, binding: TextBinding, value: Any) -> None:
        """Set text content, applying truncation if configured."""
        text = str(value) if value is not None else binding.default
        if binding.max_width is not None:
            text = _truncate_text(text, binding.max_width, binding.overflow)
        elem.text = text

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

    def _apply_color(self, elem: ET.Element, binding: ColorBinding, value: Any) -> None:
        """Set an element's fill or stroke colour."""
        color_val = str(value) if value is not None else binding.default
        elem.set(binding.attribute, color_val)

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
        from ..render.icons import _svg_to_png

        # Read target dimensions from the SVG root
        width = int(float(self._base_root.get("width", "197")))
        height = int(float(self._base_root.get("height", "98")))

        png_data = _svg_to_png(svg_data, width, height)
        return Image.open(io.BytesIO(png_data)).convert("RGB")
