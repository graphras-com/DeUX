"""Tests for the Stream Deck example (examples/streamdeck.py)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from deckui.dui.card import DuiCard
from deckui.dui.key import DuiKey
from deckui.dui.schema import (
    ColorBinding,
    EventMapping,
    IconifyBinding,
    ImageBinding,
    ListBinding,
    PackageSpec,
    PackageType,
    RangeBinding,
    RotateTransform,
    SliderBinding,
    TextBinding,
    ToggleBinding,
    TransformBinding,
)

# Make examples importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))

from streamdeck import (
    MEDIA_CATALOG,
    SCENE_DEFS,
    AudioController,
    DashboardController,
    FavoritesController,
    GaugeController,
    LightsController,
    SceneController,
    ScreenCycler,
    TimerController,
)

# ---------------------------------------------------------------------------
# Minimal SVG / spec helpers (no real .dui files needed)
# ---------------------------------------------------------------------------

_AUDIO_SVG = (
    '<svg id="AudioCard" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<text id="artist" x="4" y="20" font-size="14" fill="#fff">Artist</text>'
    '<text id="title" x="4" y="40" font-size="14" fill="#fff">Title</text>'
    '<text id="album" x="4" y="55" font-size="12" fill="#aaa">Album</text>'
    '<text id="state" x="4" y="70" font-size="10" fill="#aaa">Stopped</text>'
    '<text id="value_text" x="4" y="85" font-size="10" fill="#aaa">50%</text>'
    '<rect id="volume_bar" x="4" y="90" width="189" height="4" fill="#dedede"/>'
    '<image id="cover" x="0" y="0" width="98" height="98" href=""/>'
    '<rect id="cover_placeholder" x="0" y="0" width="98" height="98" fill="#333"/>'
    "</svg>"
)

_LIGHT_SVG = (
    '<svg id="LightCard" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<rect id="lights_on" x="0" y="0" width="10" height="10" fill="#ff0"/>'
    '<rect id="lights_off" x="0" y="0" width="10" height="10" fill="#333"/>'
    '<text id="brightness_value_text" x="4" y="40" font-size="10" fill="#fff">0%</text>'
    '<text id="kelvin_value_text" x="4" y="55" font-size="10" fill="#fff">2000K</text>'
    '<rect id="brightness_indicator" x="4" y="70" width="5" height="5" fill="#fff"/>'
    '<rect id="kelvin_indicator" x="4" y="80" width="5" height="5" fill="#fff"/>'
    "</svg>"
)

_TIMER_SVG = (
    '<svg id="TimerCard" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<rect id="background" width="197" height="98" fill="#1c1c1c"/>'
    '<rect id="foreground" width="197" height="98" fill="#dedede"/>'
    '<text id="timer" x="4" y="50" font-size="20" fill="#fff">00:00:00</text>'
    "</svg>"
)

_DASH_SVG = (
    '<svg id="DashboardCard" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<text id="date" x="4" y="20" font-size="10" fill="#fff"></text>'
    '<text id="time" x="4" y="35" font-size="10" fill="#fff"></text>'
    '<text id="pager" x="100" y="80" font-size="13" fill="#8F8F8F"'
    ' text-anchor="middle"></text>'
    '<rect id="brightness" x="4" y="90" width="189" height="4" fill="#00ff00"/>'
    "</svg>"
)

_KEY_SVG = (
    '<svg id="TestKey" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<rect id="background" color="#1c1c1c" fill="currentColor" '
    'width="120" height="120"/>'
    '<g id="foreground" color="#dedede">'
    '<g id="icon"></g>'
    '<text id="label" x="60" y="100" font-size="14" fill="currentColor">Key</text>'
    "</g>"
    "</svg>"
)

_PICTURE_KEY_SVG = (
    '<svg id="PictureKey" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<image id="picture" x="0" y="0" width="120" height="120" href=""/>'
    "</svg>"
)

_GAUGE_SVG = (
    '<svg id="GaugeCard" xmlns="http://www.w3.org/2000/svg" width="200" height="100">'
    '<polyline id="needle" points="0,0 2,-2 0,-80 -2,-2" fill="#DEDEDE"/>'
    '<text id="label">Charge</text>'
    '<text id="min_label">-50</text>'
    '<text id="mid_label">0</text>'
    '<text id="max_label">+50</text>'
    '<g id="icon"/>'
    "</svg>"
)


def _audio_spec() -> PackageSpec:
    """Build a minimal AudioCard PackageSpec for testing.

    Returns
    -------
    PackageSpec
        Spec with text, range, and event bindings matching AudioController.
    """
    return PackageSpec(
        name="AudioCard",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_AUDIO_SVG,
        bindings={
            "artist": TextBinding(node="artist", default=""),
            "title": TextBinding(node="title", default=""),
            "album": TextBinding(node="album", default=""),
            "state": TextBinding(node="state", default="Stopped"),
            "value_text": TextBinding(node="value_text", default="50%"),
            "volume": RangeBinding(node="volume_bar", default=0.5, direction="horizontal"),
            "cover": ImageBinding(node="cover"),
        },
        events=(
            EventMapping(name="toggle_play_pause", source="encoder_hold", hold_ms=500),
            EventMapping(
                name="volume_up", source="encoder_turn", direction="right", accumulate=True
            ),
            EventMapping(
                name="volume_down", source="encoder_turn", direction="left", accumulate=True
            ),
            EventMapping(
                name="mute_toggle", source="encoder_press_release", max_duration_ms=300
            ),
            EventMapping(
                name="next",
                source="encoder_press_turn",
                direction="right",
                accumulate=True,
                accumulate_max_steps=1,
            ),
            EventMapping(
                name="previous",
                source="encoder_press_turn",
                direction="left",
                accumulate=True,
                accumulate_max_steps=1,
            ),
        ),
    )


def _light_spec() -> PackageSpec:
    """Build a minimal LightCard PackageSpec for testing.

    Returns
    -------
    PackageSpec
        Spec with toggle, text, slider, and event bindings matching LightsController.
    """
    return PackageSpec(
        name="LightCard",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_LIGHT_SVG,
        bindings={
            "lights": ToggleBinding(node_on="lights_on", node_off="lights_off", default=False),
            "brightness_value_text": TextBinding(
                node="brightness_value_text", default="0%"
            ),
            "kelvin_value_text": TextBinding(node="kelvin_value_text", default="2000K"),
            "brightness": SliderBinding(
                node="brightness_indicator",
                default=0.0,
                direction="horizontal",
                min_pos=1.5,
                max_pos=183.5,
            ),
            "kelvin": SliderBinding(
                node="kelvin_indicator",
                default=0.0,
                direction="horizontal",
                min_pos=1.5,
                max_pos=183.5,
            ),
        },
        events=(
            EventMapping(name="toggle", source="encoder_press_release"),
            EventMapping(
                name="brightness_up",
                source="encoder_turn",
                direction="right",
                accumulate=True,
            ),
            EventMapping(
                name="brightness_down",
                source="encoder_turn",
                direction="left",
                accumulate=True,
            ),
            EventMapping(
                name="kelvin_up",
                source="encoder_press_turn",
                direction="right",
                accumulate=True,
                accumulate_max_steps=1,
            ),
            EventMapping(
                name="kelvin_down",
                source="encoder_press_turn",
                direction="left",
                accumulate=True,
                accumulate_max_steps=1,
            ),
        ),
    )


def _timer_spec() -> PackageSpec:
    """Build a minimal TimerCard PackageSpec for testing.

    Returns
    -------
    PackageSpec
        Spec with text and event bindings matching TimerController.
    """
    return PackageSpec(
        name="TimerCard",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_TIMER_SVG,
        bindings={
            "timer": TextBinding(node="timer", default="00:30:00"),
            "background": ColorBinding(
                node="background", attribute="color", default="#1c1c1c"
            ),
            "foreground": ColorBinding(
                node="foreground", attribute="color", default="#dedede"
            ),
        },
        events=(
            EventMapping(name="toggle", source="encoder_press_release", max_duration_ms=300),
            EventMapping(name="reset", source="encoder_hold", hold_ms=350),
            EventMapping(
                name="increase_duration",
                source="encoder_turn",
                direction="right",
                accumulate=True,
            ),
            EventMapping(
                name="decrease_duration",
                source="encoder_turn",
                direction="left",
                accumulate=True,
            ),
            EventMapping(
                name="increase_duration_alt",
                source="encoder_hold_turn",
                direction="right",
                accumulate=True,
            ),
            EventMapping(
                name="decrease_duration_alt",
                source="encoder_hold_turn",
                direction="left",
                accumulate=True,
            ),
        ),
    )


def _dash_spec() -> PackageSpec:
    """Build a minimal DashboardCard PackageSpec for testing.

    Returns
    -------
    PackageSpec
        Spec with text, range, and event bindings matching DashboardController.
    """
    return PackageSpec(
        name="DashboardCard",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_DASH_SVG,
        bindings={
            "date": TextBinding(node="date", default=""),
            "time": TextBinding(node="time", default=""),
            "nav": ListBinding(
                node="pager",
                child_tag="tspan",
                default_items=("Main", "Livingroom", "Settings"),
                default_index=0,
                active_attrs={"class": "text-selected"},
                inactive_attrs={"class": "text-muted"},
                separator=" · ",
            ),
            "brightness": RangeBinding(
                node="brightness", default=0.5, direction="horizontal"
            ),
        },
        events=(
            EventMapping(
                name="brightness_up",
                source="encoder_turn",
                direction="right",
                accumulate=True,
            ),
            EventMapping(
                name="brightness_down",
                source="encoder_turn",
                direction="left",
                accumulate=True,
            ),
            EventMapping(
                name="next_screen",
                source="encoder_press_release",
                max_duration_ms=250,
            ),
            EventMapping(
                name="change_theme",
                source="encoder_hold",
                max_duration_ms=300,
            ),
        ),
    )


def _iconkey_spec() -> PackageSpec:
    """Build a minimal IconKey PackageSpec for testing.

    Returns
    -------
    PackageSpec
        Spec mirroring ``IconKey.dui`` -- label, icon, background and
        foreground colour bindings, plus ``click``, ``press``, and
        ``release`` events.
    """
    return PackageSpec(
        name="IconKey",
        type=PackageType.KEY,
        version=1,
        svg_source=_KEY_SVG,
        bindings={
            "label": TextBinding(node="label", default="Key"),
            "icon": IconifyBinding(node="icon", size=55, default="ph:placeholder-bold"),
            "background": ColorBinding(
                node="background", attribute="color", default="#1c1c1c"
            ),
            "foreground": ColorBinding(
                node="foreground", attribute="color", default="#dedede"
            ),
        },
        events=(
            EventMapping(name="click", source="key_press_release", max_duration_ms=300),
            EventMapping(name="press", source="key_press"),
            EventMapping(name="release", source="key_release"),
        ),
    )


def _picturekey_spec() -> PackageSpec:
    """Build a minimal PictureKey PackageSpec for testing.

    Returns
    -------
    PackageSpec
        Spec with picture binding and click event.
    """
    return PackageSpec(
        name="PictureKey",
        type=PackageType.KEY,
        version=1,
        svg_source=_PICTURE_KEY_SVG,
        bindings={
            "picture": ImageBinding(node="picture"),
        },
        events=(
            EventMapping(name="click", source="key_press_release", max_duration_ms=300),
        ),
    )


def _gauge_spec() -> PackageSpec:
    """Build a minimal GaugeCard PackageSpec for testing.

    Returns
    -------
    PackageSpec
        Spec with a transform binding and encoder turn events matching
        GaugeController.
    """
    return PackageSpec(
        name="GaugeCard",
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=_GAUGE_SVG,
        bindings={
            "gauge": TransformBinding(
                node="needle",
                default=0.8,
                transforms=(
                    RotateTransform(from_angle=-50, to_angle=50, origin="0 0"),
                ),
            ),
            "label": TextBinding(node="label", default="Charge", max_width=100),
            "min_label": TextBinding(node="min_label", default="-50", max_width=30),
            "mid_label": TextBinding(node="mid_label", default="0", max_width=30),
            "max_label": TextBinding(node="max_label", default="+50", max_width=30),
            "icon": IconifyBinding(node="icon", size=24, default="ph:car-battery-light"),
        },
        events=(
            EventMapping(
                name="toggle_simulator",
                source="encoder_press_release",
                max_duration_ms=300,
            ),
            EventMapping(
                name="value_down",
                source="encoder_turn",
                direction="left",
                accumulate=False,
            ),
            EventMapping(
                name="value_up",
                source="encoder_turn",
                direction="right",
                accumulate=False,
            ),
        ),
    )


def _mock_resolve(name: str) -> PackageSpec:
    """Mock :func:`resolve_dui` that returns inline specs by package name.

    Parameters
    ----------
    name : str
        DUI package name (e.g. ``"AudioCard"``).

    Returns
    -------
    PackageSpec
        A freshly built spec matching *name*.

    Raises
    ------
    KeyError
        If no mock spec factory is registered for *name*.
    """
    _FACTORIES: dict[str, Any] = {
        "AudioCard": _audio_spec,
        "LightCard": _light_spec,
        "TimerCard": _timer_spec,
        "DashboardCard": _dash_spec,
        "GaugeCard": _gauge_spec,
        "IconKey": _iconkey_spec,
        "PictureKey": _picturekey_spec,
    }
    factory = _FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"No mock spec factory for {name!r}")
    return factory()


# ===================================================================
# compute_key_layout tests
# ===================================================================


# ===================================================================
# AudioController tests
# ===================================================================


class TestAudioController:
    """Tests for AudioController state and card bindings."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AudioController:
        """An AudioController with mocked DUI resolution."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        return AudioController(MEDIA_CATALOG, assets_dir=tmp_path)

    def test_initial_state(self, ctrl: AudioController) -> None:
        assert ctrl.volume == 50
        assert ctrl.is_muted is False
        assert ctrl.is_playing is False

    def test_card_is_dui_card(self, ctrl: AudioController) -> None:
        assert isinstance(ctrl.card, DuiCard)

    def test_card_initial_bindings(self, ctrl: AudioController) -> None:
        assert ctrl.card.get("artist") == MEDIA_CATALOG[0]["artist"]
        assert ctrl.card.get("title") == MEDIA_CATALOG[0]["title"]
        assert ctrl.card.get("state") == "Paused"
        assert ctrl.card.get("value_text") == "50%"

    def test_current_track_is_first(self, ctrl: AudioController) -> None:
        assert ctrl.current_track is MEDIA_CATALOG[0]

    async def test_play(self, ctrl: AudioController) -> None:
        await ctrl.svc.play()
        assert ctrl.is_playing is True
        assert ctrl.card.get("state") == "Playing"

    async def test_play_specific_track(self, ctrl: AudioController) -> None:
        await ctrl.svc.play(MEDIA_CATALOG[2])
        assert ctrl.is_playing is True
        assert ctrl.current_track is MEDIA_CATALOG[2]
        assert ctrl.card.get("artist") == MEDIA_CATALOG[2]["artist"]

    async def test_pause(self, ctrl: AudioController) -> None:
        await ctrl.svc.play()
        await ctrl.svc.pause()
        assert ctrl.is_playing is False
        assert ctrl.card.get("state") == "Paused"

    async def test_play_pause_toggle(self, ctrl: AudioController) -> None:
        await ctrl.svc.play_pause()
        assert ctrl.is_playing is True
        await ctrl.svc.play_pause()
        assert ctrl.is_playing is False

    async def test_next_track_wraps(self, ctrl: AudioController) -> None:
        for i in range(len(MEDIA_CATALOG)):
            t = await ctrl.svc.next_track()
            assert t is MEDIA_CATALOG[(i + 1) % len(MEDIA_CATALOG)]
        assert ctrl.card.get("artist") == ctrl.current_track["artist"]

    async def test_previous_track_wraps(self, ctrl: AudioController) -> None:
        t = await ctrl.svc.previous_track()
        assert t is MEDIA_CATALOG[-1]
        assert ctrl.card.get("artist") == MEDIA_CATALOG[-1]["artist"]

    async def test_set_volume_clamps(self, ctrl: AudioController) -> None:
        await ctrl.svc.set_volume(150)
        assert ctrl.volume == 100
        await ctrl.svc.set_volume(-50)
        assert ctrl.volume == 0

    async def test_set_volume_updates_card(self, ctrl: AudioController) -> None:
        await ctrl.svc.set_volume(75)
        assert ctrl.card.get("value_text") == "75%"
        # Volume slider binding tracks domain value normalised 0..1.
        assert ctrl.card.get("volume") == pytest.approx(0.75)

    async def test_set_volume_idempotent(self, ctrl: AudioController) -> None:
        """A same-value set neither emits nor mutates the card."""
        await ctrl.svc.set_volume(50)  # equal to default
        # value_text was set during initial render; still shows 50%.
        assert ctrl.card.get("value_text") == "50%"

    async def test_toggle_mute(self, ctrl: AudioController) -> None:
        await ctrl.svc.toggle_mute()
        assert ctrl.is_muted is True
        assert ctrl.card.get("value_text") == "Muted"
        await ctrl.svc.toggle_mute()
        assert ctrl.is_muted is False
        assert ctrl.card.get("value_text") == "50%"

    async def test_volume_handler_does_not_pre_mutate_card(
        self, ctrl: AudioController
    ) -> None:
        """volume_up handler routes through the service, not the card.

        The card's volume slider must reflect the *post-service* value,
        not a pre-emptive UI guess.  We pin the service so it ignores
        the request -- the card binding must remain unchanged.
        """
        before = ctrl.card.get("volume")
        ctrl.svc.set_volume = AsyncMock()  # type: ignore[method-assign]
        handler = ctrl.card._events._handlers["volume_up"]
        await handler(1)
        assert ctrl.card.get("volume") == before
        ctrl.svc.set_volume.assert_awaited_once_with(51)


# ===================================================================
# LightsController tests
# ===================================================================


class TestLightsController:
    """Tests for LightsController state and card bindings."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> LightsController:
        """A LightsController with mocked DUI resolution."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        return LightsController()

    def test_initial_state(self, ctrl: LightsController) -> None:
        assert ctrl.is_on is False
        assert ctrl.brightness == 0
        assert ctrl.kelvin == 2000

    def test_card_initial_bindings(self, ctrl: LightsController) -> None:
        assert ctrl.card.get("lights") is False
        assert ctrl.card.get("brightness_value_text") == "0%"
        assert ctrl.card.get("kelvin_value_text") == "2000K"
        # Slider bindings should be normalised (0/100 and (2000-2000)/(6500-2000))
        assert ctrl.card.get("brightness") == pytest.approx(0.0)
        assert ctrl.card.get("kelvin") == pytest.approx(0.0)

    async def test_toggle(self, ctrl: LightsController) -> None:
        await ctrl._svc.toggle()
        assert ctrl.is_on is True
        assert ctrl.card.get("lights") is True
        await ctrl._svc.toggle()
        assert ctrl.is_on is False

    async def test_set_brightness_clamps(self, ctrl: LightsController) -> None:
        await ctrl._svc.set_brightness(150)
        assert ctrl.brightness == 100
        assert ctrl.card.get("brightness_value_text") == "100%"
        assert ctrl.card.get("brightness") == pytest.approx(1.0)
        await ctrl._svc.set_brightness(-10)
        assert ctrl.brightness == 0
        assert ctrl.card.get("brightness") == pytest.approx(0.0)

    async def test_set_kelvin_clamps(self, ctrl: LightsController) -> None:
        await ctrl._svc.set_kelvin(1000)
        assert ctrl.kelvin == 2000
        assert ctrl.card.get("kelvin_value_text") == "2000K"
        assert ctrl.card.get("kelvin") == pytest.approx(0.0)
        await ctrl._svc.set_kelvin(9000)
        assert ctrl.kelvin == 6500
        assert ctrl.card.get("kelvin") == pytest.approx(1.0)


# ===================================================================
# TimerController tests
# ===================================================================


class TestTimerController:
    """Tests for TimerController state and card bindings."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> TimerController:
        """A TimerController with mocked DUI resolution."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        return TimerController()

    def test_initial_format(self, ctrl: TimerController) -> None:
        assert ctrl.format_time() == "00:30:00"

    def test_card_initial_binding(self, ctrl: TimerController) -> None:
        assert ctrl.card.get("timer") == "00:30:00"

    async def test_toggle_starts_and_pauses(self, ctrl: TimerController) -> None:
        await ctrl._svc.toggle()
        assert ctrl.is_running is True
        await ctrl._svc.toggle()
        assert ctrl.is_running is False

    async def test_reset(self, ctrl: TimerController) -> None:
        await ctrl._svc.toggle()
        await ctrl._svc.reset()
        assert ctrl.is_running is False
        assert ctrl.remaining == 1800

    async def test_adjust_duration(self, ctrl: TimerController) -> None:
        await ctrl._svc.adjust_duration(60)
        assert ctrl.duration == 1860
        assert ctrl.remaining == 1860
        assert ctrl.card.get("timer") == "00:31:00"

    async def test_adjust_duration_clamps_to_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        ctrl = TimerController()
        await ctrl._svc.adjust_duration(-10000)
        assert ctrl.duration == 0
        assert ctrl.card.get("timer") == "00:00:00"

    async def test_toggle_snapshots_default(
        self, ctrl: TimerController
    ) -> None:
        """Starting the timer captures remaining as new default."""
        await ctrl._svc.adjust_duration(60)  # 1860 s
        await ctrl._svc.toggle()  # start -> snapshots 1860 as default
        await ctrl._svc.toggle()  # pause
        await ctrl._svc.reset()
        assert ctrl.remaining == 1860

    async def test_coarse_step(self, ctrl: TimerController) -> None:
        """increase_duration / decrease_duration use COARSE_STEP_S (600 s / 10 min)."""
        assert ctrl.COARSE_STEP_S == 600

    async def test_fine_step(self, ctrl: TimerController) -> None:
        """increase_duration_alt / decrease_duration_alt use FINE_STEP_S (30 s)."""
        assert ctrl.FINE_STEP_S == 30


# ===================================================================
# DashboardController tests
# ===================================================================


class TestDashboardController:
    """Tests for DashboardController.

    Deck brightness is *deck-owned* state -- the controller observes
    :attr:`Deck.on_brightness_changed` rather than holding its own
    value.  The tests verify that:

    * Telemetry pushes from the service drive the temperature/humidity
      bindings.
    * Brightness handlers route through ``deck.set_brightness``, never
      the card directly.
    * ``on_attach`` replays the controller's last-known brightness onto
      the freshly-connected deck (the reconnect contract).
    """

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> DashboardController:
        """A DashboardController with mocked DUI resolution."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        return DashboardController()

    def _real_deck(self, brightness: int = 50) -> Any:
        """Build a real Deck so the AsyncEvents are wired correctly."""
        from deckui.runtime.deck import Deck

        return Deck(serial_number="TEST_DASH", brightness=brightness)

    def test_initial_state(self, ctrl: DashboardController) -> None:
        # 0.5 default -> 50% in domain units.
        assert ctrl.brightness == 50

    def test_card_initial_bindings(self, ctrl: DashboardController) -> None:
        # date and time are set in __init__
        assert ctrl.card.get("date") != ""
        assert ctrl.card.get("time") != ""

    def test_get_date_format(self, ctrl: DashboardController) -> None:
        date = ctrl.get_date()
        assert len(date) == 10
        assert date[4] == "-" and date[7] == "-"

    def test_get_time_format(self, ctrl: DashboardController) -> None:
        assert ":" in ctrl.get_time()

    async def test_brightness_handler_routes_through_deck(
        self, ctrl: DashboardController
    ) -> None:
        """brightness_up only calls deck.set_brightness; no direct card mutation."""
        deck = self._real_deck(brightness=50)
        await ctrl.on_attach(deck)
        before = ctrl.card.get("brightness")

        # Pin the deck so the event never fires; the card must stay put.
        deck.set_brightness = AsyncMock()  # type: ignore[method-assign]
        handler = ctrl.card._events._handlers["brightness_up"]
        await handler(1)
        assert ctrl.card.get("brightness") == before
        deck.set_brightness.assert_awaited_once_with(51)

    async def test_brightness_event_updates_card_and_last_known(
        self, ctrl: DashboardController
    ) -> None:
        """deck.set_brightness fires the event; subscriber updates UI + memory."""
        deck = self._real_deck(brightness=50)
        await ctrl.on_attach(deck)

        await deck.set_brightness(73)
        assert ctrl.brightness == 73
        assert ctrl.card.get("brightness") == pytest.approx(0.73)

    async def test_on_attach_replays_last_known(
        self, ctrl: DashboardController
    ) -> None:
        """Reconnect: a fresh deck gets the user's last value replayed."""
        first = self._real_deck(brightness=50)
        await ctrl.on_attach(first)
        await first.set_brightness(80)
        assert ctrl.brightness == 80

        # Simulate disconnect + reconnect: a brand-new Deck instance.
        second = self._real_deck(brightness=50)
        await ctrl.on_attach(second)
        # The replay must have driven the new deck to 80.
        assert second.brightness == 80

    async def test_on_attach_no_replay_when_already_matching(
        self, ctrl: DashboardController
    ) -> None:
        """If the new deck already matches, replay is a silent no-op."""
        deck = self._real_deck(brightness=50)
        # 50 matches the manifest default the controller is holding.
        events: list[int] = []

        @deck.on_brightness_changed
        async def _on(value: int) -> None:
            events.append(value)

        await ctrl.on_attach(deck)
        assert events == []


