"""Touch-strip card components."""

from __future__ import annotations

from .base import Card

__all__ = ["Card", "StackCard", "StatusCard"]


def __getattr__(name: str):
    if name == "StackCard":
        from .stack import StackCard

        return StackCard
    if name == "StatusCard":
        from .status import StatusCard

        return StatusCard
    raise AttributeError(name)
