"""Tests for the Stream Deck example (examples/streamdeck.py)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from deckui.dui.card import DuiCard
from deckui.dui.key import DuiKey
from deckui.dui.schema import (
    ColorBinding,
    EventMapping,
    IconifyBinding,
    ImageBinding,
    PackageSpec,
    PackageType,
    RangeBinding,
    SliderBinding,
    TextBinding,
    ToggleBinding,
)

# Make examples importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))

from streamdeck import (
    MEDIA_CATALOG,
    SCENE_DEFS,
    AudioController,
    DashboardController,
    FavoritesController,
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
    '<text id="temperature" x="4" y="50" font-size="10" fill="#fff"></text>'
    '<text id="humidity" x="4" y="65" font-size="10" fill="#fff"></text>'
    '<rect id="deck_brightness" x="4" y="80" width="189" height="4" fill="#00ff00"/>'
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
            "timer": TextBinding(node="timer", default="00:00:00"),
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
            EventMapping(
                name="next_screen",
                source="encoder_press_release",
                max_duration_ms=250,
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
        """An AudioController with a mocked load_package."""
        monkeypatch.setattr(
            "streamdeck.load_package", lambda _path: _audio_spec()
        )
        return AudioController(MEDIA_CATALOG, initial_volume=0.5, packages_dir=tmp_path)

    def test_initial_state(self, ctrl: AudioController) -> None:
        assert ctrl.volume_level == 0.5
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
        await ctrl.play()
        assert ctrl.is_playing is True
        assert ctrl.card.get("state") == "Playing"

    async def test_play_specific_track(self, ctrl: AudioController) -> None:
        await ctrl.play(MEDIA_CATALOG[2])
        assert ctrl.is_playing is True
        assert ctrl.current_track is MEDIA_CATALOG[2]
        assert ctrl.card.get("artist") == MEDIA_CATALOG[2]["artist"]

    async def test_pause(self, ctrl: AudioController) -> None:
        await ctrl.play()
        await ctrl.pause()
        assert ctrl.is_playing is False
        assert ctrl.card.get("state") == "Paused"

    async def test_play_pause_toggle(self, ctrl: AudioController) -> None:
        await ctrl.play_pause()
        assert ctrl.is_playing is True
        await ctrl.play_pause()
        assert ctrl.is_playing is False

    async def test_next_track_wraps(self, ctrl: AudioController) -> None:
        for i in range(len(MEDIA_CATALOG)):
            t = await ctrl.next_track()
            assert t is MEDIA_CATALOG[(i + 1) % len(MEDIA_CATALOG)]
        assert ctrl.card.get("artist") == ctrl.current_track["artist"]

    async def test_previous_track_wraps(self, ctrl: AudioController) -> None:
        t = await ctrl.previous_track()
        assert t is MEDIA_CATALOG[-1]
        assert ctrl.card.get("artist") == MEDIA_CATALOG[-1]["artist"]

    async def test_set_volume_clamps(self, ctrl: AudioController) -> None:
        await ctrl.set_volume(1.5)
        assert ctrl.volume_level == 1.0
        await ctrl.set_volume(-0.5)
        assert ctrl.volume_level == 0.0

    async def test_set_volume_updates_card(self, ctrl: AudioController) -> None:
        await ctrl.set_volume(0.75)
        assert ctrl.card.get("value_text") == "75%"

    async def test_toggle_mute(self, ctrl: AudioController) -> None:
        await ctrl.toggle_mute()
        assert ctrl.is_muted is True
        assert ctrl.card.get("value_text") == "Muted"
        await ctrl.toggle_mute()
        assert ctrl.is_muted is False
        assert ctrl.card.get("value_text") == "50%"


# ===================================================================
# LightsController tests
# ===================================================================


class TestLightsController:
    """Tests for LightsController state and card bindings."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> LightsController:
        """A LightsController with a mocked load_package."""
        monkeypatch.setattr(
            "streamdeck.load_package", lambda _path: _light_spec()
        )
        return LightsController(brightness=80, kelvin=4000)

    def test_initial_state(self, ctrl: LightsController) -> None:
        assert ctrl.is_on is True
        assert ctrl.brightness == 80
        assert ctrl.kelvin == 4000

    def test_card_initial_bindings(self, ctrl: LightsController) -> None:
        assert ctrl.card.get("lights") is True
        assert ctrl.card.get("brightness_value_text") == "80%"
        assert ctrl.card.get("kelvin_value_text") == "4000K"
        # Slider bindings should be normalised (80/100 and (4000-2000)/(6500-2000))
        assert ctrl.card.get("brightness") == pytest.approx(0.8)
        assert ctrl.card.get("kelvin") == pytest.approx((4000 - 2000) / (6500 - 2000))

    async def test_toggle(self, ctrl: LightsController) -> None:
        await ctrl.toggle()
        assert ctrl.is_on is False
        assert ctrl.card.get("lights") is False
        await ctrl.toggle()
        assert ctrl.is_on is True

    async def test_set_brightness_clamps(self, ctrl: LightsController) -> None:
        await ctrl.set_brightness(150)
        assert ctrl.brightness == 100
        assert ctrl.card.get("brightness_value_text") == "100%"
        assert ctrl.card.get("brightness") == pytest.approx(1.0)
        await ctrl.set_brightness(-10)
        assert ctrl.brightness == 0
        assert ctrl.card.get("brightness") == pytest.approx(0.0)

    async def test_set_kelvin_clamps(self, ctrl: LightsController) -> None:
        await ctrl.set_kelvin(1000)
        assert ctrl.kelvin == 2000
        assert ctrl.card.get("kelvin_value_text") == "2000K"
        assert ctrl.card.get("kelvin") == pytest.approx(0.0)
        await ctrl.set_kelvin(9000)
        assert ctrl.kelvin == 6500
        assert ctrl.card.get("kelvin") == pytest.approx(1.0)


