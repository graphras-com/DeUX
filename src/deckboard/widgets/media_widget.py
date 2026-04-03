"""MediaWidget — pre-configured TouchPanel with media title and volume control."""

from __future__ import annotations

from .text import LargeText
from .touch_panel import TouchPanel
from .volume import VolumeSlider


class MediaWidget(TouchPanel):
    """A ready-to-use media widget with a title display and volume slider.

    Combines a :class:`LargeText` element (showing the currently playing
    media) and a :class:`VolumeSlider` into a single :class:`TouchPanel`.
    Pressing the dial toggles mute: the volume is set to 0 and the
    previous level is restored on the next press.

    All parameters are optional — sensible defaults are applied.

    Args:
        index: Widget zone index (0–3).
        title: Initial media title text.  Defaults to ``"No Media"``.
        volume: Initial volume level.  Defaults to 50.

    Usage::

        from deckboard.widgets import MediaWidget

        media = MediaWidget(0, title="Bohemian Rhapsody", volume=75)
        media.title_text.set_text("Another One Bites the Dust")
        media.volume.set_value(60)
    """

    def __init__(
        self,
        index: int,
        *,
        title: str = "No Media",
        volume: float = 50,
    ) -> None:
        super().__init__(index)
        self._title_text = LargeText(title)
        self._volume = VolumeSlider("Volume", value=volume)
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
        was changed while muted (e.g. via dial turn), unmuting still
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

    # -- Dial interaction overrides ----------------------------------------

    def handle_dial_press(self) -> None:
        """Toggle mute when the dial is pressed.

        Overrides the default :meth:`TouchPanel.handle_dial_press`
        behaviour (which cycles active sliders) because this widget
        has only one slider.
        """
        self.toggle_mute()
