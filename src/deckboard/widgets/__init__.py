"""Ready-to-use slider / progressbar widgets for the Stream Deck+ touchscreen."""

from __future__ import annotations

from .balance import BalanceSlider
from .brightness import BrightnessSlider
from .equalizer import EqualizerSlider
from .kelvin import KelvinSlider
from .slider import LargeSlider, Slider, SmallSlider
from .temperature import TemperatureSlider
from .volume import VolumeSlider

__all__ = [
    "BalanceSlider",
    "BrightnessSlider",
    "EqualizerSlider",
    "KelvinSlider",
    "LargeSlider",
    "Slider",
    "SmallSlider",
    "TemperatureSlider",
    "VolumeSlider",
]
