"""Integration tests for Deck-level full-screen image API.

Covers :meth:`Deck.show_full_screen_image`, :meth:`Deck.show_splash`,
and :meth:`Deck.clear_full_screen_image` end-to-end against the mocked
:class:`HidDevice`.  Verifies:

* JPEG bytes are produced with the expected transmit dimensions for
  each deck family (rotation included).
* The HID method ``set_full_screen_image`` is invoked through the
  ``_device_lock`` + executor path.
* Missing device and unknown-PID error branches.
* Concurrent invocations serialise correctly.
"""

from __future__ import annotations

import asyncio
import io

import pytest
from PIL import Image

from deux.runtime.deck import Deck, DeckError
from deux.runtime.hid.protocol import ImageRotation
from deux.runtime.splash import SplashError

from .conftest import STREAM_DECK_PLUS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_size(jpeg_bytes: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(jpeg_bytes)).size


def _attached_deck(mock_device) -> Deck:
    """Build a Deck pre-attached to a mock HidDevice."""
    deck = Deck.for_testing(STREAM_DECK_PLUS, serial_number="TEST123")
    deck._device = mock_device
    return deck


# ---------------------------------------------------------------------------
# show_full_screen_image — happy paths
# ---------------------------------------------------------------------------


class TestShowFullScreenImage:
    """Successful full-screen image uploads through the Deck API."""

    async def test_pil_image_plus_no_rotation(self, mock_streamdeck_device):
        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (400, 200), (255, 0, 0))

        await deck.show_full_screen_image(src)

        mock_streamdeck_device.set_full_screen_image.assert_called_once()
        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        assert jpeg.startswith(b"\xff\xd8\xff")
        assert _decode_size(jpeg) == (800, 480)  # Plus logical == transmit

    async def test_plus_xl_ccw_90_rotation(self, mock_streamdeck_device):
        """Plus XL transmits as (800, 1280) for logical (1280, 800)."""
        # Reconfigure the mock to look like a Plus XL.
        mock_streamdeck_device.product_id = 0x00C6
        mock_streamdeck_device.logical_lcd_size = (1280, 800)
        mock_streamdeck_device.rotation = ImageRotation.CCW_90

        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (200, 100), (0, 255, 0))

        await deck.show_full_screen_image(src)

        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        assert _decode_size(jpeg) == (800, 1280)

    async def test_classic_cw_180_rotation(self, mock_streamdeck_device):
        """Classic logical 480x272 -> transmit 480x272 (rotation preserves dims)."""
        mock_streamdeck_device.product_id = 0x006D
        mock_streamdeck_device.logical_lcd_size = (480, 272)
        mock_streamdeck_device.rotation = ImageRotation.CW_180

        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (200, 100), (0, 0, 255))

        await deck.show_full_screen_image(src)

        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        assert _decode_size(jpeg) == (480, 272)

    async def test_from_path(self, mock_streamdeck_device, tmp_path):
        path = tmp_path / "splash.png"
        Image.new("RGB", (300, 300), (128, 128, 128)).save(path)
        deck = _attached_deck(mock_streamdeck_device)

        await deck.show_full_screen_image(path)

        mock_streamdeck_device.set_full_screen_image.assert_called_once()

    async def test_from_png_bytes(self, mock_streamdeck_device):
        buf = io.BytesIO()
        Image.new("RGB", (200, 200), (10, 20, 30)).save(buf, format="PNG")

        deck = _attached_deck(mock_streamdeck_device)
        await deck.show_full_screen_image(buf.getvalue())

        mock_streamdeck_device.set_full_screen_image.assert_called_once()

    async def test_contain_fit_with_background(self, mock_streamdeck_device):
        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (1600, 100), (255, 0, 0))  # very wide

        await deck.show_full_screen_image(
            src, fit="contain", background=(0, 255, 0)
        )

        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        # Top-left should be in the green letterbox area.
        top = img.getpixel((0, 0))
        assert top[1] > top[0]

    async def test_jpeg_quality_round_trip(self, mock_streamdeck_device):
        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (400, 200), (200, 100, 50))

        await deck.show_full_screen_image(src, jpeg_quality=25)

        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        assert jpeg.startswith(b"\xff\xd8\xff")


# ---------------------------------------------------------------------------
# show_splash — alias semantics
# ---------------------------------------------------------------------------


class TestShowSplash:
    async def test_calls_set_full_screen_image(self, mock_streamdeck_device):
        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (200, 200), (10, 20, 30))

        await deck.show_splash(src)

        mock_streamdeck_device.set_full_screen_image.assert_called_once()

    async def test_passes_through_kwargs(self, mock_streamdeck_device):
        """show_splash forwards fit/background/quality through to the pipeline."""
        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (1600, 100), (255, 0, 0))

        await deck.show_splash(
            src, fit="contain", background=(0, 0, 255), jpeg_quality=80
        )

        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        top = img.getpixel((0, 0))
        assert top[2] > top[0]  # blue letterbox


