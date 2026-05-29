"""Declarative UI packages for deux (.dui).

Load SVG + YAML packages and use them as touchscreen cards or physical keys
without writing any Python rendering code.

Examples
--------
::

    from deux import DuiCard, DuiKey

    # Resolve by name — uses the built-in DUI repository
    card = DuiCard("DashboardCard")
    key  = DuiKey("IconKey")
    key.set("label", "Power")

    @card.on("toggle_play_pause")
    async def handle():
        ...

    # Add a custom search path for your own packages
    from deux import add_dui_path
    add_dui_path("~/my-dui-packages")
"""

from __future__ import annotations

from .animator import SpinnerAnimator
from .card import DuiCard
from .event_map import EventMap
from .iconify import IconifyError, fetch_icon, prefetch_icons
from .iconify import clear_cache as clear_iconify_cache
from .key import DuiKey
from .loader import PackageError, load_all_packages, load_package
from .repository import (
    DuiRepository,
    add_dui_path,
    clear_dui_cache,
    list_dui_packages,
    remove_dui_path,
    resolve_dui,
)
from .schema import (
    VALID_CATEGORIES,
    Binding,
    BindingType,
    ColorBinding,
    CssClassBinding,
    EventMapping,
    IconifyBinding,
    ImageBinding,
    ImageFit,
    OverflowMode,
    PackageSpec,
    PackageType,
    RangeBinding,
    RangeDirection,
    Region,
    RotateTransform,
    SliderBinding,
    SpinnerSpec,
    TextBinding,
    ToggleBinding,
    TransformBinding,
    TransformKind,
    VisibilityBinding,
)
from .spinner import (
    SPINNER_FRAME_COUNT,
    SPINNER_INTERVAL_MS,
)
from .spinner import (
    clear_cache as clear_spinner_cache,
)
from .spinner import (
    get_frames as get_spinner_frames,
)
from .svg_renderer import SvgRenderer

__all__ = [
    "Binding",
    "BindingType",
    "ColorBinding",
    "CssClassBinding",
    "DuiCard",
    "DuiKey",
    "DuiRepository",
    "EventMap",
    "EventMapping",
    "IconifyBinding",
    "IconifyError",
    "ImageBinding",
    "ImageFit",
    "OverflowMode",
    "PackageError",
    "PackageSpec",
    "PackageType",
    "RangeBinding",
    "RangeDirection",
    "Region",
    "RotateTransform",
    "SliderBinding",
    "SPINNER_FRAME_COUNT",
    "SPINNER_INTERVAL_MS",
    "SpinnerAnimator",
    "SpinnerSpec",
    "SvgRenderer",
    "TextBinding",
    "ToggleBinding",
    "TransformBinding",
    "TransformKind",
    "VALID_CATEGORIES",
    "VisibilityBinding",
    "add_dui_path",
    "clear_dui_cache",
    "clear_iconify_cache",
    "clear_spinner_cache",
    "fetch_icon",
    "get_spinner_frames",
    "list_dui_packages",
    "load_all_packages",
    "load_package",
    "prefetch_icons",
    "remove_dui_path",
    "resolve_dui",
]
