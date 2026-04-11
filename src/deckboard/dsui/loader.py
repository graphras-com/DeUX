"""Load and validate .dsui packages from disk."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

from .schema import (
    Binding,
    BindingType,
    ColorBinding,
    EventMapping,
    HOLD_SOURCES,
    ImageBinding,
    ImageFit,
    OverflowMode,
    PackageSpec,
    PackageType,
    Region,
    TextBinding,
    VALID_DIRECTIONS,
    VALID_REGION_EVENTS,
    VALID_SOURCES,
    VisibilityBinding,
)

logger = logging.getLogger(__name__)

# SVG namespace used by ElementTree
_SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


class PackageError(Exception):
    """Raised when a .dsui package is invalid or cannot be loaded."""


def _find_svg_ids(svg_source: str) -> set[str]:
    """Extract all id attributes from an SVG string."""
    try:
        root = ET.fromstring(svg_source)  # noqa: S314 — trusted local files only
    except ET.ParseError as exc:
        raise PackageError(f"Invalid SVG: {exc}") from exc

    ids: set[str] = set()
    for elem in root.iter():
        elem_id = elem.get("id")
        if elem_id:
            ids.add(elem_id)
    return ids


def _parse_binding(name: str, raw: dict[str, Any]) -> Binding:
    """Parse a single binding entry from the manifest."""
    raw_type = raw.get("type")
    if raw_type is None:
        raise PackageError(f"Binding '{name}' missing 'type'")

    try:
        binding_type = BindingType(raw_type)
    except ValueError:
        valid = [bt.value for bt in BindingType]
        raise PackageError(
            f"Binding '{name}' has invalid type '{raw_type}'. Valid types: {valid}"
        ) from None

    node = raw.get("node")
    if node is None:
        raise PackageError(f"Binding '{name}' missing 'node'")

    if binding_type == BindingType.TEXT:
        overflow_raw = raw.get("overflow", "ellipsis")
        try:
            overflow = OverflowMode(overflow_raw)
        except ValueError:
            valid_modes = [m.value for m in OverflowMode]
            raise PackageError(
                f"Binding '{name}' has invalid overflow '{overflow_raw}'. "
                f"Valid modes: {valid_modes}"
            ) from None
        return TextBinding(
            node=node,
            default=str(raw.get("default", "")),
            max_width=raw.get("max_width"),
            overflow=overflow,
        )

    if binding_type == BindingType.IMAGE:
        fit_raw = raw.get("fit", "cover")
        try:
            fit = ImageFit(fit_raw)
        except ValueError:
            valid_fits = [f.value for f in ImageFit]
            raise PackageError(
                f"Binding '{name}' has invalid fit '{fit_raw}'. "
                f"Valid modes: {valid_fits}"
            ) from None
        return ImageBinding(
            node=node,
            fit=fit,
            placeholder_node=raw.get("placeholder_node"),
        )

    if binding_type == BindingType.VISIBILITY:
        return VisibilityBinding(
            node=node,
            default=bool(raw.get("default", True)),
        )

    # BindingType.COLOR
    return ColorBinding(
        node=node,
        attribute=str(raw.get("attribute", "fill")),
        default=str(raw.get("default", "#ffffff")),
    )


def _parse_event(raw: dict[str, Any], index: int) -> EventMapping:
    """Parse a single event mapping from the manifest."""
    name = raw.get("name")
    if name is None:
        raise PackageError(f"Event at index {index} missing 'name'")

    source = raw.get("source")
    if source is None:
        raise PackageError(f"Event '{name}' missing 'source'")
    if source not in VALID_SOURCES:
        raise PackageError(
            f"Event '{name}' has invalid source '{source}'. "
            f"Valid sources: {sorted(VALID_SOURCES)}"
        )

    direction = raw.get("direction")
    if direction is not None and direction not in VALID_DIRECTIONS:
        raise PackageError(
            f"Event '{name}' has invalid direction '{direction}'. "
            f"Valid: {sorted(VALID_DIRECTIONS)}"
        )

    max_duration_ms = raw.get("max_duration_ms")
    if max_duration_ms is not None:
        if not isinstance(max_duration_ms, int) or max_duration_ms <= 0:
            raise PackageError(
                f"Event '{name}': max_duration_ms must be a positive integer"
            )

    hold_ms = raw.get("hold_ms")
    if source in HOLD_SOURCES:
        if hold_ms is None:
            raise PackageError(
                f"Event '{name}': hold_ms is required for source '{source}'"
            )
        if not isinstance(hold_ms, int) or hold_ms <= 0:
            raise PackageError(f"Event '{name}': hold_ms must be a positive integer")
    elif hold_ms is not None:
        raise PackageError(
            f"Event '{name}': hold_ms is only valid for key_hold/encoder_hold sources"
        )

    return EventMapping(
        name=name,
        source=source,
        direction=direction,
        max_duration_ms=max_duration_ms,
        hold_ms=hold_ms,
    )


def _parse_region(name: str, raw: dict[str, Any]) -> Region:
    """Parse a single region from the manifest."""
    for field_name in ("x", "y", "width", "height"):
        if field_name not in raw:
            raise PackageError(f"Region '{name}' missing '{field_name}'")
        if not isinstance(raw[field_name], int) or raw[field_name] < 0:
            raise PackageError(
                f"Region '{name}': '{field_name}' must be a non-negative integer"
            )

    events_raw = raw.get("events", [])
    if not isinstance(events_raw, list):
        raise PackageError(f"Region '{name}': 'events' must be a list")

    for evt in events_raw:
        if evt not in VALID_REGION_EVENTS:
            raise PackageError(
                f"Region '{name}': invalid event '{evt}'. "
                f"Valid: {sorted(VALID_REGION_EVENTS)}"
            )

    return Region(
        name=name,
        x=raw["x"],
        y=raw["y"],
        width=raw["width"],
        height=raw["height"],
        events=tuple(events_raw),
    )


def load_package(path: str | Path) -> PackageSpec:
    """Load a .dsui package directory into a validated PackageSpec.

    Args:
        path: Path to the ``.dsui`` directory.

    Returns:
        A frozen :class:`PackageSpec` ready to be used by
        :class:`~deckboard.dsui.card.DsuiCard` or
        :class:`~deckboard.dsui.key.DsuiKey`.

    Raises:
        PackageError: If the package is invalid or incomplete.
    """
    pkg_dir = Path(path)
    if not pkg_dir.is_dir():
        raise PackageError(f"Package path is not a directory: {pkg_dir}")

    # --- manifest.yaml ---
    manifest_path = pkg_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise PackageError(f"Missing manifest.yaml in {pkg_dir}")

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest: dict[str, Any] = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise PackageError(f"Invalid YAML in manifest: {exc}") from exc

    if not isinstance(manifest, dict):
        raise PackageError("manifest.yaml must be a YAML mapping")

    # --- Required top-level fields ---
    name = manifest.get("name")
    if not name or not isinstance(name, str):
        raise PackageError("manifest.yaml missing or invalid 'name'")

    raw_type = manifest.get("type")
    if raw_type is None:
        raise PackageError("manifest.yaml missing 'type'")
    try:
        pkg_type = PackageType(raw_type)
    except ValueError:
        valid = [t.value for t in PackageType]
        raise PackageError(
            f"Invalid package type '{raw_type}'. Valid types: {valid}"
        ) from None

    version = manifest.get("version")
    if version is None:
        raise PackageError("manifest.yaml missing 'version'")
    if not isinstance(version, int) or version < 1:
        raise PackageError("'version' must be a positive integer")

    # --- Layout SVG ---
    layout_file = manifest.get("layout")
    if not layout_file or not isinstance(layout_file, str):
        raise PackageError("manifest.yaml missing or invalid 'layout'")

    layout_path = pkg_dir / layout_file
    if not layout_path.exists():
        raise PackageError(f"Layout file not found: {layout_path}")

    svg_source = layout_path.read_text(encoding="utf-8")
    svg_ids = _find_svg_ids(svg_source)

    # --- Bindings ---
    bindings: dict[str, Binding] = {}
    raw_bindings = manifest.get("bindings", {})
    if raw_bindings and not isinstance(raw_bindings, dict):
        raise PackageError("'bindings' must be a mapping")
    for binding_name, binding_raw in (raw_bindings or {}).items():
        if not isinstance(binding_raw, dict):
            raise PackageError(f"Binding '{binding_name}' must be a mapping")
        binding = _parse_binding(binding_name, binding_raw)
        # Validate node exists in SVG
        if binding.node not in svg_ids:
            raise PackageError(
                f"Binding '{binding_name}' references node '{binding.node}' "
                f"which does not exist in the SVG. "
                f"Available ids: {sorted(svg_ids)}"
            )
        # Validate placeholder_node for image bindings
        if isinstance(binding, ImageBinding) and binding.placeholder_node:
            if binding.placeholder_node not in svg_ids:
                raise PackageError(
                    f"Binding '{binding_name}' references placeholder_node "
                    f"'{binding.placeholder_node}' which does not exist in the SVG"
                )
        bindings[binding_name] = binding

    # --- Events ---
    events: list[EventMapping] = []
    raw_events = manifest.get("events", [])
    if raw_events and not isinstance(raw_events, list):
        raise PackageError("'events' must be a list")
    seen_names: set[str] = set()
    for i, event_raw in enumerate(raw_events or []):
        if not isinstance(event_raw, dict):
            raise PackageError(f"Event at index {i} must be a mapping")
        event = _parse_event(event_raw, i)
        if event.name in seen_names:
            raise PackageError(f"Duplicate event name '{event.name}'")
        seen_names.add(event.name)
        events.append(event)

    # --- Regions ---
    regions: list[Region] = []
    raw_regions = manifest.get("regions", {})
    if raw_regions and not isinstance(raw_regions, dict):
        raise PackageError("'regions' must be a mapping")
    for region_name, region_raw in (raw_regions or {}).items():
        if not isinstance(region_raw, dict):
            raise PackageError(f"Region '{region_name}' must be a mapping")
        region = _parse_region(region_name, region_raw)
        regions.append(region)

    # --- Assets ---
    assets: dict[str, bytes] = {}
    assets_dir = pkg_dir / "assets"
    if assets_dir.is_dir():
        for asset_file in assets_dir.iterdir():
            if asset_file.is_file():
                assets[asset_file.name] = asset_file.read_bytes()

    logger.info(
        "Loaded .dsui package '%s' (%s, %d bindings, %d events)",
        name,
        pkg_type.value,
        len(bindings),
        len(events),
    )

    return PackageSpec(
        name=name,
        type=pkg_type,
        version=version,
        svg_source=svg_source,
        bindings=bindings,
        events=tuple(events),
        regions=tuple(regions),
        assets=assets,
    )


def load_all_packages(directory: str | Path) -> dict[str, PackageSpec]:
    """Load all .dsui packages from a directory.

    Args:
        directory: Path to scan for ``.dsui`` subdirectories.

    Returns:
        A dict mapping package names to their specs.

    Raises:
        PackageError: If any package fails validation.
    """
    base = Path(directory)
    if not base.is_dir():
        raise PackageError(f"Not a directory: {base}")

    packages: dict[str, PackageSpec] = {}
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and entry.suffix == ".dsui":
            spec = load_package(entry)
            packages[spec.name] = spec

    logger.info("Loaded %d .dsui packages from %s", len(packages), base)
    return packages
