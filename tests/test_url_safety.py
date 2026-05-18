"""Tests for deux._url_safety — SSRF mitigation for URL bindings."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from deux._url_safety import (
    SSRFError,
    _is_private_ip,
    check_url,
    get_allow_private_urls,
    set_allow_private_urls,
)


@pytest.fixture(autouse=True)
def _reset_policy():
    """Ensure private-URL policy is reset around every test."""
    set_allow_private_urls(False)
    yield
    set_allow_private_urls(False)


class TestIsPrivateIp:
    """Tests for :func:`_is_private_ip`."""

    @pytest.mark.parametrize(
        "addr",
        [
            "127.0.0.1",
            "127.0.0.2",
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.1.100",
            "169.254.169.254",
            "169.254.0.1",
            "::1",
            "0.0.0.0",
        ],
    )
    def test_private_addresses_detected(self, addr: str):
        assert _is_private_ip(addr) is True

    @pytest.mark.parametrize(
        "addr",
        [
            "8.8.8.8",
            "1.1.1.1",
            "93.184.216.34",
            "2606:4700::1111",
        ],
    )
    def test_public_addresses_allowed(self, addr: str):
        assert _is_private_ip(addr) is False

    def test_invalid_address_returns_false(self):
        assert _is_private_ip("not-an-ip") is False


class TestCheckUrl:
    """Tests for :func:`check_url`."""

    def test_public_url_passes(self):
        """A URL resolving to a public IP should not raise."""
        info = [(socket.AF_INET, 0, 0, "", ("93.184.216.34", 0))]
        with patch("deux._url_safety.socket.getaddrinfo", return_value=info):
            check_url("https://example.com/image.png")

    def test_localhost_blocked(self):
        info = [(socket.AF_INET, 0, 0, "", ("127.0.0.1", 0))]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            check_url("http://localhost/secret")

    def test_metadata_endpoint_blocked(self):
        info = [(socket.AF_INET, 0, 0, "", ("169.254.169.254", 0))]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            check_url("http://169.254.169.254/latest/meta-data/")

    def test_rfc1918_10_blocked(self):
        info = [(socket.AF_INET, 0, 0, "", ("10.0.0.5", 0))]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            check_url("http://internal.corp/api")

    def test_rfc1918_172_blocked(self):
        info = [(socket.AF_INET, 0, 0, "", ("172.16.5.1", 0))]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            check_url("http://nas.local/file")

    def test_rfc1918_192_blocked(self):
        info = [(socket.AF_INET, 0, 0, "", ("192.168.1.1", 0))]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            check_url("http://router.local/admin")

    def test_ipv6_loopback_blocked(self):
        info = [(socket.AF_INET6, 0, 0, "", ("::1", 0, 0, 0))]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            check_url("http://[::1]/")

    def test_dns_failure_raises_ssrf_error(self):
        with (
            patch(
                "deux._url_safety.socket.getaddrinfo",
                side_effect=socket.gaierror("nxdomain"),
            ),
            pytest.raises(SSRFError, match="Cannot resolve"),
        ):
            check_url("http://nonexistent.invalid/x")

    def test_no_hostname_raises(self):
        with pytest.raises(SSRFError, match="Cannot extract hostname"):
            check_url("http:///no-host")

    def test_allow_private_urls_bypasses_check(self):
        """When opted in, private URLs should be allowed."""
        set_allow_private_urls(True)
        info = [(socket.AF_INET, 0, 0, "", ("127.0.0.1", 0))]
        with patch("deux._url_safety.socket.getaddrinfo", return_value=info):
            check_url("http://localhost/ok")  # should not raise

    def test_multiple_addresses_one_private_blocked(self):
        """If any resolved address is private, the URL is blocked."""
        info = [
            (socket.AF_INET, 0, 0, "", ("93.184.216.34", 0)),
            (socket.AF_INET, 0, 0, "", ("127.0.0.1", 0)),
        ]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            check_url("http://dual.example.com/")


class TestPolicy:
    """Tests for :func:`set_allow_private_urls` / :func:`get_allow_private_urls`."""

    def test_default_is_false(self):
        assert get_allow_private_urls() is False

    def test_set_true(self):
        set_allow_private_urls(True)
        assert get_allow_private_urls() is True

    def test_set_false(self):
        set_allow_private_urls(True)
        set_allow_private_urls(False)
        assert get_allow_private_urls() is False


class TestIntegrationImageFetch:
    """Verify SSRF check is wired into :func:`fetch_image`."""

    def test_fetch_image_blocks_private_url(self):
        from deux.render.image_fetch import clear_cache, fetch_image

        clear_cache()
        info = [(socket.AF_INET, 0, 0, "", ("127.0.0.1", 0))]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            fetch_image("http://localhost/evil.png")
        clear_cache()

    def test_fetch_image_allows_public_url(self):
        """Public URLs pass SSRF check (network fetch itself is mocked)."""
        import io

        from PIL import Image

        from deux.render import image_fetch as mod
        from deux.render.image_fetch import clear_cache, fetch_image

        clear_cache()
        img = Image.new("RGB", (4, 4), "red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_data = buf.getvalue()

        info = [(socket.AF_INET, 0, 0, "", ("93.184.216.34", 0))]
        with (
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            patch.object(mod, "_http_get_bytes", return_value=png_data),
        ):
            result = fetch_image("https://example.com/ok.png")
        assert isinstance(result, Image.Image)
        clear_cache()


class TestIntegrationIconify:
    """Verify SSRF check is wired into :func:`fetch_icon`."""

    def test_fetch_icon_blocks_private_api_url(self):
        from deux.dui import iconify as iconify_mod
        from deux.dui.iconify import clear_cache, fetch_icon

        clear_cache(persistent=True)
        info = [(socket.AF_INET, 0, 0, "", ("127.0.0.1", 0))]
        with (
            patch.object(iconify_mod, "ICONIFY_API_URL", "http://localhost"),
            patch("deux._url_safety.socket.getaddrinfo", return_value=info),
            pytest.raises(SSRFError, match="private address"),
        ):
            fetch_icon("mdi:home")
        clear_cache(persistent=True)


class TestPackageExports:
    """Ensure SSRF utilities are accessible from the top-level package."""

    def test_ssrf_error_exported(self):
        import deux

        assert hasattr(deux, "SSRFError")
        assert deux.SSRFError is SSRFError

    def test_set_allow_private_urls_exported(self):
        import deux

        assert hasattr(deux, "set_allow_private_urls")
        assert callable(deux.set_allow_private_urls)
