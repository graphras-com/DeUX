"""Common base exception for the deux library.

All public exception classes in deux inherit from :class:`DeuxError`,
allowing callers to catch any library error with a single handler::

    try:
        ...
    except deux.DeuxError:
        ...
"""

from __future__ import annotations


class DeuxError(Exception):
    """Root exception for every error raised by the deux library."""
