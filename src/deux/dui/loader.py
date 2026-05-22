"""Load and validate .dui packages from disk."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .._errors import DeuxError
from .._xml import safe_fromstring
from .schema import (
    DEFAULT_HOLD_MS,
    DEFAULT_MAX_DURATION_MS,
    DEFAULT_SPINNER_FRAMES,
    DEFAULT_SPINNER_INTERVAL_MS,
    HOLD_SOURCES,
    KNOWN_MANIFEST_KEYS,
    TURN_SOURCES,
    VALID_CATEGORIES,
    VALID_DIRECTIONS,
    VALID_REGION_EVENTS,
    VALID_SOURCES,
    Binding,
    BindingType,
    ColorBinding,
    CssClassBinding,
    EventMapping,
    IconifyBinding,
    ImageBinding,
    ImageFit,
    ListBinding,
    OverflowMode,
    PackageSpec,
    PackageType,
    RangeBinding,
    RangeDirection,
    Region,
    RotateTransform,
    SliderBinding,
    SpinnerSpec,
    SpinnerType,
    TextBinding,
    ToggleBinding,
    TransformBinding,
    TransformKind,
    VisibilityBinding,
)

logger = logging.getLogger(__name__)
_SVG_NS = {"svg": "http://www.w3.org/2000/svg"}

_PRESS_RELEASE_SOURCES = frozenset({"key_press_release", "encoder_press_release"})


class PackageError(DeuxError):
    """Raised when a .dui package is invalid or cannot be loaded."""


def _find_svg_ids(svg_source: str) -> set[str]:
    """Extract all ``id`` attributes from an SVG string.

    Parameters
    ----------
    svg_source : str
        Raw SVG markup to parse.

    Returns
    -------
    set[str]
        The set of ``id`` attribute values found in the SVG.

    Raises
    ------
    PackageError
        If *svg_source* is not valid XML.
    """
    try:
        root = safe_fromstring(svg_source)  # untrusted: user-supplied .dui package
    except Exception as exc:
        raise PackageError(f"Invalid SVG: {exc}") from exc

    ids: set[str] = set()
    for elem in root.iter():
        elem_id = elem.get("id")
        if elem_id:
            ids.add(elem_id)
    return ids


def _parse_binding(name: str, raw: dict[str, Any]) -> Binding:
    """Parse a single binding entry from the manifest.

    Parameters
    ----------
    name : str
        Binding name as it appears in the manifest ``bindings`` mapping.
    raw : dict[str, Any]
        Raw YAML mapping for this binding entry.

    Returns
    -------
    Binding
        A concrete binding dataclass (e.g. ``TextBinding``, ``ToggleBinding``).

    Raises
    ------
    PackageError
        If required keys are missing or values are invalid.
    """
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

    if binding_type == BindingType.TOGGLE:
        node_on = raw.get("node_on")
        if not node_on or not isinstance(node_on, str):
            raise PackageError(f"Binding '{name}' missing 'node_on'")
        node_off = raw.get("node_off")
        if not node_off or not isinstance(node_off, str):
            raise PackageError(f"Binding '{name}' missing 'node_off'")
        return ToggleBinding(
            node_on=node_on,
            node_off=node_off,
            default=bool(raw.get("default", False)),
        )

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

        wrap = bool(raw.get("wrap", False))
        max_width = raw.get("max_width")
        if wrap and max_width is None:
            raise PackageError(
                f"Binding '{name}' has wrap=true but no max_width. "
                "max_width is required when wrapping is enabled."
            )

        max_height_raw = raw.get("max_height")
        max_height: int | None = None
        if max_height_raw is not None:
            if not isinstance(max_height_raw, int) or max_height_raw <= 0:
                raise PackageError(
                    f"Binding '{name}' max_height must be a positive integer, "
                    f"got {max_height_raw!r}"
                )
            max_height = max_height_raw

        line_height_raw = raw.get("line_height")
        line_height: float | None = None
        if line_height_raw is not None:
            if not isinstance(line_height_raw, (int, float)) or line_height_raw <= 0:
                raise PackageError(
                    f"Binding '{name}' line_height must be a positive number, "
                    f"got {line_height_raw!r}"
                )
            line_height = float(line_height_raw)

        return TextBinding(
            node=node,
            default=str(raw.get("default", "")),
            max_width=max_width,
            overflow=overflow,
            wrap=wrap,
            max_height=max_height,
            line_height=line_height,
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

    if binding_type == BindingType.RANGE:
        direction_raw = raw.get("direction", "horizontal")
        try:
            direction = RangeDirection(direction_raw)
        except ValueError:
            valid_dirs = [d.value for d in RangeDirection]
            raise PackageError(
                f"Binding '{name}' has invalid direction '{direction_raw}'. "
                f"Valid directions: {valid_dirs}"
            ) from None
        default_val = raw.get("default", 0.0)
        if not isinstance(default_val, (int, float)):
            raise PackageError(f"Binding '{name}': default must be a number")
        default_float = float(default_val)
        if not 0.0 <= default_float <= 1.0:
            raise PackageError(f"Binding '{name}': default must be between 0.0 and 1.0")
        return RangeBinding(
            node=node,
            default=default_float,
            direction=direction,
        )

    if binding_type == BindingType.SLIDER:
        direction_raw = raw.get("direction", "horizontal")
        try:
            direction = RangeDirection(direction_raw)
        except ValueError:
            valid_dirs = [d.value for d in RangeDirection]
            raise PackageError(
                f"Binding '{name}' has invalid direction '{direction_raw}'. "
                f"Valid directions: {valid_dirs}"
            ) from None
        default_val = raw.get("default", 0.0)
        if not isinstance(default_val, (int, float)):
            raise PackageError(f"Binding '{name}': default must be a number")
        default_float = float(default_val)
        if not 0.0 <= default_float <= 1.0:
            raise PackageError(f"Binding '{name}': default must be between 0.0 and 1.0")
        min_pos_raw = raw.get("min_pos")
        if min_pos_raw is None:
            raise PackageError(f"Binding '{name}' missing 'min_pos'")
        if not isinstance(min_pos_raw, (int, float)):
            raise PackageError(f"Binding '{name}': min_pos must be a number")
        max_pos_raw = raw.get("max_pos")
        if max_pos_raw is None:
            raise PackageError(f"Binding '{name}' missing 'max_pos'")
        if not isinstance(max_pos_raw, (int, float)):
            raise PackageError(f"Binding '{name}': max_pos must be a number")
        if float(min_pos_raw) > float(max_pos_raw):
            raise PackageError(
                f"Binding '{name}': min_pos ({min_pos_raw}) must be <= "
                f"max_pos ({max_pos_raw})"
            )
        return SliderBinding(
            node=node,
            default=default_float,
            direction=direction,
            min_pos=float(min_pos_raw),
            max_pos=float(max_pos_raw),
        )

    if binding_type == BindingType.ICONIFY:
        size_raw = raw.get("size")
        if size_raw is None:
            raise PackageError(f"Binding '{name}' missing 'size'")
        if not isinstance(size_raw, int) or isinstance(size_raw, bool) or size_raw <= 0:
            raise PackageError(
                f"Binding '{name}': size must be a positive integer, got {size_raw!r}"
            )
        default_raw = raw.get("default", "")
        if default_raw is not None and not isinstance(default_raw, str):
            raise PackageError(f"Binding '{name}': default must be a string")
        return IconifyBinding(
            node=node,
            size=size_raw,
            default=str(default_raw) if default_raw is not None else "",
        )

    if binding_type == BindingType.LIST:
        return _parse_list_binding(name, node, raw)

    if binding_type == BindingType.TRANSFORM:
        return _parse_transform_binding(name, node, raw)

    if binding_type == BindingType.CSS_CLASS:
        default_raw = raw.get("default", "")
        if not isinstance(default_raw, str):
            raise PackageError(f"Binding '{name}': default must be a string")
        return CssClassBinding(node=node, default=default_raw)

    return ColorBinding(
        node=node,
        attribute=str(raw.get("attribute", "fill")),
        default=str(raw.get("default", "#ffffff")),
    )


def _parse_list_binding(name: str, node: str, raw: dict[str, Any]) -> ListBinding:
    """Parse a ``list`` binding entry from the manifest.

    Parameters
    ----------
    name : str
        Binding name for error messages.
    node : str
        SVG element ID (already extracted by the caller).
    raw : dict[str, Any]
        Raw YAML mapping for this binding.

    Returns
    -------
    ListBinding
        A validated list binding dataclass.

    Raises
    ------
    PackageError
        If any field is missing or has an invalid value.
    """
    child_tag_raw = raw.get("child_tag", "tspan")
    if not isinstance(child_tag_raw, str) or not child_tag_raw.strip():
        raise PackageError(
            f"Binding '{name}': child_tag must be a non-empty string, "
            f"got {child_tag_raw!r}"
        )

    default_items: tuple[str, ...] = ()
    raw_items = raw.get("default_items")
    if raw_items is not None:
        if not isinstance(raw_items, list):
            raise PackageError(f"Binding '{name}': default_items must be a list")
        for i, item in enumerate(raw_items):
            if not isinstance(item, str):
                raise PackageError(
                    f"Binding '{name}': default_items[{i}] must be a string, "
                    f"got {item!r}"
                )
        default_items = tuple(raw_items)

    default_index_raw = raw.get("default_index", 0)
    default_index: int | None
    if default_index_raw is None:
        default_index = None
    elif not isinstance(default_index_raw, int) or isinstance(default_index_raw, bool):
        raise PackageError(
            f"Binding '{name}': default_index must be an integer or null, "
            f"got {default_index_raw!r}"
        )
    else:
        default_index = default_index_raw

    if (
        default_index is not None
        and default_index != -1
        and default_items
        and default_index >= len(default_items)
    ):
        raise PackageError(
            f"Binding '{name}': default_index {default_index} is out of range "
            f"for {len(default_items)} default_items"
        )

    active_attrs = _parse_attr_dict(name, raw, "active_attrs")
    inactive_attrs = _parse_attr_dict(name, raw, "inactive_attrs")

    separator_raw = raw.get("separator", "")
    if not isinstance(separator_raw, str):
        raise PackageError(
            f"Binding '{name}': separator must be a string, got {separator_raw!r}"
        )

    icon_size_raw = raw.get("icon_size", 16)
    if (
        not isinstance(icon_size_raw, int)
        or isinstance(icon_size_raw, bool)
        or icon_size_raw <= 0
    ):
        raise PackageError(
            f"Binding '{name}': icon_size must be a positive integer, "
            f"got {icon_size_raw!r}"
        )

    return ListBinding(
        node=node,
        child_tag=child_tag_raw,
        default_items=default_items,
        default_index=default_index,
        active_attrs=active_attrs,
        inactive_attrs=inactive_attrs,
        separator=separator_raw,
        icon_size=icon_size_raw,
    )


def _parse_transform_binding(name: str, node: str, raw: dict[str, Any]) -> TransformBinding:
    """Parse a ``transform`` binding entry from the manifest.

    Parameters
    ----------
    name : str
        Binding name for error messages.
    node : str
        SVG element ID (already extracted by the caller).
    raw : dict[str, Any]
        Raw YAML mapping for this binding.

    Returns
    -------
    TransformBinding
        A validated transform binding dataclass.

    Raises
    ------
    PackageError
        If any field is missing or has an invalid value.
    """
    default_val = raw.get("default", 0.0)
    if not isinstance(default_val, (int, float)):
        raise PackageError(f"Binding '{name}': default must be a number")
    default_float = float(default_val)
    if not 0.0 <= default_float <= 1.0:
        raise PackageError(f"Binding '{name}': default must be between 0.0 and 1.0")

    raw_transforms = raw.get("transforms")
    if raw_transforms is None:
        raise PackageError(f"Binding '{name}' missing 'transforms'")
    if not isinstance(raw_transforms, list) or len(raw_transforms) == 0:
        raise PackageError(f"Binding '{name}': transforms must be a non-empty list")

    transforms: list[RotateTransform] = []
    for i, t_raw in enumerate(raw_transforms):
        if not isinstance(t_raw, dict):
            raise PackageError(
                f"Binding '{name}': transforms[{i}] must be a mapping"
            )
        kind_raw = t_raw.get("kind")
        if kind_raw is None:
            raise PackageError(f"Binding '{name}': transforms[{i}] missing 'kind'")
        try:
            kind = TransformKind(kind_raw)
        except ValueError:
            valid_kinds = [k.value for k in TransformKind]
            raise PackageError(
                f"Binding '{name}': transforms[{i}] invalid kind '{kind_raw}'. "
                f"Valid kinds: {valid_kinds}"
            ) from None

        if kind == TransformKind.ROTATE:
            transforms.append(_parse_rotate_transform(name, i, t_raw))

    return TransformBinding(
        node=node,
        default=default_float,
        transforms=tuple(transforms),
    )


def _parse_rotate_transform(name: str, index: int, raw: dict[str, Any]) -> RotateTransform:
    """Parse a single rotate transform specification.

    Parameters
    ----------
    name : str
        Binding name for error messages.
    index : int
        Transform index within the list for error messages.
    raw : dict[str, Any]
        Raw YAML mapping for this transform entry.

    Returns
    -------
    RotateTransform
        A validated rotate transform dataclass.

    Raises
    ------
    PackageError
        If required fields are missing or invalid.
    """
    from_raw = raw.get("from", 0.0)
    if not isinstance(from_raw, (int, float)):
        raise PackageError(
            f"Binding '{name}': transforms[{index}] 'from' must be a number"
        )
    to_raw = raw.get("to", 360.0)
    if not isinstance(to_raw, (int, float)):
        raise PackageError(
            f"Binding '{name}': transforms[{index}] 'to' must be a number"
        )
    origin = raw.get("origin", "center")
    if not isinstance(origin, str):
        raise PackageError(
            f"Binding '{name}': transforms[{index}] 'origin' must be a string"
        )
    return RotateTransform(
        from_angle=float(from_raw),
        to_angle=float(to_raw),
        origin=origin,
    )


def _parse_attr_dict(
    binding_name: str, raw: dict[str, Any], field_name: str
) -> dict[str, str]:
    """Parse and validate an attribute dictionary from a binding entry.

    Parameters
    ----------
    binding_name : str
        Binding name for error messages.
    raw : dict[str, Any]
        Raw YAML mapping for the binding.
    field_name : str
        Key within *raw* to parse (e.g. ``"active_attrs"``).

    Returns
    -------
    dict[str, str]
        Validated attribute dictionary with string keys and values.

    Raises
    ------
    PackageError
        If the value is not a dict or contains non-string keys/values.
    """
    attrs_raw = raw.get(field_name)
    if attrs_raw is None:
        return {}
    if not isinstance(attrs_raw, dict):
        raise PackageError(
            f"Binding '{binding_name}': {field_name} must be a mapping"
        )
    for k, v in attrs_raw.items():
        if not isinstance(k, str):
            raise PackageError(
                f"Binding '{binding_name}': {field_name} key {k!r} must be a string"
            )
        if not isinstance(v, str):
            raise PackageError(
                f"Binding '{binding_name}': {field_name}[{k!r}] must be a string, "
                f"got {v!r}"
            )
    return dict(attrs_raw)


def _parse_event(raw: dict[str, Any], index: int) -> EventMapping:
    """Parse a single event mapping from the manifest.

    Parameters
    ----------
    raw : dict[str, Any]
        Raw YAML mapping for this event entry.
    index : int
        Positional index of the event in the manifest list, used for
        error messages.

    Returns
    -------
    EventMapping
        A validated event mapping dataclass.

    Raises
    ------
    PackageError
        If required keys are missing or values are invalid.
    """
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
    if max_duration_ms is not None and (
        not isinstance(max_duration_ms, int) or max_duration_ms <= 0
    ):
        raise PackageError(f"Event '{name}': max_duration_ms must be a positive integer")

    hold_ms = raw.get("hold_ms")
    if source in HOLD_SOURCES:
        if hold_ms is not None and (not isinstance(hold_ms, int) or hold_ms <= 0):
            raise PackageError(f"Event '{name}': hold_ms must be a positive integer")
    elif hold_ms is not None:
        raise PackageError(
            f"Event '{name}': hold_ms is only valid for key_hold/encoder_hold sources"
        )

    if source in HOLD_SOURCES and hold_ms is None:
        hold_ms = DEFAULT_HOLD_MS
    if source in _PRESS_RELEASE_SOURCES and max_duration_ms is None:
        max_duration_ms = DEFAULT_MAX_DURATION_MS

    accumulate = bool(raw.get("accumulate", False))
    accumulate_delay: float | None = None
    accumulate_max_steps: int | None = None

    if accumulate and source not in TURN_SOURCES:
        raise PackageError(
            f"Event '{name}': accumulate is only valid for "
            f"encoder_turn/encoder_press_turn sources"
        )

    raw_delay = raw.get("accumulate_delay")
    if raw_delay is not None:
        if not accumulate:
            raise PackageError(
                f"Event '{name}': accumulate_delay requires accumulate: true"
            )
        if not isinstance(raw_delay, (int, float)) or raw_delay <= 0:
            raise PackageError(
                f"Event '{name}': accumulate_delay must be a positive number"
            )
        accumulate_delay = float(raw_delay)

    raw_max_steps = raw.get("accumulate_max_steps")
    if raw_max_steps is not None:
        if not accumulate:
            raise PackageError(
                f"Event '{name}': accumulate_max_steps requires accumulate: true"
            )
        if (
            not isinstance(raw_max_steps, int)
            or isinstance(raw_max_steps, bool)
            or raw_max_steps < 1
        ):
            raise PackageError(
                f"Event '{name}': accumulate_max_steps must be a positive integer"
            )
        accumulate_max_steps = raw_max_steps

    return EventMapping(
        name=name,
        source=source,
        direction=direction,
        max_duration_ms=max_duration_ms,
        hold_ms=hold_ms,
        accumulate=accumulate,
        accumulate_delay=accumulate_delay,
        accumulate_max_steps=accumulate_max_steps,
    )


def _parse_spinner(raw: dict[str, Any]) -> SpinnerSpec:
    """Parse a spinner configuration from the manifest.

    Parameters
    ----------
    raw : dict[str, Any]
        Raw YAML mapping for the ``spinner`` section.

    Returns
    -------
    SpinnerSpec
        A validated spinner specification dataclass.

    Raises
    ------
    PackageError
        If the spinner type is missing/invalid or constraints are violated.
    """
    raw_type = raw.get("type")
    if raw_type is None:
        raise PackageError("Spinner missing 'type'")
    try:
        spinner_type = SpinnerType(raw_type)
    except ValueError:
        valid = [t.value for t in SpinnerType]
        raise PackageError(
            f"Invalid spinner type '{raw_type}'. Valid types: {valid}"
        ) from None

    node = raw.get("node")
    if spinner_type in (SpinnerType.ROTATION, SpinnerType.PULSE):
        if not node or not isinstance(node, str):
            raise PackageError(
                f"Spinner type '{raw_type}' requires a 'node' (SVG element ID)"
            )
    elif node is not None and not isinstance(node, str):
        raise PackageError("Spinner 'node' must be a string if provided")

    frames = raw.get("frames", DEFAULT_SPINNER_FRAMES)
    if not isinstance(frames, int) or isinstance(frames, bool) or frames < 2:
        raise PackageError("Spinner 'frames' must be an integer >= 2")

    interval_ms = raw.get("interval_ms", DEFAULT_SPINNER_INTERVAL_MS)
    if not isinstance(interval_ms, int) or isinstance(interval_ms, bool) or interval_ms < 10:
        raise PackageError("Spinner 'interval_ms' must be an integer >= 10")

    background_node = raw.get("background_node")
    if background_node is not None and not isinstance(background_node, str):
        raise PackageError("Spinner 'background_node' must be a string if provided")

    return SpinnerSpec(
        type=spinner_type,
        node=node,
        frames=frames,
        interval_ms=interval_ms,
        background_node=background_node,
    )


def _parse_region(name: str, raw: dict[str, Any]) -> Region:
    """Parse a single region from the manifest.

    Parameters
    ----------
    name : str
        Region name as it appears in the manifest ``regions`` mapping.
    raw : dict[str, Any]
        Raw YAML mapping containing ``x``, ``y``, ``width``, ``height``,
        and optionally ``events``.

    Returns
    -------
    Region
        A validated region dataclass.

    Raises
    ------
    PackageError
        If required geometry keys are missing or event names are invalid.
    """
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


def _load_manifest(pkg_dir: Path) -> dict[str, Any]:
    """Read and parse ``manifest.yaml`` from a package directory.

    Parameters
    ----------
    pkg_dir : Path
        Directory containing the ``.dui`` package.

    Returns
    -------
    dict[str, Any]
        Parsed manifest mapping.

    Raises
    ------
    PackageError
        If the manifest is missing, not valid YAML, or not a mapping.
    """
    manifest_path = pkg_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise PackageError(f"Missing manifest.yaml in {pkg_dir}")

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest: Any = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise PackageError(f"Invalid YAML in manifest: {exc}") from exc

    if not isinstance(manifest, dict):
        raise PackageError("manifest.yaml must be a YAML mapping")
    return manifest


def _parse_core_manifest(manifest: dict[str, Any]) -> tuple[str, PackageType, int, str]:
    """Validate and extract the required core manifest fields.

    Parameters
    ----------
    manifest : dict[str, Any]
        Parsed manifest mapping.

    Returns
    -------
    tuple[str, PackageType, int, str]
        ``(name, package_type, version, layout_file)``.

    Raises
    ------
    PackageError
        If any required field is missing or invalid.
    """
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

    layout_file = manifest.get("layout")
    if not layout_file or not isinstance(layout_file, str):
        raise PackageError("manifest.yaml missing or invalid 'layout'")

    return name, pkg_type, version, layout_file


def _parse_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate and extract optional metadata fields from the manifest.

    Parameters
    ----------
    manifest : dict[str, Any]
        Parsed manifest mapping.

    Returns
    -------
    dict[str, Any]
        Mapping of metadata field names to their validated values, suitable
        for splatting into the :class:`PackageSpec` constructor. Keys:
        ``description``, ``author``, ``license``, ``tags``, ``category``,
        ``url``, ``icon``, ``min_deux``, ``device``.

    Raises
    ------
    PackageError
        If any metadata field has an invalid type or value.
    """
    description = manifest.get("description")
    if description is not None and not isinstance(description, str):
        raise PackageError("'description' must be a string")

    author = manifest.get("author")
    if author is not None and not isinstance(author, str):
        raise PackageError("'author' must be a string")

    pkg_license = manifest.get("license")
    if pkg_license is not None and not isinstance(pkg_license, str):
        raise PackageError("'license' must be a string")

    tags: tuple[str, ...] = ()
    raw_tags = manifest.get("tags")
    if raw_tags is not None:
        if not isinstance(raw_tags, list):
            raise PackageError("'tags' must be a list")
        for tag in raw_tags:
            if not isinstance(tag, str) or not tag.strip():
                raise PackageError(f"Each tag must be a non-empty string, got {tag!r}")
        tags = tuple(raw_tags)

    category = manifest.get("category")
    if category is not None:
        if not isinstance(category, str):
            raise PackageError("'category' must be a string")
        if category not in VALID_CATEGORIES:
            raise PackageError(
                f"Invalid category '{category}'. "
                f"Valid categories: {sorted(VALID_CATEGORIES)}"
            )

    url = manifest.get("url")
    if url is not None and not isinstance(url, str):
        raise PackageError("'url' must be a string")

    icon = manifest.get("icon")
    if icon is not None and not isinstance(icon, str):
        raise PackageError("'icon' must be a string")

    min_deux = manifest.get("min_deux")
    if min_deux is not None and not isinstance(min_deux, str):
        raise PackageError("'min_deux' must be a string")

    device: tuple[str, ...] = ()
    raw_device = manifest.get("device")
    if raw_device is not None:
        if not isinstance(raw_device, list):
            raise PackageError("'device' must be a list")
        for d in raw_device:
            if not isinstance(d, str) or not d.strip():
                raise PackageError(
                    f"Each device must be a non-empty string, got {d!r}"
                )
        device = tuple(raw_device)

    return {
        "description": description,
        "author": author,
        "license": pkg_license,
        "tags": tags,
        "category": category,
        "url": url,
        "icon": icon,
        "min_deux": min_deux,
        "device": device,
    }


