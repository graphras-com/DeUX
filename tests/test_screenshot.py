"""Tests for Screen.screenshot() — saving screen state as JPEG files."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from deux.runtime.capabilities import STREAM_DECK_PLUS
from deux.ui.screen import Screen
from tests.conftest import STREAM_DECK_MINI, STREAM_DECK_NEO


def _make_jpeg(width: int = 10, height: int = 10) -> bytes:
    """Create minimal JPEG bytes for testing."""
    import io

    img = Image.new("RGB", (width, height), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50)
    return buf.getvalue()


class TestScreenshotKeys:
    """Screenshot saves key images that have been rendered."""

    def test_key_with_image_saved(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_MINI)
        key = screen.key(0)
        key.set_rendered_image(_make_jpeg())

        paths = screen.screenshot(tmp_path / "out")

        assert len(paths) == 1
        assert paths[0] == tmp_path / "out" / "key_0.jpg"
        assert paths[0].exists()
        # Verify it's valid JPEG
        img = Image.open(paths[0])
        assert img.format == "JPEG"

    def test_key_without_image_skipped(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_MINI)
        screen.key(0)  # created but no image set

        paths = screen.screenshot(tmp_path / "out")

        assert paths == []

    def test_multiple_keys_sparse(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_MINI)
        screen.key(0).set_rendered_image(_make_jpeg())
        screen.key(1)  # no image
        screen.key(3).set_rendered_image(_make_jpeg())

        paths = screen.screenshot(tmp_path / "out")

        names = [p.name for p in paths]
        assert names == ["key_0.jpg", "key_3.jpg"]


class TestScreenshotTouchstrip:
    """Screenshot saves touch-strip card images."""

    def test_card_with_rendered_image_saved(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_PLUS)
        card = screen.card(0)
        card.set_rendered(Image.new("RGB", (200, 100), "blue"))

        paths = screen.screenshot(tmp_path / "out")

        card_paths = [p for p in paths if p.name.startswith("card_")]
        assert len(card_paths) == 1
        assert card_paths[0].name == "card_0.jpg"
        img = Image.open(card_paths[0])
        assert img.format == "JPEG"

    def test_card_without_render_skipped(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_PLUS)
        # All cards are BlankCard by default; rendered is None

        paths = screen.screenshot(tmp_path / "out")

        card_paths = [p for p in paths if p.name.startswith("card_")]
        assert card_paths == []

    def test_rgba_card_converted_to_rgb(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_PLUS)
        card = screen.card(1)
        card.set_rendered(Image.new("RGBA", (200, 100), (255, 0, 0, 128)))

        paths = screen.screenshot(tmp_path / "out")

        card_paths = [p for p in paths if p.name.startswith("card_")]
        assert len(card_paths) == 1
        img = Image.open(card_paths[0])
        assert img.mode == "RGB"

    def test_no_touchstrip_device(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_MINI)

        paths = screen.screenshot(tmp_path / "out")

        assert paths == []


class TestScreenshotInfoScreen:
    """Screenshot saves info screen image for Neo-like devices."""

    def test_info_screen_with_image_saved(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_NEO)
        assert screen.info_screen is not None
        screen.info_screen.set_image(Image.new("RGB", (248, 58), "green"))

        paths = screen.screenshot(tmp_path / "out")

        info_paths = [p for p in paths if p.name == "info_screen.jpg"]
        assert len(info_paths) == 1
        img = Image.open(info_paths[0])
        assert img.format == "JPEG"

    def test_info_screen_no_image_skipped(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_NEO)
        assert screen.info_screen is not None
        # image is None by default

        paths = screen.screenshot(tmp_path / "out")

        info_paths = [p for p in paths if p.name == "info_screen.jpg"]
        assert info_paths == []

    def test_no_info_screen_device(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_PLUS)
        assert screen.info_screen is None

        paths = screen.screenshot(tmp_path / "out")

        info_paths = [p for p in paths if p.name == "info_screen.jpg"]
        assert info_paths == []


class TestScreenshotDirectory:
    """Screenshot creates the output directory if needed."""

    def test_creates_nested_directory(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_MINI)
        screen.key(0).set_rendered_image(_make_jpeg())

        nested = tmp_path / "a" / "b" / "c"
        paths = screen.screenshot(nested)

        assert nested.is_dir()
        assert len(paths) == 1

    def test_empty_screen_returns_empty_list(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_PLUS)

        paths = screen.screenshot(tmp_path / "out")

        assert paths == []


class TestScreenshotMixed:
    """Screenshot with keys + touchstrip cards together."""

    def test_keys_and_cards_combined(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_PLUS)
        screen.key(0).set_rendered_image(_make_jpeg())
        screen.key(2).set_rendered_image(_make_jpeg())
        screen.card(1).set_rendered(Image.new("RGB", (200, 100), "blue"))

        paths = screen.screenshot(tmp_path / "out")

        names = [p.name for p in paths]
        assert names == ["key_0.jpg", "key_2.jpg", "card_1.jpg"]

    def test_neo_keys_and_info_screen(self, tmp_path: Path) -> None:
        screen = Screen("test", STREAM_DECK_NEO)
        screen.key(0).set_rendered_image(_make_jpeg())
        assert screen.info_screen is not None
        screen.info_screen.set_image(Image.new("RGB", (248, 58), "white"))

        paths = screen.screenshot(tmp_path / "out")

        names = [p.name for p in paths]
        assert names == ["key_0.jpg", "info_screen.jpg"]
