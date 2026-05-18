"""URL safety checks to mitigate SSRF via .dui package bindings.

By default, URLs targeting private, loopback, link-local, and cloud
metadata IP ranges are rejected.  An opt-in ``allow_private_urls``
flag can be set to permit LAN resources when explicitly needed.

Threat Model
------------
``.dui`` packages are designed to be distributed between users.  A
malicious package can embed ``image:`` bindings or ``iconify:`` URLs
that point at internal network endpoints, enabling Server-Side Request
Forgery (SSRF).  Blocked ranges include:

* Loopback — ``127.0.0.0/8``, ``::1``
* Private (RFC 1918) — ``10.0.0.0/8``, ``172.16.0.0/12``,
  ``192.168.0.0/16``
* Link-local — ``169.254.0.0/16``, ``fe80::/10``
* Cloud metadata — ``169.254.169.254``

Users who genuinely need LAN resources can call
:func:`set_allow_private_urls` to opt in.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_allow_private_urls: bool = False


class SSRFError(Exception):
    """Raised when a URL targets a blocked private/internal address."""


def set_allow_private_urls(allow: bool) -> None:
    """Opt in or out of private URL access.

    Parameters
    ----------
    allow : bool
        When ``True``, SSRF checks are disabled and private/internal
        URLs are permitted.  When ``False`` (the default), requests to
        loopback, RFC 1918, link-local, and metadata addresses are
        blocked.
    """
    global _allow_private_urls  # noqa: PLW0603
    _allow_private_urls = allow


def get_allow_private_urls() -> bool:
    """Return the current private-URL policy.

    Returns
    -------
    bool
        ``True`` if private URLs are currently allowed.
    """
    return _allow_private_urls


def _is_private_ip(addr: str) -> bool:
    """Return ``True`` if *addr* is a private, loopback, or link-local IP.

    Parameters
    ----------
    addr : str
        An IPv4 or IPv6 address string.

    Returns
    -------
    bool
        ``True`` when the address falls within a blocked range.
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def check_url(url: str) -> None:
    """Validate that *url* does not target a private/internal address.

    Resolves the hostname via DNS and checks whether any resulting IP
    address falls within a blocked range.  This guards against SSRF
    even when hostnames like ``localhost`` or attacker-controlled DNS
    resolve to private IPs.

    Parameters
    ----------
    url : str
        Fully-qualified HTTP(S) URL.

    Raises
    ------
    SSRFError
        If the resolved address is private/loopback/link-local and
        :func:`set_allow_private_urls` has not been called with
        ``True``.
    """
    if _allow_private_urls:
        return

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError(f"Cannot extract hostname from URL: {url!r}")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SSRFError(f"Cannot resolve hostname {hostname!r}: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip_str = str(sockaddr[0])
        if _is_private_ip(ip_str):
            raise SSRFError(
                f"URL {url!r} resolves to private address {ip_str} — "
                "blocked to prevent SSRF. Call "
                "deux.set_allow_private_urls(True) to allow."
            )
