"""Ready-to-use widgets and sub-elements for the Stream Deck+ touchscreen."""

from __future__ import annotations

from .balance import BalanceSlider
from .brightness import BrightnessSlider
from .dual_value import LargeDualValue, SmallDualValue
from .equalizer import EqualizerSlider
from .equalizer_widget import EqualizerWidget
from .icon_widget import IconWidget
from .kelvin import KelvinSlider
from .slider import LargeSlider, Slider, SmallSlider
from .slider_widget import SliderWidget
from .temperature import TemperatureSlider
from .text import LargeText, SmallText
from .touch_panel import TouchPanel
from .volume import VolumeSlider

__all__ = [
    "BalanceSlider",
    "BrightnessSlider",
    "EqualizerSlider",
    "EqualizerWidget",
    "IconWidget",
    "KelvinSlider",
    "LargeDualValue",
    "LargeSlider",
    "LargeText",
    "Slider",
    "SliderWidget",
    "SmallDualValue",
    "SmallSlider",
    "SmallText",
    "TemperatureSlider",
    "TouchPanel",
    "VolumeSlider",
]
