"""Tests for deckboard.ui.screen — Screen class."""

from __future__ import annotations

import pytest

from deckboard.ui.controls.key_slot import Button
from deckboard.ui.controls.encoder_slot import Dial
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

    def test_empty_buttons(self, page: Screen):
        assert page.buttons == {}

    def test_empty_dials(self, page: Screen):
        assert page.dials == {}

    def test_has_touchscreen(self, page: Screen):
        assert isinstance(page.touch_strip, TouchStrip)

    def test_widgets_list(self, page: Screen):
        assert len(page.cards) == 4


class TestPageButton:
    def test_key_alias(self, page: Screen):
        assert page.key(0) is page.key(0)

    def test_creates_button(self, page: Screen):
        b = page.key(0)
        assert isinstance(b, Button)
        assert b.index == 0

    def test_same_instance(self, page: Screen):
        a = page.key(0)
        b = page.key(0)
        assert a is b

    def test_creates_all_indices(self, page: Screen):
        for i in range(8):
            b = page.key(i)
            assert b.index == i

    def test_different_indices_different_instances(self, page: Screen):
        a = page.key(0)
        b = page.key(1)
        assert a is not b

    def test_stored_in_buttons_dict(self, page: Screen):
        b = page.key(3)
        assert page.buttons[3] is b

    def test_index_too_low(self, page: Screen):
        with pytest.raises(IndexError, match="Button index must be 0-7"):
            page.key(-1)

    def test_index_too_high(self, page: Screen):
        with pytest.raises(IndexError, match="Button index must be 0-7"):
            page.key(8)


class TestPageDial:
    def test_encoder_alias(self, page: Screen):
        assert page.encoder(0) is page.encoder(0)

    def test_creates_dial(self, page: Screen):
        d = page.encoder(0)
        assert isinstance(d, Dial)
        assert d.index == 0

    def test_same_instance(self, page: Screen):
        a = page.encoder(0)
        b = page.encoder(0)
        assert a is b

    def test_creates_all_indices(self, page: Screen):
        for i in range(4):
            d = page.encoder(i)
            assert d.index == i

    def test_stored_in_dials_dict(self, page: Screen):
        d = page.encoder(2)
        assert page.dials[2] is d

    def test_index_too_low(self, page: Screen):
        with pytest.raises(IndexError, match="Dial index must be 0-3"):
            page.encoder(-1)

    def test_index_too_high(self, page: Screen):
        with pytest.raises(IndexError, match="Dial index must be 0-3"):
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
