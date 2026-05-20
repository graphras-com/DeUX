"""Async wrappers for blocking HID I/O and input polling.

Bridges the synchronous ``hidapi`` calls into asyncio using a shared
:class:`~concurrent.futures.ThreadPoolExecutor`.  Provides an async
input polling loop that yields parsed events.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Callable

from deux.runtime._executor import get_executor
from deux.runtime.hid._ctypes_hidapi import HidApiError
from deux.runtime.hid.device import HidDevice
from deux.runtime.hid.protocol import InputEvent

logger = logging.getLogger(__name__)

#: Default HID write timeout in seconds.
HID_WRITE_TIMEOUT = 2.0

#: Default input polling interval in milliseconds.
DEFAULT_POLL_INTERVAL_MS = 50


class HidWriteTimeout(TimeoutError):
    """Raised when a blocking HID write exceeds the timeout threshold."""


async def async_hid_call(
    func: Callable[..., object],
    *args: object,
    timeout: float = HID_WRITE_TIMEOUT,
) -> object:
    """Run a blocking HID function in the shared executor with a timeout.

    Parameters
    ----------
    func : Callable
        The blocking function to execute (e.g. ``device.set_key_image``).
    *args : object
        Arguments to pass to *func*.
    timeout : float, default=HID_WRITE_TIMEOUT
        Maximum time in seconds before raising :class:`HidWriteTimeout`.

    Returns
    -------
    object
        The return value of *func*.

    Raises
    ------
    HidWriteTimeout
        If the call exceeds *timeout* seconds.
    HidApiError
        If the underlying HID operation fails.
    """
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(get_executor(), func, *args),
            timeout=timeout,
        )
    except TimeoutError:
        raise HidWriteTimeout(
            f"HID call {func.__name__} timed out after {timeout}s"
        ) from None


async def poll_input(
    device: HidDevice,
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS,
) -> AsyncIterator[InputEvent]:
    """Async generator that polls a device for input events.

    Runs ``device.read_input()`` in the executor at the specified interval,
    yielding parsed events as they arrive.  Stops when the device is closed
    or disconnected.

    Parameters
    ----------
    device : HidDevice
        An open HID device.
    poll_interval_ms : int, default=50
        HID read timeout per poll cycle in milliseconds.

    Yields
    ------
    InputEvent
        Parsed input events (key press, touch, encoder).

    Raises
    ------
    HidApiError
        If the device disconnects unexpectedly.
    """
    loop = asyncio.get_running_loop()
    executor = get_executor()

    while device.is_open:
        try:
            event = await loop.run_in_executor(
                executor, device.read_input, poll_interval_ms
            )
        except HidApiError:
            logger.warning("HID device disconnected during poll")
            break

        if event is not None:
            yield event
