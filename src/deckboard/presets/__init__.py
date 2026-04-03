"""Preset controls and cards grouped by domain instead of by raw widget files."""

from __future__ import annotations

from .audio import BalanceSlider, EqualizerSlider, EqualizerWidget, VolumeSlider
from .climate import TemperatureSlider
from .lighting import BrightnessSlider, KelvinSlider
from .sensors import IconWidget, LargeDualValue, SmallDualValue

__all__ = [
    "BalanceSlider",
    "BrightnessSlider",
    "EqualizerSlider",
    "EqualizerWidget",
    "IconWidget",
    "KelvinSlider",
    "LargeDualValue",
    "SmallDualValue",
    "TemperatureSlider",
    "VolumeSlider",
]
