"""Tests for deux.dui.iconify — icon fetch and cache."""

from __future__ import annotations

import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from deux.dui import iconify as iconify_mod
from deux.dui.iconify import (
    USER_AGENT,
    IconifyError,
    _parse_name,
    _read_disk_cache,
    _write_disk_cache,
    clear_cache,
    fetch_icon,
)

_SAMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" '
    'viewBox="0 0 24 24"><path fill="currentColor" d="M0 0"/></svg>'
)


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reset the iconify cache and redirect disk cache to tmp_path."""
    clear_cache(persistent=True)
    fake_dir = tmp_path / "iconify"
    fake_dir.mkdir()

    def _fake_get_dir() -> Path:
        fake_dir.mkdir(parents=True, exist_ok=True)
        return fake_dir

    monkeypatch.setattr(iconify_mod, "_get_disk_cache_dir", _fake_get_dir)
    monkeypatch.setattr(iconify_mod, "_disk_cache_dir", fake_dir)
    yield
    clear_cache(persistent=True)


@pytest.fixture(autouse=True)
def _bypass_ssrf():
    """Bypass SSRF checks in iconify tests (tested separately)."""
    with patch("deux.dui.iconify.check_url"):
        yield


class TestParseName:
    def test_simple(self):
        assert _parse_name("line-md:home") == ("line-md", "home")

    def test_multi_colon_rest_joined(self):
        """Only the first colon splits; the remainder becomes the name."""
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
            _parse_name(None)


class TestFetchIcon:
    def test_fetch_returns_svg(self):
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG) as mock:
            result = fetch_icon("line-md:home")
        assert result == _SAMPLE_SVG
        mock.assert_called_once()
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
            clear_cache(persistent=True)
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


class TestDiskCache:
    """Tests for persistent disk caching behaviour."""

    def test_disk_cache_written_on_fetch(self):
        """A successful network fetch writes the SVG to disk."""
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG):
            fetch_icon("mdi:check")
        assert _read_disk_cache("mdi", "check") == _SAMPLE_SVG

    def test_disk_cache_hit_avoids_network(self):
        """If the SVG is already on disk, no HTTP request is made."""
        _write_disk_cache("mdi", "cached", _SAMPLE_SVG)
        with patch.object(iconify_mod, "_http_get") as mock:
            result = fetch_icon("mdi:cached")
        mock.assert_not_called()
        assert result == _SAMPLE_SVG

    def test_negative_lookup_not_written_to_disk(self):
        """Failed fetches must NOT be persisted to disk."""
        with (
            patch.object(iconify_mod, "_http_get", return_value="404"),
            pytest.raises(IconifyError),
        ):
            fetch_icon("fake:nope")
        assert _read_disk_cache("fake", "nope") is None

    def test_network_error_not_written_to_disk(self):
        """Network errors must NOT be persisted to disk."""
        with patch.object(
            iconify_mod, "_http_get", side_effect=urllib.error.URLError("fail")
        ), pytest.raises(IconifyError):
            fetch_icon("fake:err")
        assert _read_disk_cache("fake", "err") is None

    def test_clear_cache_memory_only_preserves_disk(self):
        """clear_cache() without persistent=True keeps disk files."""
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG):
            fetch_icon("mdi:keep")
        clear_cache()
        assert _read_disk_cache("mdi", "keep") == _SAMPLE_SVG

    def test_clear_cache_persistent_removes_disk(self, tmp_path: Path):
        """clear_cache(persistent=True) wipes the disk cache directory."""
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG):
            fetch_icon("mdi:wipe")
        clear_cache(persistent=True)
        assert _read_disk_cache("mdi", "wipe") is None

    def test_corrupt_disk_file_treated_as_miss(self):
        """An empty file on disk is treated as a cache miss."""
        _write_disk_cache("mdi", "empty", "valid")
        # Overwrite with empty content to simulate corruption.
        from deux.dui.iconify import _disk_cache_path

        path = _disk_cache_path("mdi", "empty")
        path.write_text("", encoding="utf-8")
        assert _read_disk_cache("mdi", "empty") is None

    def test_disk_cache_survives_memory_clear(self):
        """After clearing only memory, disk cache still serves the icon."""
        with patch.object(iconify_mod, "_http_get", return_value=_SAMPLE_SVG) as mock:
            fetch_icon("mdi:persist")
            clear_cache()  # memory only
            result = fetch_icon("mdi:persist")
        # Only one HTTP call — second fetch came from disk.
        assert mock.call_count == 1
        assert result == _SAMPLE_SVG

    def test_write_disk_cache_handles_oserror(self, tmp_path: Path):
        """_write_disk_cache gracefully handles write failures."""
        with patch.object(
            iconify_mod, "_disk_cache_dir", tmp_path / "nonexistent" / "deep"
        ):
            # Should not raise — just logs.
            _write_disk_cache("x", "y", _SAMPLE_SVG)


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

        def fake_urlopen(req, timeout):
            captured["request"] = req
            return _FakeResp()

        with patch.object(iconify_mod.urllib.request, "urlopen", fake_urlopen):
            result = iconify_mod._http_get("https://example.test/x.svg")

        assert result == _SAMPLE_SVG
        req = captured["request"]
        assert req.get_header("User-agent") == USER_AGENT