# ===================================================================
# SceneController tests
# ===================================================================


class TestSceneController:
    """Tests for SceneController key creation."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> SceneController:
        """A SceneController with mocked DUI resolution."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        return SceneController(SCENE_DEFS)

    def test_creates_correct_number_of_keys(self, ctrl: SceneController) -> None:
        assert len(ctrl.keys) == len(SCENE_DEFS)

    def test_keys_are_dui_keys(self, ctrl: SceneController) -> None:
        for key in ctrl.keys:
            assert isinstance(key, DuiKey)

    def test_install_places_keys_at_given_positions(self, ctrl: SceneController) -> None:
        screen = MagicMock()
        ctrl.install(screen, [2, 3, 6, 7])
        positions = [call.args[0] for call in screen.set_key.call_args_list]
        assert positions == [2, 3, 6, 7]

    def test_install_truncates_to_fewer_positions(self, ctrl: SceneController) -> None:
        screen = MagicMock()
        ctrl.install(screen, [0, 1])
        assert screen.set_key.call_count == 2

    def test_install_truncates_to_fewer_keys(self, ctrl: SceneController) -> None:
        screen = MagicMock()
        ctrl.install(screen, list(range(10)))
        assert screen.set_key.call_count == len(SCENE_DEFS)

    def test_initial_colors_are_defaults(self, ctrl: SceneController) -> None:
        """Each key starts with default background color from manifest."""
        for key in ctrl.keys:
            assert key.get("background") == "#1c1c1c"

    async def test_press_does_not_change_colors(self, ctrl: SceneController) -> None:
        """Press no longer swaps colors; visual feedback is disabled."""
        key = ctrl.keys[0]
        await key.dispatch(pressed=True)
        assert key.get("background") == "#1c1c1c"

    async def test_release_keeps_colors(self, ctrl: SceneController) -> None:
        """Release keeps colors unchanged since visual feedback is disabled."""
        key = ctrl.keys[0]
        await key.dispatch(pressed=True)
        await key.dispatch(pressed=False)
        assert key.get("background") == "#1c1c1c"

    async def test_press_release_refresh_from_click_forward(
        self, ctrl: SceneController
    ) -> None:
        """Only the click forward on release triggers a refresh; press does not."""
        key = ctrl.keys[0]
        refreshes = 0

        async def _refresh() -> None:
            nonlocal refreshes
            refreshes += 1
            key.mark_clean()

        key.set_refresh_callback(_refresh)
        await key.dispatch(pressed=True)
        await key.dispatch(pressed=False)
        assert refreshes == 1

    async def test_keys_remain_independent(
        self, ctrl: SceneController
    ) -> None:
        """Pressing one key does not affect another key's state."""
        first, second = ctrl.keys[0], ctrl.keys[1]
        await first.dispatch(pressed=True)
        assert first.get("background") == "#1c1c1c"
        assert second.get("background") == "#1c1c1c"


