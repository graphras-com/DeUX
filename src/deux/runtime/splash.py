"""Full-screen ("splash") image preparation for the Stream Deck LCD.

This module owns the **device-level**, *non-DUI* path for uploading a
single image covering the entire back-panel LCD (HID Report 0x02,
Command 0x08).  The hardware behaviour of that command is one-shot:
any subsequent per-key or per-window write paints over the image, so
this feature is intended for startup splashes, lock screens, and
loading screens — **not** as a persistent background for a
:class:`~deux.ui.screen.Screen`.

The async :class:`~deux.runtime.deck.Deck` wrapper lives on the deck
itself; this module exposes the pure, testable preparation pipeline:
*input → resize/fit → rotate → JPEG-encode*.

Accepted inputs
---------------
* :class:`PIL.Image.Image` — used directly.
* :class:`str` or :class:`pathlib.Path` — loaded from disk.  Files
  with an ``.svg`` suffix (or whose content sniffs as SVG) are
  rasterised via :func:`~deux.render.svg_rasterize._svg_to_image`
  at the target logical LCD size.
* :class:`bytes` — raw image bytes.  SVG is sniffed via the leading
  bytes; otherwise the bytes are decoded with Pillow.  Pre-encoded
  JPEG bytes whose dimensions and orientation already match the
  device transmit size are passed through untouched.

Fit modes
---------
* ``"cover"`` — scale to fill, crop overflow (default).
* ``"contain"`` — scale to fit, letterbox with the given background.
* ``"stretch"`` — scale to the exact target size, ignoring aspect.

Notes
-----
Rotation is applied **after** sizing and **before** JPEG encoding
so that the bytes handed to the HID layer are already in the
device's transmit orientation.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Literal

from PIL import Image

from .._errors import DeuxError
from .hid.protocol import ImageRotation

logger = logging.getLogger(__name__)

#: Allowed fit modes for :func:`prepare_full_screen_jpeg`.
FitMode = Literal["cover", "contain", "stretch"]

# Bytes that strongly indicate an SVG document.  The check is
# deliberately broad: we accept a UTF-8 BOM, optional leading
# whitespace, an optional XML declaration, and then either ``<svg``
# or a comment / DOCTYPE that precedes one.
_SVG_SNIFF_BYTES = (b"<svg", b"<?xml", b"<!--", b"<!DOCTYPE")

#: JPEG SOI marker.
_JPEG_MAGIC = b"\xff\xd8\xff"


class SplashError(DeuxError):
    """Raised when a full-screen image cannot be prepared."""


# ---------------------------------------------------------------------------
# Input classification
# ---------------------------------------------------------------------------


def _looks_like_svg(data: bytes) -> bool:
    """Return ``True`` if *data* sniffs as an SVG document.

    The check inspects up to the first 512 bytes (after stripping a
    UTF-8 BOM and leading whitespace) for one of the markers in
    :data:`_SVG_SNIFF_BYTES`.

    Parameters
    ----------
    data : bytes
        Raw bytes to classify.

    Returns
    -------
    bool
        ``True`` if the bytes look like SVG, ``False`` otherwise.
    """
    head = data[:512].lstrip(b"\xef\xbb\xbf").lstrip()
    return any(head.startswith(marker) for marker in _SVG_SNIFF_BYTES) or (
        b"<svg" in head
    )


def _looks_like_jpeg(data: bytes) -> bool:
    """Return ``True`` if *data* begins with the JPEG SOI marker."""
    return data.startswith(_JPEG_MAGIC)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _apply_fit(
    img: Image.Image,
    target: tuple[int, int],
    fit: FitMode,
    background: tuple[int, int, int],
) -> Image.Image:
    """Resize *img* into *target* according to *fit*.

    Parameters
    ----------
    img : Image.Image
        Source image (any mode).
    target : tuple[int, int]
        Target ``(width, height)`` in pixels.
    fit : {"cover", "contain", "stretch"}
        Fit mode.  See module docstring for semantics.
    background : tuple[int, int, int]
        RGB background colour used to letterbox under ``"contain"``.

    Returns
    -------
    Image.Image
        A new RGB image of exactly *target* size.

    Raises
    ------
    SplashError
        If *fit* is not one of the supported modes.
    """
    tw, th = target
    if tw <= 0 or th <= 0:
        raise SplashError(f"Invalid target size: {target!r}")

    if fit == "stretch":
        return img.convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)

    src_w, src_h = img.size
    if src_w <= 0 or src_h <= 0:
        raise SplashError(f"Invalid source image size: {img.size!r}")

    src_ratio = src_w / src_h
    dst_ratio = tw / th

    if fit == "cover":
        if src_ratio > dst_ratio:
            # Source is wider — match height, crop width.
            new_h = th
            new_w = max(tw, int(round(new_h * src_ratio)))
        else:
            new_w = tw
            new_h = max(th, int(round(new_w / src_ratio)))
        resized = img.convert("RGB").resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        return resized.crop((left, top, left + tw, top + th))

    if fit == "contain":
        if src_ratio > dst_ratio:
            # Source is wider — match width, letterbox top/bottom.
            new_w = tw
            new_h = max(1, int(round(new_w / src_ratio)))
        else:
            new_h = th
            new_w = max(1, int(round(new_h * src_ratio)))
        resized = img.convert("RGB").resize((new_w, new_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (tw, th), background)
        canvas.paste(resized, ((tw - new_w) // 2, (th - new_h) // 2))
        return canvas

    raise SplashError(
        f"Unknown fit mode: {fit!r} (expected 'cover', 'contain', or 'stretch')"
    )


def _apply_rotation(img: Image.Image, rotation: ImageRotation) -> Image.Image:
    """Rotate *img* by the device's transmit rotation.

    Maps the :class:`ImageRotation` enum to the corresponding PIL
    rotation.  PIL's :meth:`PIL.Image.Image.rotate` rotates
    **counter-clockwise**, so the mapping is by enum *name* rather
    than its underlying integer value:

    * :attr:`ImageRotation.NONE` — no rotation.
    * :attr:`ImageRotation.CW_180` — ``img.rotate(180)`` (180° is
      equivalent CW and CCW).
    * :attr:`ImageRotation.CCW_90` — ``img.rotate(90)`` (CCW 90°).

    Parameters
    ----------
    img : Image.Image
        Source image.
    rotation : ImageRotation
        Pre-upload rotation from
        :class:`deux.runtime.hid.protocol.ImageRotation`.

    Returns
    -------
    Image.Image
        Rotated image.  When *rotation* is :attr:`ImageRotation.NONE`
        the original image is returned unchanged.

    Raises
    ------
    SplashError
        If *rotation* is not a recognised :class:`ImageRotation`.
    """
    if rotation == ImageRotation.NONE:
        return img
    if rotation == ImageRotation.CW_180:
        return img.rotate(180, expand=True)
    if rotation == ImageRotation.CCW_90:
        return img.rotate(90, expand=True)
    raise SplashError(f"Unsupported rotation: {rotation!r}")


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------


def _load_image(
    image: Image.Image | str | Path | bytes,
    logical_size: tuple[int, int],
) -> tuple[Image.Image, bool]:
    """Load *image* into a PIL :class:`Image`.

    Parameters
    ----------
    image : Image.Image, str, Path, or bytes
        The input to load.  See module docstring for accepted forms.
    logical_size : tuple[int, int]
        Target logical LCD ``(width, height)``.  Used to rasterise SVG
        inputs directly at the target resolution.

    Returns
    -------
    tuple[Image.Image, bool]
        ``(loaded_image, came_from_svg)`` — the second item is ``True``
        when the SVG fast-path was taken so callers may, for example,
        choose to skip the fit step when the SVG already matches.

    Raises
    ------
    SplashError
        If the input cannot be classified or loaded.
    """
    if isinstance(image, Image.Image):
        return image, False

    if isinstance(image, (str, Path)):
        path = Path(image)
        if not path.exists():
            raise SplashError(f"Image path does not exist: {path!r}")
        suffix = path.suffix.lower()
        data = path.read_bytes()
        if suffix == ".svg" or _looks_like_svg(data):
            return _rasterize_svg_bytes(data, logical_size), True
        try:
            return Image.open(io.BytesIO(data)), False
        except Exception as exc:  # noqa: BLE001 — Pillow raises many types
            raise SplashError(f"Failed to decode image at {path!r}: {exc}") from exc

    if isinstance(image, (bytes, bytearray, memoryview)):
        data = bytes(image)
        if _looks_like_svg(data):
            return _rasterize_svg_bytes(data, logical_size), True
        try:
            return Image.open(io.BytesIO(data)), False
        except Exception as exc:  # noqa: BLE001
            raise SplashError(f"Failed to decode image bytes: {exc}") from exc

    raise SplashError(
        f"Unsupported image input type: {type(image).__name__}"
    )


def _rasterize_svg_bytes(
    svg_data: bytes, logical_size: tuple[int, int]
) -> Image.Image:
    """Rasterise SVG bytes at the logical LCD size.

    Thin wrapper around
    :func:`deux.render.svg_rasterize._svg_to_image` that imports
    lazily so the splash module does not pay the resvg import cost
    when only raster inputs are used.

    Parameters
    ----------
    svg_data : bytes
        Raw SVG content (UTF-8).
    logical_size : tuple[int, int]
        Target ``(width, height)`` in pixels.

    Returns
    -------
    Image.Image
        Rasterised image in RGB mode at *logical_size*.

    Raises
    ------
    SplashError
        If rasterisation fails (e.g. ``resvg`` not installed, invalid
        SVG).
    """
    # Lazy import: resvg is an optional native dep — see svg_rasterize.
    from ..render.svg_rasterize import RasterizeError, _svg_to_image  # noqa: PLC0415

    width, height = logical_size
    try:
        return _svg_to_image(svg_data, width, height, mode="RGB")
    except RasterizeError as exc:
        raise SplashError(f"SVG rasterisation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Public preparation entry point
# ---------------------------------------------------------------------------


def prepare_full_screen_jpeg(
    image: Image.Image | str | Path | bytes,
    *,
    logical_size: tuple[int, int],
    rotation: ImageRotation = ImageRotation.NONE,
    fit: FitMode = "cover",
    background: tuple[int, int, int] = (0, 0, 0),
    jpeg_quality: int = 90,
) -> bytes:
    """Prepare a JPEG ready for HID command ``0x08`` (full-screen image).

    Loads *image* (from any supported input type), resizes it to
    *logical_size* using *fit*, rotates by *rotation* to match the
    device transmit orientation, and JPEG-encodes the result.

    Parameters
    ----------
    image : Image.Image, str, Path, or bytes
        The source image.  See the module docstring for accepted
        forms (including SVG sniffing).
    logical_size : tuple[int, int]
        Target logical LCD ``(width, height)`` in pixels (the
        upright orientation the user sees).  Typically obtained
        from :attr:`deux.runtime.hid.device.HidDevice.logical_lcd_size`.
    rotation : ImageRotation, default=ImageRotation.NONE
        Pre-upload rotation to apply.  Typically obtained from
        :attr:`deux.runtime.hid.device.HidDevice.rotation`.
    fit : {"cover", "contain", "stretch"}, default="cover"
        Resize strategy.  See module docstring.
    background : tuple[int, int, int], default=(0, 0, 0)
        RGB letterbox colour for ``fit="contain"``.
    jpeg_quality : int, default=90
        JPEG quality (1-95).

    Returns
    -------
    bytes
        JPEG-encoded image bytes in the device transmit orientation,
        ready to hand to
        :meth:`deux.runtime.hid.device.HidDevice.set_full_screen_image`.

    Raises
    ------
    SplashError
        If the input cannot be loaded, *fit* is invalid, or
        *logical_size* is non-positive.

    Examples
    --------
    >>> from deux.runtime.splash import prepare_full_screen_jpeg
    >>> from deux.runtime.hid.protocol import ImageRotation
    >>> jpeg = prepare_full_screen_jpeg(
    ...     "splash.png",
    ...     logical_size=(800, 480),
    ...     rotation=ImageRotation.NONE,
    ...     fit="contain",
    ...     background=(0, 0, 0),
    ... )
    """
    pil_img, _from_svg = _load_image(image, logical_size)
    fitted = _apply_fit(pil_img, logical_size, fit, background)
    rotated = _apply_rotation(fitted, rotation)

    buf = io.BytesIO()
    rotated.save(buf, format="JPEG", quality=jpeg_quality)
    return buf.getvalue()


def prepare_solid_color_jpeg(
    color: tuple[int, int, int],
    *,
    logical_size: tuple[int, int],
    rotation: ImageRotation = ImageRotation.NONE,
    jpeg_quality: int = 90,
) -> bytes:
    """Prepare a solid-colour full-screen JPEG.

    Convenience wrapper around :func:`prepare_full_screen_jpeg` for
    clearing the LCD via the full-screen image path (useful when
    :meth:`HidDevice.fill_lcd_color` is unavailable on a given
    family, or when a deterministic clear via the same code path is
    preferred).

    Parameters
    ----------
    color : tuple[int, int, int]
        RGB fill colour.
    logical_size : tuple[int, int]
        Target logical LCD ``(width, height)``.
    rotation : ImageRotation, default=ImageRotation.NONE
        Pre-upload rotation.
    jpeg_quality : int, default=90
        JPEG quality.

    Returns
    -------
    bytes
        JPEG-encoded solid-colour image in transmit orientation.
    """
    canvas = Image.new("RGB", logical_size, color)
    return prepare_full_screen_jpeg(
        canvas,
        logical_size=logical_size,
        rotation=rotation,
        fit="stretch",
        jpeg_quality=jpeg_quality,
    )
