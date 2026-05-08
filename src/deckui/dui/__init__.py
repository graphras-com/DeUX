"""Declarative UI packages for deckui (.dui).

Load SVG + YAML packages and use them as touchscreen cards or physical keys
without writing any Python rendering code.

Examples
--------
::

    from deckui.dui import DuiCard, load_package

    spec = load_package("./AudioCard.dui")
    card = DuiCard(spec)
    card.set("artist", "Ash Walker")

    @card.on("toggle_play_pause")
    async def handle():
        ...
"""

from __future__ import annotations

from .animator import SpinnerAnimator
from .card import DuiCard
from .event_map import EventMap
from .iconify import IconifyError, fetch_icon
from .iconify import clear_cache as clear_iconify_cache
from .key import DuiKey
from .loader import PackageError, load_all_packages, load_package
from .schema import (
    VALID_CATEGORIES,
    Binding,
    BindingType,
    ColorBinding,
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
    SpinnerType,
    TextBinding,
    ToggleBinding,
    TransformBinding,
    TransformKind,
    VisibilityBinding,
)
from .spinner import SpinnerFrames
from .svg_renderer import SvgRenderer

__all__ = [
    "Binding",
    "BindingType",
    "ColorBinding",
    "DuiCard",
    "DuiKey",
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
    "SpinnerAnimator",
    "SpinnerFrames",
    "SpinnerSpec",
    "SpinnerType",
    "SvgRenderer",
    "TextBinding",
    "ToggleBinding",
    "TransformBinding",
    "TransformKind",
    "VALID_CATEGORIES",
    "VisibilityBinding",
    "clear_iconify_cache",
    "fetch_icon",
    "load_all_packages",
    "load_package",
]
