"""Media-focused preset cards."""

from __future__ import annotations

from ..ui.cards.stack import StackCard
from ..ui.controls.volume import VolumeSlider
from ..ui.elements.text import LargeText

__all__ = ["MediaCard"]


class MediaCard(StackCard):
    """A ready-to-use media card with a title display and volume slider.

    Combines a :class:`LargeText` element (showing the currently playing
    media) and a :class:`VolumeSlider` into a single :class:`StackCard`.
    Pressing the encoder toggles mute: the volume is set to 0 and the
    previous level is restored on the next press.

    All parameters are optional — sensible defaults are applied.

    Args:
        index: Card zone index (0–3).
        title: Initial media title text.  Defaults to ``"No Media"``.
        volume: Initial volume level.  Defaults to 50.
        volume_min: Minimum volume.  Defaults to 0.
        volume_max: Maximum volume.  Defaults to 100.

    Usage::

        from deckboard import MediaCard

        media = MediaCard(0, title="Bohemian Rhapsody", volume=75)
        media.title_text.set_text("Another One Bites the Dust")
        media.volume.set_value(60)
    """

    def __init__(
        self,
        index: int,
        *,
        title: str = "No Media",
        volume: float = 50,
        volume_min: float = 0,
        volume_max: float = 100,
    ) -> None:
        super().__init__(index)
        self._title_text = LargeText(title)
        self._volume = VolumeSlider(
            "Volume",
            value=volume,
            min_value=volume_min,
            max_value=volume_max,
        )
        self._muted = False
        self._saved_volume: float = volume

        self.add_element(self._title_text)
        self.add_element(self._volume, default=True)

    # -- Convenience accessors ---------------------------------------------

    @property
    def title_text(self) -> LargeText:
        """The large text element showing the current media title."""
        return self._title_text

    @property
    def volume(self) -> VolumeSlider:
        """The volume slider."""
        return self._volume

    @property
    def muted(self) -> bool:
        """Whether the volume is currently muted."""
        return self._muted

    # -- Mute control ------------------------------------------------------

    def toggle_mute(self) -> None:
        """Toggle mute on/off.

        When muting, the current volume is saved and set to 0.
        When unmuting, the saved volume is restored.  If the volume
        was changed while muted (e.g. via encoder turn), unmuting still
        restores the previously saved level.
        """
        if self._muted:
            self._volume.set_value(self._saved_volume)
            self._muted = False
        else:
            self._saved_volume = self._volume.value
            self._volume.set_value(0)
            self._muted = True
        self._dirty = True

    # -- Encoder interaction overrides -------------------------------------

    def handle_encoder_press(self) -> None:
        """Toggle mute when the encoder is pressed.

        Overrides the default :meth:`StackCard.handle_encoder_press`
        behaviour (which cycles active controls) because this card
        has only one slider.
        """
        self.toggle_mute()
