"""Tests for the ``deux.tools.splash`` CLI helper."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from deux.tools.splash import _parse_color, main

# ---------------------------------------------------------------------------
# _parse_color
# ---------------------------------------------------------------------------


class TestParseColor:
    def test_hex(self):
        assert _parse_color("#1a2b3c") == (0x1A, 0x2B, 0x3C)

    def test_hex_uppercase(self):
        assert _parse_color("#FFAA00") == (255, 170, 0)

    def test_rgb_csv(self):
        assert _parse_color("10, 20, 30") == (10, 20, 30)

    def test_rgb_csv_clamps(self):
        assert _parse_color("999,-5,128") == (255, 0, 128)

    @pytest.mark.parametrize(
        "value",
        ["#abc", "#zzzzzz", "1,2", "a,b,c", "garbage"],
    )
    def test_invalid_raises(self, value):
        import argparse

        with pytest.raises(argparse.ArgumentTypeError):
            _parse_color(value)


# ---------------------------------------------------------------------------
# main — argument validation
# ---------------------------------------------------------------------------


class TestMainArgs:
    def test_no_args_exits(self, capsys):
        with pytest.raises(SystemExit):
            main([])

    def test_image_and_clear_mutually_exclusive(self, capsys, tmp_path):
        img = tmp_path / "x.png"
        Image.new("RGB", (10, 10), (0, 0, 0)).save(img)
        with pytest.raises(SystemExit):
            main([f"--image={img}", "--clear"])


# ---------------------------------------------------------------------------
# main — end-to-end with a mocked device
# ---------------------------------------------------------------------------


def _make_mock_device(
    *, pid: int = 0x0084, logical: tuple[int, int] = (800, 480)
) -> MagicMock:
    from deux.runtime.hid.protocol import ImageRotation

    dev = MagicMock()
    dev.product_id = pid
    dev.family = "Stream Deck +"
    dev.logical_lcd_size = logical
    dev.rotation = ImageRotation.NONE
    dev.open.return_value = None
    dev.close.return_value = None
    dev.set_full_screen_image.return_value = None
    return dev


class TestMainPush:
    def test_push_image(self, tmp_path):
        img = tmp_path / "boot.png"
        Image.new("RGB", (200, 100), (255, 0, 0)).save(img)
        device = _make_mock_device()

        with patch(
            "deux.runtime.hid.discovery.enumerate_devices", return_value=[device]
        ):
            rc = main([f"--image={img}"])

        assert rc == 0
        device.set_full_screen_image.assert_called_once()
        (jpeg,), _ = device.set_full_screen_image.call_args
        assert jpeg.startswith(b"\xff\xd8\xff")

    def test_clear(self):
        device = _make_mock_device()
        with patch(
            "deux.runtime.hid.discovery.enumerate_devices", return_value=[device]
        ):
            rc = main(["--clear", "--background=#ff0000"])

        assert rc == 0
        device.set_full_screen_image.assert_called_once()
        (jpeg,), _ = device.set_full_screen_image.call_args
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        r, g, b = img.getpixel((50, 50))
        assert r > 200 and g < 50 and b < 50

    def test_no_device_exits_nonzero(self, capsys):
        with patch(
            "deux.runtime.hid.discovery.enumerate_devices", return_value=[]
        ), pytest.raises(SystemExit) as excinfo:
            main(["--clear"])
        assert excinfo.value.code == 1

    def test_unknown_pid_returns_2(self):
        device = _make_mock_device(pid=0xDEAD, logical=(0, 0))
        with patch(
            "deux.runtime.hid.discovery.enumerate_devices", return_value=[device]
        ):
            rc = main(["--clear"])
        assert rc == 2
        device.close.assert_called_once()

    def test_invalid_image_returns_2(self, tmp_path):
        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not an image")
        device = _make_mock_device()
        with patch(
            "deux.runtime.hid.discovery.enumerate_devices", return_value=[device]
        ):
            rc = main([f"--image={bad}"])
        assert rc == 2
        device.set_full_screen_image.assert_not_called()
        device.close.assert_called_once()

    def test_hid_failure_returns_2(self, tmp_path):
        img = tmp_path / "boot.png"
        Image.new("RGB", (50, 50), (0, 255, 0)).save(img)
        device = _make_mock_device()
        device.set_full_screen_image.side_effect = OSError("boom")
        with patch(
            "deux.runtime.hid.discovery.enumerate_devices", return_value=[device]
        ):
            rc = main([f"--image={img}"])
        assert rc == 2
        device.close.assert_called_once()

    def test_verbose_flag_accepted(self):
        device = _make_mock_device()
        with patch(
            "deux.runtime.hid.discovery.enumerate_devices", return_value=[device]
        ):
            rc = main(["--clear", "-v"])
        assert rc == 0