# ---------------------------------------------------------------------------
# min_display_ms — splash push-hold deadline
# ---------------------------------------------------------------------------


class TestSplashMinDisplayMs:
    """:meth:`Deck.show_full_screen_image` ``min_display_ms`` semantics."""

    async def test_default_does_not_set_deadline(self, mock_streamdeck_device):
        """Default ``min_display_ms=0`` leaves the deadline at None."""
        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (200, 200), (10, 20, 30))

        await deck.show_full_screen_image(src)

        assert deck._splash_push_deadline is None

    async def test_positive_value_records_future_deadline(
        self, mock_streamdeck_device
    ):
        """A positive value sets a deadline in the future."""
        import time as _time

        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (200, 200), (10, 20, 30))

        before = _time.perf_counter()
        await deck.show_full_screen_image(src, min_display_ms=250)
        after = _time.perf_counter()

        assert deck._splash_push_deadline is not None
        # Deadline should be ~250ms after the call's start.
        assert before + 0.25 <= deck._splash_push_deadline <= after + 0.25 + 0.05

    async def test_show_splash_forwards_min_display_ms(
        self, mock_streamdeck_device
    ):
        """``show_splash`` forwards ``min_display_ms`` to the underlying method."""
        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (200, 200), (10, 20, 30))

        await deck.show_splash(src, min_display_ms=100)

        assert deck._splash_push_deadline is not None


# ---------------------------------------------------------------------------
# clear_full_screen_image
# ---------------------------------------------------------------------------


class TestClearFullScreenImage:
    async def test_default_black(self, mock_streamdeck_device):
        deck = _attached_deck(mock_streamdeck_device)

        await deck.clear_full_screen_image()

        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        r, g, b = img.getpixel((50, 50))
        assert r < 20 and g < 20 and b < 20

    async def test_custom_colour(self, mock_streamdeck_device):
        deck = _attached_deck(mock_streamdeck_device)

        await deck.clear_full_screen_image((255, 0, 0))

        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        r, g, b = img.getpixel((100, 100))
        assert r > 200 and g < 50 and b < 50

    async def test_produces_transmit_size(self, mock_streamdeck_device):
        deck = _attached_deck(mock_streamdeck_device)

        await deck.clear_full_screen_image()

        (jpeg,), _ = mock_streamdeck_device.set_full_screen_image.call_args
        assert _decode_size(jpeg) == (800, 480)

    async def test_clear_no_device_raises(self):
        deck = Deck.for_testing(STREAM_DECK_PLUS)
        with pytest.raises(DeckError, match="Device not opened"):
            await deck.clear_full_screen_image()

    async def test_clear_unknown_pid_raises(self, mock_streamdeck_device):
        mock_streamdeck_device.logical_lcd_size = (0, 0)
        mock_streamdeck_device.product_id = 0xDEAD
        deck = _attached_deck(mock_streamdeck_device)

        with pytest.raises(DeckError, match="no known LCD size"):
            await deck.clear_full_screen_image()


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    async def test_no_device_raises(self):
        deck = Deck.for_testing(STREAM_DECK_PLUS)
        with pytest.raises(DeckError, match="Device not opened"):
            await deck.show_full_screen_image(
                Image.new("RGB", (10, 10), (0, 0, 0))
            )

    async def test_unknown_pid_raises(self, mock_streamdeck_device):
        mock_streamdeck_device.logical_lcd_size = (0, 0)
        mock_streamdeck_device.product_id = 0xDEAD
        deck = _attached_deck(mock_streamdeck_device)

        with pytest.raises(DeckError, match="no known LCD size"):
            await deck.show_full_screen_image(
                Image.new("RGB", (10, 10), (0, 0, 0))
            )

    async def test_invalid_input_surfaces_splash_error(self, mock_streamdeck_device):
        deck = _attached_deck(mock_streamdeck_device)
        with pytest.raises(SplashError):
            await deck.show_full_screen_image(b"not an image")
        # HID layer must not be called when preparation fails.
        mock_streamdeck_device.set_full_screen_image.assert_not_called()


# ---------------------------------------------------------------------------
# Concurrency — _device_lock serialises uploads
# ---------------------------------------------------------------------------


class TestConcurrency:
    async def test_concurrent_calls_serialise(self, mock_streamdeck_device):
        """Two concurrent show_full_screen_image calls both complete."""
        deck = _attached_deck(mock_streamdeck_device)
        src = Image.new("RGB", (200, 200), (50, 50, 50))

        await asyncio.gather(
            deck.show_full_screen_image(src),
            deck.show_full_screen_image(src),
        )

        assert mock_streamdeck_device.set_full_screen_image.call_count == 2
