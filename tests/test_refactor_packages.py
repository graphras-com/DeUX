"""Tests for the new runtime, ui, preset, and integration package surfaces."""

from __future__ import annotations

import pytest

import deckboard


class TestRuntimePackage:
    def test_runtime_deck_reexports(self):
        from deckboard.runtime.deck import Deck, DeckError, _KEY_COUNT

        assert Deck is deckboard.Deck
        assert DeckError is deckboard.DeckError
        assert _KEY_COUNT == 8


class TestUiSubpackages:
    def test_cards_lazy_exports(self):
        import deckboard.ui.cards as cards

        assert cards.Card is deckboard.Card
        assert cards.StackCard is deckboard.StackCard
        assert cards.StatusCard is deckboard.StatusCard

    def test_cards_unknown_attribute_raises(self):
        import deckboard.ui.cards as cards

        with pytest.raises(AttributeError):
            _ = cards.Missing

    def test_controls_lazy_exports(self):
        import deckboard.ui.controls as controls

        assert controls.Control is deckboard.Control
        assert controls.RangeControl is deckboard.RangeControl
        assert controls.Slider is deckboard.Slider
        assert controls.LargeSlider is deckboard.LargeSlider
        assert controls.SmallSlider is deckboard.SmallSlider

    def test_controls_unknown_attribute_raises(self):
        import deckboard.ui.controls as controls

        with pytest.raises(AttributeError):
            _ = controls.Missing

    def test_elements_lazy_exports(self):
        import deckboard.ui.elements as elements

        assert elements.Element is deckboard.Element
        assert elements.LargeText is deckboard.LargeText
        assert elements.SmallText is deckboard.SmallText
        assert elements.LargeDualValue is deckboard.LargeDualValue
        assert elements.SmallDualValue is deckboard.SmallDualValue

    def test_elements_unknown_attribute_raises(self):
        import deckboard.ui.elements as elements

        with pytest.raises(AttributeError):
            _ = elements.Missing


class TestPresetPackages:
    def test_audio_presets_importable(self):
        from deckboard.presets.audio import (
            BalanceSlider,
            EqualizerSlider,
            EqualizerWidget,
            VolumeSlider,
        )

        assert VolumeSlider is deckboard.VolumeSlider
        assert EqualizerSlider is deckboard.EqualizerSlider
        assert BalanceSlider is deckboard.BalanceSlider
        assert EqualizerWidget is deckboard.EqualizerWidget

    def test_lighting_presets_importable(self):
        from deckboard.presets.lighting import BrightnessSlider, KelvinSlider

        assert BrightnessSlider is deckboard.BrightnessSlider
        assert KelvinSlider is deckboard.KelvinSlider

    def test_climate_presets_importable(self):
        from deckboard.presets.climate import TemperatureSlider

        assert TemperatureSlider is deckboard.TemperatureSlider

    def test_sensor_presets_importable(self):
        from deckboard.presets.sensors import IconWidget, LargeDualValue, SmallDualValue

        assert IconWidget is deckboard.IconWidget
        assert LargeDualValue is deckboard.LargeDualValue
        assert SmallDualValue is deckboard.SmallDualValue

    def test_presets_package_importable(self):
        import deckboard.presets as presets

        assert presets.VolumeSlider is deckboard.VolumeSlider
        assert presets.BrightnessSlider is deckboard.BrightnessSlider
        assert presets.TemperatureSlider is deckboard.TemperatureSlider


class TestIntegrationsPackage:
    def test_capability_profile_for_known_domain(self):
        from deckboard.integrations import EntityProfile, capability_profile

        profile = capability_profile("light")
        assert isinstance(profile, EntityProfile)
        assert profile.domain == "light"
        assert profile.supports_toggle is True
        assert profile.supports_range is True
        assert profile.supports_mode is True

    def test_capability_profile_for_unknown_domain(self):
        from deckboard.integrations.homeassistant import capability_profile

        profile = capability_profile("custom")
        assert profile.domain == "custom"
        assert profile.supports_toggle is False
