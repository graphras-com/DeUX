"""Audio-focused preset controls and cards."""

from __future__ import annotations

from ..ui.controls.balance import BalanceSlider
from ..ui.controls.equalizer import EqualizerSlider
from ..ui.controls.volume import VolumeSlider
from ..ui.cards.stack import StackCard

__all__ = ["BalanceSlider", "EqualizerCard", "EqualizerSlider", "VolumeSlider"]


class EqualizerCard(StackCard):
    """A ready-to-use equalizer card with sub, bass, treble, and balance.

    Combines three :class:`EqualizerSlider` bands (Sub, Bass, Treble) and
    one :class:`BalanceSlider` into a single :class:`StackCard`.  The Sub
    slider is the default active slider.

    All parameters are optional — sensible defaults are applied.

    Each EQ band accepts its own ``*_min`` / ``*_max`` range.  The
    ``eq_min`` / ``eq_max`` shorthand sets the same range for all three
    bands but is overridden by any per-band value.

    Args:
        index: Card zone index (0–3).
        sub: Initial Sub value.  Defaults to 0.
        bass: Initial Bass value.  Defaults to 0.
        treble: Initial Treble value.  Defaults to 0.
        balance: Initial Balance value.  Defaults to 50 (centre).
        eq_min: Shared minimum for all EQ bands.  Defaults to 0.
        eq_max: Shared maximum for all EQ bands.  Defaults to 100.
        sub_min: Minimum for the Sub band (overrides *eq_min*).
        sub_max: Maximum for the Sub band (overrides *eq_max*).
        bass_min: Minimum for the Bass band (overrides *eq_min*).
        bass_max: Maximum for the Bass band (overrides *eq_max*).
        treble_min: Minimum for the Treble band (overrides *eq_min*).
        treble_max: Maximum for the Treble band (overrides *eq_max*).
        balance_min: Minimum value for the balance slider.  Defaults to 0.
        balance_max: Maximum value for the balance slider.  Defaults to 100.

    Usage::

        from deckboard import EqualizerCard

        eq = EqualizerCard(0)
        eq.sub.set_value(75)
        eq.bass.set_value(60)
        eq.treble.set_value(40)
        eq.balance.set_value(50)
    """

    def __init__(
        self,
        index: int,
        *,
        sub: float = 0,
        bass: float = 0,
        treble: float = 0,
        balance: float = 50,
        eq_min: float = 0,
        eq_max: float = 100,
        sub_min: float | None = None,
        sub_max: float | None = None,
        bass_min: float | None = None,
        bass_max: float | None = None,
        treble_min: float | None = None,
        treble_max: float | None = None,
        balance_min: float = 0,
        balance_max: float = 100,
    ) -> None:
        super().__init__(index)
        self._sub = EqualizerSlider(
            "Sub",
            value=sub,
            min_value=sub_min if sub_min is not None else eq_min,
            max_value=sub_max if sub_max is not None else eq_max,
        )
        self._bass = EqualizerSlider(
            "Bass",
            value=bass,
            min_value=bass_min if bass_min is not None else eq_min,
            max_value=bass_max if bass_max is not None else eq_max,
        )
        self._treble = EqualizerSlider(
            "Treble",
            value=treble,
            min_value=treble_min if treble_min is not None else eq_min,
            max_value=treble_max if treble_max is not None else eq_max,
        )
        self._balance = BalanceSlider(
            "Balance",
            value=balance,
            min_value=balance_min,
            max_value=balance_max,
        )

        self.add_element(self._sub, default=True)
        self.add_element(self._bass)
        self.add_element(self._treble)
        self.add_element(self._balance)

    # -- Convenience accessors ---------------------------------------------

    @property
    def sub(self) -> EqualizerSlider:
        """The Sub equalizer slider."""
        return self._sub

    @property
    def bass(self) -> EqualizerSlider:
        """The Bass equalizer slider."""
        return self._bass

    @property
    def treble(self) -> EqualizerSlider:
        """The Treble equalizer slider."""
        return self._treble

    @property
    def balance(self) -> BalanceSlider:
        """The Balance slider."""
        return self._balance

    # -- Range setters -----------------------------------------------------

    def set_sub_range(self, min_value: float, max_value: float) -> None:
        """Set the min/max range for the Sub band slider."""
        self._sub.set_range(min_value, max_value)

    def set_bass_range(self, min_value: float, max_value: float) -> None:
        """Set the min/max range for the Bass band slider."""
        self._bass.set_range(min_value, max_value)

    def set_treble_range(self, min_value: float, max_value: float) -> None:
        """Set the min/max range for the Treble band slider."""
        self._treble.set_range(min_value, max_value)

    def set_balance_range(self, min_value: float, max_value: float) -> None:
        """Set the min/max range for the balance slider.

        The current value is re-clamped to the new range and the card
        is marked dirty.
        """
        self._balance.set_range(min_value, max_value)
