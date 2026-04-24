"""Declarative UI packages for deckui (.dui).

Load SVG + YAML packages and use them as touchscreen cards or physical keys
without writing any Python rendering code.

Examples
--------
::

    from deckui.dsui import DsuiCard, load_package

    spec = load_package("./AudioCard.dui")
    card = DsuiCard(spec)
    card.set("artist", "Ash Walker")

    @card.on("toggle_play_pause")
    async def handle():
        ...
"""

from __future__ import annotations

from .card import DsuiCard
from .event_map import EventMap
from .iconify import IconifyError, fetch_icon
from .iconify import clear_cache as clear_iconify_cache
from .key import DsuiKey
from .loader import PackageError, load_all_packages, load_package
from .schema import (
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
    SliderBinding,
    TextBinding,
    ToggleBinding,
    VisibilityBinding,
)
from .svg_renderer import SvgRenderer

__all__ = [
    "Binding",
    "BindingType",
    "ColorBinding",
    "DsuiCard",
    "DsuiKey",
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
    "SliderBinding",
    "SvgRenderer",
    "TextBinding",
    "ToggleBinding",
    "VisibilityBinding",
    "clear_iconify_cache",
    "fetch_icon",
    "load_all_packages",
    "load_package",
]