def _validate_binding_nodes(
    binding_name: str, binding: Binding, svg_ids: set[str]
) -> None:
    """Ensure that all SVG node references in a binding exist.

    Parameters
    ----------
    binding_name : str
        Name of the binding (for error messages).
    binding : Binding
        Parsed binding to validate.
    svg_ids : set[str]
        Set of element IDs available in the layout SVG.

    Raises
    ------
    PackageError
        If a referenced node is not present in *svg_ids*.
    """
    if isinstance(binding, ToggleBinding):
        if binding.node_on not in svg_ids:
            raise PackageError(
                f"Binding '{binding_name}' references node_on '{binding.node_on}' "
                f"which does not exist in the SVG. "
                f"Available ids: {sorted(svg_ids)}"
            )
        if binding.node_off not in svg_ids:
            raise PackageError(
                f"Binding '{binding_name}' references node_off '{binding.node_off}' "
                f"which does not exist in the SVG. "
                f"Available ids: {sorted(svg_ids)}"
            )
        return

    if binding.node not in svg_ids:
        raise PackageError(
            f"Binding '{binding_name}' references node '{binding.node}' "
            f"which does not exist in the SVG. "
            f"Available ids: {sorted(svg_ids)}"
        )
    if (
        isinstance(binding, ImageBinding)
        and binding.placeholder_node
        and binding.placeholder_node not in svg_ids
    ):
        raise PackageError(
            f"Binding '{binding_name}' references placeholder_node "
            f"'{binding.placeholder_node}' which does not exist in the SVG"
        )


