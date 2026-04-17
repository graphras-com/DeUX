"""Iconify icon fetching and in-process caching.

Icons are downloaded from the public Iconify HTTP API
(https://api.iconify.design) on first use and cached in memory so
subsequent renders hit no network.  The cache is process-local and
lives for the lifetime of the interpreter.
"""

from __future__ import annotations

import logging
import threading
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# Base URL of the Iconify HTTP API.  Exposed as a module attribute so
# tests can monkeypatch it.
ICONIFY_API_URL = "https://api.iconify.design"

# Timeout for HTTP requests, in seconds.
_REQUEST_TIMEOUT = 10.0

# User-Agent sent with icon requests.  The Iconify CDN returns 403 to
# the default ``Python-urllib/x.y`` UA, so we identify ourselves with
# the library name.  Exposed as a module attribute so tests and users
# can override it if needed.
USER_AGENT = "deckboard/0.1.0 (+https://github.com/graphras-com/deckboard)"

# In-process cache: maps "prefix:name" -> SVG source bytes.  ``None``
# marks a name that has been looked up and failed to load, so we do not
# spam the Iconify API for a broken icon reference.
_cache: dict[str, str | None] = {}
_cache_lock = threading.Lock()


class IconifyError(Exception):
    """Raised when an Iconify icon cannot be resolved."""


def _parse_name(name: str) -> tuple[str, str]:
    """Split a ``"prefix:icon"`` name into its parts.

    Raises:
        IconifyError: If *name* is empty or not in ``prefix:icon`` form.
    """
    if not isinstance(name, str) or not name.strip():
        raise IconifyError(f"Iconify name must be a non-empty string, got {name!r}")
    if ":" not in name:
        raise IconifyError(
            f"Iconify name '{name}' must be in 'prefix:icon' form (e.g. 'line-md:home')"
        )
    prefix, _, icon = name.partition(":")
    if not prefix or not icon:
        raise IconifyError(
            f"Iconify name '{name}' must be in 'prefix:icon' form (e.g. 'line-md:home')"
        )
    return prefix, icon


def _http_get(url: str) -> str:
    """Fetch *url* and return its body decoded as UTF-8 text.

    Sends :data:`USER_AGENT` as the ``User-Agent`` header because the
    Iconify CDN rejects requests using the default ``Python-urllib``
    identifier with HTTP 403.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset)


def fetch_icon(name: str) -> str:
    """Fetch an Iconify icon by ``prefix:icon`` name.

    The result is cached in-process; subsequent calls return the
    cached SVG source immediately.  Negative lookups (404 / network
    failure) are also cached so we do not retry broken references on
    every render.

    Args:
        name: Icon identifier in ``"prefix:icon"`` form, e.g.
            ``"line-md:home"``.

    Returns:
        The raw SVG source string as served by the Iconify API.

    Raises:
        IconifyError: If the name is malformed, the icon does not
            exist, or the network request fails.
    """
    prefix, icon = _parse_name(name)
    key = f"{prefix}:{icon}"

    with _cache_lock:
        if key in _cache:
            cached = _cache[key]
            if cached is None:
                raise IconifyError(f"Iconify icon '{key}' previously failed to load")
            return cached

    url = f"{ICONIFY_API_URL}/{prefix}/{icon}.svg"
    try:
        body = _http_get(url)
    except (urllib.error.URLError, OSError) as exc:
        with _cache_lock:
            _cache[key] = None
        raise IconifyError(f"Failed to fetch Iconify icon '{key}': {exc}") from exc

    # The Iconify API returns a 200 with literal text "404" in the body
    # when the icon does not exist.  Treat that as a failed lookup.
    stripped = body.strip()
    if stripped == "404" or not stripped.startswith("<"):
        with _cache_lock:
            _cache[key] = None
        raise IconifyError(f"Iconify icon '{key}' not found")

    with _cache_lock:
        _cache[key] = body

    logger.debug("Fetched Iconify icon '%s' (%d bytes)", key, len(body))
    return body


def clear_cache() -> None:
    """Drop all cached Iconify icons.  Primarily intended for tests."""
    with _cache_lock:
        _cache.clear()
