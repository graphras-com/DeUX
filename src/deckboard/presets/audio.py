"""Audio-focused preset controls and cards."""

from __future__ import annotations

from ..widgets.balance import BalanceSlider
from ..widgets.equalizer import EqualizerSlider
from ..widgets.equalizer_widget import EqualizerCard
from ..widgets.volume import VolumeSlider

__all__ = ["BalanceSlider", "EqualizerCard", "EqualizerSlider", "VolumeSlider"]