def _parse_bindings(
    manifest: dict[str, Any], svg_ids: set[str]
) -> dict[str, Binding]:
    """Parse and validate the ``bindings`` section of the manifest.

    Parameters
    ----------
    manifest : dict[str, Any]
        Parsed manifest mapping.
    svg_ids : set[str]
        Set of element IDs available in the layout SVG, used to validate
        node references.

    Returns
    -------
    dict[str, Binding]
        Mapping of binding name to parsed :class:`Binding` instance.

    Raises
    ------
    PackageError
        If the section is malformed or any binding is invalid.
    """
    bindings: dict[str, Binding] = {}
    raw_bindings = manifest.get("bindings", {})
    if raw_bindings and not isinstance(raw_bindings, dict):
        raise PackageError("'bindings' must be a mapping")
    for binding_name, binding_raw in (raw_bindings or {}).items():
        if not isinstance(binding_raw, dict):
            raise PackageError(f"Binding '{binding_name}' must be a mapping")
        binding = _parse_binding(binding_name, binding_raw)
        _validate_binding_nodes(binding_name, binding, svg_ids)
        bindings[binding_name] = binding
    return bindings


def _parse_events(manifest: dict[str, Any]) -> list[EventMapping]:
    """Parse and validate the ``events`` section of the manifest.

    Parameters
    ----------
    manifest : dict[str, Any]
        Parsed manifest mapping.

    Returns
    -------
    list[EventMapping]
        Ordered list of validated :class:`EventMapping` instances.

    Raises
    ------
    PackageError
        If the section is malformed, an entry is invalid, or names duplicate.
    """
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
    return events


