"""Home Assistant–style media card with album art, metadata, and volume bar."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from ..render.fonts import get_font, get_small_font
from ..render.metrics import PANEL_HEIGHT, PANEL_WIDTH
from ..runtime.events import AsyncHandler
from ..ui.cards.base import Card

if TYPE_CHECKING:
    from ..render.icons import IconManager

logger = logging.getLogger(__name__)

__all__ = ["HaMediaCard"]

# ── Volume bar layout constants ──────────────────────────────────────────

_VOL_BAR_HEIGHT = 5
_VOL_BAR_Y = PANEL_HEIGHT - _VOL_BAR_HEIGHT
_VOL_BAR_COLOR = "#68b1ff"

# ── Text colours ─────────────────────────────────────────────────────────

_ARTIST_COLOR = "#69b1ff"
_TITLE_COLOR = "#f8ab3c"
_STATE_COLOR = "#69b1ff"
_MUTE_ICON_COLOR = "#ffffff"

# ── Mute icon layout constants ───────────────────────────────────────

_MUTE_ICON_SIZE = 16
_MUTE_ICON_RIGHT_MARGIN = 5
_MUTE_ICON_Y = 66
_STATE_TEXT_Y = 52

# ── Gradient mask (pre-built once) ───────────────────────────────────────

_gradient_mask: Image.Image | None = None


def _draw_mute_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    """Draw a speaker-off (muted) icon using PIL drawing primitives.

    The icon consists of a speaker body (polygon), a cone (polygon),
    and an "×" mark to indicate muted.  All parts are drawn at *size*
    pixels inside a bounding box starting at (*x*, *y*).

    Args:
        draw: The :class:`~PIL.ImageDraw.ImageDraw` context.
        x: Left edge of the icon bounding box.
        y: Top edge of the icon bounding box.
        size: Width and height of the icon in pixels.
    """
    s = size / 16.0  # scale factor relative to a 16×16 design grid

    # Speaker body (rectangular part)
    draw.rectangle(
        (
            int(x + 1 * s),
            int(y + 5 * s),
            int(x + 4 * s),
            int(y + 11 * s),
        ),
        fill=_MUTE_ICON_COLOR,
    )

    # Speaker cone (triangular part)
    draw.polygon(
        [
            (int(x + 4 * s), int(y + 5 * s)),
            (int(x + 8 * s), int(y + 1 * s)),
            (int(x + 8 * s), int(y + 15 * s)),
            (int(x + 4 * s), int(y + 11 * s)),
        ],
        fill=_MUTE_ICON_COLOR,
    )

    # "×" mark (two diagonal lines)
    lw = max(1, int(1.5 * s))
    draw.line(
        [(int(x + 10 * s), int(y + 4 * s)), (int(x + 15 * s), int(y + 12 * s))],
        fill=_MUTE_ICON_COLOR,
        width=lw,
    )
    draw.line(
        [(int(x + 15 * s), int(y + 4 * s)), (int(x + 10 * s), int(y + 12 * s))],
        fill=_MUTE_ICON_COLOR,
        width=lw,
    )


def _build_gradient_mask() -> Image.Image:
    """Build the left-to-right transparency gradient for the entity picture.

    The gradient covers roughly the left half of the panel, ramping from
    fully transparent on the far left to fully opaque black.  The right
    half is solid black so text is always readable.

    Gradient stops (normalised to the panel width):

    * ``0%`` → alpha **0** (album art fully visible)
    * ``~30%`` → alpha **173** (68 % black overlay)
    * ``~53%`` → alpha **255** (fully opaque black)
    * ``53 %–100 %`` → alpha **255** (stays solid black)
    """
    global _gradient_mask  # noqa: PLW0603
    if _gradient_mask is not None:
        return _gradient_mask

    mask = Image.new("L", (PANEL_WIDTH, PANEL_HEIGHT), 0)
    # The gradient occupies roughly 53 % of the panel width; beyond
    # that the mask is fully opaque so text draws on pure black.
    grad_end = 0.53
    mid_stop = 0.30  # 58 % of grad_end ≈ 0.30 of panel
    for x in range(PANEL_WIDTH):
        t = x / max(PANEL_WIDTH - 1, 1)
        if t >= grad_end:
            alpha = 255
        elif t < mid_stop:
            alpha = int(t / mid_stop * 173)
        else:
            alpha = int(173 + (t - mid_stop) / (grad_end - mid_stop) * (255 - 173))
        for y in range(PANEL_HEIGHT):
            mask.putpixel((x, y), alpha)

    _gradient_mask = mask
    return _gradient_mask


class HaMediaCard(Card):
    """A Home Assistant–style media card with album art and volume bar.

    Renders an entity picture (album art) on the left with a
    transparency gradient, plus artist name, media title, playback
    state, and a thin volume bar at the bottom.

    **Emit-only interaction model**

    Encoder gestures do **not** modify the card's display state
    directly.  Instead, each gesture emits a callback that the
    integration layer should handle — typically by calling the
    backend and then updating the card with the confirmed state
    via :meth:`set_volume`, :meth:`set_state`, etc.

    * **Turn** — emits :meth:`on_volume_change` with the *requested*
      volume.  The card's volume is unchanged.
    * **Short press** (press and release within the hold threshold) —
      flips :attr:`muted` and emits :meth:`on_mute_toggle`.
    * **Long press** (hold for :attr:`long_press_seconds`) — emits
      :meth:`on_play_pause_toggle` with the *requested* playing
      state.  The card's state is unchanged.

    Args:
        index: Card zone index (0–3).
        artist: Initial artist name.  Defaults to ``""``.
        title: Initial media title.  Defaults to ``"No Media"``.
        state: Initial playback state (``"Playing"`` / ``"Paused"`` /
            ``"Idle"``).  Defaults to ``"Idle"``.
        volume: Initial volume level (0–100).  Defaults to 50.
        entity_picture: Optional album-art :class:`~PIL.Image.Image`.
        long_press_seconds: How long the encoder must be held before
            play/pause is toggled.  Defaults to ``2.0``.

    Usage::

        from deckboard import HaMediaCard

        card = HaMediaCard(
            0,
            artist="Tórshavnar Big Band",
            title="Sólsetur",
            state="Playing",
            volume=24,
        )
        card.set_entity_picture(album_art_image)
    """

    def __init__(
        self,
        index: int,
        *,
        artist: str = "",
        title: str = "No Media",
        state: str = "Idle",
        volume: float = 50,
        entity_picture: Image.Image | None = None,
        long_press_seconds: float = 2.0,
    ) -> None:
        super().__init__(index)
        self._artist = artist
        self._title = title
        self._state = state
        self._volume = max(0.0, min(100.0, float(volume)))
        self._requested_volume: float = self._volume
        self._entity_picture = entity_picture
        self._muted = False
        self._playing = state.lower() == "playing"
        self._volume_step: float = 1.0
        self._volume_change_handler: AsyncHandler | None = None
        self._mute_toggle_handler: AsyncHandler | None = None
        self._play_pause_toggle_handler: AsyncHandler | None = None
        self._long_press_seconds = max(0.0, float(long_press_seconds))
        self._long_press_task: asyncio.Task[None] | None = None
        self._long_press_fired = False

    # ── Property accessors ────────────────────────────────────────────

    @property
    def artist(self) -> str:
        """The media artist name."""
        return self._artist

    @property
    def title(self) -> str:
        """The media title."""
        return self._title

    @property
    def state(self) -> str:
        """The current playback state text (e.g. ``'Playing'``)."""
        return self._state

    @property
    def volume(self) -> float:
        """Current confirmed volume level (0–100)."""
        return self._volume

    @property
    def requested_volume(self) -> float:
        """The most recently requested volume from encoder turns.

        This accumulates encoder ticks until the backend confirms the
        change via :meth:`set_volume`.  Starts equal to :attr:`volume`.
        """
        return self._requested_volume

    @property
    def volume_normalized(self) -> float:
        """Volume mapped to 0.0 – 1.0."""
        return self._volume / 100.0

    @property
    def muted(self) -> bool:
        """Whether the volume is currently muted."""
        return self._muted

    @property
    def playing(self) -> bool:
        """Whether media is currently playing."""
        return self._playing

    @property
    def entity_picture(self) -> Image.Image | None:
        """The album-art image, or ``None``."""
        return self._entity_picture

    @property
    def volume_step(self) -> float:
        """The increment used per encoder tick."""
        return self._volume_step

    @property
    def long_press_seconds(self) -> float:
        """Seconds the encoder must be held to trigger play/pause."""
        return self._long_press_seconds

    # ── Mutators ──────────────────────────────────────────────────────

    def set_artist(self, artist: str) -> HaMediaCard:
        """Update the artist name."""
        self._artist = artist
        self._dirty = True
        return self

    def set_title(self, title: str) -> HaMediaCard:
        """Update the media title."""
        self._title = title
        self._dirty = True
        return self

    def set_state(self, state: str) -> HaMediaCard:
        """Update the playback state text and internal playing flag."""
        self._state = state
        self._playing = state.lower() == "playing"
        self._dirty = True
        return self

    def set_volume(self, volume: float) -> None:
        """Set the confirmed volume, clamping to 0–100.

        This is intended to be called by the integration layer after
        the backend has acknowledged the volume change.  No callback
        is emitted.  The :attr:`requested_volume` accumulator is
        reset to match so that subsequent encoder ticks start from
        the confirmed value.
        """
        self._volume = max(0.0, min(100.0, float(volume)))
        self._requested_volume = self._volume
        self._dirty = True

    def set_volume_step(self, step: float) -> HaMediaCard:
        """Set the encoder-turn increment for volume."""
        self._volume_step = max(0.1, float(step))
        return self

    def set_long_press_seconds(self, seconds: float) -> HaMediaCard:
        """Set how long the encoder must be held for play/pause."""
        self._long_press_seconds = max(0.0, float(seconds))
        return self

    def set_entity_picture(self, image: Image.Image | None) -> HaMediaCard:
        """Set or clear the album-art image."""
        self._entity_picture = image
        self._dirty = True
        return self

    # ── Volume change callback ────────────────────────────────────────

    def on_volume_change(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for volume change requests.

        Fired when the encoder is turned.  The handler receives the
        *requested* volume (0–100).  The card's actual volume is
        **not** modified — call :meth:`set_volume` to apply the
        confirmed value from the backend.

        Usage::

            @card.on_volume_change
            async def handle(volume: float):
                print(f"Requested volume: {volume}")
        """
        self._volume_change_handler = handler
        return handler

    # ── Mute toggle callback ──────────────────────────────────────────

    def on_mute_toggle(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for mute state changes.

        The handler receives the new ``muted`` value (``True`` or
        ``False``).

        Usage::

            @card.on_mute_toggle
            async def handle(muted: bool):
                print(f"Muted: {muted}")
        """
        self._mute_toggle_handler = handler
        return handler

    # ── Play/pause toggle callback ────────────────────────────────────

    def on_play_pause_toggle(self, handler: AsyncHandler) -> AsyncHandler:
        """Decorator to register a handler for play/pause requests.

        The handler receives the *requested* ``playing`` state
        (``True`` for play, ``False`` for pause).  The card does
        **not** change its own state — call :meth:`set_state` to
        apply the confirmed state from the backend.

        Usage::

            @card.on_play_pause_toggle
            async def handle(playing: bool):
                print(f"Requested: {'play' if playing else 'pause'}")
        """
        self._play_pause_toggle_handler = handler
        return handler

    # ── Mute control ──────────────────────────────────────────────────

    def set_muted(self, muted: bool) -> None:
        """Set the confirmed mute state.

        This is intended to be called by the integration layer to sync
        the mute state from the backend (e.g. on initial load or after
        a confirmed toggle).  No callback is emitted.
        """
        self._muted = bool(muted)
        self._dirty = True

    def toggle_mute(self) -> None:
        """Toggle mute on/off.

        Flips the :attr:`muted` flag and queues the
        :meth:`on_mute_toggle` callback with the new state.  Volume
        is **not** modified — the caller (or callback handler) is
        responsible for any volume save/restore logic.
        """
        self._muted = not self._muted
        self._dirty = True
        if self._mute_toggle_handler is not None:
            self.queue_pending_callback(self._mute_toggle_handler, (self._muted,))

    # ── Play/Pause control ────────────────────────────────────────────

    def toggle_play_pause(self) -> None:
        """Toggle between Playing and Paused states."""
        if self._playing:
            self.set_state("Paused")
        else:
            self.set_state("Playing")

    # ── Encoder interaction overrides ─────────────────────────────────

    def handle_encoder_turn(self, direction: int) -> None:
        """Emit a volume-change request without altering the confirmed volume.

        Successive encoder ticks accumulate on :attr:`requested_volume`
        so that rapid turns produce increasing/decreasing values rather
        than repeating the same stale number.  The :meth:`on_volume_change`
        callback is queued with the accumulated *requested* volume
        (clamped to 0–100).

        The confirmed :attr:`volume` is **not** modified — call
        :meth:`set_volume` to apply the backend-confirmed value (which
        also resets the accumulator).
        """
        old_requested = self._requested_volume
        self._requested_volume = max(
            0.0, min(100.0, self._requested_volume + direction * self._volume_step)
        )
        if (
            self._volume_change_handler is not None
            and self._requested_volume != old_requested
        ):
            self.queue_pending_callback(
                self._volume_change_handler, (self._requested_volume,)
            )

    def _cancel_long_press(self) -> None:
        """Cancel a pending long-press timer, if any."""
        if self._long_press_task is not None and not self._long_press_task.done():
            self._long_press_task.cancel()
        self._long_press_task = None

    async def _long_press_timer(self) -> None:
        """Sleep for :attr:`long_press_seconds`, then emit play/pause.

        Runs as an ``asyncio.Task`` started on encoder press.  If the
        encoder is released before the timer fires, the task is
        cancelled and mute/unmute is performed instead.

        The card does **not** change its own playing state — the
        :meth:`on_play_pause_toggle` callback is queued with the
        *requested* state so the integration layer can confirm it.
        """
        await asyncio.sleep(self._long_press_seconds)
        self._long_press_fired = True
        requested_playing = not self._playing
        if self._play_pause_toggle_handler is not None:
            self.queue_pending_callback(
                self._play_pause_toggle_handler, (requested_playing,)
            )
        await self.request_refresh()

    async def dispatch_encoder_press(self) -> None:
        """Start the long-press timer on encoder press.

        Overrides :meth:`Card.dispatch_encoder_press` to defer the
        short-press action (mute/unmute) until release, so the card
        can distinguish between a short press and a long hold.

        The internal state change (starting the timer) happens *before*
        the user handler so that any callback registered via
        :meth:`~Card.on_encoder_press` sees up-to-date state.
        """
        self._long_press_fired = False
        self._cancel_long_press()
        self._long_press_task = asyncio.ensure_future(self._long_press_timer())
        if self._encoder_press_handler is not None:
            await self._encoder_press_handler()

    async def dispatch_encoder_release(self) -> None:
        """Handle encoder release: mute/unmute if short, no-op if long.

        Overrides :meth:`Card.dispatch_encoder_release`.  If the
        long-press timer already fired, the release is a no-op (the
        play/pause toggle has already happened).  Otherwise the timer
        is cancelled and mute/unmute is toggled.

        The internal state change (toggle mute) happens *before* the
        user handler so that any callback registered via
        :meth:`~Card.on_encoder_release` sees up-to-date state.
        """
        self._cancel_long_press()
        if not self._long_press_fired:
            self.toggle_mute()
        if self._encoder_release_handler is not None:
            await self._encoder_release_handler()

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self) -> Image.Image:
        """Compose the card image with album art, text, and volume bar.

        Returns:
            A PANEL_WIDTH × PANEL_HEIGHT RGB :class:`~PIL.Image.Image`.
        """
        img = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        draw = ImageDraw.Draw(img)
        font = get_font()
        small_font = get_small_font()

        # 1. Entity picture (album art) ─────────────────────────────────
        if self._entity_picture is not None:
            pic = self._entity_picture.convert("RGB")
            pic = pic.resize((PANEL_HEIGHT, PANEL_HEIGHT), Image.LANCZOS)
            img.paste(pic, (0, 0))

        # 2. Gradient mask ──────────────────────────────────────────────
        mask = _build_gradient_mask()
        black = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "black")
        img = Image.composite(black, img, mask)
        draw = ImageDraw.Draw(img)

        # 3. Artist text (top area, right-aligned) ─────────────────────
        if self._artist:
            bbox_a = draw.textbbox((0, 0), self._artist, font=font)
            artist_w = bbox_a[2] - bbox_a[0]
            draw.text(
                (PANEL_WIDTH - artist_w - 5, 14),
                self._artist,
                fill=_ARTIST_COLOR,
                font=font,
            )

        # 4. Title text (middle area, right-aligned) ────────────────────
        if self._title:
            bbox_t = draw.textbbox((0, 0), self._title, font=small_font)
            title_w = bbox_t[2] - bbox_t[0]
            draw.text(
                (PANEL_WIDTH - title_w - 5, 34),
                self._title,
                fill=_TITLE_COLOR,
                font=small_font,
            )

        # 5. State text (lower-right, standard font) ───────────────────
        state_text = self._state.capitalize() if self._state else ""
        if state_text:
            bbox = draw.textbbox((0, 0), state_text, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text(
                (PANEL_WIDTH - text_w - 5, _STATE_TEXT_Y),
                state_text,
                fill=_STATE_COLOR,
                font=font,
            )

        # 5b. Mute icon (only when muted) ──────────────────────────────
        if self._muted:
            icon_x = PANEL_WIDTH - _MUTE_ICON_SIZE - _MUTE_ICON_RIGHT_MARGIN
            _draw_mute_icon(draw, icon_x, _MUTE_ICON_Y, _MUTE_ICON_SIZE)

        # 6. Volume bar background ──────────────────────────────────────
        draw.rectangle(
            (0, _VOL_BAR_Y, PANEL_WIDTH - 1, _VOL_BAR_Y + _VOL_BAR_HEIGHT - 1),
            fill="black",
        )

        # 7. Volume level fill ──────────────────────────────────────────
        fill_w = int((PANEL_WIDTH - 1) * self.volume_normalized)
        if fill_w > 0:
            draw.rectangle(
                (0, _VOL_BAR_Y, fill_w, _VOL_BAR_Y + _VOL_BAR_HEIGHT - 1),
                fill=_VOL_BAR_COLOR,
            )

        return img