# ===================================================================
# TimerController tests
# ===================================================================


class TestTimerController:
    """Tests for TimerController state and card bindings."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> TimerController:
        """A TimerController with a mocked load_package."""
        monkeypatch.setattr(
            "streamdeck.load_package", lambda _path: _timer_spec()
        )
        return TimerController(initial_seconds=300)

    def test_initial_format(self, ctrl: TimerController) -> None:
        assert ctrl.format_time() == "00:05:00"

    def test_card_initial_binding(self, ctrl: TimerController) -> None:
        assert ctrl.card.get("timer") == "00:05:00"

    async def test_toggle_starts_and_pauses(self, ctrl: TimerController) -> None:
        await ctrl.toggle()
        assert ctrl.is_running is True
        await ctrl.toggle()
        assert ctrl.is_running is False

    async def test_reset(self, ctrl: TimerController) -> None:
        await ctrl.toggle()
        await ctrl.reset()
        assert ctrl.is_running is False
        assert ctrl.remaining == 300

    async def test_adjust_duration(self, ctrl: TimerController) -> None:
        await ctrl.adjust_duration(60)
        assert ctrl.duration == 360
        assert ctrl.remaining == 360
        assert ctrl.card.get("timer") == "00:06:00"

    async def test_adjust_duration_clamps_to_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "streamdeck.load_package", lambda _path: _timer_spec()
        )
        ctrl = TimerController(initial_seconds=10)
        await ctrl.adjust_duration(-100)
        assert ctrl.duration == 0
        assert ctrl.card.get("timer") == "00:00:00"


# ===================================================================
# DashboardController tests
# ===================================================================


class TestDashboardController:
    """Tests for DashboardController state and card bindings."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> DashboardController:
        """A DashboardController with a mocked load_package."""
        monkeypatch.setattr(
            "streamdeck.load_package", lambda _path: _dash_spec()
        )
        return DashboardController(deck_brightness=60)

    def test_initial_state(self, ctrl: DashboardController) -> None:
        assert ctrl.deck_brightness == 60
        assert ctrl.temperature == "22C"
        assert ctrl.humidity == "45%"

    def test_card_initial_bindings(self, ctrl: DashboardController) -> None:
        assert ctrl.card.get("temperature") == "22C"
        assert ctrl.card.get("humidity") == "45%"

    def test_get_date_format(self, ctrl: DashboardController) -> None:
        date = ctrl.get_date()
        assert len(date) == 10
        assert date[4] == "-" and date[7] == "-"

    def test_get_time_format(self, ctrl: DashboardController) -> None:
        assert ":" in ctrl.get_time()

    async def test_set_brightness_clamps(self, ctrl: DashboardController) -> None:
        await ctrl.set_brightness(200)
        assert ctrl.deck_brightness == 100
        await ctrl.set_brightness(-50)
        assert ctrl.deck_brightness == 0

    async def test_set_brightness_calls_deck(self, ctrl: DashboardController) -> None:
        mock_deck = MagicMock()
        mock_deck.set_brightness = AsyncMock()
        ctrl.bind_deck(mock_deck)
        await ctrl.set_brightness(75)
        mock_deck.set_brightness.assert_awaited_once_with(75)

    async def test_set_brightness_without_deck(self, ctrl: DashboardController) -> None:
        await ctrl.set_brightness(50)
        assert ctrl.deck_brightness == 50


# ===================================================================
# SceneController tests
# ===================================================================


