"""Tests for deckui.ui.screen — Screen class."""

from __future__ import annotations

import pytest

from deckui.runtime.capabilities import STREAM_DECK_PLUS
from deckui.ui.cards.base import Card
from deckui.ui.cards.blank import BlankCard
from deckui.ui.controls.encoder_slot import EncoderSlot
from deckui.ui.controls.key_slot import KeySlot
from deckui.ui.screen import Screen
from deckui.ui.touch_strip import TouchStrip
from tests.conftest import STREAM_DECK_MINI, STREAM_DECK_NEO


class TestPageInit:
    def test_is_screen(self, page: Screen):
        assert isinstance(page, Screen)

    def test_name(self, page: Screen):
        assert page.name == "test"

    def test_empty_keys(self, page: Screen):
        assert page.keys == {}

    def test_empty_encoders(self, page: Screen):
        assert page.encoders == {}

    def test_has_touchscreen(self, page: Screen):
        assert isinstance(page.touch_strip, TouchStrip)

    def test_cards_list(self, page: Screen):
        assert len(page.cards) == 4

    def test_capabilities_property(self, page: Screen):
        assert page.capabilities is STREAM_DECK_PLUS


class TestScreenForMini:
    """Screen for a device with no encoders and no touchscreen."""

    def test_no_touchstrip(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        assert screen.touch_strip is None

    def test_no_cards(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        assert screen.cards == []

    def test_key_count(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        for i in range(6):
            k = screen.key(i)
            assert screen.keys[i] is k
        with pytest.raises(IndexError, match="Key index must be 0-5"):
            screen.key(6)

    def test_encoder_raises(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        with pytest.raises(IndexError, match="no encoders"):
            screen.encoder(0)

    def test_card_raises(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        with pytest.raises(IndexError, match="no touchscreen"):
            screen.card(0)

    def test_touchstrip_background_default(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        assert screen.touchstrip_background == "black"


class TestScreenForNeo:
    """Screen for Neo: 8 keys, no encoders, no touchscreen, info screen."""

    def test_has_info_screen(self):
        screen = Screen("neo", STREAM_DECK_NEO)
        assert screen.info_screen is not None
        assert screen.info_screen.width == 248
        assert screen.info_screen.height == 58

    def test_no_touchstrip(self):
        screen = Screen("neo", STREAM_DECK_NEO)
        assert screen.touch_strip is None


class TestPageKey:
    def test_key_returns_same(self, page: Screen):
        assert page.key(0) is page.key(0)

    def test_creates_key_slot(self, page: Screen):
        k = page.key(0)
        assert isinstance(k, KeySlot)
        assert page.keys[0] is k

    def test_same_instance(self, page: Screen):
        a = page.key(0)
        b = page.key(0)
        assert a is b

    def test_creates_all_indices(self, page: Screen):
        for i in range(8):
            k = page.key(i)
            assert page.keys[i] is k

    def test_different_indices_different_instances(self, page: Screen):
        a = page.key(0)
        b = page.key(1)
        assert a is not b

    def test_stored_in_keys_dict(self, page: Screen):
        k = page.key(3)
        assert page.keys[3] is k

    def test_index_too_low(self, page: Screen):
        with pytest.raises(IndexError, match="Key index must be 0-7"):
            page.key(-1)

    def test_index_too_high(self, page: Screen):
        with pytest.raises(IndexError, match="Key index must be 0-7"):
            page.key(8)


class TestPageEncoder:
    def test_encoder_returns_same(self, page: Screen):
        assert page.encoder(0) is page.encoder(0)

    def test_creates_encoder_slot(self, page: Screen):
        e = page.encoder(0)
        assert isinstance(e, EncoderSlot)
        assert page.encoders[0] is e

    def test_same_instance(self, page: Screen):
        a = page.encoder(0)
        b = page.encoder(0)
        assert a is b

    def test_creates_all_indices(self, page: Screen):
        for i in range(4):
            e = page.encoder(i)
            assert page.encoders[i] is e

    def test_stored_in_encoders_dict(self, page: Screen):
        e = page.encoder(2)
        assert page.encoders[2] is e

    def test_index_too_low(self, page: Screen):
        with pytest.raises(IndexError, match="Encoder index must be 0-3"):
            page.encoder(-1)

    def test_index_too_high(self, page: Screen):
        with pytest.raises(IndexError, match="Encoder index must be 0-3"):
            page.encoder(4)


class TestPageCard:
    def test_card_alias(self, page: Screen):
        assert page.card(0) is page.card(0)

    def test_delegates_to_touchscreen(self, page: Screen):
        w = page.card(0)
        assert isinstance(w, Card)
        assert w is page.touch_strip.card(0)

    def test_default_is_blank(self, page: Screen):
        w = page.card(0)
        assert isinstance(w, BlankCard)

    def test_index_error(self, page: Screen):
        with pytest.raises(IndexError):
            page.card(4)


class TestPageTouchstripBackground:
    def test_default_is_black(self, page: Screen):
        assert page.touchstrip_background == "black"

    def test_getter_delegates_to_touch_strip(self, page: Screen):
        page.touch_strip.background_color = "#abcdef"
        assert page.touchstrip_background == "#abcdef"

    def test_setter_delegates_to_touch_strip(self, page: Screen):
        page.touchstrip_background = "#123456"
        assert page.touch_strip.background_color == "#123456"

    def test_setter_marks_cards_dirty(self, page: Screen):
        for card in page.cards:
            card.mark_clean()
        page.touchstrip_background = "#ff0000"
        assert page.touch_strip.any_dirty is True


class TestPageSetCard:
    def test_set_card_replaces(self, page: Screen):
        from tests.test_touch_strip import _ConcreteWidget

        cw = _ConcreteWidget()
        page.set_card(0, cw)
        assert page.card(0) is cw

    def test_replace_preserves_others(self, page: Screen):
        original_1 = page.card(1)
        page.set_card(0, BlankCard())
        assert page.card(1) is original_1

    def test_set_card_no_touchscreen(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        with pytest.raises(IndexError, match="no touchscreen"):
            screen.set_card(0, BlankCard())


class TestScreenTouchstripBackgroundSvg:
    """Tests for the Screen-level background SVG API."""

    @staticmethod
    def _make_svg() -> bytes:
        return (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="100">'
            b'<rect width="800" height="100" fill="red"/>'
            b"</svg>"
        )

    def test_set_background_svg(self, page: Screen):
        page.set_touchstrip_background_svg(self._make_svg())
        assert page.touch_strip is not None
        assert page.touch_strip.bg_tiles is not None

    def test_clear_background_svg(self, page: Screen):
        page.set_touchstrip_background_svg(self._make_svg())
        page.clear_touchstrip_background_svg()
        assert page.touch_strip.bg_tiles is None

    def test_set_background_svg_from_file(self, page: Screen, tmp_path):
        svg_file = tmp_path / "bg.svg"
        svg_file.write_bytes(self._make_svg())
        page.set_touchstrip_background_svg_from_file(svg_file)
        assert page.touch_strip.bg_tiles is not None

    def test_no_touchscreen_set(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        with pytest.raises(IndexError, match="no touchscreen"):
            screen.set_touchstrip_background_svg(self._make_svg())

    def test_no_touchscreen_clear(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        with pytest.raises(IndexError, match="no touchscreen"):
            screen.clear_touchstrip_background_svg()

    def test_no_touchscreen_file(self):
        screen = Screen("mini", STREAM_DECK_MINI)
        with pytest.raises(IndexError, match="no touchscreen"):
            screen.set_touchstrip_background_svg_from_file("/fake.svg")