# ===================================================================
# FavoritesController tests
# ===================================================================


class TestFavoritesController:
    """Tests for FavoritesController key creation."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FavoritesController:
        """A FavoritesController with mocked DUI resolution."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        audio = AudioController(MEDIA_CATALOG, assets_dir=tmp_path)
        return FavoritesController(MEDIA_CATALOG, audio, assets_dir=tmp_path)

    def test_creates_correct_number_of_keys(self, ctrl: FavoritesController) -> None:
        assert len(ctrl.keys) == len(MEDIA_CATALOG)

    def test_keys_are_dui_keys(self, ctrl: FavoritesController) -> None:
        for key in ctrl.keys:
            assert isinstance(key, DuiKey)

    def test_install_places_keys_at_given_positions(
        self, ctrl: FavoritesController
    ) -> None:
        screen = MagicMock()
        ctrl.install(screen, [0, 1, 4, 5])
        positions = [call.args[0] for call in screen.set_key.call_args_list]
        assert positions == [0, 1, 4, 5]

    def test_install_truncates_to_fewer_positions(
        self, ctrl: FavoritesController
    ) -> None:
        screen = MagicMock()
        ctrl.install(screen, [0, 1])
        assert screen.set_key.call_count == 2


# ===================================================================
# GaugeController tests
# ===================================================================


