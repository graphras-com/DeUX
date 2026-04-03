"""Ready-to-use slider / progressbar widgets for the Stream Deck+ touchscreen."""

from __future__ import annotations

from .balance import BalanceSlider
from .brightness import BrightnessSlider
from .equalizer import EqualizerSlider
from .icon_widget import IconWidget
from .kelvin import KelvinSlider
from .slider import LargeSlider, Slider, SmallSlider
from .slider_widget import SliderWidget
from .temperature import TemperatureSlider
from .volume import VolumeSlider

__all__ = [
    "BalanceSlider",
    "BrightnessSlider",
    "EqualizerSlider",
    "IconWidget",
    "KelvinSlider",
    "LargeSlider",
    "Slider",
    "SliderWidget",
    "SmallSlider",
    "TemperatureSlider",
    "VolumeSlider",
]
