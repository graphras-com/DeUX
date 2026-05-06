"""Data model for .dui package manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PackageType(Enum):
    """Hardware target for a .dui package."""

    TOUCH_STRIP_CARD = "TouchStripCard"
    KEY = "Key"


class SpinnerType(Enum):
    """Animation strategy for the busy spinner."""

    ROTATION = "rotation"
    PULSE = "pulse"
    CUSTOM = "custom"


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
    LIST = "list"


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


_COLOR_ATTRIBUTES: frozenset[str] = frozenset({"fill", "stroke", "color"})


@dataclass(frozen=True, slots=True)
class ColorBinding:
    """Bind a colour value to an SVG element's fill, stroke, or color."""

    node: str
    attribute: str = "fill"
    default: str = "#ffffff"

    def __post_init__(self) -> None:
        if self.attribute not in _COLOR_ATTRIBUTES:
            msg = (
                f"Invalid color attribute {self.attribute!r}; "
                f"must be one of {sorted(_COLOR_ATTRIBUTES)}"
            )
            raise ValueError(msg)


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


@dataclass(frozen=True, slots=True)
class ListBinding:
    """Render a dynamic list of items as repeated SVG child elements.

    Each item is either a plain text label or an Iconify icon reference
    (prefixed with ``icon:``).  The item at *default_index* receives
    *active_attrs*; all others receive *inactive_attrs*.  Setting the
    index to ``-1`` or ``None`` means no item is active — every item
    gets *inactive_attrs*.

    An optional *separator* string is inserted between items as an
    additional child element styled with *inactive_attrs*.

    Parameters
    ----------
    node : str
        ID of the parent SVG element (e.g. a ``<text>`` element).
    child_tag : str
        SVG element name generated for each item (default ``"tspan"``).
    default_items : tuple[str, ...]
        Initial list of item labels.  Prefix a label with ``"icon:"``
        to render an Iconify icon instead of text (e.g.
        ``"icon:mdi:home"``).
    default_index : int | None
        Initially active item index.  ``-1`` or ``None`` means no item
        is active.
    active_attrs : dict[str, str]
        SVG attributes applied to the active item (e.g.
        ``{"fill": "#ffffff", "font-weight": "bold"}``).
    inactive_attrs : dict[str, str]
        SVG attributes applied to every inactive item.
    separator : str
        Text inserted between consecutive items.  An empty string
        disables separators.
    icon_size : int
        Pixel size for Iconify icon items.
    """

    node: str
    child_tag: str = "tspan"
    default_items: tuple[str, ...] = ()
    default_index: int | None = 0
    active_attrs: dict[str, str] = field(default_factory=dict)
    inactive_attrs: dict[str, str] = field(default_factory=dict)
    separator: str = ""
    icon_size: int = 16


Binding = (
    TextBinding
    | ImageBinding
    | VisibilityBinding
    | ColorBinding
    | RangeBinding
    | SliderBinding
    | ToggleBinding
    | IconifyBinding
    | ListBinding
)

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


TURN_SOURCES = frozenset({"encoder_turn", "encoder_press_turn"})
"""Sources that support the ``accumulate`` option."""


@dataclass(frozen=True, slots=True)
class EventMapping:
    """Map a physical input to a named semantic event."""

    name: str
    source: str
    direction: str | None = None
    max_duration_ms: int | None = None
    hold_ms: int | None = None
    accumulate: bool = False
    accumulate_delay: float | None = None
    accumulate_max_steps: int | None = None


HOLD_SOURCES = frozenset({"key_hold", "encoder_hold"})

DEFAULT_MAX_DURATION_MS: int = 500
"""Default max press duration (ms) for ``*_press_release`` events."""

DEFAULT_HOLD_MS: int = 500
"""Default hold duration (ms) for ``*_hold`` events."""

DEFAULT_RELEASE_TURN_GRACE_MS: int = 150
"""Default suppression window (ms) after a press cycle that included a turn.

After releasing the encoder following a press during which one or more turns
occurred, plain ``encoder_turn`` events are ignored for this many milliseconds.
This debounces the very common ergonomic mistake of letting a finger continue
to nudge the dial as it lifts off, preventing a ``encoder_press_turn`` gesture
from accidentally bleeding into a ``encoder_turn`` event.
"""


@dataclass(frozen=True, slots=True)
class Region:
    """A touchscreen hit-test region for touch events."""

    name: str
    x: int
    y: int
    width: int
    height: int
    events: tuple[str, ...] = ()


DEFAULT_SPINNER_FRAMES: int = 12
"""Default number of frames in a spinner animation cycle."""

DEFAULT_SPINNER_INTERVAL_MS: int = 80
"""Default interval (ms) between spinner animation frames."""


@dataclass(frozen=True, slots=True)
class SpinnerSpec:
    """Configuration for a spinner animation.

    The spinner is started and stopped explicitly by the application
    via :meth:`~deckui.dui.card.DuiCard.start_busy` /
    :meth:`~deckui.dui.card.DuiCard.finish_busy` (and the equivalent
    methods on :class:`~deckui.dui.key.DuiKey`).  It provides visual
    feedback by cycling pre-rendered animation frames on the key or
    card panel.

    Parameters
    ----------
    type
        Animation strategy: ``rotation`` (rotate an SVG node),
        ``pulse`` (fade opacity), or ``custom`` (user-provided frames).
    node
        SVG element ID to animate (required for ``rotation`` and
        ``pulse``; ignored for ``custom``).
    frames
        Number of frames per animation cycle.
    interval_ms
        Milliseconds between frames.
    background_node
        Optional SVG element ID shown behind the spinner during busy
        state.  The node is made visible when the spinner is active and
        hidden at rest, but it is **not** animated (no rotation, pulse,
        or opacity changes are applied to it).  Ignored for ``custom``
        type spinners.
    """

    type: SpinnerType
    node: str | None = None
    frames: int = DEFAULT_SPINNER_FRAMES
    interval_ms: int = DEFAULT_SPINNER_INTERVAL_MS
    background_node: str | None = None


VALID_CATEGORIES = frozenset(
    {
        "media",
        "productivity",
        "system",
        "gaming",
        "social",
        "development",
        "utilities",
        "streaming",
        "home-automation",
        "communication",
    }
)
"""Controlled vocabulary for the ``category`` manifest field."""

KNOWN_MANIFEST_KEYS = frozenset(
    {
        "name",
        "type",
        "version",
        "layout",
        "description",
        "author",
        "license",
        "tags",
        "category",
        "url",
        "icon",
        "min_deckui",
        "device",
        "bindings",
        "events",
        "regions",
        "spinner",
    }
)
"""All recognised top-level keys in a manifest.yaml file."""


@dataclass(frozen=True, slots=True)
class PackageSpec:
    """Fully validated, immutable representation of a loaded .dui package."""

    name: str
    type: PackageType
    version: int
    svg_source: str
    bindings: dict[str, Binding] = field(default_factory=dict)
    events: tuple[EventMapping, ...] = ()
    regions: tuple[Region, ...] = ()
    assets: dict[str, bytes] = field(default_factory=dict)
    spinner: SpinnerSpec | None = None
    description: str | None = None
    author: str | None = None
    license: str | None = None
    tags: tuple[str, ...] = ()
    category: str | None = None
    url: str | None = None
    icon: str | None = None
    min_deckui: str | None = None
    device: tuple[str, ...] = ()