class TestGaugeController:
    """Tests for GaugeController state and card bindings."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> GaugeController:
        """A GaugeController with mocked DUI resolution."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        return GaugeController(simulate=False)

    def test_initial_value(self, ctrl: GaugeController) -> None:
        """Gauge starts at the manifest default (0.8)."""
        assert ctrl.value == pytest.approx(0.8)

    def test_card_is_dui_card(self, ctrl: GaugeController) -> None:
        assert isinstance(ctrl.card, DuiCard)

    def test_card_initial_binding(self, ctrl: GaugeController) -> None:
        """Card gauge binding matches the initial service value."""
        assert ctrl.card.get("gauge") == pytest.approx(0.8)

    async def test_adjust_up(self, ctrl: GaugeController) -> None:
        """Adjusting up increases the value and updates the card."""
        await ctrl._svc.adjust(0.05)
        assert ctrl.value == pytest.approx(0.85)
        assert ctrl.card.get("gauge") == pytest.approx(0.85)

    async def test_adjust_down(self, ctrl: GaugeController) -> None:
        """Adjusting down decreases the value and updates the card."""
        await ctrl._svc.adjust(-0.1)
        assert ctrl.value == pytest.approx(0.7)
        assert ctrl.card.get("gauge") == pytest.approx(0.7)

    async def test_clamps_to_max(self, ctrl: GaugeController) -> None:
        """Value is clamped to 1.0."""
        await ctrl._svc.adjust(1.0)
        assert ctrl.value == pytest.approx(1.0)

    async def test_clamps_to_min(self, ctrl: GaugeController) -> None:
        """Value is clamped to 0.0."""
        await ctrl._svc.adjust(-2.0)
        assert ctrl.value == pytest.approx(0.0)

    async def test_idempotent_at_boundary(self, ctrl: GaugeController) -> None:
        """Adjusting past a boundary emits nothing on repeated calls."""
        await ctrl._svc.adjust(1.0)  # clamp to 1.0
        events: list[float] = []
        ctrl._svc.on_value_changed.subscribe(lambda v: events.append(v))
        await ctrl._svc.adjust(0.1)  # already at max
        assert events == []

    async def test_set_value(self, ctrl: GaugeController) -> None:
        """set_value sets an absolute value."""
        await ctrl._svc.set_value(0.5)
        assert ctrl.value == pytest.approx(0.5)
        assert ctrl.card.get("gauge") == pytest.approx(0.5)

    async def test_forward_value_up(self, ctrl: GaugeController) -> None:
        """value_up event handler routes through the service."""
        handler = ctrl.card._events._handlers["value_up"]
        await handler(1)
        assert ctrl.value == pytest.approx(0.81)

    async def test_forward_value_down(self, ctrl: GaugeController) -> None:
        """value_down event handler routes through the service."""
        handler = ctrl.card._events._handlers["value_down"]
        await handler(1)
        assert ctrl.value == pytest.approx(0.79)

    async def test_on_attach_starts_simulator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """on_attach starts the drift task when simulate=True."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        ctrl = GaugeController(simulate=True)
        deck = MagicMock()
        await ctrl.on_attach(deck)
        assert ctrl._svc._task is not None
        await ctrl.on_detach()
        assert ctrl._svc._task is None

    async def test_on_attach_no_task_when_disabled(
        self, ctrl: GaugeController
    ) -> None:
        """on_attach does not start a task when simulate=False."""
        deck = MagicMock()
        await ctrl.on_attach(deck)
        assert ctrl._svc._task is None

    def test_label_binding_set(self, ctrl: GaugeController) -> None:
        """Label binding is initialised from the manifest default."""
        assert ctrl.card.get("label") == "Charge"

    def test_min_label_binding_set(self, ctrl: GaugeController) -> None:
        """min_label binding is initialised from the manifest default."""
        assert ctrl.card.get("min_label") == "-50"

    def test_mid_label_binding_set(self, ctrl: GaugeController) -> None:
        """mid_label binding is initialised from the manifest default."""
        assert ctrl.card.get("mid_label") == "0"

    def test_max_label_binding_set(self, ctrl: GaugeController) -> None:
        """max_label binding is initialised from the manifest default."""
        assert ctrl.card.get("max_label") == "+50"

    def test_icon_binding_set(self, ctrl: GaugeController) -> None:
        """icon binding is initialised from the manifest default."""
        assert ctrl.card.get("icon") == "ph:car-battery-light"

    async def test_toggle_simulator_starts_when_stopped(
        self, ctrl: GaugeController
    ) -> None:
        """toggle_simulator starts the drift task when it is stopped."""
        assert ctrl._svc._task is None
        await ctrl._toggle_simulator()
        assert ctrl._svc._simulate is True
        assert ctrl._svc._task is not None
        # Clean up
        await ctrl._svc.stop()

    async def test_toggle_simulator_stops_when_running(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """toggle_simulator stops the drift task when it is running."""
        monkeypatch.setattr("deckui.dui.repository.resolve_dui", _mock_resolve)
        ctrl = GaugeController(simulate=True)
        deck = MagicMock()
        await ctrl.on_attach(deck)
        assert ctrl._svc._task is not None
        await ctrl._toggle_simulator()
        assert ctrl._svc._simulate is False
        assert ctrl._svc._task is None


# ===================================================================
# ScreenCycler tests
# ===================================================================


class TestScreenCycler:
    """Tests for the ScreenCycler controller."""

    def _stub_deck(self) -> Any:
        """Build a minimal deck stub with a real ``on_screen_changed``.

        The cycler subscribes to the deck's ``on_screen_changed`` event
        in ``on_attach``; pure ``MagicMock`` doesn't expose AsyncEvent
        semantics, so we wire one in by hand and have ``set_screen``
        emit it.
        """
        from deckui import AsyncEvent

        deck = MagicMock()
        deck.on_screen_changed = AsyncEvent()

        async def _set_screen(name: str) -> None:
            await deck.on_screen_changed.emit(name, {})

        deck.set_screen = AsyncMock(side_effect=_set_screen)
        return deck

    def test_rejects_empty_screen_list(self) -> None:
        with pytest.raises(ValueError):
            ScreenCycler([])

    def test_starts_on_first_screen(self) -> None:
        cycler = ScreenCycler(["main", "settings", "info"])
        assert cycler.current == "main"

    async def test_advance_wraps_around(self) -> None:
        cycler = ScreenCycler(["a", "b", "c"])
        deck = self._stub_deck()
        cycler.on_attach(deck)

        await cycler.advance()
        assert cycler.current == "b"
        deck.set_screen.assert_awaited_with("b")

        await cycler.advance()
        assert cycler.current == "c"

        await cycler.advance()
        assert cycler.current == "a"
        targets = [c.args[0] for c in deck.set_screen.await_args_list]
        assert targets == ["b", "c", "a"]

    async def test_current_tracks_external_screen_change(self) -> None:
        """Cycler observes deck.on_screen_changed even from external callers."""
        cycler = ScreenCycler(["a", "b", "c"])
        deck = self._stub_deck()
        cycler.on_attach(deck)

        # External code (not the cycler) drives the deck to "c".
        await deck.set_screen("c")
        assert cycler.current == "c"

        # The cycler then advances from "c" -- next is "a".
        await cycler.advance()
        assert cycler.current == "a"

    async def test_advance_without_deck_is_noop(self) -> None:
        cycler = ScreenCycler(["a", "b"])
        await cycler.advance()
        assert cycler.current == "a"

    async def test_attach_binds_event_to_advance(self) -> None:
        spec = _dash_spec()
        card = DuiCard(spec)
        cycler = ScreenCycler(["a", "b"])
        deck = self._stub_deck()
        cycler.on_attach(deck)

        cycler.attach(card)
        handler = card._events._handlers["next_screen"]
        await handler()
        assert cycler.current == "b"
        deck.set_screen.assert_awaited_with("b")

    async def test_attach_custom_event_name(self) -> None:
        spec = PackageSpec(
            name="DashboardCard",
            type=PackageType.TOUCH_STRIP_CARD,
            version=1,
            svg_source=_DASH_SVG,
            bindings=_dash_spec().bindings,
            events=(
                EventMapping(
                    name="rotate_screen",
                    source="encoder_press_release",
                    max_duration_ms=250,
                ),
            ),
        )
        card = DuiCard(spec)
        cycler = ScreenCycler(["x", "y"])
        deck = self._stub_deck()
        cycler.on_attach(deck)

        cycler.attach(card, event="rotate_screen")
        handler = card._events._handlers["rotate_screen"]
        await handler()
        assert cycler.current == "y"
