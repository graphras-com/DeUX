"""Physical slot types for keys and encoders."""

from __future__ import annotations

from ..button import Button
from ..dial import Dial

KeySlot = Button
EncoderSlot = Dial

__all__ = ["EncoderSlot", "KeySlot"]
