"""Render-only element exports for deckboard UI composition."""

from __future__ import annotations

from .base import Element

__all__ = ["Element", "LargeDualValue", "SmallDualValue", "LargeText", "SmallText"]


def __getattr__(name: str):
    if name in {"LargeText", "SmallText"}:
        from .text import LargeText, SmallText

        return {"LargeText": LargeText, "SmallText": SmallText}[name]
    if name in {"LargeDualValue", "SmallDualValue"}:
        from .dual_value import LargeDualValue, SmallDualValue

        return {
            "LargeDualValue": LargeDualValue,
            "SmallDualValue": SmallDualValue,
        }[name]
    raise AttributeError(name)
