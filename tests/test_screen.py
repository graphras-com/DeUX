"""Tests for deckboard.ui.screen — Screen class."""

from __future__ import annotations

import pytest

from deckboard.ui.controls.key_slot import KeySlot
from deckboard.ui.controls.encoder_slot import EncoderSlot
from deckboard.ui.screen import Screen
from deckboard.ui.touch_strip import TouchStrip
from deckboard.ui.cards.base import Card
from deckboard.ui.cards.status import StatusCard
from deckboard.ui.cards.stack import StackCard


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

    def test_widgets_list(self, page: Screen):
        assert len(page.cards) == 4


class TestPageKey:
    def test_key_returns_same(self, page: Screen):
        assert page.key(0) is page.key(0)

    def test_creates_key_slot(self, page: Screen):
        k = page.key(0)
        assert isinstance(k, KeySlot)
        assert k.index == 0

    def test_same_instance(self, page: Screen):
        a = page.key(0)
        b = page.key(0)
        assert a is b

    def test_creates_all_indices(self, page: Screen):
        for i in range(8):
            k = page.key(i)
            assert k.index == i

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
        assert e.index == 0

    def test_same_instance(self, page: Screen):
        a = page.encoder(0)
        b = page.encoder(0)
        assert a is b

    def test_creates_all_indices(self, page: Screen):
        for i in range(4):
            e = page.encoder(i)
            assert e.index == i

    def test_stored_in_encoders_dict(self, page: Screen):
        e = page.encoder(2)
        assert page.encoders[2] is e

    def test_index_too_low(self, page: Screen):
        with pytest.raises(IndexError, match="Encoder index must be 0-3"):
            page.encoder(-1)

    def test_index_too_high(self, page: Screen):
        with pytest.raises(IndexError, match="Encoder index must be 0-3"):
            page.encoder(4)


class TestPageWidget:
    def test_card_alias(self, page: Screen):
        assert page.card(0) is page.card(0)

    def test_delegates_to_touchscreen(self, page: Screen):
        w = page.card(0)
        assert isinstance(w, Card)
        assert w is page.touch_strip.card(0)

    def test_default_is_icon_widget(self, page: Screen):
        w = page.card(0)
        assert isinstance(w, StatusCard)

    def test_index_error(self, page: Screen):
        with pytest.raises(IndexError):
            page.card(4)


class TestPageSetWidget:
    def test_set_card_alias(self, page: Screen):
        sw = StackCard(0)
        page.set_card(0, sw)
        assert page.card(0) is sw

    def test_replace_with_slider_widget(self, page: Screen):
        sw = StackCard(0)
        page.set_card(0, sw)
        assert page.card(0) is sw

    def test_replace_preserves_others(self, page: Screen):
        original_1 = page.card(1)
        page.set_card(0, StackCard(0))
        assert page.card(1) is original_1
