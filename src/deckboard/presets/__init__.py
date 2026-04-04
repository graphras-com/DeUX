"""Preset controls and cards grouped by domain instead of by raw widget files."""

from __future__ import annotations

from .audio import BalanceSlider, EqualizerCard, EqualizerSlider, VolumeSlider
from .climate import TemperatureSlider
from .lighting import BrightnessSlider, KelvinSlider, LightCard
from .media import MediaCard
from .sensors import LargeDualValue, SmallDualValue, StatusCard

__all__ = [
    "BalanceSlider",
    "BrightnessSlider",
    "EqualizerCard",
    "EqualizerSlider",
    "KelvinSlider",
    "LargeDualValue",
    "LightCard",
    "MediaCard",
    "SmallDualValue",
    "StatusCard",
    "TemperatureSlider",
    "VolumeSlider",
]
