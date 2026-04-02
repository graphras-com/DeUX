"""Tests for deckboard.page — Page class."""

from __future__ import annotations

import pytest

from deckboard.button import Button
from deckboard.dial import Dial
from deckboard.page import Page
from deckboard.touchscreen import TouchScreen, Widget


class TestPageInit:
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
    def test_delegates_to_touchscreen(self, page: Page):
        w = page.widget(0)
        assert isinstance(w, Widget)
        assert w is page.touchscreen.widget(0)

    def test_index_error(self, page: Page):
        with pytest.raises(IndexError):
            page.widget(4)
