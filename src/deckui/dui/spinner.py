"""Spinner frame generation for busy-state animations."""

from __future__ import annotations

import copy
import io
import logging
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from PIL import Image

from ..render.key_renderer import _encode_image
from .svg_renderer import _find_element_by_id

if TYPE_CHECKING:
    from .schema import PackageSpec, SpinnerSpec

logger = logging.getLogger(__name__)

_SVG_NS = "http://www.w3.org/2000/svg"


class SpinnerFrames:
    """Pre-renders spinner animation frames from an SVG template.

    Frames are generated lazily on first access and cached for the
    lifetime of the instance.

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
    """

    def __init__(
        self,
        spec: PackageSpec,
        width: int,
        height: int,
        image_format: str = "JPEG",
        rendered_svg: str | None = None,
    ) -> None:
        if spec.spinner is None:
            raise ValueError("PackageSpec has no spinner configuration")
        self._spec = spec
        self._spinner: SpinnerSpec = spec.spinner
        self._width = width
        self._height = height
        self._image_format = image_format
        self._rendered_svg = rendered_svg
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
        """Generate frames by rotating the spinner node."""
        svg_source = self._rendered_svg or self._spec.svg_source
        base_root = ET.fromstring(svg_source)  # noqa: S314
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

            frames.append(self._rasterise(root))
        return frames

    def _generate_pulse(self) -> list[bytes]:
        """Generate frames by pulsing opacity on the spinner node."""
        svg_source = self._rendered_svg or self._spec.svg_source
        base_root = ET.fromstring(svg_source)  # noqa: S314
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

            frames.append(self._rasterise(root))
        return frames

    def _generate_custom(self) -> list[bytes]:
        """Load custom frames from package assets."""
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
            img: Image.Image = Image.open(io.BytesIO(assets[key]))
            if img.size != (self._width, self._height):
                img = img.resize(
                    (self._width, self._height), Image.Resampling.LANCZOS
                )
            if img.mode != "RGB":
                img = img.convert("RGB")
            frames.append(_encode_image(img, self._image_format))
        return frames

    def _load_gif_frames(self, data: bytes) -> list[bytes]:
        """Extract and encode frames from an animated GIF."""
        gif = Image.open(io.BytesIO(data))
        frames: list[bytes] = []
        try:
            while True:
                frame = gif.copy()
                if frame.size != (self._width, self._height):
                    frame = frame.resize(
                        (self._width, self._height), Image.Resampling.LANCZOS
                    )
                if frame.mode != "RGB":
                    frame = frame.convert("RGB")
                frames.append(_encode_image(frame, self._image_format))
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass

        if not frames:
            logger.warning("Animated GIF has no frames; returning blank frames")
            return self._blank_frames()
        return frames

    def _blank_frames(self) -> list[bytes]:
        """Return a list of blank encoded frames as fallback."""
        blank = Image.new("RGB", (self._width, self._height), "black")
        data = _encode_image(blank, self._image_format)
        return [data] * self._spinner.frames

    def _rasterise(self, root: ET.Element) -> bytes:
        """Rasterise an SVG element tree to encoded image bytes."""
        from ..render.svg_rasterize import _svg_to_png

        svg_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
        png_data = _svg_to_png(svg_bytes.encode("utf-8"), self._width, self._height)
        img = Image.open(io.BytesIO(png_data)).convert("RGB")
        return _encode_image(img, self._image_format)

    @staticmethod
    def _element_centre(elem: ET.Element) -> tuple[float, float]:
        """Compute the centre of an SVG element from its geometry attributes."""
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