def _parse_regions(manifest: dict[str, Any]) -> list[Region]:
    """Parse and validate the ``regions`` section of the manifest.

    Parameters
    ----------
    manifest : dict[str, Any]
        Parsed manifest mapping.

    Returns
    -------
    list[Region]
        Ordered list of validated :class:`Region` instances.

    Raises
    ------
    PackageError
        If the section is malformed or any region is invalid.
    """
    regions: list[Region] = []
    raw_regions = manifest.get("regions", {})
    if raw_regions and not isinstance(raw_regions, dict):
        raise PackageError("'regions' must be a mapping")
    for region_name, region_raw in (raw_regions or {}).items():
        if not isinstance(region_raw, dict):
            raise PackageError(f"Region '{region_name}' must be a mapping")
        regions.append(_parse_region(region_name, region_raw))
    return regions


def _load_assets(pkg_dir: Path) -> dict[str, bytes]:
    """Load every file under ``<pkg_dir>/assets`` into memory.

    Parameters
    ----------
    pkg_dir : Path
        Package directory containing an optional ``assets`` subdirectory.

    Returns
    -------
    dict[str, bytes]
        Mapping of asset path (relative to ``assets/``, using ``/``
        separators on POSIX) to raw bytes. Empty if the directory is absent.
    """
    assets: dict[str, bytes] = {}
    assets_dir = pkg_dir / "assets"
    if assets_dir.is_dir():
        for asset_file in sorted(assets_dir.rglob("*")):
            if asset_file.is_file():
                rel = str(asset_file.relative_to(assets_dir))
                assets[rel] = asset_file.read_bytes()
    return assets


