"""Tests for deckboard.page — Page class."""

from __future__ import annotations

import pytest

from deckboard.button import Button
from deckboard.dial import Dial
from deckboard.page import Page, Screen
from deckboard.touchscreen import TouchScreen, Widget
from deckboard.widgets.icon_widget import IconWidget
from deckboard.widgets.slider_widget import SliderWidget


class TestPageInit:
    def test_is_screen(self, page: Page):
        assert isinstance(page, Screen)

    def test_name(self, page: Page):
        assert page.name == "test"

    def test_empty_buttons(self, page: Page):
        assert page.buttons == {}

    def test_empty_dials(self, page: Page):
        assert page.dials == {}

    def test_has_touchscreen(self, page: Page):
        assert isinstance(page.touchscreen, TouchScreen)

    def test_widgets_list(self, page: Page):
        assert len(page.widgets) == 4


class TestPageButton:
    def test_key_alias(self, page: Page):
        assert page.key(0) is page.button(0)

    def test_creates_button(self, page: Page):
        b = page.button(0)
        assert isinstance(b, Button)
        assert b.index == 0

    def test_same_instance(self, page: Page):
        a = page.button(0)
        b = page.button(0)
        assert a is b

    def test_creates_all_indices(self, page: Page):
        for i in range(8):
            b = page.button(i)
            assert b.index == i

    def test_different_indices_different_instances(self, page: Page):
        a = page.button(0)
        b = page.button(1)
        assert a is not b

    def test_stored_in_buttons_dict(self, page: Page):
        b = page.button(3)
        assert page.buttons[3] is b

    def test_index_too_low(self, page: Page):
        with pytest.raises(IndexError, match="Button index must be 0-7"):
            page.button(-1)

    def test_index_too_high(self, page: Page):
        with pytest.raises(IndexError, match="Button index must be 0-7"):
            page.button(8)


class TestPageDial:
    def test_encoder_alias(self, page: Page):
        assert page.encoder(0) is page.dial(0)

    def test_creates_dial(self, page: Page):
        d = page.dial(0)
        assert isinstance(d, Dial)
        assert d.index == 0

    def test_same_instance(self, page: Page):
        a = page.dial(0)
        b = page.dial(0)
        assert a is b

    def test_creates_all_indices(self, page: Page):
        for i in range(4):
            d = page.dial(i)
            assert d.index == i

    def test_stored_in_dials_dict(self, page: Page):
        d = page.dial(2)
        assert page.dials[2] is d

    def test_index_too_low(self, page: Page):
        with pytest.raises(IndexError, match="Dial index must be 0-3"):
            page.dial(-1)

    def test_index_too_high(self, page: Page):
        with pytest.raises(IndexError, match="Dial index must be 0-3"):
            page.dial(4)


class TestPageWidget:
    def test_card_alias(self, page: Page):
        assert page.card(0) is page.widget(0)

    def test_delegates_to_touchscreen(self, page: Page):
        w = page.widget(0)
        assert isinstance(w, Widget)
        assert w is page.touchscreen.widget(0)

    def test_default_is_icon_widget(self, page: Page):
        w = page.widget(0)
        assert isinstance(w, IconWidget)

    def test_index_error(self, page: Page):
        with pytest.raises(IndexError):
            page.widget(4)


class TestPageSetWidget:
    def test_set_card_alias(self, page: Page):
        sw = SliderWidget(0)
        page.set_card(0, sw)
        assert page.card(0) is sw

    def test_replace_with_slider_widget(self, page: Page):
        sw = SliderWidget(0)
        page.set_widget(0, sw)
        assert page.widget(0) is sw

    def test_replace_preserves_others(self, page: Page):
        original_1 = page.widget(1)
        page.set_widget(0, SliderWidget(0))
        assert page.widget(1) is original_1
