"""Default theme assets bundled with DeUX.

Provides default background SVGs for all supported Stream Deck devices,
looked up by USB VID:PID so that even devices sharing a model number
(e.g. Stream Deck + and Stream Deck + XL) are correctly distinguished.
"""

from __future__ import annotations

import logging
from importlib import resources
from typing import TypedDict

import yaml

logger = logging.getLogger(__name__)

_BACKGROUNDS_PACKAGE = "deux.render.defaults.backgrounds"

# Module-level cache populated on first call.
_manifest_loaded = False
_device_map: dict[tuple[int, int], dict[str, str]] = {}


class SurfaceBackgrounds(TypedDict, total=False):
    """Mapping of surface type to raw SVG bytes.

    Keys are ``"key"``, ``"touchscreen"``, and/or ``"screen"``
    depending on the device's hardware capabilities.
    """

    key: bytes
    touchscreen: bytes
    screen: bytes


def _load_manifest() -> None:
    """Parse the backgrounds manifest and populate the device map.

    Called lazily on the first :func:`get_default_backgrounds` call.
    The manifest maps USB VID:PID pairs to SVG filenames for each
    surface type.

    Raises
    ------
    FileNotFoundError
        If the manifest YAML is missing from the package.
    """
    global _manifest_loaded, _device_map  # noqa: PLW0603

    ref = resources.files(_BACKGROUNDS_PACKAGE).joinpath("manifest.yaml")
    raw = ref.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    for entry in data.get("backgrounds", []):
        vid = int(str(entry["vid"]), 0)
        pid = int(str(entry["pid"]), 0)
        surfaces: dict[str, str] = entry.get("surfaces", {})
        _device_map[(vid, pid)] = surfaces

    _manifest_loaded = True
    logger.debug("Loaded default backgrounds manifest: %d devices", len(_device_map))


def _read_svg(filename: str) -> bytes:
    """Read a bundled SVG file from the backgrounds package.

    Parameters
    ----------
    filename : str
        Name of the SVG file (e.g. ``"72x72.svg"``).

    Returns
    -------
    bytes
        Raw SVG content.
    """
    ref = resources.files(_BACKGROUNDS_PACKAGE).joinpath(filename)
    return ref.read_bytes()


def get_default_backgrounds(vid: int, pid: int) -> SurfaceBackgrounds:
    """Return default background SVGs for a device identified by VID:PID.

    Looks up the bundled manifest to find the correct SVG files for
    each surface type (key, touchscreen, screen) supported by the
    device.

    Parameters
    ----------
    vid : int
        USB vendor ID (e.g. ``0x0FD9`` for Elgato).
    pid : int
        USB product ID.

    Returns
    -------
    SurfaceBackgrounds
        Mapping of surface type to raw SVG bytes.  Returns an empty
        dict if no defaults are defined for the given VID:PID.

    Examples
    --------
    ::

        backgrounds = get_default_backgrounds(0x0FD9, 0x0084)
        if "key" in backgrounds:
            key_svg = backgrounds["key"]
    """
    if not _manifest_loaded:
        try:
            _load_manifest()
        except Exception:
            logger.warning("Failed to load default backgrounds manifest", exc_info=True)
            return SurfaceBackgrounds()

    surfaces = _device_map.get((vid, pid))
    if surfaces is None:
        return SurfaceBackgrounds()

    result = SurfaceBackgrounds()
    for surface_type, filename in surfaces.items():
        try:
            result[surface_type] = _read_svg(filename)  # type: ignore[literal-required]
        except Exception:
            logger.warning(
                "Failed to load default background %s for %04x:%04x",
                filename,
                vid,
                pid,
                exc_info=True,
            )

    return result


def list_supported_devices() -> list[tuple[int, int]]:
    """Return all VID:PID pairs that have default backgrounds.

    Returns
    -------
    list[tuple[int, int]]
        Sorted list of ``(vendor_id, product_id)`` tuples.
    """
    if not _manifest_loaded:
        try:
            _load_manifest()
        except Exception:
            logger.warning("Failed to load default backgrounds manifest", exc_info=True)
            return []

    return sorted(_device_map.keys())


def reset_cache() -> None:
    """Clear the internal manifest cache.

    Primarily useful for testing.
    """
    global _manifest_loaded, _device_map  # noqa: PLW0603
    _manifest_loaded = False
    _device_map = {}
