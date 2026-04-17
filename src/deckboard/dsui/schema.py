"""Data model for .dsui package manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PackageType(Enum):
    """Hardware target for a .dsui package."""

    TOUCH_STRIP_CARD = "TouchStripCard"
    KEY = "Key"


class BindingType(Enum):
    """Supported binding types for SVG node manipulation."""

    TEXT = "text"
    IMAGE = "image"
    VISIBILITY = "visibility"
    COLOR = "color"
    RANGE = "range"
    SLIDER = "slider"
    TOGGLE = "toggle"
    ICONIFY = "iconify"


class OverflowMode(Enum):
    """Text overflow handling strategy."""

    ELLIPSIS = "ellipsis"
    CLIP = "clip"


class ImageFit(Enum):
    """Image scaling strategy within the target node dimensions."""

    COVER = "cover"
    CONTAIN = "contain"
    FILL = "fill"


class RangeDirection(Enum):
    """Axis along which a range binding scales an SVG element."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass(frozen=True, slots=True)
class TextBinding:
    """Bind a value to a ``<text>`` SVG element's content.

    When *wrap* is ``True`` the renderer word-wraps the text into
    multiple ``<tspan>`` lines that each fit within *max_width* pixels.
    Font metrics are auto-detected from the SVG ``<text>`` element.
    If the wrapped text exceeds *max_height*, the last visible line is
    truncated according to *overflow*.
    """

    node: str
    default: str = ""
    max_width: int | None = None
    overflow: OverflowMode = OverflowMode.ELLIPSIS
    wrap: bool = False
    max_height: int | None = None
    line_height: float | None = None


@dataclass(frozen=True, slots=True)
class ImageBinding:
    """Bind a PIL Image to an <image> SVG element's href."""

    node: str
    fit: ImageFit = ImageFit.COVER
    placeholder_node: str | None = None


@dataclass(frozen=True, slots=True)
class VisibilityBinding:
    """Toggle the display attribute of an SVG element."""

    node: str
    default: bool = True


@dataclass(frozen=True, slots=True)
class ColorBinding:
    """Bind a colour value to an SVG element's fill or stroke."""

    node: str
    attribute: str = "fill"
    default: str = "#ffffff"


@dataclass(frozen=True, slots=True)
class RangeBinding:
    """Scale an SVG element's width or height proportional to a 0–1 value."""

    node: str
    default: float = 0.0
    direction: RangeDirection = RangeDirection.HORIZONTAL


@dataclass(frozen=True, slots=True)
class SliderBinding:
    """Translate an SVG element between two positions proportional to a 0–1 value."""

    node: str
    default: float = 0.0
    direction: RangeDirection = RangeDirection.HORIZONTAL
    min_pos: float = 0.0
    max_pos: float = 0.0


@dataclass(frozen=True, slots=True)
class ToggleBinding:
    """Switch between two SVG elements based on a boolean value.

    When the value is truthy, ``node_on`` is visible and ``node_off``
    is hidden.  When falsy, the opposite applies.
    """

    node_on: str
    node_off: str
    default: bool = False


@dataclass(frozen=True, slots=True)
class IconifyBinding:
    """Load an Iconify icon by name and embed it into an SVG ``<g>`` element.

    The icon name follows the Iconify convention ``<prefix>:<name>`` (for
    example ``line-md:home``).  Icons are fetched from
    ``https://api.iconify.design`` on first use and cached in-process.

    The resolved icon SVG is inserted as children of the target ``<g>``
    node, scaled to a ``size`` × ``size`` square.  Setting the binding
    value to ``None`` or an empty string removes any previously embedded
    icon from the node.
    """

    node: str
    size: int
    default: str = ""


Binding = (
    TextBinding
    | ImageBinding
    | VisibilityBinding
    | ColorBinding
    | RangeBinding
    | SliderBinding
    | ToggleBinding
    | IconifyBinding
)

# Valid event source names and their physical origins
VALID_SOURCES = frozenset(
    {
        "encoder_press",
        "encoder_release",
        "encoder_press_release",
        "encoder_turn",
        "encoder_press_turn",
        "encoder_hold",
        "key_press",
        "key_release",
        "key_press_release",
        "key_hold",
        "tap",
        "long_press",
    }
)

VALID_DIRECTIONS = frozenset({"left", "right"})

VALID_REGION_EVENTS = frozenset({"tap", "long_press"})


@dataclass(frozen=True, slots=True)
class EventMapping:
    """Map a physical input to a named semantic event."""

    name: str
    source: str
    direction: str | None = None
    max_duration_ms: int | None = None
    hold_ms: int | None = None


# Sources that require the hold_ms field.
HOLD_SOURCES = frozenset({"key_hold", "encoder_hold"})


@dataclass(frozen=True, slots=True)
class Region:
    """A touchscreen hit-test region for touch events."""

    name: str
    x: int
    y: int
    width: int
    height: int
    events: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PackageSpec:
    """Fully validated, immutable representation of a loaded .dsui package."""

    name: str
    type: PackageType
    version: int
    svg_source: str
    bindings: dict[str, Binding] = field(default_factory=dict)
    events: tuple[EventMapping, ...] = ()
    regions: tuple[Region, ...] = ()
    assets: dict[str, bytes] = field(default_factory=dict)
