"""Library-owned spinner frame generation for busy-state animations.

The spinner is a fixed 8-frame, 360°-rotation animation rendered into
a caller-provided placeholder ``<g id="...">`` element in a package's
layout SVG.  All geometry (background tile + 8 radial bars) is owned
by the library; package authors only choose where the placeholder is
positioned via its own ``transform`` attribute.

Frames are cached process-wide in an LRU keyed by
``(rendered_svg, spinner_node_id, width, height, image_format,
bg_signature)`` so that repeated busy cycles on the same panel reuse
the same frame bytes.
"""

from __future__ import annotations

import copy
import hashlib
import io
import logging
import xml.etree.ElementTree as ET
from collections import OrderedDict
from typing import TYPE_CHECKING

from PIL import Image

from .._xml import safe_fromstring
from .svg_renderer import _find_element_by_id

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_SVG_NS = "http://www.w3.org/2000/svg"

#: Number of frames in the canonical spinner animation (one per 45°).
SPINNER_FRAME_COUNT: int = 8

#: Milliseconds between frames in the canonical spinner animation.
SPINNER_INTERVAL_MS: int = 100

#: Maximum number of frame-lists held in the process-wide LRU cache.
_CACHE_MAX_ENTRIES: int = 64

#: Canonical spinner content as an SVG group fragment.  Coordinates are
#: centred around (0, 0) so the placeholder's ``transform`` attribute
#: positions it.  One bar is tinted ``#dedede`` (the "head" of the
#: rotation); the remaining seven are ``#5c5b5b``.  An opaque rounded
#: rectangle behind the bars provides contrast against arbitrary panel
#: backgrounds.
_SPINNER_TEMPLATE_SVG: str = (
    f'<g xmlns="{_SVG_NS}">'
    '<rect color="#1c1c1c" x="-27.5" y="-27.5" width="55" height="55" '
    'rx="4" ry="4" fill="currentColor" fill-opacity="0.8" stroke="none"/>'
    '<g class="deux-spinner-rotor" transform="rotate({angle})">'
    f'<svg xmlns="{_SVG_NS}" color="#5c5b5b" x="-24" y="-24" '
    'width="48" height="48" viewBox="0 0 48 48" fill="none">'
    '<rect color="#dedede" x="22" width="4" height="12" rx="2" fill="currentColor"/>'
    '<rect x="22" y="36" width="4" height="12" rx="2" fill="currentColor"/>'
    '<rect y="26" width="4" height="12" rx="2" transform="rotate(-90 0 26)" fill="currentColor"/>'
    '<rect x="36" y="26" width="4" height="12" rx="2" '
    'transform="rotate(-90 36 26)" fill="currentColor"/>'
    '<rect x="5.61523" y="8.4436" width="4" height="12" rx="2" '
    'transform="rotate(-45 5.61523 8.4436)" fill="currentColor"/>'
    '<rect x="31.071" y="33.8995" width="4" height="12" rx="2" '
    'transform="rotate(-45 31.071 33.8995)" fill="currentColor"/>'
    '<rect x="8.4436" y="42.3848" width="4" height="12" rx="2" '
    'transform="rotate(-135 8.4436 42.3848)" fill="currentColor"/>'
    '<rect x="33.8994" y="16.9288" width="4" height="12" rx="2" '
    'transform="rotate(-135 33.8994 16.9288)" fill="currentColor"/>'
    "</svg></g></g>"
)


_CacheKey = tuple[str, str, int, int, str, str]
_cache: OrderedDict[_CacheKey, list[bytes]] = OrderedDict()


def _bg_signature(bg_tile: bytes | Image.Image | None) -> str:
    """Compute a stable digest for a background tile.

    Parameters
    ----------
    bg_tile : bytes, PIL.Image.Image, or None
        The background image data (or ``None`` if no tile is set).

    Returns
    -------
    str
        Hex digest uniquely identifying the tile, or ``"none"`` when
        no tile is provided.
    """
    if bg_tile is None:
        return "none"
    if isinstance(bg_tile, bytes):
        return hashlib.sha1(bg_tile, usedforsecurity=False).hexdigest()
    buf = io.BytesIO()
    bg_tile.save(buf, format="PNG")
    return hashlib.sha1(buf.getvalue(), usedforsecurity=False).hexdigest()


