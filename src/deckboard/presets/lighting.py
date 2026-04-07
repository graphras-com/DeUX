"""Lighting-focused preset controls and cards."""

from __future__ import annotations

from ..ui.controls.brightness import BrightnessSlider
from ..ui.controls.kelvin import KelvinSlider
from ..ui.cards.stack import StackCard

__all__ = ["BrightnessSlider", "KelvinSlider", "LightCard"]


class LightCard(StackCard):
    """A ready-to-use light control card with brightness and kelvin.

    Combines one :class:`BrightnessSlider` (on top) and one
    :class:`KelvinSlider` (below) into a single :class:`StackCard`.
    The Brightness slider is the default active slider.

    All parameters are optional — sensible defaults are applied.

    Args:
        index: Card zone index (0–3).
        brightness: Initial brightness value (0–100).  Defaults to 100.
        kelvin: Initial colour temperature in Kelvin.  Defaults to 4000.
        brightness_min: Minimum brightness.  Defaults to 0.
        brightness_max: Maximum brightness.  Defaults to 100.
        kelvin_min: Minimum colour temperature in Kelvin.  Defaults to 2000.
        kelvin_max: Maximum colour temperature in Kelvin.  Defaults to 6500.

    Usage::

        from deckboard import LightCard

        light = LightCard(0)
        light.brightness.set_value(80)
        light.kelvin.set_value(3200)
    """

    def __init__(
        self,
        index: int,
        *,
        brightness: float = 100,
        kelvin: float = 4000,
        brightness_min: float = 0,
        brightness_max: float = 100,
        kelvin_min: float = 2000,
        kelvin_max: float = 6500,
    ) -> None:
        super().__init__(index)
        self._brightness = BrightnessSlider(
            "Brightness",
            value=brightness,
            min_value=brightness_min,
            max_value=brightness_max,
        )
        self._kelvin = KelvinSlider(
            "Kelvin",
            value=kelvin,
            min_value=kelvin_min,
            max_value=kelvin_max,
        )

        self.add_element(self._brightness, default=True)
        self.add_element(self._kelvin)

    # -- Convenience accessors ---------------------------------------------

    @property
    def brightness(self) -> BrightnessSlider:
        """The Brightness slider."""
        return self._brightness

    @property
    def kelvin(self) -> KelvinSlider:
        """The Kelvin (colour temperature) slider."""
        return self._kelvin
