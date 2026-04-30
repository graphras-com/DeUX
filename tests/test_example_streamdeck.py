"""Tests for the Stream Deck+ demo example (examples/streamdeck.py)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make examples importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))

from streamdeck import (
    MEDIA_CATALOG,
    AudioPlayer,
    DashboardController,
    LightsController,
    TimerController,
    setup_audio_card,
    setup_dashboard_card,
    setup_favorites,
    setup_lights_card,
    setup_scenes,
    setup_timer_card,
)

from deckui.dui.card import DuiCard
from deckui.dui.schema import (
    EventMapping,
    IconifyBinding,
    PackageSpec,
    PackageType,
    RangeBinding,
    TextBinding,
    ToggleBinding,
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
    '<text id="timer" x="4" y="50" font-size="20" fill="#fff">00:00:00</text>'
    "</svg>"
)

_DASH_SVG = (
    '<svg id="DashboardCard" xmlns="http://www.w3.org/2000/svg" width="197" height="98">'
    '<text id="date" x="4" y="20" font-size="10" fill="#fff"></text>'
    '<text id="time" x="4" y="35" font-size="10" fill="#fff"></text>'
    '<text id="temperature" x="4" y="50" font-size="10" fill="#fff"></text>'
    '<text id="humidity" x="4" y="65" font-size="10" fill="#fff"></text>'
    '<rect id="deck_brightness" x="4" y="80" width="189" height="4" fill="#00ff00"/>'
    "</svg>"
)

_KEY_SVG = (
    '<svg id="TestKey" xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
    '<rect id="background" width="120" height="120" fill="#1c1c1c"/>'
    '<g id="icon"></g>'
    '<text id="label" x="60" y="100" font-size="14" fill="#fff">Key</text>'
    "</svg>"
)


def _card_spec(name: str, svg: str, bindings: dict, events: tuple = ()) -> PackageSpec:
    """Build a minimal TouchStripCard PackageSpec.

    Parameters
    ----------
    name : str
        Package name.
    svg : str
        SVG source string.
    bindings : dict
        Mapping of binding name to binding descriptor.
    events : tuple
        Event mappings.

    Returns
    -------
    PackageSpec
        A valid spec for testing.
    """
    return PackageSpec(
        name=name,
        type=PackageType.TOUCH_STRIP_CARD,
        version=1,
        svg_source=svg,
        bindings=bindings,
        events=events,
    )


def _key_spec(name: str = "TestKey", svg: str = _KEY_SVG) -> PackageSpec:
    """Build a minimal Key PackageSpec.

    Parameters
    ----------
    name : str
        Package name.
    svg : str
        SVG source string.

    Returns
    -------
    PackageSpec
        A valid key spec for testing.
    """
    return PackageSpec(
        name=name,
        type=PackageType.KEY,
        version=1,
        svg_source=svg,
        bindings={
            "label": TextBinding(node="label", default="Key"),
            "icon": IconifyBinding(node="icon", size=55, default="ph:placeholder-bold"),
        },
        events=(
            EventMapping(name="click", source="key_press_release", max_duration_ms=300),
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# AudioPlayer tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAudioPlayer:
    """Tests for the mock AudioPlayer."""

    def test_initial_state(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG, initial_volume=0.5)
        assert player.volume_level == 0.5
        assert player.is_muted is False
        assert player.is_playing is False

    def test_current_track_is_first(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        assert player.current_track is MEDIA_CATALOG[0]

    async def test_play(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        await player.play()
        assert player.is_playing is True

    async def test_play_specific_track(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        await player.play(MEDIA_CATALOG[2])
        assert player.is_playing is True
        assert player.current_track is MEDIA_CATALOG[2]

    async def test_pause(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        await player.play()
        await player.pause()
        assert player.is_playing is False

    async def test_play_pause_toggle(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        await player.play_pause()
        assert player.is_playing is True
        await player.play_pause()
        assert player.is_playing is False

    async def test_next_track_wraps(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        for i in range(len(MEDIA_CATALOG)):
            t = await player.next_track()
            assert t is MEDIA_CATALOG[(i + 1) % len(MEDIA_CATALOG)]

    async def test_previous_track_wraps(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        t = await player.previous_track()
        assert t is MEDIA_CATALOG[-1]

    async def test_set_volume_clamps(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        await player.set_volume(1.5)
        assert player.volume_level == 1.0
        await player.set_volume(-0.5)
        assert player.volume_level == 0.0

    async def test_toggle_mute(self) -> None:
        player = AudioPlayer(MEDIA_CATALOG)
        await player.toggle_mute()
        assert player.is_muted is True
        await player.toggle_mute()
        assert player.is_muted is False


# ═══════════════════════════════════════════════════════════════════════════
# LightsController tests
# ═══════════════════════════════════════════════════════════════════════════


class TestLightsController:
    """Tests for the mock LightsController."""

    def test_initial_state(self) -> None:
        ctrl = LightsController(brightness=70, kelvin=3500)
        assert ctrl.is_on is True
        assert ctrl.brightness == 70
        assert ctrl.kelvin == 3500

    async def test_toggle(self) -> None:
        ctrl = LightsController()
        await ctrl.toggle()
        assert ctrl.is_on is False
        await ctrl.toggle()
        assert ctrl.is_on is True

    async def test_set_brightness_clamps(self) -> None:
        ctrl = LightsController()
        await ctrl.set_brightness(150)
        assert ctrl.brightness == 100
        await ctrl.set_brightness(-10)
        assert ctrl.brightness == 0

    async def test_set_kelvin_clamps(self) -> None:
        ctrl = LightsController()
        await ctrl.set_kelvin(1000)
        assert ctrl.kelvin == 2000
        await ctrl.set_kelvin(9000)
        assert ctrl.kelvin == 6500


# ═══════════════════════════════════════════════════════════════════════════
# TimerController tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTimerController:
    """Tests for the mock TimerController."""

    def test_initial_format(self) -> None:
        ctrl = TimerController(initial_seconds=3661)
        assert ctrl._format() == "01:01:01"

    async def test_toggle_starts_and_pauses(self) -> None:
        ctrl = TimerController()
        await ctrl.toggle()
        assert ctrl.is_running is True
        await ctrl.toggle()
        assert ctrl.is_running is False

    async def test_reset(self) -> None:
        ctrl = TimerController(initial_seconds=600)
        await ctrl.toggle()
        await ctrl.reset()
        assert ctrl.is_running is False
        assert ctrl.remaining == 600

    async def test_adjust_duration(self) -> None:
        ctrl = TimerController(initial_seconds=300)
        await ctrl.adjust_duration(60)
        assert ctrl.duration == 360
        assert ctrl.remaining == 360

    async def test_adjust_duration_clamps_to_zero(self) -> None:
        ctrl = TimerController(initial_seconds=10)
        await ctrl.adjust_duration(-100)
        assert ctrl.duration == 0


# ═══════════════════════════════════════════════════════════════════════════
# DashboardController tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDashboardController:
    """Tests for the mock DashboardController."""

    def test_initial_state(self) -> None:
        ctrl = DashboardController(deck_brightness=40)
        assert ctrl.deck_brightness == 40
        assert ctrl.temperature == "22°C"
        assert ctrl.humidity == "45%"

    def test_get_date_format(self) -> None:
        ctrl = DashboardController()
        date = ctrl.get_date()
        # Should be YYYY-MM-DD
        assert len(date) == 10
        assert date[4] == "-" and date[7] == "-"

    def test_get_time_format(self) -> None:
        ctrl = DashboardController()
        time_str = ctrl.get_time()
        assert ":" in time_str

    async def test_set_brightness_clamps(self) -> None:
        ctrl = DashboardController()
        await ctrl.set_brightness(200)
        assert ctrl.deck_brightness == 100
        await ctrl.set_brightness(-50)
        assert ctrl.deck_brightness == 0


# ═══════════════════════════════════════════════════════════════════════════
# Card setup function tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSetupAudioCard:
    """Tests for setup_audio_card wiring."""

    @pytest.fixture
    def audio_spec(self) -> PackageSpec:
        """Minimal AudioCard spec with volume range and text bindings."""
        return _card_spec(
            "AudioCard",
            _AUDIO_SVG,
            bindings={
                "artist": TextBinding(node="artist", default=""),
                "title": TextBinding(node="title", default=""),
                "album": TextBinding(node="album", default=""),
                "state": TextBinding(node="state", default="Stopped"),
                "value_text": TextBinding(node="value_text", default="50%"),
                "volume": RangeBinding(node="volume_bar", default=0.5, direction="horizontal"),
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
                    name="mute_toggle",
                    source="encoder_press_release",
                    max_duration_ms=300,
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

    def test_populates_initial_state(self, audio_spec: PackageSpec) -> None:
        card = DuiCard(audio_spec)
        player = AudioPlayer(MEDIA_CATALOG, initial_volume=0.5)
        setup_audio_card(card, player)

        assert card.get("artist") == MEDIA_CATALOG[0]["artist"]
        assert card.get("title") == MEDIA_CATALOG[0]["title"]
        assert card.get("state") == "Paused"
        assert card.get("value_text") == "50%"


class TestSetupLightsCard:
    """Tests for setup_lights_card wiring."""

    @pytest.fixture
    def light_spec(self) -> PackageSpec:
        """Minimal LightCard spec."""
        return _card_spec(
            "LightCard",
            _LIGHT_SVG,
            bindings={
                "lights": ToggleBinding(
                    node_on="lights_on", node_off="lights_off", default=False
                ),
                "brightness_value_text": TextBinding(
                    node="brightness_value_text", default="0%"
                ),
                "kelvin_value_text": TextBinding(node="kelvin_value_text", default="2000K"),
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

    def test_populates_initial_state(self, light_spec: PackageSpec) -> None:
        card = DuiCard(light_spec)
        lights = LightsController(brightness=80, kelvin=4000)
        setup_lights_card(card, lights)

        assert card.get("lights") is True
        assert card.get("brightness_value_text") == "80%"
        assert card.get("kelvin_value_text") == "4000K"


class TestSetupTimerCard:
    """Tests for setup_timer_card wiring."""

    @pytest.fixture
    def timer_spec(self) -> PackageSpec:
        """Minimal TimerCard spec."""
        return _card_spec(
            "TimerCard",
            _TIMER_SVG,
            bindings={
                "timer": TextBinding(node="timer", default="00:00:00"),
            },
            events=(
                EventMapping(
                    name="toggle", source="encoder_press_release", max_duration_ms=300
                ),
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
            ),
        )

    def test_populates_initial_state(self, timer_spec: PackageSpec) -> None:
        card = DuiCard(timer_spec)
        timer = TimerController(initial_seconds=300)
        setup_timer_card(card, timer)

        assert card.get("timer") == "00:05:00"


class TestSetupDashboardCard:
    """Tests for setup_dashboard_card wiring."""

    @pytest.fixture
    def dash_spec(self) -> PackageSpec:
        """Minimal DashboardCard spec."""
        return _card_spec(
            "DashboardCard",
            _DASH_SVG,
            bindings={
                "date": TextBinding(node="date", default=""),
                "time": TextBinding(node="time", default=""),
                "temperature": TextBinding(node="temperature", default=""),
                "humidity": TextBinding(node="humidity", default=""),
                "deck_brightness": RangeBinding(
                    node="deck_brightness", default=0.5, direction="horizontal"
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
            ),
        )

    def test_populates_initial_state(self, dash_spec: PackageSpec) -> None:
        card = DuiCard(dash_spec)
        dashboard = DashboardController(deck_brightness=60)
        mock_deck = MagicMock()
        setup_dashboard_card(card, dashboard, mock_deck)

        assert card.get("temperature") == "22°C"
        assert card.get("humidity") == "45%"


class TestSetupFavorites:
    """Tests for setup_favorites key creation."""

    def test_creates_keys_at_correct_positions(self) -> None:
        spec = _key_spec()
        screen = MagicMock()
        player = AudioPlayer(MEDIA_CATALOG)
        keys = setup_favorites(screen, player, spec)

        assert len(keys) == 4
        # Verify set_key was called for each favorite position
        positions = [call.args[0] for call in screen.set_key.call_args_list]
        assert positions == [0, 1, 4, 5]


class TestSetupScenes:
    """Tests for setup_scenes key creation."""

    def test_creates_keys_at_correct_positions(self) -> None:
        spec = _key_spec()
        screen = MagicMock()
        setup_scenes(screen, spec)

        positions = [call.args[0] for call in screen.set_key.call_args_list]
        assert positions == [2, 3, 6, 7]
