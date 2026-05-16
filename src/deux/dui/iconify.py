"""Iconify icon fetching with in-memory and persistent disk caching.

Icons are downloaded from the public Iconify HTTP API
(https://api.iconify.design) on first use and cached both in memory
and on disk so subsequent runs avoid network requests entirely.

The disk cache uses ``platformdirs`` to resolve a platform-appropriate
cache directory (``~/.cache/deux/iconify`` on Linux,
``~/Library/Caches/deux/iconify`` on macOS, etc.).

Negative lookups (404 / network failure) are cached in memory only so
a process restart retries previously-failed icons.
"""

from __future__ import annotations

import logging
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import cast

import platformdirs

logger = logging.getLogger(__name__)

ICONIFY_API_URL = "https://api.iconify.design"

_REQUEST_TIMEOUT = 10.0

USER_AGENT = "deux/0.1.0 (+https://github.com/graphras-com/DeUX)"

_cache: dict[str, str | None] = {}
_cache_lock = threading.Lock()

_disk_cache_dir: Path | None = None
_disk_cache_dir_lock = threading.Lock()


class IconifyError(Exception):
    """Raised when an Iconify icon cannot be resolved."""


def _get_disk_cache_dir() -> Path:
    """Return the persistent cache directory, creating it lazily.

    Returns
    -------
    Path
        Platform-appropriate cache directory for Iconify SVGs.
    """
    global _disk_cache_dir  # noqa: PLW0603
    if _disk_cache_dir is not None:
        return _disk_cache_dir
    with _disk_cache_dir_lock:
        # Double-check after acquiring the lock.
        if _disk_cache_dir is not None:
            return _disk_cache_dir
        cache_root = Path(platformdirs.user_cache_dir("deux")) / "iconify"
        cache_root.mkdir(parents=True, exist_ok=True)
        _disk_cache_dir = cache_root
        return _disk_cache_dir


def _disk_cache_path(prefix: str, icon: str) -> Path:
    """Return the on-disk path for a given icon.

    Parameters
    ----------
    prefix : str
        Icon-set prefix (e.g. ``"mdi"``).
    icon : str
        Icon name within the set (e.g. ``"home"``).

    Returns
    -------
    Path
        File path where the cached SVG is (or would be) stored.
    """
    return _get_disk_cache_dir() / prefix / f"{icon}.svg"


def _read_disk_cache(prefix: str, icon: str) -> str | None:
    """Read an icon from the disk cache.

    Parameters
    ----------
    prefix : str
        Icon-set prefix.
    icon : str
        Icon name.

    Returns
    -------
    str or None
        The cached SVG text, or ``None`` if not present or unreadable.
    """
    path = _disk_cache_path(prefix, icon)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    return text


def _write_disk_cache(prefix: str, icon: str, svg: str) -> None:
    """Write an icon SVG to the disk cache.

    Parameters
    ----------
    prefix : str
        Icon-set prefix.
    icon : str
        Icon name.
    svg : str
        SVG source text to persist.
    """
    path = _disk_cache_path(prefix, icon)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
    except OSError:
        logger.debug("Failed to write icon cache file %s", path, exc_info=True)


def _parse_name(name: str) -> tuple[str, str]:
    """Split a ``"prefix:icon"`` name into its parts.

    Raises
    ------
    IconifyError
        If *name* is empty or not in ``prefix:icon`` form.
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
        return cast("str", resp.read().decode(charset))


def fetch_icon(name: str) -> str:
    """Fetch an Iconify icon by ``prefix:icon`` name.

    The lookup order is: in-memory cache, disk cache, network.
    Successful fetches are stored in both caches.  Negative lookups
    (404 / network failure) are cached in memory only so a restart
    retries previously-failed icons.

    Parameters
    ----------
    name : str
        Icon identifier in ``"prefix:icon"`` form, e.g.
        ``"line-md:home"``.

    Returns
    -------
    str
        The raw SVG source string as served by the Iconify API.

    Raises
    ------
    IconifyError
        If the name is malformed, the icon does not
        exist, or the network request fails.
    """
    prefix, icon = _parse_name(name)
    key = f"{prefix}:{icon}"

    # 1. In-memory cache
    with _cache_lock:
        if key in _cache:
            cached = _cache[key]
            if cached is None:
                raise IconifyError(f"Iconify icon '{key}' previously failed to load")
            return cached

    # 2. Disk cache
    disk_hit = _read_disk_cache(prefix, icon)
    if disk_hit is not None:
        with _cache_lock:
            _cache[key] = disk_hit
        logger.debug("Loaded Iconify icon '%s' from disk cache", key)
        return disk_hit

    # 3. Network fetch
    url = f"{ICONIFY_API_URL}/{prefix}/{icon}.svg"
    try:
        body = _http_get(url)
    except (urllib.error.URLError, OSError) as exc:
        with _cache_lock:
            _cache[key] = None
        raise IconifyError(f"Failed to fetch Iconify icon '{key}': {exc}") from exc

    stripped = body.strip()
    if stripped == "404" or not stripped.startswith("<"):
        with _cache_lock:
            _cache[key] = None
        raise IconifyError(f"Iconify icon '{key}' not found")

    with _cache_lock:
        _cache[key] = body

    _write_disk_cache(prefix, icon, body)

    logger.debug("Fetched Iconify icon '%s' (%d bytes)", key, len(body))
    return body


def clear_cache(*, persistent: bool = False) -> None:
    """Drop all cached Iconify icons.

    Parameters
    ----------
    persistent : bool, default=False
        When ``True``, also remove the on-disk cache directory.
        By default only the in-memory cache is cleared.
    """
    global _disk_cache_dir  # noqa: PLW0603
    with _cache_lock:
        _cache.clear()
    if persistent:
        with _disk_cache_dir_lock:
            if _disk_cache_dir is not None:
                shutil.rmtree(_disk_cache_dir, ignore_errors=True)
                _disk_cache_dir = None