def _parse_and_validate_spinner(
    manifest: dict[str, Any], svg_ids: set[str], assets: dict[str, bytes]
) -> SpinnerSpec | None:
    """Parse the ``spinner`` section and validate referenced nodes/assets.

    Parameters
    ----------
    manifest : dict[str, Any]
        Parsed manifest mapping.
    svg_ids : set[str]
        Set of element IDs available in the layout SVG.
    assets : dict[str, bytes]
        Loaded asset catalog, used to verify custom spinner frames.

    Returns
    -------
    SpinnerSpec | None
        Validated spinner specification, or ``None`` if no spinner is
        configured.

    Raises
    ------
    PackageError
        If the spinner is malformed, references missing SVG ids, or its
        ``custom`` type lacks the required asset files.
    """
    raw_spinner = manifest.get("spinner")
    if raw_spinner is None:
        return None
    if not isinstance(raw_spinner, dict):
        raise PackageError("'spinner' must be a mapping")
    spinner = _parse_spinner(raw_spinner)

    if spinner.node is not None and spinner.node not in svg_ids:
        raise PackageError(
            f"Spinner references node '{spinner.node}' "
            f"which does not exist in the SVG. "
            f"Available ids: {sorted(svg_ids)}"
        )

    if spinner.background_node is not None and spinner.background_node not in svg_ids:
        raise PackageError(
            f"Spinner references background_node '{spinner.background_node}' "
            f"which does not exist in the SVG. "
            f"Available ids: {sorted(svg_ids)}"
        )

    if spinner.type == SpinnerType.CUSTOM:
        has_gif = "spinner.gif" in assets
        frame_keys = sorted(k for k in assets if k.startswith("spinner/frame_"))
        if not has_gif and not frame_keys:
            raise PackageError(
                "Spinner type 'custom' requires either 'assets/spinner.gif' "
                "or frame images in 'assets/spinner/' "
                "(e.g. 'spinner/frame_00.png', 'spinner/frame_01.png', ...)"
            )

    return spinner