def clear_cache() -> None:
    """Drop all cached spinner frames.

    Intended for use by tests and by application code that wants to
    release memory held by the spinner LRU.
    """
    _cache.clear()


def get_frames(
    *,
    rendered_svg: str,
    spinner_node_id: str,
    width: int,
    height: int,
    image_format: str = "JPEG",
    bg_tile: bytes | Image.Image | None = None,
) -> list[bytes]:
    """Return the 8 encoded frames of the canonical spinner animation.

    The result is cached process-wide in an LRU keyed by the rendered
    SVG, target dimensions, image format, and background-tile
    signature.  Cache hits return the same ``list`` object that was
    cached, so callers must not mutate it.

    Parameters
    ----------
    rendered_svg : str
        Layout SVG with bindings already applied (the same string that
        would be rasterised for a static render).  Must contain an
        element whose ``id`` matches ``spinner_node_id``.
    spinner_node_id : str
        ID of the placeholder group that the library injects spinner
        content into.
    width : int
        Target image width in pixels.
    height : int
        Target image height in pixels.
    image_format : str, default="JPEG"
        Output encoding; passed through to the image encoder.
    bg_tile : bytes, PIL.Image.Image, or None, optional
        Optional background tile composited beneath each frame to make
        the spinner blend with the surrounding panel.

    Returns
    -------
    list[bytes]
        ``SPINNER_FRAME_COUNT`` encoded frames, one per 45° rotation
        step.  When the placeholder node is missing from
        ``rendered_svg``, a list of blank fallback frames is returned.
    """
    key: _CacheKey = (
        hashlib.sha1(rendered_svg.encode("utf-8"), usedforsecurity=False).hexdigest(),
        spinner_node_id,
        width,
        height,
        image_format.upper(),
        _bg_signature(bg_tile),
    )
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        return cached

    frames = _render_frames(
        rendered_svg=rendered_svg,
        spinner_node_id=spinner_node_id,
        width=width,
        height=height,
        image_format=image_format,
        bg_tile=bg_tile,
    )

    _cache[key] = frames
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)
    return frames


def _render_frames(
    *,
    rendered_svg: str,
    spinner_node_id: str,
    width: int,
    height: int,
    image_format: str,
    bg_tile: bytes | Image.Image | None,
) -> list[bytes]:
    """Generate the 8 spinner frames without consulting the cache.

    Parameters mirror :func:`get_frames`; see that function for
    semantics.

    Returns
    -------
    list[bytes]
        Encoded frames, or a fallback list of blank frames when the
        placeholder node cannot be located.
    """
    base_root = safe_fromstring(rendered_svg)  # untrusted: .dui package source
    placeholder = _find_element_by_id(base_root, spinner_node_id)
    if placeholder is None:
        logger.warning(
            "Spinner placeholder '%s' not found in rendered SVG; "
            "returning blank frames",
            spinner_node_id,
        )
        return _blank_frames(width, height, image_format, bg_tile)

    step = 360.0 / SPINNER_FRAME_COUNT
    frames: list[bytes] = []
    for i in range(SPINNER_FRAME_COUNT):
        angle = step * i
        root = copy.deepcopy(base_root)
        target = _find_element_by_id(root, spinner_node_id)
        if target is None:  # defensive; deep-copied tree
            return _blank_frames(width, height, image_format, bg_tile)
        target.attrib.pop("display", None)
        _replace_children(target, _build_spinner_fragment(angle))
        frames.append(_rasterise(root, width, height, image_format, bg_tile))
    return frames


def _build_spinner_fragment(angle: float) -> ET.Element:
    """Parse the canonical spinner template for a given rotation angle.

    Parameters
    ----------
    angle : float
        Rotation in degrees applied to the inner rotor group.

    Returns
    -------
    xml.etree.ElementTree.Element
        Root ``<g>`` element of the canonical spinner content.
    """
    return safe_fromstring(_SPINNER_TEMPLATE_SVG.format(angle=f"{angle:.1f}"))


