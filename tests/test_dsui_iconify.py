"""Tests for deckui.dsui.iconify — icon fetch and cache."""

from __future__ import annotations

import urllib.error
from unittest.mock import patch

import pytest

from deckui.dsui import iconify as iconify_mod
from deckui.dsui.iconify import (
    USER_AGENT,
    IconifyError,
    _parse_name,
    clear_cache,
    fetch_icon,
)

_SAMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" '
    'viewBox="0 0 24 24"><path fill="currentColor" d="M0 0"/></svg>'
)


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Reset the iconify cache around every test."""
    clear_cache()
    yield
    clear_cache()


class TestParseName:
    def test_simple(self):
        assert _parse_name("line-md:home") == ("line-md", "home")

    def test_multi_colon_rest_joined(self):
        """Only the first colon splits; the remainder becomes the name."""
        # Iconify names shouldn't contain colons but be permissive on parse.
        prefix, icon = _parse_name("mdi:account:alt")
        assert prefix == "mdi"
        assert icon == "account:alt"

    def test_no_colon_raises(self):
        with pytest.raises(IconifyError, match="prefix:icon"):
            _parse_name("homeonly")

    def test_empty_raises(self):
        with pytest.raises(IconifyError, match="non-empty"):
            _parse_name("")

    def test_whitespace_only_raises(self):
        with pytest.raises(IconifyError, match="non-empty"):
            _parse_name("   ")

    def test_empty_prefix_raises(self):
        with pytest.raises(IconifyError, match="prefix:icon"):
            _parse_name(":home")

    def test_empty_icon_raises(self):
        with pytest.raises(IconifyError, match="prefix:icon"):
            _parse_name("mdi:")

    def test_non_string_raises(self):
        with pytest.raises(IconifyError, match="non-empty"):
            _parse_name(None)  # type: ignore[arg-type]


class TestFetchIcon:
    def test_fetch_returns_svg(self):
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG) as mock:
            result = fetch_icon("line-md:home")
        assert result == _SAMPLE_SVG
        mock.assert_called_once()
        # URL should combine the configured API base with the icon path.
        url_arg = mock.call_args.args[0]
        assert url_arg.endswith("/line-md/home.svg")

    def test_cache_hit_skips_http(self):
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG) as mock:
            fetch_icon("line-md:home")
            fetch_icon("line-md:home")
            fetch_icon("line-md:home")
        assert mock.call_count == 1

    def test_different_names_cached_separately(self):
        def side_effect(url: str) -> str:
            if "/home.svg" in url:
                return _SAMPLE_SVG
            return _SAMPLE_SVG.replace("M0 0", "M1 1")

        with patch.object(iconify_mod, "_http_get", side_effect=side_effect) as mock:
            a = fetch_icon("line-md:home")
            b = fetch_icon("line-md:settings")
            # repeat — should be cached
            fetch_icon("line-md:home")
            fetch_icon("line-md:settings")
        assert mock.call_count == 2
        assert a != b

    def test_invalid_name_raises(self):
        with pytest.raises(IconifyError):
            fetch_icon("no-colon")

    def test_404_body_raises_and_caches_failure(self):
        with patch.object(iconify_mod, "_http_get", return_value="404") as mock:
            with pytest.raises(IconifyError, match="not found"):
                fetch_icon("fake:missing")
            # Second call must not re-hit the network.
            with pytest.raises(IconifyError, match="previously failed"):
                fetch_icon("fake:missing")
        assert mock.call_count == 1

    def test_non_svg_body_treated_as_missing(self):
        with (
            patch.object(iconify_mod, "_http_get", return_value="random junk"),
            pytest.raises(IconifyError, match="not found"),
        ):
            fetch_icon("fake:weird")

    def test_network_error_raises_and_caches(self):
        err = urllib.error.URLError("unreachable")
        with patch.object(iconify_mod, "_http_get", side_effect=err) as mock:
            with pytest.raises(IconifyError, match="Failed to fetch"):
                fetch_icon("line-md:offline")
            # Negative lookup cached — no retry.
            with pytest.raises(IconifyError, match="previously failed"):
                fetch_icon("line-md:offline")
        assert mock.call_count == 1

    def test_os_error_also_caught(self):
        """A plain OSError from the socket layer is wrapped as IconifyError."""
        with (
            patch.object(iconify_mod, "_http_get", side_effect=OSError("boom")),
            pytest.raises(IconifyError, match="Failed to fetch"),
        ):
            fetch_icon("line-md:boom")

    def test_clear_cache_forces_refetch(self):
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG) as mock:
            fetch_icon("line-md:home")
            clear_cache()
            fetch_icon("line-md:home")
        assert mock.call_count == 2

    def test_clear_cache_drops_negative_entries(self):
        with patch.object(iconify_mod, "_http_get", return_value="404") as mock:
            with pytest.raises(IconifyError):
                fetch_icon("fake:gone")
            clear_cache()
            with pytest.raises(IconifyError):
                fetch_icon("fake:gone")
        assert mock.call_count == 2

    def test_uses_configured_api_url(self):
        with patch.object(iconify_mod, "ICONIFY_API_URL", "https://example.test"):
            with patch.object(
                iconify_mod, "_http_get", return_value=_SAMPLE_SVG
            ) as mock:
                fetch_icon("line-md:home")
            url_arg = mock.call_args.args[0]
            assert url_arg == "https://example.test/line-md/home.svg"


class TestHttpGet:
    """Verify transport-level behaviour of :func:`_http_get`."""

    def test_sends_user_agent_header(self):
        """The Iconify CDN 403s the default Python-urllib UA."""
        captured: dict[str, object] = {}

        class _FakeHeaders:
            def get_content_charset(self) -> str | None:
                return None

        class _FakeResp:
            headers = _FakeHeaders()

            def read(self) -> bytes:
                return _SAMPLE_SVG.encode("utf-8")

            def __enter__(self) -> _FakeResp:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

        def fake_urlopen(req, timeout):  # noqa: ARG001
            captured["request"] = req
            return _FakeResp()

        # urlopen normally gets a Request with a ``.headers`` mapping.
        # Capture it and verify the UA was attached.
        with patch.object(iconify_mod.urllib.request, "urlopen", fake_urlopen):
            result = iconify_mod._http_get("https://example.test/x.svg")

        assert result == _SAMPLE_SVG
        req = captured["request"]
        # urllib normalises header names to Capitalized form via
        # ``Request.add_header``; ``get_header`` does a case-insensitive lookup.
        assert req.get_header("User-agent") == USER_AGENT