def _check_unknown_keys(manifest: dict[str, Any], name: str, strict: bool) -> None:
    """Warn or fail on top-level keys that are not part of the schema.

    Parameters
    ----------
    manifest : dict[str, Any]
        Parsed manifest mapping.
    name : str
        Package name (for log/error messages).
    strict : bool
        When ``True``, raise on unknown keys; otherwise log a warning.

    Raises
    ------
    PackageError
        If unknown keys are present and *strict* is ``True``.
    """
    unknown_keys = set(manifest.keys()) - KNOWN_MANIFEST_KEYS
    if not unknown_keys:
        return
    if strict:
        raise PackageError(
            f"Package '{name}': unknown manifest keys: {sorted(unknown_keys)}"
        )
    logger.warning(
        "Package '%s': unknown manifest keys: %s", name, sorted(unknown_keys)
    )


def load_package(path: str | Path, *, strict: bool = True) -> PackageSpec:
    """Load a .dui package directory into a validated PackageSpec.

    Parameters
    ----------
    path
        Path to the ``.dui`` directory.
    strict : bool, default=True
        When ``True``, unknown manifest keys raise :exc:`PackageError`.
        Set to ``False`` for forward-compatible loading that only warns.

    Returns
    -------
    PackageSpec
        A frozen :class:`PackageSpec` ready to be used by
        :class:`~deux.dui.card.DuiCard` or
        :class:`~deux.dui.key.DuiKey`.

    Raises
    ------
    PackageError
        If the package is invalid or incomplete.
    """
    pkg_dir = Path(path)
    if not pkg_dir.is_dir():
        raise PackageError(f"Package path is not a directory: {pkg_dir}")

    manifest = _load_manifest(pkg_dir)
    name, pkg_type, version, layout_file = _parse_core_manifest(manifest)

    layout_path = pkg_dir / layout_file
    if not layout_path.exists():
        raise PackageError(f"Layout file not found: {layout_path}")
    svg_source = layout_path.read_text(encoding="utf-8")
    svg_ids = _find_svg_ids(svg_source)

    _check_unknown_keys(manifest, name, strict)

    metadata = _parse_metadata(manifest)
    bindings = _parse_bindings(manifest, svg_ids)
    events = _parse_events(manifest)
    regions = _parse_regions(manifest)
    assets = _load_assets(pkg_dir)
    spinner = _parse_and_validate_spinner(manifest, svg_ids, assets)

    logger.info(
        "Loaded .dui package '%s' (%s, %d bindings, %d events)",
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
        spinner=spinner,
        **metadata,
    )


def load_all_packages(directory: str | Path) -> dict[str, PackageSpec]:
    """Load all .dui packages from a directory.

    Parameters
    ----------
    directory
        Path to scan for ``.dui`` subdirectories.

    Returns
    -------
    dict[str, PackageSpec]
        A dict mapping package names to their specs.

    Raises
    ------
    PackageError
        If any package fails validation.
    """
    base = Path(directory)
    if not base.is_dir():
        raise PackageError(f"Not a directory: {base}")

    packages: dict[str, PackageSpec] = {}
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and entry.suffix == ".dui":
            spec = load_package(entry)
            packages[spec.name] = spec

    logger.info("Loaded %d .dui packages from %s", len(packages), base)
    return packages