class TestSceneController:
    """Tests for SceneController key creation."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch) -> SceneController:
        """A SceneController with a mocked load_package."""
        monkeypatch.setattr(
            "streamdeck.load_package", lambda _path: _iconkey_spec()
        )
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
        """Each key starts with default background/foreground colors from manifest."""
        for key in ctrl.keys:
            assert key.get("background") == "#1c1c1c"
            assert key.get("foreground") == "#dedede"

    async def test_press_swaps_colors(self, ctrl: SceneController) -> None:
        """key.dispatch(pressed=True) swaps fg/bg via the press handler."""
        key = ctrl.keys[0]
        await key.dispatch(pressed=True)
        assert key.get("background") == "#dedede"
        assert key.get("foreground") == "#1c1c1c"

    async def test_release_restores_colors(self, ctrl: SceneController) -> None:
        """A release after a press restores the original colors."""
        key = ctrl.keys[0]
        await key.dispatch(pressed=True)
        await key.dispatch(pressed=False)
        assert key.get("background") == "#1c1c1c"
        assert key.get("foreground") == "#dedede"

    async def test_press_release_requests_refresh(
        self, ctrl: SceneController
    ) -> None:
        """Press and release each call request_refresh on the key.

        The stub mimics ``Deck.refresh`` by clearing the dirty flag,
        which is what makes the auto-refresh wrapper idempotent in
        production: when a handler explicitly calls ``request_refresh``,
        the card is rendered and marked clean, so the wrapper's
        post-handler ``if is_dirty: refresh()`` check finds nothing to
        do.
        """
        key = ctrl.keys[0]
        refreshes = 0

        async def _refresh() -> None:
            nonlocal refreshes
            refreshes += 1
            key.mark_clean()

        key.set_refresh_callback(_refresh)
        await key.dispatch(pressed=True)
        await key.dispatch(pressed=False)
        assert refreshes == 2

    async def test_each_key_has_independent_handlers(
        self, ctrl: SceneController
    ) -> None:
        """Closure capture is per-key: pressing one key only affects that key."""
        first, second = ctrl.keys[0], ctrl.keys[1]
        await first.dispatch(pressed=True)
        # First is inverted, second is untouched.
        assert first.get("background") == "#dedede"
        assert second.get("background") == "#1c1c1c"


# ===================================================================
# FavoritesController tests
# ===================================================================


class TestFavoritesController:
    """Tests for FavoritesController key creation."""

    @pytest.fixture
    def ctrl(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FavoritesController:
        """A FavoritesController with mocked load_package calls."""
        specs = {"AudioCard.dui": _audio_spec(), "PictureKey.dui": _picturekey_spec()}
        monkeypatch.setattr(
            "streamdeck.load_package",
            lambda path: specs[Path(path).name],
        )
        audio = AudioController(MEDIA_CATALOG, initial_volume=0.3, packages_dir=tmp_path)
        return FavoritesController(MEDIA_CATALOG, audio, packages_dir=tmp_path)

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
# ScreenCycler tests
# ===================================================================


class TestScreenCycler:
    """Tests for the ScreenCycler controller."""

    def test_rejects_empty_screen_list(self) -> None:
        with pytest.raises(ValueError):
            ScreenCycler([])

    def test_starts_on_first_screen(self) -> None:
        cycler = ScreenCycler(["main", "settings", "info"])
        assert cycler.current == "main"

    async def test_advance_wraps_around(self) -> None:
        cycler = ScreenCycler(["a", "b", "c"])
        deck = MagicMock()
        deck.set_screen = AsyncMock()
        cycler.bind_deck(deck)

        await cycler.advance()
        assert cycler.current == "b"
        deck.set_screen.assert_awaited_with("b")

        await cycler.advance()
        assert cycler.current == "c"

        await cycler.advance()
        assert cycler.current == "a"
        # Three calls in total, in order.
        targets = [c.args[0] for c in deck.set_screen.await_args_list]
        assert targets == ["b", "c", "a"]

    async def test_advance_without_deck_is_noop(self) -> None:
        cycler = ScreenCycler(["a", "b"])
        # No bind_deck() -- must not raise and must not advance index.
        await cycler.advance()
        assert cycler.current == "a"

    async def test_attach_binds_event_to_advance(self) -> None:
        spec = _dash_spec()
        card = DuiCard(spec)
        cycler = ScreenCycler(["a", "b"])
        deck = MagicMock()
        deck.set_screen = AsyncMock()
        cycler.bind_deck(deck)

        cycler.attach(card)
        # The cycler registers a handler against the manifest event;
        # invoke it the same way the deck would.
        handler = card._events._handlers["next_screen"]
        await handler()
        assert cycler.current == "b"
        deck.set_screen.assert_awaited_with("b")

    async def test_attach_custom_event_name(self) -> None:
        # Build a dashboard-shaped spec but with a differently-named event.
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
        deck = MagicMock()
        deck.set_screen = AsyncMock()
        cycler.bind_deck(deck)

        cycler.attach(card, event="rotate_screen")
        handler = card._events._handlers["rotate_screen"]
        await handler()
        assert cycler.current == "y"
