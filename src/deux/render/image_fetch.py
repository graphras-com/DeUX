"""Remote image fetching and in-process caching.

Images are downloaded over HTTP(S) on first use and cached in memory
so subsequent renders hit no network.  The cache is process-local and
lives for the lifetime of the interpreter.
"""

from __future__ import annotations

import io
import logging
import threading
import urllib.error
import urllib.request

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 10.0

USER_AGENT = "deux/0.1.0 (+https://github.com/graphras-com/DeUX)"

_cache: dict[str, Image.Image | None] = {}
_cache_lock = threading.Lock()


class ImageFetchError(Exception):
    """Raised when a remote image cannot be fetched or decoded."""


def _validate_url(url: str) -> None:
    """Reject obviously invalid URLs.

    Parameters
    ----------
    url : str
        The URL string to validate.

    Raises
    ------
    ImageFetchError
        If *url* is empty or does not start with ``http://`` or ``https://``.
    """
    if not isinstance(url, str) or not url.strip():
        raise ImageFetchError(f"URL must be a non-empty string, got {url!r}")
    if not url.startswith(("http://", "https://")):
        raise ImageFetchError(
            f"URL must start with http:// or https://, got {url!r}"
        )


def _http_get_bytes(url: str) -> bytes:
    """Fetch *url* and return its body as raw bytes.

    Parameters
    ----------
    url : str
        Fully-qualified HTTP(S) URL.

    Returns
    -------
    bytes
        The raw response body.

    Raises
    ------
    urllib.error.URLError
        On network or HTTP errors.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT) as resp:
        return bytes(resp.read())


def fetch_image(url: str) -> Image.Image:
    """Fetch a remote image by URL and return it as a PIL Image.

    The result is cached in-process; subsequent calls with the same URL
    return the cached :class:`~PIL.Image.Image` immediately.  Negative
    lookups (network failure, invalid image data) are also cached so we
    do not retry broken URLs on every render.

    Parameters
    ----------
    url : str
        Fully-qualified HTTP(S) URL pointing to an image resource.

    Returns
    -------
    PIL.Image.Image
        The decoded image.

    Raises
    ------
    ImageFetchError
        If the URL is malformed, the network request fails, or the
        response cannot be decoded as a valid image.
    """
    _validate_url(url)

    with _cache_lock:
        if url in _cache:
            cached = _cache[url]
            if cached is None:
                raise ImageFetchError(f"Image at '{url}' previously failed to load")
            return cached.copy()

    try:
        data = _http_get_bytes(url)
    except (urllib.error.URLError, OSError) as exc:
        with _cache_lock:
            _cache[url] = None
        raise ImageFetchError(f"Failed to fetch image from '{url}': {exc}") from exc

    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # force full decode so errors surface now
    except (UnidentifiedImageError, OSError) as exc:
        with _cache_lock:
            _cache[url] = None
        raise ImageFetchError(
            f"Response from '{url}' is not a valid image: {exc}"
        ) from exc

    with _cache_lock:
        _cache[url] = img

    logger.debug("Fetched image from '%s' (%d bytes, %s)", url, len(data), img.size)
    return img.copy()


def clear_cache() -> None:
    """Drop all cached images.  Primarily intended for tests."""
    with _cache_lock:
        _cache.clear()
