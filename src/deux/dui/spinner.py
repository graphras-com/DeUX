"""Spinner frame generation for busy-state animations."""

from __future__ import annotations

import copy
import io
import logging
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from PIL import Image

from .._xml import safe_fromstring
from .svg_renderer import _find_element_by_id

if TYPE_CHECKING:
    from .schema import PackageSpec, SpinnerSpec

logger = logging.getLogger(__name__)

_SVG_NS = "http://www.w3.org/2000/svg"


class SpinnerFrames:
    """Pre-renders spinner animation frames from an SVG template.

    Frames are generated lazily on first access and cached for the
    lifetime of the instance.

    When a *bg_tile* is provided, each frame is composited onto the
    background tile before encoding so that transparent regions of
    the spinner reveal the touchstrip background underneath.

    Parameters
    ----------
    spec
        The package specification containing the SVG source and spinner config.
    width
        Target image width in pixels.
    height
        Target image height in pixels.
    image_format
        Encoding format (``"JPEG"`` or ``"BMP"``).
    rendered_svg
        Optional pre-rendered SVG source with bindings already applied.
    bg_tile
        Optional RGB background tile to composite frames onto.
    """

    def __init__(
        self,
        spec: PackageSpec,
        width: int,
        height: int,
        image_format: str = "JPEG",
        rendered_svg: str | None = None,
        bg_tile: bytes | Image.Image | None = None,
    ) -> None:
        if spec.spinner is None:
            raise ValueError("PackageSpec has no spinner configuration")
        self._spec = spec
        self._spinner: SpinnerSpec = spec.spinner
        self._width = width
        self._height = height
        self._image_format = image_format
        self._rendered_svg = rendered_svg
        self._bg_tile = bg_tile
        self._cached_frames: list[bytes] | None = None

    @property
    def frame_count(self) -> int:
        """Number of frames in the animation cycle."""
        return self._spinner.frames

    @property
    def interval_ms(self) -> int:
        """Milliseconds between frames."""
        return self._spinner.interval_ms

    @property
    def frames(self) -> list[bytes]:
        """Encoded animation frames, generated on first access."""
        if self._cached_frames is None:
            self._cached_frames = self._generate()
        return self._cached_frames

    def _generate(self) -> list[bytes]:
        """Generate all animation frames."""
        from .schema import SpinnerType

        if self._spinner.type == SpinnerType.ROTATION:
            return self._generate_rotation()
        if self._spinner.type == SpinnerType.PULSE:
            return self._generate_pulse()
        return self._generate_custom()

    def _generate_rotation(self) -> list[bytes]:
        """Generate frames by rotating the spinner node.

        Returns
        -------
        list[bytes]
            Encoded image frames, one per rotation step.
        """
        svg_source = self._rendered_svg or self._spec.svg_source
        base_root = safe_fromstring(svg_source)  # untrusted: .dui package
        node = self._spinner.node
        assert node is not None

        # Find the element to determine its centre of rotation
        elem = _find_element_by_id(base_root, node)
        if elem is None:
            logger.warning("Spinner node '%s' not found; returning blank frames", node)
            return self._blank_frames()

        cx, cy = self._element_centre(elem)
        step = 360.0 / self._spinner.frames

        frames: list[bytes] = []
        for i in range(self._spinner.frames):
            root = copy.deepcopy(base_root)
            el = _find_element_by_id(root, node)
            if el is not None:
                # Make the spinner node visible
                el.attrib.pop("display", None)
                angle = step * i
                existing = el.get("transform", "")
                rotation = f"rotate({angle:.1f},{cx:.1f},{cy:.1f})"
                el.set("transform", f"{existing} {rotation}".strip())

            self._show_background_node(root)
            frames.append(self._rasterise(root))
        return frames

    def _generate_pulse(self) -> list[bytes]:
        """Generate frames by pulsing opacity on the spinner node.

        Returns
        -------
        list[bytes]
            Encoded image frames with a triangle-wave opacity cycle.
        """
        svg_source = self._rendered_svg or self._spec.svg_source
        base_root = safe_fromstring(svg_source)  # untrusted: .dui package
        node = self._spinner.node
        assert node is not None

        n = self._spinner.frames
        frames: list[bytes] = []
        for i in range(n):
            root = copy.deepcopy(base_root)
            el = _find_element_by_id(root, node)
            if el is not None:
                el.attrib.pop("display", None)
                # Triangle wave: 0→1→0 over the cycle
                t = i / n
                opacity = 1.0 - 2.0 * abs(t - 0.5)
                opacity = max(0.2, min(1.0, 0.2 + 0.8 * opacity))
                el.set("opacity", f"{opacity:.2f}")

            self._show_background_node(root)
            frames.append(self._rasterise(root))
        return frames

    def _show_background_node(self, root: ET.Element) -> None:
        """Make the background node visible in the given SVG tree.

        If ``background_node`` is configured on the spinner spec, this
        removes ``display="none"`` from it so the background appears
        behind the animated spinner.  No transform or opacity changes
        are applied — the node is shown as-is.

        Parameters
        ----------
        root
            The parsed SVG element tree (will be mutated in place).
        """
        bg_id = self._spinner.background_node
        if bg_id is not None:
            bg_el = _find_element_by_id(root, bg_id)
            if bg_el is not None:
                bg_el.attrib.pop("display", None)

    def _generate_custom(self) -> list[bytes]:
        """Load custom frames from package assets.

        Looks for ``assets/spinner.gif`` first, then numbered PNGs in
        ``assets/spinner/``. Falls back to blank frames if neither is found.

        Returns
        -------
        list[bytes]
            Encoded image frames loaded from the package assets.
        """
        assets = self._spec.assets

        # Try animated GIF first
        if "spinner.gif" in assets:
            return self._load_gif_frames(assets["spinner.gif"])

        # Try numbered PNGs in spinner/ subdirectory
        frame_keys = sorted(k for k in assets if k.startswith("spinner/frame_"))
        if not frame_keys:
            logger.warning("No custom spinner frames found; returning blank frames")
            return self._blank_frames()

        frames: list[bytes] = []
        for key in frame_keys:
            frame_img: Image.Image = Image.open(io.BytesIO(assets[key]))
            if frame_img.size != (self._width, self._height):
                frame_img = frame_img.resize(
                    (self._width, self._height), Image.Resampling.LANCZOS
                )
            buf = io.BytesIO()
            frame_img.save(buf, format="PNG")
            frames.append(self._composite_on_bg(buf.getvalue()))
        return frames

    def _load_gif_frames(self, data: bytes) -> list[bytes]:
        """Extract and encode frames from an animated GIF.

        Parameters
        ----------
        data : bytes
            Raw GIF file bytes.

        Returns
        -------
        list[bytes]
            Encoded image frames; falls back to blank frames if the GIF
            contains no frames.
        """
        gif = Image.open(io.BytesIO(data))
        n_frames = getattr(gif, "n_frames", 1)

        frames: list[bytes] = []
        for i in range(n_frames):
            gif.seek(i)
            frame = gif.convert("RGBA")
            if frame.size != (self._width, self._height):
                frame = frame.resize(
                    (self._width, self._height), Image.Resampling.LANCZOS
                )
            buf = io.BytesIO()
            frame.save(buf, format="PNG")
            frames.append(self._composite_on_bg(buf.getvalue()))

        if not frames:
            logger.warning("Animated GIF has no frames; returning blank frames")
            return self._blank_frames()
        return frames

    def _blank_frames(self) -> list[bytes]:
        """Return a list of blank encoded frames as fallback.

        When a background tile is set, blank frames show the background
        tile instead of solid black.

        Returns
        -------
        list[bytes]
            Blank or background-filled frames, one per configured spinner
            frame count.
        """
        if self._bg_tile is not None:
            data = self._encode_tile(self._bg_tile)
        else:
            data = self._encode_blank()
        return [data] * self._spinner.frames

    def _composite_on_bg(self, png_data: bytes) -> bytes:
        """Composite a frame onto the background tile if available.

        Parameters
        ----------
        png_data : bytes
            PNG-encoded frame data (may have alpha).

        Returns
        -------
        bytes
            Encoded image bytes in the instance's configured format.
        """
        frame = Image.open(io.BytesIO(png_data)).convert("RGBA")

        if self._bg_tile is not None:
            if isinstance(self._bg_tile, bytes):
                base = Image.open(io.BytesIO(self._bg_tile)).convert("RGBA")
            else:
                base = self._bg_tile.convert("RGBA")
            result = Image.alpha_composite(base, frame)
        else:
            result = frame

        return self._encode_pil(result)

    def _encode_pil(self, img: Image.Image) -> bytes:
        """Encode a PIL image in the configured format.

        Parameters
        ----------
        img
            A ``PIL.Image.Image`` instance.

        Returns
        -------
        bytes
            Encoded image bytes.
        """
        from ..render.key_renderer import _encode_image_bytes

        return _encode_image_bytes(img, self._image_format)

    def _encode_tile(self, tile: bytes | Image.Image) -> bytes:
        """Re-encode a tile in the configured output format.

        Parameters
        ----------
        tile : bytes or Image.Image
            PNG-encoded tile bytes or a PIL Image.

        Returns
        -------
        bytes
            Image bytes in the configured format.
        """
        if isinstance(tile, bytes):
            img = Image.open(io.BytesIO(tile)).convert("RGB")
        else:
            img = tile.convert("RGB")
        return self._encode_pil(img)

    def _encode_blank(self) -> bytes:
        """Encode a solid black frame.

        Returns
        -------
        bytes
            Black frame in the configured format.
        """
        img = Image.new("RGB", (self._width, self._height), (0, 0, 0))
        return self._encode_pil(img)

    def _rasterise(self, root: ET.Element) -> bytes:
        """Rasterise an SVG element tree to encoded image bytes.

        Parameters
        ----------
        root : ET.Element
            The SVG document root to render.

        Returns
        -------
        bytes
            Image data encoded in the instance's configured format.
        """
        from ..render.svg_rasterize import _svg_to_png

        svg_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
        png_data = _svg_to_png(svg_bytes.encode("utf-8"), self._width, self._height)
        return self._composite_on_bg(png_data)

    @staticmethod
    def _element_centre(elem: ET.Element) -> tuple[float, float]:
        """Compute the centre of an SVG element from its geometry attributes.

        Handles both rectangular elements (``x``, ``y``, ``width``, ``height``)
        and circle/ellipse elements (``cx``, ``cy``).

        Parameters
        ----------
        elem : ET.Element
            The SVG element to measure.

        Returns
        -------
        tuple[float, float]
            ``(cx, cy)`` centre coordinates.
        """
        x = float(elem.get("x", "0"))
        y = float(elem.get("y", "0"))
        w = float(elem.get("width", "0"))
        h = float(elem.get("height", "0"))

        # For circle/ellipse elements
        if w == 0 and h == 0:
            cx = float(elem.get("cx", str(x)))
            cy = float(elem.get("cy", str(y)))
            return cx, cy

        return x + w / 2, y + h / 2
