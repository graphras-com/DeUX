"""Interactive control exports for deckboard UI composition."""

from __future__ import annotations

from .base import Control

__all__ = ["Control", "LargeSlider", "RangeControl", "Slider", "SmallSlider"]


def __getattr__(name: str):
    if name in {"LargeSlider", "RangeControl", "Slider", "SmallSlider"}:
        from .range import LargeSlider, RangeControl, Slider, SmallSlider

        return {
            "LargeSlider": LargeSlider,
            "RangeControl": RangeControl,
            "Slider": Slider,
            "SmallSlider": SmallSlider,
        }[name]
    raise AttributeError(name)
