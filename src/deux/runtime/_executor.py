"""Shared thread-pool executor for blocking HID I/O.

Provides a single module-level :class:`~concurrent.futures.ThreadPoolExecutor`
used by :class:`Deck`, :class:`DeckManager`, and :func:`list_devices` instead
of per-instance pools.  This eliminates idle-thread waste at multi-deck scale
and ensures deterministic shutdown via :func:`shutdown_executor`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

_MAX_WORKERS = 4

_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """Return the shared executor, creating it on first access.

    The pool is lazily initialised so that import-time side-effects are
    avoided.  All callers share the same instance.

    Returns
    -------
    ThreadPoolExecutor
        The shared executor.
    """
    global _executor  # noqa: PLW0603
    if _executor is None or _executor._shutdown:
        _executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)
    return _executor


def shutdown_executor(*, wait: bool = True) -> None:
    """Shut down the shared executor.

    Parameters
    ----------
    wait : bool, default=True
        If ``True``, block until all in-flight tasks complete, ensuring
        no HID locks are held non-deterministically.
    """
    global _executor  # noqa: PLW0603
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None
