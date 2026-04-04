"""Equalizer card preset with EQ bands and balance."""

from __future__ import annotations

from .balance import BalanceSlider
from .equalizer import EqualizerSlider
from .touch_panel import StackCard


class EqualizerCard(StackCard):
    """A ready-to-use equalizer card with sub, bass, treble, and balance.

    Combines three :class:`EqualizerSlider` bands (Sub, Bass, Treble) and
    one :class:`BalanceSlider` into a single :class:`StackCard`.  The Sub
    slider is the default active slider.

    All parameters are optional — sensible defaults are applied.

    Args:
        index: Card zone index (0–3).
        sub: Initial Sub value.  Defaults to 0.
        bass: Initial Bass value.  Defaults to 0.
        treble: Initial Treble value.  Defaults to 0.
        balance: Initial Balance value.  Defaults to 50 (centre).

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
    ) -> None:
        super().__init__(index)
        self._sub = EqualizerSlider("Sub", value=sub)
        self._bass = EqualizerSlider("Bass", value=bass)
        self._treble = EqualizerSlider("Treble", value=treble)
        self._balance = BalanceSlider("Balance", value=balance)

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