def _replace_children(parent: ET.Element, replacement: ET.Element) -> None:
    """Replace ``parent``'s children with the children of ``replacement``.

    The canonical spinner template wraps its content in an outer ``<g>``
    purely to satisfy XML parsing; only the inner elements are grafted
    into the placeholder so that the placeholder's own ``transform``
    (and any other attributes) remain authoritative.

    Parameters
    ----------
    parent : xml.etree.ElementTree.Element
        Placeholder element whose children are discarded.
    replacement : xml.etree.ElementTree.Element
        Container whose children become the new children of ``parent``.
    """
    for child in list(parent):
        parent.remove(child)
    for child in list(replacement):
        parent.append(child)


def _rasterise(
    root: ET.Element,
    width: int,
    height: int,
    image_format: str,
    bg_tile: bytes | Image.Image | None,
) -> bytes:
    """Rasterise an SVG tree and composite it onto an optional tile.

    Parameters
    ----------
    root : xml.etree.ElementTree.Element
        SVG document root to render.
    width : int
        Output width in pixels.
    height : int
        Output height in pixels.
    image_format : str
        Encoding format (``"JPEG"`` or ``"BMP"``).
    bg_tile : bytes, PIL.Image.Image, or None
        Optional background tile used to fill transparent regions.

    Returns
    -------
    bytes
        Encoded image bytes in ``image_format``.
    """
    # Inline import: tests patch ``deux.render.svg_rasterize._svg_to_image``.
    from ..render.svg_rasterize import _svg_to_image  # noqa: PLC0415

    svg_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
    frame = _svg_to_image(svg_bytes.encode("utf-8"), width, height, mode="RGBA")
    return _composite_on_bg(frame, bg_tile, image_format)


def _composite_on_bg(
    frame: Image.Image,
    bg_tile: bytes | Image.Image | None,
    image_format: str,
) -> bytes:
    """Composite an RGBA frame onto an optional tile and encode it.

    Parameters
    ----------
    frame : PIL.Image.Image
        RGBA frame produced by the SVG rasteriser.
    bg_tile : bytes, PIL.Image.Image, or None
        Optional tile composited beneath ``frame``.
    image_format : str
        Output encoding.

    Returns
    -------
    bytes
        Encoded image bytes.
    """
    if bg_tile is not None:
        if isinstance(bg_tile, bytes):
            base = Image.open(io.BytesIO(bg_tile)).convert("RGBA")
        else:
            base = bg_tile.convert("RGBA")
        result = Image.alpha_composite(base, frame)
    else:
        result = frame
    return _encode(result, image_format)


def _encode(img: Image.Image, image_format: str) -> bytes:
    """Encode a PIL image in the requested format.

    Parameters
    ----------
    img : PIL.Image.Image
        Image to encode.
    image_format : str
        Output format (``"JPEG"`` or ``"BMP"``).

    Returns
    -------
    bytes
        Encoded image bytes.
    """
    # Inline import: tests patch ``deux.render.key_renderer._encode_image_bytes``.
    from ..render.key_renderer import _encode_image_bytes  # noqa: PLC0415

    return _encode_image_bytes(img, image_format)


def _blank_frames(
    width: int,
    height: int,
    image_format: str,
    bg_tile: bytes | Image.Image | None,
) -> list[bytes]:
    """Return ``SPINNER_FRAME_COUNT`` blank frames as a fallback.

    When a background tile is provided, the blank frames show that
    tile; otherwise they are solid black.

    Parameters
    ----------
    width, height : int
        Output dimensions.
    image_format : str
        Output encoding.
    bg_tile : bytes, PIL.Image.Image, or None
        Optional background tile.

    Returns
    -------
    list[bytes]
        ``SPINNER_FRAME_COUNT`` copies of a single blank frame.
    """
    if bg_tile is not None:
        if isinstance(bg_tile, bytes):
            img = Image.open(io.BytesIO(bg_tile)).convert("RGB")
        else:
            img = bg_tile.convert("RGB")
    else:
        img = Image.new("RGB", (width, height), (0, 0, 0))
    data = _encode(img, image_format)
    return [data] * SPINNER_FRAME_COUNT
